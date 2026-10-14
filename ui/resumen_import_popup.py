import tkinter as tk
from tkinter import messagebox, ttk

import db
from db import ResultadoLote


class ResumenImportPopup(tk.Toplevel):
    """Muestra el resultado de una importación masiva (Excel u OCR): cuántos se cargaron OK,
    y deja revisar los posibles duplicados (cargar igual / descartar), de a uno o varios a la
    vez (Ctrl+A, Shift+clic, Ctrl+clic). Los
    fallidos solo se listan con el motivo, no se pueden reintentar acá."""

    def __init__(self, master, resultado: ResultadoLote, on_cerrar):
        super().__init__(master)
        self.resultado = resultado
        self.on_cerrar = on_cerrar
        self.pendientes = list(resultado.duplicados)  # [(FilaImport, [Cliente]), ...]

        self.title("Resultado de la importación")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.resumen_label = tk.Label(self, font=("", 10, "bold"), justify="left")
        self.resumen_label.pack(padx=12, pady=(12, 6), anchor="w")

        tk.Label(self, text="Posibles duplicados a revisar:").pack(padx=12, anchor="w")
        cols = ("nombre", "contacto", "existente")
        tabla = tk.Frame(self)
        tabla.pack(padx=12, pady=6)
        self.tree = ttk.Treeview(tabla, columns=cols, show="headings", height=16, selectmode="extended")
        for c, label, width in [
            ("nombre", "Nombre nuevo", 170),
            ("contacto", "Contacto nuevo", 130),
            ("existente", "Ya existe como", 320),
        ]:
            self.tree.heading(c, text=label)
            self.tree.column(c, width=width)
        vsb = ttk.Scrollbar(tabla, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left")
        vsb.pack(side="left", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._actualizar_seleccion())

        self.seleccion_label = tk.Label(self, text="", fg="#2563eb")
        self.seleccion_label.pack(padx=12, anchor="w")

        accion_frame = tk.Frame(self)
        accion_frame.pack(pady=(0, 6))
        tk.Button(accion_frame, text="Seleccionar todos", command=self._seleccionar_todos, width=16).pack(
            side="left", padx=6
        )
        tk.Button(accion_frame, text="Cargar igual", command=self._cargar_seleccionados, width=14).pack(
            side="left", padx=6
        )
        tk.Button(accion_frame, text="Descartar", command=self._descartar_seleccionados, width=14).pack(
            side="left", padx=6
        )

        # Ctrl+A en esta ventana selecciona todos. Se ata a la ventana entera (no sólo a la
        # tabla) y corta con "break": si no, el atajo global de la app abre "Nuevo cliente".
        for tecla in ("<Control-a>", "<Control-A>"):
            self.bind(tecla, self._seleccionar_todos)

        if resultado.fallidos:
            tk.Label(self, text="Filas con datos faltantes (no se cargaron):").pack(
                padx=12, pady=(6, 0), anchor="w"
            )
            texto_fallidos = tk.Text(self, width=60, height=4)
            for fila, motivo in resultado.fallidos:
                origen = f" ({fila.origen})" if fila.origen else ""
                texto_fallidos.insert("end", f"- {fila.nombre or '(sin nombre)'}{origen}: {motivo}\n")
            texto_fallidos.config(state="disabled")
            texto_fallidos.pack(padx=12, pady=(0, 6))

        tk.Button(self, text="Cerrar", command=self._cerrar, width=14).pack(pady=(0, 12))

        self._refrescar_tabla()
        self.tree.focus_set()

    def _refrescar_tabla(self):
        self.tree.delete(*self.tree.get_children())
        for i, (fila, existentes) in enumerate(self.pendientes):
            existente_txt = ", ".join(
                f"{e.nombre} ({e.contacto})" + (" — tiene carpeta en Z2" if e.origen == "z2" else "")
                for e in existentes[:2]
            )
            self.tree.insert("", "end", iid=str(i), values=(fila.nombre, fila.contacto, existente_txt))
        self.resumen_label.config(
            text=(
                f"Cargados OK: {self.resultado.ok}\n"
                f"Posibles duplicados pendientes: {len(self.pendientes)}\n"
                f"Fallidos: {len(self.resultado.fallidos)}"
            )
        )
        self._actualizar_seleccion()

    def _seleccionados(self) -> list[int]:
        return sorted(int(i) for i in self.tree.selection())

    def _actualizar_seleccion(self):
        n = len(self.tree.selection())
        self.seleccion_label.config(
            text="" if n == 0 else "1 seleccionado" if n == 1 else f"{n} seleccionados"
        )

    def _seleccionar_todos(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        self.tree.focus_set()
        return "break"

    def _sacar_de_pendientes(self, indices: list[int]) -> list:
        # De atrás para adelante, así los índices que faltan sacar no se corren.
        return [self.pendientes.pop(i)[0] for i in sorted(indices, reverse=True)]

    def _cargar_seleccionados(self):
        indices = self._seleccionados()
        if not indices:
            return
        if len(indices) > 1 and not messagebox.askyesno(
            "Cargar igual",
            f"¿Cargar los {len(indices)} seleccionados aunque parezcan repetidos?",
            parent=self,
        ):
            return
        for fila in self._sacar_de_pendientes(indices):
            db.cargar_fila_igual(fila)
            self.resultado.ok += 1
        self._refrescar_tabla()

    def _descartar_seleccionados(self):
        indices = self._seleccionados()
        if not indices:
            return
        self._sacar_de_pendientes(indices)
        self._refrescar_tabla()

    def _cerrar(self):
        self.destroy()
        self.on_cerrar()
