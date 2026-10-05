"""Integración con Z2 (Gestor de Carpetas ART).

Tiene DOS mitades distintas, conviene no mezclarlas:
  - Importar (leer la BASE por Neon, usuario z1_lector): trae clientes para cargar en Z1.
  - buscar_coincidencias (consultar un ENDPOINT por HTTP): avisa si el cliente que se está
    por cargar ya tiene carpeta en Z2. Es la que evita cobrarle dos veces a la misma persona.

Las dos son SOLO LECTURA: Z1 nunca escribe en la base de Z2. Y las dos son a prueba de caídas:
si Z2 está apagado, sin internet, con la URL mal puesta o devolviendo cualquier cosa, devuelven
lista vacía y Z1 sigue funcionando exactamente como antes. La integración suma información,
nunca puede romper la app.

Z2 publica en su propia base de Neon. Z1 lee SOLO cuatro columnas de esa base --
apellido, nombre, telefono y recomendado_por -- con un usuario de solo lectura
(z1_lector) que no puede ver nada más: ni lesion, ni notas, ni DNI, ni la tabla
de usuarios. Los cuatro campos van a la ficha de Z1 como nombre, contacto (REC.)
y recomendado por.

La dirección es de una sola vía: Z1 nunca escribe en la base de Z2.

IMPORTAR (lee la base de Z2 por Neon, con el usuario de solo lectura z1_lector)

Reglas de coincidencia:
  - Si el caso trae teléfono, se busca por teléfono (solo dígitos).
    - Coincide  -> no se crea nada; queda anotado que ya tiene carpeta en Z2.
    - No coincide -> se crea el cliente en estado NUEVO.
  - Si el caso NO trae teléfono (raro), se busca por nombre EXACTO.
    - Coincide  -> no se crea nada; se deja para revisión manual.
    - No coincide -> se crea el cliente en estado NUEVO.

Todo se normaliza como ya lo hace Z1 en el resto del código: mayúsculas, sin
tildes, y teléfono solo dígitos. Si Z1 pre-normalizara distinto a como se
guardó, aparecerían duplicados sin que nada lo indique.
"""
from dataclasses import dataclass, field

import config
import db

# Cuántos clientes crea en una sola pasada. Es una red de contención: si algo
# saliera mal, el daño queda acotado y se ve enseguida.
MAX_IMPORTADOS_POR_PASADA = 200

# Lo que se escribe en NOTAS del cliente importado. Sirve para que, mirando la
# ficha, se vea de dónde salió y por qué existe.
NOTA_ORIGEN_Z2 = "Importado desde Z2 (carpeta ART)."

ESTADO_NUEVO = "NUEVO"


class IntegracionDesactivada(Exception):
    """No se configuró la conexión con Z2. La importación está apagada, no rota."""


class ErrorDeConexion(Exception):
    """Falló la consulta a la base de Z2. No se importó nada."""


@dataclass
class Resultado:
    """Lo que pasó en una pasada. No escribe nada: solo informa."""

    total_en_z2: int = 0
    nuevos: list = field(default_factory=list)
    ya_existentes: list = field(default_factory=list)
    para_revisar: list = field(default_factory=list)

    @property
    def resumen(self) -> str:
        return (
            f"{self.total_en_z2} en Z2 · {len(self.nuevos)} nuevos · "
            f"{len(self.ya_existentes)} ya estaban · {len(self.para_revisar)} para revisar"
        )


def _conexion_z2() -> str:
    connection_string = config.obtener_z2_read_url().strip()
    if not connection_string:
        raise IntegracionDesactivada()
    return connection_string


