import tkinter as tk
from tkinter import messagebox

import config


class ApiKeyPopup(tk.Toplevel):
    """Configuración de "Importar con IA": API key de OpenRouter y qué modelo usar. Se guarda
    en %APPDATA%\\GestorClientes\\config.json — nunca se versiona ni se hardcodea en el código."""

    def __init__(self, master, on_guardada=None):
        super().__init__(master)
        self.on_guardada = on_guardada

        self.title("Configurar IA (OpenRouter)")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        info = (
            "Se obtiene en openrouter.ai/keys. Se guarda solo en esta PC "
            "(%APPDATA%\\GestorClientes\\config.json), nunca se comparte."
        )
        tk.Label(self, text="API key de OpenRouter", anchor="w").pack(padx=16, pady=(16, 0), fill="x")
        tk.Label(self, text=info, wraplength=360, justify="left", fg="gray30").pack(
            padx=16, pady=(0, 6), fill="x"
        )

        self.key_var = tk.StringVar(value=config.obtener_api_key())
        entry = tk.Entry(self, textvariable=self.key_var, show="•", width=45)
        entry.pack(padx=16, pady=(0, 12))
        entry.focus_set()

        tk.Label(self, text="Modelo a usar", anchor="w").pack(padx=16, fill="x")
        tk.Label(
            self,
            text='Cualquier modelo con visión de openrouter.ai/models. Ej: "openrouter/auto" '
            "para que elija automáticamente.",
            wraplength=360,
            justify="left",
            fg="gray30",
        ).pack(padx=16, pady=(0, 6), fill="x")

        self.modelo_var = tk.StringVar(value=config.obtener_modelo_ia())
        tk.Entry(self, textvariable=self.modelo_var, width=45).pack(padx=16, pady=(0, 8))

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
        config.guardar_modelo_ia(self.modelo_var.get())
        self.destroy()
        if self.on_guardada:
            self.on_guardada()
