# Gestor de Clientes (local, Windows)

App de escritorio local para seguimiento de clientes. Sin servidor, sin internet, todo en SQLite.

## Stack
- Python 3 + Tkinter (stdlib, sin dependencias extra)
- SQLite (`sqlite3`, stdlib)
- Empaquetable a `.exe` con PyInstaller

## Correr en desarrollo

```bash
python main.py
```

No requiere instalar nada para correr (Tkinter y sqlite3 son parte de Python estándar).
`requirements.txt` solo trae `pyinstaller`, necesario para generar el `.exe`.

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

## Funcionalidad

- Alta, edición, borrado y cambio de estado de clientes.
- Estados configurables (nombre y color) desde el botón "Estados".
- Filtros por estado, rango de fechas y texto libre (nombre/notas).
- Importar/exportar clientes en CSV (columnas: `nombre, contacto, estado, notas`).
  La importación tolera columnas faltantes o filas incompletas: reporta errores por fila
  sin interrumpir el resto de la carga.
