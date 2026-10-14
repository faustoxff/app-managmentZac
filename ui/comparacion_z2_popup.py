import tkinter as tk
from tkinter import messagebox, ttk

import db


class ComparacionZ2Popup(tk.Toplevel):
    """Clientes de Z1 que también están en la copia local de Z2, con la opción de cambiarles
    el estado (por ejemplo a CLIENTE). Sólo modifica el estado en Z1: nunca escribe en Z2.

    Sin `coincidencias`, compara todo (botón "Comparar con Z1" de la Pestaña Z2). Con
    `coincidencias`, muestra sólo esas (el aviso automático del chequeo periódico)."""

    def __init__(self, master, coincidencias=None, titulo=None, on_cambio=None):
        super().__init__(master)
        self.on_cambio = on_cambio
        self.title(titulo or "Comparación Z1 con Z2")
        self.geometry("1040x560")
        self.transient(master)

        self.resumen_label = tk.Label(self, anchor="w", padx=10, pady=8, font=("", 10, "bold"))
        self.resumen_label.pack(fill="x")

        cols = ("z1_nombre", "z1_tel", "z1_estado", "z2_nombre", "z2_tel", "art", "motivo")
        encabezados = {
            "z1_nombre": ("NOMBRE EN Z1", 210),
            "z1_tel": ("TELÉFONO Z1", 140),
            "z1_estado": ("ESTADO Z1", 110),
            "z2_nombre": ("NOMBRE EN Z2", 210),
            "z2_tel": ("TELÉFONO Z2", 120),
            "art": ("ART", 110),
            "motivo": ("COINCIDE POR", 120),
        }
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
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

        acciones = tk.Frame(self, pady=8)
        acciones.pack(fill="x", padx=8)
        tk.Button(acciones, text="Seleccionar todos", command=self._seleccionar_todos).pack(side="left")
        tk.Label(acciones, text="   Pasar los seleccionados al estado:").pack(side="left")
        self.estados = db.listar_estados()
        nombres = [e.nombre for e in self.estados]
        self.estado_var = tk.StringVar(value="CLIENTE" if "CLIENTE" in nombres else (nombres[0] if nombres else ""))
        ttk.Combobox(
            acciones, textvariable=self.estado_var, values=nombres, state="readonly", width=16
        ).pack(side="left", padx=6)
        tk.Button(acciones, text="Cambiar estado", command=self._cambiar_estado).pack(side="left")
        tk.Button(acciones, text="Cerrar", command=self.destroy, width=12).pack(side="right")

        for tecla in ("<Control-a>", "<Control-A>"):
            # "break" para que el atajo global de la app no abra "Nuevo cliente".
            self.bind(tecla, lambda _e: self._seleccionar_todos() or "break")

        self._fijas = coincidencias
        self._cargar()

    def _cargar(self):
        self.tree.delete(*self.tree.get_children())
        casos, _ = db.listar_z2_casos()
        if not casos:
            self.resumen_label.config(
                text='Todavía no hay carpetas de Z2. Tocá "Sincronizar con Z2" primero.', fg="gray30"
            )
            self.coincidencias = []
            return
        if self._fijas is None:
            self.coincidencias = db.comparar_z1_con_z2()
        else:
            # Se releen los clientes para mostrar el estado actual (puede haber cambiado).
            actuales = {c.id: c for c in db.listar_clientes()}
            self.coincidencias = [
                {**r, "cliente": actuales[r["cliente"].id]} for r in self._fijas if r["cliente"].id in actuales
            ]
        for i, r in enumerate(self.coincidencias):
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
        if self.coincidencias:
            clientes = len({r["cliente"].id for r in self.coincidencias})
            self.resumen_label.config(
                text=f"{clientes} contacto(s) de Z1 ya están en Z2. Revisalos y, si corresponde, "
                "cambiales el estado.",
                fg="#b45309",
            )
        else:
            self.resumen_label.config(
                text=f"No hay contactos iguales entre Z1 y las {len(casos)} carpetas de Z2.",
                fg="#15803d",
            )

    def _seleccionar_todos(self):
        self.tree.selection_set(self.tree.get_children())

    def _cambiar_estado(self):
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showinfo("Cambiar estado", "Seleccioná uno o más contactos.", parent=self)
            return
        estado = next((e for e in self.estados if e.nombre == self.estado_var.get()), None)
        if estado is None:
            return
        # Un mismo cliente puede aparecer en dos filas (coincide con dos carpetas).
        ids = {self.coincidencias[int(i)]["cliente"].id for i in seleccion}
        if not messagebox.askyesno(
            "Cambiar estado",
            f"¿Pasar {len(ids)} contacto(s) a {estado.nombre}?",
            parent=self,
        ):
            return
        for cliente_id in ids:
            db.cambiar_estado_cliente(cliente_id, estado.id)
        self._cargar()
        if self.on_cambio:
            self.on_cambio()
