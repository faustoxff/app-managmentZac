"""Guardar un cliente nuevo tiene que funcionar siempre, con o sin coincidencia en Z2.
Un bug acá dejaba el botón Guardar sin efecto (NameError dentro del callback)."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import db  # noqa: E402
from test_estados import BaseDB  # noqa: E402


class TestGuardarClienteNuevo(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        self._config_orig = config.CONFIG_PATH
        config.CONFIG_PATH = self.dir / "config.json"

    def tearDown(self):
        config.CONFIG_PATH = self._config_orig
        super().tearDown()

    def _ventana(self):
        import tkinter as tk

        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin display disponible para probar Tkinter")
        root.withdraw()
        return root

    def _guardar_y_esperar(self, root, form, nombre, telefono):
        form.nombre_var.set(nombre)
        form.contacto_var.set(telefono)
        form.update()
        form._guardar()
        # Un mainloop de verdad: la consulta a Z2 corre en un hilo y vuelve con after(0),
        # y eso solo se procesa dentro de mainloop (igual que en la app).
        root.after(800, root.quit)
        root.mainloop()

    def test_dos_clientes_seguidos_sin_coincidencias_en_z2(self):
        import z2_sync
        from ui.cliente_form import ClienteForm
        import tkinter.messagebox as mb

        root = self._ventana()
        z2_orig = z2_sync.buscar_coincidencias_en_z2
        z2_sync.buscar_coincidencias_en_z2 = lambda n, t: []
        mb.showwarning = mb.showerror = mb.showinfo = lambda *a, **k: None
        try:
            form = ClienteForm(root, on_saved=lambda: None)
            self._guardar_y_esperar(root, form, "PRIMERO UNO", "1150000001")
            self._guardar_y_esperar(root, form, "SEGUNDO DOS", "1150000002")
            nombres = sorted(c.nombre for c in db.listar_clientes())
            self.assertEqual(nombres, ["PRIMERO UNO", "SEGUNDO DOS"])
        finally:
            z2_sync.buscar_coincidencias_en_z2 = z2_orig
            root.destroy()

    def test_guardar_con_coincidencia_en_z2_pregunta_y_guarda(self):
        import z2_sync
        from ui.cliente_form import ClienteForm
        import tkinter.messagebox as mb

        root = self._ventana()
        z2_orig = z2_sync.buscar_coincidencias_en_z2
        preguntas = []
        z2_sync.buscar_coincidencias_en_z2 = lambda n, t: [
            {"id": "x", "nombre": "OTRO", "telefono": "1", "detalle": "carpeta ART"}
        ]
        mb.askyesno = lambda *a, **k: (preguntas.append(a[0]), True)[1]
        mb.showwarning = mb.showerror = mb.showinfo = lambda *a, **k: None
        try:
            form = ClienteForm(root, on_saved=lambda: None)
            self._guardar_y_esperar(root, form, "NUEVO Z2", "1199999999")
            self.assertEqual(len(preguntas), 1)
            self.assertIn("NUEVO Z2", [c.nombre for c in db.listar_clientes()])
        finally:
            z2_sync.buscar_coincidencias_en_z2 = z2_orig
            root.destroy()


if __name__ == "__main__":
    unittest.main()
