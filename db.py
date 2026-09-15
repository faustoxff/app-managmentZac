"""Acceso a SQLite. Cada operación abre y cierra su propia conexión (context manager)."""
import csv
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from typing import Iterable, Optional

from config import DB_PATH
from models import Cliente, Estado

ESTADOS_SEED = [
    ("Nuevo", "#3b82f6"),
    ("Contactado", "#f59e0b"),
    ("En negociación", "#a855f7"),
    ("Cerrado", "#22c55e"),
    ("Perdido", "#ef4444"),
]


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
                recomendado_por TEXT
            )
            """
        )
        columnas = {r["name"] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()}
        if "recomendado_por" not in columnas:
            conn.execute("ALTER TABLE clientes ADD COLUMN recomendado_por TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clientes_estado ON clientes(estado_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clientes_fecha ON clientes(fecha_actualizacion)")

        count = conn.execute("SELECT COUNT(*) FROM estados").fetchone()[0]
        if count == 0:
            for orden, (nombre, color) in enumerate(ESTADOS_SEED):
                conn.execute(
                    "INSERT INTO estados (nombre, color, orden) VALUES (?, ?, ?)",
                    (nombre, color, orden),
                )


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
        query += " AND (c.nombre LIKE ? OR c.notas LIKE ? OR c.recomendado_por LIKE ?)"
        like = f"%{texto}%"
        params.extend([like, like, like])
    query += " ORDER BY c.fecha_actualizacion DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_cliente(r) for r in rows]


def crear_cliente(
    nombre: str, contacto: str, estado_id: int, notas: str = "", recomendado_por: str = ""
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO clientes (nombre, contacto, estado_id, fecha_actualizacion, notas, recomendado_por) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (nombre, contacto, estado_id, _now_iso(), notas, recomendado_por),
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
    with get_conn() as conn:
        conn.execute(
            "UPDATE clientes SET nombre = ?, contacto = ?, estado_id = ?, "
            "fecha_actualizacion = ?, notas = ?, recomendado_por = ? WHERE id = ?",
            (nombre, contacto, estado_id, _now_iso(), notas, recomendado_por, cliente_id),
        )


def cambiar_estado_cliente(cliente_id: int, estado_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE clientes SET estado_id = ?, fecha_actualizacion = ? WHERE id = ?",
            (estado_id, _now_iso(), cliente_id),
        )


def eliminar_cliente(cliente_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))


# ---------- CSV ----------

CSV_COLUMNAS = ["nombre", "contacto", "estado", "notas", "recomendado_por"]


def exportar_csv(path: str, clientes: Iterable[Cliente]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["nombre", "contacto", "estado", "fecha_actualizacion", "notas", "recomendado_por"],
        )
        writer.writeheader()
        for c in clientes:
            writer.writerow(
                {
                    "nombre": c.nombre,
                    "contacto": c.contacto,
                    "estado": c.estado_nombre,
                    "fecha_actualizacion": c.fecha_actualizacion,
                    "notas": c.notas,
                    "recomendado_por": c.recomendado_por,
                }
            )


def _abrir_csv_texto(path: str):
    """Excel en español suele exportar CSV en cp1252 en vez de UTF-8; probamos UTF-8 primero
    y si falla al decodificar, caemos a cp1252 para no romper con tildes/ñ."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            f = open(path, newline="", encoding=encoding)
            f.read()
            f.seek(0)
            return f
        except UnicodeDecodeError:
            continue
    return open(path, newline="", encoding="utf-8-sig", errors="replace")


def importar_csv(path: str) -> tuple[int, list[str]]:
    """Importa clientes desde CSV. Columnas esperadas: nombre, contacto, estado, notas.
    Tolera columnas faltantes: usa valores por defecto y reporta filas con error.
    Devuelve (cantidad_importada, lista_de_errores).
    """
    estados = {e.nombre.lower(): e.id for e in listar_estados()}
    estado_default_id = listar_estados()[0].id if estados else None

    importados = 0
    errores: list[str] = []

    with _abrir_csv_texto(path) as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return 0, ["El CSV está vacío o no tiene encabezados."]

        for i, row in enumerate(reader, start=2):
            nombre = (row.get("nombre") or "").strip()
            if not nombre:
                errores.append(f"Fila {i}: falta 'nombre', se omite.")
                continue
            contacto = (row.get("contacto") or "").strip()
            notas = (row.get("notas") or "").strip()
            recomendado_por = (row.get("recomendado_por") or "").strip()
            estado_txt = (row.get("estado") or "").strip().lower()
            estado_id = estados.get(estado_txt, estado_default_id)
            if estado_id is None:
                errores.append(f"Fila {i}: no hay estados configurados, se omite.")
                continue
            try:
                crear_cliente(nombre, contacto, estado_id, notas, recomendado_por)
                importados += 1
            except Exception as exc:  # noqa: BLE001 - reportar y continuar con el resto del CSV
                errores.append(f"Fila {i}: error al importar ({exc}).")

    return importados, errores
