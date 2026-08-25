"""Endpoints de export (etapa 8): Excel del día (Revenue+Cash+Auditoría), PDF
ejecutivo, y el export genérico de tablas que usan TODOS los tabs.
"""
from __future__ import annotations

import re
from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.export.table import build_workbook
from app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])
settings = get_settings()

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExportColumn(BaseModel):
    label: str = ""
    type: str = "text"          # text | money | pct | int | number | date
    width: float | None = None


class ExportGroup(BaseModel):
    label: str = ""
    span: int = 1


class ExportSheet(BaseModel):
    name: str = "Hoja"
    title: str | None = None
    subtitle: str | None = None
    caption: str | None = None
    header_groups: list[ExportGroup] = Field(default_factory=list)
    columns: list[ExportColumn] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    total_rows: list[int] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ExportRequest(BaseModel):
    """Lo que manda cualquier tab para bajar lo que está viendo."""
    filename: str = "DAILY-OPS"
    title: str = "DAILY-OPS"
    subtitle: str | None = None
    sheets: list[ExportSheet] = Field(default_factory=list)


def _nombre_archivo(base: str) -> str:
    """Sanea el nombre: sin separadores de ruta ni comillas, que van al header
    Content-Disposition."""
    limpio = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" .") or "DAILY-OPS"
    return limpio[:120]


@router.post("/table/excel")
async def export_table_excel(body: ExportRequest) -> StreamingResponse:
    """Export genérico: recibe la(s) tabla(s) que el tab está mostrando y
    devuelve un .xlsx con el formato de la casa.

    No recalcula nada — el Excel dice exactamente lo mismo que la pantalla, que
    es justamente lo que se le pide a un libro contable. Los números llegan como
    números (no como texto), así que en Excel se pueden sumar y filtrar.
    """
    total_filas = sum(len(s.rows) for s in body.sheets)
    if total_filas > 200_000:
        raise HTTPException(status_code=413, detail="Demasiadas filas para un solo Excel.")
    content = build_workbook(body.model_dump())
    filename = f"{_nombre_archivo(body.filename)}.xlsx"
    return StreamingResponse(
        BytesIO(content),
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
