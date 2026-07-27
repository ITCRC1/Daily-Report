"""Endpoints de export (etapa 8): Excel del día (Revenue+Cash+Auditoría) y PDF ejecutivo."""
from __future__ import annotations

from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])
settings = get_settings()


@router.get("/{business_date}/excel")
async def export_excel(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Excel del día: hojas Revenue, Cash, Auditoria — mismos datos que las páginas."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        content = await export_service.daily_excel(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = f"DAILY-OPS_{code}_{business_date.isoformat()}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{business_date}/pdf")
async def export_pdf(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """PDF ejecutivo (una página) del día — pensado para enviar a dueños."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        content = await export_service.daily_pdf(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = f"DAILY-OPS_{code}_{business_date.isoformat()}.pdf"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
