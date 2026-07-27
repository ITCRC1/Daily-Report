"""Reconciliación real Opera ↔ Integrity del 2026-06-08 (golden end-to-end).

El archivo Integrity es 'DAILY REVENUE REPORT 2026-06-08.xlsx' (mal nombrado, pero
es el mayor: hoja única 'Datos'). Se clasifica por contenido, no por nombre (§2.8).
"""
from pathlib import Path

import pytest

from app.engine.reconcile import recon_kpis, reconcile
from app.ingest.integrity import parse_integrity
from app.ingest.opera import parse_revenue

INP = Path(__file__).resolve().parents[2] / "goldens" / "inputs" / "2026-06-08"
REV = INP / "COWLCR_20260608_REVENUE.xml"
INTEG = INP / "DAILY REVENUE REPORT 2026-06-08.xlsx"
pytestmark = pytest.mark.skipif(
    not (REV.exists() and INTEG.exists()), reason="faltan insumos 2026-06-08"
)


def _recon():
    headers, _ = parse_revenue(REV)
    integ = parse_integrity(INTEG)
    rows = reconcile(headers, integ)
    return {r.tcode: r for r in rows}, rows


def test_accommodation_cuadra():
    by_tc, _ = _recon()
    assert by_tc["1000"].estado == "OK"
    assert by_tc["1000"].opera == pytest.approx(5023.96, abs=0.01)
    assert by_tc["1000"].integrity == pytest.approx(5023.96, abs=0.01)


def test_kpis_del_dia():
    _, rows = _recon()
    k = recon_kpis(rows)
    assert k["faltante"] == 0          # nada perdido entre sistemas
    assert k["ok"] >= 33               # la gran mayoría cuadra
    assert k["discrepancia"] == 2      # 6480 y 6485 (ajustes)


def test_pagos_regla_de_signo():
    by_tc, _ = _recon()
    # 3700/3721 son PAYMENT: integridad = -int_db, deben cuadrar
    assert by_tc["3700"].estado == "OK"
    assert by_tc["3721"].estado == "OK"
    assert by_tc["3700"].integrity < 0


def test_ajustes_negativos_surgen_como_discrepancia():
    """6480/6485: revenue negativo en Opera, débito en Integrity → excepción visible.

    Documenta el comportamiento §5.4 (revenue usa int_cr): el ajuste NO se netea
    en silencio; surge para revisión del auditor. Cambiarlo sería inventar regla.
    """
    by_tc, _ = _recon()
    assert by_tc["6480"].estado == "DISCREPANCIA"
    assert by_tc["6480"].opera < 0
    assert by_tc["6485"].estado == "DISCREPANCIA"
