import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import config
import db
import version
from fechas import formatear_fecha
from ui.actualizacion_popup import ActualizacionPopup
from ui.api_key_popup import ApiKeyPopup
from ui.backup_popup import BackupPopup
from ui.cliente_form import ClienteForm
from ui.estados import EstadosPopup
from ui.editar_lote_popup import EditarLotePopup
from ui.filtros import FiltrosPopup
from ui.ia_import_popup import IAImportPopup
from ui.mapeo_excel_popup import MapeoColumnasPopup
from ui.ocr_review_popup import OcrReviewPopup
from ui.resumen_import_popup import ResumenImportPopup
from ui.subida_celular_popup import SubidaCelularPopup


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        # Visible siempre, sin depender de internet ni de entrar a ningún menú — antes la
        # única forma de saber qué versión tenía instalada una PC era abrir "Buscar
        # actualización" (que además necesita conexión), lo que hacía imposible confirmar a
        # distancia si un usuario estaba realmente corriendo la versión nueva después de una
        # actualización o instalación manual.
        self.title(f"Gestor de Clientes — v{version.__version__}")
        self.geometry("980x560")
        self.minsize(760, 420)

        self.filtros: dict = {}
        self._estado_colores: dict[int, str] = {}
        self.busqueda_rapida = ""
        self._debounce_id = None

        # Estado de "subida por celular": None mientras está apagado.
        self.photo_server = None
        self.cola_fotos: "queue.Queue[str] | None" = None
        self.ocr_popup_activo = None
        self._subida_ip = None
        self._subida_puerto = None
        self._ocr_en_progreso = False

        self._build_menu()
        self._build_toolbar()
        self._build_table()
        self._refrescar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind_all("<Control-a>", self._atajo_nuevo_cliente)
        # Con Bloq Mayús activado, Windows manda el evento como Control-A (mayúscula) en vez
        # de Control-a — el bind es case-sensitive, así que sin esto el atajo no respondía con
        # Bloq Mayús puesto (algo común en esta app, que fuerza nombres en mayúscula).
        self.bind_all("<Control-A>", self._atajo_nuevo_cliente)

    def _on_close(self):
        if self.photo_server is not None:
            try:
                self.photo_server.detener()
            except OSError:
                pass  # no bloqueamos el cierre de la app por un error al apagar el servidor
        if config.obtener_backup_automatico() and config.obtener_neon_connection_string():
            # Backup sincrónico a propósito acá: la ventana se está por cerrar de todos modos,
            # así que no hace falta un hilo aparte — solo que no bloquee más de unos segundos.
            import backup

            try:
                backup.hacer_backup_ahora()
            except Exception:  # noqa: BLE001 - nunca impedimos cerrar la app por esto
                pass
        self.destroy()

    # ---------- construcción de UI ----------

    def _build_menu(self):
        menubar = tk.Menu(self)
        config_menu = tk.Menu(menubar, tearoff=0)
        config_menu.add_command(label="Configurar IA", command=self._cambiar_api_key)
        config_menu.add_command(label="Backup en la nube (Neon)", command=self._abrir_backup)
        menubar.add_cascade(label="Configuración", menu=config_menu)

        ayuda_menu = tk.Menu(menubar, tearoff=0)
        ayuda_menu.add_command(label="Buscar actualización", command=self._buscar_actualizacion)
        ayuda_menu.add_command(label="Ver log de diagnóstico", command=self._ver_log_diagnostico)
        menubar.add_cascade(label="Ayuda", menu=ayuda_menu)

        self.config(menu=menubar)

    def _abrir_backup(self):
        BackupPopup(self)

    def _ver_log_diagnostico(self):
        # Para poder pedirle este archivo a un usuario sin que tenga que navegar carpetas
        # ocultas de Windows (%APPDATA% no se ve por default en el Explorador) — un clic desde
        # acá alcanza para mandarlo por WhatsApp/mail.
        if not db.LOG_PATH.exists():
            messagebox.showinfo(
                "Sin log todavía", "Todavía no se generó ningún log de diagnóstico."
            )
            return
        import os

        if not hasattr(os, "startfile"):
            # os.startfile solo existe en Windows — en desarrollo sobre Linux/Mac mostramos
            # la ruta en vez de fallar.
            messagebox.showinfo("Log de diagnóstico", f"Archivo en:\n{db.LOG_PATH}")
            return
        try:
            os.startfile(db.LOG_PATH)  # abre con el editor de texto default de Windows
        except OSError as exc:
            messagebox.showerror("No se pudo abrir", f"No se pudo abrir el archivo:\n{exc}")

    def _cambiar_api_key(self):
        ApiKeyPopup(self)

    def _buscar_actualizacion(self):
        ActualizacionPopup(self)

    def _build_toolbar(self):
        bar = tk.Frame(self, pady=8, padx=8)
        bar.pack(fill="x")

        tk.Button(bar, text="Nuevo cliente", command=self._nuevo_cliente).pack(side="left", padx=4)
        tk.Button(bar, text="Editar", command=self._editar_cliente).pack(side="left", padx=4)
        tk.Button(bar, text="Borrar", command=self._borrar_cliente).pack(side="left", padx=4)
        tk.Button(bar, text="Filtros", command=self._abrir_filtros).pack(side="left", padx=4)
        tk.Button(bar, text="Estados", command=self._abrir_estados).pack(side="left", padx=4)
        tk.Button(bar, text="Imprimir seleccionados", command=self._imprimir).pack(side="left", padx=4)
        tk.Button(bar, text="Editar seleccionados", command=self._editar_seleccionados).pack(
            side="left", padx=4
        )

        # Empaquetados a la derecha en orden inverso al visual: el último en este bloque
        # queda más a la izquierda. Orden visual resultante (izq -> der): Subida por celular,
        # Importar Excel, Importar por foto, Importar con IA, Exportar Excel.
        tk.Button(bar, text="Exportar Excel", command=self._exportar_excel).pack(side="right", padx=4)
        tk.Button(bar, text="Importar con IA", command=self._importar_ia).pack(side="right", padx=4)
        tk.Button(bar, text="Importar por foto", command=self._importar_foto).pack(side="right", padx=4)
        tk.Button(bar, text="Importar Excel", command=self._importar_excel).pack(side="right", padx=4)
        self.subida_btn = tk.Button(
            bar, text="Subida por celular", command=self._toggle_subida_celular
        )
        self.subida_btn.pack(side="right", padx=4)

        busqueda_frame = tk.Frame(self, pady=(0), padx=8)
        busqueda_frame.pack(fill="x")
        tk.Label(busqueda_frame, text="Buscar:").pack(side="left")
        self.busqueda_var = tk.StringVar()
        self.busqueda_var.trace_add("write", self._on_busqueda_tecla)
        tk.Entry(busqueda_frame, textvariable=self.busqueda_var, width=30).pack(
            side="left", padx=(6, 0)
        )
        tk.Button(
            busqueda_frame, text="✕", command=self._limpiar_busqueda, width=2, fg="gray30"
        ).pack(side="left", padx=(2, 0))
        tk.Label(
            busqueda_frame, text="(nombre o teléfono — convive con el popup de Filtros)", fg="gray40"
        ).pack(side="left", padx=(8, 0))

        self.filtros_label = tk.Label(self, text="", fg="gray20", anchor="w", padx=8)
        self.filtros_label.pack(fill="x")

    def _build_table(self):
        cols = ("nombre", "contacto", "estado", "fecha_alta", "fecha", "recomendado_por", "notas")
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        headers = {
            "nombre": ("Nombre", 180),
            "contacto": ("Contacto", 160),
            "estado": ("Estado", 110),
            "fecha_alta": ("Fecha de alta", 140),
            "fecha": ("Última actualización", 150),
            "recomendado_por": ("Recomendado por", 150),
            "notas": ("Notas", 230),
        }
        for c, (label, width) in headers.items():
            self.tree.heading(c, text=label, anchor="w")
            self.tree.column(c, width=width, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._combo_estado_activo: ttk.Combobox | None = None
        self._ultima_celda = None  # (fila_iid, col_index) del último clic, para Ctrl+C
        self.tree.bind("<Button-1>", self._click_tabla)
        self.tree.bind("<Double-1>", self._doble_click_tabla)
        self.tree.bind("<Control-c>", self._copiar_celda)

    # ---------- búsqueda rápida ----------

    def _on_busqueda_tecla(self, *_args):
        """Debounce: cada tecla cancela el after() pendiente y agenda uno nuevo. Si el usuario
        sigue tipeando, nunca llega a dispararse — recién consulta la DB 300ms después de la
        última tecla, no en cada una."""
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(300, self._aplicar_busqueda_rapida)

    def _aplicar_busqueda_rapida(self):
        self._debounce_id = None
        self.busqueda_rapida = self.busqueda_var.get().strip()
        self._refrescar()

    def _limpiar_busqueda(self):
        """La cruz limpia y aplica al toque, sin esperar los 300ms del debounce — al vaciar
        el campo a mano no hace falta ese margen, el usuario ya terminó de decidir."""
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
            self._debounce_id = None
        self.busqueda_var.set("")
        self.busqueda_rapida = ""
        self._refrescar()

    # ---------- datos ----------

    def _refrescar(self):
        # La búsqueda rápida, si tiene texto, pisa el texto del popup de Filtros para esta
        # consulta (pero el estado/fecha del popup se siguen respetando). Si está vacía, se
        # vuelve a usar lo que haya quedado cargado en el popup.
        texto_efectivo = self.busqueda_rapida or self.filtros.get("texto")
        clientes = db.listar_clientes(
            estado_id=self.filtros.get("estado_id"),
            fecha_desde=self.filtros.get("fecha_desde"),
            fecha_hasta=self.filtros.get("fecha_hasta"),
            texto=texto_efectivo,
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
                values=(
                    c.nombre,
                    c.contacto,
                    c.estado_nombre,
                    formatear_fecha(c.fecha_alta),
                    formatear_fecha(c.fecha_actualizacion),
                    c.recomendado_por,
                    c.notas,
                ),
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
        r, g, b = (int(v + (255 - v) * 0.55) for v in (r, g, b))
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

    def _seleccion_ids(self) -> list[int]:
        return [int(i) for i in self.tree.selection()]

    # ---------- edición inline del estado ----------

    def _click_tabla(self, event):
        if self._combo_estado_activo is not None:
            self._combo_estado_activo.destroy()
            self._combo_estado_activo = None

        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        columna = self.tree.identify_column(event.x)
        fila_iid = self.tree.identify_row(event.y)
        if not fila_iid:
            return
        col_index = int(columna.replace("#", "")) - 1
        self._ultima_celda = (fila_iid, col_index)  # recordado para Ctrl+C

        if self.tree["columns"][col_index] != "estado":
            return

        self._abrir_editor_estado_inline(fila_iid, columna)

    def _copiar_celda(self, event=None):
        """Ctrl+C copia al portapapeles el valor de la última celda clickeada (ej. para pegar
        un teléfono en WhatsApp o el dialer). No hay edición de celda por pegado — para
        modificar un dato se usa "Editar" (abre el formulario) como ya existía."""
        if not self._ultima_celda:
            return
        fila_iid, col_index = self._ultima_celda
        if not self.tree.exists(fila_iid):
            return
        valores = self.tree.item(fila_iid, "values")
        if col_index >= len(valores):
            return
        self.clipboard_clear()
        self.clipboard_append(str(valores[col_index]))

    def _doble_click_tabla(self, event):
        # Si el doble clic cae sobre la celda de estado, no abrimos el formulario completo:
        # el clic simple ya deja elegir el estado con el dropdown inline.
        columna = self.tree.identify_column(event.x)
        if columna:
            col_index = int(columna.replace("#", "")) - 1
            if self.tree["columns"][col_index] == "estado":
                return
        self._editar_cliente()

    def _abrir_editor_estado_inline(self, fila_iid: str, columna: str):
        bbox = self.tree.bbox(fila_iid, columna)
        if not bbox:
            return
        x, y, w, h = bbox

        cliente_id = int(fila_iid)
        cliente = next((c for c in self._clientes_actuales if c.id == cliente_id), None)
        if not cliente:
            return

        estados = db.listar_estados()
        var = tk.StringVar(value=cliente.estado_nombre)
        combo = ttk.Combobox(
            self.tree, textvariable=var, values=[e.nombre for e in estados], state="readonly"
        )
        combo.place(x=x, y=y, width=w, height=h)
        combo.focus_set()
        self._combo_estado_activo = combo

        def cerrar():
            combo.destroy()
            if self._combo_estado_activo is combo:
                self._combo_estado_activo = None

        def confirmar(event=None):
            nuevo_nombre = var.get()
            cerrar()
            nuevo_estado = next((e for e in estados if e.nombre == nuevo_nombre), None)
            if nuevo_estado and nuevo_estado.id != cliente.estado_id:
                db.cambiar_estado_cliente(cliente_id, nuevo_estado.id)
                self._refrescar()

        # OJO: NO bindear <FocusOut> acá para cerrar — abrir la lista desplegable del propio
        # combobox dispara un FocusOut transitorio (el foco pasa al popup de opciones), así
        # que destruir el widget en ese evento cierra el dropdown antes de que se llegue a ver
        # ninguna opción. El combo se cierra solo al elegir un valor, al tocar Escape, o al
        # hacer clic en otra celda de la tabla (que ya limpia cualquier combo abierto).
        combo.bind("<<ComboboxSelected>>", confirmar)
        combo.bind("<Escape>", lambda e: cerrar())

    # ---------- acciones ----------

    def _nuevo_cliente(self):
        ClienteForm(self, on_saved=self._refrescar)

    def _atajo_nuevo_cliente(self, event):
        # bind_all dispara esto en toda la app, incluidos los Entry/Text de cualquier ventana
        # (por ejemplo, el buscador o los campos del propio formulario de cliente) — Ctrl+A ahí
        # ya tiene su uso normal de Tkinter (ir al inicio de la línea), así que no lo pisamos.
        foco = self.focus_get()
        if isinstance(foco, (tk.Entry, tk.Text, ttk.Combobox)):
            return
        # bind_all también dispara con el foco en cualquier popup modal abierto (Estados,
        # Backup, Filtros, etc.) si el widget enfocado ahí no es un Entry/Text/Combobox (ej.
        # una Treeview o un Button) — sin este chequeo, se abría "Nuevo cliente" encima del
        # popup y le robaba el grab modal, dejándolo roto al cerrar el nuevo formulario.
        if foco is not None and foco.winfo_toplevel() is not self:
            return
        self._nuevo_cliente()
        return "break"

    def _editar_cliente(self):
        cliente_id = self._seleccion_id()
        if not cliente_id:
            messagebox.showinfo("Seleccionar", "Elegí un cliente para editar.")
            return
        cliente = next(c for c in self._clientes_actuales if c.id == cliente_id)
        ClienteForm(self, on_saved=self._refrescar, cliente=cliente)

    def _borrar_cliente(self):
        ids = self._seleccion_ids()
        if not ids:
            messagebox.showinfo("Seleccionar", "Elegí uno o más clientes para borrar.")
            return
        pregunta = (
            "¿Borrar el cliente seleccionado?"
            if len(ids) == 1
            else f"¿Borrar los {len(ids)} clientes seleccionados?"
        )
        if not messagebox.askyesno("Confirmar", pregunta):
            return
        for cliente_id in ids:
            db.eliminar_cliente(cliente_id)
        self._refrescar()

    def _abrir_filtros(self):
        FiltrosPopup(self, self.filtros, on_apply=self._aplicar_filtros)

    def _aplicar_filtros(self, filtros: dict):
        self.filtros = filtros
        self._refrescar()

    def _abrir_estados(self):
        EstadosPopup(self, on_change=self._refrescar)

    def _exportar_excel(self):
        if not self._clientes_actuales:
            messagebox.showinfo("Sin datos", "No hay clientes para exportar en la vista actual.")
            return
        try:
            import excel_import
        except ImportError:
            messagebox.showerror(
                "Falta una dependencia",
                "Para exportar a Excel hace falta instalar openpyxl:\n\npip install openpyxl",
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], initialfile="clientes.xlsx"
        )
        if not path:
            return
        try:
            excel_import.exportar_excel(path, self._clientes_actuales)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error al exportar", str(exc))
            return
        messagebox.showinfo("Exportado", f"Se exportaron {len(self._clientes_actuales)} clientes.")

    def _imprimir(self):
        ids_seleccionados = set(self._seleccion_ids())
        if ids_seleccionados:
            clientes = [c for c in self._clientes_actuales if c.id in ids_seleccionados]
        else:
            clientes = self._clientes_actuales

        if not clientes:
            messagebox.showinfo("Sin datos", "No hay clientes para imprimir en la vista actual.")
            return

        try:
            import impresion

            impresion.imprimir_clientes(clientes)
        except Exception as exc:  # noqa: BLE001 - no crashear si falla abrir el navegador
            messagebox.showerror("Error al generar la vista de impresión", str(exc))

    def _editar_seleccionados(self):
        ids_seleccionados = set(self._seleccion_ids())
        if not ids_seleccionados:
            messagebox.showinfo("Seleccionar", "Elegí uno o más clientes para editar.")
            return
        clientes = [c for c in self._clientes_actuales if c.id in ids_seleccionados]
        EditarLotePopup(self, clientes, on_guardado=self._refrescar)

    # ---------- Import Excel ----------

    def _importar_excel(self):
        try:
            import excel_import
        except ImportError:
            messagebox.showerror(
                "Falta una dependencia",
                "Para importar Excel hace falta instalar openpyxl:\n\npip install openpyxl",
            )
            return

        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            headers = excel_import.leer_headers(path)
        except Exception as exc:  # noqa: BLE001 - no crashear ante un .xlsx corrupto/inválido
            messagebox.showerror("Error al leer el Excel", str(exc))
            return
        if not headers:
            messagebox.showwarning(
                "Excel vacío", "El archivo no tiene encabezados en la primera fila."
            )
            return

        MapeoColumnasPopup(self, headers, on_confirmar=lambda mapeo: self._procesar_excel(path, mapeo))

    def _procesar_excel(self, path: str, mapeo: dict):
        import excel_import

        try:
            filas = excel_import.parsear_filas(path, mapeo)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error al importar", str(exc))
            return

        resultado = db.procesar_lote(filas)
        self._refrescar()
        ResumenImportPopup(self, resultado, on_cerrar=self._refrescar)

    # ---------- Import por foto (OCR) ----------

    def _importar_foto(self):
        try:
            import ocr_import  # noqa: F401 - solo para chequear que la dependencia está
        except ImportError:
            messagebox.showerror(
                "Falta una dependencia",
                "Para importar por foto hace falta instalar pytesseract y Pillow:\n\n"
                "pip install pytesseract Pillow",
            )
            return

        path = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return

        self._procesar_foto_ocr(path)

    def _procesar_foto_ocr(self, path: str):
        """Corre el OCR sobre una foto (en un hilo aparte, para no congelar la ventana mientras
        Tesseract procesa la imagen) y abre la tabla de revisión al terminar. Se usa tanto para
        el botón manual como para las fotos que llegan por la subida desde el celular."""
        if self._ocr_en_progreso or self.ocr_popup_activo is not None:
            # El botón manual no se deshabilita mientras corre el OCR, así que un segundo clic
            # (o una segunda foto del celular llegando casi al mismo tiempo) podría pisar la
            # que ya se está procesando. También cubrimos el caso de que ya haya una tabla de
            # revisión abierta sin confirmar: antes solo se chequeaba _ocr_en_progreso, así que
            # el botón manual podía abrir una SEGUNDA revisión mientras la primera seguía sin
            # cerrar, pisando la referencia en self.ocr_popup_activo (la cola de fotos del
            # celular, más abajo, ya hacía bien este chequeo).
            messagebox.showinfo(
                "Procesando", "Ya hay una foto en proceso o pendiente de revisión, esperá a que termine."
            )
            return
        self._ocr_en_progreso = True
        threading.Thread(target=self._trabajo_ocr, args=(path,), daemon=True).start()

    def _trabajo_ocr(self, path: str):
        import ocr_import

        try:
            try:
                candidatos = ocr_import.extraer_candidatos(path)
            except ocr_import.TesseractNoDisponible as exc:
                # Python borra `exc` al salir del except (aunque el return ya se haya
                # ejecutado) — como self.after difiere la lambda, hay que copiar el texto a
                # una variable normal antes, si no explota con NameError cuando Tkinter la
                # ejecuta más tarde.
                mensaje = str(exc)
                self._agendar_en_ui(lambda: self._on_ocr_error("Tesseract no disponible", mensaje))
                return
            except Exception as exc:  # noqa: BLE001 - no crashear ante una imagen rara
                mensaje = str(exc)
                self._agendar_en_ui(lambda: self._on_ocr_error("Error al procesar la imagen", mensaje))
                return
            self._agendar_en_ui(
                lambda: self._on_ocr_listo(candidatos, ocr_import.hubo_fallback_idioma())
            )
        finally:
            self._borrar_si_es_foto_pendiente(path)

    def _agendar_en_ui(self, callback):
        """self.after(0, callback), pero sin reventar si la ventana ya se cerró mientras el
        OCR corría en el hilo de fondo (ej. Tesseract tarda unos segundos en una foto grande y
        el usuario cierra la app antes de que termine) — self.after() en una ventana ya
        destruida lanza desde este hilo daemon, sin ningún try/except arriba que lo atrape."""
        try:
            self.after(0, callback)
        except (RuntimeError, tk.TclError):
            pass

    def _borrar_si_es_foto_pendiente(self, path: str):
        """Las fotos que llegan por "Subida por celular" quedan en una carpeta interna de la
        app (config.carpeta_fotos_pendientes()) solo como paso intermedio hasta que el OCR las
        procesa — una vez procesadas ya no hacen falta, y sin borrarlas se acumulan ahí para
        siempre. NO tocamos fotos elegidas a mano con "Importar por foto" (vienen de un
        filedialog): esas son archivos del usuario en su propia carpeta, no nuestros para
        borrar."""
        try:
            p = Path(path)
            if p.parent == config.carpeta_fotos_pendientes():
                p.unlink(missing_ok=True)
        except OSError:
            pass

    def _on_ocr_error(self, titulo: str, mensaje: str):
        self._ocr_en_progreso = False
        if not self.winfo_exists():
            return  # la ventana se cerró mientras el OCR corría en el hilo de fondo
        messagebox.showerror(titulo, mensaje)

    def _on_ocr_listo(self, candidatos, hubo_fallback_idioma: bool):
        self._ocr_en_progreso = False
        if not self.winfo_exists():
            return  # la ventana se cerró mientras el OCR corría en el hilo de fondo

        if hubo_fallback_idioma:
            messagebox.showwarning(
                "No se pudo usar español",
                "No se pudo cargar el idioma español para leer la foto y se usó inglés en su "
                "lugar, así que los resultados van a ser mucho peores de lo normal. Revisá "
                "los datos con más cuidado antes de confirmar, o probá reinstalar/actualizar "
                "la app.",
            )

        self.ocr_popup_activo = OcrReviewPopup(
            self,
            candidatos,
            on_confirmar=self._procesar_ocr,
            on_cerrar=self._limpiar_ocr_popup_activo,
        )

    def _limpiar_ocr_popup_activo(self):
        self.ocr_popup_activo = None

    def _procesar_ocr(self, filas):
        resultado = db.procesar_lote(filas)
        self._refrescar()
        ResumenImportPopup(self, resultado, on_cerrar=self._refrescar)

    # ---------- Import con IA ----------

    def _importar_ia(self):
        try:
            import ia_import  # noqa: F401 - solo para chequear que la dependencia está
        except ImportError:
            messagebox.showerror(
                "Falta una dependencia",
                "Para importar con IA hace falta instalar anthropic:\n\npip install anthropic",
            )
            return
        IAImportPopup(self, on_resultado=self._on_resultado_ia)

    def _on_resultado_ia(self, candidatos):
        self.ocr_popup_activo = OcrReviewPopup(
            self,
            candidatos,
            on_confirmar=self._procesar_ocr,
            on_cerrar=self._limpiar_ocr_popup_activo,
        )

    # ---------- Subida de fotos desde el celular ----------

    def _toggle_subida_celular(self):
        if self.photo_server is not None:
            # ya está activo: reabre el QR por si el usuario cerró el popup sin desactivar
            SubidaCelularPopup(
                self, self._subida_ip, self._subida_puerto, on_desactivar=self._desactivar_subida_celular
            )
            return

        try:
            import photo_server
        except ImportError:
            messagebox.showerror(
                "Falta una dependencia",
                "Para esto hace falta instalar qrcode:\n\npip install qrcode",
            )
            return

        self.cola_fotos = queue.Queue()
        servidor = photo_server.PhotoServer(config.carpeta_fotos_pendientes(), self.cola_fotos)
        try:
            ip, puerto = servidor.iniciar()
        except OSError as exc:
            messagebox.showerror(
                "No se pudo activar",
                f"No se pudo levantar el servidor local:\n{exc}\n\n"
                "Podés seguir usando 'Importar por foto' manualmente.",
            )
            return

        self.photo_server = servidor
        self._subida_ip, self._subida_puerto = ip, puerto
        self.subida_btn.config(text="Subida por celular (activa)")

        SubidaCelularPopup(self, ip, puerto, on_desactivar=self._desactivar_subida_celular)
        self._revisar_cola_fotos()

    def _desactivar_subida_celular(self):
        if self.photo_server is not None:
            self.photo_server.detener()
        self.photo_server = None
        self.cola_fotos = None
        self.subida_btn.config(text="Subida por celular")

    def _revisar_cola_fotos(self):
        if self.cola_fotos is not None and self.ocr_popup_activo is None and not self._ocr_en_progreso:
            try:
                path_foto = self.cola_fotos.get_nowait()
            except queue.Empty:
                path_foto = None
            if path_foto is not None:
                self._procesar_foto_ocr(path_foto)

        if self.photo_server is not None:
            self.after(500, self._revisar_cola_fotos)
