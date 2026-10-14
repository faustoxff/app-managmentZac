"""Tema visual con la paleta de Z2 (src/styles.css de Z2), para CustomTkinter y ttk.

OJO con CustomTkinter: en sus widgets `.config(...)` y `widget["opcion"]` NO funcionan (caen al
Frame de Tkinter de abajo y tiran error). Hay que usar `.configure(...)` y `.cget(...)`.
"""
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

FONDO = "#f8fdff"
PANEL = "#ffffff"
PANEL_SUAVE = "#f4fbfd"
LINEA = "#d7e9ee"
LINEA_FUERTE = "#bddce4"
TEXTO = "#17212b"
TEXTO_BOTON = "#344054"
APAGADO = "#5c6f7a"
APAGADO_2 = "#879aa4"
ACENTO = "#12aeca"
ACENTO_OSCURO = "#087f95"
ACENTO_SUAVE = "#e7faff"
PELIGRO = "#b42318"

FAMILIA = "Segoe UI"  # en Windows; en otros sistemas Tk elige una parecida


def fuente(tamano: int = 12, negrita: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=FAMILIA, size=tamano, weight="bold" if negrita else "normal")


def boton(parent, texto: str, comando, primario: bool = False, peligro: bool = False, **kw):
    """Botón con el estilo de Z2: primario turquesa, secundario blanco con borde."""
    if primario or peligro:
        color = PELIGRO if peligro else ACENTO
        estilo = dict(
            fg_color=color, hover_color="#912018" if peligro else ACENTO_OSCURO,
            text_color="#ffffff", border_width=0,
        )
    else:
        estilo = dict(
            fg_color=PANEL, hover_color=ACENTO_SUAVE, text_color=TEXTO_BOTON,
            border_width=1, border_color=LINEA_FUERTE,
        )
    estilo.update(
        text=texto.upper(), command=comando, corner_radius=8, height=32, width=10,
        font=fuente(11, negrita=True), text_color_disabled=APAGADO_2,
    )
    estilo.update(kw)
    return ctk.CTkButton(parent, **estilo)


def campo(parent, variable=None, ancho: int = 260, **kw):
    return ctk.CTkEntry(
        parent, textvariable=variable, width=ancho, height=32, corner_radius=8,
        border_width=1, border_color=LINEA_FUERTE, fg_color=PANEL, text_color=TEXTO,
        font=fuente(12), **kw,
    )


def aplicar_tema_ttk(root: tk.Misc) -> None:
    """Tablas, desplegables y barras de desplazamiento (ttk) con los mismos colores."""
    ctk.set_appearance_mode("light")
    estilo = ttk.Style(root)
    estilo.theme_use("clam")
    estilo.configure(
        "Treeview",
        background=PANEL, fieldbackground=PANEL, foreground=TEXTO,
        bordercolor=LINEA, borderwidth=1, rowheight=28, font=(FAMILIA, 10),
    )
    estilo.map(
        "Treeview",
        background=[("selected", ACENTO_OSCURO)],
        foreground=[("selected", "#ffffff")],
    )
    estilo.configure(
        "Treeview.Heading",
        background=PANEL_SUAVE, foreground=APAGADO, bordercolor=LINEA, relief="flat",
        font=(FAMILIA, 9, "bold"), padding=(6, 6),
    )
    estilo.map("Treeview.Heading", background=[("active", ACENTO_SUAVE)], foreground=[("active", ACENTO_OSCURO)])
    estilo.configure(
        "TCombobox", fieldbackground=PANEL, background=PANEL, foreground=TEXTO,
        bordercolor=LINEA_FUERTE, arrowcolor=ACENTO_OSCURO, padding=4,
    )
    estilo.map(
        "TCombobox",
        fieldbackground=[("readonly", PANEL)],
        selectbackground=[("readonly", PANEL)],
        selectforeground=[("readonly", TEXTO)],
        bordercolor=[("focus", ACENTO)],
    )
    for orient in ("Vertical", "Horizontal"):
        estilo.configure(
            f"{orient}.TScrollbar", background=LINEA, troughcolor=PANEL_SUAVE,
            bordercolor=PANEL_SUAVE, arrowcolor=APAGADO, relief="flat",
        )


def _descendientes(w):
    for hijo in w.winfo_children():
        yield hijo
        yield from _descendientes(hijo)


def estilizar_clasico(ventana, primarios=(), peligro=()):
    """Pinta con la paleta de Z2 una ventana hecha con los controles clásicos de Tkinter, sin
    reemplazarlos. Sirve para formularios donde el manejo de teclado y foco depende de esos
    controles (en CustomTkinter el foco queda en un widget interno y Enter no llega al botón)."""
    colores_por_defecto = {"black", "#000000", "SystemButtonText", "SystemWindowText"}
    ventana.configure(bg=FONDO)
    for w in _descendientes(ventana):
        clase = w.winfo_class()
        if clase == "Frame":
            w.configure(bg=FONDO)
        elif clase == "Label":
            opciones = {"bg": FONDO, "font": (FAMILIA, 10)}
            if str(w.cget("fg")) in colores_por_defecto:
                opciones["fg"] = TEXTO_BOTON
            if str(w.cget("relief")) == "sunken":
                opciones.update(bg=PANEL, relief="flat", highlightthickness=1, highlightbackground=LINEA_FUERTE)
            w.configure(**opciones)
        elif clase in ("Entry", "Text"):
            w.configure(
                relief="flat", bg=PANEL, fg=TEXTO, insertbackground=TEXTO, font=(FAMILIA, 11),
                highlightthickness=1, highlightbackground=LINEA_FUERTE, highlightcolor=ACENTO,
            )
        elif clase == "Button":
            if w in primarios or w in peligro:
                color, oscuro = (PELIGRO, "#912018") if w in peligro else (ACENTO, ACENTO_OSCURO)
                w.configure(bg=color, fg="#ffffff", activebackground=oscuro, activeforeground="#ffffff")
            else:
                w.configure(
                    bg=PANEL, fg=TEXTO_BOTON, activebackground=ACENTO_SUAVE, activeforeground=ACENTO_OSCURO,
                    highlightbackground=LINEA_FUERTE,
                )
            w.configure(relief="flat", bd=0, font=(FAMILIA, 10, "bold"), padx=12, pady=5, cursor="hand2")
