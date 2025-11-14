import cv2
import numpy as np
import time
import subprocess
import shutil
import os
import requests
from pathlib import Path
from skimage.metrics import structural_similarity as ssim
from moviepy import VideoFileClip, concatenate_videoclips
from ultralytics import YOLO
from app.config import UPLOAD_DIR, PROCESSED_DIR, YOLO_MAP

# Cargar modelo YOLO una vez
yolo_model = YOLO("yolov8m.pt")

def descargar_video(url, save_path):
    """Descarga un video desde URL"""
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

def obtener_duracion_formato(video_path):
    """Devuelve duración HH:MM:SS y en minutos"""
    clip = VideoFileClip(video_path)
    duracion_seg = int(clip.duration)
    clip.close()
    minutos = duracion_seg // 60
    segundos = duracion_seg % 60
    return f"{minutos:02d}:{segundos:02d}", duracion_seg / 60

def obtener_resolucion_redimensionada(w, h, min_w=320, min_h=240):
    """Calcula resolución reducida proporcional"""
    target_w = min_w
    new_h = int(h * (target_w / w))
    if new_h < min_h:
        target_h = min_h
        new_w = int(w * (target_h / h))
        return new_w, target_h
    return target_w, new_h

def calcular_ssim_promedio(video_path, step=4, max_frames=2000, frac=0.2):
    """Calcula SSIM promedio y std tomando una muestra limitada"""

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"No se pudo abrir el video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    limite = min(int(total_frames * frac), max_frames)

    ret, prev_frame = cap.read()
    if not ret:
        cap.release()
        raise Exception("No se pudo leer el primer frame para calcular SSIM promedio")

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    h, w = prev_gray.shape
    resize_w, resize_h = obtener_resolucion_redimensionada(w, h)
    prev_resized = cv2.resize(prev_gray, (resize_w, resize_h))

    ssim_scores = []
    count = 0

    while count < limite:
        # saltar step-1 frames
        for _ in range(step - 1):
            if not cap.grab():
                break
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized_gray = cv2.resize(gray, (resize_w, resize_h))
        score = ssim(prev_resized, resized_gray)
        ssim_scores.append(score)
        prev_resized = resized_gray
        count += step

    cap.release()

    if not ssim_scores:
        return 1.0, 0.0

    ssim_array = np.array(ssim_scores)
    return np.mean(ssim_array), np.std(ssim_array)

def ajustar_umbral(promedio, desviacion, default=0.85):
    """Ajusta el umbral dinámicamente"""
    if promedio > 0.79:
        umbral = promedio - desviacion
    else:
        umbral = promedio
    return max(0.55, min(umbral, 0.98))

def timestamp_frame(frame, segundos, prefix="Tiempo del video original: "):
    """
    Dibuja el tiempo HH:MM:SS del video (según 'segundos') en la esquina superior izquierda.
    Si 'prefix' no es None, antepone ese texto (p. ej., 'Tiempo del video original: ').
    """
    t_str = time.strftime("%H:%M:%S", time.gmtime(segundos))
    text = f"{prefix}{t_str}" if prefix is not None else t_str

    # Estilo
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.9
    thickness = 2
    margin = 10

    # Medir rectángulo de fondo
    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = margin, margin + th

    # Fondo semitransparente para legibilidad
    overlay = frame.copy()
    cv2.rectangle(overlay, (x - 8, y - th - 8), (x + tw + 8, y + 8), (0, 0, 0), -1)
    alpha = 0.45
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    # Texto (contorno + relleno)
    cv2.putText(frame, text, (x, y), font, font_scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), font, font_scale, (0, 255, 0), thickness, cv2.LINE_AA)

    return frame

def asegurar_video_web(input_path):
    """
    Convierte un video a un formato compatible con navegadores web usando FFmpeg.
    """
    web_compatible_path = input_path.with_name(f"{input_path.stem}_web.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-c:v", "libx264", "-preset", "fast",
        "-movflags", "+faststart", "-pix_fmt", "yuv420p",
        str(web_compatible_path)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return web_compatible_path
    except FileNotFoundError:
        raise Exception("Comando 'ffmpeg' no encontrado. Asegúrate de que FFmpeg esté instalado y en el PATH del sistema.")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error durante la conversión con FFmpeg: {e.stderr}")