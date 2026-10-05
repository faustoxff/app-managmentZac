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


MODELO_IA_DEFAULT = "google/gemma-4-31b-it:free"
# Los modelos gratis de OpenRouter rotan seguido (dejan de estar disponibles y aparecen otros
# nuevos) — si este default deja de funcionar, la lista de modelos con visión disponibles hoy
# está en https://openrouter.ai/models?fmt=cards&input_modalities=image&max_price=0, o
# cambiando el campo "Modelo" desde Configuración > Configurar IA.


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


def obtener_neon_connection_string() -> str:
    """Cadena de conexión de Neon (postgres://usuario:password@host/db) para el backup en la
    nube. Se consigue en el panel de Neon (Connection Details). Vacío si nunca se configuró."""
    return _leer_config().get("neon_connection_string", "")


def guardar_neon_connection_string(connection_string: str) -> None:
    datos = _leer_config()
    datos["neon_connection_string"] = connection_string.strip()
    _escribir_config(datos)


def obtener_z2_url() -> str:
    """URL base de Z2 (Gestor de Carpetas ART), sin la ruta /api... Ej: https://mi-z2.onrender.com
    Vacío si la integración con Z2 nunca se configuró."""
    return _leer_config().get("z2_url", "")


def guardar_z2_url(url: str) -> None:
    datos = _leer_config()
    datos["z2_url"] = url.strip().rstrip("/")
    _escribir_config(datos)


def obtener_z2_token() -> str:
    """Token de integración que Z2 exige en el header Authorization. Es el INTEGRATION_TOKEN
    del .env de Z2; no es el login de un usuario de Z2. Vacío si nunca se configuró."""
    return _leer_config().get("z2_token", "")


def guardar_z2_token(token: str) -> None:
    datos = _leer_config()
    datos["z2_token"] = token.strip()
    _escribir_config(datos)


def obtener_z2_read_url() -> str:
    """Cadena de conexión de SOLO LECTURA a la base de Z2, para la importación
    de clientes (ver z2_sync.py). Es el usuario z1_lector, que únicamente puede
    leer 3 columnas de public.cases: apellido, nombre y telefono. No usar la del
    dueño de la base. Vacío si la importación nunca se configuró."""
    return _leer_config().get("z2_read_url", "")


def guardar_z2_read_url(connection_string: str) -> None:
    datos = _leer_config()
    datos["z2_read_url"] = connection_string.strip()
    _escribir_config(datos)


def obtener_backup_automatico() -> bool:
    return bool(_leer_config().get("backup_automatico", False))


def guardar_backup_automatico(activo: bool) -> None:
    datos = _leer_config()
    datos["backup_automatico"] = bool(activo)
    _escribir_config(datos)


def obtener_recordatorios_avisados_hoy(hoy: str) -> list[int]:
    """IDs de clientes cuyo aviso de recordatorio ("Fulano viene hoy") ya se mostró en el día
    `hoy` (AAAA-MM-DD) — para no repetir el cartel si se reabre la app el mismo día. Se guarda
    junto con la fecha: si `hoy` no coincide con lo guardado, es de otro día y no cuenta."""
    datos = _leer_config().get("recordatorios_avisados", {})
    if datos.get("fecha") != hoy:
        return []
    return datos.get("ids", [])


def agregar_recordatorios_avisados_hoy(hoy: str, ids_nuevos: list[int]) -> None:
    ya_avisados = set(obtener_recordatorios_avisados_hoy(hoy))
    ya_avisados.update(ids_nuevos)
    datos = _leer_config()
    datos["recordatorios_avisados"] = {"fecha": hoy, "ids": sorted(ya_avisados)}
    _escribir_config(datos)
