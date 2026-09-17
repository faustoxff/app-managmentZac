import tkinter as tk

from PIL import ImageTk


class SubidaCelularPopup(tk.Toplevel):
    """Muestra el QR y la URL para subir una foto desde el celular. Cerrar esta ventana (X)
    NO apaga el servidor — solo el botón "Desactivar" lo hace, así el usuario puede cerrar el
    QR y seguir sacando/subiendo fotos sin tener que dejarlo abierto en pantalla."""

    def __init__(self, master, ip: str, puerto: int, on_desactivar):
        super().__init__(master)
        self.on_desactivar = on_desactivar

        self.title("Subir foto desde el celular")
        self.resizable(False, False)
        self.transient(master)

        url = f"http://{ip}:{puerto}"

        tk.Label(
            self,
            text="Escaneá este código con la cámara del celular\n(tiene que estar en el mismo WiFi):",
            justify="center",
        ).pack(padx=16, pady=(16, 8))

        import qrcode

        qr_img = qrcode.make(url).resize((260, 260))
        self._qr_photo = ImageTk.PhotoImage(qr_img)  # referencia guardada para que no se pierda por GC
        tk.Label(self, image=self._qr_photo).pack(padx=16, pady=8)

        url_var = tk.StringVar(value=url)
        entry = tk.Entry(self, textvariable=url_var, justify="center", state="readonly", width=30)
        entry.pack(padx=16, pady=(0, 4))
        tk.Label(self, text="(o escribí esa dirección en el navegador del celular a mano)", fg="gray30").pack(
            padx=16, pady=(0, 12)
        )

        tk.Button(self, text="Desactivar", command=self._desactivar, width=16).pack(pady=(0, 16))

    def _desactivar(self):
        self.destroy()
        self.on_desactivar()
