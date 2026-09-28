"""Recordatorios: guardar fecha en el cliente, y listar los de hoy para el aviso de las 8am."""
import pathlib
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from test_estados import BaseDB  # noqa: E402


class TestRecordatorios(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        self.nuevo = self.estado_id("Nuevo")

    def test_crear_con_recordatorio_para_hoy(self):
        hoy = date.today().isoformat()
        db.crear_cliente("CON TURNO", "1", self.nuevo, "", "", hoy)
        db.crear_cliente("SIN TURNO", "2", self.nuevo)
        self.assertEqual([c.nombre for c in db.listar_recordatorios_de_hoy()], ["CON TURNO"])

    def test_recordatorio_de_otro_dia_no_sale_hoy(self):
        manana = (date.today() + timedelta(days=1)).isoformat()
        db.crear_cliente("PARA MAÑANA", "1", self.nuevo, "", "", manana)
        self.assertEqual(db.listar_recordatorios_de_hoy(), [])

    def test_actualizar_cliente_pone_y_quita_recordatorio(self):
        hoy = date.today().isoformat()
        cid = db.crear_cliente("A", "1", self.nuevo)
        db.actualizar_cliente(cid, "A", "1", self.nuevo, "", "", hoy)
        self.assertEqual(len(db.listar_recordatorios_de_hoy()), 1)
        db.actualizar_cliente(cid, "A", "1", self.nuevo, "", "", "")
        self.assertEqual(db.listar_recordatorios_de_hoy(), [])

    def test_recordatorio_sobrevive_a_reiniciar(self):
        hoy = date.today().isoformat()
        db.crear_cliente("A", "1", self.nuevo, "", "", hoy)
        self.reiniciar(4)
        self.assertEqual(len(db.listar_recordatorios_de_hoy()), 1)


if __name__ == "__main__":
    unittest.main()
