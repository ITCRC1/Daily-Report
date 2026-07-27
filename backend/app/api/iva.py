"""Endpoints de IVA 13% (Tab 7.7)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import iva_service

router = APIRouter(prefix="/iva", tags=["iva"])
settings = get_settings()


@router.get("/today-mtd")
async def iva_today_mtd(
    business_date: date = Query(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    return await iva_service.today_mtd(session, business_date, property_code=code)


@router.get("")
async def iva_range(
    date_from: date = Query(...), date_to: date = Query(...),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await iva_service.range_view(session, date_from, date_to, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
