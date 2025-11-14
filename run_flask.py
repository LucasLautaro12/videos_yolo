import sys
from pathlib import Path

# Agregar el directorio raíz al path de Python
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app.flask_app import app

if __name__ == "__main__":
    app.run(debug=True)
