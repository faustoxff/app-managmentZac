"""Consulta a Z2 (Gestor de Carpetas ART) para avisar si el cliente que se está por cargar en
Z1 ya existe como carpeta del otro programa.

Deliberadamente SOLO LECTURA y a prueba de caídas: Z1 nunca escribe en la base de Z2, y si Z2
está apagado, sin internet, con la URL mal configurada o devolviendo cualquier cosa raro,
esta función devuelve una lista vacía y Z1 sigue funcionando exactamente como antes. La
integración suma información, nunca puede romper la app.

La consulta se hace en un hilo aparte (ver ui/cliente_form.py) porque Z2 es una app web y la
red puede tardar: si se llamara en el hilo de la UI, la ventana se congelaría en cada tecla.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

import config

# Corto a propósito: la búsqueda es EN VIVO, se dispara a cada tecla tipeada con un debounce
# de 300ms. Un timeout largo dejaría requests viejos en vuelo y, cuando llegaran, taparían
# los resultados de una consulta más nueva.
TIMEOUT_SEGUNDOS = 3.0
MAX_RESULTADOS = 20


class IntegracionNoConfigurada(Exception):
    """Falta la URL o el token: la integración está apagada, no rota."""


def _config() -> tuple[str, str]:
    url = config.obtener_z2_url().strip()
    token = config.obtener_z2_token().strip()
    if not url or not token:
        raise IntegracionNoConfigurada()
    return url, token


def _url_coincidencias(url: str, nombre: str, telefono: str) -> str:
    params = urllib.parse.urlencode({"nombre": nombre, "telefono": telefono})
    return f"{url.rstrip('/')}/api/integracion/coincidencias?{params}"


def buscar_coincidencias(nombre: str, telefono: str) -> list[dict]:
    """Devuelve [{origen, id, nombre, telefono, dni, detalle}, ...]. Lista vacía si algo falla.

    Nunca levanta excepciones: el llamador la dispara en un hilo cuyo resultado se pinta en un
    panel informativo, así que un error acá no tiene a quién avisarle. Para depurar queda el
    log de diagnóstico de Z1, que ya usa db._log_diagnostico().
    """
    import db

    try:
        url, token = _config()
    except IntegracionNoConfigurada:
        return []  # integración apagada a propósito: es lo normal si nadie la configuró

    destino = _url_coincidencias(url, nombre, telefono)
    peticion = urllib.request.Request(destino, headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        db._log_diagnostico(f"integración Z2: HTTP {exc.code} consultando coincidencias")
        return []
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        db._log_diagnostico(f"integración Z2: no se pudo consultar ({exc})")
        return []
    except (ValueError, UnicodeDecodeError) as exc:
        # Respuesta 200 pero no es el JSON esperado (un proxy, una página de error del server).
        db._log_diagnostico(f"integración Z2: respuesta ilegible ({exc})")
        return []

    crudos = datos.get("coincidencias")
    if not isinstance(crudos, list):
        return []

    # Se filtra a lo que el panel sabe mostrar. Z2 es otro programa: si mañana agrega un campo
    # raro, el panel tiene que seguir funcionando igual en vez de romper con un KeyError.
    return [
        {
            "origen": "z2",
            "id": str(c.get("id") or ""),
            "nombre": str(c.get("nombre") or ""),
            "telefono": str(c.get("telefono") or ""),
            "detalle": str(c.get("detalle") or ""),
        }
        for c in crudos
        if isinstance(c, dict)
    ][:MAX_RESULTADOS]


def probar_conexion() -> tuple[bool, str]:
    """Para el botón 'Probar conexión' del popup de configuración. Acá SÍ sewanten errores,
    porque es una acción explícita del usuario y necesita saber qué pasó."""
    url, token = _config()
    destino = _url_coincidencias(url, "", "")
    peticion = urllib.request.Request(destino, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, "El token fue rechazado. Revisá que coincida con INTEGRATION_TOKEN de Z2."
        if exc.code == 503:
            return False, "Z2 tiene la integración deshabilitada (falta INTEGRATION_TOKEN)."
        return False, f"Z2 respondió HTTP {exc.code}."
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"No se pudo llegar a Z2: {exc}"
    except (ValueError, UnicodeDecodeError):
        return False, "Z2 respondió algo que no es JSON. Revisá la URL."
    return True, f"Conectado a {url}."
