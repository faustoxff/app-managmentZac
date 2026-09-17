"""Extracción de (nombre, teléfono) desde una foto usando la API de Anthropic (visión), como
alternativa al OCR local (ocr_import.py) para hojas con formatos raros donde Tesseract no da
buenos resultados. Necesita internet y una API key propia — a diferencia del resto de la app,
que funciona 100% offline."""
import base64
import json
import mimetypes
import re

import config
from db import FilaImport

INSTRUCCION_DEFAULT = "Extraé nombre completo y teléfono de cada persona en esta hoja."

MODELO = "claude-sonnet-5"

PROMPT_FORMATO = (
    ' Respondé ÚNICAMENTE con JSON válido: una lista de objetos con las claves "nombre" y '
    '"telefono" (string), sin texto adicional antes ni después, y sin bloque de código '
    "markdown alrededor. Si no hay teléfono para alguien, usá un string vacío en esa clave. "
    "Si no encontrás a nadie, respondé con una lista vacía: []."
)


class IAImportError(Exception):
    """Error de red, de API, o de formato de respuesta — siempre con un mensaje pensado para
    mostrarse directo en un messagebox, sin exponer detalles técnicos innecesarios."""


class FaltaApiKey(IAImportError):
    """Señal específica (no un string mágico) para que la UI muestre el popup de API key y
    reintente, en vez de mostrar esto como un error genérico."""


def _requerir_cliente_anthropic():
    try:
        import anthropic
    except ImportError as exc:
        raise IAImportError(
            "Falta instalar la librería anthropic:\n\npip install anthropic"
        ) from exc

    api_key = config.obtener_api_key()
    if not api_key:
        raise FaltaApiKey()

    return anthropic.Anthropic(api_key=api_key)


def _extraer_json(texto: str) -> list:
    """La IA debería responder solo JSON, pero por las dudas toleramos que venga envuelto en
    ```json ... ``` o con texto alrededor: buscamos el primer '[' hasta el último ']'."""
    texto = texto.strip()
    match = re.search(r"\[.*\]", texto, re.DOTALL)
    if not match:
        raise IAImportError("La IA no devolvió una lista JSON reconocible.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise IAImportError(f"La IA devolvió JSON inválido: {exc}") from exc


def extraer_candidatos(path_imagen: str, instruccion: str) -> list[FilaImport]:
    client = _requerir_cliente_anthropic()

    media_type = mimetypes.guess_type(path_imagen)[0] or "image/jpeg"
    if media_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        media_type = "image/jpeg"

    try:
        with open(path_imagen, "rb") as f:
            imagen_b64 = base64.standard_b64encode(f.read()).decode("ascii")
    except OSError as exc:
        raise IAImportError(f"No se pudo leer la imagen: {exc}") from exc

    instruccion = (instruccion or INSTRUCCION_DEFAULT).strip() + PROMPT_FORMATO

    try:
        respuesta = client.messages.create(
            model=MODELO,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": imagen_b64},
                        },
                        {"type": "text", "text": instruccion},
                    ],
                }
            ],
        )
    except Exception as exc:  # noqa: BLE001 - cubrimos toda la superficie de errores del SDK
        raise IAImportError(_mensaje_error_api(exc)) from exc

    texto_respuesta = "".join(
        bloque.text for bloque in respuesta.content if getattr(bloque, "type", None) == "text"
    )
    datos = _extraer_json(texto_respuesta)

    candidatos = []
    for item in datos:
        if not isinstance(item, dict):
            continue
        nombre = str(item.get("nombre", "")).strip()
        telefono = str(item.get("telefono", "")).strip()
        if not nombre and not telefono:
            continue
        candidatos.append(FilaImport(nombre=nombre, contacto=telefono, origen="IA"))
    return candidatos


def _mensaje_error_api(exc: Exception) -> str:
    texto = str(exc).lower()
    if "authenticat" in texto or "401" in texto or "invalid x-api-key" in texto or "api key" in texto:
        return (
            "La API key no es válida. Podés cambiarla desde el menú "
            "Configuración > Cambiar API key de IA."
        )
    if "timeout" in texto or "timed out" in texto:
        return "Se agotó el tiempo de espera. Revisá tu conexión a internet e intentá de nuevo."
    if "connection" in texto or "network" in texto or "resolve" in texto:
        return "No hay conexión a internet (o no se pudo contactar la API). Intentá de nuevo."
    return f"Error al consultar la IA: {exc}"
