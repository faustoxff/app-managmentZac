import threading
import tkinter as tk
from tkinter import messagebox, ttk

import version


class ActualizacionPopup(tk.Toplevel):
    """Busca actualizaciones al abrirse (en un hilo aparte, no bloquea la ventana). Si hay una
    nueva, deja elegir "Actualizar ahora" (descarga con barra de progreso y reemplaza el .exe)
    o "Más tarde" (cierra sin hacer nada)."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Buscar actualización")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.estado_label = tk.Label(self, text="Buscando actualizaciones...", wraplength=320)
        self.estado_label.pack(padx=20, pady=20)

        self.progreso = ttk.Progressbar(self, length=280, mode="determinate")
        self.actualizar_btn = tk.Button(self, text="Actualizar ahora", command=self._actualizar_ahora)
        self.btn_frame = tk.Frame(self)
        self.cerrar_btn = tk.Button(self.btn_frame, text="Más tarde", command=self.destroy, width=12)

        self._actualizacion = None
        threading.Thread(target=self._trabajo_buscar, daemon=True).start()

    def _trabajo_buscar(self):
        import updater

        try:
            actualizacion = updater.verificar_actualizacion()
        except updater.NoSePudoComprobar:
            self.after(0, self._on_busqueda_fallo)
            return
        except Exception:  # noqa: BLE001 - cualquier otra falla no debe dejar el popup
            # trabado para siempre en "Buscando actualizaciones..." sin avisar nada.
            self.after(0, self._on_busqueda_fallo)
            return
        self.after(0, lambda: self._on_busqueda_lista(actualizacion))

    def _on_busqueda_fallo(self):
        if not self.winfo_exists():
            return  # el popup se cerró mientras el hilo de fondo todavía buscaba
        self.estado_label.config(
            text="No se pudo comprobar si hay una actualización.\n"
            "Revisá tu conexión a internet e intentá de nuevo más tarde."
        )
        tk.Button(self, text="Cerrar", command=self.destroy, width=12).pack(pady=(0, 16))

    def _on_busqueda_lista(self, actualizacion):
        if actualizacion is None:
            self.estado_label.config(
                text=f"Ya tenés la última versión instalada (v{version.__version__})."
            )
            tk.Button(self, text="Cerrar", command=self.destroy, width=12).pack(pady=(0, 16))
            return

        self._actualizacion = actualizacion
        self.estado_label.config(
            text=f"Hay una versión nueva disponible: {actualizacion.version_nueva}\n"
            f"(la actual es v{version.__version__})"
        )
        self.actualizar_btn.pack(pady=(0, 8))
        self.btn_frame.pack(pady=(0, 16))
        self.cerrar_btn.pack()

    def _actualizar_ahora(self):
        if not messagebox.askyesno(
            "Confirmar actualización",
            "La app se va a cerrar para instalar la actualización y se va a volver a abrir "
            "sola. ¿Continuar?",
            parent=self,
        ):
            return

        self.actualizar_btn.config(state="disabled")
        self.cerrar_btn.config(state="disabled")
        self.estado_label.config(text="Descargando actualización...")
        self.progreso.pack(padx=20, pady=(0, 16))
        threading.Thread(target=self._trabajo_descargar, daemon=True).start()

    def _trabajo_descargar(self):
        import updater

        def on_progreso(descargado, total):
            if total:
                porcentaje = int(descargado / total * 100)
                self.after(0, lambda: self.progreso.config(value=porcentaje))

        try:
            destino = updater.descargar_actualizacion(
                self._actualizacion.url_descarga, self._actualizacion.tamano, on_progreso
            )
            updater.aplicar_actualizacion(destino)
            # aplicar_actualizacion() llama os._exit() si todo salió bien — si volvemos acá fue
            # porque no estamos empaquetados (RuntimeError, capturada abajo junto con
            # cualquier otra falla de la descarga o el reemplazo).
        except Exception as exc:  # noqa: BLE001 - cualquier falla acá (red, disco lleno,
            # permisos, lo que sea) tiene que mostrarse, nunca dejar la barra de progreso
            # trabada para siempre sin explicación.
            mensaje = str(exc)  # Python borra `exc` al salir del except — hay que copiar el
            # texto a una variable normal antes de que la lambda difierida (self.after) lo use.
            self.after(0, lambda: self._on_error(mensaje))

    def _on_error(self, mensaje: str):
        if not self.winfo_exists():
            return  # el popup se cerró mientras el hilo de fondo todavía descargaba
        self.actualizar_btn.config(state="normal")
        self.cerrar_btn.config(state="normal")
        self.progreso.pack_forget()
        self.estado_label.config(text="Error al actualizar.")
        messagebox.showerror("Error al actualizar", mensaje, parent=self)
