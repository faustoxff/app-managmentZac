import tkinter as tk
from tkinter import ttk

from models import Cliente


class DuplicadoPopup(tk.Toplevel):
    """Aviso no bloqueante de posible duplicado. Deja elegir entre ver el registro existente
    o cargar el nuevo de todos modos."""

    def __init__(self, master, duplicados: list[Cliente], on_ver_existente, on_cargar_igual):
        super().__init__(master)
        self.duplicados = duplicados
        self.on_ver_existente = on_ver_existente
        self.on_cargar_igual = on_cargar_igual

        self.title("Posible duplicado")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        tk.Label(
            self,
            text="Ya existe un registro parecido. Elegí qué hacer:",
            font=("", 10, "bold"),
        ).pack(padx=12, pady=(12, 6), anchor="w")

        cols = ("nombre", "contacto", "estado", "fecha")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=min(5, len(duplicados)))
        for c, label, width in [
            ("nombre", "Nombre", 160),
            ("contacto", "Contacto", 140),
            ("estado", "Estado", 110),
            ("fecha", "Última actualización", 150),
        ]:
            self.tree.heading(c, text=label)
            self.tree.column(c, width=width)
        for d in duplicados:
            self.tree.insert(
                "", "end", iid=str(d.id), values=(d.nombre, d.contacto, d.estado_nombre, d.fecha_actualizacion)
            )
        self.tree.pack(padx=12, pady=6)
        if duplicados:
            self.tree.selection_set(str(duplicados[0].id))

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(6, 12))
        tk.Button(btn_frame, text="Ver paciente existente", command=self._ver, width=20).pack(
            side="left", padx=6
        )
        tk.Button(btn_frame, text="Cargar de todos modos", command=self._cargar, width=20).pack(
            side="left", padx=6
        )

    def _seleccionado(self) -> Cliente:
        sel = self.tree.selection()
        cliente_id = int(sel[0]) if sel else self.duplicados[0].id
        return next(d for d in self.duplicados if d.id == cliente_id)

    def _ver(self):
        elegido = self._seleccionado()
        self.destroy()
        self.on_ver_existente(elegido)

    def _cargar(self):
        self.destroy()
        self.on_cargar_igual()