def leer_casos_de_z2() -> list[dict]:
    """Trae de Z2 solo lo que Z1 necesita. Levanta error si algo falla; el
    llamador decide si lo muestra o lo ignora."""
    import psycopg2

    try:
        conn = psycopg2.connect(_conexion_z2(), connect_timeout=15)
    except psycopg2.Error as exc:
        raise ErrorDeConexion(f"No se pudo conectar a la base de Z2: {exc}") from exc

    try:
        with conn.cursor() as cur:
            # Las 4 columnas que el usuario de solo lectura puede ver. Pedir una
            # quinta haría fallar toda la consulta, no devolver campos de menos:
            # por eso el SELECT es explícito y no un "select *".
            cur.execute(
                """
                SELECT COALESCE(apellido, ''),
                       COALESCE(nombre, ''),
                       COALESCE(telefono, ''),
                       COALESCE(recomendado_por, ''),
                       COALESCE(estado, ''),
                       COALESCE(categoria, ''),
                       COALESCE(fecha_accidente::text, ''),
                       COALESCE(art, ''),
                       COALESCE(dni, '')
                FROM public.cases
                """
            )
            filas = cur.fetchall()
    except psycopg2.Error as exc:
        raise ErrorDeConexion(f"Falló la consulta a Z2: {exc}") from exc
    finally:
        conn.close()

    return [
        {
            "apellido": f[0],
            "nombre": f[1],
            "telefono": f[2],
            "recomendado_por": f[3],
            "estado_planilla": f[4],
            "categoria": f[5],
            "fecha_accidente": f[6][:10],
            "art": f[7],
            "dni": f[8],
        }
        for f in filas
    ]


def comparar(casos: list[dict]) -> Resultado:
    """Compara los casos de Z2 contra los clientes de Z1. No escribe nada."""
    resultado = Resultado(total_en_z2=len(casos))

    with db.get_conn() as conn:
        filas = conn.execute(
            "SELECT nombre, COALESCE(contacto, '') AS contacto FROM clientes"
        ).fetchall()

    por_telefono: dict[str, str] = {}
    por_nombre: set[str] = set()
    for nombre_crudo, contacto_crudo in filas:
        telefono = db.normalizar_telefono(contacto_crudo)
        if telefono:
            por_telefono[telefono] = nombre_crudo
        nombre = db.normalizar_nombre(nombre_crudo)
        if nombre:
            por_nombre.add(nombre)

    for caso in casos:
        nombre = db.normalizar_nombre(f"{caso['apellido']} {caso['nombre']}".strip())
        telefono = db.normalizar_telefono(caso["telefono"])
        # Recomendado por va tal cual viene de Z2, sin normalizar: es un nombre de
        # persona o estudio, no algo con tildes que haya que comparar.
        entrada = {
            "nombre": nombre,
            "telefono": caso["telefono"],
            "recomendado_por": caso.get("recomendado_por") or "",
        }

        if telefono:
            existente = por_telefono.get(telefono)
            if existente:
                resultado.ya_existentes.append({**entrada, "con": existente})
            else:
                resultado.nuevos.append(entrada)
                por_telefono[telefono] = nombre
            continue

        if nombre in por_nombre:
            resultado.para_revisar.append(entrada)
        else:
            resultado.nuevos.append(entrada)

    return resultado


def importar(resultado: Resultado) -> list[int]:
    """Crea en Z1 los clientes que la comparación marcó como nuevos. Devuelve
    los ids creados. Si algo falla, corta: es preferible importar la mitad que
    dejar la base a medio camino."""
    if not resultado.nuevos:
        return []

    estado = db.obtener_id_estado(ESTADO_NUEVO)
    if estado is None:
        raise ErrorDeConexion(f"El estado {ESTADO_NUEVO} no existe en Z1.")

    creados = []
    pendientes = resultado.nuevos[:MAX_IMPORTADOS_POR_PASADA]
    if len(resultado.nuevos) > MAX_IMPORTADOS_POR_PASADA:
        print(
            f"[Z2] Ojo: {len(resultado.nuevos)} nuevos, se importan "
            f"{MAX_IMPORTADOS_POR_PASADA} por pasada."
        )

    for cliente in pendientes:
        cliente_id = db.crear_cliente(
            nombre=cliente["nombre"],
            contacto=cliente["telefono"],
            estado_id=estado,
            notas=NOTA_ORIGEN_Z2,
            recomendado_por=cliente.get("recomendado_por", ""),
        )
        creados.append(cliente_id)

    return creados


