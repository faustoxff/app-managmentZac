import tkinter as tk
from tkinter import ttk

import db
from db import ResultadoLote


class ResumenImportPopup(tk.Toplevel):
    """Muestra el resultado de una importación masiva (Excel u OCR): cuántos se cargaron OK,
    y deja revisar los posibles duplicados uno por uno (cargar igual / descartar). Los
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
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=6)
        for c, label, width in [
            ("nombre", "Nombre nuevo", 150),
            ("contacto", "Contacto nuevo", 130),
            ("existente", "Ya existe como", 220),
        ]:
            self.tree.heading(c, text=label)
            self.tree.column(c, width=width)
        self.tree.pack(padx=12, pady=6)

        accion_frame = tk.Frame(self)
        accion_frame.pack(pady=(0, 6))
        tk.Button(accion_frame, text="Cargar igual", command=self._cargar_seleccionado, width=14).pack(
            side="left", padx=6
        )
        tk.Button(accion_frame, text="Descartar", command=self._descartar_seleccionado, width=14).pack(
            side="left", padx=6
        )

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

    def _refrescar_tabla(self):
        self.tree.delete(*self.tree.get_children())
        for i, (fila, existentes) in enumerate(self.pendientes):
            existente_txt = ", ".join(f"{e.nombre} ({e.contacto})" for e in existentes[:2])
            self.tree.insert("", "end", iid=str(i), values=(fila.nombre, fila.contacto, existente_txt))
        self.resumen_label.config(
            text=(
                f"Cargados OK: {self.resultado.ok}\n"
                f"Posibles duplicados pendientes: {len(self.pendientes)}\n"
                f"Fallidos: {len(self.resultado.fallidos)}"
            )
        )

    def _seleccion_idx(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _cargar_seleccionado(self):
        idx = self._seleccion_idx()
        if idx is None:
            return
        fila, _ = self.pendientes.pop(idx)
        db.cargar_fila_igual(fila)
        self.resultado.ok += 1
        self._refrescar_tabla()

    def _descartar_seleccionado(self):
        idx = self._seleccion_idx()
        if idx is None:
            return
        self.pendientes.pop(idx)
        self._refrescar_tabla()

    def _cerrar(self):
        self.destroy()
        self.on_cerrar()
