import threading
import tkinter as tk
from tkinter import messagebox, ttk


class RestaurarBackupPopup(tk.Toplevel):
    """Lista los backups disponibles en Neon y deja restaurar uno, con confirmación (es
    destructivo: pisa la base de datos local)."""

    def __init__(self, master, backups: list[tuple[str, str]], on_restaurado):
        super().__init__(master)
        self.backups = backups
        self.on_restaurado = on_restaurado

        self.title("Restaurar backup")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        tk.Label(
            self,
            text="Elegí qué backup restaurar. Esto reemplaza TODOS los datos locales actuales.",
            wraplength=380,
            justify="left",
            fg="#92620a",
        ).pack(padx=16, pady=(16, 8))

        cols = ("nombre", "fecha")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=min(8, len(backups)))
        self.tree.heading("nombre", text="Backup")
        self.tree.heading("fecha", text="Fecha")
        self.tree.column("nombre", width=220)
        self.tree.column("fecha", width=130)
        for nombre, fecha in backups:
            self.tree.insert("", "end", iid=nombre, values=(nombre, fecha))
        self.tree.pack(padx=16, pady=6)
        if backups:
            self.tree.selection_set(backups[0][0])

        self.estado_label = tk.Label(self, text="", fg="gray30")
        self.estado_label.pack(padx=16, pady=(4, 0))

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=16)
        self.restaurar_btn = tk.Button(
            btn_frame, text="Restaurar este backup", command=self._restaurar, width=18
        )
        self.restaurar_btn.pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=12).pack(side="left", padx=6)

    def _restaurar(self):
        sel = self.tree.selection()
        if not sel:
            return
        nombre = sel[0]
        if not messagebox.askyesno(
            "Confirmar restauración",
            f"¿Restaurar '{nombre}'?\n\nEsto reemplaza TODOS los clientes que tenés cargados "
            "ahora en esta PC por los del backup. No se puede deshacer.",
            parent=self,
        ):
            return

        self.restaurar_btn.config(state="disabled")
        self.estado_label.config(text="Restaurando...")
        threading.Thread(target=self._trabajo_restaurar, args=(nombre,), daemon=True).start()

    def _trabajo_restaurar(self, nombre: str):
        import backup

        try:
            backup.restaurar_backup(nombre)
        except backup.BackupError as exc:
            self.after(0, lambda: self._on_error(str(exc)))
            return
        self.after(0, self._on_ok)

    def _on_ok(self):
        self.destroy()
        self.on_restaurado()

    def _on_error(self, mensaje: str):
        self.restaurar_btn.config(state="normal")
        self.estado_label.config(text="")
        messagebox.showerror("Error al restaurar", mensaje, parent=self)
