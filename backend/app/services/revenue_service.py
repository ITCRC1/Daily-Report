"""Servicio de Revenue (etapa 2, Tab 3 — Daily Revenue Report).

Arma el 'Summary' del golden: por cada centro de revenue, Today / MTD / Full
Month con Actual, Budget y Varianza. El Actual sale del pivote diario del motor
(engine/revenue.py) sobre las líneas de Integrity (cuenta 4%, cr−db, §5.3).

Budget: conectado a `fact_budget` (derivado en Tab 6.1, §3 — mensual ÷ días del
mes). El presupuesto se carga por DEPARTAMENTO (outlet, dim_department), que
coincide 1:1 con las columnas de Daily (§5.1b). Weekly usa naturaleza (§5.1a,
abre Rooms/Rooms Others y Sustainable Fee/Misc. Rev Others) — el budget no
tiene esa granularidad, así que el outlet completo se asigna a la columna
"madre" (Rooms, Sustainable Fee) y las columnas "Others" quedan en 0 de
presupuesto (no hay de dónde derivarlas, no se inventa un reparto).
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date as date_cls

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.revenue import (
    OUTPUT_COLUMNS,
    WEEKLY_COLUMNS,
    daily_revenue,
    lines_from_integrity,
    room_revenue_by_category,
    weekly_pivot,
)
from app.engine.room_stats import (
    NON_REVENUE_MARKET_CODES, market_segment_rollup, opera_daily_vs_history, room_stats_rollup,
)
from app.models import (
    AppConfig, Budget, BudgetMonthly, Department, Forecast, IntegrityLine,
    MarketCode, OccupancyStat, Property, RevenueActualDaily, RoomCategory, RoomStat, WeekCalendar,
)
from app.services import room_stats_service

# outlet (output_column, §5.1b) -> columna Weekly correspondiente (§5.1a). Las
# columnas *_Others no tienen contraparte en el budget por departamento.
_OUTLET_TO_WEEKLY_COL = {
    "Rooms": "Rooms", "SPA": "SPA", "Retail-Gift Shop": "Retail-Gift Shop",
    "Tours": "Tours", "Transportation": "Transportation", "Laundry": "Laundry",
    "Innoceana": "Innoceana", "Crowther Lab": "Crowther Lab",
    "Sustainable Fee": "Sustainable Fee", "F&B": "F&B",
}

# cost_center (dim_department, Tab 6.4) -> columna Weekly (§5.1a) — usado como
# respaldo para días sin ingesta real Opera/Integrity (§10, no fabrica datos:
# solo rellena con lo que Bismark ya cargó en bloque en 6.4).
_DEPT_TO_WEEKLY_COL = {
    "0110": "Rooms", "ROOMS-OTH": "Rooms Others",
    "FB-FOOD": "F&B", "FB-BEV": "F&B", "FB-MISC": "F&B",
    "0140": "SPA", "0150": "Tours", "0151": "Retail-Gift Shop",
    "0152": "Transportation", "0160": "Laundry", "0155": "Innoceana",
    "0156": "Crowther Lab", "0170": "Sustainable Fee", "MISC-REV-OTH": "Misc. Rev Others",
}
_DEPT_TO_FB_SUB = {"FB-FOOD": "food", "FB-BEV": "beverage", "FB-MISC": "misc"}

# Inverso de _DEPT_TO_WEEKLY_COL (columna Weekly -> dept_code de 6.4), para
# `merged_revenue_actual` (Tab 7.1 / Power Query "revenue_actual") -- mapea el
# pivote de ingesta real de vuelta al mismo esquema de dept_code que usa la
# grilla masiva de 6.4, para poder combinarlos día por día sin romper el
# pivot que ya arma el frontend.
_WEEKLY_COL_TO_DEPT = {
    "Rooms": "0110", "Rooms Others": "ROOMS-OTH",
    "SPA": "0140", "Tours": "0150", "Retail-Gift Shop": "0151",
    "Transportation": "0152", "Laundry": "0160", "Innoceana": "0155",
    "Crowther Lab": "0156", "Sustainable Fee": "0170", "Misc. Rev Others": "MISC-REV-OTH",
}
_FB_SUB_TO_DEPT = {"food": "FB-FOOD", "beverage": "FB-BEV", "misc": "FB-MISC"}

# Igual que _DEPT_TO_WEEKLY_COL pero para el esquema Daily (§5.1b, outlet
# colapsado): Rooms Others cae dentro de "Rooms". "Misc. Rev Others" (MISC-REV-OTH)
# y "Misc. Revenue" (MISC-REV) YA NO se pliegan en Sustainable Fee -- van a la
# línea propia "Misc. Revenue" (misma que Tab 4), así Sustainable Fee = solo 0170
# y ambos reportes reconcilian. Ver _DEPT_TO_DAILY_MISC.
_DEPT_TO_DAILY_COL = {
    "0110": "Rooms", "ROOMS-OTH": "Rooms",
    "FB-FOOD": "F&B", "FB-BEV": "F&B", "FB-MISC": "F&B",
    "0140": "SPA", "0150": "Tours", "0151": "Retail-Gift Shop",
    "0152": "Transportation", "0160": "Laundry", "0155": "Innoceana",
    "0156": "Crowther Lab", "0170": "Sustainable Fee",
}
# Depts del respaldo 6.4 que caen en la línea "Misc. Revenue" (espeja el
# `week_cols["Misc. Rev Others"] + otros` de Tab 4).
_DEPT_TO_DAILY_MISC = {"MISC-REV-OTH", "MISC-REV"}


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _integrity_by_day(session, pid, month_start, upto) -> dict[date_cls, list[dict]]:
    """Líneas de Integrity del mes (hasta `upto`), agrupadas por día."""
    rows = (await session.execute(
        select(IntegrityLine).where(
            IntegrityLine.property_id == pid,
            IntegrityLine.business_date >= month_start,
            IntegrityLine.business_date <= upto,
        )
    )).scalars().all()
    by_day: dict[date_cls, list[dict]] = defaultdict(list)
    for r in rows:
        by_day[r.business_date].append({
            "cuenta": r.cuenta, "nombre_cuenta": r.nombre_cuenta,
            "cred_usd": r.cred_usd, "deb_usd": r.deb_usd,
        })
    return by_day


async def _room_stats(session, pid, start, end) -> list[RoomStat]:
    return (await session.execute(
        select(RoomStat).where(
            RoomStat.property_id == pid,
            RoomStat.business_date >= start, RoomStat.business_date <= end,
        )
    )).scalars().all()


async def _total_rooms(session, pid) -> int:
    """Habitaciones físicas del hotel (app_config.total_rooms, default 30) --
    §Bismark confirmado: los reportes SIEMPRE usan este número para Occupancy%/
    ADR, sin importar qué disponibilidad reporte Opera ese día. Cualquier
    diferencia real se documenta como hallazgo (run_audit), nunca se fabrica
    en silencio pero tampoco mueve el número reportado."""
    row = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == "total_rooms")
    )).scalar_one_or_none()
    try:
        return int(row.value) if row else 30
    except (TypeError, ValueError):
        return 30


async def _kpis_for_day(session, pid, bdate) -> dict:
    """Pax / RN / ADR / Occupancy del día. Disponibilidad = total_rooms fijo
    (§Bismark) si hubo ingesta STATISTICS ese día; 0 si no hay ingesta (no se
    fabrica un día sin datos)."""
    stats = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid, OccupancyStat.business_date == bdate
        )
    )).scalars().all()
    rn = sum(s.rooms for s in stats)
    pax = sum(s.persons for s in stats)
    available = await _total_rooms(session, pid) if stats else 0
    return {"rn": rn, "pax": pax, "available_rooms": available}


async def _dept_names_by_cost_center(session, pid) -> dict[str, str | None]:
    rows = (await session.execute(
        select(Department).where(Department.property_id == pid)
    )).scalars().all()
    return {d.cost_center: d.outlet_name for d in rows if d.cost_center}


async def merged_revenue_actual(session: AsyncSession, pid, date_from: date_cls | None,
                                date_to: date_cls | None) -> list[dict]:
    """Tab 7.1 / Power Query "revenue_actual" -- Revenue Actual Daily, pero
    combinando día por día la ingesta real Opera/Integrity (Tabs 1-2, fuente
    PRIMARIA cuando existe, mismo pivote naturaleza que usa Tab 4 Weekly --
    weekly_pivot) con el respaldo de la grilla masiva de 6.4 para los días
    SIN ingesta real -- NUNCA se suman ambas fuentes el mismo día (§10, mismo
    criterio ya usado en daily_report/weekly_report). Sin esto, un día recién
    ingestado en Tab 1 (ej. hoy) aparecía vacío en 7.1 porque la grilla de
    6.4 nunca lo tuvo cargado."""
    dept_names = await _dept_names_by_cost_center(session, pid)

    iq = select(IntegrityLine).where(IntegrityLine.property_id == pid)
    if date_from:
        iq = iq.where(IntegrityLine.business_date >= date_from)
    if date_to:
        iq = iq.where(IntegrityLine.business_date <= date_to)
    integrity_by_day: dict[date_cls, list[dict]] = defaultdict(list)
    for r in (await session.execute(iq)).scalars().all():
        integrity_by_day[r.business_date].append({
            "cuenta": r.cuenta, "nombre_cuenta": r.nombre_cuenta,
            "cred_usd": r.cred_usd, "deb_usd": r.deb_usd,
        })

    aq = (select(RevenueActualDaily, Department.cost_center)
          .join(Department, RevenueActualDaily.dept_id == Department.id)
          .where(RevenueActualDaily.property_id == pid))
    if date_from:
        aq = aq.where(RevenueActualDaily.date >= date_from)
    if date_to:
        aq = aq.where(RevenueActualDaily.date <= date_to)
    actual_by_day: dict[date_cls, list] = defaultdict(list)
    for r, cost_center in (await session.execute(aq)).all():
        actual_by_day[r.date].append((r, cost_center))

    # Comps/in-house por día (COM/INHOUSE del XML STATISTICS) -- se restan del
    # rooms_sold/total_pax para que el ADR/%Occ que arma la tabla de 7.1/7.2
    # sea de habitaciones que pagan (mismo criterio que §5.2 / Tab 6.6 / 7.3).
    cq = select(OccupancyStat).where(
        OccupancyStat.property_id == pid,
        OccupancyStat.market_code.in_(NON_REVENUE_MARKET_CODES),
    )
    if date_from:
        cq = cq.where(OccupancyStat.business_date >= date_from)
    if date_to:
        cq = cq.where(OccupancyStat.business_date <= date_to)
    comps_by_day: dict[date_cls, dict] = defaultdict(lambda: {"rn": 0, "pax": 0})
    for r in (await session.execute(cq)).scalars().all():
        comps_by_day[r.business_date]["rn"] += int(r.rooms or 0)
        comps_by_day[r.business_date]["pax"] += int(r.persons or 0)

    out: list[dict] = []
    for d in sorted(set(integrity_by_day) | set(actual_by_day)):
        if d in integrity_by_day:
            pivot = weekly_pivot(lines_from_integrity(integrity_by_day[d]))
            kpis = await _kpis_for_day(session, pid, d)
            for col, dept_code in _WEEKLY_COL_TO_DEPT.items():
                row = {
                    "date": d.isoformat(), "dept_code": dept_code,
                    "dept_name": dept_names.get(dept_code), "amount_usd": pivot["columns"].get(col, 0.0),
                    "rooms_sold": None, "total_pax": None, "available_rooms": None,
                }
                if dept_code == "0110":
                    row["rooms_sold"] = max(float(kpis["rn"]) - comps_by_day[d]["rn"], 0.0)
                    row["total_pax"] = max(float(kpis["pax"]) - comps_by_day[d]["pax"], 0.0)
                    row["available_rooms"] = float(kpis["available_rooms"])
                out.append(row)
            for sub, dept_code in _FB_SUB_TO_DEPT.items():
                out.append({
                    "date": d.isoformat(), "dept_code": dept_code,
                    "dept_name": dept_names.get(dept_code),
                    "amount_usd": pivot["fb_detail"].get(sub, 0.0),
                    "rooms_sold": None, "total_pax": None, "available_rooms": None,
                })
        else:
            for r, cost_center in actual_by_day[d]:
                # rooms_sold/total_pax vienen brutos del grid 6.4 -> netear comps del día.
                rs_net = (max(float(r.rooms_sold) - comps_by_day[d]["rn"], 0.0)
                          if r.rooms_sold is not None else None)
                px_net = (max(float(r.total_pax) - comps_by_day[d]["pax"], 0.0)
                          if r.total_pax is not None else None)
                out.append({
                    "date": d.isoformat(), "dept_code": cost_center,
                    "dept_name": dept_names.get(cost_center), "amount_usd": float(r.amount_usd),
                    "rooms_sold": rs_net,
                    "total_pax": px_net,
                    "available_rooms": float(r.available_rooms) if r.available_rooms is not None else None,
                })
    return out


def _empty_cols() -> dict[str, float]:
    return {c: 0.0 for c in OUTPUT_COLUMNS}


async def _budget_by_outlet_column(session, pid, start, end) -> dict[str, float]:
    """Σ fact_budget.amount_usd en el rango, agrupado por output_column del
    departamento (§5.1b) — la misma clasificación que usa Daily Revenue."""
    rows = (await session.execute(
        select(Budget, Department.output_column)
        .join(Department, Budget.dept_id == Department.id)
        .where(Budget.property_id == pid, Budget.date >= start, Budget.date <= end)
    )).all()
    totals: dict[str, float] = defaultdict(float)
    for budget_row, output_column in rows:
        totals[output_column] += float(budget_row.amount_usd)
    return {k: round(v, 2) for k, v in totals.items()}


async def _budget_by_dept_cost_center(session, pid, start, end) -> dict[str, float]:
    """Σ fact_budget.amount_usd en el rango, agrupado por cost_center del
    departamento (§5.1b) -- a diferencia de `_budget_by_outlet_column`, NO
    colapsa FB-FOOD/FB-BEV/FB-MISC en un solo 'F&B' (para "On-Property
    Production Detail", que necesita el budget de cada uno por separado)."""
    rows = (await session.execute(
        select(Budget, Department.cost_center)
        .join(Department, Budget.dept_id == Department.id)
        .where(Budget.property_id == pid, Budget.date >= start, Budget.date <= end)
    )).all()
    totals: dict[str, float] = defaultdict(float)
    for budget_row, cost_center in rows:
        totals[cost_center] += float(budget_row.amount_usd)
    return {k: round(v, 2) for k, v in totals.items()}


async def _forecast_by_outlet_column(session, pid, start, end) -> dict[str, float]:
    """Σ fact_forecast.amount_usd en el rango, agrupado por output_column --
    gemelo de `_budget_by_outlet_column`, para la columna Forecast del cuadro
    FULL MONTH RESULT (Tab 3)."""
    rows = (await session.execute(
        select(Forecast, Department.output_column)
        .join(Department, Forecast.dept_id == Department.id)
        .where(Forecast.property_id == pid, Forecast.date >= start, Forecast.date <= end)
    )).all()
    totals: dict[str, float] = defaultdict(float)
    for forecast_row, output_column in rows:
        totals[output_column] += float(forecast_row.amount_usd)
    return {k: round(v, 2) for k, v in totals.items()}


async def _forecast_by_dept_cost_center(session, pid, start, end) -> dict[str, float]:
    """Igual que arriba pero por cost_center (no colapsa FB-FOOD/BEV/MISC)."""
    rows = (await session.execute(
        select(Forecast, Department.cost_center)
        .join(Department, Forecast.dept_id == Department.id)
        .where(Forecast.property_id == pid, Forecast.date >= start, Forecast.date <= end)
    )).all()
    totals: dict[str, float] = defaultdict(float)
    for forecast_row, cost_center in rows:
        totals[cost_center] += float(forecast_row.amount_usd)
    return {k: round(v, 2) for k, v in totals.items()}


async def _budget_adr_occ(session, pid, year: int, month_from: int, month_to: int) -> dict:
    """ADR/Occupancy% presupuestados (general, no por tipo de habitación --
    Integrity Room Revenue + Room Statistics son la fuente 'oficial' para
    controlar tarifas; no hace falta budget por room-type). Ponderado por
    `rooms_occupied` presupuestado de cada mes cuando el rango cruza más de
    un mes (ej. YTD)."""
    rows = (await session.execute(
        select(BudgetMonthly, Department.cost_center)
        .join(Department, BudgetMonthly.dept_id == Department.id)
        .where(BudgetMonthly.property_id == pid, BudgetMonthly.year == year,
               BudgetMonthly.month >= month_from, BudgetMonthly.month <= month_to,
               Department.cost_center == "0110")
    )).all()
    total_rn = sum(float(r.rooms_occupied or 0) for r, _ in rows)
    total_revenue = sum(float(r.adr or 0) * float(r.rooms_occupied or 0) for r, _ in rows)
    total_available = sum(float(r.available_rooms or 0) for r, _ in rows)
    return {
        "adr": round(total_revenue / total_rn, 2) if total_rn else 0.0,
        "occupancy_pct": round(total_rn / total_available, 4) if total_available else 0.0,
    }


async def _budget_room_stats_for_range(session, pid, start: date_cls, end: date_cls) -> dict:
    """RN/Pax/Disponibles/ADR presupuestados para un rango arbitrario de días
    (semana, YTD parcial) -- prorratea `BudgetMonthly` (mensual) por fracción
    de días superpuestos con cada mes tocado por el rango. Necesario porque
    `fact_budget` solo deriva el monto $ diario (§3), no las estadísticas de
    habitaciones -- Tab 4 (Weekly/YTD) las necesita día-fraccionadas, a
    diferencia de Tab 3 (Today/MTD, que caen en un solo mes)."""
    rows = (await session.execute(
        select(BudgetMonthly, Department.cost_center)
        .join(Department, BudgetMonthly.dept_id == Department.id)
        .where(BudgetMonthly.property_id == pid, Department.cost_center == "0110")
    )).all()
    total_rn = total_pax = total_available = total_revenue = 0.0
    for r, _ in rows:
        days_in_month = calendar.monthrange(r.year, r.month)[1]
        month_start = date_cls(r.year, r.month, 1)
        month_end = date_cls(r.year, r.month, days_in_month)
        overlap_start = max(start, month_start)
        overlap_end = min(end, month_end)
        if overlap_start > overlap_end:
            continue
        frac = ((overlap_end - overlap_start).days + 1) / days_in_month
        total_rn += float(r.rooms_occupied or 0) * frac
        total_pax += float(r.guests or 0) * frac
        total_available += float(r.available_rooms or 0) * frac
        total_revenue += float(r.adr or 0) * float(r.rooms_occupied or 0) * frac
    return {
        "rn": round(total_rn, 2), "pax": round(total_pax, 2), "available_rooms": round(total_available, 2),
        "adr": round(total_revenue / total_rn, 2) if total_rn else 0.0,
        "occupancy_pct": round(total_rn / total_available, 4) if total_available else 0.0,
    }


def _room_stats_records(rows: list[RoomStat]) -> list[dict]:
    return [{
        "short_description": r.room_category, "room_revenue": r.room_revenue,
        "stay_rooms": r.stay_rooms, "stay_persons": r.stay_persons,
        "physical_rooms": r.physical_rooms,
    } for r in rows]


async def _kpis_for_range(session, pid, start, end) -> dict:
    """Pax / RN / disponibles sumados sobre un rango de días (los que estén
    cargados). Disponibilidad = total_rooms fijo (§Bismark) × cantidad de días
    con ingesta STATISTICS en el rango -- no la suma de physical_rooms real."""
    stats = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid,
            OccupancyStat.business_date >= start, OccupancyStat.business_date <= end,
        )
    )).scalars().all()
    days_with_data = len({s.business_date for s in stats})
    total_rooms = await _total_rooms(session, pid)
    return {
        "rn": sum(s.rooms for s in stats), "pax": sum(s.persons for s in stats),
        "available_rooms": days_with_data * total_rooms,
    }


