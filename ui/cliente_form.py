from datetime import date
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import db
import z2_sync
from models import Cliente
from ui.calendario_popup import CalendarioPopup
from ui.duplicado_popup import DuplicadoPopup
from ui.panel_duplicados import PanelDuplicados

# Espera antes de buscar coincidencias mientras se tipea. Mismo criterio que el debounce de
# la búsqueda rápida de la ventana principal (300ms): evita consultar la base en cada tecla
# sin dejar el panel con atraso perceptible.
DEBOUNCE_BUSQUEDA_MS = 300


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

        tk.Label(self, text="Recordatorio").grid(row=4, column=0, sticky="w", **pad)
        recordatorio_frame = tk.Frame(self)
        recordatorio_frame.grid(row=4, column=1, sticky="w", **pad)
        self._recordatorio_fecha = cliente.fecha_recordatorio if cliente else ""
        self.recordatorio_label = tk.Label(recordatorio_frame, text="", width=24, anchor="w", relief="sunken")
        self.recordatorio_label.pack(side="left")
        tk.Button(recordatorio_frame, text="📅", width=3, command=self._elegir_recordatorio).pack(
            side="left", padx=(4, 0)
        )
        self._refrescar_label_recordatorio()

        self.contacto_entry = contacto_entry  # atributo: _restituir_foco lo necesita

        # Panel lateral de coincidencias: solo al DAR DE ALTA. Al editar, el cliente que se
        # está editando coincide consigo mismo y el panel llenaría de falsos positivos; el
        # chequeo de duplicados al guardar ya cubre ese caso (ver _guardar).
        self._panel_duplicados: PanelDuplicados | None = None
        self._debounce_busqueda_id = None
        if cliente is None:
            for var in (self.nombre_var, self.contacto_var):
                var.trace_add("write", self._programar_busqueda_duplicados)
            # Se recuerda en qué campo está escribiendo para devolverle el foco si el panel se
            # lo queda (ver _restituir_foco).
            self._ultimo_entry_focado = None
            self._reafirmar_foco_id = None
            for entry in (self.nombre_entry, contacto_entry):
                entry.bind(
                    "<FocusIn>", lambda _e, w=entry: setattr(self, "_ultimo_entry_focado", w)
                )
            # El panel es hijo de este Toplevel: si el formulario se cierra por la X (que no
            # pasa por _guardar ni por _limpiar_para_siguiente), el panel se va con él en vez
            # de quedar flotando sin formulario al que pertenecer.
            self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Enter guarda directo desde cualquiera de estos campos (no en Notas, ahí Enter tiene
        # que seguir insertando un salto de línea como siempre).
        for widget in (self.nombre_entry, contacto_entry, self.estado_combo, recomendado_entry):
            widget.bind("<Return>", self._enter_guarda)

        tk.Label(self, text="Notas").grid(row=5, column=0, sticky="nw", **pad)
        self.notas_text = tk.Text(self, width=40, height=6)
        if cliente:
            self.notas_text.insert("1.0", cliente.notas)
        self.notas_text.grid(row=5, column=1, **pad)
        # Por default, Tab en un Text de Tkinter inserta una tabulación en vez de mover el
        # foco (a diferencia de un Entry) — acá lo pisamos para que vaya directo a Guardar y
        # se pueda cargar un cliente entero sin tocar el mouse.
        self.notas_text.bind("<Tab>", self._tab_a_guardar)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(10, 0))
        self.guardar_btn = tk.Button(btn_frame, text="Guardar", command=self._guardar, width=12)
        self.guardar_btn.pack(side="left", padx=5)
        # Los botones de Tkinter solo invocan su comando con la tecla Espacio, no con Enter
        # (a diferencia de los Entry/Combobox de arriba) — sin este bind, si el foco llega acá
        # con Tab (ej. desde Notas), apretar Enter no hacía nada.
        self.guardar_btn.bind("<Return>", self._enter_guarda)
        cierra = "Cerrar" if not cliente else "Cancelar"
        tk.Button(btn_frame, text=cierra, command=self.destroy, width=12).pack(side="left", padx=5)

        self.guardado_label = tk.Label(self, text="", fg="#16a34a")
        self.guardado_label.grid(row=7, column=0, columnspan=2, pady=(4, 8))

        self.nombre_entry.focus_set()

    def _tab_a_guardar(self, event):
        self.guardar_btn.focus_set()
        return "break"  # evita que el Text inserte una tabulación

    def _enter_guarda(self, event):
        self._guardar()
        return "break"

    def _elegir_recordatorio(self):
        CalendarioPopup(self, on_elegir=self._set_recordatorio, fecha_inicial=self._recordatorio_fecha)

    def _set_recordatorio(self, fecha_iso: str):
        self._recordatorio_fecha = fecha_iso
        self._refrescar_label_recordatorio()

    def _refrescar_label_recordatorio(self):
        if not self._recordatorio_fecha:
            self.recordatorio_label.config(text="(sin fecha)", fg="gray40")
            return
        try:
            d = date.fromisoformat(self._recordatorio_fecha)
            self.recordatorio_label.config(text=d.strftime("%d/%m/%Y"), fg="black")
        except ValueError:
            self.recordatorio_label.config(text="(sin fecha)", fg="gray40")

    def _forzar_mayusculas(self, *_args):
        """Se ve en mayúscula mientras se escribe, no solo al guardar (db.crear_cliente ya lo
        hace igual, pero así queda consistente en pantalla desde el primer momento)."""
        texto = self.nombre_var.get()
        mayus = texto.upper()
        if texto != mayus:
            self.nombre_var.set(mayus)

    # ---------- panel lateral de coincidencias ----------

    def _programar_busqueda_duplicados(self, *_args):
        """Debounce: cada tecla cancela la búsqueda pendiente y agenda una nueva, así nunca
        se consulta la base en cada pulsación."""
        self._cancelar_busqueda_duplicados()
        if self.cliente is not None:
            return
        self._debounce_busqueda_id = self.after(
            DEBOUNCE_BUSQUEDA_MS, self._buscar_duplicados_vivo
        )

    def _cancelar_busqueda_duplicados(self):
        # getattr porque destroy() puede correr antes de que __init__ llegue a armar el
        # debounce (ej. el caso de "no hay estados configurados", que destruye la ventana
        # apenas abre).
        if getattr(self, "_debounce_busqueda_id", None) is not None:
            try:
                self.after_cancel(self._debounce_busqueda_id)
            except (tk.TclError, ValueError):
                pass  # la ventana ya se cerró; no hay nada que cancelar
            self._debounce_busqueda_id = None

    def _buscar_duplicados_vivo(self):
        self._debounce_busqueda_id = None
        if self.cliente is not None:
            return
        nombre = self.nombre_var.get().strip()
        contacto = self.contacto_var.get().strip()
        if not nombre and not contacto:
            # Con los dos campos vacíos no hay nada que comparar (y la función ni siquiera
            # tocaría la DB): se oculta el panel en vez de dejarlo mostrando la consulta vieja.
            if self._panel_duplicados is not None:
                self._panel_duplicados.ocultar()
            return
        coincidencias = db.buscar_posibles_duplicados(nombre, contacto)

        if coincidencias:
            if self._panel_duplicados is None:
                self._panel_duplicados = PanelDuplicados(self, on_ver_existente=self._ver_existente)
            self._panel_duplicados.actualizar(coincidencias, nombre, contacto)
            self._restituir_foco()
            self._reafirmar_foco_id = self.after(60, self._reafirmar_foco)
        elif self._panel_duplicados is not None:
            self._panel_duplicados.ocultar()

        # Z2 NO se consulta acá a propósito: preguntar por red en cada tecla hace
        # esperar por algo que igual se va a mirar al guardar. El aviso de "este
        # señor ya tiene carpeta en Z2" sale en _guardar(), una sola vez.

    def _restituir_foco(self):
        """Al aparecer, la Toplevel puede robarle el foco al Entry (según el window manager),
        y como el panel se repinta en cada tecla el usuario se quedaría tipeando en un campo
        muerto. Se lo devolvemos al campo en el que estaba escribiendo.

        Hace falta focus_force() y no focus_set(): con focus_set() el foco sigue despertado en
        la toplevel del panel, porque el window manager considera que ésa es la ventana activa
        (probado sobre display real: focus_get() seguía devolviendo el panel)."""
        if self._panel_duplicados is None or not self._panel_duplicados.winfo_ismapped():
            return
        self._forzar_foco_en_entries()

    def _forzar_foco_en_entries(self):
        actual = self.focus_get()
        if actual is self.nombre_entry or actual is self.contacto_entry:
            return  # el foco ya está donde tiene que estar
        (getattr(self, "_ultimo_entry_focado", None) or self.nombre_entry).focus_force()

    def _reafirmar_foco(self):
        """El window manager le asigna el foco a la ventana nueva ASINCRÓNICAMENTE, después de
        que termina el callback que la mapeó: reaffirmarlo dentro del mismo callback no
        alcanza (probado sobre display real — el foco volvía al panel en el siguiente ciclo de
        eventos). Se reintenta un instante después, con update_idletasks de por medio para que
        el panel ya tenga geometría y no se robe el foco después."""
        try:
            if not self.winfo_exists() or self._panel_duplicados is None:
                return
            if not self._panel_duplicados.winfo_ismapped():
                return
            self.update_idletasks()
            self._forzar_foco_en_entries()
        except tk.TclError:
            pass  # la ventana se cerró mientras tanto

    def _cerrar_panel_duplicados(self):
        """Se usa al guardar o al cancelar: el panel no debe quedar flotando al lado de un
        formulario que ya limpió sus campos."""
        self._cancelar_busqueda_duplicados()
        if getattr(self, "_panel_duplicados", None) is not None:
            self._panel_duplicados.destroy()
            self._panel_duplicados = None

    def destroy(self):
        # El after() de reafirmación del foco no debe sobrevivir a la ventana: dispararía
        # contra un Toplevel destruido.
        if getattr(self, "_reafirmar_foco_id", None) is not None:
            try:
                self.after_cancel(self._reafirmar_foco_id)
            except (tk.TclError, ValueError):
                pass
            self._reafirmar_foco_id = None
        # Override para que todos los caminos de salida (X, guardar, cancelar, ver
        # existente) se lleven el panel y el debounce pendiente: si el after() sobrevive al
        # Toplevel, dispara contra una ventana destruida y revienta en el hilo de Tkinter.
        self._cancelar_busqueda_duplicados()
        if getattr(self, "_panel_duplicados", None) is not None:
            self._panel_duplicados.destroy()
            self._panel_duplicados = None
        super().destroy()

    # ---------- guardar ----------

    def _guardar(self):
        nombre = self.nombre_var.get().strip()
        if not nombre:
            messagebox.showwarning("Falta nombre", "El nombre es obligatorio.", parent=self)
            return
        contacto = self.contacto_var.get().strip()
        notas = self.notas_text.get("1.0", "end").strip()
        recomendado_por = self.recomendado_var.get().strip()
        estado_id = next(e.id for e in self.estados if e.nombre == self.estado_var.get())

        # Editar no chequea nada: ya se está modificando un cliente que existe.
        if self.cliente:
            self._guardar_final(nombre, contacto, estado_id, notas, recomendado_por)
            return

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

        # No hay duplicados en la base local, pero el cliente puede tener una carpeta
        # en Z2. Eso es lo que hay que avisar: si a tu pap le cobró y después aparece
        # la carpeta, el doble cobro ya pasó. Solo se consulta al guardar, una vez.
        self._consultar_z2_antes_de_guardar(nombre, contacto, estado_id, notas, recomendado_por)

    def _consultar_z2_antes_de_guardar(
        self, nombre, contacto, estado_id, notas, recomendado_por
    ):
        """Consulta Z2 en un hilo y, si encuentra el cliente, abre el panel para que se
        vea de dónde vino la coincidencia.

        Si Z2 está apagado o sin internet, sigue derecho a guardar: la integración
        suma información, nunca puede bloquear el trabajo."""
        self.guardar_btn.config(state="disabled", text="Consultando Z2...")
        self.generacion_guardado = getattr(self, "generacion_guardado", 0) + 1
        generacion = self.generacion_guardado

        def seguir():
            # Si el usuario cerró el formulario mientras se consultaba, no se toca nada.
            if generacion != self.generacion_guardado or not self.winfo_exists():
                return
            self.guardar_btn.config(state="normal", text="Guardar")
            if self._panel_duplicados is not None:
                self._panel_duplicados.ocultar()
            if coincidencias:
                self._mostrar_coincidencias_z2(
                    coincidencias, nombre, contacto, estado_id, notas, recomendado_por
                )
            else:
                self._guardar_final(nombre, contacto, estado_id, notas, recomendado_por)

        def consultar():
            try:
                remotas = z2_sync.buscar_coincidencias_en_z2(nombre, contacto)
            except Exception:  # noqa: BLE001 - nunca romper el guardado por esto
                remotas = []
            # after(0) salta al hilo de la UI: Tkinter no deja tocar widgets desde otro.
            coincidencias = [r for r in remotas if isinstance(r, dict)]
            try:
                self.after(0, seguir)
            except tk.TclError:
                pass  # se cerró la ventana: no hay a quién avisarle

        threading.Thread(target=consultar, daemon=True).start()

    def _mostrar_coincidencias_z2(
        self, coincidencias, nombre, contacto, estado_id, notas, recomendado_por
    ):
        """El cliente ya tiene carpeta en Z2. Se abre el MISMO panel de duplicados que
        se usa en vivo, con la columna 'Origen' marcando Z2, para que se vea de dónde
        salió la coincidencia.

        Cargar igual queda a decisión del usuario: el panel es informativo, no frena."""
        if self._panel_duplicados is None:
            self._panel_duplicados = PanelDuplicados(self, on_ver_existente=self._ver_existente)

        clientes = [
            Cliente(
                # id va en None a propósito: acá los ids son int de SQLite y el de Z2 es
                # un uuid. El identificador de Z2 va en id_remoto; el panel arma el iid de
                # la fila con "origen:id_remoto", así que dos coincidencias de Z2 no
                # terminan con el mismo iid (Treeview no los admite repetidos).
                id=None,
                id_remoto=r.get("id", ""),
                nombre=r.get("nombre", ""),
                contacto=r.get("telefono", ""),
                estado_id=0,
                fecha_actualizacion="",
                detalle=r.get("detalle", ""),
                origen="z2",
            )
            for r in coincidencias
        ]
        self._panel_duplicados.actualizar(clientes, nombre, contacto)
        self._restituir_foco()

        # Además del panel lateral, un cartel: el panel se puede no ver, y esto es
        # justo el caso en el que el usuario tiene que enterarse.
        resumen = "\n".join(f"• {r.get('nombre', '')} — {r.get('detalle', '')}" for r in coincidencias[:5])
        if len(coincidencias) > 5:
            resumen += f"\n… y {len(coincidencias) - 5} más."

        if messagebox.askyesno(
            "Este cliente ya tiene carpeta en Z2",
            f"{resumen}\n\n"
            "Ese cliente ya es tuyo y tiene carpeta ART.\n\n"
            "¿Lo guardás igual en Z1?\n"
            "(Si no, se cancela y queda solo en Z2.)",
            parent=self,
        ):
            self._cerrar_panel_duplicados()
            self._guardar_final(nombre, contacto, estado_id, notas, recomendado_por)

    def _guardar_final(self, nombre, contacto, estado_id, notas, recomendado_por):
        if self.cliente:
            db.actualizar_cliente(
                self.cliente.id, nombre, contacto, estado_id, notas, recomendado_por,
                self._recordatorio_fecha,
            )
            self.on_saved()
            self.destroy()
            return

        db.crear_cliente(nombre, contacto, estado_id, notas, recomendado_por, self._recordatorio_fecha)
        self.on_saved()
        # A diferencia de editar, acá dejamos la ventana abierta y limpiamos los campos: es
        # común cargar varios clientes nuevos seguidos (ej. una planilla que se pasa a mano),
        # y volver a abrir "Nuevo cliente" por cada uno es más lento que solo seguir tipeando.
        self._limpiar_para_siguiente(nombre)

    def _limpiar_para_siguiente(self, nombre_guardado: str):
        # El panel se cierra explícitamente y no se espera al debounce: los traces de los
        # StringVar de abajo van a disparar una búsqueda con los campos recién vacíos, pero
        # quedaría mostrando el cliente recién guardado hasta que corra.
        self._cerrar_panel_duplicados()
        self.nombre_var.set("")
        self.contacto_var.set("")
        self.recomendado_var.set("")
        self.notas_text.delete("1.0", "end")
        self._recordatorio_fecha = ""
        self._refrescar_label_recordatorio()
        self.guardado_label.config(text=f"✓ {nombre_guardado} guardado — listo para cargar otro")
        self.nombre_entry.focus_set()

    def _ver_existente(self, cliente_existente: Cliente):
        self._cerrar_panel_duplicados()
        self.destroy()
        ClienteForm(self.master, on_saved=self.on_saved, cliente=cliente_existente)
