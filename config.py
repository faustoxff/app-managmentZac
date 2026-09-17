"""Resolución de rutas de datos, válida tanto en modo script como empaquetado (.exe)."""
import os
import sys
from pathlib import Path

APP_NAME = "GestorClientes"


def get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".local" / "share"
    data_dir = base / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DB_PATH = get_data_dir() / "clientes.db"


def carpeta_fotos_pendientes() -> Path:
    carpeta = get_data_dir() / "fotos_pendientes"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta
