"""Las columnas de la tabla se ajustan al contenido: ni tan angostas que corten texto corto,
ni tan anchas por una sola nota larga que no se pueda usar la tabla."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from test_estados import BaseDB  # noqa: E402


class TestColumnasAutoajuste(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()

    def _app(self):
        import tkinter as tk

        if not hasattr(self, "_root_probado"):
            try:
                tk.Tk().destroy()
            except tk.TclError:
                self.skipTest("sin display disponible para probar Tkinter")
            self._root_probado = True
        from ui.app import App

        return App()

    def test_columna_notas_crece_con_nota_larga_pero_no_sin_limite(self):
        nuevo = self.estado_id("Nuevo")
        db.crear_cliente("A", "1", nuevo, "N" * 500, "")
        app = self._app()
        try:
            minimo, maximo = app.ANCHOS_COLUMNA["notas"]
            ancho = app.tree.column("notas", "width")
            self.assertGreater(ancho, minimo)
            self.assertLessEqual(ancho, maximo)
        finally:
            app.destroy()

    def test_columna_corta_no_queda_mas_angosta_que_el_minimo(self):
        nuevo = self.estado_id("Nuevo")
        db.crear_cliente("A", "1", nuevo, "ok", "")
        app = self._app()
        try:
            for col in app.tree["columns"]:
                minimo, maximo = app.ANCHOS_COLUMNA[col]
                ancho = app.tree.column(col, "width")
                self.assertGreaterEqual(ancho, minimo)
                self.assertLessEqual(ancho, maximo)
        finally:
            app.destroy()

    def test_encabezado_recomendado_por_es_corto(self):
        app = self._app()
        try:
            self.assertEqual(app.tree.heading("recomendado_por")["text"], "Rec.")
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
