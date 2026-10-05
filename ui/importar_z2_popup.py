"""Popup de importación de clientes desde Z2 (Gestor de Carpetas ART).

Z1 lee de la base de Z2 solo 4 columnas: apellido, nombre, telefono y
recomendado_por. Acá se muestra lo que hay en Z2 ordenado en tres grupos, con el
mismo criterio del PanelDuplicados: rojo cuando el teléfono coincide (conclusión
firme), amarillo cuando solo el nombre coincide (duda que necesita un ojo humano).

Reglas, para que el aviso no prometa más de lo que cumple:
  - Coincide el teléfono  -> NO se crea nada. Es la misma persona.
  - Sin teléfono y coincide el nombre exacto -> NO se crea nada, queda acá para
    revisar. No hay teléfono con el cual confirmarlo, así que se decide a mano.
  - Sin coincidencias -> se crea en estado NUEVO.

Se importa en un hilo aparte (ver app.py) porque Z2 es una base en internet: si
se llamara en el hilo de la UI, la ventana se congelaría mientras espera.
"""
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import db
import z2_sync

# Colores tomados del panel de duplicados, para que el usuario no tenga que
# aprender un código de colores nuevo en la misma pantalla.
COLOR_FUERTE = "#b91c1c"   # teléfono igual: seguro que ya está
COLOR_DUDA = "#92620a"      # solo el nombre: miralo
COLOR_OK = "#15803d"       # nuevo, se va a crear
COLOR_GRIS = "#6b7280"     # informativo

# Máximo de filas listadas: con más el popup queda más alto que la pantalla. Lo
# que sobra se avisa abajo, no se esconde.
MAX_FILAS_VISIBLES = 12


class ImportarZ2Popup(tk.Toplevel):
    """Muestra qué hay para importar desde Z2 y deja confirmar.

    No crea nada por su cuenta: `callback` recibe la lista ya filtrada (solo los
    nuevos y los que necesitan revisión) y es app.py quien la pasa a z2_sync, en
    el hilo de la UI.
    """

    def __init__(self, master, resultado: z2_sync.Resultado, on_importar, on_cerrar):
        super().__init__(master)
        self.resultado = resultado
        self.on_importar = on_importar
        self.on_cerrar = on_cerrar

        self.title("Importar clientes desde Z2")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Filas a mostrar: los nuevos primero (son los que se crean), después los
        # que hay que revisar, y al final los que ya estaban (informativo).
        self.nuevos = list(resultado.nuevos)
        self.revisar = list(resultado.para_revisar)
        self.existentes = list(resultado.ya_existentes)

        self.resumen_label = tk.Label(self, font=("", 10, "bold"), justify="left", anchor="w")
        self.resumen_label.pack(padx=12, pady=(12, 8), anchor="w")

        cols = ("estado", "nombre", "contacto", "recomendado_por")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for c, label, ancho in [
            ("estado", "", 34),
            ("nombre", "Nombre", 210),
            ("contacto", "Teléfono", 140),
            ("recomendado_por", "Recomendado por", 180),
        ]:
            self.tree.heading(c, text=label)
            self.tree.column(c, width=ancho)
        self.tree.pack(padx=12, pady=(0, 6))
        # La primera columna no lleva encabezado: es un indicador, no un dato.
        self.tree.heading("estado", text="")

        # Cada fila va con su color y su ícono. El triángulo ⚠ es el aviso de
        # "esto se parece a uno que ya tenés, fijate": sale solo cuando el
        # teléfono no alcanza para confirmarlo.
        total_filas = 0
        for entrada in self.nuevos:
            self.tree.insert("", "end", iid=f"nuevo-{total_filas}",
                             values=("✔", entrada["nombre"], entrada["telefono"],
                                     entrada.get("recomendado_por", "")),
                             tags=("ok",))
            total_filas += 1
        for entrada in self.revisar:
            self.tree.insert("", "end", iid=f"revisar-{total_filas}",
                             values=("⚠", entrada["nombre"], entrada["telefono"] or "(sin teléfono)",
                                     entrada.get("recomendado_por", "")),
                             tags=("duda",))
            total_filas += 1
        for entrada in self.existentes:
            if total_filas >= MAX_FILAS_VISIBLES:
                break
            self.tree.insert("", "end", iid=f"existe-{total_filas}",
                             values=("·", entrada["nombre"], entrada["telefono"],
                                     entrada.get("recomendado_por", "")),
                             tags=("gris",))
            total_filas += 1

        self.tree.tag_configure("ok", foreground=COLOR_OK)
        self.tree.tag_configure("duda", foreground=COLOR_DUDA)
        self.tree.tag_configure("gris", foreground=COLOR_GRIS)

        self.pie_label = tk.Label(self, text="", fg=COLOR_GRIS, anchor="w", justify="left")
        self.pie_label.pack(padx=12, anchor="w")

        botones = tk.Frame(self)
        botones.pack(pady=(10, 12))
        self.boton_importar = tk.Button(
            botones, text=f"Importar {len(self.nuevos)} cliente(s)", command=self._importar, width=22
        )
        self.boton_importar.pack(side="left", padx=6)
        if not self.nuevos:
            # Nada nuevo que traer: no tiene sentido un botón que no hace nada.
            self.boton_importar.config(state="disabled")
        tk.Button(botones, text="Cerrar", command=self._cerrar, width=12).pack(side="left", padx=6)

        self._refrescar_pie()

    def _refrescar_pie(self):
        self.resumen_label.config(
            text=(
                f"En Z2 hay {self.resultado.total_en_z2} carpeta(s).\n"
                f"Nuevos para crear: {len(self.nuevos)}   ·   "
                f"Para revisar: {len(self.revisar)}   ·   "
                f"Ya estaban: {len(self.existentes)}"
            )
        )

        lineas = []
        if self.revisar:
            lineas.append(
                "⚠ Mismo nombre exacto pero SIN teléfono: no se puede confirmar si es la misma "
                "persona, así que no se importa. Revisalos a mano."
            )
        if self.existentes:
            lineas.append(
                "· Con teléfono idéntico a un cliente que ya tenés: es la misma persona, "
                "no se crea nada."
            )
        if not self.nuevos and not self.revisar:
            lineas.append("No hay nada nuevo para traer desde Z2.")
        if self.pie_label.cget("text") and len(self.nuevos) + len(self.revisar) + len(self.existentes) > MAX_FILAS_VISIBLES:
            lineas.append(f"Mostrando las primeras {MAX_FILAS_VISIBLES} filas de la lista.")
        self.pie_label.config(text="\n\n".join(lineas))

    def _importar(self):
        if not self.nuevos:
            return
        self.on_importar(list(self.nuevos))

    def _cerrar(self):
        self.destroy()
        self.on_cerrar()


