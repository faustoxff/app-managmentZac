"""Exporta una lista de contactos (solo nombre y teléfono) a un PDF.

Escribe el PDF a mano con la biblioteca estándar (fuente Helvetica incluida en todo lector de
PDF), para no sumar dependencias que después haya que empaquetar en el .exe. Soporta los
caracteres del español; cualquier otro símbolo fuera de Latin-1 se reemplaza por "?"."""
from typing import Iterable

from models import Cliente

ANCHO, ALTO = 595, 842  # A4 vertical, en puntos
MARGEN = 50
X_TELEFONO = 360
TAM = 11
INTERLINEADO = 20
MAX_CHARS_NOMBRE = 55  # a 11 pt, Helvetica entra en la columna del nombre
MAX_CHARS_TELEFONO = 30


def _codificar(texto: str, maximo: int) -> str:
    """Pasa a Latin-1 (WinAnsi, el que declara la fuente), recorta lo largo y escapa lo
    que tiene significado especial dentro de una cadena PDF."""
    texto = " ".join(texto.split())  # sin saltos de línea ni espacios repetidos
    if len(texto) > maximo:
        texto = texto[: maximo - 3] + "..."
    crudo = texto.encode("latin-1", errors="replace").decode("latin-1")
    return crudo.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pagina(filas: list[tuple[str, str]], titulo: str, numero: int, total: int) -> bytes:
    y = ALTO - MARGEN
    ops = [
        f"BT /F2 16 Tf {MARGEN} {y} Td ({_codificar(titulo, 80)}) Tj ET",
    ]
    y -= 34
    ops.append(f"BT /F2 {TAM} Tf {MARGEN} {y} Td (Nombre) Tj ET")
    ops.append(f"BT /F2 {TAM} Tf {X_TELEFONO} {y} Td (Tel\\351fono) Tj ET")
    y -= 6
    ops.append(f"{MARGEN} {y} m {ANCHO - MARGEN} {y} l S")
    y -= INTERLINEADO - 4
    for nombre, telefono in filas:
        ops.append(f"BT /F1 {TAM} Tf {MARGEN} {y} Td ({_codificar(nombre, MAX_CHARS_NOMBRE)}) Tj ET")
        ops.append(
            f"BT /F1 {TAM} Tf {X_TELEFONO} {y} Td ({_codificar(telefono, MAX_CHARS_TELEFONO)}) Tj ET"
        )
        y -= INTERLINEADO
    ops.append(f"BT /F1 9 Tf {ANCHO / 2 - 20:.0f} 28 Td (P\\341gina {numero} de {total}) Tj ET")
    return "\n".join(ops).encode("latin-1")


def _filas_por_pagina() -> int:
    util = ALTO - 2 * MARGEN - 34 - 6 - (INTERLINEADO - 4) - 20
    return util // INTERLINEADO


def generar_pdf(clientes: Iterable[Cliente], titulo: str = "Contactos") -> bytes:
    filas = [(c.nombre or "", c.contacto or "") for c in clientes]
    por_pagina = _filas_por_pagina()
    bloques = [filas[i : i + por_pagina] for i in range(0, len(filas), por_pagina)] or [[]]

    # Objetos: 1 catálogo, 2 páginas, 3-4 fuentes, y de a dos (página + contenido) por hoja.
    objetos: list[bytes] = [b""] * (4 + 2 * len(bloques))
    ids_paginas = [5 + 2 * i for i in range(len(bloques))]
    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{i} 0 R" for i in ids_paginas)
    objetos[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(bloques)} >>".encode()
    objetos[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    objetos[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    for i, bloque in enumerate(bloques):
        contenido = _pagina(bloque, titulo, i + 1, len(bloques))
        objetos[4 + 2 * i] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO} {ALTO}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {ids_paginas[i] + 1} 0 R >>"
        ).encode()
        objetos[5 + 2 * i] = b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream"

    salida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, cuerpo in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida += f"{n} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n"
    ).encode()
    return bytes(salida)


def exportar_pdf(path: str, clientes: Iterable[Cliente], titulo: str = "Contactos") -> None:
    with open(path, "wb") as f:
        f.write(generar_pdf(clientes, titulo))
