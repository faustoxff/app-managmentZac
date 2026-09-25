"""La impresión tiene que sacar TODOS los datos del cliente, notas completas incluidas."""
import pathlib
import sys
import unittest
import webbrowser

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import impresion  # noqa: E402
from models import Cliente  # noqa: E402


class TestImpresion(unittest.TestCase):
    def test_sale_todo_incluidas_las_notas_completas(self):
        cliente = Cliente(
            id=1, nombre="PEREZ JUAN", contacto="2231234567", estado_id=1, estado_nombre="Nuevo",
            estado_color="#fff", fecha_actualizacion="2026-09-24T10:00:00",
            fecha_alta="2026-09-22T09:00:00", notas="linea uno\nlinea dos " + "largo " * 40,
            recomendado_por="ARA",
        )
        abiertos = []
        original = webbrowser.open
        webbrowser.open = abiertos.append
        try:
            impresion.imprimir_clientes([cliente])
        finally:
            webbrowser.open = original
        html = pathlib.Path(abiertos[0][len("file://"):]).read_text(encoding="utf-8")
        for esperado in ("PEREZ JUAN", "2231234567", "Nuevo", "ARA", "linea uno\nlinea dos"):
            self.assertIn(esperado, html)
        self.assertEqual(html.count("largo "), 40)
        for columna in ("Fecha de alta", "Última actualización", "Recomendado por", "Notas"):
            self.assertIn(f"<th>{columna}</th>", html)


if __name__ == "__main__":
    unittest.main()
