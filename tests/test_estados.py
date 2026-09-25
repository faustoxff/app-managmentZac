"""Pruebas de regresión de los estados de los clientes. Si alguna falla, el build NO sigue:
los clientes de un usuario nunca deben cambiar de estado solos al abrir la app."""
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import db  # noqa: E402
import version  # noqa: E402


class BaseDB(unittest.TestCase):
    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self._orig = (db.DB_PATH, db.get_data_dir, db.LOG_PATH, db.BACKUPS_LOCALES_DIR, version.__version__)
        db.DB_PATH = self.dir / "clientes.db"
        db.get_data_dir = lambda: self.dir
        db.LOG_PATH = self.dir / "diagnostico.log"
        db.BACKUPS_LOCALES_DIR = self.dir / "backups_locales"
        version.__version__ = "9.9.9"

    def tearDown(self):
        db.DB_PATH, db.get_data_dir, db.LOG_PATH, db.BACKUPS_LOCALES_DIR, version.__version__ = self._orig

    def estado_id(self, nombre):
        return next(e.id for e in db.listar_estados() if e.nombre == nombre)

    def reparto(self):
        return dict(Counter(c.estado_nombre for c in db.listar_clientes()))

    def reiniciar(self, veces=5):
        for _ in range(veces):
            db.init_db()


class TestEstadosNoCambianSolos(BaseDB):
    def test_cada_estado_se_mantiene_al_reiniciar(self):
        db.init_db()
        esperado = {}
        for i, e in enumerate(db.listar_estados()):
            for j in range(3):
                db.crear_cliente(f"P{i}{j}", f"11500{i}{j}000", e.id)
            esperado[e.nombre] = 3
        self.reiniciar(6)
        self.assertEqual(self.reparto(), esperado)

    def test_nuevo_no_pasa_a_esperar(self):
        db.init_db()
        for i in range(5):
            db.crear_cliente(f"N{i}", f"1160000{i}00", self.estado_id("Nuevo"))
        self.reiniciar()
        self.assertEqual(self.reparto(), {"Nuevo": 5})

    def test_estado_propio_sobrevive(self):
        db.init_db()
        propio = db.crear_estado("Turno confirmado", "#123456")
        db.crear_cliente("A", "1170000001", propio)
        self.reiniciar()
        self.assertEqual(self.reparto(), {"Turno confirmado": 1})
        self.assertIn("Turno confirmado", [e.nombre for e in db.listar_estados()])

    def test_estado_renombrado_a_mano_sobrevive(self):
        db.init_db()
        db.actualizar_estado(self.estado_id("Viene"), "Viene a la clínica", "#06b6d4")
        db.crear_cliente("A", "1170000002", self.estado_id("Viene a la clínica"))
        self.reiniciar()
        self.assertEqual(self.reparto(), {"Viene a la clínica": 1})

    def test_base_dejada_por_el_bug_viejo_no_se_mueve(self):
        db.init_db()
        c = sqlite3.connect(db.DB_PATH)
        c.execute("UPDATE estados SET orden = 999 WHERE nombre = 'Nuevo'")
        c.commit()
        c.close()
        db.crear_cliente("A", "1180000001", self.estado_id("Nuevo"))
        db.crear_cliente("B", "1180000002", self.estado_id("Esperar"))
        self.reiniciar()
        self.assertEqual(self.reparto(), {"Nuevo": 1, "Esperar": 1})

    def test_esquema_viejo_de_5_estados_se_migra_una_vez(self):
        c = sqlite3.connect(db.DB_PATH)
        c.executescript(
            """
            CREATE TABLE estados (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE,
                color TEXT NOT NULL DEFAULT '#808080', orden INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, contacto TEXT,
                estado_id INTEGER NOT NULL, fecha_actualizacion TEXT NOT NULL, notas TEXT);
            INSERT INTO estados (nombre, orden) VALUES ('Contactado',1),('Cerrado',3),('Perdido',4);
            INSERT INTO clientes (nombre, contacto, estado_id, fecha_actualizacion)
              VALUES ('A','1',1,'2026-01-01'),('B','2',2,'2026-01-01'),('C','3',3,'2026-01-01');
            """
        )
        c.commit()
        c.close()
        self.reiniciar()
        self.assertEqual(self.reparto(), {"Viene": 1, "Cliente": 1, "Descartado": 1})

    def test_color_personalizado_se_respeta(self):
        db.init_db()
        db.actualizar_estado(self.estado_id("Esperar"), "Esperar", "#ff00ff")
        self.reiniciar()
        color = next(e.color for e in db.listar_estados() if e.nombre == "Esperar")
        self.assertEqual(color, "#ff00ff")

    def test_cantidad_de_estados_no_crece(self):
        self.reiniciar(8)
        self.assertEqual(len(db.listar_estados()), len(db.ESTADOS_SEED))


class TestVersionVieja(BaseDB):
    def test_app_vieja_no_migra_una_base_de_una_version_mas_nueva(self):
        version.__version__ = "9.9.9"
        db.init_db()
        db.crear_cliente("A", "1190000001", self.estado_id("Nuevo"))
        version.__version__ = "1.0.0"
        db.init_db()
        self.assertEqual(db.version_vieja_detectada(), "9.9.9")
        self.assertEqual(self.reparto(), {"Nuevo": 1})


class TestCopiaDeSeguridad(BaseDB):
    def test_se_crea_copia_al_arrancar_y_se_poda(self):
        db.init_db()
        db.crear_cliente("A", "1100000001", self.estado_id("Nuevo"))
        for _ in range(3):
            db.init_db()
        copias = list(db.BACKUPS_LOCALES_DIR.glob("clientes_*.db"))
        self.assertGreaterEqual(len(copias), 1)
        self.assertLessEqual(len(copias), db.MAX_COPIAS_ARRANQUE)


class TestVersionYTag(unittest.TestCase):
    def test_version_tiene_formato_x_y_z(self):
        partes = version.__version__.split(".")
        self.assertEqual(len(partes), 3)
        self.assertTrue(all(p.isdigit() for p in partes))


if __name__ == "__main__":
    unittest.main()
