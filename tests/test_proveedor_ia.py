"""Proveedor de IA (Gemini / OpenRouter): default, compatibilidad con quien ya tenía OpenRouter
y que las keys y modelos de cada proveedor no se pisen entre sí."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import config  # noqa: E402


class ProveedorIATest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = pathlib.Path(tmp.name) / "config.json"
        patcher = mock.patch.object(config, "CONFIG_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_sin_config_el_proveedor_es_gemini(self):
        self.assertEqual(config.obtener_proveedor_ia(), "gemini")
        self.assertEqual(config.obtener_modelo_ia(), "gemini-2.5-flash")
        self.assertEqual(config.obtener_api_key(), "")

    def test_con_key_de_openrouter_previa_sigue_openrouter(self):
        self.path.write_text(json.dumps({"openrouter_api_key": "k-vieja", "modelo_ia": "m/x"}))
        self.assertEqual(config.obtener_proveedor_ia(), "openrouter")
        self.assertEqual(config.obtener_api_key(), "k-vieja")
        self.assertEqual(config.obtener_modelo_ia(), "m/x")

    def test_proveedor_elegido_gana_sobre_la_key_previa(self):
        self.path.write_text(json.dumps({"openrouter_api_key": "k", "proveedor_ia": "gemini"}))
        self.assertEqual(config.obtener_proveedor_ia(), "gemini")

    def test_proveedor_invalido_no_se_guarda(self):
        config.guardar_proveedor_ia("inexistente")
        self.assertEqual(config.obtener_proveedor_ia(), "gemini")

    def test_keys_y_modelos_no_se_pisan(self):
        config.guardar_api_key("key-gemini", "gemini")
        config.guardar_api_key("key-openrouter", "openrouter")
        config.guardar_modelo_ia("gemini-x", "gemini")
        config.guardar_modelo_ia("or/modelo", "openrouter")

        self.assertEqual(config.obtener_api_key("gemini"), "key-gemini")
        self.assertEqual(config.obtener_api_key("openrouter"), "key-openrouter")
        self.assertEqual(config.obtener_modelo_ia("gemini"), "gemini-x")
        self.assertEqual(config.obtener_modelo_ia("openrouter"), "or/modelo")

    def test_sin_indicar_proveedor_usa_el_activo(self):
        config.guardar_proveedor_ia("openrouter")
        config.guardar_api_key("  k-or  ")
        self.assertEqual(config.obtener_api_key("openrouter"), "k-or")
        self.assertEqual(config.obtener_api_key("gemini"), "")

    def test_modelo_vacio_vuelve_al_default_del_proveedor(self):
        config.guardar_modelo_ia("  ", "gemini")
        config.guardar_modelo_ia("", "openrouter")
        self.assertEqual(config.obtener_modelo_ia("gemini"), "gemini-2.5-flash")
        self.assertEqual(config.obtener_modelo_ia("openrouter"), config.MODELO_IA_DEFAULT)


if __name__ == "__main__":
    unittest.main()
