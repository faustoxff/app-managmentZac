"""Permiso del Firewall de Windows para "Subida por celular".

El celular se conecta directo a la PC. En una red que Windows marca como "pública" el firewall
descarta esas conexiones en silencio (el celular se queda cargando), así que en un WiFi
andaba y en otro no. Acá la app crea una regla que deja entrar conexiones a ESTE programa en
cualquier tipo de red, sólo en los puertos que usa photo_server.

Crear la regla necesita permisos de administrador: Windows muestra su cartel de confirmación
una vez. Si el usuario dice que no, la app sigue andando igual que antes.
"""
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

# El mismo rango que prueba PhotoServer.iniciar (puerto_desde=8000, intentos=20).
PUERTOS = "8000-8019"


def aplica() -> bool:
    """Sólo tiene sentido en el .exe de Windows: en desarrollo no hay un programa fijo."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def _nombre_regla(exe: str) -> str:
    # El hash de la ruta hace que, si el .exe se mueve de carpeta, se note que falta la regla
    # para la ruta nueva (las reglas por programa dependen de la ruta exacta).
    sufijo = hashlib.sha1(exe.lower().encode("utf-8")).hexdigest()[:8]
    return f"GestorClientes - Subida por celular [{sufijo}]"


def _sin_ventana() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def comandos(exe: str) -> list[str]:
    """Primero se borran las reglas de ENTRADA de este programa: la que crea el cartel de
    Windows al permitir sólo redes privadas incluye un BLOQUEO para las públicas, y un bloqueo
    le gana a cualquier permiso. Sólo toca reglas de este .exe, ninguna otra."""
    return [
        f'netsh advfirewall firewall delete rule name=all dir=in program="{exe}"',
        f'netsh advfirewall firewall add rule name="{_nombre_regla(exe)}" dir=in action=allow '
        f'program="{exe}" protocol=TCP localport={PUERTOS} profile=any',
    ]


def regla_existe(exe: str | None = None) -> bool:
    exe = exe or sys.executable
    try:
        r = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={_nombre_regla(exe)}"],
            capture_output=True,
            creationflags=_sin_ventana(),
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    # netsh devuelve 1 si no encuentra la regla. Se usa el código de salida y no el texto
    # porque el texto viene en el idioma de Windows.
    return r.returncode == 0


def configurar(exe: str | None = None) -> bool:
    """Crea la regla pidiendo permiso de administrador. Devuelve True si quedó creada."""
    exe = exe or sys.executable
    bat = Path(tempfile.gettempdir()) / "GestorClientes_firewall.bat"
    bat.write_text(
        "@echo off\r\nchcp 65001 >nul\r\n" + "\r\n".join(comandos(exe)) + "\r\n", encoding="utf-8"
    )
    ruta = str(bat).replace("'", "''")
    try:
        # Start-Process -Verb RunAs muestra el cartel de Windows; -Wait espera a que termine.
        # Si el usuario cancela, PowerShell termina con error y la regla no se crea.
        subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                f"Start-Process -FilePath '{ruta}' -Verb RunAs -Wait -WindowStyle Hidden",
            ],
            capture_output=True,
            creationflags=_sin_ventana(),
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        try:
            bat.unlink()
        except OSError:
            pass
    return regla_existe(exe)