async def _comps_by_category(session, pid, start, end) -> dict[str, dict]:
    """Comps/in-house (market_code COM/INHOUSE del XML STATISTICS) agrupados por
    categoría de habitación vía `room_class` (dim_room_category.room_class,
    mapeo confirmado por Bismark en Tab 3.1). Alimenta el neteo de ADR/Occ en
    las tablas §5.2 -- STATISTICS no trae monto, así que revenue=0 (el comp no
    aporta revenue; solo se le resta la habitación/persona al RN)."""
    depts = (await session.execute(
        select(RoomCategory).where(RoomCategory.property_id == pid)
    )).scalars().all()
    room_class_to_category = {
        d.room_class: (d.opera_short_desc or d.report_name) for d in depts if d.room_class
    }
    rows = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid,
            OccupancyStat.business_date >= start, OccupancyStat.business_date <= end,
            OccupancyStat.market_code.in_(NON_REVENUE_MARKET_CODES),
        )
    )).scalars().all()
    out: dict[str, dict] = {}
    for r in rows:
        cat = room_class_to_category.get(r.room_class or "", "Otros")
        c = out.setdefault(cat, {"stay_rooms": 0, "stay_persons": 0, "revenue": 0.0})
        c["stay_rooms"] += int(r.rooms or 0)
        c["stay_persons"] += int(r.persons or 0)
    return out


