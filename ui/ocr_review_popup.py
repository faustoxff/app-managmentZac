import tkinter as tk
from tkinter import messagebox, ttk

from db import FilaImport


class OcrReviewPopup(tk.Toplevel):
    """Tabla editable con los candidatos (nombre, teléfono) detectados por OCR. El usuario
    corrige errores de lectura, borra filas basura y puede agregar filas a mano antes de
    confirmar la importación."""

    def __init__(self, master, candidatos: list[FilaImport], on_confirmar, on_cerrar=None):
        super().__init__(master)
        self.on_confirmar = on_confirmar
        self.on_cerrar = on_cerrar

        self.title("Revisar datos detectados en la foto")
        self.geometry("520x420")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

        info = (
            "Revisá y corregí lo detectado. Borrá las filas que sean basura del OCR y "
            "agregá a mano lo que haya faltado."
        )
        tk.Label(self, text=info, wraplength=480, justify="left").pack(padx=12, pady=(12, 6), anchor="w")

        header = tk.Frame(self)
        header.pack(fill="x", padx=12)
        tk.Label(header, text="Nombre", width=28, anchor="w").pack(side="left")
        tk.Label(header, text="Teléfono", width=18, anchor="w").pack(side="left")

        contenedor = tk.Frame(self)
        contenedor.pack(fill="both", expand=True, padx=12, pady=6)
        canvas = tk.Canvas(contenedor, highlightthickness=0)
        scrollbar = ttk.Scrollbar(contenedor, orient="vertical", command=canvas.yview)
        self.filas_frame = tk.Frame(canvas)
        self.filas_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.filas_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.filas_widgets: list[tuple[tk.StringVar, tk.StringVar, tk.Frame]] = []
        if not candidatos:
            self._agregar_fila()
        else:
            for c in candidatos:
                self._agregar_fila(c.nombre, c.contacto)

        tk.Button(self, text="+ Agregar fila", command=lambda: self._agregar_fila()).pack(
            padx=12, pady=(0, 6), anchor="w"
        )

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(0, 12))
        tk.Button(btn_frame, text="Confirmar importación", command=self._confirmar, width=20).pack(
            side="left", padx=6
        )
        tk.Button(btn_frame, text="Cancelar", command=self._cerrar, width=14).pack(side="left", padx=6)

    def _agregar_fila(self, nombre: str = "", contacto: str = ""):
        fila_frame = tk.Frame(self.filas_frame)
        fila_frame.pack(fill="x", pady=2)

        nombre_var = tk.StringVar(value=nombre)
        contacto_var = tk.StringVar(value=contacto)
        tk.Entry(fila_frame, textvariable=nombre_var, width=28).pack(side="left", padx=(0, 4))
        tk.Entry(fila_frame, textvariable=contacto_var, width=18).pack(side="left", padx=(0, 4))
        tk.Button(
            fila_frame, text="Borrar", command=lambda: self._borrar_fila(fila_frame)
        ).pack(side="left")

        self.filas_widgets.append((nombre_var, contacto_var, fila_frame))

    def _borrar_fila(self, fila_frame):
        self.filas_widgets = [f for f in self.filas_widgets if f[2] is not fila_frame]
        fila_frame.destroy()

    def _confirmar(self):
        filas = []
        for nombre_var, contacto_var, _ in self.filas_widgets:
            nombre = nombre_var.get().strip()
            contacto = contacto_var.get().strip()
            if not nombre and not contacto:
                continue
            filas.append(FilaImport(nombre=nombre, contacto=contacto, origen="Foto (revisado)"))

        if not filas:
            messagebox.showinfo("Sin datos", "No hay filas para importar.", parent=self)
            return

        self.on_confirmar(filas)
        self._cerrar()

    def _cerrar(self):
        self.destroy()
        if self.on_cerrar:
            self.on_cerrar()
