"""_otb_concept_findings (audit_service): todo lo que no cuadra en 2.5 debe
convertirse en hallazgo — el caso real del 2026-06-08 (inventario 30 vs 22)."""
from app.services.audit_service import _otb_concept_findings

OTB_ROOMS_0608 = {
    "no_rooms": 13, "no_persons": 20, "inventory_rooms": 30,
    "adr": 386.46, "occupancy": 43.3333,
}
ACTUAL_0608 = {"rn": 13, "pax": 20, "available": 22, "adr": 386.46, "occupancy_pct": 0.5909}


def test_solo_lo_que_no_cuadra_se_reporta():
    out = _otb_concept_findings(OTB_ROOMS_0608, ACTUAL_0608)
    conceptos = {f["concepto"] for f in out}
    # RN/Pax/ADR cuadran exacto -> no deben aparecer como hallazgo
    assert "Habitaciones (RN)" not in conceptos
    assert "Personas (Pax)" not in conceptos
    assert "ADR" not in conceptos
    # Inventario y Ocupación NO cuadran -> deben aparecer
    assert "Inventario disponible" in conceptos
    assert "Ocupación %" in conceptos


def test_diferencia_correcta():
    out = {f["concepto"]: f for f in _otb_concept_findings(OTB_ROOMS_0608, ACTUAL_0608)}
    assert out["Inventario disponible"]["diferencia"] == -8
    assert out["Ocupación %"]["diferencia"] > 15  # 59.09 - 43.33 ≈ 15.76


def test_todo_cuadrado_no_da_hallazgos():
    otb = {"no_rooms": 10, "no_persons": 15, "inventory_rooms": 20, "adr": 100.0, "occupancy": 50.0}
    real = {"rn": 10, "pax": 15, "available": 20, "adr": 100.0, "occupancy_pct": 0.5}
    assert _otb_concept_findings(otb, real) == []


def test_sin_datos_no_rompe():
    assert _otb_concept_findings(None, ACTUAL_0608) == []
    assert _otb_concept_findings(OTB_ROOMS_0608, None) == []