def sincronizar(crear: bool = False) -> Resultado:
    """Pasada completa: lee de Z2, compara con Z1 y, si crear=True, importa.

    Con crear=False es una simulación: no escribe nada y sirve para ver qué
    pasaría antes de hacerlo.
    """
    resultado = comparar(leer_casos_de_z2())
    if crear:
        importar(resultado)
    return resultado


def probar_conexion() -> tuple[bool, str]:
    """Para el botón 'Probar conexión' del popup de configuración. Acá SÍ se
    levantan errores, porque es una acción explícita del usuario y necesita
    saber qué pasó."""
    try:
        casos = leer_casos_de_z2()
    except IntegracionDesactivada:
        return False, "Falta configurar la conexión de solo lectura de Z2."
    except ErrorDeConexion as exc:
        return False, str(exc)

    if not casos:
        return True, "Conectado a Z2. La base no tiene carpetas todavía."

    muestra = casos[0]
    return True, (
        f"Conectado a Z2: {len(casos)} carpeta(s). "
        f"Por ejemplo '{muestra['apellido']} {muestra['nombre']}'."
    )


# --------------------------------------------------------------------------
# Consulta por HTTP al endpoint de coincidencias de Z2.
#
# A diferencia de lo de arriba, esto NO lee la base: le pregunta a Z2 por su
# API, que devuelve solo 4 campos por coincidencia. Se usa al guardar un cliente
# nuevo para avisar "este señor ya tiene carpeta en Z2" antes de crearlo acá.
# --------------------------------------------------------------------------

# Corto a propósito: se consulta al GUARDAR, no en cada tecla, así que no hay
# búsquedas viejas en vuelo. Aun así un timeout corto hace que un Z2 lento no
# deje la ventana esperando.
TIMEOUT_SEGUNDOS = 8.0


def buscar_coincidencias_en_z2(nombre: str, telefono: str) -> list[dict]:
    """Devuelve [{origen:'z2', id, nombre, telefono, detalle}, ...]. Vacío si Z2
    no está configurado, está apagado o contesta cualquier cosa."""
    import json
    import urllib.error
    import urllib.parse
    import urllib.request

    url = config.obtener_z2_url().strip()
    token = config.obtener_z2_token().strip()
    if not url or not token:
        return []

    destino = (
        f"{url.rstrip('/')}/api/integracion/coincidencias?"
        + urllib.parse.urlencode({"nombre": nombre, "telefono": telefono})
    )
    peticion = urllib.request.Request(destino, headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - red caída, Z2 apagado, 401, 503, HTML...
        return []  # la integración suma información: si falla, Z1 sigue igual

    crudos = datos.get("coincidencias")
    if not isinstance(crudos, list):
        return []

    # Z2 es otro programa: si mañana manda un campo raro o falta alguno, el panel
    # tiene que seguir funcionando en vez de romper con un KeyError.
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
    ]


def probar_coincidencias() -> tuple[bool, str]:
    """Para el botón 'Probar conexión'. Acá SÍ se levantan errores, porque es una
    acción explícita del usuario."""
    import json
    import urllib.error
    import urllib.request

    url = config.obtener_z2_url().strip()
    token = config.obtener_z2_token().strip()
    if not url or not token:
        return False, "Falta configurar la URL y el token de integración de Z2."

    destino = f"{url.rstrip('/')}/api/integracion/coincidencias?nombre=&telefono="
    peticion = urllib.request.Request(destino, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, "Token rechazado. Revisá que coincida con INTEGRATION_TOKEN de Z2."
        if exc.code == 503:
            return False, "Z2 tiene la integración deshabilitada (falta INTEGRATION_TOKEN)."
        return False, f"Z2 respondió HTTP {exc.code}."
    except Exception:  # noqa: BLE001
        return False, f"No se pudo llegar a Z2: revisé la URL y la conexión."
    return True, f"Conectado a {url}."
