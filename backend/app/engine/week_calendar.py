"""Corte semanal Vie-Jue (Tab 6.10 Weekly Calendar, confirmado por Bismark
2026-07-11 vía `CORTES SEMANALES.xlsx`). Puro cálculo, sin DB -- usado por
`seed.py` (bootstrap de un entorno nuevo) y por
`master_data_service.recalculate_weeks` (botón "Recalcular" de Tab 6.10).

IMPORTANTE: esto es la SEMILLA/estándar. Las semanas quedan EDITABLES fila por
fila en Tab 6.10 (fecha inicio/fin), y Tab 4 (Weekly Revenue) lee los rangos
vigentes de `dim_week_calendar`. `dim_calendar` (por día) es una tabla APARTE
que NO se toca -- ambas coexisten para variantes de reporting.
"""
from __future__ import annotations

from datetime import date, timedelta


def build_label(week_num: int, week_start: date, week_end: date) -> str:
    """Etiqueta canónica de una semana: `W26 | 19-Jun-2026 to 25-Jun-2026`.
    Se deriva SIEMPRE de (week_num, start, end) -- nunca se escribe a mano, así
    que al editar las fechas en Tab 6.10 el label se actualiza solo."""
    return (
        f"W{week_num:02d} | {week_start.strftime('%d-%b-%Y')} "
        f"to {week_end.strftime('%d-%b-%Y')}"
    )


def week_of(d: date) -> tuple[int, date, date, str]:
    """Semana Vie-Jue estándar que contiene `d`. La semana pertenece al año de
    su jueves de cierre; el número cuenta desde la primera semana Vie-Jue cuyo
    jueves cae en ese año. Verificado exacto contra las 53 semanas de 2026 de
    `CORTES SEMANALES.xlsx` (0 mismatches: fecha, número y label)."""
    days_since_friday = (d.weekday() - 4) % 7   # Mon=0..Sun=6, Friday=4
    week_start = d - timedelta(days=days_since_friday)
    week_end = week_start + timedelta(days=6)   # jueves
    year = week_end.year
    jan1 = date(year, 1, 1)
    days_to_first_thu = (3 - jan1.weekday()) % 7   # Thursday=3
    first_thu = jan1 + timedelta(days=days_to_first_thu)
    first_week_start = first_thu - timedelta(days=6)
    week_num = (week_start - first_week_start).days // 7 + 1
    return week_num, week_start, week_end, build_label(week_num, week_start, week_end)


def generate_weeks(start: date, end: date) -> list[dict]:
    """Semanas Vie-Jue contiguas cubriendo [start, end], una fila por semana.
    Es la SEMILLA estándar; después cada fila es editable. La primera semana es
    la que contiene `start`; se avanza de jueves en jueves hasta pasar `end`."""
    _, week_start, _, _ = week_of(start)
    weeks = []
    while week_start <= end:
        week_num, ws, we, label = week_of(week_start)
        weeks.append({"week_num": week_num, "week_start": ws, "week_end": we, "week_label": label})
        week_start = we + timedelta(days=1)
    return weeks
