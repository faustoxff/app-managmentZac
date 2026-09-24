"""Auto-actualización de la app: consulta GitHub Releases, descarga el .exe nuevo, y arma un
script .bat que hace el reemplazo (en Windows, un .exe no puede sobrescribirse a sí mismo
mientras sigue corriendo — por eso el reemplazo lo hace un proceso aparte, después de que la
app se cierra sola)."""
import json
import os
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import certifi
import version

REPO = "faustoxff/app-managmentZac"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
TIMEOUT = 10

# En vez de confiar en el almacén de certificados del sistema operativo (falla con
# "CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate" en Windows viejos o sin
# actualizar, a los que les falta el certificado raíz que usa GitHub) usamos el paquete de
# certificados que trae certifi, empaquetado dentro del propio .exe — así funciona igual sin
# importar qué tan actualizado esté el Windows donde corre.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


@dataclass
class ActualizacionDisponible:
    version_nueva: str
    url_descarga: str
    tamano: int


class NoSePudoComprobar(Exception):
    """La consulta a GitHub falló (sin internet, GitHub caído, timeout, etc.) — distinto de
    "ya está al día", que sí es una respuesta válida. Antes ambos casos devolvían None y la UI
    mostraba "ya tenés la última versión" incluso cuando en realidad no se pudo comprobar
    nada, lo cual podía ocultarle a un usuario con problemas de conexión que su chequeo nunca
    llegó a buen puerto."""

    pass


def _version_a_tupla(v: str) -> tuple[int, ...]:
    v = (v or "").strip().lstrip("vV")
    partes = []
    for p in v.split("."):
        try:
            partes.append(int(p))
        except ValueError:
            partes.append(0)
    return tuple(partes) or (0,)


