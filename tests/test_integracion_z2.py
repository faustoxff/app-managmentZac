"""Pruebas de la integración con Z2 (Gestor de Carpetas ART).

Lo que se verifica acá es la parte que puede romper en silencio: que Z1 nunca quede pegado si
Z2 no está, y que una respuesta rara de Z2 no reviente la UI. El formato de la respuesta se
respeta tal cual lo manda Z2 (server/integracion.js de este repo).
"""
import json
import unittest
from unittest import mock
import urllib.error

import config
import integracion_z2


class FakeRespuesta:
    """Suficiente para urlopen(): contexto con read() y close()."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class TestIntegracionZ2(unittest.TestCase):
    def setUp(self):
        self._config_original = config._leer_config()
        config.guardar_z2_url("https://z2.example.com")
        config.guardar_z2_token("token-de-prueba")

    def tearDown(self):
        # Restaura el config real del usuario: los tests escriben en el mismo config.json que
        # usa la app de verdad, y dejar la URL de prueba pondría avisos fantasma.
        import config as cfg

        for clave in ("z2_url", "z2_token"):
            datos = cfg._leer_config()
            if clave in self._config_original:
                datos[clave] = self._config_original[clave]
            else:
                datos.pop(clave, None)
            cfg._escribir_config(datos)

    def _mock_urlopen(self, **kwargs):
        """mock.patch de urlopen. Acepta return_value= o side_effect= igual que mock.patch,
        que es más claro que pasar la resolución posicionalmente en cada test."""
        return mock.patch.object(integracion_z2.urllib.request, "urlopen", **kwargs)

    # ---------- no configurado ----------

    def test_sin_url_no_hace_ninguna_consulta(self):
        config.guardar_z2_url("")
        with mock.patch.object(integracion_z2.urllib.request, "urlopen") as urlopen:
            self.assertEqual(integracion_z2.buscar_coincidencias("JOSE", ""), [])
        urlopen.assert_not_called()

    def test_sin_token_no_hace_ninguna_consulta(self):
        config.guardar_z2_token("")
        with mock.patch.object(integracion_z2.urllib.request, "urlopen") as urlopen:
            self.assertEqual(integracion_z2.buscar_coincidencias("JOSE", ""), [])
        urlopen.assert_not_called()

    # ---------- Z2 caído: la app sigue igual ----------

    def test_z2_caido_devuelve_vacio(self):
        with self._mock_urlopen(side_effect=urllib.error.URLError("no route to host")):
            self.assertEqual(integracion_z2.buscar_coincidencias("JOSE", "113"), [])

    def test_timeout_devuelve_vacio(self):
        with self._mock_urlopen(side_effect=TimeoutError()):
            self.assertEqual(integracion_z2.buscar_coincidencias("JOSE", ""), [])

    def test_token_invalido_devuelve_vacio(self):
        # HTTPError además de ser una excepción es un objeto con fp: si el test no lo cierra,
        # al final del run Python se queja con un ResourceWarning ("cleaning up <HTTPError
        # 401>"). Se cierra explícitamente para que la salida de los tests quede limpia.
        error = urllib.error.HTTPError("u", 401, "no", None, None)
        try:
            with self._mock_urlopen(side_effect=error):
                self.assertEqual(integracion_z2.buscar_coincidencias("JOSE", ""), [])
        finally:
            error.close()

    def test_json_invalido_devuelve_vacio(self):
        # Un proxy o una página de error con estado 200: status ok, body inútil.
        with self._mock_urlopen(return_value=FakeRespuesta(b"<html>404</html>")):
            self.assertEqual(integracion_z2.buscar_coincidencias("JOSE", ""), [])

    def test_payload_con_forma_inesperada_no_revienta(self):
        # Z2 es otro programa: si mañana cambia la forma de la respuesta, Z1 tiene que
        # seguir andando con lo poco que entienda.
        with self._mock_urlopen(return_value=FakeRespuesta(b'{"coincidencias": "no soy lista"}')):
            self.assertEqual(integracion_z2.buscar_coincidencias("JOSE", ""), [])

    def test_elementos_que_no_son_dict_se_descartan(self):
        payload = json.dumps({"coincidencias": ["basura", 42, {"nombre": "JOSE"}]}).encode()
        with self._mock_urlopen(return_value=FakeRespuesta(payload)):
            resultado = integracion_z2.buscar_coincidencias("JOSE", "")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["nombre"], "JOSE")

    # ---------- camino feliz ----------

    def test_mapea_las_coincidencias_de_z2(self):
        payload = json.dumps(
            {
                "coincidencias": [
                    {
                        "origen": "z2",
                        "id": "0d9d5f0e-1111-2222-3333-444455556666",
                        "nombre": "GARCIA JOSE",
                        "telefono": "1134567890",
                        "dni": "30111222",
                        "detalle": "ART: AAPA — Estado: En tratamiento",
                    }
                ]
            }
        ).encode()
        with self._mock_urlopen(return_value=FakeRespuesta(payload)):
            resultado = integracion_z2.buscar_coincidencias("JOSE", "1134567890")

        self.assertEqual(len(resultado), 1)
        fila = resultado[0]
        self.assertEqual(fila["origen"], "z2")
        self.assertEqual(fila["nombre"], "GARCIA JOSE")
        self.assertEqual(fila["telefono"], "1134567890")
        self.assertIn("ART: AAPA", fila["detalle"])

    def test_envia_el_token_en_authorization(self):
        payload = json.dumps({"coincidencias": []}).encode()
        with self._mock_urlopen(return_value=FakeRespuesta(payload)) as urlopen:
            integracion_z2.buscar_coincidencias("JOSE", "")

        peticion = urlopen.call_args[0][0]
        self.assertEqual(peticion.get_header("Authorization"), "Bearer token-de-prueba")

    def test_manda_nombre_y_telefono_en_la_query(self):
        payload = json.dumps({"coincidencias": []}).encode()
        with self._mock_urlopen(return_value=FakeRespuesta(payload)) as urlopen:
            integracion_z2.buscar_coincidencias("JOSE PEREZ", "11 3456-7890")

        url = urlopen.call_args[0][0].full_url
        self.assertIn("api/integracion/coincidencias", url)
        self.assertIn("nombre=JOSE+PEREZ", url)
        self.assertIn("telefono=11+3456-7890", url)

    def test_url_con_barra_final_no_la_duplica(self):
        config.guardar_z2_url("https://z2.example.com/")
        payload = json.dumps({"coincidencias": []}).encode()
        with self._mock_urlopen(return_value=FakeRespuesta(payload)) as urlopen:
            integracion_z2.buscar_coincidencias("JOSE", "")

        url = urlopen.call_args[0][0].full_url
        self.assertNotIn("com//api", url)
        self.assertIn("com/api/integracion", url)

    # ---------- probar conexión ----------

    def test_probar_conexion_ok(self):
        with self._mock_urlopen(return_value=FakeRespuesta(b'{"coincidencias": []}')):
            ok, mensaje = integracion_z2.probar_conexion()
        self.assertTrue(ok)
        self.assertIn("z2.example.com", mensaje)

    def test_probar_conexion_explica_el_401(self):
        # Un mensaje genérico de HTTP no le sirve de nada al usuario: el 401 casi siempre
        # significa token mal copiado, y eso sí tiene una acción concreta.
        error = urllib.error.HTTPError("u", 401, "no", None, None)
        try:
            with self._mock_urlopen(side_effect=error):
                ok, mensaje = integracion_z2.probar_conexion()
        finally:
            error.close()
        self.assertFalse(ok)
        self.assertIn("INTEGRATION_TOKEN", mensaje)

    def test_probar_conexion_sin_configurar_avisa(self):
        config.guardar_z2_url("")
        with self.assertRaises(integracion_z2.IntegracionNoConfigurada):
            integracion_z2.probar_conexion()


class TestLoQueZ1Manda(unittest.TestCase):
    """Z1 manda los valores CRUDOS del formulario y deja que Z2 normalice.

    Es deliberado: la normalización vive en un solo lugar (el SQL de Z2) y no duplicada acá.
    Si Z1 pre-normalizara, los dos lados podrían divergir sin que nada lo indique, que es
    justo la forma de falla más difícil de detectar en esta integración. Estos tests fijan el
    contrato para que, si algún día Z1 cambia y empieza a mandar otra cosa, salte solo."""

    def setUp(self):
        self._config_original = config._leer_config()
        config.guardar_z2_url("https://z2.example.com")
        config.guardar_z2_token("token-de-prueba")

    def tearDown(self):
        import config as cfg

        for clave in ("z2_url", "z2_token"):
            datos = cfg._leer_config()
            if clave in self._config_original:
                datos[clave] = self._config_original[clave]
            else:
                datos.pop(clave, None)
            cfg._escribir_config(datos)

    def test_manda_el_nombre_tal_cual_lo_typed(self):
        # Con tildes y minúsculas: es Z2 quien las saca, no Z1.
        payload = json.dumps({"coincidencias": []}).encode()
        with mock.patch.object(
            integracion_z2.urllib.request, "urlopen", return_value=FakeRespuesta(payload)
        ) as urlopen:
            integracion_z2.buscar_coincidencias("josé garcía", "")

        url = urlopen.call_args[0][0].full_url
        self.assertIn("nombre=jos%C3%A9+garc%C3%ADa", url)

    def test_manda_el_telefono_tal_cual_con_su_formato(self):
        payload = json.dumps({"coincidencias": []}).encode()
        with mock.patch.object(
            integracion_z2.urllib.request, "urlopen", return_value=FakeRespuesta(payload)
        ) as urlopen:
            integracion_z2.buscar_coincidencias("", "(11) 3456-7890")

        url = urlopen.call_args[0][0].full_url
        self.assertIn("telefono=%2811%29+3456-7890", url)


if __name__ == "__main__":
    unittest.main()
