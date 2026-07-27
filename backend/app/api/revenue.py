"""Endpoints de Revenue (Tab 3 — Daily Revenue Report)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import revenue_service

router = APIRouter(prefix="/revenue", tags=["revenue"])
settings = get_settings()


@router.get("/weekly/{business_date}")
async def revenue_weekly_view(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Weekly Revenue Report: semana Lun-Dom que contiene `business_date` + YTD."""
    code = prop or settings.DEFAULT_PROPERTY
    return await revenue_service.weekly_report(session, business_date, property_code=code)


@router.get("/opera-validation/{business_date}")
async def revenue_opera_validation_view(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Tab 3.1 -- Opera Daily (XML STATISTICS, oficial) vs Opera History
    (XML statroomtype, para confirmar) por categoría de habitación."""
    code = prop or settings.DEFAULT_PROPERTY
    return await revenue_service.opera_validation_report(session, business_date, property_code=code)


@router.get("/market-segment/{business_date}")
async def revenue_market_segment_view(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Tab 3.2 -- Análisis por Market Code (canal/COM/In-house) Today + MTD."""
    code = prop or settings.DEFAULT_PROPERTY
    return await revenue_service.market_segment_report(session, business_date, property_code=code)


@router.get("/{business_date}")
async def revenue_view(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Daily Revenue Report del día: 12 centros (Today + MTD) + KPIs."""
    code = prop or settings.DEFAULT_PROPERTY
    return await revenue_service.daily_report(session, business_date, property_code=code)
