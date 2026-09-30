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
        nuevo = self.estado_id("NUEVO")
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
        nuevo = self.estado_id("NUEVO")
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
            self.assertEqual(app.tree.heading("recomendado_por")["text"], "REC.")
        finally:
            app.destroy()

    def test_encabezados_en_mayuscula(self):
        app = self._app()
        try:
            for col in app.tree["columns"]:
                texto = app.tree.heading(col)["text"]
                self.assertEqual(texto, texto.upper())
        finally:
            app.destroy()



class TestBotonLimpiarFiltroYSeleccion(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        nuevo = self.estado_id("NUEVO")
        db.crear_cliente("A", "1", nuevo)
        db.crear_cliente("B", "2", nuevo)
        db.crear_cliente("C", "3", nuevo)

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

    def test_boton_limpiar_filtro_se_habilita_y_limpia(self):
        app = self._app()
        try:
            self.assertEqual(str(app.limpiar_filtro_btn["state"]), "disabled")
            app._aplicar_filtros({"recomendado_por": "ARA"})
            self.assertEqual(str(app.limpiar_filtro_btn["state"]), "normal")
            app._limpiar_filtro()
            self.assertEqual(str(app.limpiar_filtro_btn["state"]), "disabled")
            self.assertEqual(app.filtros, {})
        finally:
            app.destroy()

    def test_estado_todos_no_cuenta_como_filtro_activo(self):
        app = self._app()
        try:
            app._aplicar_filtros({"estado_nombre": "(Todos)"})
            self.assertEqual(str(app.limpiar_filtro_btn["state"]), "disabled")
        finally:
            app.destroy()

    def test_contador_de_seleccionados(self):
        app = self._app()
        try:
            ids = [str(c.id) for c in app._clientes_actuales]
            self.assertEqual(app.seleccion_label.cget("text"), "")
            app.tree.selection_set(ids[0])
            app.update()
            self.assertEqual(app.seleccion_label.cget("text"), "1 cliente seleccionado")
            app.tree.selection_set(ids)
            app.update()
            self.assertEqual(app.seleccion_label.cget("text"), "3 clientes seleccionados")
            app.tree.selection_remove(*ids)
            app.update()
            self.assertEqual(app.seleccion_label.cget("text"), "")
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()


class TestOrdenarPorEncabezado(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        nuevo = self.estado_id("NUEVO")
        db.crear_cliente("ZAPATA", "1", nuevo, "", "MARA")
        db.crear_cliente("ACOSTA", "2", nuevo, "", "ARA")
        db.crear_cliente("MEDINA", "3", nuevo, "", "ARA")
        db.crear_cliente("BAEZ", "4", nuevo, "", "")

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

    def _nombres(self, app):
        return [app.tree.item(i)["values"][0] for i in app.tree.get_children()]

    def test_clic_en_nombre_ordena_alfabetico_y_el_segundo_invierte(self):
        app = self._app()
        try:
            app._ordenar_por_columna("nombre")
            self.assertEqual(self._nombres(app), ["ACOSTA", "BAEZ", "MEDINA", "ZAPATA"])
            self.assertEqual(app.tree.heading("nombre")["text"], "NOMBRE ▲")
            app._ordenar_por_columna("nombre")
            self.assertEqual(self._nombres(app), ["ZAPATA", "MEDINA", "BAEZ", "ACOSTA"])
            self.assertEqual(app.tree.heading("nombre")["text"], "NOMBRE ▼")
        finally:
            app.destroy()

    def test_clic_en_recomendado_agrupa_por_ese_valor(self):
        app = self._app()
        try:
            app._ordenar_por_columna("recomendado_por")
            recs = [app.tree.item(i)["values"][5] for i in app.tree.get_children()]
            self.assertEqual(recs, sorted(recs))
        finally:
            app.destroy()

    def test_encabezados_alta_y_modificacion(self):
        app = self._app()
        try:
            self.assertEqual(app.tree.heading("fecha_alta")["text"], "ALTA")
            self.assertEqual(app.tree.heading("fecha")["text"], "MODIFICACIÓN")
        finally:
            app.destroy()
