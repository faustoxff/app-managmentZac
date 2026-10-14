"""Ventana de resultado de importación: descartar o cargar varios duplicados a la vez."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from db import FilaImport  # noqa: E402
from test_estados import BaseDB  # noqa: E402


class TestResumenImportVarios(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        nuevo = self.estado_id("NUEVO")
        for i in range(4):
            db.crear_cliente(f"PERSONA {i}", f"223500000{i}", nuevo)

    def _popup(self):
        import tkinter as tk
        import tkinter.messagebox as mb

        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin display disponible para probar Tkinter")
        root.withdraw()
        mb.askyesno = lambda *a, **k: True
        from ui.resumen_import_popup import ResumenImportPopup

        resultado = db.procesar_lote(
            [FilaImport(nombre=f"PERSONA {i}", contacto=f"223500000{i}") for i in range(4)]
        )
        return root, ResumenImportPopup(root, resultado, on_cerrar=lambda: None)

    def test_ctrl_a_selecciona_todos_y_descartar_los_saca_a_todos(self):
        root, pop = self._popup()
        try:
            self.assertEqual(pop._seleccionar_todos(), "break")
            self.assertEqual(len(pop.tree.selection()), 4)
            pop._descartar_seleccionados()
            self.assertEqual(pop.pendientes, [])
            self.assertEqual(len(db.listar_clientes()), 4)  # descartar no carga nada
        finally:
            root.destroy()

    def test_cargar_varios_seleccionados(self):
        root, pop = self._popup()
        try:
            pop.tree.selection_set(("1", "3"))
            pop._cargar_seleccionados()
            self.assertEqual([f.nombre for f, _ in pop.pendientes], ["PERSONA 0", "PERSONA 2"])
            self.assertEqual(len(db.listar_clientes()), 6)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
