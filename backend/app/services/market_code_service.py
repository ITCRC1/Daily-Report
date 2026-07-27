"""Tab 7.10 Market Codes — pivote por market code sobre un rango de fechas.

- Rooms (room nights) y Pax: del XML STATISTICS (`fact_occupancy_stat`).
- Room Revenue (cargo de Accommodation) y Revenue Total (todo `type='REVENUE'`):
  del XML Revenue (`fact_opera_txn_detail`, que trae market_code por transacción).

Se une con `dim_market_code` para Description (name) y Market Group (kpi_group).
Un market code sin fila en el catálogo cae en Market Group = "Unmapped" (§10: no
se pierde en silencio). El código vacío se muestra como "(blank)".
"""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketCode, OccupancyStat, OperaTxnDetail, Property

# Agrupación de negocio pedida por el owner (Tab 7.10, 2ª tabla). Códigos fuera
# del mapa caen en "Other" para que el total cierre (§10, no se pierde nada).
GROUP_MAP = {
    "DIR": "Direct", "WEB": "Direct", "BAR": "Direct",
    "OTA": "OTA",
    "TAFIT": "Travel Agency", "TAGP": "Travel Agency", "TA": "Travel Agency",
    "FNF": "Groups", "RET": "Groups", "SOC": "Groups", "WED": "Groups",
}
GROUP_ORDER = ["Direct", "OTA", "Travel Agency", "Groups"]


async def _pid(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def market_code_report(session: AsyncSession, property_code: str = "COWLCR",
                             date_from: date_cls | None = None,
                             date_to: date_cls | None = None) -> dict:
    pid = await _pid(session, property_code)

    # Rooms / Pax (XML STATISTICS)
    occ = (await session.execute(
        select(OccupancyStat.market_code,
               func.coalesce(func.sum(OccupancyStat.rooms), 0),
               func.coalesce(func.sum(OccupancyStat.persons), 0))
        .where(OccupancyStat.property_id == pid,
               OccupancyStat.business_date >= date_from,
               OccupancyStat.business_date <= date_to)
        .group_by(OccupancyStat.market_code)
    )).all()
    occ_map = {(mc or ""): {"rooms": int(r or 0), "pax": int(p or 0)} for mc, r, p in occ}

    # Room Revenue (Accommodation) / Revenue Total (XML Revenue, solo type='REVENUE')
    is_room = func.lower(func.coalesce(OperaTxnDetail.description, "")).like("%accomod%")
    rev = (await session.execute(
        select(OperaTxnDetail.market_code,
               func.coalesce(func.sum(case((is_room, OperaTxnDetail.trx_amount), else_=0)), 0),
               func.coalesce(func.sum(OperaTxnDetail.trx_amount), 0))
        .where(OperaTxnDetail.property_id == pid,
               OperaTxnDetail.business_date >= date_from,
               OperaTxnDetail.business_date <= date_to,
               OperaTxnDetail.type == "REVENUE")
        .group_by(OperaTxnDetail.market_code)
    )).all()
    rev_map = {(mc or ""): {"room_rev": float(rr or 0), "total": float(tt or 0)} for mc, rr, tt in rev}

    dims = (await session.execute(
        select(MarketCode).where(MarketCode.property_id == pid)
    )).scalars().all()
    dim_map = {d.code: d for d in dims}

    codes = set(occ_map) | set(rev_map) | set(dim_map)
    rows = []
    for code in codes:
        o = occ_map.get(code, {})
        r = rev_map.get(code, {})
        d = dim_map.get(code)
        rows.append({
            "market_code": code if code else "(blank)",
            "description": d.name if d else None,
            "market_group": (d.kpi_group if d else None) or "Unmapped",
            "pax": o.get("pax", 0),
            "rooms": o.get("rooms", 0),
            "room_revenue": round(r.get("room_rev", 0.0), 2),
            "revenue_total": round(r.get("total", 0.0), 2),
        })
    rows.sort(key=lambda x: (-x["revenue_total"], x["market_code"]))

    total = {
        "pax": sum(x["pax"] for x in rows),
        "rooms": sum(x["rooms"] for x in rows),
        "room_revenue": round(sum(x["room_revenue"] for x in rows), 2),
        "revenue_total": round(sum(x["revenue_total"] for x in rows), 2),
    }

    # 2ª tabla: rollup por grupo de negocio (Direct/OTA/Travel Agency/Groups + Other)
    gacc = {g: {"pax": 0, "rooms": 0, "room_revenue": 0.0, "revenue_total": 0.0}
            for g in [*GROUP_ORDER, "Other"]}
    for x in rows:
        g = GROUP_MAP.get(x["market_code"].upper(), "Other")
        a = gacc[g]
        a["pax"] += x["pax"]; a["rooms"] += x["rooms"]
        a["room_revenue"] += x["room_revenue"]; a["revenue_total"] += x["revenue_total"]
    order = [*GROUP_ORDER] + (["Other"] if any(gacc["Other"].values()) else [])
    groups = [{"group": g, "pax": gacc[g]["pax"], "rooms": gacc[g]["rooms"],
               "room_revenue": round(gacc[g]["room_revenue"], 2),
               "revenue_total": round(gacc[g]["revenue_total"], 2)} for g in order]

    return {
        "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
        "rows": rows, "total": total, "groups": groups,
    }
