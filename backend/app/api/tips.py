"""Endpoints de gratuidades: Tab 7.6.1 Tip 10% + Tab 7.6.2 Extra Tips (y el
tab original 7.6, que sigue apuntando a kind="extra_tips")."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import tips_service

router = APIRouter(prefix="/tips", tags=["tips"])
settings = get_settings()


class PayoutBody(BaseModel):
    paid_usd: float = 0.0
    note: str | None = None


@router.get("/kinds")
async def tips_kinds() -> dict:
    return tips_service.GRATUITY_KINDS


@router.get("/{kind}/today-mtd")
async def tips_today_mtd(
    kind: str, business_date: date = Query(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await tips_service.today_mtd(session, kind, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{kind}")
async def tips_range(
    kind: str, date_from: date = Query(...), date_to: date = Query(...),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await tips_service.ledger_range(session, kind, date_from, date_to, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{kind}/payout/{entry_date}")
async def tips_set_payout(
    kind: str, entry_date: date, body: PayoutBody, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await tips_service.set_payout(session, kind, entry_date, body.paid_usd, body.note, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
