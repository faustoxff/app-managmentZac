import tkinter as tk
from tkinter import messagebox, ttk

import db
from models import Cliente
from ui.duplicado_popup import DuplicadoPopup


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
        self.nombre_var.trace_add("write", self._forzar_mayusculas)
        self.nombre_entry = tk.Entry(self, textvariable=self.nombre_var, width=40)
        self.nombre_entry.grid(row=0, column=1, **pad)

        tk.Label(self, text="Contacto").grid(row=1, column=0, sticky="w", **pad)
        self.contacto_var = tk.StringVar(value=cliente.contacto if cliente else "")
        contacto_entry = tk.Entry(self, textvariable=self.contacto_var, width=40)
        contacto_entry.grid(row=1, column=1, **pad)

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

        tk.Label(self, text="Recomendado por").grid(row=3, column=0, sticky="w", **pad)
        self.recomendado_var = tk.StringVar(value=cliente.recomendado_por if cliente else "")
        recomendado_entry = tk.Entry(self, textvariable=self.recomendado_var, width=40)
        recomendado_entry.grid(row=3, column=1, **pad)

        # Enter guarda directo desde cualquiera de estos campos (no en Notas, ahí Enter tiene
        # que seguir insertando un salto de línea como siempre).
        for widget in (self.nombre_entry, contacto_entry, self.estado_combo, recomendado_entry):
            widget.bind("<Return>", self._enter_guarda)

        tk.Label(self, text="Notas").grid(row=4, column=0, sticky="nw", **pad)
        self.notas_text = tk.Text(self, width=40, height=6)
        if cliente:
            self.notas_text.insert("1.0", cliente.notas)
        self.notas_text.grid(row=4, column=1, **pad)
        # Por default, Tab en un Text de Tkinter inserta una tabulación en vez de mover el
        # foco (a diferencia de un Entry) — acá lo pisamos para que vaya directo a Guardar y
        # se pueda cargar un cliente entero sin tocar el mouse.
        self.notas_text.bind("<Tab>", self._tab_a_guardar)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        self.guardar_btn = tk.Button(btn_frame, text="Guardar", command=self._guardar, width=12)
        self.guardar_btn.pack(side="left", padx=5)
        cierra = "Cerrar" if not cliente else "Cancelar"
        tk.Button(btn_frame, text=cierra, command=self.destroy, width=12).pack(side="left", padx=5)

        self.guardado_label = tk.Label(self, text="", fg="#16a34a")
        self.guardado_label.grid(row=6, column=0, columnspan=2, pady=(4, 8))

        self.nombre_entry.focus_set()

    def _tab_a_guardar(self, event):
        self.guardar_btn.focus_set()
        return "break"  # evita que el Text inserte una tabulación

    def _enter_guarda(self, event):
        self._guardar()
        return "break"

    def _forzar_mayusculas(self, *_args):
        """Se ve en mayúscula mientras se escribe, no solo al guardar (db.crear_cliente ya lo
        hace igual, pero así queda consistente en pantalla desde el primer momento)."""
        texto = self.nombre_var.get()
        mayus = texto.upper()
        if texto != mayus:
            self.nombre_var.set(mayus)

    def _guardar(self):
        nombre = self.nombre_var.get().strip()
        if not nombre:
            messagebox.showwarning("Falta nombre", "El nombre es obligatorio.", parent=self)
            return
        contacto = self.contacto_var.get().strip()
        notas = self.notas_text.get("1.0", "end").strip()
        recomendado_por = self.recomendado_var.get().strip()
        estado_id = next(e.id for e in self.estados if e.nombre == self.estado_var.get())

        if not self.cliente:
            duplicados = db.buscar_duplicados(nombre, contacto)
            if duplicados:
                DuplicadoPopup(
                    self,
                    duplicados,
                    on_ver_existente=self._ver_existente,
                    on_cargar_igual=lambda: self._guardar_final(
                        nombre, contacto, estado_id, notas, recomendado_por
                    ),
                )
                return

        self._guardar_final(nombre, contacto, estado_id, notas, recomendado_por)

    def _guardar_final(self, nombre, contacto, estado_id, notas, recomendado_por):
        if self.cliente:
            db.actualizar_cliente(self.cliente.id, nombre, contacto, estado_id, notas, recomendado_por)
            self.on_saved()
            self.destroy()
            return

        db.crear_cliente(nombre, contacto, estado_id, notas, recomendado_por)
        self.on_saved()
        # A diferencia de editar, acá dejamos la ventana abierta y limpiamos los campos: es
        # común cargar varios clientes nuevos seguidos (ej. una planilla que se pasa a mano),
        # y volver a abrir "Nuevo cliente" por cada uno es más lento que solo seguir tipeando.
        self._limpiar_para_siguiente(nombre)

    def _limpiar_para_siguiente(self, nombre_guardado: str):
        self.nombre_var.set("")
        self.contacto_var.set("")
        self.recomendado_var.set("")
        self.notas_text.delete("1.0", "end")
        self.guardado_label.config(text=f"✓ {nombre_guardado} guardado — listo para cargar otro")
        self.nombre_entry.focus_set()

    def _ver_existente(self, cliente_existente: Cliente):
        self.destroy()
        ClienteForm(self.master, on_saved=self.on_saved, cliente=cliente_existente)
