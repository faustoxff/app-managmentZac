"""Copia local de las carpetas de Z2 (tabla z2_casos).

Lo que se pidió explícitamente:
  - Sincronizar reemplaza la copia de Z2, pero NUNCA toca la tabla de clientes de Z1.
  - Un cliente que ya pasó a Z1 no se borra aunque desaparezca de Z2.
  - Importar dos veces no vuelve a crear los mismos clientes.
"""
import pathlib
import sqlite3
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import db  # noqa: E402
import z2_sync  # noqa: E402
from test_estados import BaseDB  # noqa: E402


def caso(apellido, nombre, telefono, reco=""):
    return {"apellido": apellido, "nombre": nombre, "telefono": telefono, "recomendado_por": reco,
            "estado_planilla": "", "categoria": "", "fecha_accidente": "", "art": "", "dni": ""}


class TestZ2Espejo(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        self._leer_orig = z2_sync.leer_casos_de_z2

    def tearDown(self):
        z2_sync.leer_casos_de_z2 = self._leer_orig
        super().tearDown()

    def _foto_clientes(self):
        con = sqlite3.connect(db.DB_PATH)
        filas = con.execute("SELECT * FROM clientes ORDER BY id").fetchall()
        con.close()
        return filas

    def test_sincronizar_no_toca_la_tabla_de_clientes(self):
        nuevo = self.estado_id("NUEVO")
        db.crear_cliente("MANUAL UNO", "1111", nuevo, "nota", "ARA")
        db.crear_cliente("PEREZ JUAN", "2222", nuevo, "", "", origen="z2")
        antes = self._foto_clientes()

        z2_sync.leer_casos_de_z2 = lambda: [caso("GOMEZ", "ANA", "3333")]
        z2_sync.sincronizar_copia_local()
        z2_sync.leer_casos_de_z2 = lambda: []  # Z2 "borró" todo
        z2_sync.sincronizar_copia_local()

        self.assertEqual(self._foto_clientes(), antes)

    def test_sincronizar_reemplaza_la_copia_completa(self):
        z2_sync.leer_casos_de_z2 = lambda: [caso("A", "UNO", "1"), caso("B", "DOS", "2")]
        z2_sync.sincronizar_copia_local()
        z2_sync.leer_casos_de_z2 = lambda: [caso("C", "TRES", "3")]
        z2_sync.sincronizar_copia_local()
        casos, cuando = db.listar_z2_casos()
        self.assertEqual([c["apellido"] for c in casos], ["C"])
        self.assertTrue(cuando)

    def test_si_z2_falla_la_copia_anterior_queda(self):
        z2_sync.leer_casos_de_z2 = lambda: [caso("A", "UNO", "1")]
        z2_sync.sincronizar_copia_local()

        def falla():
            raise z2_sync.ErrorDeConexion("sin internet")

        z2_sync.leer_casos_de_z2 = falla
        with self.assertRaises(z2_sync.ErrorDeConexion):
            z2_sync.sincronizar_copia_local()
        self.assertEqual(len(db.listar_z2_casos()[0]), 1)

    def test_importar_dos_veces_no_duplica(self):
        casos = [caso("PEREZ", "JUAN", "2235000001"), caso("GOMEZ", "ANA", "2235000002"),
                 caso("SIN", "TELEFONO", "")]
        primera = z2_sync.comparar(casos)
        self.assertEqual(len(primera.nuevos), 3)
        z2_sync.importar(primera)

        segunda = z2_sync.comparar(casos)
        self.assertEqual(segunda.nuevos, [])
        self.assertEqual(len(db.listar_clientes()), 3)

    def test_aviso_de_duplicado_busca_en_la_copia_local(self):
        z2_sync.leer_casos_de_z2 = lambda: [caso("ACEVEDO", "FELIX", "2235-244401")]
        z2_sync.sincronizar_copia_local()
        self.assertEqual(len(db.buscar_en_z2_casos("CUALQUIERA", "2235244401")), 1)
        self.assertEqual(len(db.buscar_en_z2_casos("Acevedo Félix", "")), 1)
        self.assertEqual(db.buscar_en_z2_casos("OTRO", "1111"), [])


class TestComparacionZ1Z2(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        self.nuevo = self.estado_id("NUEVO")

    def test_coincide_por_telefono_aunque_haya_varios_en_el_campo(self):
        db.crear_cliente("GARCIA GLORIA", "2235271271 / 5304959", self.nuevo)
        db.reemplazar_z2_casos([caso("OTRA", "PERSONA", "530-4959")])
        r = db.comparar_z1_con_z2()
        self.assertEqual([(x["cliente"].nombre, x["motivo"]) for x in r], [("GARCIA GLORIA", "teléfono")])

    def test_coincide_por_nombre_sin_tildes(self):
        db.crear_cliente("ACEVEDO FELIX", "", self.nuevo)
        db.reemplazar_z2_casos([caso("ACEVEDO", "FÉLIX", "")])
        self.assertEqual(db.comparar_z1_con_z2()[0]["motivo"], "nombre")

    def test_telefono_y_nombre_cuentan_una_sola_vez(self):
        db.crear_cliente("PEREZ JUAN", "2235000001", self.nuevo)
        db.reemplazar_z2_casos([caso("PEREZ", "JUAN", "2235000001")])
        r = db.comparar_z1_con_z2()
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["motivo"], "teléfono y nombre")

    def test_sin_coincidencias_y_no_modifica_nada(self):
        db.crear_cliente("PEREZ JUAN", "2235000001", self.nuevo)
        db.reemplazar_z2_casos([caso("GOMEZ", "ANA", "2235999999")])
        con = sqlite3.connect(db.DB_PATH)
        antes = (con.execute("SELECT * FROM clientes").fetchall(), con.execute("SELECT * FROM z2_casos").fetchall())
        self.assertEqual(db.comparar_z1_con_z2(), [])
        despues = (con.execute("SELECT * FROM clientes").fetchall(), con.execute("SELECT * FROM z2_casos").fetchall())
        con.close()
        self.assertEqual(antes, despues)


class TestImportacionContraZ2(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        db.reemplazar_z2_casos([caso("ACEVEDO", "FELIX", "2235244401")])

    def test_fila_que_esta_en_z2_queda_para_revisar(self):
        from db import FilaImport

        r = db.procesar_lote([
            FilaImport(nombre="ACEVEDO FELIX", contacto="2235-244401"),
            FilaImport(nombre="OTRO", contacto="2235111111"),
        ])
        self.assertEqual(r.ok, 1)
        self.assertEqual(len(r.duplicados), 1)
        self.assertEqual(r.duplicados[0][1][0].origen, "z2")
        self.assertEqual([c.nombre for c in db.listar_clientes()], ["OTRO"])

    def test_cliente_local_se_reconoce_como_local_en_el_panel(self):
        # Regresión: la columna "origen" de la base pisaba el origen del panel ("local").
        db.crear_cliente("PEREZ JUAN", "2235000001", self.estado_id("NUEVO"), origen="z2")
        c = db.buscar_posibles_duplicados("PEREZ JUAN", "2235000001")[0]
        self.assertEqual(c.origen, "local")
        self.assertEqual(c.procedencia, "z2")


if __name__ == "__main__":
    unittest.main()