def verificar_actualizacion() -> ActualizacionDisponible | None:
    """Devuelve la actualización disponible, o None si ya está al día. Lanza
    NoSePudoComprobar si la consulta en sí falló (sin internet, GitHub caído, el repo no tiene
    releases todavía, etc.) — nunca deja que un error de red se confunda con "ya estás al
    día"."""
    try:
        req = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL_CONTEXT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
        raise NoSePudoComprobar(str(exc)) from exc

    tag = data.get("tag_name", "")
    if not tag or _version_a_tupla(tag) <= _version_a_tupla(version.__version__):
        return None

    exe_asset = next(
        (a for a in data.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None
    )
    if not exe_asset:
        return None

    return ActualizacionDisponible(
        version_nueva=tag,
        url_descarga=exe_asset["browser_download_url"],
        tamano=exe_asset.get("size", 0),
    )


def descargar_actualizacion(url: str, tamano_esperado: int, progreso_callback=None) -> Path:
    """Descarga el .exe nuevo a una carpeta temporal. progreso_callback(descargado, total) se
    llama después de cada chunk si se pasa. Lanza OSError si la descarga queda incompleta o
    corrupta (0 bytes, o tamaño final distinto al que reportó el servidor)."""
    carpeta = Path(tempfile.gettempdir()) / "GestorClientes_update"
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / "GestorClientes_nuevo.exe"

    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CONTEXT) as resp:
        total = int(resp.headers.get("Content-Length") or tamano_esperado or 0)
        descargado = 0
        with open(destino, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                descargado += len(chunk)
                if progreso_callback:
                    progreso_callback(descargado, total)

    tamano_real = destino.stat().st_size
    if tamano_real == 0 or (total and tamano_real != total):
        destino.unlink(missing_ok=True)
        raise OSError(f"La descarga quedó incompleta ({tamano_real} de {total} bytes esperados).")

    return destino


# Ver el mensaje anterior en la conversación para la explicación completa de por qué está
# armado así (rename+verificar+rollback, nunca deja la app sin un .exe funcional).
BAT_TEMPLATE = r"""@echo off
setlocal
set "OLD_EXE=%~1"
set "NEW_EXE=%~2"
set "BACKUP_EXE=%OLD_EXE%.old"

set "LOG=%APPDATA%\GestorClientes\actualizacion.log"
echo %date% %time% inicio: reemplazar "%OLD_EXE%" >> "%LOG%"

set /a intentos=0
:esperar
if exist "%BACKUP_EXE%" del "%BACKUP_EXE%" >nul 2>&1
ren "%OLD_EXE%" "%~nx1.old" >nul 2>&1
if exist "%BACKUP_EXE%" goto :renombrado_ok
set /a intentos+=1
if %intentos% GEQ 20 goto :abandonar
timeout /t 1 /nobreak >nul
goto :esperar

:renombrado_ok
move /y "%NEW_EXE%" "%OLD_EXE%" >nul 2>&1

if not exist "%OLD_EXE%" goto :rollback
for %%A in ("%OLD_EXE%") do if %%~zA EQU 0 goto :rollback

del "%BACKUP_EXE%" >nul 2>&1
echo %date% %time% OK: version nueva instalada >> "%LOG%"
start "" "%OLD_EXE%"
goto :borrarse

:rollback
echo %date% %time% FALLO: no se pudo instalar, se restauro la version VIEJA >> "%LOG%"
if exist "%OLD_EXE%" del "%OLD_EXE%" >nul 2>&1
ren "%BACKUP_EXE%" "%~nx1"
start "" "%OLD_EXE%"
goto :borrarse

:abandonar
echo %date% %time% FALLO: la app vieja no se cerro a tiempo, sigue la version VIEJA >> "%LOG%"
start "" "%OLD_EXE%"

:borrarse
(goto) 2>nul & del "%~f0"
"""


def generar_bat(exe_viejo: Path, exe_nuevo: Path) -> Path:
    """Separado de aplicar_actualizacion() para poder probar que el .bat se arma bien sin
    necesitar Windows ni cerrar el proceso — eso lo prueba el test, no requiere mockear nada."""
    carpeta_temp = Path(tempfile.gettempdir()) / "GestorClientes_update"
    carpeta_temp.mkdir(parents=True, exist_ok=True)
    bat_path = carpeta_temp / "actualizar.bat"
    bat_path.write_text(BAT_TEMPLATE, encoding="utf-8")
    return bat_path


def _entorno_para_relanzar() -> dict:
    """Un .exe de PyInstaller --onefile deja variables de entorno (_MEIPASS2, _PYI_*) que
    apuntan a su carpeta temporal de extracción. Si el proceso hijo las hereda, el .exe nuevo
    cree ser una "segunda instancia" del viejo y usa ESA carpeta, que se borra apenas el viejo
    cierra: resultado "Failed to load Python DLL (python311.dll)". Las sacamos y pedimos al
    bootloader que arranque como proceso independiente."""
    env = {k: v for k, v in os.environ.items() if k != "_MEIPASS2" and not k.startswith("_PYI_")}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def aplicar_actualizacion(path_exe_nuevo: Path) -> None:
    """Genera el .bat de reemplazo, lo lanza desacoplado del proceso actual, y cierra la app
    (necesario para que Windows libere el archivo del .exe viejo). Solo tiene sentido corriendo
    empaquetado — en modo desarrollo (`python main.py`) no hay un .exe propio para reemplazar."""
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "La auto-actualización solo funciona en el .exe empaquetado, no en modo desarrollo."
        )

    exe_actual = Path(sys.executable)
    bat_path = generar_bat(exe_actual, path_exe_nuevo)

    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
        subprocess, "DETACHED_PROCESS", 0
    )
    subprocess.Popen(
        ["cmd", "/c", str(bat_path), str(exe_actual), str(path_exe_nuevo)],
        creationflags=creationflags,
        close_fds=True,
        env=_entorno_para_relanzar(),
    )
    # Esto se llama desde un hilo de fondo (ver ActualizacionPopup._trabajo_descargar): un
    # sys.exit() ahí solo terminaría ESE hilo (lanza SystemExit únicamente en el hilo que lo
    # llama), dejando la ventana de Tkinter abierta y el .exe viejo sin liberar — el .bat de
    # reemplazo entonces reintenta 20 veces, nunca lo logra, y aborta sin aplicar la
    # actualización. os._exit() sí mata el proceso entero sin importar desde qué hilo se llame.
    os._exit(0)
