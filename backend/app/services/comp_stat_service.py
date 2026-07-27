"""Control de estadísticas de COMPS/IN-HOUSE por tipo de habitación.

- Tab 7.8 "YTD June 30 2026 Comps": comps históricos por (mes, categoría) de
  `comp_stat_monthly` (cargados del Excel del owner). El acumulado Ene-Jun
  reconcilia con la línea Comps del ancla de Tab 6.6 (243 RN / 346 Pax).
- Tab 7.9 "Daily Comps by Room Type": el saldo de arranque (YTD Jun-30 por tipo
  = Tab 7.8) + los comps DIARIOS por tipo del XML STATISTICS (OccupancyStat,
  market_code COM/INHOUSE) de los días posteriores, con acumulado corrido.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.room_stats import CATEGORY_ORDER, NON_REVENUE_MARKET_CODES
from app.models import CompStatMonthly, OccupancyStat, Property, RoomCategory

MONTHS_YTD = 6  # el histórico del Excel llega a junio (mes 6)


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(select(Property.id).where(Property.code == code))).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


def _sorted_cats(cats: set[str]) -> list[str]:
    known = [c for c in CATEGORY_ORDER if c in cats]
    extra = sorted(c for c in cats if c not in CATEGORY_ORDER)
    return known + extra


async def monthly_view(session: AsyncSession, property_code: str = "COWLCR", year: int = 2026) -> dict:
    """Tab 7.8: comps por (categoría × mes) + Total YTD, RN y Pax.

    Se ACTUALIZA con la ingesta diaria: los meses históricos (Ene-Jun, del Excel
    en comp_stat_monthly) mandan; los meses SIN histórico (Jul-Dic) se arman en
    vivo del XML STATISTICS (OccupancyStat COM/INHOUSE) agregando cada día en el
    mes y tipo que corresponde. Así el mismo comp que entra por el daily aparece
    acá por mes y en Tab 7.9 por día."""
    pid = await _property_id(session, property_code)
    rows = (await session.execute(
        select(CompStatMonthly).where(
            CompStatMonthly.property_id == pid, CompStatMonthly.year == year
        )
    )).scalars().all()
    hist_months = {int(r.month) for r in rows}
    by_cat: dict[str, dict] = {}
    for r in rows:
        c = by_cat.setdefault(r.room_category, {"rn": {}, "pax": {}})
        c["rn"][int(r.month)] = float(r.rn)
        c["pax"][int(r.month)] = float(r.pax)

    # Meses SIN histórico (ej. Jul-Dic): rollup en vivo del daily por (mes, tipo).
    daily = await _comps_daily_by_cat(session, pid, date(year, 1, 1), date(year, 12, 31))
    live_months: set[int] = set()
    for (d, cat), v in daily.items():
        m = d.month
        if m in hist_months:
            continue  # el Excel manda para Ene-Jun (incluye días sin XML STATISTICS)
        live_months.add(m)
        c = by_cat.setdefault(cat, {"rn": {}, "pax": {}})
        c["rn"][m] = c["rn"].get(m, 0.0) + v["rn"]
        c["pax"][m] = c["pax"].get(m, 0.0) + v["pax"]

    months = sorted(hist_months | live_months)
    cats = _sorted_cats(set(by_cat))

    categories = []
    for cat in cats:
        rn_m = {m: by_cat[cat]["rn"].get(m, 0.0) for m in months}
        pax_m = {m: by_cat[cat]["pax"].get(m, 0.0) for m in months}
        categories.append({
            "category": cat, "rn": rn_m, "pax": pax_m,
            "rn_ytd": round(sum(rn_m.values()), 2), "pax_ytd": round(sum(pax_m.values()), 2),
        })
    total = {
        "rn": {m: round(sum(c["rn"][m] for c in categories), 2) for m in months},
        "pax": {m: round(sum(c["pax"][m] for c in categories), 2) for m in months},
        "rn_ytd": round(sum(c["rn_ytd"] for c in categories), 2),
        "pax_ytd": round(sum(c["pax_ytd"] for c in categories), 2),
    }
    return {"year": year, "months": months, "categories": categories, "total": total}


async def _comps_daily_by_cat(session: AsyncSession, pid, start: date, end: date) -> dict:
    """Comps por (día, categoría) del XML STATISTICS (COM/INHOUSE) vía room_class."""
    cats = (await session.execute(
        select(RoomCategory).where(RoomCategory.property_id == pid)
    )).scalars().all()
    rc_to_cat = {c.room_class: (c.opera_short_desc or c.report_name) for c in cats if c.room_class}
    rows = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid,
            OccupancyStat.business_date >= start, OccupancyStat.business_date <= end,
            OccupancyStat.market_code.in_(NON_REVENUE_MARKET_CODES),
        )
    )).scalars().all()
    out: dict[tuple, dict] = {}
    for r in rows:
        cat = rc_to_cat.get(r.room_class or "", "Otros")
        d = out.setdefault((r.business_date, cat), {"rn": 0, "pax": 0})
        d["rn"] += int(r.rooms or 0)
        d["pax"] += int(r.persons or 0)
    return out


async def daily_view(session: AsyncSession, property_code: str = "COWLCR",
                     year: int = 2026, date_from: date | None = None,
                     date_to: date | None = None) -> dict:
    """Tab 7.9: saldo de arranque (YTD Jun-30 por tipo, de comp_stat_monthly) +
    comps diarios por tipo (COM/INHOUSE) del rango pedido, con acumulado corrido."""
    pid = await _property_id(session, property_code)

    # Opening = YTD Ene-Jun por categoría (= línea Comps de Tab 6.6, 243/346).
    mrows = (await session.execute(
        select(CompStatMonthly).where(
            CompStatMonthly.property_id == pid, CompStatMonthly.year == year,
            CompStatMonthly.month <= MONTHS_YTD,
        )
    )).scalars().all()
    opening: dict[str, dict] = {}
    for r in mrows:
        o = opening.setdefault(r.room_category, {"rn": 0.0, "pax": 0.0})
        o["rn"] += float(r.rn)
        o["pax"] += float(r.pax)

    # Daily = comps por día del XML STATISTICS, desde el 1-jul (post-corte) o el
    # rango pedido. El arranque conceptual es el 30-jun (opening).
    start = date_from or date(year, MONTHS_YTD + 1, 1)
    end = date_to or date(year, 12, 31)
    comps = await _comps_daily_by_cat(session, pid, start, end)

    cats = _sorted_cats(set(opening) | {c for (_, c) in comps})
    opening_rows = [{"category": c, "rn": round(opening.get(c, {}).get("rn", 0.0), 2),
                     "pax": round(opening.get(c, {}).get("pax", 0.0), 2)} for c in cats]
    opening_total = {"rn": round(sum(o["rn"] for o in opening_rows), 2),
                     "pax": round(sum(o["pax"] for o in opening_rows), 2)}

    days = sorted({d for (d, _) in comps})
    running = {c: {"rn": opening.get(c, {}).get("rn", 0.0), "pax": opening.get(c, {}).get("pax", 0.0)} for c in cats}
    daily = []
    for d in days:
        row = {"date": d.isoformat(), "by_cat": {}, "rn": 0.0, "pax": 0.0}
        for c in cats:
            v = comps.get((d, c), {"rn": 0, "pax": 0})
            running[c]["rn"] += v["rn"]
            running[c]["pax"] += v["pax"]
            row["by_cat"][c] = {"rn": v["rn"], "pax": v["pax"]}
            row["rn"] += v["rn"]
            row["pax"] += v["pax"]
        daily.append(row)
    running_total = {"rn": round(sum(r["rn"] for r in running.values()), 2),
                     "pax": round(sum(r["pax"] for r in running.values()), 2)}
    running_rows = [{"category": c, "rn": round(running[c]["rn"], 2), "pax": round(running[c]["pax"], 2)} for c in cats]

    return {
        "categories": cats,
        "opening_label": f"YTD {date(year, MONTHS_YTD, 30).isoformat()}",
        "opening": opening_rows, "opening_total": opening_total,
        "daily": daily,
        "running": running_rows, "running_total": running_total,
    }
