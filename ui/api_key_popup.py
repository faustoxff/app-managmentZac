import tkinter as tk
from tkinter import messagebox

import config


class ApiKeyPopup(tk.Toplevel):
    """Pide la API key de Anthropic (o deja cambiar la ya guardada). Se guarda en
    %APPDATA%\\GestorClientes\\config.json — nunca se versiona ni se hardcodea en el código."""

    def __init__(self, master, on_guardada=None):
        super().__init__(master)
        self.on_guardada = on_guardada

        self.title("API key de Anthropic")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        info = (
            "Necesaria para \"Importar con IA\". Se guarda solo en esta PC "
            "(%APPDATA%\\GestorClientes\\config.json), nunca se comparte."
        )
        tk.Label(self, text=info, wraplength=360, justify="left").pack(padx=16, pady=(16, 8))

        self.key_var = tk.StringVar(value=config.obtener_api_key())
        entry = tk.Entry(self, textvariable=self.key_var, show="•", width=45)
        entry.pack(padx=16, pady=8)
        entry.focus_set()

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(8, 16))
        tk.Button(btn_frame, text="Guardar", command=self._guardar, width=12).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=12).pack(side="left", padx=6)

    def _guardar(self):
        api_key = self.key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Falta la key", "Ingresá una API key.", parent=self)
            return
        config.guardar_api_key(api_key)
        self.destroy()
        if self.on_guardada:
            self.on_guardada()
