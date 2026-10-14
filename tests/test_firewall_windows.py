"""Permiso del firewall para Subida por celular. Los comandos de Windows se simulan: lo que se
prueba es qué se ejecuta y cómo se decide si la regla quedó creada."""
import inspect
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import firewall_windows as fw  # noqa: E402
import photo_server  # noqa: E402

EXE = r"C:\Users\ESTUDIO 2024\Desktop\Gestor DEFINITIVO 3.0\GestorClienteZ.exe"


class TestFirewallWindows(unittest.TestCase):
    def test_puertos_coinciden_con_el_servidor(self):
        params = inspect.signature(photo_server.PhotoServer.iniciar).parameters
        desde = params["puerto_desde"].default
        hasta = desde + params["intentos"].default - 1
        self.assertEqual(fw.PUERTOS, f"{desde}-{hasta}")

    def test_comandos_solo_tocan_este_programa(self):
        borrar, agregar = fw.comandos(EXE)
        self.assertIn(f'program="{EXE}"', borrar)
        self.assertIn("dir=in", borrar)
        self.assertIn("action=allow", agregar)
        self.assertIn("profile=any", agregar)
        self.assertIn(f'program="{EXE}"', agregar)
        self.assertIn(f"localport={fw.PUERTOS}", agregar)

    def test_el_nombre_cambia_si_se_mueve_el_exe(self):
        self.assertNotEqual(fw._nombre_regla(EXE), fw._nombre_regla(EXE.replace("Desktop", "Documents")))

    def test_no_aplica_fuera_del_exe_de_windows(self):
        with mock.patch.object(fw.sys, "platform", "linux"):
            self.assertFalse(fw.aplica())

    def test_regla_existe_usa_el_codigo_de_salida(self):
        with mock.patch.object(fw.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            self.assertTrue(fw.regla_existe(EXE))
        with mock.patch.object(fw.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertFalse(fw.regla_existe(EXE))
        with mock.patch.object(fw.subprocess, "run", side_effect=FileNotFoundError):
            self.assertFalse(fw.regla_existe(EXE))

    def test_configurar_pide_admin_y_borra_el_archivo_temporal(self):
        llamadas = []

        def falso_run(args, **kwargs):
            llamadas.append(args)
            if args[0] == "powershell":
                bat = pathlib.Path(args[-1].split("'")[1])
                self.assertIn("netsh advfirewall firewall add rule", bat.read_text(encoding="utf-8"))
                return subprocess.CompletedProcess(args, 0)
            return subprocess.CompletedProcess(args, 0)  # netsh show rule: existe

        with mock.patch.object(fw.subprocess, "run", side_effect=falso_run):
            self.assertTrue(fw.configurar(EXE))
        self.assertIn("-Verb RunAs", llamadas[0][-1])
        self.assertFalse(list(pathlib.Path(fw.tempfile.gettempdir()).glob("GestorClientes_firewall.bat")))

    def test_si_se_cancela_el_cartel_no_queda_configurado(self):
        def falso_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 1)  # cancelado, y la regla no existe

        with mock.patch.object(fw.subprocess, "run", side_effect=falso_run):
            self.assertFalse(fw.configurar(EXE))


if __name__ == "__main__":
    unittest.main()
