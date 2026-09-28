import calendar
from datetime import date
import tkinter as tk

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
DIAS = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]


class CalendarioPopup(tk.Toplevel):
    """Selector de fecha simple, en Tkinter puro (sin librerías externas): un mes a la vez,
    con flechas para navegar. Al elegir un día llama on_elegir("AAAA-MM-DD") y se cierra."""

    def __init__(self, master, on_elegir, fecha_inicial: str = ""):
        super().__init__(master)
        self.on_elegir = on_elegir
        self.title("Elegir fecha")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        try:
            inicial = date.fromisoformat(fecha_inicial) if fecha_inicial else date.today()
        except ValueError:
            inicial = date.today()
        self.anio, self.mes = inicial.year, inicial.month

        header = tk.Frame(self)
        header.pack(padx=10, pady=(10, 4))
        tk.Button(header, text="◀", width=3, command=self._mes_anterior).pack(side="left")
        self.titulo_label = tk.Label(header, width=16, anchor="center", font=("", 10, "bold"))
        self.titulo_label.pack(side="left", padx=6)
        tk.Button(header, text="▶", width=3, command=self._mes_siguiente).pack(side="left")

        self.dias_frame = tk.Frame(self)
        self.dias_frame.pack(padx=10, pady=(0, 6))

        btn_frame = tk.Frame(self)
        btn_frame.pack(padx=10, pady=(0, 10))
        tk.Button(btn_frame, text="Hoy", command=self._elegir_hoy, width=10).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Quitar fecha", command=self._quitar, width=12).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Cerrar", command=self.destroy, width=10).pack(side="left", padx=4)

        self._dibujar_mes()

    def _mes_anterior(self):
        self.mes -= 1
        if self.mes == 0:
            self.mes, self.anio = 12, self.anio - 1
        self._dibujar_mes()

    def _mes_siguiente(self):
        self.mes += 1
        if self.mes == 13:
            self.mes, self.anio = 1, self.anio + 1
        self._dibujar_mes()

    def _dibujar_mes(self):
        for w in self.dias_frame.winfo_children():
            w.destroy()

        self.titulo_label.config(text=f"{MESES[self.mes - 1]} {self.anio}")
        for col, nombre in enumerate(DIAS):
            tk.Label(self.dias_frame, text=nombre, width=4, fg="gray30").grid(row=0, column=col)

        hoy = date.today()
        for fila, semana in enumerate(calendar.Calendar(firstweekday=0).monthdayscalendar(self.anio, self.mes), start=1):
            for col, dia in enumerate(semana):
                if dia == 0:
                    continue
                es_hoy = (self.anio, self.mes, dia) == (hoy.year, hoy.month, hoy.day)
                tk.Button(
                    self.dias_frame,
                    text=str(dia),
                    width=4,
                    relief="solid" if es_hoy else "flat",
                    command=lambda d=dia: self._elegir(d),
                ).grid(row=fila, column=col, padx=1, pady=1)

    def _elegir(self, dia: int):
        self.on_elegir(date(self.anio, self.mes, dia).isoformat())
        self.destroy()

    def _elegir_hoy(self):
        self.on_elegir(date.today().isoformat())
        self.destroy()

    def _quitar(self):
        self.on_elegir("")
        self.destroy()
