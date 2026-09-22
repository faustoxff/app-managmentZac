import tkinter as tk
from tkinter import messagebox

import db
from ui.app import App


def main():
    try:
        db.init_db()
    except Exception as exc:  # noqa: BLE001 - una DB corrupta/bloqueada no debe crashear con
        # un traceback crudo al arrancar: en este punto todavía no existe ninguna ventana de
        # Tkinter, así que armamos una mínima solo para poder mostrar el messagebox.
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Error al iniciar",
            f"No se pudo abrir la base de datos:\n{exc}",
        )
        root.destroy()
        return

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
