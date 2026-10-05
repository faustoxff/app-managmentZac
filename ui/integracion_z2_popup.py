import threading
import tkinter as tk
from tkinter import messagebox

import config


class IntegracionZ2Popup(tk.Toplevel):
    """Configura la conexión con Z2 (Gestor de Carpetas ART) para que el alta de clientes
    avise si esa persona ya existe como carpeta del otro programa.

    La URL y el token se guardan en el config.json de Z1, no en el repo: son credenciales de
    una base que vive en la nube.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Integración con Z2")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        info = (
            "Al cargar un cliente nuevo, Z1 consulta a Z2 para avisarte si esa persona ya "
            "tiene una carpeta en el otro programa. Z1 solo lee: nunca escribe ni borra nada "
            "de Z2.\n\n"
            "La URL es la base donde está Z2 (por ejemplo https://mi-z2.onrender.com) y el "
            "token es el INTEGRATION_TOKEN del archivo .env de Z2. Si lo dejás vacío, la "
            "integración queda apagada y Z1 funciona exactamente como antes."
        )
        tk.Label(self, text=info, wraplength=420, justify="left").pack(padx=16, pady=(16, 12))

        tk.Label(self, text="URL de Z2", anchor="w").pack(padx=16, fill="x")
        self.url_var = tk.StringVar(value=config.obtener_z2_url())
        tk.Entry(self, textvariable=self.url_var, width=52).pack(padx=16, pady=(0, 10))

        tk.Label(self, text="Token de integración", anchor="w").pack(padx=16, fill="x")
        self.token_var = tk.StringVar(value=config.obtener_z2_token())
        tk.Entry(self, textvariable=self.token_var, show="•", width=52).pack(
            padx=16, pady=(0, 10)
        )

        tk.Label(
            self,
            text="Conexión de solo lectura a la base de Z2 (para la Pestaña Z2 → Sincronizar con Z2)",
            anchor="w", wraplength=420, justify="left",
        ).pack(padx=16, fill="x")
        self.read_url_var = tk.StringVar(value=config.obtener_z2_read_url())
        tk.Entry(self, textvariable=self.read_url_var, show="•", width=52).pack(
            padx=16, pady=(0, 10)
        )

        self.estado_label = tk.Label(self, text="", fg="gray30", wraplength=420, justify="left")
        self.estado_label.pack(padx=16, pady=(4, 0), anchor="w")

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=16)
        tk.Button(btn_frame, text="Guardar", command=self._guardar, width=12).pack(
            side="left", padx=4
        )
        self.probar_btn = tk.Button(
            btn_frame, text="Probar conexión", command=self._probar, width=15
        )
        self.probar_btn.pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cerrar", command=self.destroy, width=10).pack(
            side="left", padx=4
        )

    def _guardar_config(self):
        config.guardar_z2_url(self.url_var.get())
        config.guardar_z2_token(self.token_var.get())
        config.guardar_z2_read_url(self.read_url_var.get())

    def _guardar(self):
        self._guardar_config()
        if not self.url_var.get().strip() or not self.token_var.get().strip():
            messagebox.showinfo(
                "Guardado",
                "Configuración guardada. Con la URL o el token vacío la integración queda "
                "apagada.",
                parent=self,
            )
        else:
            messagebox.showinfo("Guardado", "Integración con Z2 configurada.", parent=self)

    def _probar(self):
        self._guardar_config()
        self.probar_btn.config(state="disabled")
        self.estado_label.config(text="Conectando con Z2...", fg="gray30")
        # La prueba sí va en un hilo: si Z2 está caído o sin internet, urlopen se queda
        # esperando al timeout y sin esto la ventana queda congelada sin explicación.
        threading.Thread(target=self._trabajo_probar, daemon=True).start()

    def _trabajo_probar(self):
        import integracion_z2

        try:
            ok, mensaje = integracion_z2.probar_conexion()
        except integracion_z2.IntegracionNoConfigurada:
            ok, mensaje = False, "Falta la URL o el token."
        # El mensaje se copia a una variable antes del after: Python borra `exc` al salir del
        # except, y la lambda diferida reventaría con NameError (mismo motivo que en
        # backup_popup).
        self.after(0, lambda: self._on_resultado(ok, mensaje))

    def _on_resultado(self, ok: bool, mensaje: str):
        self.probar_btn.config(state="normal")
        self.estado_label.config(text=mensaje, fg="#15803d" if ok else "#b91c1c")
