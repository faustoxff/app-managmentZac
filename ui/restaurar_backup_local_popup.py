import tkinter as tk
from tkinter import messagebox, ttk

import db


class RestaurarBackupLocalPopup(tk.Toplevel):
    """Backups automáticos y LOCALES (no dependen de internet ni de Neon) — se toma uno cada
    vez que arranca la app, antes de tocar nada de la base de datos. Sirve como red de
    seguridad ante cualquier cambio masivo inesperado: no hace falta cargar a mano de nuevo
    cientos de clientes, alcanza con volver a un backup de un arranque anterior."""

    def __init__(self, master, on_restaurado):
        super().__init__(master)
        self.on_restaurado = on_restaurado

        self.title("Restaurar backup local")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        backups = db.listar_backups_locales()

        tk.Label(
            self,
            text="Copias automáticas tomadas en cada arranque de la app, antes de tocar la "
            "base de datos. Elegí una fecha para volver a ese estado — reemplaza TODOS los "
            "datos actuales.",
            wraplength=380,
            justify="left",
            fg="#92620a",
        ).pack(padx=16, pady=(16, 8))

        if not backups:
            tk.Label(self, text="Todavía no hay ningún backup local disponible.").pack(padx=16, pady=8)
            tk.Button(self, text="Cerrar", command=self.destroy, width=12).pack(pady=(0, 16))
            return

        cols = ("fecha",)
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=min(10, len(backups)))
        self.tree.heading("fecha", text="Fecha")
        self.tree.column("fecha", width=220)
        for nombre, fecha in backups:
            self.tree.insert("", "end", iid=nombre, values=(fecha,))
        self.tree.pack(padx=16, pady=6)
        self.tree.selection_set(backups[0][0])

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=16)
        tk.Button(btn_frame, text="Restaurar esta fecha", command=self._restaurar, width=18).pack(
            side="left", padx=6
        )
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=12).pack(side="left", padx=6)

    def _restaurar(self):
        sel = self.tree.selection()
        if not sel:
            return
        nombre = sel[0]
        if not messagebox.askyesno(
            "Confirmar restauración",
            "¿Restaurar este backup local?\n\nEsto reemplaza TODOS los clientes que tenés "
            "cargados ahora por los de ese momento. No se puede deshacer.",
            parent=self,
        ):
            return
        try:
            db.restaurar_backup_local(nombre)
        except OSError as exc:
            messagebox.showerror("Error al restaurar", str(exc), parent=self)
            return
        self.destroy()
        self.on_restaurado()
