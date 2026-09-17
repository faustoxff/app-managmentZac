import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from ui.api_key_popup import ApiKeyPopup


class IAImportPopup(tk.Toplevel):
    """Selector de imagen + instrucción tipo chat para importar con IA (vía OpenRouter).
    La llamada a la API corre en un hilo aparte para no congelar la ventana; el resultado
    vuelve al hilo principal con self.after(), nunca se toca la UI desde el hilo de red."""

    def __init__(self, master, on_resultado):
        super().__init__(master)
        self.on_resultado = on_resultado
        self.path_imagen: str | None = None

        self.title("Importar con IA")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        sel_frame = tk.Frame(self)
        sel_frame.pack(padx=16, pady=(16, 8), fill="x")
        tk.Button(sel_frame, text="Seleccionar imagen...", command=self._seleccionar_imagen).pack(
            side="left"
        )
        self.archivo_label = tk.Label(sel_frame, text="(ningún archivo)", fg="gray30")
        self.archivo_label.pack(side="left", padx=10)

        tk.Label(self, text="Instrucción para la IA:", anchor="w").pack(
            padx=16, pady=(8, 2), fill="x"
        )

        import ia_import

        self.texto = tk.Text(self, width=52, height=5, wrap="word")
        self.texto.insert("1.0", ia_import.INSTRUCCION_DEFAULT)
        self.texto.pack(padx=16, pady=(0, 8))

        self.estado_label = tk.Label(self, text="", fg="gray30")
        self.estado_label.pack(padx=16, anchor="w")

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(8, 16))
        self.enviar_btn = tk.Button(btn_frame, text="Enviar", command=self._enviar, width=14)
        self.enviar_btn.pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=14).pack(side="left", padx=6)

    def _seleccionar_imagen(self):
        path = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp"), ("Todos los archivos", "*.*")],
            parent=self,
        )
        if path:
            self.path_imagen = path
            self.archivo_label.config(text=path.split("/")[-1])

    def _set_cargando(self, cargando: bool, texto: str = ""):
        self.enviar_btn.config(state="disabled" if cargando else "normal")
        self.estado_label.config(text=texto)

    def _enviar(self):
        if not self.path_imagen:
            messagebox.showwarning("Falta la imagen", "Elegí una imagen primero.", parent=self)
            return

        instruccion = self.texto.get("1.0", "end").strip()
        self._set_cargando(True, "Consultando IA... (puede tardar unos segundos)")
        threading.Thread(target=self._trabajo, args=(self.path_imagen, instruccion), daemon=True).start()

    def _trabajo(self, path: str, instruccion: str):
        import ia_import

        try:
            candidatos = ia_import.extraer_candidatos(path, instruccion)
        except ia_import.FaltaApiKey:
            self.after(0, self._pedir_api_key)
            return
        except ia_import.IAImportError as exc:
            self.after(0, lambda: self._on_error(str(exc)))
            return
        except Exception as exc:  # noqa: BLE001 - no crashear ante nada inesperado del SDK
            self.after(0, lambda: self._on_error(f"Error inesperado: {exc}"))
            return

        self.after(0, lambda: self._on_exito(candidatos))

    def _pedir_api_key(self):
        self._set_cargando(False)
        ApiKeyPopup(self, on_guardada=self._enviar)  # al guardar, reintenta el envío solo

    def _on_error(self, mensaje: str):
        self._set_cargando(False)
        messagebox.showerror("Error al importar con IA", mensaje, parent=self)

    def _on_exito(self, candidatos):
        self.destroy()
        self.on_resultado(candidatos)
