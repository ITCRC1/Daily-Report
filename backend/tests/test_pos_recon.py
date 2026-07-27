"""Motor de auditoría Simphony POS (2.9): consistencia interna del Excel de
Ventas, contra el único día real disponible (2026-06-28 — no cruza con el
06-08, pero valida el parser y el motor con datos genuinos)."""
from pathlib import Path

import pytest

from app.engine.pos_recon import pos_internal_checks, pos_vs_pms_check
from app.ingest.pos import parse_pos_excel

INP = Path(__file__).resolve().parents[2] / "goldens" / "inputs" / "2026-06-28"
POS_FILE = INP / "Ventas_2026-06-28_FINAL.xlsx"
pytestmark = pytest.mark.skipif(not POS_FILE.exists(), reason="falta el POS del 06-28")


def _summary_and_checks():
    meta = parse_pos_excel(POS_FILE)
    summary = {
        "ventas_netas": meta["ventas_netas"], "cargos_servicio": meta["sc"],
        "total_ventas": meta["total_dia"], "voids": meta["voids"],
        "room_charge_confirmado": meta["room_charge"],
    }
    checks = [{"monto": c["monto"], "is_room_charge": "ROOM CHARGE" in c["forma_pago"].upper()}
              for c in meta["all_checks"]]
    return summary, checks


def test_ventas_netas_mas_sc_cuadra_con_total():
    """Ventas Netas ($1,592.40) + Cargos Servicio ($57.00) = Total Ventas ($1,649.40)."""
    summary, checks = _summary_and_checks()
    out = {c["concepto"]: c for c in pos_internal_checks(summary, checks)}
    r = out["Ventas Netas + Cargos Servicio vs Total Ventas"]
    assert r["estado"] == "OK"
    assert r["diferencia"] == pytest.approx(0.0, abs=0.01)


def test_room_charge_forma_pago_cuadra_con_mapeo():
    """Room Charge por forma de pago ($1,155.02) == confirmado en Mapeo Simphony→Opera."""
    summary, checks = _summary_and_checks()
    out = {c["concepto"]: c for c in pos_internal_checks(summary, checks)}
    r = out["Room Charge (forma de pago) vs Mapeo Simphony→Opera"]
    assert r["estado"] == "OK"
    assert r["a"] == pytest.approx(1155.02, abs=0.01)
    assert r["b"] == pytest.approx(1155.02, abs=0.01)


def test_suma_detalle_no_cuadra_con_total_discrepancia_real():
    """Caso real encontrado: la suma de TODOS los checks ($1,793.42) no coincide
    con el Total Ventas del Resumen Ejecutivo ($1,649.40) — diferencia $144.02.
    No se oculta: el motor debe marcarlo DISCREPANCIA."""
    summary, checks = _summary_and_checks()
    out = {c["concepto"]: c for c in pos_internal_checks(summary, checks)}
    r = out["Suma Detalle de Checks vs Total Ventas"]
    assert r["estado"] == "DISCREPANCIA"
    assert r["diferencia"] == pytest.approx(144.02, abs=0.01)


def test_pos_vs_pms_ok_cuando_coincide():
    r = pos_vs_pms_check(total_ventas=1000.0, opera_fb=1000.0, integrity_fb=1000.0)
    assert r["opera_recon"]["estado"] == "OK"
    assert r["integrity_recon"]["estado"] == "OK"


def test_pos_vs_pms_discrepancia_cuando_no_coincide():
    r = pos_vs_pms_check(total_ventas=1000.0, opera_fb=950.0, integrity_fb=1000.0)
    assert r["opera_recon"]["estado"] == "DISCREPANCIA"
    assert r["opera_recon"]["diferencia"] == 50.0
    assert r["integrity_recon"]["estado"] == "OK"


# --- 2026-06-08: el POS del día real (cruza con Opera/Integrity, ya no bloqueado) ---

INP_0608 = Path(__file__).resolve().parents[2] / "goldens" / "inputs" / "2026-06-08"
POS_FILE_0608 = INP_0608 / "Ventas_08_Junio_2026_FINAL.xlsx"
pytestmark_0608 = pytest.mark.skipif(not POS_FILE_0608.exists(), reason="falta el POS del 06-08")


@pytestmark_0608
def test_0608_internal_checks_reales():
    """Golden real: Ventas Netas+SC=Total OK, Room Charge=Mapeo OK, pero la suma
    del Detalle de Checks NO cuadra con el Total (discrepancia real, no fabricada)."""
    meta = parse_pos_excel(POS_FILE_0608)
    summary = {
        "ventas_netas": meta["ventas_netas"], "cargos_servicio": meta["sc"],
        "total_ventas": meta["total_dia"], "voids": meta["voids"],
        "room_charge_confirmado": meta["room_charge"],
    }
    checks = [{"monto": c["monto"], "is_room_charge": "ROOM CHARGE" in c["forma_pago"].upper()}
              for c in meta["all_checks"]]
    out = {c["concepto"]: c for c in pos_internal_checks(summary, checks)}

    assert out["Ventas Netas + Cargos Servicio vs Total Ventas"]["estado"] == "OK"
    assert out["Room Charge (forma de pago) vs Mapeo Simphony→Opera"]["estado"] == "OK"

    r = out["Suma Detalle de Checks vs Total Ventas"]
    assert r["estado"] == "DISCREPANCIA"
    assert r["diferencia"] == pytest.approx(145.72, abs=0.01)


@pytestmark_0608
def test_0608_room_charge_confirmado():
    """Room Charge → Opera del 06-08 real: $964.12 (14 checks)."""
    meta = parse_pos_excel(POS_FILE_0608)
    assert meta["room_charge"] == pytest.approx(964.12, abs=0.01)
    assert len(meta["rc_detail"]) == 14


@pytestmark_0608
def test_0608_pos_vs_pms_discrepancia_real():
    """Cruce real POS vs Opera/Integrity (F&B) del 2026-06-08: el POS vendió
    $1,477.20 pero Opera/Integrity tienen $2,005.32 posteado en F&B ese día —
    discrepancia real de $528.12, evidencia visible, no oculta."""
    meta = parse_pos_excel(POS_FILE_0608)
    r = pos_vs_pms_check(total_ventas=meta["total_dia"], opera_fb=2005.32, integrity_fb=2005.32)
    assert r["opera_recon"]["estado"] == "DISCREPANCIA"
    assert r["opera_recon"]["diferencia"] == pytest.approx(-528.12, abs=0.01)
    assert r["integrity_recon"]["estado"] == "DISCREPANCIA"
