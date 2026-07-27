"""Motor de Revenue (etapa 2): clasificación 12-col + pivote diario.

Validación por reconciliación: el pivote del 2026-06-08 desde el Integrity debe
cuadrar al centavo con el total de Opera (9560.02) y Rooms = Accommodation
(tcode 1000 = 5023.96), que a su vez es el HF Rooms Only (§5.6).
"""
from pathlib import Path

import pytest

from app.engine.revenue import (
    daily_revenue,
    fb_subcategory,
    lines_from_integrity,
    output_column,
    weekly_output_column,
    weekly_pivot,
)
from app.ingest.integrity import parse_integrity_lines

INP = Path(__file__).resolve().parents[2] / "goldens" / "inputs" / "2026-06-08"
INTEG = INP / "DAILY REVENUE REPORT 2026-06-08.xlsx"
pytestmark = pytest.mark.skipif(not INTEG.exists(), reason="falta Integrity 06-08")


def test_output_column_por_outlet():
    assert output_column("4000-0110-004-001-001-08-03") == "Rooms"
    assert output_column("4110-0123-120-999-001-08-00") == "F&B"
    assert output_column("4201-0140-020-999-001-08-00") == "SPA"
    assert output_column("4880-0170-999-999-001-08-00") == "Sustainable Fee"
    assert output_column("9999-8888-x") == "Otros"  # excepción visible


def test_fb_subcategory_por_naturaleza():
    assert fb_subcategory("4110-0123-...") == "FOOD"
    assert fb_subcategory("4120-0123-...") == "FOOD"       # §5.1a: 4120 → FOOD
    assert fb_subcategory("4130-0123-...") == "BEVERAGE"
    assert fb_subcategory("4132-0123-...") == "MISC"


def _pivot():
    rows = parse_integrity_lines(INTEG)
    return daily_revenue(lines_from_integrity(rows))


def test_total_reconcilia_con_opera():
    p = _pivot()
    assert p["total"] == pytest.approx(9560.02, abs=0.01)


def test_rooms_es_accommodation():
    p = _pivot()
    assert p["columns"]["Rooms"] == pytest.approx(5023.96, abs=0.01)


def test_fb_split_cuadra():
    """F&B (columna) == Food + Beverage + Misc (§ split check del golden)."""
    p = _pivot()
    assert p["fb_split_check"] == pytest.approx(0.0, abs=0.01)
    fb = p["fb_detail"]
    assert p["columns"]["F&B"] == pytest.approx(
        fb["food"] + fb["beverage"] + fb["misc"], abs=0.01)


def test_sin_otros_en_dia_conocido():
    """El 06-08 no debe tener cuentas fuera del mapa canónico."""
    p = _pivot()
    assert p["otros_total"] == pytest.approx(0.0, abs=0.01), p["otros"]


# --- Weekly (§5.1a nature-based: Rooms/Rooms Others, Sustainable Fee/Misc. Rev Others) ---

def test_weekly_output_column_abre_rooms_y_sustainable():
    assert weekly_output_column("4000-0110-...") == "Rooms"
    assert weekly_output_column("4010-0110-...") == "Rooms Others"  # nature != 4000
    assert weekly_output_column("4880-0170-...") == "Sustainable Fee"
    assert weekly_output_column("4800-0170-...") == "Misc. Rev Others"
    assert weekly_output_column("4110-0123-...") == "F&B"
    assert weekly_output_column("4201-0140-...") == "SPA"


def test_weekly_pivot_reproduce_golden_actual_06_08():
    """Golden: fila 2026-06-08 de la hoja 'Actual' del WEEKLY workbook —
    valida las 12 columnas al centavo, no solo el total."""
    rows = parse_integrity_lines(INTEG)
    p = weekly_pivot(lines_from_integrity(rows))
    expected = {
        "Rooms": 5023.96, "Rooms Others": 0.0, "F&B": 2005.32, "SPA": 390.0,
        "Tours": 1745.28, "Retail-Gift Shop": 27.0, "Transportation": 81.0,
        "Laundry": 0.0, "Innoceana": 0.0, "Crowther Lab": 0.0,
        "Sustainable Fee": 287.46, "Misc. Rev Others": 0.0,
    }
    for col, exp in expected.items():
        assert p["columns"][col] == pytest.approx(exp, abs=0.01), col
    assert p["fb_detail"] == {"food": 1531.32, "beverage": 474.0, "misc": 0.0}
    assert p["total"] == pytest.approx(9560.02, abs=0.01)
