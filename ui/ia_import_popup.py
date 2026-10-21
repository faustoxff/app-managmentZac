import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from ui.api_key_popup import ApiKeyPopup
from ui import tema


PAUSA_ENTRE_FOTOS = 6.5  # segundos


class IAImportPopup(tk.Toplevel):
    """Selector de imagen + instrucción tipo chat para importar con IA (Gemini u OpenRouter, según Configurar IA).
    La llamada a la API corre en un hilo aparte para no congelar la ventana; el resultado
    vuelve al hilo principal con self.after(), nunca se toca la UI desde el hilo de red."""

    def __init__(self, master, on_resultado):
        super().__init__(master)
        self.on_resultado = on_resultado
        self.paths: list[str] = []
        self._cancelado = threading.Event()  # el hilo de fondo lo mira para frenar al cerrar

        self.title("Importar con IA")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        sel_frame = tk.Frame(self)
        sel_frame.pack(padx=16, pady=(16, 8), fill="x")
        tk.Button(sel_frame, text="Seleccionar imágenes...", command=self._seleccionar_imagen).pack(
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
        self.enviar_btn = tema.primario(tk.Button(btn_frame, text="Enviar", command=self._enviar, width=14))
        self.enviar_btn.pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancelar", command=self.destroy, width=14).pack(side="left", padx=6)

    def destroy(self):
        # Cerrar el popup (Cancelar o la X) corta el lote: sin esto el hilo seguía pidiendo
        # fotos a la IA hasta terminar, gastando cuota para nada.
        self._cancelado.set()
        super().destroy()

    def _agendar(self, callback):
        """self.after(0, callback) desde el hilo de fondo, sin reventar si el popup ya se cerró."""
        try:
            self.after(0, callback)
        except (RuntimeError, tk.TclError):
            pass

    def _seleccionar_imagen(self):
        paths = filedialog.askopenfilenames(
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp"), ("Todos los archivos", "*.*")],
            parent=self,
        )
        if paths:
            self.paths = list(paths)
            self.archivo_label.config(
                text=Path(paths[0]).name if len(paths) == 1 else f"{len(paths)} imágenes"
            )

    def _set_cargando(self, cargando: bool, texto: str = ""):
        self.enviar_btn.config(state="disabled" if cargando else "normal")
        self.estado_label.config(text=texto)

    def _enviar(self):
        if not self.paths:
            messagebox.showwarning("Falta la imagen", "Elegí al menos una imagen.", parent=self)
            return

        instruccion = self.texto.get("1.0", "end").strip()
        self._set_cargando(True, "Consultando IA... (puede tardar unos segundos)")
        threading.Thread(target=self._trabajo, args=(list(self.paths), instruccion), daemon=True).start()

    def _trabajo(self, paths: list[str], instruccion: str):
        import ia_import

        candidatos = []
        fallidas = []  # (nombre de la foto, motivo): una foto que falla no tira abajo el lote
        for i, path in enumerate(paths, start=1):
            if i > 1:
                # La capa gratis de Gemini admite ~10 pedidos por minuto: espaciarlos
                # evita el error 429 al mandar varias fotos seguidas.
                if self._cancelado.wait(PAUSA_ENTRE_FOTOS):
                    return
            if self._cancelado.is_set():
                return
            if len(paths) > 1:
                texto = f"Leyendo foto {i} de {len(paths)}..."
                self._agendar(lambda t=texto: self._mostrar_progreso(t))
            try:
                candidatos.extend(ia_import.extraer_candidatos(path, instruccion))
            except ia_import.FaltaApiKey:
                self._agendar(self._pedir_api_key)
                return
            except ia_import.IAImportError as exc:
                fallidas.append((Path(path).name, str(exc)))
            except Exception as exc:  # noqa: BLE001 - no crashear ante nada inesperado del SDK
                fallidas.append((Path(path).name, f"Error inesperado: {exc}"))

        if self._cancelado.is_set():
            return
        if not candidatos and fallidas:
            # Nada se pudo leer: mostramos el error de la primera foto (suele ser el mismo
            # para todas: key inválida, límite de uso, etc.).
            mensaje = fallidas[0][1]
            self._agendar(lambda: self._on_error(mensaje))
            return
        self._agendar(lambda: self._on_exito(candidatos, fallidas))

    def _mostrar_progreso(self, texto: str):
        if self.winfo_exists():
            self.estado_label.config(text=texto)

    def _pedir_api_key(self):
        self._set_cargando(False)
        ApiKeyPopup(self, on_guardada=self._enviar)  # al guardar, reintenta el envío solo

    def _on_error(self, mensaje: str):
        self._set_cargando(False)
        messagebox.showerror("Error al importar con IA", mensaje, parent=self)

    def _on_exito(self, candidatos, fallidas=()):
        if fallidas:
            detalle = "\n".join(f"- {nombre}: {motivo.splitlines()[0]}" for nombre, motivo in fallidas)
            messagebox.showwarning(
                "Algunas fotos no se pudieron leer",
                f"Se leyeron las demás, pero estas fallaron:\n\n{detalle}\n\n"
                "Podés volver a importar solo esas más tarde.",
                parent=self,
            )
        self.destroy()
        self.on_resultado(candidatos)
