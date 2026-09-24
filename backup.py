"""Backup de la base de datos a Neon (Postgres en la nube), como una copia completa del
archivo clientes.db guardada en una columna bytea. Es solo una red de seguridad ante rotura
de la PC — no guarda cada cliente como fila real, así que no se puede consultar/buscar
clientes desde la web de Neon (a propósito: eso sería un feature bastante más grande y no es
lo que hace falta acá)."""
from datetime import datetime

import config

MAX_BACKUPS = 10  # se borran los más viejos para no acumular espacio de más en Neon
TABLA = "gestorclientes_backups"


class BackupError(Exception):
    """Error de conexión, de red, o de Neon en sí — mensaje pensado para mostrarse directo en
    un messagebox."""


class FaltaConnectionString(BackupError):
    """Señal específica para que la UI muestre el popup de configuración y reintente."""


def _requerir_psycopg2():
    try:
        import psycopg2
    except ImportError as exc:
        raise BackupError(
            "Falta instalar la librería psycopg2-binary:\n\npip install psycopg2-binary"
        ) from exc
    return psycopg2


def _conectar(psycopg2):
    connection_string = config.obtener_neon_connection_string()
    if not connection_string:
        raise FaltaConnectionString()
    try:
        return psycopg2.connect(connection_string, connect_timeout=15)
    except psycopg2.Error as exc:
        # Antes solo se capturaba OperationalError (típico de red/host caído) — pero una
        # cadena de conexión con formato inválido puede hacer que psycopg2 tire otro
        # subtipo de error (ej. ProgrammingError) que quedaba sin capturar acá y se
        # colaba sin envolver en BackupError hasta el hilo de la UI, dejando el popup de
        # backup trabado en "Subiendo..." para siempre sin ningún mensaje de error.
        raise BackupError(
            f"No se pudo conectar a Neon (revisá la cadena de conexión y tu internet):\n{exc}"
        ) from exc


def _asegurar_tabla(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLA} (
                id SERIAL PRIMARY KEY,
                creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
                nombre_archivo TEXT NOT NULL,
                datos BYTEA NOT NULL
            )
            """
        )
    conn.commit()


def hacer_backup_ahora() -> str:
    """Sube el archivo clientes.db actual a Neon. Devuelve el nombre del backup subido."""
    if not config.DB_PATH.exists():
        raise BackupError("Todavía no hay una base de datos para respaldar.")

    psycopg2 = _requerir_psycopg2()
    datos = config.DB_PATH.read_bytes()
    nombre = f"clientes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    conn = _conectar(psycopg2)
    try:
        _asegurar_tabla(conn)
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {TABLA} (nombre_archivo, datos) VALUES (%s, %s)",
                (nombre, psycopg2.Binary(datos)),
            )
            cur.execute(
                f"""
                DELETE FROM {TABLA}
                WHERE id NOT IN (
                    SELECT id FROM {TABLA} ORDER BY creado_en DESC LIMIT %s
                )
                """,
                (MAX_BACKUPS,),
            )
        conn.commit()
    except (FaltaConnectionString, BackupError):
        raise
    except Exception as exc:  # noqa: BLE001 - cubrimos cualquier error de Neon/red
        raise BackupError(f"Error al subir el backup a Neon:\n{exc}") from exc
    finally:
        conn.close()

    return nombre


def listar_backups() -> list[tuple[str, str]]:
    """Devuelve [(nombre_archivo, fecha_legible), ...] del más nuevo al más viejo."""
    psycopg2 = _requerir_psycopg2()
    conn = _conectar(psycopg2)
    try:
        _asegurar_tabla(conn)
        with conn.cursor() as cur:
            cur.execute(f"SELECT nombre_archivo, creado_en FROM {TABLA} ORDER BY creado_en DESC")
            filas = cur.fetchall()
        return [(nombre, creado_en.strftime("%d/%m/%Y %H:%M")) for nombre, creado_en in filas]
    except (FaltaConnectionString, BackupError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise BackupError(f"Error al listar los backups de Neon:\n{exc}") from exc
    finally:
        conn.close()


def restaurar_backup(nombre_archivo: str) -> None:
    """Descarga ese backup y sobreescribe la base de datos local. Es destructivo (pisa lo que
    haya localmente), por eso la UI tiene que confirmar antes de llamar a esto."""
    psycopg2 = _requerir_psycopg2()
    conn = _conectar(psycopg2)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT datos FROM {TABLA} WHERE nombre_archivo = %s", (nombre_archivo,))
            fila = cur.fetchone()
        if not fila:
            raise BackupError(f"No se encontró el backup '{nombre_archivo}' en Neon.")
        config.DB_PATH.write_bytes(bytes(fila[0]))
        # Este es el único lugar de todo el código que sobreescribe la DB local desde Neon —
        # se deja registro acá para poder confirmar o descartar con evidencia real si algún
        # reseteo de datos vino de acá (solo pasa si alguien confirmó a mano el popup de
        # "Restaurar backup", nunca automático).
        import db

        db._log_diagnostico(f"RESTAURACIÓN DESDE NEON: se sobreescribió la DB local con '{nombre_archivo}'")
    except (FaltaConnectionString, BackupError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise BackupError(f"Error al restaurar el backup desde Neon:\n{exc}") from exc
    finally:
        conn.close()
