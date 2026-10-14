"""Shift+↓ / Shift+↑ van extendiendo la selección en las tablas."""
import unittest


class TestShiftFlechas(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from tkinter import ttk

        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("sin display disponible para probar Tkinter")
        from ui.seleccion_teclado import habilitar_shift_flechas

        self.tree = ttk.Treeview(self.root, columns=("a",), show="headings", selectmode="extended")
        self.tree.pack()
        for i in range(5):
            self.tree.insert("", "end", iid=str(i), values=(i,))
        habilitar_shift_flechas(self.tree)
        self.root.update()
        self.tree.focus_force()

    def tearDown(self):
        self.root.destroy()

    def _teclas(self, *secuencia):
        for tecla in secuencia:
            self.tree.event_generate(tecla)
        self.root.update()
        return list(self.tree.selection())

    def test_extiende_y_achica(self):
        self.tree.selection_set("1")
        self.tree.focus("1")
        self.assertEqual(self._teclas("<Shift-Down>", "<Shift-Down>"), ["1", "2", "3"])
        self.assertEqual(self._teclas("<Shift-Up>"), ["1", "2"])

    def test_sube_desde_el_ancla(self):
        self.tree.selection_set("3")
        self.tree.focus("3")
        self.assertEqual(self._teclas("<Shift-Up>", "<Shift-Up>"), ["1", "2", "3"])

    def test_no_se_pasa_del_final(self):
        self.tree.selection_set("3")
        self.tree.focus("3")
        self.assertEqual(self._teclas(*["<Shift-Down>"] * 6), ["3", "4"])


if __name__ == "__main__":
    unittest.main()
