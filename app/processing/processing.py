# processing.py
import cv2
import subprocess
from pathlib import Path
from skimage.metrics import structural_similarity as ssim

from app.utils.utils import (
    calcular_ssim_promedio,
    ajustar_umbral,
    timestamp_frame,
    yolo_model,       # cargado una sola vez en utils
)
from app.config import YOLO_MAP
from app.utils.paralelo import procesar_en_paralelo


def procesar_video(video_path, output_path, step=1, offset=0, target_classes=None):
    """
    Procesa un video (o chunk):
      - SSIM full=True: conserva frame si ALGUNA ventana < umbral (umbral dinámico).
      - YOLO: 1x si hay detección; 2.5x si no hay (ajustable).
      - Escribe MP4 temporal con overlay de tiempo ORIGINAL (abs_idx/fps + offset).
      - Re-encode final con FFmpeg concatenando segmentos 1x / 2.5x.
      - Sin deriva: reloj = abs_idx/fps. No usamos POS_MSEC.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"No se pudo abrir el video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    temp_out = Path(output_path).with_name(f"{Path(output_path).stem}_temp.mp4")
    out = cv2.VideoWriter(str(temp_out), cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))

    # Umbral dinámico según tu lógica
    promedio, desviacion = calcular_ssim_promedio(video_path, step=step)
    umbral = ajustar_umbral(promedio, desviacion)
    print(f"📊 SSIM promedio={promedio:.4f}, std={desviacion:.4f}, umbral={umbral:.4f}")

    prev_gray = None
    frame_count, guardados = 0, 0

    # Estado de detección (para colas) y armado de segmentos de velocidad
    deteccion_activa = False
    frames_despues_deteccion = 0
    max_frames_despues_deteccion = 20  # conserva algunos frames luego de la última detección

    segmentos = []            # (inicio_segundos, fin_segundos, velocidad)
    seg_inicio = 0.0
    velocidad_actual = 2.5      # por defecto rápido (2.5x)

    # ---- Reloj robusto: índice absoluto de frame del original
    abs_idx = 0  # cuenta TODOS los frames consumidos (incluidos los saltados con grab)

    while True:
        # Salteo de frames cuando NO hay detección activa, para acelerar
        if not deteccion_activa and step > 1:
            for _ in range(step - 1):
                if not cap.grab():
                    break
                abs_idx += 1  # avanzar el reloj por cada frame saltado

        ret, frame = cap.read()
        if not ret:
            break

        abs_idx += 1  # consumimos 1 frame más
        frame_count += 1

        # Tiempo EXACTO del frame actual (0-based) sin depender de POS_MSEC
        segundos = (abs_idx - 1) / fps
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ---------- SSIM por mapa (full=True) ----------
        if not deteccion_activa:
            if prev_gray is None:
                prev_gray = gray
            else:
                prev_small = cv2.resize(prev_gray, (320, 240))
                cur_small  = cv2.resize(gray,      (320, 240))
                _score, sim_map = ssim(prev_small, cur_small, full=True)
                # Si TODAS las ventanas >= umbral => descartar; si alguna < umbral => conservar
                if not (sim_map < umbral).any():
                    prev_gray = gray
                    continue

        # ---------- YOLO detección ----------
        frame = timestamp_frame(frame, segundos + offset)
        hay_deteccion = False
        try:
            results = yolo_model(frame, verbose=False)
            for box in results[0].boxes:
                cls_id = int(box.cls)
                if target_classes is None or cls_id in target_classes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    label = yolo_model.names[cls_id]
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, label, (x1, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    hay_deteccion = True
        except Exception:
            hay_deteccion = False

        # Ajuste de velocidad deseada
        nueva_vel = 1 if hay_deteccion else 2.5
        if nueva_vel != velocidad_actual:
            seg_fin = segundos
            if seg_fin > seg_inicio:
                segmentos.append((seg_inicio, seg_fin, velocidad_actual))
            seg_inicio = segundos
            velocidad_actual = nueva_vel

        # Escribimos el frame al MP4 temporal (con overlays)
        out.write(frame)
        guardados += 1
        prev_gray = gray

        # Ventana de "cola" luego de una detección para no cortar abrupto
        if hay_deteccion:
            deteccion_activa = True
            frames_despues_deteccion = 0
        elif deteccion_activa:
            frames_despues_deteccion += 1
            if frames_despues_deteccion >= max_frames_despues_deteccion:
                deteccion_activa = False

        if frame_count % 100 == 0:
            print(f"➡️ Procesados {frame_count} frames, guardados {guardados}")

    # Cierre de recursos
    duracion_chunk = abs_idx / fps
    cap.release()
    out.release()

    # Cerrar último segmento abierto
    if duracion_chunk > seg_inicio:
        segmentos.append((seg_inicio, duracion_chunk, velocidad_actual))

    # ---------- Re-encode final con FFmpeg ----------
    if not segmentos:
        # Caso sin detecciones: todo a 2.5x
        print("⚠️ Chunk sin detecciones → todo a x2.5")
        cmd = [
            "ffmpeg", "-y", "-i", str(temp_out),
            "-filter:v", "setpts=0.4*PTS",           # 1 / 2.5 = 0.4
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an", str(output_path)
        ]
        subprocess.run(cmd, check=True)
        temp_out.unlink(missing_ok=True)
        return str(output_path), guardados

    # Construcción de filter_complex para concatenar segmentos con velocidades
    filtros = []
    maps_v = ""
    for i, (ini, fin, vel) in enumerate(segmentos):
        filtros.append(
            f"[0:v]trim=start={ini}:end={fin},setpts=PTS-STARTPTS[v{i}];\n"
            f"[v{i}]setpts={1/vel}*PTS[v{i}f];\n"
        )
        maps_v += f"[v{i}f]"

    if len(segmentos) > 1:
        filtros.append(f"{maps_v}concat=n={len(segmentos)}:v=1:a=0[v];\n")
        map_args = ["-map", "[v]"]
    else:
        map_args = ["-map", "[v0f]"]

    filter_complex = "".join(filtros)

    cwd = Path(output_path).parent
    fname_in = Path(temp_out).name
    fname_out = Path(output_path).name

    # Guardamos el script de filtros para simplificar el llamado
    script_path = cwd / (Path(fname_out).stem + ".fcs")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(filter_complex)

    cmd = [
        "ffmpeg", "-y", "-i", str(fname_in),
        "-filter_complex_script", script_path.name,
        *map_args,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an", str(fname_out)
    ]
    subprocess.run(cmd, check=True, cwd=str(cwd))

    # Limpieza
    try:
        script_path.unlink(missing_ok=True)
        temp_out.unlink(missing_ok=True)
    except Exception:
        pass

    return str(output_path), guardados


def ejecutar_procesamiento(video_path, output_path, duracion_min,
                           target_classes=None, forzar_todas=False):
    """
    Wrapper compatible con app_streamlit.py y app_flask.py.
    - duracion_min: ya viene calculado por la UI; se usa solo para decidir paralelización.
    - forzar_todas: si True, se ignoran filtros y se detectan todas las clases YOLO.
    """
    if forzar_todas:
        target_classes = list(YOLO_MAP.values())

    if duracion_min > 10:
        final, guardados = procesar_en_paralelo(
            procesar_video,
            video_path,
            output_path,
            step=4,
            chunk_minutes=10,
            procesos=4,
            target_classes=target_classes
        )
    else:
        final, guardados = procesar_video(
            video_path,
            output_path,
            step=2,
            target_classes=target_classes
        )

    return final, guardados
