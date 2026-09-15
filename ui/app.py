import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import db
from ui.cliente_form import ClienteForm
from ui.estados import EstadosPopup
from ui.filtros import FiltrosPopup


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestor de Clientes")
        self.geometry("980x560")
        self.minsize(760, 420)

        self.filtros: dict = {}
        self._estado_colores: dict[int, str] = {}

        self._build_toolbar()
        self._build_table()
        self._refrescar()

    # ---------- construcción de UI ----------

    def _build_toolbar(self):
        bar = tk.Frame(self, pady=8, padx=8)
        bar.pack(fill="x")

        tk.Button(bar, text="Nuevo cliente", command=self._nuevo_cliente).pack(side="left", padx=4)
        tk.Button(bar, text="Editar", command=self._editar_cliente).pack(side="left", padx=4)
        tk.Button(bar, text="Borrar", command=self._borrar_cliente).pack(side="left", padx=4)
        tk.Button(bar, text="Filtros", command=self._abrir_filtros).pack(side="left", padx=4)
        tk.Button(bar, text="Estados", command=self._abrir_estados).pack(side="left", padx=4)

        tk.Button(bar, text="Importar CSV", command=self._importar_csv).pack(side="right", padx=4)
        tk.Button(bar, text="Exportar CSV", command=self._exportar_csv).pack(side="right", padx=4)

        self.filtros_label = tk.Label(self, text="", fg="gray20", anchor="w", padx=8)
        self.filtros_label.pack(fill="x")

    def _build_table(self):
        cols = ("nombre", "contacto", "estado", "fecha", "notas")
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        headers = {
            "nombre": ("Nombre", 180),
            "contacto": ("Contacto", 160),
            "estado": ("Estado", 130),
            "fecha": ("Última actualización", 150),
            "notas": ("Notas", 280),
        }
        for c, (label, width) in headers.items():
            self.tree.heading(c, text=label)
            self.tree.column(c, width=width, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self._editar_cliente())

    # ---------- datos ----------

    def _refrescar(self):
        clientes = db.listar_clientes(
            estado_id=self.filtros.get("estado_id"),
            fecha_desde=self.filtros.get("fecha_desde"),
            fecha_hasta=self.filtros.get("fecha_hasta"),
            texto=self.filtros.get("texto"),
        )
        self.tree.delete(*self.tree.get_children())
        for c in clientes:
            tag = f"estado_{c.estado_id}"
            self._estado_colores[c.estado_id] = c.estado_color
            self.tree.tag_configure(tag, background=self._suavizar(c.estado_color))
            self.tree.insert(
                "",
                "end",
                iid=str(c.id),
                values=(c.nombre, c.contacto, c.estado_nombre, c.fecha_actualizacion, c.notas),
                tags=(tag,),
            )
        self._clientes_actuales = clientes
        self._actualizar_label_filtros()

    @staticmethod
    def _suavizar(hex_color: str) -> str:
        """Mezcla el color del estado con blanco para que el texto siga siendo legible."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) != 6:
            return "#ffffff"
        r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        r, g, b = (int(v + (255 - v) * 0.75) for v in (r, g, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _actualizar_label_filtros(self):
        partes = []
        if self.filtros.get("estado_nombre") and self.filtros["estado_nombre"] != "(Todos)":
            partes.append(f"Estado: {self.filtros['estado_nombre']}")
        if self.filtros.get("fecha_desde"):
            partes.append(f"Desde: {self.filtros['fecha_desde']}")
        if self.filtros.get("fecha_hasta"):
            partes.append(f"Hasta: {self.filtros['fecha_hasta']}")
        if self.filtros.get("texto"):
            partes.append(f"Texto: '{self.filtros['texto']}'")
        texto = "Filtros: " + " | ".join(partes) if partes else "Sin filtros aplicados"
        self.filtros_label.config(text=f"{texto}   ({len(self._clientes_actuales)} clientes)")

    def _seleccion_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    # ---------- acciones ----------

    def _nuevo_cliente(self):
        ClienteForm(self, on_saved=self._refrescar)

    def _editar_cliente(self):
        cliente_id = self._seleccion_id()
        if not cliente_id:
            messagebox.showinfo("Seleccionar", "Elegí un cliente para editar.")
            return
        cliente = next(c for c in self._clientes_actuales if c.id == cliente_id)
        ClienteForm(self, on_saved=self._refrescar, cliente=cliente)

    def _borrar_cliente(self):
        cliente_id = self._seleccion_id()
        if not cliente_id:
            messagebox.showinfo("Seleccionar", "Elegí un cliente para borrar.")
            return
        if not messagebox.askyesno("Confirmar", "¿Borrar el cliente seleccionado?"):
            return
        db.eliminar_cliente(cliente_id)
        self._refrescar()

    def _abrir_filtros(self):
        FiltrosPopup(self, self.filtros, on_apply=self._aplicar_filtros)

    def _aplicar_filtros(self, filtros: dict):
        self.filtros = filtros
        self._refrescar()

    def _abrir_estados(self):
        EstadosPopup(self, on_change=self._refrescar)

    def _importar_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            importados, errores = db.importar_csv(path)
        except Exception as exc:  # noqa: BLE001 - no crashear ante CSV inválido
            messagebox.showerror("Error al importar", f"No se pudo leer el archivo:\n{exc}")
            return
        self._refrescar()
        msg = f"Se importaron {importados} clientes."
        if errores:
            msg += f"\n\n{len(errores)} fila(s) con problemas:\n" + "\n".join(errores[:15])
            if len(errores) > 15:
                msg += f"\n... y {len(errores) - 15} más."
        messagebox.showinfo("Importación finalizada", msg)

    def _exportar_csv(self):
        if not self._clientes_actuales:
            messagebox.showinfo("Sin datos", "No hay clientes para exportar en la vista actual.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="clientes.csv"
        )
        if not path:
            return
        try:
            db.exportar_csv(path, self._clientes_actuales)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error al exportar", str(exc))
            return
        messagebox.showinfo("Exportado", f"Se exportaron {len(self._clientes_actuales)} clientes.")
