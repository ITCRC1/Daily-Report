"""Endpoint On The Books (Tab 8) — reporte mensual Budget vs OTB + NET GAP."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import ontb_service

router = APIRouter(prefix="/ontb", tags=["ontb"])
settings = get_settings()


@router.get("")
async def ontb(
    year: int = Query(..., description="año calendario, ej. 2026"),
    as_of: date = Query(default=None, description="corte final (snapshot OTB a mostrar)"),
    compare_to: date = Query(default=None, description="corte inicial (para la variación)"),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await ontb_service.ontb_report(session, year, property_code=code,
                                              as_of=as_of, compare_to=compare_to)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/heatmap")
async def ontb_heatmap(
    year: int = Query(...), as_of: date = Query(default=None),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await ontb_service.ontb_heatmap(session, year, property_code=code, as_of=as_of)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pacing")
async def ontb_pacing(
    prop: str = Query(default=None), limit: int = Query(default=8),
    year: int = Query(default=None, description="filtra el total OTB al año (multi-año)"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await ontb_service.ontb_pacing(session, property_code=code, limit=limit, year=year)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
