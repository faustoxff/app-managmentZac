"""Chequeo periódico contra Z2: avisa una sola vez por cliente, no avisa de los que vinieron
de Z2, y deja cambiarles el estado sin tocar Z2."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import db  # noqa: E402
from test_estados import BaseDB  # noqa: E402
from test_z2_espejo import caso  # noqa: E402


class TestChequeoZ2(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        self._config_orig = config.CONFIG_PATH
        config.CONFIG_PATH = self.dir / "config.json"
        nuevo = self.estado_id("NUEVO")
        db.crear_cliente("PEREZ JUAN", "2235000001", nuevo)
        db.crear_cliente("TRAIDO", "2235000003", nuevo, origen="z2")
        db.crear_cliente("NADA", "2235999999", nuevo)
        db.reemplazar_z2_casos([caso("PEREZ", "JUAN", "2235000001"), caso("TRAIDO", "", "2235000003")])

    def tearDown(self):
        config.CONFIG_PATH = self._config_orig
        super().tearDown()

    def _app(self):
        import tkinter as tk

        try:
            tk.Tk().destroy()
        except tk.TclError:
            self.skipTest("sin display disponible para probar Tkinter")
        from ui.app import App

        return App()

    def test_avisa_una_sola_vez_y_no_de_los_traidos_de_z2(self):
        app = self._app()
        try:
            self.assertEqual([r["cliente"].nombre for r in app._nuevos_en_z2()], ["PEREZ JUAN"])
            app._avisar_nuevos_en_z2()
            self.assertTrue(app._aviso_z2.winfo_exists())
            app._aviso_z2.destroy()
            self.assertEqual(app._nuevos_en_z2(), [])
        finally:
            app.destroy()

    def test_cambiar_estado_desde_el_aviso(self):
        import tkinter.messagebox as mb

        app = self._app()
        mb.askyesno = lambda *a, **k: True
        try:
            app._avisar_nuevos_en_z2()
            av = app._aviso_z2
            av._seleccionar_todos()
            av.estado_var.set("CLIENTE")
            av._cambiar_estado()
            estados = {c.nombre: c.estado_nombre for c in db.listar_clientes()}
            self.assertEqual(estados["PEREZ JUAN"], "CLIENTE")
            self.assertEqual(estados["NADA"], "NUEVO")
            self.assertEqual(len(db.listar_z2_casos()[0]), 2)  # Z2 no se toca
        finally:
            app.destroy()

    def test_cambiar_estado_de_uno_desde_la_celda(self):
        import tkinter as tk

        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin display disponible para probar Tkinter")
        from ui.comparacion_z2_popup import ComparacionZ2Popup

        try:
            pop = ComparacionZ2Popup(root)
            root.update()
            fila = pop.tree.get_children()[0]
            pop._abrir_combo_estado(fila, "#3")
            pop._combo_estado.set("CLIENTE")
            pop._combo_estado.event_generate("<<ComboboxSelected>>")
            root.update()
            estados = {c.nombre: c.estado_nombre for c in db.listar_clientes()}
            self.assertEqual(estados["PEREZ JUAN"], "CLIENTE")
            self.assertEqual(estados["NADA"], "NUEVO")
        finally:
            root.destroy()

    def test_la_ventana_se_abre_una_sola_vez_por_dia(self):
        from datetime import date

        app = self._app()
        try:
            app._avisar_nuevos_en_z2()
            app._aviso_z2.destroy()
            db.crear_cliente("OTRO", "2235000003", self.estado_id("NUEVO"))
            db.reemplazar_z2_casos([caso("PEREZ", "JUAN", "2235000001"), caso("OTRO", "", "2235000003")])
            app._avisar_nuevos_en_z2()
            self.assertFalse(app._aviso_z2.winfo_exists())
            self.assertEqual(config.obtener_z2_ultimo_aviso(), date.today().isoformat())
            # Al día siguiente sí: el que apareció después no se perdió.
            config.guardar_z2_ultimo_aviso("2000-01-01")
            app._avisar_nuevos_en_z2()
            self.assertTrue(app._aviso_z2.winfo_exists())
        finally:
            app.destroy()

    def test_config_recuerda_avisados(self):
        config.agregar_z2_avisados([1, 2])
        config.agregar_z2_avisados([2, 3])
        self.assertEqual(config.obtener_z2_avisados(), {1, 2, 3})


if __name__ == "__main__":
    unittest.main()
