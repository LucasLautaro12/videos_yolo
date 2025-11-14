from flask import Flask, request, jsonify, send_from_directory
from app.config import UPLOAD_DIR, PROCESSED_DIR, YOLO_MAP
from app.utils.utils import descargar_video, obtener_duracion_formato
from app.processing.processing import ejecutar_procesamiento
import os

app = Flask(__name__)

app = Flask(__name__)

UPLOAD_FOLDER = UPLOAD_DIR
PROCESSED_FOLDER = PROCESSED_DIR

@app.route('/subir_video', methods=['POST'])
def subir_video():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "Se requiere una URL o ruta local del video"}), 400

    video_url = data['url']

    # --- Detectar si es local o remoto ---
    if video_url.startswith("http://") or video_url.startswith("https://"):
        # Caso 1: remoto → descargar
        nombre_archivo = video_url.split("/")[-1].split("?")[0]
        local_path = os.path.join(UPLOAD_FOLDER, nombre_archivo)
        print(f"⬇️ Descargando: {video_url}")
        descargar_video(video_url, local_path)
        forzar_todas = True
    else:
        # Caso 2: local → usar directamente la ruta
        nombre_archivo = os.path.basename(video_url)
        local_path = video_url
        print(f"📂 Usando archivo local: {local_path}")
        forzar_todas = False

    output_path = os.path.join(PROCESSED_FOLDER, f"procesado_{nombre_archivo}")

    try:
        duracion_str, duracion_min = obtener_duracion_formato(local_path)
        final, guardados = ejecutar_procesamiento(
            local_path,
            output_path,
            duracion_min=duracion_min,
            forzar_todas=forzar_todas
        )

        return jsonify({
            "mensaje": "Video procesado exitosamente",
            "archivo_procesado": f"/descargar/procesado_{nombre_archivo}",
            "frames_guardados": guardados
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/descargar/<filename>', methods=['GET'])
def descargar_video_route(filename):
    return send_from_directory(PROCESSED_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)