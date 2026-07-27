"""Endpoints de Deposit Ledger (Tab 7.5) -- carga manual de depositado/aplicado."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import deposit_ledger_service

router = APIRouter(prefix="/deposit-ledger", tags=["deposit-ledger"])
settings = get_settings()


class EntryBody(BaseModel):
    deposited_usd: float = 0.0
    applied_usd: float = 0.0
    note: str | None = None


class OpeningBody(BaseModel):
    anchor_date: date
    balance_usd: float = 0.0
    note: str | None = None


@router.get("")
async def deposit_ledger_range(
    date_from: date = Query(...), date_to: date = Query(...),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    """Rango [date_from, date_to]: saldo de apertura + una fila por día + saldo de cierre."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await deposit_ledger_service.ledger_range(session, date_from, date_to, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/entries/{entry_date}")
async def deposit_ledger_set_entry(
    entry_date: date, body: EntryBody, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Alta/edición de la entrada manual de un día (upsert)."""
    code = prop or settings.DEFAULT_PROPERTY
    return await deposit_ledger_service.set_entry(
        session, entry_date, body.deposited_usd, body.applied_usd, body.note, property_code=code,
    )


@router.delete("/entries/{entry_date}")
async def deposit_ledger_delete_entry(
    entry_date: date, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    await deposit_ledger_service.delete_entry(session, entry_date, property_code=code)
    return {"deleted": entry_date.isoformat()}


@router.get("/opening")
async def deposit_ledger_get_opening(
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict | None:
    code = prop or settings.DEFAULT_PROPERTY
    return await deposit_ledger_service.get_opening(session, property_code=code)


@router.put("/opening")
async def deposit_ledger_set_opening(
    body: OpeningBody, prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    return await deposit_ledger_service.set_opening(
        session, body.anchor_date, body.balance_usd, body.note, property_code=code,
    )
