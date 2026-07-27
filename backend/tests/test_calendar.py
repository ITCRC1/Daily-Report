"""Test del generador de calendario (corte Vie–Jue sin huecos, confirmado por
Bismark 2026-07-11 vía `CORTES SEMANALES.xlsx` — reemplaza el corte Lun-Dom
anterior, bug §6.1).

No requiere DB. Valida la lógica pura de semana/etiqueta.
"""
from datetime import date, timedelta

from app.seed import _week_label


def test_semana_viernes_a_jueves():
    # 24-Jun-2026 es miércoles → semana 19-Jun (vie) a 25-Jun (jue)
    iso_week, ws, we, label = _week_label(date(2026, 6, 24))
    assert ws == date(2026, 6, 19)
    assert ws.weekday() == 4  # viernes
    assert we == date(2026, 6, 25)
    assert we.weekday() == 3  # jueves
    assert label == "W26 | 19-Jun-2026 to 25-Jun-2026"


def test_primera_semana_2026_confirmada_por_archivo():
    # W01 2026, tal como viene en CORTES SEMANALES.xlsx: 26-Dic-2025 a 01-Ene-2026
    iso_week, ws, we, label = _week_label(date(2026, 1, 1))
    assert iso_week == 1
    assert ws == date(2025, 12, 26)
    assert we == date(2026, 1, 1)
    assert label == "W01 | 26-Dec-2025 to 01-Jan-2026"


def test_sin_huecos_entre_semanas():
    # jueves + 1 día = viernes de la semana siguiente (sin días huérfanos, bug §6.1)
    _, ws_jue, we_jue, _ = _week_label(date(2026, 6, 25))  # jueves
    _, ws_vie, _, _ = _week_label(date(2026, 6, 26))       # viernes siguiente
    assert ws_vie == we_jue + timedelta(days=1)
