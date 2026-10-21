"""Extracción de (nombre, teléfono) desde una foto usando un modelo con visión vía OpenRouter
(https://openrouter.ai), como alternativa al OCR local (ocr_import.py) para hojas con formatos
raros donde Tesseract no da buenos resultados. Necesita internet y una API key propia — a
diferencia del resto de la app, que funciona 100% offline.

OpenRouter expone una API compatible con la de OpenAI (mismo formato de mensajes/imagen), así
que usamos el SDK `openai` apuntando a su base_url en vez de necesitar un SDK propio."""
import base64
import json
import mimetypes
import re

import config
from db import FilaImport

INSTRUCCION_DEFAULT = (
    "Extraé nombre completo (apellido y nombre) y teléfono de cada persona en esta hoja. "
    "Ignorá encabezados, fechas, profesionales e instituciones. Escribí el teléfono solo con "
    "dígitos, sin espacios ni guiones. Si un dato no se lee bien, dejalo vacío en vez de inventarlo."
)

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


def _requerir_cliente_openrouter():
    try:
        import openai
    except ImportError as exc:
        raise IAImportError("Falta instalar la librería openai:\n\npip install openai") from exc

    api_key = config.obtener_api_key()
    if not api_key:
        raise FaltaApiKey()

    base_url = config.PROVEEDORES_IA[config.obtener_proveedor_ia()]["base_url"]
    return openai.OpenAI(api_key=api_key, base_url=base_url)


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
    import openai  # ya validado disponible por _requerir_cliente_openrouter()

    client = _requerir_cliente_openrouter()
    modelo = config.obtener_modelo_ia()
    proveedor = config.obtener_proveedor_ia()
    nombre_proveedor = config.PROVEEDORES_IA[proveedor]["nombre"]
    es_openrouter = proveedor == "openrouter"
    # Este sufijo se agrega a los errores para que se vea con qué proveedor y modelo falló:
    # alcanza para detectar, por ejemplo, que la key de Gemini está cargada pero el proveedor
    # activo sigue siendo OpenRouter.
    contexto = f'\n\n(Proveedor: {nombre_proveedor} · modelo: "{modelo}")'

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
        respuesta = client.chat.completions.create(
            model=modelo,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruccion},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{imagen_b64}"},
                        },
                    ],
                }
            ],
        )
    except openai.RateLimitError as exc:
        raise IAImportError(
            "Se alcanzó el límite de uso gratuito de la IA (error 429).\n\n"
            "Esperá un minuto y probá de nuevo (la capa gratis permite pocas fotos por minuto "
            "y un tope por día)."
            + (" Con OpenRouter también podés cargar crédito." if es_openrouter else "")
            + contexto
        ) from exc
    except openai.AuthenticationError as exc:
        raise IAImportError(
            "La API key de la IA no es válida. Podés cambiarla desde el menú "
            "Configuración > Configurar IA. Chequeá que el proveedor elegido sea el de tu key."
            + contexto
        ) from exc
    except openai.APITimeoutError as exc:
        raise IAImportError(
            "Se agotó el tiempo de espera. Revisá tu conexión a internet e intentá de nuevo."
        ) from exc
    except openai.APIConnectionError as exc:
        raise IAImportError(
            f"No hay conexión a internet (o no se pudo contactar a {nombre_proveedor}). Intentá de nuevo."
        ) from exc
    except openai.NotFoundError as exc:
        if es_openrouter:
            ayuda = (
                "los modelos gratis rotan seguido. Cambiá el modelo desde Configuración > "
                "Configurar IA (lista de modelos con visión disponibles ahora: "
                'openrouter.ai/models, filtrá por "image input" y "free").'
            )
        else:
            ayuda = (
                "revisá el nombre en Configuración > Configurar IA (el recomendado es "
                f'"{config.PROVEEDORES_IA[proveedor]["modelo_default"]}"). Si ese nombre es el '
                "correcto, chequeá que el proveedor elegido sea el de tu key."
            )
        raise IAImportError(
            f'El modelo configurado ("{modelo}") no está disponible en {nombre_proveedor}: '
            f"{ayuda}{contexto}"
        ) from exc
    except openai.APIStatusError as exc:
        if exc.status_code == 402:
            raise IAImportError(
                "No hay crédito cargado en la cuenta de OpenRouter (error 402).\n\n"
                "Cargá crédito en openrouter.ai/settings/credits (con unos pocos dólares "
                "alcanza para muchísimas fotos), o usá un modelo gratis (con :free al final "
                "del nombre) desde Configuración > Configurar IA."
            ) from exc
        raise IAImportError(
            f"Error al consultar la IA (código {exc.status_code}): {exc}{contexto}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - cubrimos toda la superficie de errores del SDK
        raise IAImportError(f"Error al consultar la IA: {exc}{contexto}") from exc

    texto_respuesta = respuesta.choices[0].message.content or ""
    datos = _extraer_json(texto_respuesta)

    candidatos = []
    for item in datos:
        if not isinstance(item, dict):
            continue
        nombre = str(item.get("nombre", "")).strip().upper()
        telefono = str(item.get("telefono", "")).strip()
        if not nombre and not telefono:
            continue
        candidatos.append(FilaImport(nombre=nombre, contacto=telefono, origen="IA"))
    return candidatos
