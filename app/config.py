#config.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "videos_subidos"
PROCESSED_DIR = BASE_DIR / "videos_procesados"
STATIC_DIR = BASE_DIR / "static"

LOGO_PATH = STATIC_DIR / "Logo_MPA.png"

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

YOLO_MAP = {
    "persona": 0,
    "bicicleta": 1,
    "auto": 2,
    "moto": 3,
    "colectivo": 5,
    "camión": 7,
    "semáforo": 9,
    "gato": 15,
    "perro": 16,
    "caballo": 17,
    "mochila": 24,
    "televisor": 62,
    "notebook": 63,
    "mouse": 64,
    "teclado": 66,
    "celular": 67,
    "microondas": 68,
    "horno": 69,
    "tostadora": 70,
    "heladera": 72
}

YOLO_CLASSES = list(YOLO_MAP.keys())

# --- Configuración App ---
PAGE_TITLE = "Procesamiento Inteligente de Videos"
LOGO_FILENAME = "Logo_MPA.png"
ALLOWED_VIDEO_TYPES = ["mp4", "mov", "avi", "mkv"]
LOGO_PATH = BASE_DIR / LOGO_FILENAME
