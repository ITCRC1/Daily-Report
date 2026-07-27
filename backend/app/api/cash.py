"""Endpoints de Cash (Tab 5 — Daily Cash from Operation)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import cash_forecast_service, cash_service

router = APIRouter(prefix="/cash", tags=["cash"])
settings = get_settings()


class CashFlowForecastIn(BaseModel):
    opening: float = 0.0
    net: list[float] = []
    begin: list[float | None] = []  # override de Beginning Cash por mes (None = roll-forward)


class MonthlyCashPositionIn(BaseModel):
    opening: float | None = None
    other_collections: float | None = None
    pay_vendors: float | None = None
    pay_capital: float | None = None
    pay_payroll: float | None = None
    pay_social_security: float | None = None
    pay_ins: float | None = None
    pay_hacienda: float | None = None
    other_pay_1: float | None = None
    other_pay_2: float | None = None
    other_pay_3: float | None = None
    other_pay_4: float | None = None
    # Tasas de tarjeta (en %) para netear el bruto — canales POS y Ecommerce.
    pos_commission_pct: float | None = None
    pos_retention_pct: float | None = None
    ecom_commission_pct: float | None = None
    ecom_retention_pct: float | None = None
    labels: dict[str, str] | None = None  # {other_pay_1: "Rent", ...} globales por propiedad


@router.get("/flow-forecast")
async def cash_flow_forecast(
    year: int = Query(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await cash_forecast_service.get_forecast(session, year, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/flow-forecast")
async def save_cash_flow_forecast(
    body: CashFlowForecastIn,
    year: int = Query(...), scenario: str = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await cash_forecast_service.save_forecast(
            session, year, scenario, body.opening, body.net, begins=body.begin, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/monthly-position")
async def cash_monthly_position(
    year: int = Query(...), month: int = Query(...),
    as_of: date = Query(default=None, description="business date para el MTD; default fin de mes"),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await cash_service.monthly_position(session, year, month, property_code=code, as_of=as_of)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/monthly-position")
async def save_cash_monthly_position(
    body: MonthlyCashPositionIn,
    year: int = Query(...), month: int = Query(...),
    as_of: date = Query(default=None),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        data = body.model_dump()
        labels = data.pop("labels", None)
        return await cash_service.save_monthly_position(
            session, year, month, data, property_code=code, as_of=as_of, labels=labels)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/weekly/{business_date}")
async def cash_weekly_view(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Weekly Cash: semana Lun-Dom que contiene `business_date` + YTD."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await cash_service.weekly_cash(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/monthly-summary")
async def cash_monthly_summary(
    year: int = Query(..., description="año calendario, ej. 2026"),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Tab 5.1 — Monthly Summary / Transaction Currency Basis: Cards/Transfers/
    Cash/SINPE en su moneda nativa + Non-Cash, mes a mes + YTD."""
    code = prop or settings.DEFAULT_PROPERTY
    return await cash_service.monthly_currency_summary(session, year, property_code=code)


@router.get("/{business_date}")
async def cash_view(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Daily Cash from Operation: Today + MTD, buckets de dos niveles (§5.5)."""
    code = prop or settings.DEFAULT_PROPERTY
    return await cash_service.daily_cash(session, business_date, property_code=code)
