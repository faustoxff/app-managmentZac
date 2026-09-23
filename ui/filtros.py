import tkinter as tk
from tkinter import ttk

import db


class FiltrosPopup(tk.Toplevel):
    """Popup para configurar filtros (estado, rango de fechas, texto libre)."""

    def __init__(self, master, filtros_actuales: dict, on_apply):
        super().__init__(master)
        self.on_apply = on_apply
        self.title("Filtros")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        pad = {"padx": 10, "pady": 6}

        estados = db.listar_estados()
        nombres = ["(Todos)"] + [e.nombre for e in estados]

        tk.Label(self, text="Estado").grid(row=0, column=0, sticky="w", **pad)
        self.estado_var = tk.StringVar(value=filtros_actuales.get("estado_nombre", "(Todos)"))
        ttk.Combobox(
            self, textvariable=self.estado_var, values=nombres, state="readonly", width=27
        ).grid(row=0, column=1, **pad)

        tk.Label(self, text="Desde (AAAA-MM-DD)").grid(row=1, column=0, sticky="w", **pad)
        self.desde_var = tk.StringVar(value=filtros_actuales.get("fecha_desde", ""))
        tk.Entry(self, textvariable=self.desde_var, width=30).grid(row=1, column=1, **pad)

        tk.Label(self, text="Hasta (AAAA-MM-DD)").grid(row=2, column=0, sticky="w", **pad)
        self.hasta_var = tk.StringVar(value=filtros_actuales.get("fecha_hasta", ""))
        tk.Entry(self, textvariable=self.hasta_var, width=30).grid(row=2, column=1, **pad)

        tk.Label(self, text="Texto (nombre/notas/recomendado por)").grid(
            row=3, column=0, sticky="w", **pad
        )
        self.texto_var = tk.StringVar(value=filtros_actuales.get("texto", ""))
        tk.Entry(self, textvariable=self.texto_var, width=30).grid(row=3, column=1, **pad)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Aplicar", command=self._aplicar, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Limpiar", command=self._limpiar, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cerrar", command=self.destroy, width=12).pack(side="left", padx=5)

        self.estados = estados

    def _aplicar(self):
        estado_nombre = self.estado_var.get()
        estado_id = None
        if estado_nombre != "(Todos)":
            estado_id = next((e.id for e in self.estados if e.nombre == estado_nombre), None)

        filtros = {
            "estado_id": estado_id,
            "estado_nombre": estado_nombre,
            "fecha_desde": self.desde_var.get().strip() or None,
            "fecha_hasta": self.hasta_var.get().strip() or None,
            "texto": self.texto_var.get().strip() or None,
        }
        self.on_apply(filtros)
        self.destroy()

    def _limpiar(self):
        self.on_apply({})
        self.destroy()
