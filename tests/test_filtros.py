"""Filtros de la lista de clientes: recomendado por y fecha de alta."""
import pathlib
import sqlite3
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from test_estados import BaseDB  # noqa: E402


class TestFiltros(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        nuevo = self.estado_id("Nuevo")
        esperar = self.estado_id("Esperar")
        datos = [
            ("A UNO", "1", nuevo, "ARA", "2026-09-22T10:00:00"),
            ("B DOS", "2", esperar, "ARA", "2026-09-24T10:00:00"),
            ("C TRES", "3", nuevo, "MARA", "2026-09-24T11:00:00"),
            ("D CUATRO", "4", nuevo, "ARQ", "2026-09-18T09:00:00"),
            ("E CINCO", "5", nuevo, "", "2026-09-24T12:00:00"),
        ]
        for nombre, tel, est, rec, alta in datos:
            cid = db.crear_cliente(nombre, tel, est, "", rec)
            con = sqlite3.connect(db.DB_PATH)
            con.execute("UPDATE clientes SET fecha_alta = ? WHERE nombre = ?", (alta, nombre))
            con.commit()
            con.close()

    def nombres(self, **filtros):
        return sorted(c.nombre for c in db.listar_clientes(**filtros))

    def test_recomendado_exacto_no_trae_los_que_solo_lo_contienen(self):
        self.assertEqual(self.nombres(recomendado_por="ARA"), ["A UNO", "B DOS"])

    def test_recomendado_ignora_mayusculas(self):
        self.assertEqual(self.nombres(recomendado_por="ara"), ["A UNO", "B DOS"])

    def test_recomendado_texto_suelto_busca_por_contiene(self):
        self.assertEqual(self.nombres(recomendado_por="AR"), ["A UNO", "B DOS", "C TRES", "D CUATRO"])

    def test_lista_de_recomendados_sin_vacios_ni_repetidos(self):
        self.assertEqual(db.listar_recomendados(), ["ARA", "ARQ", "MARA"])

    def test_fecha_de_alta_desde_hasta(self):
        self.assertEqual(self.nombres(alta_desde="2026-09-24"), ["B DOS", "C TRES", "E CINCO"])
        self.assertEqual(self.nombres(alta_hasta="2026-09-22"), ["A UNO", "D CUATRO"])
        self.assertEqual(
            self.nombres(alta_desde="2026-09-22", alta_hasta="2026-09-22"), ["A UNO"]
        )

    def test_filtros_se_combinan(self):
        self.assertEqual(
            self.nombres(recomendado_por="ARA", estado_id=self.estado_id("Esperar")), ["B DOS"]
        )
        self.assertEqual(self.nombres(recomendado_por="ARA", alta_desde="2026-09-24"), ["B DOS"])

    def test_sin_filtros_trae_todos(self):
        self.assertEqual(len(self.nombres()), 5)


if __name__ == "__main__":
    unittest.main()
