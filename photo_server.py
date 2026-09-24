"""Servidor HTTP mínimo (solo stdlib) para recibir fotos desde el celular en la misma red
WiFi. Corre en un hilo daemon aparte; nunca toca la UI de Tkinter directamente — deja el path
de cada foto recibida en una queue.Queue para que la ventana principal la consuma con
root.after() (polling), que es la única forma segura de cruzar de un hilo a Tkinter.

Pensado para uso casero en una red confiable (no expuesto a internet): no hay autenticación ni
hardening contra abuso deliberado, solo límites básicos para no crashear con una request rara.
"""
import http.server
import queue
import re
import socket
import socketserver
import threading
import time
import uuid
from pathlib import Path

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # una foto de celular normal entra cómoda en 25MB
EXTENSIONES_VALIDAS = {".jpg", ".jpeg", ".png"}

PAGINA_SUBIDA = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Subir foto - Gestor de Clientes</title>
<style>
  body { font-family: sans-serif; padding: 24px; text-align: center; background: #f5f5f5; }
  h1 { font-size: 1.2rem; }
  input[type=file] { margin: 24px 0; }
  button { font-size: 1.1rem; padding: 12px 24px; background: #2563eb; color: white;
           border: none; border-radius: 8px; }
  #estado { margin-top: 16px; font-weight: bold; }
</style>
</head><body>
<h1>Sacá o elegí la foto de la planilla</h1>
<form id="f">
  <input type="file" name="foto" accept="image/*" required><br>
  <button type="submit">Subir</button>
</form>
<div id="estado"></div>
<script>
document.getElementById('f').addEventListener('submit', async function (e) {
  e.preventDefault();
  const estado = document.getElementById('estado');
  const datos = new FormData(this);
  estado.textContent = 'Subiendo...';
  try {
    const resp = await fetch('/upload', { method: 'POST', body: datos });
    estado.textContent = resp.ok ? 'Listo, ya se envió a la app.' : 'Error al subir.';
  } catch (err) {
    estado.textContent = 'Error al subir.';
  }
});
</script>
</body></html>"""


def _extraer_archivo(body: bytes, boundary: bytes) -> tuple[str | None, bytes | None]:
    """Parser mínimo de multipart/form-data para un único campo de archivo. No usa `cgi`
    (deprecado/removido en Python moderno) ni ninguna librería externa."""
    for parte in body.split(b"--" + boundary):
        if b"filename=" not in parte:
            continue
        fin_headers = parte.find(b"\r\n\r\n")
        if fin_headers == -1:
            continue
        headers = parte[:fin_headers].decode("utf-8", errors="replace")
        contenido = parte[fin_headers + 4 :]
        if contenido.endswith(b"\r\n"):
            contenido = contenido[:-2]
        m = re.search(r'filename="([^"]*)"', headers)
        filename = m.group(1) if m else "foto.jpg"
        if not contenido:
            continue
        return filename, contenido
    return None, None


def _crear_handler(carpeta_destino: Path, cola: "queue.Queue[str]"):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # silencia el log por request en la consola

        def do_GET(self):
            if self.path != "/":
                self.send_response(404)
                self.end_headers()
                return
            cuerpo = PAGINA_SUBIDA.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_POST(self):
            if self.path != "/upload":
                self.send_response(404)
                self.end_headers()
                return

            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type or "boundary=" not in content_type:
                self.send_response(400)
                self.end_headers()
                return

            largo = int(self.headers.get("Content-Length", 0))
            if largo <= 0 or largo > MAX_UPLOAD_BYTES:
                self.send_response(413)
                self.end_headers()
                return

            body = self.rfile.read(largo)
            boundary = content_type.split("boundary=")[-1].strip().encode()
            filename, contenido = _extraer_archivo(body, boundary)
            if not contenido:
                self.send_response(400)
                self.end_headers()
                return

            ext = Path(filename or "").suffix.lower()
            if ext not in EXTENSIONES_VALIDAS:
                ext = ".jpg"
            # ThreadingTCPServer atiende cada request en su propio hilo: dos subidas casi
            # simultáneas (doble tap, reintento por wifi lenta) podían caer en el mismo
            # milisegundo y pisarse el archivo una a la otra. Se agrega un sufijo random corto
            # además del timestamp para que dos nombres nunca choquen.
            destino = carpeta_destino / f"foto_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{ext}"
            destino.write_bytes(contenido)
            cola.put(str(destino))

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")

    return Handler


class _Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True  # evita "address already in use" al reactivar rápido en el mismo puerto
    daemon_threads = True  # así un upload lento/colgado no impide que el proceso termine al cerrar la app


class PhotoServer:
    def __init__(self, carpeta_destino: Path, cola: "queue.Queue[str]"):
        self.carpeta_destino = carpeta_destino
        self.cola = cola
        self.httpd: socketserver.TCPServer | None = None
        self.thread: threading.Thread | None = None
        self.puerto: int | None = None

    def iniciar(self, puerto_desde: int = 8000, intentos: int = 20) -> tuple[str, int]:
        handler = _crear_handler(self.carpeta_destino, self.cola)
        ultimo_error: OSError | None = None
        for puerto in range(puerto_desde, puerto_desde + intentos):
            try:
                httpd = _Servidor(("0.0.0.0", puerto), handler)
            except OSError as exc:
                ultimo_error = exc
                continue
            self.httpd = httpd
            self.puerto = puerto
            break
        else:
            raise ultimo_error or OSError("No se encontró un puerto libre")

        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self._ip_local(), self.puerto

    def detener(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        self.thread = None

    @staticmethod
    def _ip_local() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))  # no llega a mandar nada, solo fuerza al SO a elegir la interfaz
            return s.getsockname()[0]
        except OSError:
            return socket.gethostbyname(socket.gethostname())
        finally:
            s.close()
