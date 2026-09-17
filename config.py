"""Resolución de rutas de datos, válida tanto en modo script como empaquetado (.exe)."""
import json
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


CONFIG_PATH = get_data_dir() / "config.json"


def _leer_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _escribir_config(datos: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # no crashear si no se puede escribir (disco lleno, permisos, etc.)


MODELO_IA_DEFAULT = "meta-llama/llama-3.2-11b-vision-instruct:free"


def obtener_api_key() -> str:
    """API key de OpenRouter (openrouter.ai/keys) para "Importar con IA". Vacío si nunca se
    configuró."""
    return _leer_config().get("openrouter_api_key", "")


def guardar_api_key(api_key: str) -> None:
    datos = _leer_config()
    datos["openrouter_api_key"] = api_key.strip()
    _escribir_config(datos)


def obtener_modelo_ia() -> str:
    return _leer_config().get("modelo_ia", MODELO_IA_DEFAULT)


def guardar_modelo_ia(modelo: str) -> None:
    datos = _leer_config()
    datos["modelo_ia"] = modelo.strip() or MODELO_IA_DEFAULT
    _escribir_config(datos)
