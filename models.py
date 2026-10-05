from dataclasses import dataclass
from typing import Optional


@dataclass
class Estado:
    id: Optional[int]
    nombre: str
    color: str = "#808080"
    orden: int = 0


@dataclass
class Cliente:
    id: Optional[int]
    nombre: str
    contacto: str
    estado_id: int
    fecha_actualizacion: str
    fecha_alta: str = ""
    notas: str = ""
    recomendado_por: str = ""
    # Columna "origen" de la base: "z2" si el cliente se trajo de Z2, "" si se cargó en Z1. Se
    # llama distinto que `origen` (más abajo) porque ése es otro dato: de qué base sale una fila
    # en el panel de duplicados ("local" o "z2").
    procedencia: str = ""
    fecha_recordatorio: str = ""  # "AAAA-MM-DD" o "" si no tiene — ver db.listar_recordatorios_de_hoy
    # Texto secondary de una fila que viene de Z2 (ART, estado, prioridad). Vacío en las locales:
    # para un cliente de esta base no hay nada más que mostrar que nombre y teléfono.
    detalle: str = ""
    # Campos de conveniencia, se rellenan al leer con JOIN
    estado_nombre: str = ""
    estado_color: str = "#808080"
    # De dónde salió la fila en el panel de coincidencias: "local" es de esta base (SQLite),
    # "z2" viene de la consulta al otro programa. Solo lo usa la UI para distinguir el origen;
    # un Cliente creado/acomodado por el resto de la app nunca lo cambia.
    origen: str = "local"
    # Identificador que la fila tiene en SU base de origen, para cuando no es esta. Vacío para
    # los clientes locales (su id ya está en `id`); para los de Z2 es el uuid de la carpeta. El
    # panel lo usa solo para armar un iid único de Treeview — nunca para consultar la base.
    id_remoto: str = ""
