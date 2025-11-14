# paralelo.py
import os
import subprocess
import shutil
from multiprocessing import Pool

def dividir_video(input_path, chunk_minutes=10, output_dir="chunks"):
    """
    Corta el video en chunks exactos usando seek preciso:
    - Accurate seek: -i input -ss start -t dur  (re-encode)
    - Evita saltos a keyframes y corrimientos de varios segundos.
    """
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    chunk_secs = int(chunk_minutes * 60)

    # Duración total en segundos con ffprobe
    def _probe_duration(path):
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ]
        out = subprocess.check_output(cmd).decode().strip()
        return float(out)

    total = _probe_duration(input_path)
    n_chunks = (int(total) + chunk_secs - 1) // chunk_secs

    chunk_paths = []
    for i in range(n_chunks):
        start = i * chunk_secs
        dur = min(chunk_secs, total - start + 0.01)  # +epsilon para cerrar bien
        out_path = os.path.join(output_dir, f"chunk_{i:03d}.mp4")

        # Accurate seek (re-encode). NO usar -c copy.
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,        # input primero
            "-ss", str(start),       # luego -ss (accurate seek)
            "-t",  str(dur),
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",
            out_path
        ]
        subprocess.run(cmd, check=True)
        chunk_paths.append((out_path, start))  # guardamos path + offset real

    return chunk_paths


def _tarea_procesar(args):
    """
    Ejecuta procesar_video sobre un chunk.
    args = (func, chunk_path, offset, output_dir, idx, kwargs)
    """
    func, chunk_path, offset, output_dir, idx, kwargs = args
    out_path = os.path.join(output_dir, f"proc_{idx:03d}.mp4")
    try:
        final, frames = func(chunk_path, out_path, offset=offset, **kwargs)
        return final, frames
    except Exception as e:
        print(f"❌ Chunk {idx:03d} falló: {e}")
        return None, 0


def unir_videos(paths, output_path):
    """
    Concatena MP4s por lista. Usa concat demuxer.
    """
    list_file = "file_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        output_path
    ]
    subprocess.run(cmd, check=True)
    os.remove(list_file)
    return output_path


def procesar_en_paralelo(func, input_path, output_path,
                         step=4, chunk_minutes=10, procesos=4, **kwargs):
    """
    Divide input en chunks con seek preciso, procesa cada uno en paralelo
    pasando offset=start real, y concatena.
    """
    chunks = dividir_video(input_path, chunk_minutes=chunk_minutes, output_dir="chunks")

    tareas = []
    out_dir = "chunks_proc"
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    for idx, (chunk_path, start) in enumerate(chunks):
        # IMPORTANTÍSIMO: offset = start REAL del chunk en el original
        tarea = (func, chunk_path, start, out_dir, idx, {"step": step, **kwargs})
        tareas.append(tarea)

    with Pool(processes=procesos) as pool:
        resultados = pool.map(_tarea_procesar, tareas)

    out_paths = [r[0] for r in resultados if r[0] is not None]
    frames_totales = sum(r[1] for r in resultados if r[0] is not None)

    if not out_paths:
        raise Exception("❌ Todos los chunks fallaron en el procesamiento.")

    final_output = unir_videos(out_paths, output_path)

    # Limpieza
    if os.path.exists("chunks"):
        shutil.rmtree("chunks")
    if os.path.exists("chunks_proc"):
        shutil.rmtree("chunks_proc")

    print(f"✅ Procesamiento paralelo completado: {len(out_paths)} chunks procesados")
    return final_output, frames_totales
