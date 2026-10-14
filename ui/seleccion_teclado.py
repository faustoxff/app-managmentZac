from tkinter import ttk


def habilitar_shift_flechas(tree: ttk.Treeview) -> None:
    """Shift+↓ / Shift+↑ van agregando filas a la selección, como en Excel o el Explorador.
    El Treeview de Tkinter no lo trae: con Shift+flecha sólo mueve la fila seleccionada.

    La selección va desde la fila "ancla" (donde se empezó) hasta la actual, así que volver
    para atrás con Shift+↑ también achica la selección."""

    estado = {"ancla": None}

    def mover(paso: int):
        filas = tree.get_children()
        if not filas:
            return "break"
        actual = tree.focus() or (tree.selection()[0] if tree.selection() else "")
        if actual not in filas:
            # Primera vez: Shift+↓ arranca en la primera fila, Shift+↑ en la última.
            destino = filas[0] if paso > 0 else filas[-1]
            estado["ancla"] = destino
        else:
            i = filas.index(actual) + paso
            if not 0 <= i < len(filas):
                return "break"
            destino = filas[i]
            # Si la selección cambió por otro lado (clic, flecha sola), se arranca de nuevo
            # desde la fila actual.
            if estado["ancla"] not in tree.selection():
                estado["ancla"] = actual
        a, b = sorted((filas.index(estado["ancla"]), filas.index(destino)))
        tree.selection_set(filas[a : b + 1])
        tree.focus(destino)
        tree.see(destino)
        return "break"

    tree.bind("<Shift-Down>", lambda _e: mover(1))
    tree.bind("<Shift-Up>", lambda _e: mover(-1))