def abrir_importar_z2(master, al_terminar=None):
    """Abre el popup de importación desde Z2.

    Tkinter NO permite crear widgets fuera del hilo principal: revienta con
    "RuntimeError: main thread is not in main loop". Por eso el hilo auxiliar solo
    lee de Z2 y publica el resultado con master.after(0, ...), que es la forma
    oficial de volver al hilo de la UI. Toda ventana o messagebox se arma desde
    el hilo principal.

    Si Z2 no está configurado o no responde, NO se abre el popup: se avisa con un
    mensaje y Z1 sigue funcionando exactamente igual. La importación suma
    información; nunca puede romper la app.
    """

    def _en_hilo_principal(fn, *args):
        """Ejecuta fn en el hilo de la UI, aunque se llame desde el auxiliar."""
        master.after(0, lambda: fn(*args))

    def _importar_confirmados(master, nuevos, al_terminar):
        """El usuario apretó Importar. Escribe en un hilo (toca la DB) y avisa de
        vuelta en el hilo principal."""

        def escribir():
            try:
                ids = z2_sync.importar(z2_sync.Resultado(nuevos=nuevos))
            except Exception as exc:  # noqa: BLE001 - el error va al messagebox
                _en_hilo_principal(_avisar_error, master, f"No se pudo importar:\n\n{exc}", al_terminar)
                return
            _en_hilo_principal(
                _avisar_info, master, f"Se importaron {len(ids)} cliente(s) a Z1.", al_terminar
            )

        threading.Thread(target=escribir, daemon=True).start()

    def _avisar_error(master, mensaje, al_terminar):
        messagebox.showerror("Importar desde Z2", mensaje, parent=master)
        if al_terminar:
            al_terminar()

    def _avisar_info(master, mensaje, al_terminar):
        messagebox.showinfo("Importar desde Z2", mensaje, parent=master)
        if al_terminar:
            al_terminar()

    def _mostrar(master, resultado, error, al_terminar):
        """Hilo principal: acá sí se abren ventanas."""
        if error:
            messagebox.showerror("Importar desde Z2", error, parent=master)
            if al_terminar:
                al_terminar()
            return
        ImportarZ2Popup(
            master,
            resultado,
            on_importar=lambda nuevos: _importar_confirmados(master, nuevos, al_terminar),
            on_cerrar=lambda: None,
        )

    def _buscar():
        try:
            resultado = z2_sync.sincronizar(crear=False)
        except z2_sync.IntegracionDesactivada:
            _en_hilo_principal(
                _mostrar,
                master,
                None,
                "La importación desde Z2 no está configurada.\n\n"
                "Va en Configuración → Conexión con Z2 (solo lectura).",
                al_terminar,
            )
            return
        except Exception as exc:  # noqa: BLE001 - la UI no tiene a quién avisarle de esto
            _en_hilo_principal(_mostrar, master, None, f"No se pudo leer Z2.\n\n{exc}", al_terminar)
            return
        _en_hilo_principal(_mostrar, master, resultado, None, al_terminar)

    threading.Thread(target=_buscar, daemon=True).start()
