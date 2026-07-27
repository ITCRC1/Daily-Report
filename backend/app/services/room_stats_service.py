"""Tab 6.6 -- Rooms Statistics YTD por categoría, con ancla editable
(room_stat_opening) + acumulado diario real de fact_room_stat (§statroomtype,
Tab 1). YTD a cualquier día = ancla vigente por categoría + fact_room_stat
de los días posteriores al ancla, hasta el día pedido (§10, nunca se fabrica
el detalle diario que no existe -- el ancla es la forma explícita de decir
"a partir de acá no tengo el desglose diario, solo el acumulado")."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.room_stats import CATEGORY_ORDER, NON_REVENUE_MARKET_CODES, room_stats_rollup
from app.models import OccupancyStat, Property, RoomCategory, RoomStat, RoomStatOpening

# Fila especial (no es categoría) para el ancla acumulado de comps/in-house
# hasta el corte -- Tab 6.6. Reusa los mismos campos del ancla (stay_rooms=RN
# comp, stay_persons=Pax comp, revenue=revenue comp; physical_rooms n/a).
COMPS_SENTINEL = "Comps/In-House"


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


def _opening_row(r: RoomStatOpening) -> dict:
    return {
        "id": str(r.id), "room_category": r.room_category,
        "anchor_date": r.anchor_date.isoformat(),
        "revenue": float(r.revenue), "stay_rooms": float(r.stay_rooms),
        "stay_persons": float(r.stay_persons), "physical_rooms": float(r.physical_rooms),
    }


async def _units_by_category(session: AsyncSession, pid) -> dict[str, int]:
    rows = (await session.execute(
        select(RoomCategory).where(RoomCategory.property_id == pid)
    )).scalars().all()
    return {r.opera_short_desc: (r.units or 0) for r in rows if r.opera_short_desc}


async def units_by_category(session: AsyncSession, property_code: str = "COWLCR") -> dict[str, int]:
    """Units (habitaciones físicas) por categoría -- Tab 6.7, no depende de período."""
    pid = await _property_id(session, property_code)
    return await _units_by_category(session, pid)


async def list_openings(session: AsyncSession, property_code: str = "COWLCR") -> list[dict]:
    """Un ancla por categoría (CATEGORY_ORDER), con units para contexto de UI --
    categorías sin ancla guardada todavía se devuelven en 0."""
    pid = await _property_id(session, property_code)
    units = await _units_by_category(session, pid)
    rows = (await session.execute(
        select(RoomStatOpening).where(RoomStatOpening.property_id == pid)
    )).scalars().all()
    by_cat = {r.room_category: _opening_row(r) for r in rows}
    out = []
    for cat in CATEGORY_ORDER:
        row = by_cat.get(cat) or {
            "id": None, "room_category": cat, "anchor_date": None,
            "revenue": 0.0, "stay_rooms": 0.0, "stay_persons": 0.0, "physical_rooms": 0.0,
        }
        row["units"] = units.get(cat, 0)
        out.append(row)
    # Fila editable de comps/in-house (acumulado hasta el corte) -- va al final.
    comps = by_cat.get(COMPS_SENTINEL) or {
        "id": None, "room_category": COMPS_SENTINEL, "anchor_date": None,
        "revenue": 0.0, "stay_rooms": 0.0, "stay_persons": 0.0, "physical_rooms": 0.0,
    }
    comps["units"] = 0
    out.append(comps)
    return out


async def upsert_openings(session: AsyncSession, items: list[dict], property_code: str = "COWLCR") -> list[dict]:
    """Guarda el ancla editable de Tab 6.6 -- upsert por (property_id, room_category)."""
    pid = await _property_id(session, property_code)
    existing = {
        r.room_category: r for r in (await session.execute(
            select(RoomStatOpening).where(RoomStatOpening.property_id == pid)
        )).scalars().all()
    }
    for item in items:
        cat = item.get("room_category")
        if cat not in CATEGORY_ORDER and cat != COMPS_SENTINEL:
            raise ValueError(f"Categoría desconocida: '{cat}'.")
        anchor_date = item.get("anchor_date")
        if not anchor_date:
            raise ValueError(f"anchor_date es obligatorio para '{cat}'.")
        if isinstance(anchor_date, str):
            anchor_date = date.fromisoformat(anchor_date)
        row = existing.get(cat)
        if row is None:
            row = RoomStatOpening(property_id=pid, room_category=cat, anchor_date=anchor_date)
            session.add(row)
            existing[cat] = row
        row.anchor_date = anchor_date
        row.revenue = item.get("revenue") or 0
        row.stay_rooms = item.get("stay_rooms") or 0
        row.stay_persons = item.get("stay_persons") or 0
        row.physical_rooms = item.get("physical_rooms") or 0
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError("Conflicto guardando el ancla YTD (categoría duplicada).")
    return await list_openings(session, property_code=property_code)


async def room_stats_ytd(session: AsyncSession, as_of: date, property_code: str = "COWLCR") -> dict:
    """Rollup YTD por categoría: ancla vigente (si la hay y es <= as_of) +
    fact_room_stat real de (anchor_date, as_of]. Categorías sin ancla usan
    solo fact_room_stat del año hasta as_of (mismo criterio que Tab 3/3.1/4).

    Las categorías se muestran BRUTAS (con comps dentro). El neteo de comps/
    in-house del ADR se hace a nivel TOTAL, no por categoría, porque el tramo
    pre-corte es un acumulado del ancla sin desglose por categoría -- no se
    puede atribuir a categorías sin inventar (§10). Comps YTD a netear =
    ancla `Comps/In-House` (pre-corte, editable en Tab 6.6) + comps reales del
    XML STATISTICS de los días POSTERIORES al corte (COM/INHOUSE). Se devuelve
    `net` (bruto − comps, con ADR limpio) y `comps_line` para la reconciliación."""
    pid = await _property_id(session, property_code)
    units = await _units_by_category(session, pid)
    openings = (await session.execute(
        select(RoomStatOpening).where(RoomStatOpening.property_id == pid)
    )).scalars().all()

    opening_by_cat: dict[str, dict] = {}
    delta_start_by_cat: dict[str, date] = {}
    comps_anchor: dict | None = None
    comps_cutoff: date | None = None
    year_start = date(as_of.year, 1, 1)
    for o in openings:
        if o.room_category == COMPS_SENTINEL:
            if o.anchor_date <= as_of:
                comps_anchor = {"stay_rooms": float(o.stay_rooms),
                                "stay_persons": float(o.stay_persons), "revenue": float(o.revenue)}
                comps_cutoff = o.anchor_date
            continue
        if o.anchor_date > as_of:
            continue  # ancla posterior al día pedido -- todavía no aplica
        opening_by_cat[o.room_category] = {
            "revenue": float(o.revenue), "stay_rooms": float(o.stay_rooms),
            "stay_persons": float(o.stay_persons), "physical_rooms": float(o.physical_rooms),
        }
        delta_start_by_cat[o.room_category] = o.anchor_date

    earliest_start = min([year_start, *delta_start_by_cat.values()]) if delta_start_by_cat else year_start
    rows = (await session.execute(
        select(RoomStat).where(
            RoomStat.property_id == pid,
            RoomStat.business_date >= earliest_start,
            RoomStat.business_date <= as_of,
        )
    )).scalars().all()

    records = []
    for r in rows:
        cat = r.room_category
        start_excl = delta_start_by_cat.get(cat, year_start - timedelta(days=1))
        if r.business_date <= start_excl:
            continue  # ya cubierto por el ancla de esa categoría, o fuera de año
        records.append({
            "short_description": cat, "room_revenue": r.room_revenue,
            "stay_rooms": r.stay_rooms, "stay_persons": r.stay_persons,
            "physical_rooms": r.physical_rooms,
        })

    result = room_stats_rollup(records, opening=opening_by_cat)  # BRUTO por categoría
    for c in result["categories"]:
        c["units"] = units.get(c["category"], 0)

    # Comps YTD: STATISTICS post-corte (días > corte del ancla comps, o todo el
    # año si no hay ancla comps) + ancla comps (pre-corte).
    stat_start = (comps_cutoff + timedelta(days=1)) if comps_cutoff else year_start
    post_rows = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid,
            OccupancyStat.market_code.in_(NON_REVENUE_MARKET_CODES),
            OccupancyStat.business_date >= stat_start,
            OccupancyStat.business_date <= as_of,
        )
    )).scalars().all()
    post_rooms = sum(int(r.rooms or 0) for r in post_rows)
    post_pers = sum(int(r.persons or 0) for r in post_rows)
    a_rooms = comps_anchor["stay_rooms"] if comps_anchor else 0.0
    a_pers = comps_anchor["stay_persons"] if comps_anchor else 0.0
    a_rev = comps_anchor["revenue"] if comps_anchor else 0.0

    gross = result["overall"]
    comp_rooms = post_rooms + a_rooms
    comp_pers = post_pers + a_pers
    comp_rev = a_rev  # STATISTICS no trae monto; el revenue del comp = el del ancla
    net_rooms = gross["stay_rooms"] - comp_rooms
    net_pers = gross["stay_persons"] - comp_pers
    net_rev = gross["revenue"] - comp_rev
    net = {
        "revenue": round(net_rev, 2), "stay_rooms": net_rooms, "stay_persons": net_pers,
        "physical_rooms": gross["physical_rooms"], "units": sum(units.values()),
        "occupancy_pct": round(net_rooms / gross["physical_rooms"], 4) if gross["physical_rooms"] else 0.0,
        "adr": round(net_rev / net_rooms, 2) if net_rooms else 0.0,
    }
    comps_line = {
        "stay_rooms": comp_rooms, "stay_persons": comp_pers, "revenue": round(comp_rev, 2),
        "anchor_rooms": a_rooms, "anchor_persons": a_pers, "anchor_revenue": round(a_rev, 2),
        "post_cutoff_rooms": post_rooms, "post_cutoff_persons": post_pers,
        "cutoff": comps_cutoff.isoformat() if comps_cutoff else None,
    }
    return {
        "as_of": as_of.isoformat(),
        "year_start": year_start.isoformat(),
        "openings": {cat: v | {"anchor_date": delta_start_by_cat[cat].isoformat()} for cat, v in opening_by_cat.items()},
        **result,
        "comps_line": comps_line,
        "net": net,
    }


async def daily_view_for_pid(session: AsyncSession, pid,
                             date_from: date | None = None, date_to: date | None = None) -> list[dict]:
    """Tab 7.3 / Power Query -- un registro por (día, categoría). El ancla YTD
    de cada categoría (Tab 6.6, room_stat_opening) se muestra como un único
    registro "histórico" fechado en su `anchor_date` (ej. 2026-06-30) -- así
    el hueco de días sin XML statroomtype ingestado (todo lo anterior al
    ancla) no aparece vacío, aparece resumido en ese corte. Los días reales
    de fact_room_stat POSTERIORES al ancla de esa categoría se listan tal
    cual, sin acumular más -- mismo criterio de "excluir <= anchor_date" que
    usa room_stats_ytd(), para no duplicar lo que el ancla ya incluye."""
    openings = (await session.execute(
        select(RoomStatOpening).where(RoomStatOpening.property_id == pid)
    )).scalars().all()
    anchor_date_by_cat = {o.room_category: o.anchor_date for o in openings}

    # Comps/in-house por (día, categoría) del XML STATISTICS (COM/INHOUSE), vía
    # room_class -> categoría (mismo mapeo que _comps_by_category de Tab 3/4/6.6).
    # Se RESTAN de RN/Pax para que la tarifa (ADR = Revenue / RN) no salga diluida
    # por habitaciones cortesía (que no aportan revenue). Pedido del owner 2026-07-11.
    cats = (await session.execute(
        select(RoomCategory).where(RoomCategory.property_id == pid)
    )).scalars().all()
    room_class_to_category = {c.room_class: (c.opera_short_desc or c.report_name) for c in cats if c.room_class}
    comp_rows = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid,
            OccupancyStat.market_code.in_(NON_REVENUE_MARKET_CODES),
        )
    )).scalars().all()
    comps_by_day_cat: dict[tuple, dict] = {}
    for r in comp_rows:
        cat = room_class_to_category.get(r.room_class or "", "Otros")
        c = comps_by_day_cat.setdefault((r.business_date, cat), {"rooms": 0, "persons": 0})
        c["rooms"] += int(r.rooms or 0)
        c["persons"] += int(r.persons or 0)

    # Anclas de Tab 6.6: las categorías van en BRUTO; el ancla `Comps/In-House`
    # (acumulado pre-corte, no desglosable por categoría §10) va en NEGATIVO para
    # que la fila de su fecha netee al total (bruto − comps = neto).
    def _opening_row_out(o) -> dict:
        sign = -1.0 if o.room_category == COMPS_SENTINEL else 1.0
        return {
            "date": o.anchor_date.isoformat(), "category": o.room_category,
            "revenue": float(o.revenue),
            "stay_rooms": sign * float(o.stay_rooms),
            "stay_persons": sign * float(o.stay_persons),
            "physical_rooms": float(o.physical_rooms),
        }
    out = [_opening_row_out(o) for o in openings]

    rows = (await session.execute(
        select(RoomStat).where(RoomStat.property_id == pid).order_by(RoomStat.business_date)
    )).scalars().all()
    for r in rows:
        anchor_date = anchor_date_by_cat.get(r.room_category)
        if anchor_date and r.business_date <= anchor_date:
            continue  # ya incluido en el corte histórico de esa categoría
        # Neto de comps de ESE día y categoría (post-corte, desglose real del XML).
        comp = comps_by_day_cat.get((r.business_date, r.room_category), {"rooms": 0, "persons": 0})
        out.append({
            "date": r.business_date.isoformat(), "category": r.room_category,
            "revenue": float(r.room_revenue),
            "stay_rooms": float(r.stay_rooms) - comp["rooms"],
            "stay_persons": float(r.stay_persons) - comp["persons"],
            "physical_rooms": float(r.physical_rooms),
        })

    if date_from:
        out = [x for x in out if x["date"] >= date_from.isoformat()]
    if date_to:
        out = [x for x in out if x["date"] <= date_to.isoformat()]
    out.sort(key=lambda x: (x["date"], x["category"]))
    return out


async def daily_view(session: AsyncSession, property_code: str = "COWLCR") -> list[dict]:
    """Tab 7.3 -- wrapper de `daily_view_for_pid` que resuelve la propiedad por código."""
    pid = await _property_id(session, property_code)
    return await daily_view_for_pid(session, pid)
