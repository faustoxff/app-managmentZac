import threading
import tkinter as tk
from tkinter import messagebox, ttk

import db
import z2_sync
from fechas import formatear_fecha

ESTADO_SIN_VERIFICAR = "sin verificar"
ESTADO_EN_Z2 = "está en Z2"
ESTADO_NO_EN_Z2 = "NO está en Z2"


class PestanaImportadosZ2(tk.Toplevel):
    """Clientes que bajaron de Z2 (origen = "z2"), en una ventana aparte de la lista
    principal. Permite verificar, contra la base de Z2, que cada uno siga existiendo allá."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Importados de Z2")
        self.geometry("900x460")
        self.transient(master)

        barra = tk.Frame(self, padx=8, pady=8)
        barra.pack(fill="x")
        self.verificar_btn = tk.Button(
            barra, text="Verificar con Z2", command=self._verificar, width=18
        )
        self.verificar_btn.pack(side="left")
        self.resumen_label = tk.Label(barra, text="", fg="gray25", padx=12)
        self.resumen_label.pack(side="left")

        cols = ("nombre", "contacto", "estado", "alta", "rec", "z2")
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        encabezados = {
            "nombre": ("NOMBRE", 220),
            "contacto": ("CONTACTO", 130),
            "estado": ("ESTADO", 110),
            "alta": ("ALTA", 100),
            "rec": ("REC.", 120),
            "z2": ("VERIFICACIÓN EN Z2", 190),
        }
        for c, (texto, ancho) in encabezados.items():
            self.tree.heading(c, text=texto, anchor="w")
            self.tree.column(c, width=ancho, anchor="w", stretch=False)
        self.tree.tag_configure("ok", foreground="#15803d")
        self.tree.tag_configure("falta", foreground="#b91c1c")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self._estado_z2: dict[int, str] = {}
        self._cargar()

    def _cargar(self):
        self.tree.delete(*self.tree.get_children())
        estados = {e.id: e.nombre for e in db.listar_estados()}
        clientes = db.listar_clientes(origen=z2_sync.ORIGEN_Z2)
        for c in clientes:
            estado = self._estado_z2.get(c.id, ESTADO_SIN_VERIFICAR)
            tags = ("ok",) if estado == ESTADO_EN_Z2 else ("falta",) if estado == ESTADO_NO_EN_Z2 else ()
            self.tree.insert(
                "",
                "end",
                iid=str(c.id),
                values=(
                    c.nombre,
                    c.contacto,
                    estados.get(c.estado_id, c.estado_nombre),
                    formatear_fecha(c.fecha_alta),
                    c.recomendado_por,
                    estado,
                ),
                tags=tags,
            )
        self.resumen_label.config(text=f"{len(clientes)} cliente(s) importados de Z2")

    def _verificar(self):
        self.verificar_btn.config(state="disabled", text="Verificando...")
        self.resumen_label.config(text="Consultando Z2...")

        def trabajo():
            try:
                telefonos = z2_sync.telefonos_en_z2()
                error = None
            except Exception as exc:  # noqa: BLE001 - se muestra al usuario, no se traga
                telefonos = None
                error = str(exc)
            try:
                self.after(0, lambda: self._pintar_verificacion(telefonos, error))
            except tk.TclError:
                pass  # la ventana se cerró mientras se consultaba

        threading.Thread(target=trabajo, daemon=True).start()

    def _pintar_verificacion(self, telefonos, error):
        self.verificar_btn.config(state="normal", text="Verificar con Z2")
        if error is not None:
            messagebox.showerror(
                "No se pudo verificar",
                f"No se pudo consultar Z2:\n\n{error}\n\nRevisá la conexión de solo lectura "
                "en Configuración → Integración con Z2.",
                parent=self,
            )
            self.resumen_label.config(text="La verificación falló.")
            return

        clientes = db.listar_clientes(origen=z2_sync.ORIGEN_Z2)
        faltan = 0
        for c in clientes:
            telefono = db.normalizar_telefono(c.contacto)
            en_z2 = bool(telefono) and telefono in telefonos
            self._estado_z2[c.id] = ESTADO_EN_Z2 if en_z2 else ESTADO_NO_EN_Z2
            faltan += 0 if en_z2 else 1
        self._cargar()
        self.resumen_label.config(
            text=f"Verificados: {len(clientes) - faltan} están en Z2 · {faltan} no aparecen"
        )
