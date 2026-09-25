"""El OCR empaquetado tiene que poder abrir sus idiomas en Windows. Un bug anterior agregaba
`--tessdata-dir "<ruta>"` al config: en Windows pytesseract corta el config con
shlex(posix=False), que NO saca las comillas, y Tesseract recibía la ruta con comillas
literales y no podía abrir ningún idioma."""
import os
import pathlib
import shlex
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import ocr_import  # noqa: E402


class FakePytesseract:
    Output = types.SimpleNamespace(DICT="dict")

    class TesseractNotFoundError(Exception):
        pass

    def __init__(self):
        self.llamadas = []
        self.pytesseract = types.SimpleNamespace(tesseract_cmd="")

    def image_to_data(self, img, lang=None, config="", output_type=None):
        self.llamadas.append(config)
        return {"text": []}

    def image_to_string(self, img, lang=None, config=""):
        self.llamadas.append(config)
        return ""


class TestConfigOCR(unittest.TestCase):
    def tokens_como_en_windows(self, config):
        return shlex.split(config, posix=False)

    def test_config_no_lleva_comillas_ni_tessdata_dir(self):
        # Se simula la app EMPAQUETADA (.exe): es el único modo en que se armaba la ruta.
        base = pathlib.Path(tempfile.mkdtemp())
        (base / "tesseract" / "tessdata").mkdir(parents=True)
        (base / "tesseract" / "tesseract.exe").write_bytes(b"x")
        fake = FakePytesseract()

        def requerir():
            ocr_import._configurar_tesseract_embebido(fake)
            return fake

        orig = ocr_import._requerir_pytesseract
        ocr_import._requerir_pytesseract = requerir
        sys.frozen, sys._MEIPASS = True, str(base)
        previo = os.environ.pop("TESSDATA_PREFIX", None)
        try:
            from PIL import Image

            ocr_import._extraer_palabras(Image.new("L", (10, 10)))
            ocr_import._recortar_y_refinar(
                Image.new("L", (50, 50)),
                [ocr_import._Palabra("A", 1, 1, 5, 5, 90.0, (1, 1, 1))],
                ocr_import.ALFABETO_NOMBRE,
            )
        finally:
            ocr_import._requerir_pytesseract = orig
            del sys.frozen, sys._MEIPASS
            os.environ.pop("TESSDATA_PREFIX", None)
            if previo is not None:
                os.environ["TESSDATA_PREFIX"] = previo
        self.assertTrue(fake.llamadas)
        for config in fake.llamadas:
            for token in self.tokens_como_en_windows(config):
                self.assertNotIn('"', token, f"comillas literales en el argumento: {config}")
            self.assertNotIn("--tessdata-dir", config)

    def test_empaquetado_usa_solo_tessdata_prefix(self):
        base = pathlib.Path(tempfile.mkdtemp())
        (base / "tesseract" / "tessdata").mkdir(parents=True)
        (base / "tesseract" / "tesseract.exe").write_bytes(b"x")
        fake = FakePytesseract()
        sys.frozen, sys._MEIPASS = True, str(base)
        previo = os.environ.pop("TESSDATA_PREFIX", None)
        try:
            ocr_import._configurar_tesseract_embebido(fake)
            self.assertEqual(os.environ["TESSDATA_PREFIX"], str(base / "tesseract" / "tessdata"))
            self.assertEqual(fake.pytesseract.tesseract_cmd, str(base / "tesseract" / "tesseract.exe"))
        finally:
            del sys.frozen, sys._MEIPASS
            os.environ.pop("TESSDATA_PREFIX", None)
            if previo is not None:
                os.environ["TESSDATA_PREFIX"] = previo


if __name__ == "__main__":
    unittest.main()
