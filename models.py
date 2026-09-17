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
    # Campos de conveniencia, se rellenan al leer con JOIN
    estado_nombre: str = ""
    estado_color: str = "#808080"
