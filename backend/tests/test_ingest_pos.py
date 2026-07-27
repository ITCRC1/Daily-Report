"""Test del parser POS contra el Excel de Ventas real (2026-06-28)."""
from pathlib import Path

import pytest

from app.ingest.pos import parse_pos_excel

POS = (Path(__file__).resolve().parents[2] / "goldens" / "inputs" / "2026-06-28"
       / "Ventas_2026-06-28_FINAL.xlsx")
pytestmark = pytest.mark.skipif(not POS.exists(), reason="falta POS 2026-06-28")


def test_pos_checks_y_room_charges():
    meta = parse_pos_excel(POS)
    assert meta["source"] == "excel"
    # Detalle de Checks: hay checks parseados con monto
    assert len(meta["all_checks"]) > 0
    assert all("check_num" in c and "monto" in c for c in meta["all_checks"])
    # Resúmenes derivados
    assert meta["by_employee"], "debe haber resumen por empleado"
    assert meta["by_payment"], "debe haber resumen por forma de pago"
    # Room charges (Mapeo Simphony -> Opera)
    assert meta["room_charge"] > 0
    assert len(meta["rc_detail"]) > 0
    # consistencia: suma de rc_detail == room_charge
    assert round(sum(r["monto"] for r in meta["rc_detail"]), 2) == pytest.approx(
        meta["room_charge"], abs=0.01
    )