async def _actual_daily_by_day_output_cols(session, pid, start, end) -> dict[date_cls, dict]:
    """Respaldo de Tab 6.4 mapeado al esquema Daily (outlet colapsado, §5.1b) --
    para Today/MTD del Tab 3 en días sin ingesta real Opera/Integrity."""
    rows = (await session.execute(
        select(RevenueActualDaily, Department.cost_center)
        .join(Department, RevenueActualDaily.dept_id == Department.id)
        .where(RevenueActualDaily.property_id == pid,
               RevenueActualDaily.date >= start, RevenueActualDaily.date <= end)
    )).all()
    by_day: dict[date_cls, dict] = defaultdict(lambda: {
        "cols": _empty_cols(),
        "fb": {"food": 0.0, "beverage": 0.0, "misc": 0.0},
        "misc": 0.0,
        "rn": 0.0, "pax": 0.0, "available_rooms": 0.0,
    })
    for r, cost_center in rows:
        d = by_day[r.date]
        col = _DEPT_TO_DAILY_COL.get(cost_center)
        if col:
            d["cols"][col] += float(r.amount_usd)
        elif cost_center in _DEPT_TO_DAILY_MISC:
            d["misc"] += float(r.amount_usd)  # Misc. Revenue (línea propia, como Tab 4)
        if cost_center in _DEPT_TO_FB_SUB:
            d["fb"][_DEPT_TO_FB_SUB[cost_center]] += float(r.amount_usd)
        if cost_center == "0110":
            d["rn"] += float(r.rooms_sold or 0)
            d["pax"] += float(r.total_pax or 0)
            d["available_rooms"] += float(r.available_rooms or 0)
    return by_day


