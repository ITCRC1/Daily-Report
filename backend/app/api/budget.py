"""Endpoints de Budget (Tab 6.1 Monthly by Department + 6.5 Daily derivado).

Ciclo (§2 decisión cerrada #2): descargar plantilla → llenar offline en Excel
→ subir → reemplazo total del año → se deriva el diario automáticamente.
"""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import budget_service

router = APIRouter(prefix="/master-data/budget", tags=["budget"])
settings = get_settings()


@router.get("/template")
async def budget_template(
    year: int = Query(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    code = prop or settings.DEFAULT_PROPERTY
    content = await budget_service.build_template(session, year, property_code=code)
    filename = f"Budget_{code}_{year}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/upload")
async def budget_upload(
    year: int = Query(...), file: UploadFile = File(...),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    content = await file.read()
    try:
        return await budget_service.upload_and_replace(session, year, content, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
async def budget_monthly_view(
    year: int = Query(...), prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    code = prop or settings.DEFAULT_PROPERTY
    return await budget_service.monthly_summary(session, year, property_code=code)


@router.get("/daily")
async def budget_daily_view(
    year: int = Query(...), month: int = Query(..., ge=1, le=12),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    code = prop or settings.DEFAULT_PROPERTY
    return await budget_service.daily_summary(session, year, month, property_code=code)
