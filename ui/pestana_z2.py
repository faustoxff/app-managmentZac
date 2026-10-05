"""Pestaña de consulta: los clientes que están en Z2 (carpetas ART).

Es una ventana de SOLO LECTURA. No edita, no borra, no cambia estados: su único
propósito es que se vea, antes de dar de alta un cliente, si esa persona ya tiene
una carpeta ART. Nada de lo que hay en Z2 se copia a la base local por abrirla;
traer un cliente es una acción explícita, con el botón "Traer a Z1".

Como la pestaña principal, trae búsqueda, filtro, orden por columna y la lista
completa. Lo que NO tiene son los botones de modificar, porque acá no hay nada
que modificar.
"""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import config
import db
import z2_sync


class PestanaZ2(tk.Toplevel):
    """Lista en vivo de las carpetas de Z2. Los datos se leen de la base de Z2
    (por Neon, con el usuario de solo lectura), no del endpoint de coincidencias:
    acá se quiere ver todo, no lo que coincide con una búsqueda puntual."""

    def __init__(self, master, on_cliente_traido=None):
        super().__init__(master)
        self.on_cliente_traido = on_cliente_traido
        self.casos: list[dict] = []
        self.filtro_texto = ""
        self._orden: str | None = None
        self._orden_asc = True
        self._cargando = False

        self.title("Clientes de Z2 (carpetas ART) — solo consulta")
        self.geometry("920x520")
        self.transient(master)

        self._construir()

        # La lectura va en un hilo: son cientos de filas en internet y congelar la
        # ventana mientras llegan sería el peor primer gesto de una ventana de consulta.
        self.after(60, self._cargar)

    def _construir(self):
        pad = {"padx": 8, "pady": 5}

        barra = tk.Frame(self)
        barra.pack(fill="x")

        tk.Label(barra, text="Buscar:").pack(side="left", **(pad))
        self.buscar_var = tk.StringVar()
        self.buscar_var.trace_add("write", self._on_buscar)
        entry = tk.Entry(barra, textvariable=self.buscar_var, width=34)
        entry.pack(side="left", padx=(4, 12))
        entry.bind("<Return>", lambda _e: self._on_buscar())
        entry.bind("<Escape>", lambda _e: self.buscar_var.set(""))

        tk.Label(barra, text="Recomendado:").pack(side="left", **(pad))
        self.reco_var = tk.StringVar()
        self.reco_var.trace_add("write", self._aplicar_filtros)
        self.reco_combo = ttk.Combobox(
            barra, textvariable=self.reco_var, values=["(Todos)"], width=18, state="readonly"
        )
        self.reco_combo.pack(side="left", padx=(4, 12))

        tk.Button(barra, text="Recargar", command=self._cargar).pack(side="left", padx=4)
        tk.Button(barra, text="Cerrar", command=self.destroy).pack(side="right", padx=8, pady=5)

        self.resumen_label = tk.Label(self, anchor="w", fg="gray30", **pad)
        self.resumen_label.pack(fill="x")

        contenedor = tk.Frame(self)
        contenedor.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("nombre", "telefono", "recomendado_por", "art", "categoria", "fecha_accidente")
        self.encabezados = {
            "nombre": "NOMBRE",
            "telefono": "TELÉFONO",
            "recomendado_por": "REC.",
            "art": "ART",
            "categoria": "CAT.",
            "fecha_accidente": "FECHA ACC.",
        }
        anchos = {
            "nombre": 250,
            "telefono": 130,
            "recomendado_por": 140,
            "art": 150,
            "categoria": 60,
            "fecha_accidente": 100,
        }

        self.tree = ttk.Treeview(contenedor, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(
                c, text=self.encabezados[c], anchor="w", command=lambda col=c: self._ordenar(col)
            )
            self.tree.column(c, width=anchos[c], anchor="w", stretch=(c == "nombre"))
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(contenedor, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.bind("<Double-1>", lambda _e: self._traer())
        self.tree.bind("<Return>", lambda _e: self._traer())

        # Aviso de "solo consulta": la barra de abajo deja claro que desde acá no se
        # toca nada de Z2, y que traer un cliente lo carga en Z1.
        pie = tk.Frame(self)
        pie.pack(fill="x", padx=8, pady=(0, 8))
        self.traer_btn = tk.Button(pie, text="Traer a Z1", command=self._traer, width=14)
        self.traer_btn.pack(side="left")
        tk.Label(
            pie,
            text="  Z1 nunca manda nada a Z2. Traer un cliente lo carga solo en Z1.",
            fg="gray40",
        ).pack(side="left")

    # ------------------------------------------------------------------ datos

    def _cargar(self):
        self._cargando = True
        self.resumen_label.config(text="Leyendo Z2...", fg="gray30")

        def leer():
            try:
                casos = z2_sync.leer_casos_de_z2()
                error = None
            except Exception as exc:  # noqa: BLE001 - se muestra al usuario
                casos, error = [], str(exc)
            self.after(0, lambda: self._pintar(casos, error))

        threading.Thread(target=leer, daemon=True).start()

    def _pintar(self, casos, error=None):
        if not self.winfo_exists():
            return
        self._cargando = False

        if error:
            self.casos = []
            self.resumen_label.config(
                text=f"No se pudo leer Z2: {error}", fg="#b91c1c"
            )
            self._rellenar_tabla()
            return

        self.casos = casos

        # El combo de "Recomendado" se arma con lo que hay, para no obligar a
        # escribir a mano un valor que ya existe.
        valores = sorted({str(c.get("recomendado_por") or "") for c in casos} - {""})
        self.reco_combo.configure(values=["(Todos)"] + valores)

        self._rellenar_tabla()

    def _visibles(self) -> list[dict]:
        """Aplica el filtro de texto y el de recomendado por."""
        texto = self.filtro_texto
        reco = self.reco_var.get()

        filas = self.casos
        if texto:
            partes = [p for p in texto.lower().split(",") if p.strip()]
            filas = [
                c
                for c in filas
                if all(
                    p.strip() in f"{c['apellido']} {c['nombre']} {c['telefono']} "
                    f"{c.get('recomendado_por') or ''} {c.get('art') or ''} "
                    f"{c.get('categoria') or ''} {c.get('dni') or ''}".lower()
                    for p in partes
                )
            ]
        if reco and reco != "(Todos)":
            filas = [c for c in filas if str(c.get("recomendado_por") or "") == reco]
        return filas

    def _rellenar_tabla(self):
        self.tree.delete(*self.tree.get_children())
        filas = self._visibles()

        if self._orden:
            filas = sorted(
                filas,
                key=lambda c: str(c.get(self._orden) or ""),
                reverse=not self._orden_asc,
            )

        for i, c in enumerate(filas):
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    f"{c['apellido']} {c['nombre']}".strip(),
                    c["telefono"] or "",
                    c.get("recomendado_por") or "",
                    c.get("art") or "",
                    c.get("categoria") or "",
                    c.get("fecha_accidente") or "",
                ),
            )

        if not filas:
            self.resumen_label.config(
                text=(
                    "Sin resultados."
                    if self.casos
                    else "No se pudieron leer las carpetas de Z2."
                ),
                fg="gray30",
            )
        else:
            self.resumen_label.config(
                text=f"{len(filas)} de {len(self.casos)} carpetas de Z2.",
                fg="gray30",
            )

    # ------------------------------------------------------------- interacción

    def _on_buscar(self, *_args):
        # Mismo criterio que la ventana principal: se espera a que pare de tipear.
        if getattr(self, "_debounce_id", None):
            try:
                self.after_cancel(self._debounce_id)
            except (tk.TclError, ValueError):
                pass
        self._debounce_id = self.after(300, self._aplicar_filtros)

    def _aplicar_filtros(self, *_args):
        self.filtro_texto = self.buscar_var.get()
        if not self._cargando:
            self._rellenar_tabla()

    def _ordenar(self, columna):
        if self._orden == columna:
            self._orden_asc = not self._orden_asc
        else:
            self._orden, self._orden_asc = columna, True
        self._rellenar_tabla()

    def _seleccionado(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self._visibles()[int(sel[0])]

    def _traer(self):
        """Trae la carpeta de Z2 a la base local de Z1, en estado NUEVO.

        Se consulta Z2 para armar el nombre completo y el recomendado por con su
        formato real (acá solo llegan cuatro campos); el resto no se copia, y en
        particular NINGÚN dato médico: la carpeta se queda en Z2."""
        caso = self._seleccionado()
        if caso is None:
            messagebox.showinfo(
                "Falta seleccionar", "Elegí una carpeta de la lista.", parent=self
            )
            return

        nombre = f"{caso['apellido']} {caso['nombre']}".strip()

        # No crear dos veces el mismo: se avisa y se sale.
        if db.buscar_duplicados(nombre, caso["telefono"]):
            messagebox.showwarning(
                "Ya está cargado",
                f"{nombre}\n\nEse cliente ya está en la base de Z1.",
                parent=self,
            )
            return

        estado_id = db.obtener_id_estado(z2_sync.ESTADO_NUEVO)
        if estado_id is None:
            messagebox.showerror(
                "Falta el estado",
                f"El estado {z2_sync.ESTADO_NUEVO} no existe en Z1.",
                parent=self,
            )
            return

        cliente_id = db.crear_cliente(
            nombre=nombre,
            contacto=caso["telefono"],
            estado_id=estado_id,
            notas=z2_sync.NOTA_ORIGEN_Z2,
            recomendado_por=str(caso.get("recomendado_por") or ""),
        )

        messagebox.showinfo(
            "Traído de Z2",
            f"{nombre}\n\nCargado en Z1 con estado {z2_sync.ESTADO_NUEVO}.\n"
            "La carpeta ART queda en Z2.",
            parent=self,
        )

        if self.on_cliente_traido:
            self.on_cliente_traido(cliente_id)