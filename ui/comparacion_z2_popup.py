import tkinter as tk
from tkinter import ttk

import db


class ComparacionZ2Popup(tk.Toplevel):
    """Clientes de Z1 que también están en la copia local de Z2. Sólo muestra: no cambia
    nada en ninguna de las dos tablas."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Comparación Z1 con Z2")
        self.geometry("1000x480")
        self.transient(master)

        self.resumen_label = tk.Label(self, anchor="w", padx=10, pady=8, font=("", 10, "bold"))
        self.resumen_label.pack(fill="x")

        cols = ("z1_nombre", "z1_tel", "z1_estado", "z2_nombre", "z2_tel", "art", "motivo")
        encabezados = {
            "z1_nombre": ("NOMBRE EN Z1", 210),
            "z1_tel": ("TELÉFONO Z1", 140),
            "z1_estado": ("ESTADO Z1", 100),
            "z2_nombre": ("NOMBRE EN Z2", 210),
            "z2_tel": ("TELÉFONO Z2", 120),
            "art": ("ART", 110),
            "motivo": ("COINCIDE POR", 120),
        }
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, (texto, ancho) in encabezados.items():
            self.tree.heading(c, text=texto, anchor="w")
            self.tree.column(c, width=ancho, anchor="w", stretch=False)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        tk.Button(self, text="Cerrar", command=self.destroy, width=12).pack(pady=8)
        self._cargar()

    def _cargar(self):
        casos, _ = db.listar_z2_casos()
        if not casos:
            self.resumen_label.config(
                text='Todavía no hay carpetas de Z2. Tocá "Sincronizar con Z2" primero.', fg="gray30"
            )
            return
        coincidencias = db.comparar_z1_con_z2()
        for i, r in enumerate(coincidencias):
            c, z2 = r["cliente"], r["z2"]
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    c.nombre,
                    c.contacto,
                    c.estado_nombre,
                    f"{z2['apellido']} {z2['nombre']}".strip(),
                    z2["telefono"],
                    z2["art"],
                    r["motivo"],
                ),
            )
        if coincidencias:
            clientes = len({r["cliente"].id for r in coincidencias})
            self.resumen_label.config(
                text=f"{clientes} cliente(s) de Z1 también están en Z2.", fg="#b45309"
            )
        else:
            self.resumen_label.config(
                text=f"No hay clientes iguales entre Z1 y las {len(casos)} carpetas de Z2.",
                fg="#15803d",
            )
