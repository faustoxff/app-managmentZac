import tkinter as tk
from tkinter import messagebox, ttk

import db
from models import Cliente


class ClienteForm(tk.Toplevel):
    """Popup de alta/edición de cliente."""

    def __init__(self, master, on_saved, cliente: Cliente | None = None):
        super().__init__(master)
        self.on_saved = on_saved
        self.cliente = cliente
        self.title("Editar cliente" if cliente else "Nuevo cliente")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.estados = db.listar_estados()
        if not self.estados:
            messagebox.showerror("Error", "No hay estados configurados.", parent=self)
            self.destroy()
            return

        pad = {"padx": 10, "pady": 6}

        tk.Label(self, text="Nombre *").grid(row=0, column=0, sticky="w", **pad)
        self.nombre_var = tk.StringVar(value=cliente.nombre if cliente else "")
        tk.Entry(self, textvariable=self.nombre_var, width=40).grid(row=0, column=1, **pad)

        tk.Label(self, text="Contacto").grid(row=1, column=0, sticky="w", **pad)
        self.contacto_var = tk.StringVar(value=cliente.contacto if cliente else "")
        tk.Entry(self, textvariable=self.contacto_var, width=40).grid(row=1, column=1, **pad)

        tk.Label(self, text="Estado").grid(row=2, column=0, sticky="w", **pad)
        self.estado_var = tk.StringVar()
        nombres_estados = [e.nombre for e in self.estados]
        self.estado_combo = ttk.Combobox(
            self, textvariable=self.estado_var, values=nombres_estados, state="readonly", width=37
        )
        if cliente:
            actual = next((e.nombre for e in self.estados if e.id == cliente.estado_id), nombres_estados[0])
            self.estado_var.set(actual)
        else:
            self.estado_var.set(nombres_estados[0])
        self.estado_combo.grid(row=2, column=1, **pad)

        tk.Label(self, text="Notas").grid(row=3, column=0, sticky="nw", **pad)
        self.notas_text = tk.Text(self, width=40, height=6)
        if cliente:
            self.notas_text.insert("1.0", cliente.notas)
        self.notas_text.grid(row=3, column=1, **pad)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Guardar", command=self._guardar, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=12).pack(side="left", padx=5)

    def _guardar(self):
        nombre = self.nombre_var.get().strip()
        if not nombre:
            messagebox.showwarning("Falta nombre", "El nombre es obligatorio.", parent=self)
            return
        contacto = self.contacto_var.get().strip()
        notas = self.notas_text.get("1.0", "end").strip()
        estado_id = next(e.id for e in self.estados if e.nombre == self.estado_var.get())

        if self.cliente:
            db.actualizar_cliente(self.cliente.id, nombre, contacto, estado_id, notas)
        else:
            db.crear_cliente(nombre, contacto, estado_id, notas)

        self.on_saved()
        self.destroy()
