"""Pruebas de la búsqueda de coincidencias del panel lateral del alta de clientes.

La función es nueva y es la que decide qué le aparece al usuario mientras tipea, así que
estas pruebas fijan los tres criterios que la hacen útil: no marca falsamente por un
prefijo corto, marca por teléfono aunque el nombre sea otro, y ordena las coincidencias
fuertes (teléfono) antes de las débiles (nombre parecido).
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import db  # noqa: E402
from test_estados import BaseDB  # noqa: E402


class TestBusquedaEnVivo(BaseDB):
    def setUp(self):
        super().setUp()
        db.init_db()
        self.nuevo = self.estado_id("NUEVO")
        self.ok = self.estado_id("OK")

    def _nombres(self, resultado):
        return {c.nombre for c in resultado}

    # ---------- match por teléfono ----------

    def test_telefono_identico_encuentra_aunque_el_nombre_sea_otro(self):
        db.crear_cliente("MARIA PEREZ", "1155551234", self.nuevo)
        # Nombre completamente distinto: el teléfono solo tiene que coincidir.
        r = db.buscar_posibles_duplicados("OTRO NOMBRE", "11 5555-1234")
        self.assertEqual(self._nombres(r), {"MARIA PEREZ"})

    def test_telefono_con_distinto_formato_se_normaliza(self):
        db.crear_cliente("MARIA PEREZ", "1155551234", self.nuevo)
        r = db.buscar_posibles_duplicados("OTRO", "(11) 5555 1234")
        self.assertEqual(len(r), 1)

    def test_telefono_distinto_no_encuentra(self):
        db.crear_cliente("MARIA PEREZ", "1155551234", self.nuevo)
        r = db.buscar_posibles_duplicados("OTRO", "1199999999")
        self.assertEqual(r, [])

    def test_consulta_solo_telefono_no_dispara_el_nombre(self):
        # Sin nombre no hay nada que comparar por nombre, pero el teléfono sigue serviendo.
        db.crear_cliente("MARIA PEREZ", "1155551234", self.nuevo)
        self.assertEqual(len(db.buscar_posibles_duplicados("", "1155551234")), 1)

    # ---------- match parcial por nombre ----------

    def test_prefijo_del_nombre_encuentra(self):
        # El caso que motiva la funcionalidad: todavía no terminaste de escribir el nombre.
        db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        r = db.buscar_posibles_duplicados("JOSE", "1199999999")
        self.assertEqual(self._nombres(r), {"JOSE GARCIA"})

    def test_nombre_completo_encuentra(self):
        db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        r = db.buscar_posibles_duplicados("JOSE GARCIA", "1199999999")
        self.assertEqual(len(r), 1)

    def test_match_parcial_ignora_tildes_y_mayusculas(self):
        # Los nombres se guardan normalizados; lo tipeado también tiene que normalizarse.
        db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        r = db.buscar_posibles_duplicados("josé", "1199999999")
        self.assertEqual(len(r), 1)

    def test_nombre_prefijo_muy_corto_no_dispara(self):
        # 1-2 letras matchearían casi toda la base: el panel tiene que quedarse oculto.
        db.crear_cliente("ANA", "1155551111", self.nuevo)
        db.crear_cliente("MARIA PEREZ", "1155552222", self.nuevo)
        db.crear_cliente("JOSE GARCIA", "1155553333", self.nuevo)
        self.assertEqual(db.buscar_posibles_duplicados("A", "1199999999"), [])
        self.assertEqual(db.buscar_posibles_duplicados("AN", "1199999999"), [])

    def test_tres_letras_si_dispara(self):
        db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        self.assertEqual(len(db.buscar_posibles_duplicados("JOS", "1199999999")), 1)

    def test_nombre_sin_coincidir_no_encuentra(self):
        db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        self.assertEqual(db.buscar_posibles_duplicados("PEDRO", "1199999999"), [])

    def test_guion_bajo_en_el_nombre_se_busca_literal(self):
        # Sin escapar, LIKE trataría el "_" como comodín de un solo carácter y matchearía
        # cualquier nombre de la misma longitud.
        db.crear_cliente("MARIA_LOPEZ", "1155551111", self.nuevo)
        db.crear_cliente("MARIAX LOPEZ", "1155552222", self.nuevo)
        r = db.buscar_posibles_duplicados("MARIA_LOPEZ", "1199999999")
        self.assertEqual(self._nombres(r), {"MARIA_LOPEZ"})

    def test_porcentaje_en_el_nombre_se_busca_literal(self):
        db.crear_cliente("100% CLIENTE", "1155551111", self.nuevo)
        r = db.buscar_posibles_duplicados("100%", "1199999999")
        self.assertEqual(len(r), 1)

    # ---------- casos borde ----------

    def test_campos_vacios_no_tocan_la_db(self):
        # Se llama en cada tecla: con medio campo vacío tiene que salir sin consultar.
        db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        self.assertEqual(db.buscar_posibles_duplicados("", ""), [])
        self.assertEqual(db.buscar_posibles_duplicados("", "   "), [])

    def test_excluir_id_saca_al_propio_cliente(self):
        # Necesario si la búsqueda se reutiliza al editar: el cliente no es duplicado de sí mismo.
        c = db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        self.assertEqual(len(db.buscar_posibles_duplicados("JOSE GARCIA", "1155551111")), 1)
        self.assertEqual(db.buscar_posibles_duplicados("JOSE GARCIA", "1155551111", excluir_id=c), [])

    def test_telefono_exacto_va_primero_que_nombre_parecido(self):
        db.crear_cliente("PEREZ ANA", "1155550000", self.nuevo)  # solo nombre parecido
        db.crear_cliente("OTRA PERSONA", "1155551234", self.nuevo)  # teléfono exacto
        r = db.buscar_posibles_duplicados("PEREZ", "1155551234")
        self.assertEqual([c.nombre for c in r][0], "OTRA PERSONA")
        self.assertEqual(len(r), 2)

    def test_encuentra_varios_a_la_vez(self):
        db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        db.crear_cliente("JOSE LOPEZ", "1155552222", self.nuevo)
        db.crear_cliente("MARIA PEREZ", "1155553333", self.nuevo)
        r = db.buscar_posibles_duplicados("JOSE", "1199999999")
        self.assertEqual(self._nombres(r), {"JOSE GARCIA", "JOSE LOPEZ"})

    def test_no_rompe_con_cliente_sin_estado_nombre_vacio(self):
        # Un cliente con nombre corto o contacto vacío no debe romper la búsqueda.
        db.crear_cliente("AB", "1", self.nuevo)
        db.crear_cliente("JOSE GARCIA", "1155551111", self.nuevo)
        r = db.buscar_posibles_duplicados("JOSE", "1199999999")
        self.assertEqual(self._nombres(r), {"JOSE GARCIA"})


class TestNormalizacionDelPanel(unittest.TestCase):
    """Los helpers de normalización del panel tienen que dar el mismo resultado que los de
    db: si no, el rótulo "Coincide por" puede contradecir por qué la fila apareció."""

    def setUp(self):
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from ui.panel_duplicados import normalizar_contacto, normalizar_para_comparar

        self.norm_contacto = normalizar_contacto
        self.norm_nombre = normalizar_para_comparar

    def test_mismo_normalizado_de_telefono_que_db(self):
        for crudo in ("1155551234", "11 5555 1234", "(11) 5555-1234", " 1155551234 "):
            self.assertEqual(self.norm_contacto(crudo), db.normalizar_telefono(crudo))

    def test_mismo_normalizado_de_nombre_que_db(self):
        for crudo in ("José García", "JOSE GARCIA", "  josé   garcía ", "MARIA_LOPEZ"):
            self.assertEqual(self.norm_nombre(crudo), db.normalizar_nombre(crudo))

    def test_vacio(self):
        self.assertEqual(self.norm_contacto(""), "")
        self.assertEqual(self.norm_nombre(""), "")


if __name__ == "__main__":
    unittest.main()
