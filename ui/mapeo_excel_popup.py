import tkinter as tk
from tkinter import messagebox, ttk

import excel_import

CAMPOS = [
    ("nombre", "Nombre *", True),
    ("contacto", "Contacto / Teléfono *", True),
    ("estado", "Estado", False),
    ("notas", "Notas", False),
]


class MapeoColumnasPopup(tk.Toplevel):
    """Deja elegir qué columna del Excel corresponde a cada campo de la DB. Precarga el
    último mapeo usado si los headers del archivo actual coinciden con los guardados."""

    def __init__(self, master, headers: list[str], on_confirmar):
        super().__init__(master)
        self.headers = headers
        self.on_confirmar = on_confirmar
        self.combos: dict[str, tk.StringVar] = {}

        self.title("Mapeo de columnas — Importar Excel")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        tk.Label(
            self, text="Elegí qué columna del Excel corresponde a cada campo:", font=("", 10, "bold")
        ).grid(row=0, column=0, columnspan=2, padx=12, pady=(12, 8), sticky="w")

        sugerido = excel_import.sugerir_mapeo(headers)
        opciones = ["(Ninguna)"] + headers

        for i, (campo, label, obligatorio) in enumerate(CAMPOS, start=1):
            tk.Label(self, text=label).grid(row=i, column=0, padx=12, pady=6, sticky="w")
            var = tk.StringVar(value=sugerido.get(campo, "(Ninguna)" if not obligatorio else ""))
            combo = ttk.Combobox(self, textvariable=var, values=opciones, state="readonly", width=30)
            combo.grid(row=i, column=1, padx=12, pady=6)
            self.combos[campo] = var

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=len(CAMPOS) + 1, column=0, columnspan=2, pady=12)
        tk.Button(btn_frame, text="Importar", command=self._confirmar, width=14).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=14).pack(side="left", padx=6)

    def _confirmar(self):
        mapeo = {}
        for campo, var in self.combos.items():
            valor = var.get()
            if valor and valor != "(Ninguna)":
                mapeo[campo] = valor

        faltantes = [label for campo, label, obligatorio in CAMPOS if obligatorio and campo not in mapeo]
        if faltantes:
            messagebox.showwarning(
                "Falta mapear", f"Elegí una columna para: {', '.join(faltantes)}", parent=self
            )
            return

        excel_import.guardar_mapeo(mapeo)
        self.destroy()
        self.on_confirmar(mapeo)
