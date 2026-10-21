import tkinter as tk
from tkinter import messagebox

import config
from ui import tema


class ApiKeyPopup(tk.Toplevel):
    """Configuración de "Importar con IA": proveedor, API key y modelo. Se guarda
    en %APPDATA%\\GestorClientes\\config.json — nunca se versiona ni se hardcodea en el código."""

    def __init__(self, master, on_guardada=None):
        super().__init__(master)
        self.on_guardada = on_guardada

        self.title("Configurar IA")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.proveedor_var = tk.StringVar(value=config.obtener_proveedor_ia())
        tk.Label(self, text="Proveedor", anchor="w").pack(padx=16, pady=(16, 0), fill="x")
        for clave, datos in config.PROVEEDORES_IA.items():
            tk.Radiobutton(
                self, text=datos["nombre"], variable=self.proveedor_var, value=clave,
                command=self._cambio_proveedor, anchor="w",
            ).pack(padx=16, fill="x")

        self.info_label = tk.Label(self, wraplength=360, justify="left", fg="gray30")
        self.info_label.pack(padx=16, pady=(8, 6), fill="x")
        self.key_var = tk.StringVar()
        entry = tk.Entry(self, textvariable=self.key_var, show="•", width=45)
        entry.pack(padx=16, pady=(0, 12))
        entry.focus_set()

        tk.Label(self, text="Modelo a usar", anchor="w").pack(padx=16, fill="x")
        self.modelo_var = tk.StringVar()
        tk.Entry(self, textvariable=self.modelo_var, width=45).pack(padx=16, pady=(0, 8))
        self._cambio_proveedor()

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(8, 16))
        tema.primario(tk.Button(btn_frame, text="Guardar", command=self._guardar, width=12)).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=12).pack(side="left", padx=6)

    def _cambio_proveedor(self):
        proveedor = self.proveedor_var.get()
        datos = config.PROVEEDORES_IA[proveedor]
        self.info_label.config(
            text=f"API key: se obtiene en {datos['donde_key']}. Se guarda solo en esta PC "
            "(%APPDATA%\\GestorClientes\\config.json), nunca se comparte."
        )
        self.key_var.set(config.obtener_api_key(proveedor))
        self.modelo_var.set(config.obtener_modelo_ia(proveedor))

    def _guardar(self):
        api_key = self.key_var.get().strip()
        if not api_key:
            messagebox.showwarning("Falta la key", "Ingresá una API key.", parent=self)
            return
        proveedor = self.proveedor_var.get()
        config.guardar_proveedor_ia(proveedor)
        config.guardar_api_key(api_key, proveedor)
        config.guardar_modelo_ia(self.modelo_var.get(), proveedor)
        self.destroy()
        if self.on_guardada:
            self.on_guardada()
