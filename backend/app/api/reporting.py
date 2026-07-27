"""Tab 7.4 -- Power Query endpoints (dataset catalog + column-projected query
+ CSV/Excel export). See app/services/query_service.py for the dataset
allowlist and why this is not a free-text SQL builder."""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import query_service as svc

router = APIRouter(prefix="/reporting", tags=["reporting"])
settings = get_settings()


def _parse_columns(columns: str | None) -> list[str]:
    return [c.strip() for c in columns.split(",") if c.strip()] if columns else []


@router.get("/datasets")
async def datasets_list() -> list[dict]:
    return svc.list_datasets()


@router.get("/query")
async def query(
    dataset: str = Query(...), columns: str = Query(default=""),
    date_from: date | None = Query(default=None), date_to: date | None = Query(default=None),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> list[dict]:
    try:
        return await svc.run_query(
            session, dataset, _parse_columns(columns), date_from, date_to,
            property_code=prop or settings.DEFAULT_PROPERTY,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/query/export")
async def query_export(
    dataset: str = Query(...), columns: str = Query(default=""),
    date_from: date | None = Query(default=None), date_to: date | None = Query(default=None),
    fmt: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    prop: str = Query(default=None), session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    try:
        rows = await svc.run_query(
            session, dataset, _parse_columns(columns), date_from, date_to,
            property_code=prop or settings.DEFAULT_PROPERTY,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    headers = list(rows[0].keys()) if rows else _parse_columns(columns)
    filename = f"{dataset}.{fmt}"

    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = dataset[:31]
        ws.append(headers)
        for r in rows:
            ws.append([r.get(h) for h in headers])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow([r.get(h) for h in headers])
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
