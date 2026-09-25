"""Genera una vista HTML simple de clientes y la abre en el navegador para imprimir desde ahí
(sin dependencias pesadas tipo reportlab: alcanza con el botón "Imprimir" del navegador)."""
import html
import tempfile
import webbrowser
from typing import Iterable

from fechas import formatear_fecha
from models import Cliente


def imprimir_clientes(clientes: Iterable[Cliente]) -> None:
    filas_html = "\n".join(
        "<tr>"
        f"<td>{html.escape(c.nombre)}</td>"
        f"<td>{html.escape(c.contacto)}</td>"
        f"<td>{html.escape(c.estado_nombre)}</td>"
        f"<td>{html.escape(formatear_fecha(c.fecha_alta))}</td>"
        f"<td>{html.escape(formatear_fecha(c.fecha_actualizacion))}</td>"
        f"<td>{html.escape(c.recomendado_por or '')}</td>"
        f"<td class=\"notas\">{html.escape(c.notas or '')}</td>"
        "</tr>"
        for c in clientes
    )

    contenido = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Clientes</title>
<style>
  body {{ font-family: sans-serif; margin: 24px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #999; padding: 6px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #eee; }}
  /* Las notas salen completas: respetan los saltos de línea y se parten en varias líneas
     en vez de cortarse o achicarse. */
  td.notas {{ white-space: pre-wrap; overflow-wrap: anywhere; min-width: 200px; }}
  thead {{ display: table-header-group; }}  /* repite el encabezado en cada hoja */
  tr {{ page-break-inside: avoid; }}
  @page {{ size: A4 landscape; margin: 12mm; }}
  button {{ font-size: 1rem; padding: 8px 16px; margin-bottom: 16px; }}
  @media print {{ button {{ display: none; }} }}
</style></head><body>
<h2>Clientes</h2>
<button onclick="window.print()">Imprimir</button>
<table>
<thead><tr><th>Nombre</th><th>Contacto</th><th>Estado</th><th>Fecha de alta</th><th>Última actualización</th><th>Recomendado por</th><th>Notas</th></tr></thead>
<tbody>
{filas_html}
</tbody>
</table>
</body></html>"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(contenido)
        path = f.name

    webbrowser.open(f"file://{path}")
