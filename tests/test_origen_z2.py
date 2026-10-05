"""Clientes importados de Z2 se distinguen por el campo origen, no por el texto de notas."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import db  # noqa: E402
import z2_sync  # noqa: E402
from test_estados import BaseDB  # noqa: E402


class TestOrigenZ2(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        self.nuevo = self.estado_id("NUEVO")

    def test_filtro_por_origen_z2(self):
        db.crear_cliente("DE Z2", "1", self.nuevo, "", "", origen=z2_sync.ORIGEN_Z2)
        db.crear_cliente("MANUAL", "2", self.nuevo)
        self.assertEqual([c.nombre for c in db.listar_clientes(origen="z2")], ["DE Z2"])
        self.assertEqual(
            sorted(c.nombre for c in db.listar_clientes()), ["DE Z2", "MANUAL"]
        )

    def test_origen_sobrevive_a_reiniciar_y_se_edita_sin_perderlo(self):
        cid = db.crear_cliente("DE Z2", "1", self.nuevo, "", "", origen=z2_sync.ORIGEN_Z2)
        self.reiniciar(3)
        db.actualizar_cliente(cid, "DE Z2", "1", self.nuevo, "nota editada", "")
        self.assertEqual([c.nombre for c in db.listar_clientes(origen="z2")], ["DE Z2"])

    def test_origen_vacio_para_clientes_manuales(self):
        db.crear_cliente("MANUAL", "2", self.nuevo)
        self.assertEqual(db.listar_clientes(origen="z2"), [])


if __name__ == "__main__":
    unittest.main()
