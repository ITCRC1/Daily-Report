"""Endpoints de Tab 6.4 -- Revenue real diario por depto (Year to Date)."""
from __future__ import annotations

from datetime import date as date_cls

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import revenue_actual_service

router = APIRouter(prefix="/master-data/revenue-actual", tags=["revenue-actual"])
settings = get_settings()


@router.post("/upload")
async def revenue_actual_upload(
    file: UploadFile = File(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    content = await file.read()
    try:
        return await revenue_actual_service.upload_daily_grid(session, content, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def revenue_actual_view(
    prop: str = Query(default=None),
    date_from: date_cls | None = Query(default=None),
    date_to: date_cls | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    code = prop or settings.DEFAULT_PROPERTY
    return await revenue_actual_service.daily_view(session, property_code=code, date_from=date_from, date_to=date_to)
