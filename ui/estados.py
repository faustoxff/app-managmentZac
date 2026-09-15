import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

import db


class EstadosPopup(tk.Toplevel):
    """Popup para gestionar (crear/editar/borrar) los estados configurables."""

    def __init__(self, master, on_change):
        super().__init__(master)
        self.on_change = on_change
        self.title("Gestionar estados")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.tree = ttk.Treeview(self, columns=("color",), show="headings", height=8)
        self.tree.heading("color", text="Estado / Color")
        self.tree.column("color", width=250)
        self.tree.grid(row=0, column=0, columnspan=3, padx=10, pady=10)
        self.tree.bind("<Double-1>", lambda e: self._editar())

        tk.Button(self, text="Nuevo", command=self._nuevo, width=12).grid(row=1, column=0, pady=6)
        tk.Button(self, text="Editar", command=self._editar, width=12).grid(row=1, column=1, pady=6)
        tk.Button(self, text="Borrar", command=self._borrar, width=12).grid(row=1, column=2, pady=6)

        tk.Button(self, text="Cerrar", command=self._cerrar, width=12).grid(
            row=2, column=0, columnspan=3, pady=(0, 10)
        )

        self._cargar()

    def _cargar(self):
        self.tree.delete(*self.tree.get_children())
        for e in db.listar_estados():
            self.tree.insert("", "end", iid=str(e.id), values=(f"{e.nombre}  ({e.color})",))

    def _seleccion_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _nuevo(self):
        self._abrir_dialogo_estado()

    def _editar(self):
        estado_id = self._seleccion_id()
        if not estado_id:
            messagebox.showinfo("Seleccionar", "Elegí un estado para editar.", parent=self)
            return
        estado = next(e for e in db.listar_estados() if e.id == estado_id)
        self._abrir_dialogo_estado(estado)

    def _borrar(self):
        estado_id = self._seleccion_id()
        if not estado_id:
            messagebox.showinfo("Seleccionar", "Elegí un estado para borrar.", parent=self)
            return
        if not messagebox.askyesno("Confirmar", "¿Borrar este estado?", parent=self):
            return
        ok, msg = db.eliminar_estado(estado_id)
        if not ok:
            messagebox.showerror("No se puede borrar", msg, parent=self)
            return
        self._cargar()

    def _abrir_dialogo_estado(self, estado=None):
        dialogo = tk.Toplevel(self)
        dialogo.title("Estado")
        dialogo.transient(self)
        dialogo.grab_set()

        tk.Label(dialogo, text="Nombre").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        nombre_var = tk.StringVar(value=estado.nombre if estado else "")
        tk.Entry(dialogo, textvariable=nombre_var, width=25).grid(row=0, column=1, padx=10, pady=8)

        color_var = tk.StringVar(value=estado.color if estado else "#808080")

        def elegir_color():
            _, hexval = colorchooser.askcolor(color=color_var.get(), parent=dialogo)
            if hexval:
                color_var.set(hexval)
                color_preview.config(bg=hexval)

        tk.Label(dialogo, text="Color").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        color_frame = tk.Frame(dialogo)
        color_frame.grid(row=1, column=1, padx=10, pady=8, sticky="w")
        color_preview = tk.Label(color_frame, bg=color_var.get(), width=4)
        color_preview.pack(side="left", padx=(0, 8))
        tk.Button(color_frame, text="Elegir...", command=elegir_color).pack(side="left")

        def guardar():
            nombre = nombre_var.get().strip()
            if not nombre:
                messagebox.showwarning("Falta nombre", "El nombre es obligatorio.", parent=dialogo)
                return
            try:
                if estado:
                    db.actualizar_estado(estado.id, nombre, color_var.get())
                else:
                    db.crear_estado(nombre, color_var.get())
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Error", f"No se pudo guardar: {exc}", parent=dialogo)
                return
            dialogo.destroy()
            self._cargar()

        tk.Button(dialogo, text="Guardar", command=guardar, width=12).grid(
            row=2, column=0, columnspan=2, pady=10
        )

    def _cerrar(self):
        self.on_change()
        self.destroy()
