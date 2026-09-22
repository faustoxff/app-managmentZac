import tkinter as tk
from tkinter import messagebox, ttk

import db
from models import Cliente

COLOR_AVISO = "#fff3cd"


class EditarLotePopup(tk.Toplevel):
    """Edita varios clientes a la vez en una sola mini-tabla (una fila por cliente
    seleccionado, todos los campos editables ahí mismo). Al guardar: las filas sin conflicto
    se guardan directo; las que generan un posible duplicado con OTRO cliente se marcan en
    amarillo y quedan pendientes hasta que el usuario confirme fila por fila con "Guardar
    igual" — nunca se pisa un dato por un duplicado sin que el usuario lo vea."""

    def __init__(self, master, clientes: list[Cliente], on_guardado):
        super().__init__(master)
        self.on_guardado = on_guardado
        self.estados = db.listar_estados()
        self.nombres_estados = [e.nombre for e in self.estados]
        self.hubo_cambios = False

        self.title(f"Editar seleccionados ({len(clientes)} clientes)")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        tk.Label(
            self,
            text="Editá lo que necesites y guardá todo junto. Las filas en amarillo tienen un "
            "posible duplicado con otro cliente y no se guardan solas.",
            wraplength=560,
            justify="left",
        ).pack(padx=12, pady=(12, 6), anchor="w")

        cambio_masivo_frame = tk.Frame(self)
        cambio_masivo_frame.pack(padx=12, pady=(0, 8), anchor="w")
        tk.Label(cambio_masivo_frame, text="Poner a todos los seleccionados en estado:").pack(
            side="left"
        )
        self.estado_masivo_var = tk.StringVar()
        ttk.Combobox(
            cambio_masivo_frame,
            textvariable=self.estado_masivo_var,
            values=self.nombres_estados,
            state="readonly",
            width=14,
        ).pack(side="left", padx=6)
        tk.Button(cambio_masivo_frame, text="Aplicar a todos", command=self._aplicar_estado_masivo).pack(
            side="left"
        )

        header = tk.Frame(self)
        header.pack(fill="x", padx=12)
        for texto, ancho in [
            ("Nombre", 20),
            ("Teléfono", 14),
            ("Estado", 12),
            ("Notas", 16),
            ("Recomendado por", 14),
        ]:
            tk.Label(header, text=texto, width=ancho, anchor="w").pack(side="left", padx=2)

        contenedor = tk.Frame(self)
        contenedor.pack(fill="both", expand=True, padx=12, pady=6)
        canvas = tk.Canvas(contenedor, highlightthickness=0, height=min(320, 46 * len(clientes)))
        scrollbar = ttk.Scrollbar(contenedor, orient="vertical", command=canvas.yview)
        self.filas_frame = tk.Frame(canvas)
        self.filas_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.filas_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.filas: list[dict] = []
        for c in clientes:
            self._agregar_fila(c)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(0, 12))
        tk.Button(btn_frame, text="Guardar cambios", command=self._guardar_todo, width=16).pack(
            side="left", padx=6
        )
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=12).pack(side="left", padx=6)

    def _agregar_fila(self, cliente: Cliente):
        fila_frame = tk.Frame(self.filas_frame)
        fila_frame.pack(fill="x", pady=2)

        nombre_var = tk.StringVar(value=cliente.nombre)
        contacto_var = tk.StringVar(value=cliente.contacto)
        estado_var = tk.StringVar(value=cliente.estado_nombre)
        notas_var = tk.StringVar(value=cliente.notas)
        recomendado_var = tk.StringVar(value=cliente.recomendado_por)

        e_nombre = tk.Entry(fila_frame, textvariable=nombre_var, width=20)
        e_nombre.pack(side="left", padx=2)
        e_contacto = tk.Entry(fila_frame, textvariable=contacto_var, width=14)
        e_contacto.pack(side="left", padx=2)
        combo_estado = ttk.Combobox(
            fila_frame, textvariable=estado_var, values=self.nombres_estados, state="readonly", width=10
        )
        combo_estado.pack(side="left", padx=2)
        e_notas = tk.Entry(fila_frame, textvariable=notas_var, width=16)
        e_notas.pack(side="left", padx=2)
        e_recomendado = tk.Entry(fila_frame, textvariable=recomendado_var, width=14)
        e_recomendado.pack(side="left", padx=2)

        aviso_label = tk.Label(fila_frame, text="⚠️ posible duplicado", fg="#92620a")
        forzar_btn = tk.Button(fila_frame, text="Guardar igual", width=12)
        # aviso_label/forzar_btn se muestran recién si _guardar_todo() detecta conflicto en
        # esta fila — no se pack() todavía.

        fila = {
            "cliente": cliente,
            "nombre_var": nombre_var,
            "contacto_var": contacto_var,
            "estado_var": estado_var,
            "notas_var": notas_var,
            "recomendado_var": recomendado_var,
            "entries": (e_nombre, e_contacto, e_notas, e_recomendado),
            "aviso_label": aviso_label,
            "forzar_btn": forzar_btn,
            "guardada": False,
        }
        forzar_btn.config(command=lambda f=fila: self._forzar_fila(f))
        self.filas.append(fila)

    def _aplicar_estado_masivo(self):
        nuevo_estado = self.estado_masivo_var.get()
        if not nuevo_estado:
            messagebox.showinfo("Elegir estado", "Elegí un estado para aplicar.", parent=self)
            return
        for fila in self.filas:
            if not fila["guardada"]:
                fila["estado_var"].set(nuevo_estado)

    def _valores_actuales(self, fila: dict):
        nombre = fila["nombre_var"].get().strip()
        contacto = fila["contacto_var"].get().strip()
        notas = fila["notas_var"].get().strip()
        recomendado_por = fila["recomendado_var"].get().strip()
        estado_id = next(e.id for e in self.estados if e.nombre == fila["estado_var"].get())
        return nombre, contacto, notas, recomendado_por, estado_id

    def _cambio_sensible(self, fila: dict, nombre: str, contacto: str) -> bool:
        """Solo chequeamos duplicados si nombre o teléfono realmente cambiaron — no tiene
        sentido re-validar contra sí mismo si esos dos campos quedaron igual que antes."""
        cliente = fila["cliente"]
        return nombre != cliente.nombre or contacto != cliente.contacto

    def _guardar_fila(self, fila: dict, nombre, contacto, notas, recomendado_por, estado_id):
        cliente = fila["cliente"]
        db.actualizar_cliente(cliente.id, nombre, contacto, estado_id, notas, recomendado_por)
        fila["guardada"] = True
        self.hubo_cambios = True
        for entry in fila["entries"]:
            entry.config(state="disabled")

    def _forzar_fila(self, fila: dict):
        nombre, contacto, notas, recomendado_por, estado_id = self._valores_actuales(fila)
        self._guardar_fila(fila, nombre, contacto, notas, recomendado_por, estado_id)
        fila["aviso_label"].pack_forget()
        fila["forzar_btn"].pack_forget()

    def _guardar_todo(self):
        pendientes = 0
        for fila in self.filas:
            if fila["guardada"]:
                continue
            nombre, contacto, notas, recomendado_por, estado_id = self._valores_actuales(fila)
            if not nombre or not contacto:
                messagebox.showwarning(
                    "Faltan datos", "Nombre y teléfono son obligatorios en todas las filas.", parent=self
                )
                return

            if self._cambio_sensible(fila, nombre, contacto):
                duplicados = [
                    d for d in db.buscar_duplicados(nombre, contacto) if d.id != fila["cliente"].id
                ]
                if duplicados:
                    fila["aviso_label"].pack(side="left", padx=(4, 2))
                    fila["forzar_btn"].pack(side="left", padx=2)
                    pendientes += 1
                    continue

            self._guardar_fila(fila, nombre, contacto, notas, recomendado_por, estado_id)

        if pendientes:
            messagebox.showwarning(
                "Revisar duplicados",
                f"{pendientes} fila(s) marcadas en amarillo tienen un posible duplicado con "
                "otro cliente y no se guardaron. Usá 'Guardar igual' en esa fila si igual "
                "querés cargarlo así, o corregí el dato.",
                parent=self,
            )
            return

        if self.hubo_cambios:
            self.on_guardado()
        self.destroy()
