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


def instalar_opciones(root: tk.Misc) -> None:
    """Colores y letra de Z2 para TODOS los controles clásicos de Tkinter (los de todas las
    ventanas), vía la base de opciones de Tk: se aplica a cada control que se cree después,
    incluidos los que aparecen sobre la marcha (filas que se agregan, avisos que se muestran
    más tarde). Lo que el código ya pone a mano (por ejemplo un color de aviso) se respeta.

    Los botones secundarios van celeste suave en vez de blanco con borde: en Windows los
    botones clásicos no dibujan un borde de color, y blanco sobre el fondo casi blanco no se
    vería como botón."""
    o = root.option_add
    for clase in ("Toplevel", "Frame", "Canvas", "Labelframe"):
        o(f"*{clase}.background", FONDO)
    o("*Canvas.highlightThickness", 0)
    o("*Label.background", FONDO)
    o("*Label.foreground", TEXTO_BOTON)
    o("*Label.font", (FAMILIA, 10))
    for clase in ("Checkbutton", "Radiobutton"):
        o(f"*{clase}.background", FONDO)
        o(f"*{clase}.activeBackground", FONDO)
        o(f"*{clase}.foreground", TEXTO_BOTON)
        o(f"*{clase}.font", (FAMILIA, 10))
    for clase in ("Entry", "Text", "Listbox", "Spinbox"):
        o(f"*{clase}.background", PANEL)
        o(f"*{clase}.foreground", TEXTO)
        o(f"*{clase}.relief", "flat")
        o(f"*{clase}.borderWidth", 0)
        o(f"*{clase}.highlightThickness", 1)
        o(f"*{clase}.highlightBackground", LINEA_FUERTE)
        o(f"*{clase}.highlightColor", ACENTO)
        o(f"*{clase}.selectBackground", ACENTO)
        o(f"*{clase}.selectForeground", "#ffffff")
        o(f"*{clase}.font", (FAMILIA, 11))
    o("*Entry.insertBackground", TEXTO)
    o("*Text.insertBackground", TEXTO)
    o("*Button.background", ACENTO_SUAVE)
    o("*Button.foreground", ACENTO_OSCURO)
    o("*Button.activeBackground", LINEA)
    o("*Button.activeForeground", ACENTO_OSCURO)
    o("*Button.relief", "flat")
    o("*Button.borderWidth", 0)
    o("*Button.highlightThickness", 0)
    o("*Button.font", (FAMILIA, 10, "bold"))
    o("*Button.padX", 12)
    o("*Button.padY", 5)
    o("*Button.cursor", "hand2")
    o("*Menu.background", PANEL)
    o("*Menu.foreground", TEXTO)
    o("*Menu.activeBackground", ACENTO_SUAVE)
    o("*Menu.activeForeground", ACENTO_OSCURO)
    o("*Menu.font", (FAMILIA, 10))


def primario(boton: tk.Button) -> tk.Button:
    """Botón de la acción principal de una ventana (Guardar, Aplicar...): turquesa de Z2."""
    boton.configure(bg=ACENTO, fg="#ffffff", activebackground=ACENTO_OSCURO, activeforeground="#ffffff")
    return boton


def peligro(boton: tk.Button) -> tk.Button:
    """Botón de una acción que borra o pisa datos: rojo de Z2."""
    boton.configure(bg=PELIGRO, fg="#ffffff", activebackground="#912018", activeforeground="#ffffff")
    return boton
