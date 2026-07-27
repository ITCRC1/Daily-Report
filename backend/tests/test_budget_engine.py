"""Motor de derivación diaria del Budget (§3): confirmado en el spec original
121,219.07 / 31 = 3,910.29, residual al último día."""
from decimal import Decimal

from app.engine.budget import derive_daily_amounts


def test_derivacion_confirmada_en_el_spec():
    daily = derive_daily_amounts(Decimal("121219.07"), 2026, 5)  # mayo, 31 días
    assert len(daily) == 31
    assert daily[0] == Decimal("3910.29")
    assert daily[-2] == Decimal("3910.29")
    # el residual de redondeo cae en el último día
    assert daily[-1] == Decimal("3910.37")


def test_suma_diaria_cierra_exacto_contra_el_mensual():
    monthly = Decimal("121219.07")
    daily = derive_daily_amounts(monthly, 2026, 5)
    assert sum(daily) == monthly


def test_febrero_bisiesto_vs_no_bisiesto():
    assert len(derive_daily_amounts(Decimal("1000"), 2024, 2)) == 29  # bisiesto
    assert len(derive_daily_amounts(Decimal("1000"), 2026, 2)) == 28


def test_monto_cero():
    daily = derive_daily_amounts(Decimal("0"), 2026, 6)
    assert all(d == Decimal("0.00") for d in daily)
