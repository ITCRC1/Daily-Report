"""Motor de Budget (Tab 6.1/6.5) — derivación del presupuesto diario a partir
del mensual por departamento (§3 modelo: fact_budget = budget_monthly / días
del mes; el residual de redondeo va al último día para que Σ diarios = mensual
exacto). Confirmado en el spec: 121,219.07 / 31 = 3,910.29.
"""
from __future__ import annotations

import calendar
from decimal import ROUND_HALF_UP, Decimal


def derive_daily_amounts(monthly_amount: Decimal | float, year: int, month: int) -> list[Decimal]:
    """Reparte `monthly_amount` en los días del mes; el resto de redondeo cae
    en el último día para que la suma cierre exacta contra el mensual."""
    monthly_amount = Decimal(str(monthly_amount))
    days = calendar.monthrange(year, month)[1]
    base = (monthly_amount / days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    daily = [base] * days
    residual = (monthly_amount - base * days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    daily[-1] = (daily[-1] + residual).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return daily
