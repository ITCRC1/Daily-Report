# -*- coding: utf-8 -*-
"""Hoja 3 del reporte a dueños — carga los datos de History and Forecast.

El armado de la hoja (filas, bloques, totales, Occ.%) vive en
`engine/history_forecast.py`, que es puro. Acá sólo se juntan las dos fuentes:

    HISTORY  (del 1 al día del Daily)   -- todo de la app
      Total Revenue   revenue_service.revenue_total_by_day (el mismo número
                      que el grand total del Tab 3 de ese día)
      ADR Rooms Only  room_stats_rollup(...)["overall"]["adr"] -- tarifa de
                      habitación, neta de cortesías
      Total Occ / PAX fact_occupancy_stat, netos de comps/in-house

    FORECAST (del día siguiente al fin de mes)  -- Opera
      todo de fact_otb_daily del snapshot vigente (history_forecast)

Se arma el mes de una sola pasada: cinco consultas para todo el mes en vez de
llamar al Daily 31 veces.

⚠️ Dos fuentes distintas en la misma fila, a propósito y documentado: el
`occ`/`pax` salen de fact_occupancy_stat (el XML STATISTICS) y el ADR del
rollup de fact_room_stat. Es lo que muestra el Tab 3 en sus KPI y en Room
Statistics respectivamente, y es la combinación que el owner validó contra su
cuadro el 2026-11-06. No se unifican por las buenas: cambiaría cifras que ya
revisó.
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date as date_cls
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.history_forecast import armar_hoja
from app.engine.room_stats import NON_REVENUE_MARKET_CODES, room_stats_rollup
from app.models import OccupancyStat, OtbDaily, Property, RoomStat
from app.services import inventory_service, revenue_service


# El reporte entero esta en ingles ("Daily Revenue Report", "TODAY",
# "MONTH TO DAY") y el rotulo de esta hoja tiene que acompanarlo SIEMPRE.
# `calendar.month_name` sigue el locale del proceso: con LANG en espanol
# devuelve "noviembre", y el titulo de la hoja impresa cambiaria de idioma
# segun como arranque el contenedor, sin que nadie lo toque.
MESES_EN = ["", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"]


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _history_by_day(session: AsyncSession, pid, start: date_cls, end: date_cls) -> dict:
    """Los días cerrados, tal como los muestra el Daily."""
    revenue_by_day = await revenue_service.revenue_total_by_day(session, pid, start, end)
    comps_by_day = await revenue_service.comps_by_day_and_category(session, pid, start, end)

    # Room stats del mes de una sola vez, agrupadas por día: el rollup es puro
    # y correr 31 veces no cuesta nada, lo caro sería consultar 31 veces.
    rs_rows = (await session.execute(
        select(RoomStat).where(
            RoomStat.property_id == pid,
            RoomStat.business_date >= start, RoomStat.business_date <= end,
        )
    )).scalars().all()
    rs_by_day: dict[date_cls, list[dict]] = defaultdict(list)
    for r in rs_rows:
        rs_by_day[r.business_date].append({
            "short_description": r.room_category, "room_revenue": r.room_revenue,
            "stay_rooms": r.stay_rooms, "stay_persons": r.stay_persons,
            "physical_rooms": r.physical_rooms,
        })

    # RN / Pax BRUTOS del XML STATISTICS, y los comps que hay que restarles.
    occ_rows = (await session.execute(
        select(OccupancyStat.business_date,
               func.sum(OccupancyStat.rooms), func.sum(OccupancyStat.persons))
        .where(OccupancyStat.property_id == pid,
               OccupancyStat.business_date >= start, OccupancyStat.business_date <= end)
        .group_by(OccupancyStat.business_date)
    )).all()
    bruto_by_day = {d: (float(rn or 0), float(px or 0)) for d, rn, px in occ_rows}

    out: dict[date_cls, dict] = {}
    for d in sorted(set(revenue_by_day) | set(rs_by_day) | set(bruto_by_day)):
        comps = comps_by_day.get(d, {})
        comp_rn = sum(c["stay_rooms"] for c in comps.values())
        comp_px = sum(c["stay_persons"] for c in comps.values())
        rn_bruto, px_bruto = bruto_by_day.get(d, (0.0, 0.0))
        overall = room_stats_rollup(rs_by_day.get(d, []), comp_by_category=comps)["overall"]
        revenue = revenue_by_day.get(d, 0.0)
        out[d] = {
            # Netos de cortesías, igual que los KPI del Tab 3.
            "occ": max(rn_bruto - comp_rn, 0.0),
            "pax": max(px_bruto - comp_px, 0.0),
            "revenue": revenue,
            "rooms_revenue": float(overall["revenue"]),
            "adr": float(overall["adr"]),
            # Cargado = el día TIENE ingesta, no que tenga números distintos de
            # cero. `out` solo recibe días que aparecieron en alguna fuente
            # (Integrity, la grilla 6.4, fact_room_stat o fact_occupancy_stat),
            # así que llegar hasta acá ya es estar cargado.
            #
            # ⚠️ Antes esto miraba los VALORES, y en octubre --el mes que CWL
            # cierra-- marcaba "sin cargar" días que sí estaban ingestados y
            # que legítimamente dan cero. La misma hoja decía "3 días cargados
            # en el mes" arriba y "sin cargar" abajo. Un día cerrado con cero
            # actividad no es un día que falte subir.
            "loaded": True,
        }
    return out


async def _forecast_by_day(session: AsyncSession, pid, start: date_cls,
                           end: date_cls) -> tuple[dict, date_cls | None]:
    """Los días por venir, del `history_forecast` de Opera.

    Siempre el snapshot MÁS RECIENTE que haya, sin importar el día del reporte
    (owner, 2026-11-06: *«siempre debemos tomar forecast on the books del día
    más reciente»*). On The Books es lo que hay reservado AHORA: el corte más
    fresco es la mejor respuesta sobre lo que queda del mes, y un corte viejo
    subestima lo que entró desde entonces.

    Antes esto se limitaba a los snapshots `<= as_of`, por miedo a que un corte
    posterior al Daily trajera como "forecast" días que Opera ya cerró. Dos
    razones por las que el criterio del owner gana: esos días vienen con el
    dato REAL de Opera, que es mejor información y no peor; y Tab 8 (On The
    Books) ya tomaba por defecto el último corte de todos, así que la hoja 3
    estaba contradiciendo a la pantalla de al lado con los mismos datos.

    De qué corte salió se devuelve igual (`snapshot_date`) y la hoja lo
    imprime al pie: tomar el más fresco no exime de decir cuál fue.
    """
    snapshot = (await session.execute(
        select(func.max(OtbDaily.snapshot_date)).where(
            OtbDaily.property_id == pid)
    )).scalar_one_or_none()
    if snapshot is None:
        return {}, None

    rows = (await session.execute(
        select(OtbDaily).where(
            OtbDaily.property_id == pid, OtbDaily.snapshot_date == snapshot,
            OtbDaily.the_date >= start, OtbDaily.the_date <= end,
        )
    )).scalars().all()
    return {
        r.the_date: {
            "occ": float(r.rooms_sold or 0),
            "pax": float(r.persons or 0),
            "revenue": float(r.revenue or 0),
            "rooms_revenue": float(r.rooms_revenue or 0),
            "adr": float(r.adr or 0),
        }
        for r in rows
    }, snapshot


async def history_forecast_report(session: AsyncSession, business_date: date_cls,
                                  property_code: str = "COWLCR") -> dict:
    """Hoja 3: el mes de `business_date`, cortado en ese mismo día."""
    pid = await _property_id(session, property_code)
    ultimo = calendar.monthrange(business_date.year, business_date.month)[1]
    month_start = business_date.replace(day=1)
    month_end = date_cls(business_date.year, business_date.month, ultimo)
    dias = [date_cls(business_date.year, business_date.month, n) for n in range(1, ultimo + 1)]

    history = await _history_by_day(session, pid, month_start, business_date)
    # El Forecast arranca el día SIGUIENTE al del Daily (owner, 2026-11-06).
    forecast, snapshot = ({}, None)
    if business_date < month_end:
        forecast, snapshot = await _forecast_by_day(
            session, pid, business_date + timedelta(days=1), month_end)

    hoja = armar_hoja(dias, business_date, history, forecast,
                      await inventory_service.tramos(session, pid))
    return {
        "business_date": business_date.isoformat(),
        "property": property_code,
        "month_label": f"{MESES_EN[business_date.month]} {business_date.year}",
        "month_start": month_start.isoformat(),
        "month_end": month_end.isoformat(),
        # De qué corte de Opera salió el Forecast. None = no hay OTB cargado
        # hasta esa fecha, y entonces los días por venir salen en cero: la hoja
        # lo dice en vez de aparentar un mes flojo.
        "snapshot_date": snapshot.isoformat() if snapshot else None,
        **hoja,
    }
