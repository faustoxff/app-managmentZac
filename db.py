"""Acceso a SQLite. Cada operación abre y cierra su propia conexión (context manager)."""
import sqlite3
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from config import DB_PATH
from models import Cliente, Estado

ESTADOS_SEED = [
    ("Nuevo", "#8b5cf6"),
    ("Descartado", "#6b7280"),
    ("OK", "#16a34a"),
    ("Cliente", "#2563eb"),
    ("Viene", "#06b6d4"),
    ("Esperar", "#f59e0b"),
    ("No contesta", "#ef4444"),
]
ESTADOS_SEED_NOMBRES = {nombre for nombre, _ in ESTADOS_SEED}

# Paleta anterior de ESTADOS_SEED (algunos tonos quedaban muy parecidos entre sí, en especial
# los cálidos de "Viene"/"Esperar"/"No contesta"). Se usa solo para detectar, en la migración,
# qué instalaciones todavía tienen el color por defecto viejo sin tocar y así poder
# actualizarlas al nuevo sin pisar un color que el usuario haya elegido a mano.
_ESTADOS_SEED_COLOR_VIEJO = {
    "Nuevo": "#8b5cf6",
    "Descartado": "#9ca3af",
    "OK": "#22c55e",
    "Cliente": "#3b82f6",
    "Viene": "#eab308",
    "Esperar": "#f97316",
    "No contesta": "#ef4444",
}