def _pct(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


async def daily_report(session: AsyncSession, business_date: date_cls,
                       property_code: str = "COWLCR") -> dict:
    """Daily Revenue Report (Summary) para un día: Today + MTD + Full Month + KPIs.

    Today/MTD combinan, día por día, ingesta real (Opera/Integrity, fuente
    primaria) con el respaldo de Tab 6.4 para días sin ingesta -- mismo
    criterio que Tab 4 Weekly (nunca se suman ambas fuentes el mismo día)."""
    pid = await _property_id(session, property_code)
    month_start = business_date.replace(day=1)
    month_end = date_cls(business_date.year, business_date.month,
                         calendar.monthrange(business_date.year, business_date.month)[1])
    integrity_by_day = await _integrity_by_day(session, pid, month_start, business_date)
    actual_by_day = await _actual_daily_by_day_output_cols(session, pid, month_start, business_date)

    def _integrity_daily_cols(rows: list[dict]) -> tuple[dict, dict, float]:
        """Pivote Daily de un día Integrity usando EXACTAMENTE el mismo motor que
        Tab 4 (`weekly_pivot`), remapeado al esquema Daily (outlet colapsado):
        Rooms = Rooms + Rooms Others; Sustainable Fee = solo naturaleza 4880;
        Misc. Revenue = "Misc. Rev Others" (0170 no-4880) + otros (fuera de mapa).
        Así Tab 3 y Tab 4 usan los mismos números por día -> reconcilian."""
        wp = weekly_pivot(lines_from_integrity(rows))
        wc = wp["columns"]
        cols = {c: wc.get(c, 0.0) for c in OUTPUT_COLUMNS}
        cols["Rooms"] = round(cols["Rooms"] + wc["Rooms Others"], 2)
        misc = round(wc["Misc. Rev Others"] + wp["otros_total"], 2)
        return cols, wp["fb_detail"], misc

    def _day_pivot(d: date_cls) -> tuple[dict, dict, float]:
        """(cols, fb_detail, misc) de un día -- Integrity si está, si no 6.4."""
        if d in integrity_by_day:
            return _integrity_daily_cols(integrity_by_day[d])
        if d in actual_by_day:
            a = actual_by_day[d]
            return a["cols"], a["fb"], a["misc"]
        return _empty_cols(), {"food": 0.0, "beverage": 0.0, "misc": 0.0}, 0.0

    # Today
    today_cols, today_fb, today_misc = _day_pivot(business_date)
    today_otros = (daily_revenue(lines_from_integrity(integrity_by_day[business_date]))["otros"]
                  if business_date in integrity_by_day else [])

    # MTD = suma de cada día del mes hasta hoy, combinando ambas fuentes
    mtd_cols = _empty_cols()
    mtd_fb = {"food": 0.0, "beverage": 0.0, "misc": 0.0}
    mtd_misc = 0.0
    mtd_rn_fb, mtd_pax_fb, mtd_available_fb = 0.0, 0.0, 0.0
    days_loaded = 0
    all_days = {d for d in integrity_by_day if d <= business_date} | {d for d in actual_by_day if d <= business_date}
    for d in all_days:
        cols, fb, misc = _day_pivot(d)
        days_loaded += 1
        for c in OUTPUT_COLUMNS:
            mtd_cols[c] += cols[c]
        for k in mtd_fb:
            mtd_fb[k] += fb[k]
        mtd_misc += misc   # ← antes se descartaba en MTD: causaba el descuadre del rango
        if d not in integrity_by_day and d in actual_by_day:
            mtd_rn_fb += actual_by_day[d]["rn"]
            mtd_pax_fb += actual_by_day[d]["pax"]
            mtd_available_fb += actual_by_day[d]["available_rooms"]
    mtd_cols = {c: round(v, 2) for c, v in mtd_cols.items()}
    mtd_fb = {k: round(v, 2) for k, v in mtd_fb.items()}
    mtd_misc = round(mtd_misc, 2)

    # Budget: fact_budget por departamento (outlet, §5.1b — misma clasificación
    # que las columnas de Daily). 0 si no hay presupuesto cargado ese período.
    today_budget = await _budget_by_outlet_column(session, pid, business_date, business_date)
    mtd_budget = await _budget_by_outlet_column(session, pid, month_start, business_date)
    month_budget = await _budget_by_outlet_column(session, pid, month_start, month_end)
    has_budget = bool(today_budget or mtd_budget)
    # Forecast del mes completo -- sólo alimenta el cuadro FULL MONTH RESULT.
    month_forecast = await _forecast_by_outlet_column(session, pid, month_start, month_end)

    def _center(name: str, today_actual: float, mtd_actual: float,
               today_bud: dict | None = None, mtd_bud: dict | None = None,
               month_bud: dict | None = None, month_fcst: dict | None = None) -> dict:
        tb = (today_bud if today_bud is not None else today_budget).get(name, 0.0)
        mb = (mtd_bud if mtd_bud is not None else mtd_budget).get(name, 0.0)
        full = (month_bud if month_bud is not None else month_budget).get(name, 0.0)
        fcst = (month_fcst if month_fcst is not None else month_forecast).get(name, 0.0)
        amount_to_budget = round(mtd_actual - full, 2)
        amount_to_forecast = round(mtd_actual - fcst, 2)
        return {
            "center": name,
            "today_actual": round(today_actual, 2), "today_budget": tb,
            "today_var": round(today_actual - tb, 2), "today_var_pct": _pct(today_actual - tb, tb),
            "mtd_actual": round(mtd_actual, 2), "mtd_budget": mb,
            "mtd_var": round(mtd_actual - mb, 2), "mtd_var_pct": _pct(mtd_actual - mb, mb),
            "month_budget_total": round(full, 2), "amount_to_budget": amount_to_budget,
            "monthly_var_pct": _pct(amount_to_budget, full),
            "month_forecast_total": round(fcst, 2), "amount_to_forecast": amount_to_forecast,
            "monthly_fcst_var_pct": _pct(amount_to_forecast, fcst),
        }

    centers = [_center(c, today_cols[c], mtd_cols[c]) for c in OUTPUT_COLUMNS]

    # On-Property Production (Detail Visibility): F&B abierto en Food/Beverage/
    # Misc (cada uno con SU propio budget -- depts FB-FOOD/FB-BEV/FB-MISC, no
    # el "F&B" agregado) + SPA/Retail-Gift Shop/Laundry (mismos centers de
    # arriba, reusados tal cual).
    today_budget_dept = await _budget_by_dept_cost_center(session, pid, business_date, business_date)
    mtd_budget_dept = await _budget_by_dept_cost_center(session, pid, month_start, business_date)
    month_budget_dept = await _budget_by_dept_cost_center(session, pid, month_start, month_end)

    # Línea "Misc. Revenue" (misma que Tab 4): Integrity fuera de mapa + 6.4
    # MISC-REV-OTH/MISC-REV (actual), budget del dept MISC-REV. Antes se plegaba
    # en Sustainable Fee (backup) o se descartaba en el MTD (Integrity) -> era el
    # descuadre vs Tab 4. Va después de Sustainable Fee, al final de los centers.
    misc_tb = today_budget_dept.get("MISC-REV", 0.0)
    misc_mb = mtd_budget_dept.get("MISC-REV", 0.0)
    misc_full = month_budget_dept.get("MISC-REV", 0.0)
    misc_a2b = round(mtd_misc - misc_full, 2)
    month_forecast_dept = await _forecast_by_dept_cost_center(session, pid, month_start, month_end)
    misc_fcst = month_forecast_dept.get("MISC-REV", 0.0)
    misc_a2f = round(mtd_misc - misc_fcst, 2)
    centers.append({
        "center": "Misc. Revenue",
        "today_actual": round(today_misc, 2), "today_budget": round(misc_tb, 2),
        "today_var": round(today_misc - misc_tb, 2), "today_var_pct": _pct(today_misc - misc_tb, misc_tb),
        "mtd_actual": mtd_misc, "mtd_budget": round(misc_mb, 2),
        "mtd_var": round(mtd_misc - misc_mb, 2), "mtd_var_pct": _pct(mtd_misc - misc_mb, misc_mb),
        "month_budget_total": round(misc_full, 2), "amount_to_budget": misc_a2b,
        "monthly_var_pct": _pct(misc_a2b, misc_full),
        "month_forecast_total": round(misc_fcst, 2), "amount_to_forecast": misc_a2f,
        "monthly_fcst_var_pct": _pct(misc_a2f, misc_fcst),
    })

    fb_dept_map = {"food": "FB-FOOD", "beverage": "FB-BEV", "misc": "FB-MISC"}
    fb_labels = {"food": "Food Revenue (Detail)", "beverage": "Beverage Revenue (Detail)", "misc": "F&B Misc Revenue (Detail)"}
    # "Food Revenue (Detail)" sacado de este cuadro a pedido del owner (§On-
    # Property Production) -- TOTAL ON-PROPERTY SALES ya no la incluye tampoco
    # (se resta la misma lista que se muestra, no queda un monto oculto).
    on_property_rows = [
        {**_center(fb_dept_map[k], today_fb[k], mtd_fb[k],
                   today_budget_dept, mtd_budget_dept, month_budget_dept,
                   month_forecast_dept), "center": fb_labels[k]}
        for k in ("beverage", "misc")
    ]
    for c in ("SPA", "Retail-Gift Shop", "Laundry"):
        on_property_rows.append(next(row for row in centers if row["center"] == c))

    def _sum_field(rows: list[dict], field: str) -> float:
        return round(sum(r[field] for r in rows), 2)

    on_property_total = {
        "center": "TOTAL ON-PROPERTY SALES",
        "today_actual": _sum_field(on_property_rows, "today_actual"),
        "today_budget": _sum_field(on_property_rows, "today_budget"),
        "mtd_actual": _sum_field(on_property_rows, "mtd_actual"),
        "mtd_budget": _sum_field(on_property_rows, "mtd_budget"),
        "month_budget_total": _sum_field(on_property_rows, "month_budget_total"),
        "amount_to_budget": _sum_field(on_property_rows, "amount_to_budget"),
        "month_forecast_total": _sum_field(on_property_rows, "month_forecast_total"),
        "amount_to_forecast": _sum_field(on_property_rows, "amount_to_forecast"),
    }
    on_property_total["today_var"] = round(on_property_total["today_actual"] - on_property_total["today_budget"], 2)
    on_property_total["today_var_pct"] = _pct(on_property_total["today_var"], on_property_total["today_budget"])
    on_property_total["mtd_var"] = round(on_property_total["mtd_actual"] - on_property_total["mtd_budget"], 2)
    on_property_total["mtd_var_pct"] = _pct(on_property_total["mtd_var"], on_property_total["mtd_budget"])
    on_property_total["monthly_var_pct"] = _pct(on_property_total["amount_to_budget"], on_property_total["month_budget_total"])
    on_property_total["monthly_fcst_var_pct"] = _pct(on_property_total["amount_to_forecast"], on_property_total["month_forecast_total"])
    # + Misc. Revenue en AMBOS (Today ya lo incluía vía otros; el MTD lo perdía).
    grand_today = round(sum(today_cols.values()) + today_misc, 2)
    grand_mtd = round(sum(mtd_cols.values()) + mtd_misc, 2)
    # Budget: sum(...values()) ya incluye la col "Otros" = budget del dept
    # MISC-REV (misma cifra que la fila Misc. Revenue) -> grand = suma de filas.
    grand_today_budget = round(sum(today_budget.values()), 2)
    grand_mtd_budget = round(sum(mtd_budget.values()), 2)
    grand_month_budget = round(sum(month_budget.values()), 2)
    grand_amount_to_budget = round(grand_mtd - grand_month_budget, 2)
    grand_month_forecast = round(sum(month_forecast.values()), 2)
    grand_amount_to_forecast = round(grand_mtd - grand_month_forecast, 2)

    kpis = await _kpis_for_day(session, pid, business_date)
    if business_date not in integrity_by_day and business_date in actual_by_day:
        kpis["rn"] += actual_by_day[business_date]["rn"]
        kpis["pax"] += actual_by_day[business_date]["pax"]
        kpis["available_rooms"] += actual_by_day[business_date]["available_rooms"]
    # Netear comps/in-house (market_code COM/INHOUSE) del RN/Pax ANTES del ADR/Occ:
    # las tarjetas deben mostrar la tarifa de las habitaciones que PAGAN, mismo
    # criterio que la tabla §5.2 y Tabs 6.6/7.3. `available_rooms` (total fijo) no
    # cambia. comps_today se reusa abajo para la tabla por categoría.
    comps_today = await _comps_by_category(session, pid, business_date, business_date)
    comp_rn_today = sum(c["stay_rooms"] for c in comps_today.values())
    comp_pax_today = sum(c["stay_persons"] for c in comps_today.values())
    rn_net = max(kpis["rn"] - comp_rn_today, 0)
    pax_net = max(kpis["pax"] - comp_pax_today, 0)
    rooms_today = today_cols["Rooms"]
    adr = round(rooms_today / rn_net, 2) if rn_net else 0.0
    occ = round(rn_net / kpis["available_rooms"], 4) if kpis["available_rooms"] else 0.0

    # MTD ADR/Occupancy real -- Integrity Room Revenue (mtd_cols["Rooms"]) ÷
    # Room Statistics NETAS de comps (STATISTICS real + respaldo 6.4, combinados
    # sin doble conteo), fuente "oficial" para controlar tarifas.
    mtd_kpis_real = await _kpis_for_range(session, pid, month_start, business_date)
    comps_mtd = await _comps_by_category(session, pid, month_start, business_date)
    comp_rn_mtd = sum(c["stay_rooms"] for c in comps_mtd.values())
    comp_pax_mtd = sum(c["stay_persons"] for c in comps_mtd.values())
    mtd_rn = max(mtd_kpis_real["rn"] + mtd_rn_fb - comp_rn_mtd, 0)
    mtd_pax = max(mtd_kpis_real["pax"] + mtd_pax_fb - comp_pax_mtd, 0)
    mtd_available = mtd_kpis_real["available_rooms"] + mtd_available_fb
    mtd_adr = round(mtd_cols["Rooms"] / mtd_rn, 2) if mtd_rn else 0.0
    mtd_occ = round(mtd_rn / mtd_available, 4) if mtd_available else 0.0

    # ADR/Occupancy presupuestados (general, §BudgetMonthly.adr) -- Today y MTD
    # caen dentro del mismo mes, así que comparten el mismo target mensual.
    budget_adr_occ = await _budget_adr_occ(session, pid, business_date.year,
                                           business_date.month, business_date.month)

    units_map = await room_stats_service.units_by_category(session, property_code=property_code)

    room_stats_today = await _room_stats(session, pid, business_date, business_date)
    room_categories_today_full = room_stats_rollup(
        _room_stats_records(room_stats_today), comp_by_category=comps_today)
    room_categories = [
        {**c, "units": units_map.get(c["category"], 0)} for c in room_categories_today_full["categories"]
    ]
    room_categories_overall = {**room_categories_today_full["overall"], "units": sum(units_map.values())}
    room_categories_comps = room_categories_today_full["comps_line"]
    room_categories_reconciled = {**room_categories_today_full["reconciled"], "units": sum(units_map.values())}

    # MTD por tipo de habitación (Months to Day Stats, §5.2) -- mismo motor,
    # rango de todo el mes en vez de un solo día. physical_rooms sumado día a
    # día = room-nights disponibles del mes (no una foto de un día), que es
    # justo lo que pide "Total Room Nights Available" del golden.
    room_stats_mtd = await _room_stats(session, pid, month_start, business_date)
    room_categories_mtd_full = room_stats_rollup(
        _room_stats_records(room_stats_mtd), comp_by_category=comps_mtd)
    room_categories_mtd = [
        {**c, "units": units_map.get(c["category"], 0)} for c in room_categories_mtd_full["categories"]
    ]
    room_categories_mtd_overall = {**room_categories_mtd_full["overall"], "units": sum(units_map.values())}
    room_categories_mtd_comps = room_categories_mtd_full["comps_line"]
    room_categories_mtd_reconciled = {**room_categories_mtd_full["reconciled"], "units": sum(units_map.values())}

    return {
        "business_date": business_date.isoformat(),
        "property": property_code,
        "days_loaded_mtd": days_loaded,
        "budget_status": ("Connected to fact_budget (Tab 6.1)." if has_budget else
                          "No budget loaded for this period — upload it in Tab 6.1."),
        "centers": centers,
        "grand_total": {
            "today_actual": grand_today, "today_budget": grand_today_budget,
            "today_var_pct": _pct(grand_today - grand_today_budget, grand_today_budget),
            "mtd_actual": grand_mtd, "mtd_budget": grand_mtd_budget,
            "mtd_var_pct": _pct(grand_mtd - grand_mtd_budget, grand_mtd_budget),
            "month_budget_total": grand_month_budget, "amount_to_budget": grand_amount_to_budget,
            "monthly_var_pct": _pct(grand_amount_to_budget, grand_month_budget),
            "month_forecast_total": grand_month_forecast,
            "amount_to_forecast": grand_amount_to_forecast,
            "monthly_fcst_var_pct": _pct(grand_amount_to_forecast, grand_month_forecast),
        },
        "fb_detail": {"today": today_fb, "mtd": mtd_fb},
        "otros": today_otros,
        "kpis": {
            "pax": pax_net, "rooms_occupied": rn_net,
            "available_rooms": kpis["available_rooms"],
            "adr": adr, "occupancy_pct": occ,
            "mtd_rooms_occupied": mtd_rn, "mtd_pax": round(mtd_pax, 2),
            "mtd_adr": mtd_adr, "mtd_occupancy_pct": mtd_occ,
            "adr_budget": budget_adr_occ["adr"], "occupancy_budget": budget_adr_occ["occupancy_pct"],
        },
        "room_categories": room_categories,
        "room_categories_overall": room_categories_overall,
        "room_categories_comps": room_categories_comps,
        "room_categories_reconciled": room_categories_reconciled,
        "room_categories_mtd": room_categories_mtd,
        "room_categories_mtd_overall": room_categories_mtd_overall,
        "room_categories_mtd_comps": room_categories_mtd_comps,
        "room_categories_mtd_reconciled": room_categories_mtd_reconciled,
        "on_property_production": {"rows": on_property_rows, "total": on_property_total},
    }


async def _actual_daily_by_day(session, pid, start, end) -> dict[date_cls, dict]:
    """Tab 6.4 (carga masiva) agrupado por día, ya en columnas Weekly — respaldo
    para días sin ingesta real (§10, no fabrica: usa solo lo que ya está cargado)."""
    rows = (await session.execute(
        select(RevenueActualDaily, Department.cost_center)
        .join(Department, RevenueActualDaily.dept_id == Department.id)
        .where(RevenueActualDaily.property_id == pid,
               RevenueActualDaily.date >= start, RevenueActualDaily.date <= end)
    )).all()
    by_day: dict[date_cls, dict] = defaultdict(lambda: {
        "cols": {c: 0.0 for c in WEEKLY_COLUMNS},
        "fb": {"food": 0.0, "beverage": 0.0, "misc": 0.0},
        "rn": 0.0, "pax": 0.0, "available_rooms": 0.0,
    })
    for r, cost_center in rows:
        d = by_day[r.date]
        col = _DEPT_TO_WEEKLY_COL.get(cost_center)
        if col:
            d["cols"][col] += float(r.amount_usd)
        if cost_center in _DEPT_TO_FB_SUB:
            d["fb"][_DEPT_TO_FB_SUB[cost_center]] += float(r.amount_usd)
        if cost_center == "0110":
            d["rn"] += float(r.rooms_sold or 0)
            d["pax"] += float(r.total_pax or 0)
            d["available_rooms"] += float(r.available_rooms or 0)
    return by_day


def _aggregate_weekly(integrity_by_day: dict, actual_by_day: dict) -> tuple[dict, dict, float, int, float, float, float]:
    """Suma por día: Integrity real si está cargado (fuente primaria), si no,
    respaldo de Tab 6.4 (carga masiva). Nunca suma ambos el mismo día (§10)."""
    cols = {c: 0.0 for c in WEEKLY_COLUMNS}
    fb = {"food": 0.0, "beverage": 0.0, "misc": 0.0}
    otros_total = 0.0
    rn_fallback = 0.0
    pax_fallback = 0.0
    available_fallback = 0.0
    days = 0
    all_dates = set(integrity_by_day) | set(actual_by_day)
    for d in all_dates:
        days += 1
        if d in integrity_by_day:
            p = weekly_pivot(lines_from_integrity(integrity_by_day[d]))
            for c in WEEKLY_COLUMNS:
                cols[c] += p["columns"][c]
            for k in fb:
                fb[k] += p["fb_detail"][k]
            otros_total += p["otros_total"]
        else:
            a = actual_by_day[d]
            for c in WEEKLY_COLUMNS:
                cols[c] += a["cols"][c]
            for k in fb:
                fb[k] += a["fb"][k]
            rn_fallback += a["rn"]
            pax_fallback += a["pax"]
            available_fallback += a["available_rooms"]
    cols = {c: round(v, 2) for c, v in cols.items()}
    fb = {k: round(v, 2) for k, v in fb.items()}
    return cols, fb, round(otros_total, 2), days, rn_fallback, pax_fallback, available_fallback


def _week_stats(cols: dict, kpis: dict) -> dict:
    rn = kpis["rn"]
    adr = round(cols["Rooms"] / rn, 2) if rn else 0.0
    occ = round(rn / kpis["available_rooms"], 4) if kpis["available_rooms"] else 0.0
    return {"rn": rn, "pax": kpis["pax"], "available_rooms": kpis["available_rooms"],
            "adr": adr, "occupancy_pct": occ}


async def weekly_report(session: AsyncSession, business_date: date_cls,
                        property_code: str = "COWLCR") -> dict:
    """Weekly Revenue Report (Tab 4): semana que contiene `business_date` + YTD.

    Los RANGOS de semana los define Tab 6.10 (dim_week_calendar, EDITABLE): se
    resuelve por rango (week_start <= business_date <= week_end). Editar una
    semana en 6.10 cambia este reporte en sincronía. YTD = suma de los días
    cargados desde el 1-ene hasta el fin de semana (parcial y honesto: no
    fabrica datos de días sin ingestar). dim_calendar (por día) es otra tabla,
    no se usa acá.
    """
    pid = await _property_id(session, property_code)
    cal = (await session.execute(
        select(WeekCalendar).where(
            WeekCalendar.property_id == pid,
            WeekCalendar.week_start <= business_date,
            WeekCalendar.week_end >= business_date,
        ).order_by(WeekCalendar.week_start).limit(1)
    )).scalars().first()
    if cal is None:
        raise ValueError(f"'{business_date}' no está cubierta por ninguna semana de Tab 6.10 (Weekly Calendar).")

    year_start = business_date.replace(month=1, day=1)
    week_integrity = await _integrity_by_day(session, pid, cal.week_start, cal.week_end)
    ytd_integrity = await _integrity_by_day(session, pid, year_start, cal.week_end)
    week_actual = await _actual_daily_by_day(session, pid, cal.week_start, cal.week_end)
    ytd_actual = await _actual_daily_by_day(session, pid, year_start, cal.week_end)

    week_cols, week_fb, week_otros, week_days, week_rn_fb, week_pax_fb, week_avail_fb = _aggregate_weekly(week_integrity, week_actual)
    ytd_cols, ytd_fb, ytd_otros, ytd_days, ytd_rn_fb, ytd_pax_fb, ytd_avail_fb = _aggregate_weekly(ytd_integrity, ytd_actual)

    # Budget: fact_budget por outlet, remapeado a las columnas Weekly (§5.1a) —
    # las columnas *_Others no tienen contraparte en el budget, quedan en 0.
    week_budget_by_outlet = await _budget_by_outlet_column(session, pid, cal.week_start, cal.week_end)
    ytd_budget_by_outlet = await _budget_by_outlet_column(session, pid, year_start, cal.week_end)

    def _remap_to_weekly(by_outlet: dict[str, float]) -> dict[str, float]:
        out = {c: 0.0 for c in WEEKLY_COLUMNS}
        for outlet_col, amount in by_outlet.items():
            weekly_col = _OUTLET_TO_WEEKLY_COL.get(outlet_col)
            if weekly_col:
                out[weekly_col] += amount
        return {k: round(v, 2) for k, v in out.items()}

    week_budget = _remap_to_weekly(week_budget_by_outlet)
    ytd_budget = _remap_to_weekly(ytd_budget_by_outlet)
    has_budget = bool(week_budget_by_outlet or ytd_budget_by_outlet)

    def _center(name: str, weekly_actual: float, weekly_budget: float,
               ytd_actual: float, ytd_budget: float, *, indent: bool = False,
               decimals: int = 2) -> dict:
        # decimals=4 para porcentajes (Occupancy): la fracción con 4 decimales =
        # 2 decimales reales del % en el front (round(0.5098,2)=0.51 daría 51.00%).
        weekly_var = round(weekly_actual - weekly_budget, decimals)
        ytd_var = round(ytd_actual - ytd_budget, decimals)
        return {
            "center": name, "indent": indent,
            "weekly_actual": round(weekly_actual, decimals), "weekly_budget": round(weekly_budget, decimals),
            "weekly_var": weekly_var, "weekly_var_pct": _pct(weekly_var, weekly_budget),
            "ytd_actual": round(ytd_actual, decimals), "ytd_budget": round(ytd_budget, decimals),
            "ytd_var": ytd_var, "ytd_var_pct": _pct(ytd_var, ytd_budget),
        }

    centers = [_center(c, week_cols[c], week_budget[c], ytd_cols[c], ytd_budget[c]) for c in WEEKLY_COLUMNS]

    # F&B abierto en Food/Beverage/Misc (cada uno con SU budget -- depts
    # FB-FOOD/FB-BEV/FB-MISC) + Misc. Revenue (cuentas fuera del mapa
    # canónico, dept MISC-REV) -- Tab 4 "así debe quedar" del owner.
    week_budget_dept = await _budget_by_dept_cost_center(session, pid, cal.week_start, cal.week_end)
    ytd_budget_dept = await _budget_by_dept_cost_center(session, pid, year_start, cal.week_end)
    fb_sub_rows = [
        _center("Food", week_fb["food"], week_budget_dept.get("FB-FOOD", 0.0),
                ytd_fb["food"], ytd_budget_dept.get("FB-FOOD", 0.0), indent=True),
        _center("Beverage", week_fb["beverage"], week_budget_dept.get("FB-BEV", 0.0),
                ytd_fb["beverage"], ytd_budget_dept.get("FB-BEV", 0.0), indent=True),
        _center("Misc", week_fb["misc"], week_budget_dept.get("FB-MISC", 0.0),
                ytd_fb["misc"], ytd_budget_dept.get("FB-MISC", 0.0), indent=True),
    ]
    # "Misc. Rev Others" (dept MISC-REV-OTH, vía 6.4/naturaleza) y "Misc.
    # Revenue" (cuentas Integrity fuera del mapa canónico, dept MISC-REV) son
    # la MISMA línea de negocio para el owner -- se fusionan en una sola fila
    # (§Bismark, confirmado: "realmente son las mismas").
    misc_revenue_row = _center(
        "Misc. Revenue",
        week_cols["Misc. Rev Others"] + week_otros,
        week_budget["Misc. Rev Others"] + week_budget_dept.get("MISC-REV", 0.0),
        ytd_cols["Misc. Rev Others"] + ytd_otros,
        ytd_budget["Misc. Rev Others"] + ytd_budget_dept.get("MISC-REV", 0.0),
    )

    # Orden exacto pedido por el owner (no es el mismo orden que WEEKLY_COLUMNS
    # -- Tours antes de Retail-Gift Shop acá).
    ROW_ORDER = ["Rooms", "Rooms Others", "F&B", "SPA", "Tours", "Retail-Gift Shop",
                "Transportation", "Laundry", "Innoceana", "Crowther Lab", "Sustainable Fee"]
    by_name = {c["center"]: c for c in centers}
    table_rows = []
    for name in ROW_ORDER:
        table_rows.append(by_name[name])
        if name == "F&B":
            table_rows.extend(fb_sub_rows)
    table_rows.append(misc_revenue_row)

    grand_weekly_actual = round(sum(week_cols.values()) + week_otros, 2)
    grand_weekly_budget = round(sum(week_budget.values()) + week_budget_dept.get("MISC-REV", 0.0), 2)
    grand_ytd_actual = round(sum(ytd_cols.values()) + ytd_otros, 2)
    grand_ytd_budget = round(sum(ytd_budget.values()) + ytd_budget_dept.get("MISC-REV", 0.0), 2)
    total_row = _center("Total Daily Rev. Weekly", grand_weekly_actual, grand_weekly_budget,
                        grand_ytd_actual, grand_ytd_budget)
    table_rows.append(total_row)

    week_kpis = await _kpis_for_range(session, pid, cal.week_start, cal.week_end)
    ytd_kpis = await _kpis_for_range(session, pid, year_start, cal.week_end)
    # RN/Pax de días sin ingesta real se completan con el respaldo de 6.4 (nunca
    # se solapan: _aggregate_weekly ya excluye los días con Integrity real).
    week_kpis["rn"] += week_rn_fb
    week_kpis["pax"] += week_pax_fb
    week_kpis["available_rooms"] += week_avail_fb
    ytd_kpis["rn"] += ytd_rn_fb
    ytd_kpis["pax"] += ytd_pax_fb
    ytd_kpis["available_rooms"] += ytd_avail_fb

    week_comps = await _comps_by_category(session, pid, cal.week_start, cal.week_end)
    week_room_stats = await _room_stats(session, pid, cal.week_start, cal.week_end)
    room_categories_full = room_stats_rollup(_room_stats_records(week_room_stats), comp_by_category=week_comps)
    units_map = await room_stats_service.units_by_category(session, property_code=property_code)
    room_categories = [
        {**c, "units": units_map.get(c["category"], 0)} for c in room_categories_full["categories"]
    ]
    room_categories_overall = {
        **room_categories_full["overall"],
        "units": sum(units_map.values()),
    }
    room_categories_comps = room_categories_full["comps_line"]
    room_categories_reconciled = {**room_categories_full["reconciled"], "units": sum(units_map.values())}
    # Tab 6.6 -- YTD por categoría (ancla editable room_stat_opening + fact_room_stat
    # real posterior al ancla), integrado acá para que el reporte semanal de dueños
    # traiga siempre el mismo YTD que Tab 6.6.
    room_categories_ytd_full = await room_stats_service.room_stats_ytd(
        session, cal.week_end, property_code=property_code,
    )
    room_categories_ytd = room_categories_ytd_full["categories"]  # BRUTO por categoría
    room_categories_ytd_overall = {
        **room_categories_ytd_full["overall"],
        "units": sum(c["units"] for c in room_categories_ytd),
    }
    room_categories_ytd_comps = room_categories_ytd_full["comps_line"]
    room_categories_ytd_net = room_categories_ytd_full["net"]

    # Budget de RN/Pax/Disponibles/ADR/Occ prorrateado por día para el rango
    # exacto (semana parcial, YTD parcial) -- no el mes completo (§ arriba).
    week_budget_room = await _budget_room_stats_for_range(session, pid, cal.week_start, cal.week_end)
    ytd_budget_room = await _budget_room_stats_for_range(session, pid, year_start, cal.week_end)

    # Netear comps/in-house (COM/INHOUSE) del RN/Pax de las filas de estadísticas
    # (Rooms Sold RN, Total Pax, Occupancy%, ADR) -- mismo criterio que §5.2 y
    # Tab 3. week_comps ya está; para YTD se calculan sobre el rango completo.
    # `available_rooms` (total fijo) no cambia.
    ytd_comps = await _comps_by_category(session, pid, year_start, cal.week_end)
    week_kpis["rn"] = max(week_kpis["rn"] - sum(c["stay_rooms"] for c in week_comps.values()), 0)
    week_kpis["pax"] = max(week_kpis["pax"] - sum(c["stay_persons"] for c in week_comps.values()), 0)
    ytd_kpis["rn"] = max(ytd_kpis["rn"] - sum(c["stay_rooms"] for c in ytd_comps.values()), 0)
    ytd_kpis["pax"] = max(ytd_kpis["pax"] - sum(c["stay_persons"] for c in ytd_comps.values()), 0)

    week_stats = _week_stats(week_cols, week_kpis)
    ytd_stats = _week_stats(ytd_cols, ytd_kpis)
    week_stats["adr_budget"] = week_budget_room["adr"]
    week_stats["occupancy_budget"] = week_budget_room["occupancy_pct"]
    ytd_stats["adr_budget"] = ytd_budget_room["adr"]
    ytd_stats["occupancy_budget"] = ytd_budget_room["occupancy_pct"]

    # Filas de estadísticas: se toman de las MISMAS tablas de room stats de abajo
    # (net = revenue rooms, gross = occupied incl comps) para que RECONCILIEN
    # siempre — antes salían de _kpis_for_range (OccupancyStat+grid 6.4) y no
    # pegaban con la tabla YTD por categoría (ancla + fact_room_stat). "Rooms Sold
    # (RN)"/"Total Pax"/"Occupancy%"/"ADR" van NETOS (habitaciones que pagan);
    # "Occupied Rooms (FULL AMOUNT)" va en GROSS (total ocupadas = net + comps).
    stat_rows = [
        {**_center("Rooms Sold (RN)", room_categories_overall["stay_rooms"], week_budget_room["rn"],
                   room_categories_ytd_net["stay_rooms"], ytd_budget_room["rn"]), "unit": "count"},
        {**_center("Total Pax", room_categories_overall["stay_persons"], week_budget_room["pax"],
                   room_categories_ytd_net["stay_persons"], ytd_budget_room["pax"]), "unit": "count"},
        {**_center("Occupied Rooms (FULL AMOUNT)", room_categories_reconciled["stay_rooms"], week_budget_room["rn"],
                   room_categories_ytd_overall["stay_rooms"], ytd_budget_room["rn"]), "unit": "count"},
        # Available = capacidad FIJA (30 hab × días, §Bismark), igual que el budget
        # -- NO el physical_rooms de Opera (que varía por días no ingestados). Así
        # available actual == available budget. Occupancy = RN neto / capacidad fija.
        {**_center("Available Rooms (Nights)", week_kpis["available_rooms"], week_budget_room["available_rooms"],
                   ytd_kpis["available_rooms"], ytd_budget_room["available_rooms"]), "unit": "count"},
        {**_center("Occupancy %",
                   room_categories_overall["stay_rooms"] / week_kpis["available_rooms"] if week_kpis["available_rooms"] else 0.0,
                   week_budget_room["occupancy_pct"],
                   room_categories_ytd_net["stay_rooms"] / ytd_kpis["available_rooms"] if ytd_kpis["available_rooms"] else 0.0,
                   ytd_budget_room["occupancy_pct"], decimals=4), "unit": "percent"},
        {**_center("ADR (Rooms Rev / RN)", room_categories_overall["adr"], week_budget_room["adr"],
                   room_categories_ytd_net["adr"], ytd_budget_room["adr"]), "unit": "currency"},
    ]
    table_rows.extend(stat_rows)

    return {
        "business_date": business_date.isoformat(),
        "property": property_code,
        "week": {"iso_week": cal.week_num, "week_start": cal.week_start.isoformat(),
                 "week_end": cal.week_end.isoformat(), "label": cal.week_label},
        "days_loaded_week": week_days, "days_loaded_ytd": ytd_days,
        "budget_status": ("Connected to fact_budget (Tab 6.1)." if has_budget else
                          "No budget loaded for this period — upload it in Tab 6.1."),
        "centers": centers,
        "table_rows": table_rows,
        "grand_total": {
            "weekly_actual": grand_weekly_actual, "weekly_budget": grand_weekly_budget,
            "ytd_actual": grand_ytd_actual, "ytd_budget": grand_ytd_budget,
        },
        "fb_detail": {"weekly": week_fb, "ytd": ytd_fb},
        "otros_total": {"weekly": week_otros, "ytd": ytd_otros},
        "stats": {
            "weekly": week_stats,
            "ytd": ytd_stats,
        },
        "room_categories": room_categories,
        "room_categories_overall": room_categories_overall,
        "room_categories_comps": room_categories_comps,
        "room_categories_reconciled": room_categories_reconciled,
        "room_categories_ytd": room_categories_ytd,
        "room_categories_ytd_overall": room_categories_ytd_overall,
        "room_categories_ytd_comps": room_categories_ytd_comps,
        "room_categories_ytd_net": room_categories_ytd_net,
    }


async def opera_validation_report(session: AsyncSession, business_date: date_cls,
                                  property_code: str = "COWLCR") -> dict:
    """Tab 3.1 -- Opera Daily (XML STATISTICS, "oficial") vs Opera History
    (XML statroomtype, "para confirmar") por categoría de habitación, para un
    día puntual. Diferencia visible por categoría (§10, nunca en silencio)."""
    pid = await _property_id(session, property_code)

    depts = (await session.execute(
        select(RoomCategory).where(RoomCategory.property_id == pid)
    )).scalars().all()
    room_class_to_category = {
        d.room_class: (d.opera_short_desc or d.report_name)
        for d in depts if d.room_class
    }

    occ_rows = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid, OccupancyStat.business_date == business_date
        )
    )).scalars().all()
    occupancy_records = [{"room_class": r.room_class, "rooms": r.rooms, "persons": r.persons} for r in occ_rows]

    room_stats_rows = await _room_stats(session, pid, business_date, business_date)
    room_stat_records = _room_stats_records(room_stats_rows)

    # Integrity Room Revenue POR CATEGORÍA (fuente "oficial" de tarifas, §Bismark
    # -- sufijo de cuenta 01-06 confirmado contra datos reales, no es frágil).
    # Solo disponible si el día tiene ingesta real de Integrity -- el respaldo
    # de 6.4 no trae este desglose, no se fabrica (§10).
    code2_to_category = {d.code2: (d.opera_short_desc or d.report_name) for d in depts}
    integrity_day = await _integrity_by_day(session, pid, business_date, business_date)
    revenue_daily_by_category: dict[str, float] = {}
    if business_date in integrity_day:
        by_code2 = room_revenue_by_category(lines_from_integrity(integrity_day[business_date]))
        for code2, amount in by_code2.items():
            # code2 '00' = Other Rooms Revenue (sufijo fuera de 01-06, §Bismark)
            cat = "Otros" if code2 == "00" else code2_to_category.get(code2, "Otros")
            revenue_daily_by_category[cat] = revenue_daily_by_category.get(cat, 0.0) + amount

    comps_day = await _comps_by_category(session, pid, business_date, business_date)
    result = opera_daily_vs_history(occupancy_records, room_stat_records, room_class_to_category,
                                    revenue_daily_by_category=revenue_daily_by_category,
                                    comp_by_category=comps_day)
    return {
        "business_date": business_date.isoformat(), "property": property_code,
        "room_class_mapping": room_class_to_category,
        # False si el día no tiene ingesta del XML statroomtype -- comparar
        # "Daily vs History" contra un History vacío (todo en 0) no es una
        # discrepancia real, es ausencia de insumo (§10, no fabricar hallazgos).
        "has_history_data": len(room_stat_records) > 0,
        **result,
    }


