"""Endpoints de Forecast (Tab 6.1.1) — gemelo de budget.py.

Mismo ciclo que el Budget: descargar plantilla → llenar offline en Excel →
subir → reemplazo total del año → se deriva el diario automáticamente.
"""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import forecast_service

router = APIRouter(prefix="/master-data/forecast", tags=["forecast"])
settings = get_settings()


@router.get("/template")
async def forecast_template(
    year: int = Query(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    code = prop or settings.DEFAULT_PROPERTY
    content = await forecast_service.build_template(session, year, property_code=code)
    filename = f"Forecast_{code}_{year}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/upload")
async def forecast_upload(
    year: int = Query(...), file: UploadFile = File(...),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    content = await file.read()
    try:
        return await forecast_service.upload_and_replace(session, year, content, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def forecast_monthly_view(
    year: int = Query(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    code = prop or settings.DEFAULT_PROPERTY
    return await forecast_service.monthly_summary(session, year, property_code=code)


@router.get("/daily")
async def forecast_daily_view(
    year: int = Query(...), month: int = Query(..., ge=1, le=12),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    code = prop or settings.DEFAULT_PROPERTY
    return await forecast_service.daily_summary(session, year, month, property_code=code)
