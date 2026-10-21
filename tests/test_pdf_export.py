"""El PDF exportado lleva solo nombre y teléfono, y es un PDF bien formado aunque haya
acentos, paréntesis o muchas filas (varias páginas)."""
import pathlib
import re
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pdf_export  # noqa: E402
from models import Cliente  # noqa: E402


def _cliente(i, nombre, tel, **kw):
    return Cliente(
        id=i, nombre=nombre, contacto=tel, estado_id=1, fecha_actualizacion="2026-09-24T10:00:00", **kw
    )


class TestPdfExport(unittest.TestCase):
    def test_estructura_valida_y_xref_correcta(self):
        pdf = pdf_export.generar_pdf([_cliente(1, "PÉREZ, JUAN (hijo)", "2231234567")])
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        inicio = int(re.search(rb"startxref\n(\d+)", pdf).group(1))
        self.assertTrue(pdf[inicio:].startswith(b"xref"))
        for m in re.finditer(rb"(\d{10}) 00000 n", pdf):
            self.assertRegex(pdf[int(m.group(1)) :], rb"^\d+ 0 obj")

    def test_solo_nombre_y_telefono(self):
        c = _cliente(1, "GOMEZ ANA", "1155551234", notas="NOTA SECRETA", recomendado_por="ARA")
        pdf = pdf_export.generar_pdf([c])
        self.assertIn(b"GOMEZ ANA", pdf)
        self.assertIn(b"1155551234", pdf)
        self.assertNotIn(b"NOTA SECRETA", pdf)
        self.assertNotIn(b"ARA", pdf)

    def test_parentesis_y_acentos_se_escapan_y_codifican(self):
        pdf = pdf_export.generar_pdf([_cliente(1, "Ñandú (x)", "1")])
        self.assertIn(b"(\xd1and\xfa \\(x\\))", pdf)

    def test_muchas_filas_generan_varias_paginas(self):
        n = pdf_export._filas_por_pagina()
        pdf = pdf_export.generar_pdf([_cliente(i, f"C{i}", str(i)) for i in range(n * 2 + 1)])
        self.assertEqual(pdf.count(b"/Type /Page "), 3)
        self.assertIn(b"/Count 3", pdf)

    def test_lista_vacia_igual_da_un_pdf(self):
        self.assertEqual(pdf_export.generar_pdf([]).count(b"/Type /Page "), 1)


if __name__ == "__main__":
    unittest.main()