# Mapea nombres del esquema VIEJO de estados (5 estados) a su equivalente en el esquema
# actual. Se usa una sola vez por estado viejo encontrado, en _migrar_estados_a_nuevo_esquema:
# cualquier estado que el usuario haya creado o renombrado a mano (no está acá) NO se toca.
#
# OJO: "Nuevo" NO va acá. El esquema viejo tenía un "Nuevo" con otro significado, pero el
# esquema actual TAMBIÉN tiene un estado llamado "Nuevo" (ESTADOS_SEED, el default para
# clientes importados). Si "Nuevo" estuviera en este mapeo, la migración de la fase 1 no
# puede distinguir el "Nuevo" viejo del "Nuevo" actual: en cada arranque encontraría la fila
# "Nuevo" legítima, movería a esos clientes a "Esperar" y borraría la fila. Eso es lo que
# causaba que los clientes en "Nuevo" quedaran reseteados a "Esperar" en cada reinicio.
MAPEO_ESTADOS_MIGRACION = {
    "Contactado": "Viene",
    "En negociación": "Esperar",
    "Cerrado": "Cliente",
    "Perdido": "Descartado",
}


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS estados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                color TEXT NOT NULL DEFAULT '#808080',
                orden INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                contacto TEXT,
                estado_id INTEGER NOT NULL REFERENCES estados(id) ON DELETE RESTRICT,
                fecha_actualizacion TEXT NOT NULL,
                notas TEXT,
                recomendado_por TEXT,
                contacto_normalizado TEXT,
                fecha_alta TEXT
            )
            """
        )
        columnas = {r["name"] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()}
        if "recomendado_por" not in columnas:
            conn.execute("ALTER TABLE clientes ADD COLUMN recomendado_por TEXT")
        if "contacto_normalizado" not in columnas:
            conn.execute("ALTER TABLE clientes ADD COLUMN contacto_normalizado TEXT")
            conn.execute(
                "UPDATE clientes SET contacto_normalizado = "
                "REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(contacto, ''), ' ', ''), '-', ''), '(', ''), ')', '')"
            )
        if "fecha_alta" not in columnas:
            conn.execute("ALTER TABLE clientes ADD COLUMN fecha_alta TEXT")
            # No hay dato real de cuándo se dio de alta un registro viejo: mejor aproximación
            # disponible es su fecha_actualizacion actual.
            conn.execute("UPDATE clientes SET fecha_alta = fecha_actualizacion WHERE fecha_alta IS NULL")

        # Nombres siempre en mayúscula y sin tildes: normaliza los que ya estaban en la DB de
        # antes de este cambio. SQLite no tiene una función nativa para sacar tildes (no hay
        # equivalente de unicodedata.normalize en SQL puro), así que se hace en Python:
        # traemos los nombres y sólo tocamos los que realmente cambian (idempotente).
        for row in conn.execute("SELECT id, nombre FROM clientes").fetchall():
            limpio = normalizar_nombre(row["nombre"])
            if limpio != row["nombre"]:
                conn.execute("UPDATE clientes SET nombre = ? WHERE id = ?", (limpio, row["id"]))

        conn.execute("CREATE INDEX IF NOT EXISTS idx_clientes_estado ON clientes(estado_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clientes_fecha ON clientes(fecha_actualizacion)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_clientes_contacto_norm ON clientes(contacto_normalizado)"
        )

        _migrar_estados_a_nuevo_esquema(conn)


def _migrar_estados_a_nuevo_esquema(conn: sqlite3.Connection) -> None:
    """Crea los ESTADOS_SEED actuales si faltan, y migra los clientes que estaban en un
    estado del esquema VIEJO conocido (MAPEO_ESTADOS_MIGRACION). Es idempotente: en una DB ya
    migrada no encuentra nada para mover.

    Va en 2 fases: primero se resuelven los nombres que son clave de MAPEO_ESTADOS_MIGRACION
    (fase 1, mueve sus clientes y borra la fila vieja) y recién después se siembran/reordenan
    los ESTADOS_SEED actuales (fase 2). IMPORTANTE: MAPEO_ESTADOS_MIGRACION nunca puede tener
    como clave el nombre de un estado que también exista en ESTADOS_SEED (como pasaba antes
    con "Nuevo") — si lo tuviera, la fase 1 no podría distinguir la fila legítima y actual de
    ese nombre de una fila vieja pendiente de migrar, y en cada arranque movería de nuevo a
    esos clientes y borraría la fila (para recrearla vacía en la fase 2). Ver el comentario
    junto a MAPEO_ESTADOS_MIGRACION.

    IMPORTANTE — esto NO toca ningún estado que no sea una key conocida de
    MAPEO_ESTADOS_MIGRACION: los estados que el usuario cree o renombre a mano desde el botón
    "Estados" son legítimos y tienen que sobrevivir para siempre a través de reinicios de la
    app. (Hubo una versión anterior de esta función con una "fase 3" que borraba cualquier
    estado no incluido en ESTADOS_SEED en CADA arranque — eso rompía cualquier estado custom
    que el usuario hubiera creado, moviendo sus clientes a "Esperar" sin aviso. Ya no existe.)
    """
    # Fase 1: estados que son clave del mapeo viejo->nuevo, se resuelven primero.
    viejos = conn.execute("SELECT id, nombre FROM estados").fetchall()
    for row in viejos:
        nombre_viejo, id_viejo = row["nombre"], row["id"]
        if nombre_viejo not in MAPEO_ESTADOS_MIGRACION:
            continue
        nombre_nuevo = MAPEO_ESTADOS_MIGRACION[nombre_viejo]
        fila_destino = conn.execute(
            "SELECT id FROM estados WHERE nombre = ?", (nombre_nuevo,)
        ).fetchone()
        if fila_destino:
            id_nuevo = fila_destino["id"]
        else:
            color = next((c for n, c in ESTADOS_SEED if n == nombre_nuevo), "#808080")
            id_nuevo = conn.execute(
                "INSERT INTO estados (nombre, color, orden) VALUES (?, ?, 999)", (nombre_nuevo, color)
            ).lastrowid
        conn.execute("UPDATE clientes SET estado_id = ? WHERE estado_id = ?", (id_nuevo, id_viejo))
        conn.execute("DELETE FROM estados WHERE id = ?", (id_viejo,))

    # Fase 2: asegura que existan (y con el orden correcto) todos los ESTADOS_SEED actuales.
    existentes_filas = {
        r["nombre"]: (r["id"], r["color"]) for r in conn.execute("SELECT id, nombre, color FROM estados").fetchall()
    }
    for orden, (nombre, color) in enumerate(ESTADOS_SEED):
        if nombre not in existentes_filas:
            cur = conn.execute(
                "INSERT INTO estados (nombre, color, orden) VALUES (?, ?, ?)", (nombre, color, orden)
            )
            existentes_filas[nombre] = (cur.lastrowid, color)
        else:
            id_existente, color_actual = existentes_filas[nombre]
            conn.execute("UPDATE estados SET orden = ? WHERE id = ?", (orden, id_existente))
            # Si el color sigue siendo el default viejo (el usuario nunca lo cambió a mano
            # desde "Estados"), lo actualizamos al nuevo default: algunos tonos cálidos
            # quedaban casi indistinguibles entre sí en la tabla.
            if color_actual == _ESTADOS_SEED_COLOR_VIEJO.get(nombre):
                conn.execute("UPDATE estados SET color = ? WHERE id = ?", (color, id_existente))


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalizar_telefono(contacto: str) -> str:
    """Saca espacios, guiones y paréntesis para poder comparar teléfonos con distinto formato."""
    if not contacto:
        return ""
    for ch in (" ", "-", "(", ")"):
        contacto = contacto.replace(ch, "")
    return contacto.strip()


def normalizar_nombre(nombre: str) -> str:
    """Mayúsculas, sin tildes/diacríticos y con espacios múltiples colapsados. Se usa TANTO
    para guardar el nombre en la DB (crear_cliente/actualizar_cliente) como para compararlo al
    buscar duplicados — así "José García" y "JOSE GARCIA" (típico error de OCR con tildes)
    quedan literalmente como el mismo string guardado, no solo "detectados como iguales"."""
    if not nombre:
        return ""
    s = nombre.strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


# ---------- Estados ----------

def listar_estados() -> list[Estado]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM estados ORDER BY orden, nombre").fetchall()
        return [Estado(id=r["id"], nombre=r["nombre"], color=r["color"], orden=r["orden"]) for r in rows]


def crear_estado(nombre: str, color: str = "#808080") -> int:
    with get_conn() as conn:
        orden = conn.execute("SELECT COALESCE(MAX(orden), -1) + 1 FROM estados").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO estados (nombre, color, orden) VALUES (?, ?, ?)", (nombre, color, orden)
        )
        return cur.lastrowid


def actualizar_estado(estado_id: int, nombre: str, color: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE estados SET nombre = ?, color = ? WHERE id = ?", (nombre, color, estado_id)
        )


def eliminar_estado(estado_id: int) -> tuple[bool, str]:
    """Evita borrar un estado en uso por clientes."""
    with get_conn() as conn:
        en_uso = conn.execute(
            "SELECT COUNT(*) FROM clientes WHERE estado_id = ?", (estado_id,)
        ).fetchone()[0]
        if en_uso > 0:
            return False, f"No se puede borrar: {en_uso} cliente(s) usan este estado."
        conn.execute("DELETE FROM estados WHERE id = ?", (estado_id,))
        return True, ""


# ---------- Clientes ----------

def _row_to_cliente(r: sqlite3.Row) -> Cliente:
    return Cliente(
        id=r["id"],
        nombre=r["nombre"],
        contacto=r["contacto"] or "",
        estado_id=r["estado_id"],
        fecha_actualizacion=r["fecha_actualizacion"],
        fecha_alta=r["fecha_alta"] or r["fecha_actualizacion"],
        notas=r["notas"] or "",
        recomendado_por=r["recomendado_por"] or "",
        estado_nombre=r["estado_nombre"],
        estado_color=r["estado_color"],
    )


def listar_clientes(
    estado_id: Optional[int] = None,
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    texto: Optional[str] = None,
) -> list[Cliente]:
    query = """
        SELECT c.*, e.nombre AS estado_nombre, e.color AS estado_color
        FROM clientes c
        JOIN estados e ON e.id = c.estado_id
        WHERE 1=1
    """
    params: list = []
    if estado_id:
        query += " AND c.estado_id = ?"
        params.append(estado_id)
    if fecha_desde:
        query += " AND c.fecha_actualizacion >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        query += " AND c.fecha_actualizacion <= ?"
        params.append(fecha_hasta + "T23:59:59")
    if texto:
        query += " AND (c.nombre LIKE ? OR c.contacto LIKE ? OR c.notas LIKE ? OR c.recomendado_por LIKE ?)"
        like = f"%{texto}%"
        params.extend([like, like, like, like])
    query += " ORDER BY c.fecha_actualizacion DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_cliente(r) for r in rows]


def crear_cliente(
    nombre: str, contacto: str, estado_id: int, notas: str = "", recomendado_por: str = ""
) -> int:
    nombre = normalizar_nombre(nombre)
    with get_conn() as conn:
        ahora = _now_iso()
        cur = conn.execute(
            "INSERT INTO clientes "
            "(nombre, contacto, estado_id, fecha_actualizacion, fecha_alta, notas, recomendado_por, "
            "contacto_normalizado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (nombre, contacto, estado_id, ahora, ahora, notas, recomendado_por, normalizar_telefono(contacto)),
        )
        return cur.lastrowid


def actualizar_cliente(
    cliente_id: int,
    nombre: str,
    contacto: str,
    estado_id: int,
    notas: str,
    recomendado_por: str = "",
) -> None:
    nombre = normalizar_nombre(nombre)
    with get_conn() as conn:
        # fecha_alta NO se toca acá a propósito: se setea una sola vez, al crear el registro.
        conn.execute(
            "UPDATE clientes SET nombre = ?, contacto = ?, estado_id = ?, "
            "fecha_actualizacion = ?, notas = ?, recomendado_por = ?, contacto_normalizado = ? WHERE id = ?",
            (
                nombre,
                contacto,
                estado_id,
                _now_iso(),
                notas,
                recomendado_por,
                normalizar_telefono(contacto),
                cliente_id,
            ),
        )


def buscar_duplicados(nombre: str, contacto: str) -> list[Cliente]:
    """Chequeo no bloqueante: primero por teléfono normalizado, y si no matchea, por nombre
    (case-insensitive, sin tildes). Se usa tanto en el alta manual como en las importaciones
    masivas. La comparación por nombre se hace en Python (no en SQL) para poder ignorar
    diacríticos con unicodedata, algo que SQLite no maneja de forma nativa."""
    contacto_norm = normalizar_telefono(contacto)
    nombre_norm = normalizar_nombre(nombre)

    with get_conn() as conn:
        if contacto_norm:
            rows = conn.execute(
                """
                SELECT c.*, e.nombre AS estado_nombre, e.color AS estado_color
                FROM clientes c JOIN estados e ON e.id = c.estado_id
                WHERE c.contacto_normalizado = ?
                """,
                (contacto_norm,),
            ).fetchall()
            if rows:
                return [_row_to_cliente(r) for r in rows]

        if nombre_norm:
            rows = conn.execute(
                """
                SELECT c.*, e.nombre AS estado_nombre, e.color AS estado_color
                FROM clientes c JOIN estados e ON e.id = c.estado_id
                """
            ).fetchall()
            coincidencias = [r for r in rows if normalizar_nombre(r["nombre"]) == nombre_norm]
            if coincidencias:
                return [_row_to_cliente(r) for r in coincidencias]

    return []


def cambiar_estado_cliente(cliente_id: int, estado_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE clientes SET estado_id = ?, fecha_actualizacion = ? WHERE id = ?",
            (estado_id, _now_iso(), cliente_id),
        )


def eliminar_cliente(cliente_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))


# ---------- Importación masiva genérica (Excel, OCR) ----------


@dataclass
class FilaImport:
    """Una fila candidata a importar, venga de Excel o de OCR (estos últimos solo traen
    nombre/contacto; el resto queda vacío y usa los defaults)."""

    nombre: str
    contacto: str
    estado: str = ""
    notas: str = ""
    recomendado_por: str = ""
    origen: str = ""  # info libre para mostrar en la revisión (ej. línea del Excel u OCR)
    # Confianza 0-100 que tuvo Tesseract al leer nombre/teléfono (None = no aplica, ej. Excel
    # o IA). Solo se usa para pintar de aviso las filas dudosas en la tabla de revisión — no
    # afecta en nada el guardado en la DB.
    confianza_nombre: float | None = None
    confianza_telefono: float | None = None


@dataclass
class ResultadoLote:
    ok: int = 0
    duplicados: list[tuple[FilaImport, list[Cliente]]] = field(default_factory=list)
    fallidos: list[tuple[FilaImport, str]] = field(default_factory=list)


def _resolver_estado_id(nombre_estado: str, estados_por_nombre: dict, default_id: Optional[int]) -> Optional[int]:
    if not nombre_estado:
        return default_id
    return estados_por_nombre.get(nombre_estado.strip().lower(), default_id)


def procesar_lote(filas: Iterable[FilaImport]) -> ResultadoLote:
    """Clasifica cada fila en OK (se carga directo) / duplicado (posible, queda para revisar)
    / fallido (falta nombre o contacto). No pide confirmación por fila: eso lo resuelve la UI
    después, mostrando el resumen y dejando decidir uno por uno los duplicados."""
    estados_por_nombre = {e.nombre.lower(): e.id for e in listar_estados()}
    estado_default_id = listar_estados()[0].id if estados_por_nombre else None

    resultado = ResultadoLote()
    for fila in filas:
        nombre = (fila.nombre or "").strip()
        contacto = (fila.contacto or "").strip()
        if not nombre or not contacto:
            resultado.fallidos.append((fila, "Falta nombre o contacto"))
            continue

        dups = buscar_duplicados(nombre, contacto)
        if dups:
            resultado.duplicados.append((fila, dups))
            continue

        estado_id = _resolver_estado_id(fila.estado, estados_por_nombre, estado_default_id)
        if estado_id is None:
            resultado.fallidos.append((fila, "No hay estados configurados"))
            continue

        crear_cliente(nombre, contacto, estado_id, fila.notas, fila.recomendado_por)
        resultado.ok += 1

    return resultado


def cargar_fila_igual(fila: FilaImport) -> None:
    """Inserta una fila que había quedado marcada como posible duplicado, ignorando el aviso."""
    estados_por_nombre = {e.nombre.lower(): e.id for e in listar_estados()}
    estado_default_id = listar_estados()[0].id if estados_por_nombre else None
    estado_id = _resolver_estado_id(fila.estado, estados_por_nombre, estado_default_id)
    crear_cliente(fila.nombre.strip(), fila.contacto.strip(), estado_id, fila.notas, fila.recomendado_por)