def _occupancy_records(rows) -> list[dict]:
    return [{
        "market_code": r.market_code, "rooms": r.rooms, "persons": r.persons,
        "noshow_rooms": r.noshow_rooms, "cancel_rooms": r.cancel_rooms,
    } for r in rows]


async def market_segment_report(session: AsyncSession, business_date: date_cls,
                                 property_code: str = "COWLCR") -> dict:
    """Tab 3.2 -- Análisis por Market Code (canal/COM/In-house, §visibilidad de
    tarifa) para Today y MTD. Fuente: fact_occupancy_stat (XML STATISTICS,
    ya ingestado en Tab 1/2.4) -- si un día no tiene ese XML, no aparece
    (no se fabrica)."""
    pid = await _property_id(session, property_code)
    month_start = business_date.replace(day=1)

    today_rows = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid, OccupancyStat.business_date == business_date
        )
    )).scalars().all()
    mtd_rows = (await session.execute(
        select(OccupancyStat).where(
            OccupancyStat.property_id == pid,
            OccupancyStat.business_date >= month_start, OccupancyStat.business_date <= business_date,
        )
    )).scalars().all()

    code_to_group = dict((await session.execute(
        select(MarketCode.code, MarketCode.kpi_group)
        .where(MarketCode.property_id == pid, MarketCode.kpi_group.is_not(None))
    )).all())

    today = market_segment_rollup(_occupancy_records(today_rows), code_to_group)
    mtd = market_segment_rollup(_occupancy_records(mtd_rows), code_to_group)

    market_names = dict((await session.execute(
        select(MarketCode.code, MarketCode.name).where(MarketCode.property_id == pid)
    )).all())

    return {
        "business_date": business_date.isoformat(), "property": property_code,
        "market_names": market_names,
        "today": today, "mtd": mtd,
    }
