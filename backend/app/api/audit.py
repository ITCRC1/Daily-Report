"""Endpoints de auditoría (Tab 2): resumen + detalle de reconciliación + gate (§2.7)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])
settings = get_settings()


class ReleaseIn(BaseModel):
    released_by: str | None = None
    override_flag: bool = False
    override_note: str | None = None


class RefreshIn(BaseModel):
    refreshed_by: str | None = None


class ReopenIn(BaseModel):
    reopen_note: str | None = None


class FindingUpdateIn(BaseModel):
    estado: str  # 'abierto' | 'cerrado' (§constraint de dim)
    resolved_note: str | None = None


# OJO: estas 2 rutas van ANTES de "/{business_date}" -- FastAPI matchea por
# orden de registro y "findings" con forma de path igual a {business_date}
# (un solo segmento) rompería con 422 si quedara después.
@router.get("/findings")
async def findings_view(
    estado: str | None = Query(default="abierto"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """2.10 — acumulado Year to Date de hallazgos (no limitado a un solo día).
    Default: todos los que siguen `estado=abierto` desde el 1-ene hasta hoy."""
    code = prop or settings.DEFAULT_PROPERTY
    return await audit_service.list_findings(
        session, property_code=code, estado=estado, date_from=date_from, date_to=date_to)


@router.patch("/findings/{finding_id}")
async def findings_update(
    finding_id: uuid.UUID, body: FindingUpdateIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Cambia estado (abierto/cerrado) + comentario amplio -- sobrevive a
    re-correr 'Ingerir + Auditar' (ver `_upsert_finding` en el servicio)."""
    if body.estado not in ("abierto", "cerrado"):
        raise HTTPException(status_code=400, detail="estado debe ser 'abierto' o 'cerrado'.")
    try:
        return await audit_service.update_finding(
            session, finding_id, body.estado, body.resolved_note)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{business_date}")
async def audit_view(
    business_date: date,
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reconciliación del día (KPIs + filas). Recomputa desde lo persistido."""
    code = prop or settings.DEFAULT_PROPERTY
    return await audit_service.get_audit(session, business_date, property_code=code)


@router.post("/{business_date}/release")
async def release_view(
    business_date: date,
    body: ReleaseIn = ReleaseIn(),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Libera el daily a dueños (§2.6/§2.7) — respeta gate_hard, permite override."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await audit_service.release_day(
            session, business_date, property_code=code,
            released_by=body.released_by, override_flag=body.override_flag,
            override_note=body.override_note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{business_date}/reopen")
async def reopen_view(
    business_date: date,
    body: ReopenIn = ReopenIn(),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reabre un daily ya liberado (antes no existía forma de deshacer
    'Liberar a dueños' desde la UI)."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await audit_service.reopen_day(session, business_date, property_code=code,
                                              reopen_note=body.reopen_note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{business_date}/refresh")
async def refresh_view(
    business_date: date,
    body: RefreshIn = RefreshIn(),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """REFRESH (§2.6): re-lee insumos vigentes y recalcula, dejando traza."""
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await audit_service.refresh_day(
            session, business_date, property_code=code, refreshed_by=body.refreshed_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
