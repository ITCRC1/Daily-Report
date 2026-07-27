"""Tab 7.10 Market Codes — pivote por market code (Pax/Rooms/Room Revenue/Revenue Total)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import market_code_service

router = APIRouter(prefix="/market-codes", tags=["market-codes"])
settings = get_settings()


@router.get("")
async def market_codes(
    date_from: date = Query(..., description="inicio del rango"),
    date_to: date = Query(..., description="fin del rango (inclusive)"),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await market_code_service.market_code_report(
            session, property_code=code, date_from=date_from, date_to=date_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
