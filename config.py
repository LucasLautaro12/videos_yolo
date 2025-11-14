from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "videos_subidos"
PROCESSED_DIR = BASE_DIR / "videos_procesados"
STATIC_DIR = BASE_DIR / "static"

LOGO_PATH = STATIC_DIR / "Logo_MPA.png"

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)


# --- Configuración YOLO ---
# Mapeo ID → Nombre (para detección)
YOLO_MAP = {
    0: "persona",
    1: "bicicleta",
    2: "auto",
    3: "moto",
    5: "colectivo",
    7: "camión",
    9: "semáforo",
    15: "gato",
    16: "perro",
    17: "caballo",
    24: "mochila",
    62: "televisor",
    63: "notebook",
    64: "mouse",
    66: "teclado",
    67: "celular",
    68: "microondas",
    69: "horno",
    70: "tostadora",
    72: "heladera"
}

# Mapeo Nombre → ID (para filtros)
YOLO_NAME_TO_ID = {v: k for k, v in YOLO_MAP.items()}

YOLO_CLASSES = list(YOLO_MAP.values())

# --- Configuración App ---
PAGE_TITLE = "Procesamiento Inteligente de Videos"
LOGO_FILENAME = "Logo_MPA.png"
ALLOWED_VIDEO_TYPES = ["mp4", "mov", "avi", "mkv"]
LOGO_PATH = BASE_DIR / LOGO_FILENAME