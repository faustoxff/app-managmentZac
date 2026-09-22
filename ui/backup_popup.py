import threading
import tkinter as tk
from tkinter import messagebox

import config


class BackupPopup(tk.Toplevel):
    """Configura la conexión a Neon y deja hacer backup / restaurar el archivo completo de la
    base de datos. Las operaciones de red corren en un hilo aparte para no congelar la
    ventana."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Backup en la nube (Neon)")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        info = (
            "Sube una copia completa de la base de datos a Neon (Postgres en la nube) como "
            "red de seguridad si se rompe la PC. La cadena de conexión se consigue en el "
            "panel de Neon → Connect."
        )
        tk.Label(self, text=info, wraplength=400, justify="left").pack(padx=16, pady=(16, 10))

        tk.Label(self, text="Cadena de conexión de Neon", anchor="w").pack(padx=16, fill="x")
        self.cs_var = tk.StringVar(value=config.obtener_neon_connection_string())
        tk.Entry(self, textvariable=self.cs_var, show="•", width=48).pack(padx=16, pady=(0, 10))

        self.automatico_var = tk.BooleanVar(value=config.obtener_backup_automatico())
        tk.Checkbutton(
            self,
            text="Hacer backup automático cada vez que se cierra el programa",
            variable=self.automatico_var,
        ).pack(padx=16, anchor="w")

        self.estado_label = tk.Label(self, text="", fg="gray30")
        self.estado_label.pack(padx=16, pady=(10, 0), anchor="w")

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=16)
        tk.Button(btn_frame, text="Guardar", command=self._guardar, width=12).pack(side="left", padx=4)
        self.backup_btn = tk.Button(
            btn_frame, text="Backup ahora", command=self._backup_ahora, width=13
        )
        self.backup_btn.pack(side="left", padx=4)
        self.restaurar_btn = tk.Button(
            btn_frame, text="Restaurar...", command=self._abrir_restaurar, width=12
        )
        self.restaurar_btn.pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cerrar", command=self.destroy, width=10).pack(side="left", padx=4)

    def _guardar_config(self):
        config.guardar_neon_connection_string(self.cs_var.get())
        config.guardar_backup_automatico(self.automatico_var.get())

    def _guardar(self):
        self._guardar_config()
        messagebox.showinfo("Guardado", "Configuración de backup guardada.", parent=self)

    def _set_cargando(self, cargando: bool, texto: str = ""):
        estado = "disabled" if cargando else "normal"
        self.backup_btn.config(state=estado)
        self.restaurar_btn.config(state=estado)
        self.estado_label.config(text=texto)

    def _backup_ahora(self):
        self._guardar_config()
        self._set_cargando(True, "Subiendo backup a Neon...")
        threading.Thread(target=self._trabajo_backup, daemon=True).start()

    def _trabajo_backup(self):
        import backup

        try:
            nombre = backup.hacer_backup_ahora()
        except backup.BackupError as exc:
            # Python borra `exc` al salir del except — self.after difiere la lambda, así que
            # hay que copiar el texto a una variable normal antes o explota con NameError.
            mensaje = str(exc)
            self.after(0, lambda: self._on_error(mensaje))
            return
        self.after(0, lambda: self._on_backup_ok(nombre))

    def _on_backup_ok(self, nombre: str):
        self._set_cargando(False)
        messagebox.showinfo("Backup listo", f"Se subió a Neon: {nombre}", parent=self)

    def _on_error(self, mensaje: str):
        self._set_cargando(False)
        messagebox.showerror("Error", mensaje, parent=self)

    def _abrir_restaurar(self):
        self._guardar_config()
        self._set_cargando(True, "Consultando backups disponibles...")
        threading.Thread(target=self._trabajo_listar, daemon=True).start()

    def _trabajo_listar(self):
        import backup

        try:
            backups = backup.listar_backups()
        except backup.BackupError as exc:
            mensaje = str(exc)
            self.after(0, lambda: self._on_error(mensaje))
            return
        self.after(0, lambda: self._on_listado_ok(backups))

    def _on_listado_ok(self, backups: list[tuple[str, str]]):
        self._set_cargando(False)
        if not backups:
            messagebox.showinfo("Sin backups", "Todavía no hay ningún backup en Neon.", parent=self)
            return
        from ui.restaurar_backup_popup import RestaurarBackupPopup

        RestaurarBackupPopup(self, backups, on_restaurado=self._on_restaurado)

    def _on_restaurado(self):
        messagebox.showinfo(
            "Restaurado",
            "Base de datos restaurada. Cerrá y volvé a abrir el programa para ver los cambios.",
            parent=self,
        )
