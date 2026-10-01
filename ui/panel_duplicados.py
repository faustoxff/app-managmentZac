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
        cols = ("nombre", "contacto")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=MAX_FILAS_VISIBLES)
        for c, label, ancho in [
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
            self.tree.insert("", "end", iid=str(c.id), values=(c.nombre, c.contacto))
        if coincidencias:
            self.tree.selection_set(str(coincidencias[0].id))

        exactas = sum(1 for c in coincidencias if self._motivo(c) == "teléfono")
        if exactas:
            # Un teléfono igual es el caso fuerte: se dice explícitamente.
            self.subtitulo_label.config(text=f"({exactas} por teléfono)", fg="#b91c1c")
        else:
            self.subtitulo_label.config(text="(solo por nombre)", fg="#92620a")

        if len(coincidencias) > MAX_FILAS_VISIBLES:
            self.pie_label.config(
                text=f"Mostrando {MAX_FILAS_VISIBLES} de {len(coincidencias)} — "
                "se guardan igual si confirmás.\nDoble clic para ver el cliente existente."
            )
        else:
            self.pie_label.config(text="Doble clic para ver el cliente existente.")

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
        sel = self.tree.selection()
        if not sel or not self.on_ver_existente:
            return
        cliente_id = int(sel[0])
        elegido = next((c for c in self._coincidencias if c.id == cliente_id), None)
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
