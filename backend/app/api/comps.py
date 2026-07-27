"""Tab 7.8 / 7.9 -- Control de estadísticas de comps/in-house por tipo."""
from __future__ import annotations

from datetime import date as date_cls

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import comp_stat_service as svc

router = APIRouter(prefix="/comps", tags=["comps"])
settings = get_settings()


@router.get("/monthly")
async def comps_monthly(
    year: int = Query(default=2026), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.monthly_view(session, property_code=prop or settings.DEFAULT_PROPERTY, year=year)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/daily")
async def comps_daily(
    year: int = Query(default=2026),
    date_from: date_cls | None = Query(default=None),
    date_to: date_cls | None = Query(default=None),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        return await svc.daily_view(session, property_code=prop or settings.DEFAULT_PROPERTY,
                                    year=year, date_from=date_from, date_to=date_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
