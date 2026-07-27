"""Endpoints de Master Data (Tab 6): 6.2 Cash Mapping, 6.3 Integrity Mapping,
6.6 Rooms Statistics YTD, 6.7 Rooms Mapping. (6.1/6.4/6.5 viven en sus propios
servicios -- budget_service / revenue_actual_service.)
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import config_service as config_svc
from app.services import master_data_service as svc
from app.services import room_stats_service as room_stats_svc

router = APIRouter(prefix="/master-data", tags=["master-data"])
settings = get_settings()


class PaymentMapIn(BaseModel):
    transaction_code: str
    code: str | None = None
    description: str | None = None
    banco_codigo: str | None = None
    banco_nombre: str | None = None
    moneda: str | None = None
    tipo_pago: str | None = None
    marca_metodo: str | None = None
    grupo: str | None = None
    cash_flow: str | None = None
    canal: str | None = None
    report_bucket: str | None = None


class DepartmentIn(BaseModel):
    cuenta_nature: str | None = None
    cost_center: str | None = None
    outlet_name: str | None = None
    output_column: str


class RoomCategoryIn(BaseModel):
    code2: str
    report_name: str | None = None
    opera_short_desc: str | None = None
    room_class: str | None = None
    integrity_string: str | None = None
    units: int | None = None


class MarketCodeIn(BaseModel):
    code: str
    name: str | None = None
    kpi_group: str | None = None


class RoomStatOpeningIn(BaseModel):
    room_category: str
    anchor_date: str
    revenue: float = 0
    stay_rooms: float = 0
    stay_persons: float = 0
    physical_rooms: float = 0


class RoomStatOpeningBatchIn(BaseModel):
    items: list[RoomStatOpeningIn]


class ParamIn(BaseModel):
    value: str


class WeekCalendarIn(BaseModel):
    week_start: str | None = None
    week_end: str | None = None


@router.get("/payment-map")
async def payment_map_list(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await svc.list_payment_map(session, property_code=prop or settings.DEFAULT_PROPERTY)


@router.post("/payment-map")
async def payment_map_create(
    body: PaymentMapIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.create_payment_map(session, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/payment-map/{row_id}")
async def payment_map_update(
    row_id: str, body: PaymentMapIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.update_payment_map(session, row_id, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/payment-map/{row_id}")
async def payment_map_delete(
    row_id: str, prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await svc.delete_payment_map(session, row_id, property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": row_id}


@router.get("/departments")
async def departments_list(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await svc.list_departments(session, property_code=prop or settings.DEFAULT_PROPERTY)


@router.post("/departments")
async def departments_create(
    body: DepartmentIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.create_department(session, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/departments/{row_id}")
async def departments_update(
    row_id: str, body: DepartmentIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.update_department(session, row_id, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/departments/{row_id}")
async def departments_delete(
    row_id: str, prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await svc.delete_department(session, row_id, property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": row_id}


@router.get("/room-categories")
async def room_categories_list(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await svc.list_room_categories(session, property_code=prop or settings.DEFAULT_PROPERTY)


@router.post("/room-categories")
async def room_categories_create(
    body: RoomCategoryIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.create_room_category(session, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/room-categories/{row_id}")
async def room_categories_update(
    row_id: str, body: RoomCategoryIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.update_room_category(session, row_id, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/room-categories/{row_id}")
async def room_categories_delete(
    row_id: str, prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await svc.delete_room_category(session, row_id, property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": row_id}


@router.get("/market-codes")
async def market_codes_list(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await svc.list_market_codes(session, property_code=prop or settings.DEFAULT_PROPERTY)


@router.post("/market-codes")
async def market_codes_create(
    body: MarketCodeIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.create_market_code(session, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/market-codes/{row_id}")
async def market_codes_update(
    row_id: str, body: MarketCodeIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.update_market_code(session, row_id, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/market-codes/{row_id}")
async def market_codes_delete(
    row_id: str, prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await svc.delete_market_code(session, row_id, property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": row_id}


@router.get("/room-stats/opening")
async def room_stats_opening_list(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await room_stats_svc.list_openings(session, property_code=prop or settings.DEFAULT_PROPERTY)


@router.put("/room-stats/opening")
async def room_stats_opening_save(
    body: RoomStatOpeningBatchIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    try:
        return await room_stats_svc.upsert_openings(
            session, [i.model_dump() for i in body.items], property_code=prop or settings.DEFAULT_PROPERTY,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/room-stats/ytd")
async def room_stats_ytd(
    as_of: date = Query(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await room_stats_svc.room_stats_ytd(session, as_of, property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/room-stats/daily")
async def room_stats_daily(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await room_stats_svc.daily_view(session, property_code=prop or settings.DEFAULT_PROPERTY)


# --- 6.9 Parametros / Cuentas (config_service) ---
@router.get("/params")
async def params_list(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await config_svc.list_params(session, property_code=prop or settings.DEFAULT_PROPERTY)


@router.put("/params/{key}")
async def params_update(
    key: str, body: ParamIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await config_svc.set_param(session, key, body.value, property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/params/{key}")
async def params_reset(
    key: str, prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await config_svc.reset_param(session, key, property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- 6.10 Weekly Calendar (dim_week_calendar) ------------------------------
@router.get("/week-calendar")
async def week_calendar_list(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await svc.list_weeks(session, property_code=prop or settings.DEFAULT_PROPERTY)


@router.put("/week-calendar/{row_id}")
async def week_calendar_update(
    row_id: str, body: WeekCalendarIn, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.update_week(session, row_id, body.model_dump(), property_code=prop or settings.DEFAULT_PROPERTY)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/week-calendar/recalculate")
async def week_calendar_recalculate(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    return await svc.recalculate_weeks(session, property_code=prop or settings.DEFAULT_PROPERTY)
