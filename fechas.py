"""Formateo de fechas para mostrar en pantalla. Lo que se guarda en la DB sigue siendo ISO
completo (para poder ordenar/filtrar bien) — esto solo cambia cómo se ve."""


def formatear_fecha(fecha_iso: str) -> str:
    """DD/MM/AAAA sin hora ni la 'T'. Ej: "2026-09-17T16:38:03" -> "17/09/2026"."""
    fecha = (fecha_iso or "").split("T")[0]
    partes = fecha.split("-")
    if len(partes) != 3:
        return fecha_iso or ""
    anio, mes, dia = partes
    return f"{dia}/{mes}/{anio}"
