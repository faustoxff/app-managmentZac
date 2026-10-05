"""Panel lateral NO modal que va mostrando coincidencias mientras se tipea un cliente nuevo.

Es deliberadamente una Toplevel sin `grab_set()` (a diferencia de DuplicadoPopup, que sí
frena): el panel tiene que poder actualizarse en cada tecla sin robarle el foco al Entry ni
bloquear el formulario. Solo informa; el pedido de confirmación sigue siendo el popup modal
de DuplicadoPopup al apretar Guardar.

Se posiciona al costado de la ventana del formulario y se oculta solo (withdraw) cuando no
queda ninguna coincidencia, así no ocupa pantalla en el caso normal.
"""
import tkinter as tk
from tkinter import ttk

from models import Cliente

# Margen en px entre el borde derecho del formulario y este panel.
GAP_PX = 10
# Margen contra los bordes de la pantalla, para que el panel nunca quede medio fuera.
MARGEN_PANTALLA_PX = 10
# Alto máximo en filas: si alguien tiene 40 coincidencias no tiene sentido abrir una ventana
# de 40 filas al lado del formulario (taparía el resto de la app); se muestran las primeras
# y el rótulo de abajo aclara cuántas hay en total.
MAX_FILAS_VISIBLES = 6


class PanelDuplicados(tk.Toplevel):
    """Muestra los clientes que coinciden con lo que se está tipeando. `motivo()` decide si
    cada fila apareció por teléfono exacto o por nombre parecido, para que el aviso sea
    accionable y no un "hay coincidencias" genérico."""

    def __init__(self, master, on_ver_existente=None):
        super().__init__(master)
        self.on_ver_existente = on_ver_existente
        self._coincidencias: list[Cliente] = []
        self._nombre_consulta = ""
        self._contacto_consulta = ""

        self.title("Posibles coincidencias")
        self.resizable(False, False)
        self.transient(master)  # se minimiza junto con el formulario, no queda huérfana
        # Sin grab_set() a propósito: nada de esto puede bloquear la escritura en el
        # formulario. Tampoco focus_force() — el foco tiene que quedarse en el Entry.

        header = tk.Frame(self)
        header.pack(padx=10, pady=(10, 4), anchor="w")
        self.titulo_label = tk.Label(
            header, text="Posibles coincidencias", font=("", 10, "bold"), anchor="w"
        )
        self.titulo_label.pack(side="left")
        self.subtitulo_label = tk.Label(header, text="", fg="#92620a", anchor="w")
        self.subtitulo_label.pack(side="left", padx=(6, 0))

        # Solo nombre y teléfono: es lo único que hace falta para reconocer al cliente de un
        # vistazo. El estado no suma acá (no estás decidiendo un cambio de estado, solo
        # "¡uh, este señor ya está cargado!") y el motivo de la coincidencia ya se dice en el
        # subtítulo de arriba, que no obliga a leer una columna más.
        #
        # "origen" sí hace falta: desde que existe la integración con Z2, la misma pantalla
        # puede mezclar clientes de esta base con carpetas del otro programa, y un cliente que
        # está en los dos aparece dos veces. Sin esta columna el padre ve al mismo señor listado
        # dos veces sin poder saber de dónde salió cada uno, que es justo lo que el panel
        # existe para evitar.
        cols = ("origen", "nombre", "contacto")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=MAX_FILAS_VISIBLES)
        for c, label, ancho in [
            ("origen", "Origen", 60),
            ("nombre", "Nombre", 190),
            ("contacto", "Teléfono", 130),
        ]:
            self.tree.heading(c, text=label)
            self.tree.column(c, width=ancho)
        self.tree.pack(padx=10, pady=4)
        self.tree.bind("<Double-1>", self._ver_existente)
        # Un ENTER con una fila seleccionada hace lo mismo que el doble clic.
        self.tree.bind("<Return>", self._ver_existente)

        self.pie_label = tk.Label(self, text="", fg="gray30", anchor="w", justify="left")
        self.pie_label.pack(padx=10, pady=(0, 8), anchor="w")

        self.withdraw()  # arranca oculto: sin coincidencias no hay panel

    # ---------- actualización ----------

    def actualizar(self, coincidencias: list[Cliente], nombre: str, contacto: str) -> None:
        """Refresca el contenido con las coincidencias actuales. Con lista vacía se oculta
        solo. Se puede llamar en cada tecla: es barato (no toca la DB, solo repinta)."""
        self._coincidencias = coincidencias
        self._nombre_consulta = normalizar_para_comparar(nombre)
        self._contacto_consulta = normalizar_contacto(contacto)

        if not coincidencias:
            self.ocultar()
            return

        self.tree.delete(*self.tree.get_children())
        for c in coincidencias[:MAX_FILAS_VISIBLES]:
            self.tree.insert(
                "",
                "end",
                iid=iid_de(c),
                values=(etiqueta_origen(c.origen), c.nombre, c.contacto),
            )
        if coincidencias:
            self.tree.selection_set(iid_de(coincidencias[0]))

        exactas = sum(1 for c in coincidencias if self._motivo(c) == "teléfono")
        remotas = sum(1 for c in coincidencias if c.origen == "z2")
        partes = []
        if exactas:
            # Un teléfono igual es el caso fuerte: se dice explícitamente.
            partes.append(f"{exactas} por teléfono")
        else:
            partes.append("solo por nombre")
        if remotas:
            partes.append(f"{remotas} de Z2")
        texto = f"({' — '.join(partes)})"
        self.subtitulo_label.config(
            text=texto, fg="#b91c1c" if exactas else "#92620a"
        )

        # Las coincidencias de Z2 traen un texto extra (ART, estado, prioridad) que no cabe en
        # una columna más sin ensanchar el panel; va en el pie, que se lee sin clicking nada.
        detalle = next((c.detalle for c in coincidencias if c.origen == "z2" and c.detalle), "")

        lineas = []
        if detalle:
            lineas.append(f"En Z2: {detalle}")
        if len(coincidencias) > MAX_FILAS_VISIBLES:
            lineas.append(
                f"Mostrando {MAX_FILAS_VISIBLES} de {len(coincidencias)} — "
                "se guardan igual si confirmás."
            )
        if any(c.origen == "local" for c in coincidencias):
            lineas.append("Doble clic para ver el cliente existente.")
        self.pie_label.config(text="\n".join(lineas))

        self._reubicar()
        self.deiconify()
        # update_idletasks antes de pedir la geometría: recién_desde packing todavía no
        # calculó el tamaño real, y sin esto el panel se posicionaría con alto 0.
        self.update_idletasks()
        self._reubicar()

    def ocultar(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._coincidencias = []
        if self.winfo_ismapped():
            self.withdraw()

    def _motivo(self, c: Cliente) -> str:
        """Por qué apareció esta fila: teléfono idéntico (conclusión firme) o solo nombre
        parecidos. Se calcula con la misma normalización que usa la búsqueda, así el rótulo
        no puede contradecir por qué la fila salió en los resultados."""
        if self._contacto_consulta and normalizar_contacto(c.contacto) == self._contacto_consulta:
            return "teléfono"
        return "nombre"

    def _ver_existente(self, _event=None):
        """Doble clic / Enter sobre una fila.

        Solo tiene sentido para las locales: abrir un Cliente de Z2 con este popup llamaría a
        buscar/editar en la base LOCAL con un id que no existe acá (y que además es un uuid, no
        el entero que espera db.py). Las de Z2 muestran su detalle en la fila de abajo."""
        sel = self.tree.selection()
        if not sel or not self.on_ver_existente:
            return
        iid = sel[0]
        origen, _, cliente_id = iid.partition(":")
        if origen != "local":
            return
        elegido = next(
            (c for c in self._coincidencias if c.origen == "local" and str(c.id) == cliente_id),
            None,
        )
        if elegido is not None:
            self.on_ver_existente(elegido)

    def _reubicar(self) -> None:
        """Se ancla al costado derecho del formulario, alineado con su borde superior, y se
        corrige si no entra en la pantalla (formulario pegado al borde derecho)."""
        try:
            x = self.master.winfo_rootx() + self.master.winfo_width() + GAP_PX
            y = self.master.winfo_rooty()
        except tk.TclError:  # el formulario se cerró mientras se calculaba
            return
        ancho = self.winfo_width()
        alto = self.winfo_height()
        if not ancho or not alto:  # geometría todavía sin calcular
            return

        max_x = self.winfo_screenwidth() - ancho - MARGEN_PANTALLA_PX
        max_y = self.winfo_screenheight() - alto - MARGEN_PANTALLA_PX
        x = min(x, max_x)
        y = min(y, max_y)
        self.geometry(f"+{max(x, MARGEN_PANTALLA_PX)}+{max(y, MARGEN_PANTALLA_PX)}")


def iid_de(c: Cliente) -> str:
    """Identificador de fila en el Treeview.

    Tiene que ser único sí o sí: Treeview lanza TclError si se inserta un iid repetido, así
    que no alcanza con el id de la base. Se arma con el origen adelante y el id de LA BASE DE
    ORIGEN: los locales usan `id` (un entero de esta base) y los de Z2 usan `id_remoto` (el
    uuid de la carpeta), porque no son el mismo tipo de dato ni del mismo espacio de ids.
    """
    return f"{c.origen}:{c.id if c.origen == 'local' else c.id_remoto}"


def etiqueta_origen(origen: str) -> str:
    """Texto de la columna Origen. 'Z2' es corto a propósito: la columna tiene 60px y la idea
    es que se lea de reojo, no que ocupe el lugar del nombre."""
    return "Z2" if origen == "z2" else "Local"


def normalizar_contacto(contacto: str) -> str:
    """Espejo de db.normalizar_telefono(), pero local para que este módulo se pueda importar
    (y testear) sin tocar la base."""
    if not contacto:
        return ""
    for ch in (" ", "-", "(", ")"):
        contacto = contacto.replace(ch, "")
    return contacto.strip()


def normalizar_para_comparar(texto: str) -> str:
    """Espejo de db.normalizar_nombre() (mayúsculas, sin diacríticos) para el rótulo de
    motivo. Se mantiene acá en vez de importar de db para no crear una dependencia del panel
    hacia el acceso a datos: el panel solo presentation."""
    import unicodedata

    if not texto:
        return ""
    s = unicodedata.normalize("NFKD", texto.strip().upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())
