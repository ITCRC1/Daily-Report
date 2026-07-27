"""Tab 5.2 (panel derecho) — Full Year Cash Flow Forecast por escenario.

Editable por escenario: `opening` (saldo al cierre de Dic del año anterior) +
Net Change in Cash de cada mes (n1..n12). Beginning/Ending Cash se derivan con
roll-forward: Beginning[Ene]=opening; Ending[m]=Beginning[m]+Net[m];
Beginning[m+1]=Ending[m]. Total Net = Σ Net; Total Ending = Ending de Dic.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CashFlowForecast, Property

SCENARIOS = [("current", "Current Forecast"), ("april", "Forecast April 2026"), ("budget", "Budget 2026")]
_SCN_KEYS = {k for k, _ in SCENARIOS}
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


async def _pid(session: AsyncSession, code: str):
    pid = (await session.execute(select(Property.id).where(Property.code == code))).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


def _rollforward(opening: float, nets: list[float], begins: list[float | None]) -> dict:
    """beginning[m] = override si viene, si no el Ending del mes anterior
    (Ene = opening). ending[m] = beginning[m] + net[m]."""
    beginning, ending = [], []
    for m in range(12):
        ov = begins[m] if m < len(begins) else None
        beg = ov if ov is not None else (opening if m == 0 else ending[m - 1])
        beginning.append(beg)
        ending.append(beg + nets[m])
    return {
        "opening": round(opening, 2),
        "net": [round(x, 2) for x in nets],
        "begin_override": [round(x, 2) if x is not None else None for x in begins],
        "beginning": [round(x, 2) for x in beginning],
        "ending": [round(x, 2) for x in ending],
        "net_total": round(sum(nets), 2),
        "ending_total": round(ending[-1], 2) if ending else round(opening, 2),
    }


async def get_forecast(session: AsyncSession, year: int, property_code: str = "COWLCR") -> dict:
    pid = await _pid(session, property_code)
    rows = (await session.execute(
        select(CashFlowForecast).where(
            CashFlowForecast.property_id == pid, CashFlowForecast.year == year)
    )).scalars().all()
    by = {r.scenario: r for r in rows}

    scenarios = []
    for scn, label in SCENARIOS:
        r = by.get(scn)
        opening = float(r.opening) if r else 0.0
        nets = [float(getattr(r, f"n{m}")) if r else 0.0 for m in range(1, 13)]
        begins = [(float(getattr(r, f"b{m}")) if getattr(r, f"b{m}") is not None else None) if r else None
                  for m in range(1, 13)]
        scenarios.append({"scenario": scn, "label": label, **_rollforward(opening, nets, begins)})

    # Variancias: Ending Cash del Current − cada otro escenario (por mes + total)
    cur = next((s for s in scenarios if s["scenario"] == "current"), None)
    variances = []
    if cur:
        for s in scenarios:
            if s["scenario"] == "current":
                continue
            variances.append({
                "label": f"Variance: Current − {s['label']}",
                "values": [round(cur["ending"][i] - s["ending"][i], 2) for i in range(12)],
                "total": round(cur["ending_total"] - s["ending_total"], 2),
            })

    return {
        "year": year,
        "opening_label": f"Dec-{str(year - 1)[2:]}",
        "months": [f"{mn}-{str(year)[2:]}" for mn in _MONTHS],
        "scenarios": scenarios,
        "variances": variances,
    }


async def save_forecast(session: AsyncSession, year: int, scenario: str,
                        opening: float, nets: list[float],
                        begins: list | None = None, property_code: str = "COWLCR") -> dict:
    if scenario not in _SCN_KEYS:
        raise ValueError(f"Escenario inválido: {scenario}")
    pid = await _pid(session, property_code)
    row = (await session.execute(
        select(CashFlowForecast).where(
            CashFlowForecast.property_id == pid, CashFlowForecast.year == year,
            CashFlowForecast.scenario == scenario)
    )).scalar_one_or_none()
    if row is None:
        row = CashFlowForecast(property_id=pid, year=year, scenario=scenario)
        session.add(row)
    row.opening = Decimal(str(opening or 0))
    vals = (list(nets) + [0] * 12)[:12]
    for i in range(12):
        setattr(row, f"n{i + 1}", Decimal(str(vals[i] or 0)))
    bvals = (list(begins) + [None] * 12)[:12] if begins is not None else [None] * 12
    for i in range(12):
        v = bvals[i]
        setattr(row, f"b{i + 1}", Decimal(str(v)) if v is not None and str(v) != "" else None)
    await session.commit()
    return await get_forecast(session, year, property_code=property_code)
