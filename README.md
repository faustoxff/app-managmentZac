# Gestor de Clientes (local, Windows)

App de escritorio local para seguimiento de clientes. Sin servidor, sin internet, todo en SQLite.

## Stack
- Python 3 + Tkinter (stdlib, sin dependencias extra)
- SQLite (`sqlite3`, stdlib)
- openpyxl (importar Excel), pytesseract + Pillow (importar por foto/OCR) y qrcode (subida
  desde el celular)
- Servidor para la subida desde el celular con `http.server`/`socketserver` (stdlib, sin
  Flask ni nada externo)
- Empaquetable a `.exe` con PyInstaller

## Correr en desarrollo

```bash
pip install -r requirements.txt
python main.py
```

El core de la app (CRUD, filtros) solo necesita Tkinter y sqlite3, que son parte de
Python estándar. Las dependencias de `requirements.txt` son para importar desde Excel/foto y
para generar el `.exe`; si no se instalan, esos botones muestran un aviso claro en vez de
romper el resto de la app.

## Importar por foto (OCR) — Tesseract

**El `.exe` de Windows generado por GitHub Actions ya trae Tesseract-OCR empaquetado adentro**
(con el idioma español incluido) — no hace falta instalar nada aparte para usar "Importar por
foto" ni "Subida por celular" con ese ejecutable. Ver `.github/workflows/build.yml`
(`choco install tesseract` + `--add-data` de PyInstaller) y `ocr_import.py`
(`_configurar_tesseract_embebido`), que detecta automáticamente si está corriendo empaquetado
y usa ese Tesseract en vez de buscar uno en el sistema.

Esto solo aplica al `.exe` ya compilado. Corriendo en modo desarrollo (`python main.py`) sigue
haciendo falta **Tesseract-OCR** instalado en el sistema (es un programa aparte, no una
librería de Python):

- Windows: descargar el instalador desde https://github.com/UB-Mannheim/tesseract/wiki y
  marcar la opción de agregarlo al PATH durante la instalación (o agregarlo a mano después).
- Si Tesseract no está instalado, el botón "Importar por foto" muestra un mensaje claro con
  este mismo link, en vez de romper la app.

Para mejor reconocimiento en español, instalar también el paquete de idioma `spa` de Tesseract
(el instalador de Windows lo ofrece como opción). Si no está disponible, la app cae
automáticamente al idioma por defecto.

## Subida de fotos desde el celular

El botón "Subida por celular" levanta un servidor HTTP local (solo en la red WiFi, no expuesto
a internet) y muestra un código QR. Escaneándolo desde el celular (misma red que la PC) se abre
una página simple para elegir/sacar una foto y subirla; al llegar, la app la procesa con el
mismo OCR de "Importar por foto" automáticamente, sin tocar nada más en la PC.

- Se activa bajo demanda (no hay ningún puerto abierto si no se usa el botón).
- Si Windows Firewall pregunta la primera vez que se activa, hay que permitir el acceso para
  que el celular pueda conectarse.
- Si no se puede levantar el servidor (puerto ocupado, sin permisos), la app avisa y sigue
  funcionando normal — "Importar por foto" con selector de archivo manual sigue disponible.
- El botón "Desactivar" (dentro del popup del QR) cierra el servidor; también se cierra solo
  al cerrar la app.

## Dónde se guarda la base de datos

- Windows: `%APPDATA%\GestorClientes\clientes.db`
- Linux/Mac (para desarrollo): `~/.local/share/GestorClientes/clientes.db`

Se crea automáticamente al primer inicio, tanto corriendo `python main.py` como desde el `.exe`
empaquetado (ver `config.py`). No depende del directorio del ejecutable, así que funciona bien
con `--onefile` (que usa un directorio temporal efímero para extraer el código).

## Generar el .exe (en Windows)

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name GestorClientes main.py
```

El ejecutable queda en `dist/GestorClientes.exe`. No necesita Python instalado en la máquina destino.

### Generar el .exe sin tener Windows (GitHub Actions)

PyInstaller no hace cross-compile: un build corrido en Linux genera un binario de Linux, no un
`.exe`. El workflow en `.github/workflows/build.yml` resuelve esto compilando en runners de
GitHub (Windows y Linux) cada vez que se hace push a `main`, o manualmente desde la pestaña
"Actions" del repo ("Run workflow").

Los ejecutables generados quedan como *artifacts* de esa ejecución (pestaña Actions → el run
correspondiente → sección Artifacts), listos para descargar sin necesitar Windows en la máquina
local.

## Funcionalidad

- Alta, edición, borrado y cambio de estado de clientes.
- Estados configurables (nombre y color) desde el botón "Estados".
- Filtros por estado, rango de fechas y texto libre (nombre/notas/recomendado por).
- Los nombres se guardan siempre en MAYÚSCULA (alta manual, edición, y todas las
  importaciones), incluso mientras se escribe en el formulario.
- **Validación de duplicados**: al cargar un cliente (a mano, o vía Excel/foto), si ya existe
  uno con el mismo teléfono (normalizado) o el mismo nombre (sin importar mayúsculas/tildes),
  se avisa antes de cargar — sin bloquear, se puede ver el existente o cargar igual.
- **Importar Excel** (`.xlsx`): deja mapear qué columna del archivo corresponde a cada campo
  (nombre, contacto, estado, notas), y recuerda el último mapeo usado para no repetirlo con
  archivos del mismo formato. Al final muestra cuántos se cargaron OK, cuántos son posibles
  duplicados (revisables uno por uno) y cuántos fallaron por datos faltantes.
- **Importar por foto**: extrae nombre y teléfono de una foto de planilla de turnos vía OCR
  local (sin internet, sin APIs pagas). Muestra una tabla editable para corregir lo detectado
  antes de confirmar la carga. Ver la sección de instalación de Tesseract más arriba.
- **Subida por celular**: sacá la foto directo desde el teléfono (mismo WiFi, sin cables ni
  apps) y se procesa sola con el mismo OCR. Ver sección dedicada más arriba.
