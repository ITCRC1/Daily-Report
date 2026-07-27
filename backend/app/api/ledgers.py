"""Endpoints de ledgers (auxiliares) — saldos corrientes + edición de apertura (2.3)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import ledger_service

router = APIRouter(prefix="/ledgers", tags=["ledgers"])
settings = get_settings()


class OpeningIn(BaseModel):
    ledger: str          # guest | package | ar | deposit
    amount: float
    note: str | None = None


@router.get("/{business_date}")
async def ledgers_view(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    code = prop or settings.DEFAULT_PROPERTY
    return await ledger_service.balances_for_day(session, business_date, property_code=code)


@router.get("/{business_date}/detail")
async def ledger_detail(
    business_date: date,
    ledger: str = Query(..., description="guest|package|ar|deposit"),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Detalle auxiliar (folios) que respalda el saldo del ledger."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await ledger_service.ledger_detail(session, business_date, ledger, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{business_date}/opening")
async def set_opening(
    business_date: date,
    body: OpeningIn,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Fija/edita el saldo de apertura de un ledger en la fecha (re-ancla para 'empezar bien')."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await ledger_service.set_opening(
            session, business_date, body.ledger, body.amount, body.note, property_code=code
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
