"""Endpoints de ingesta por día (etapa 1) + disparo de auditoría (etapa 4)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import audit_service, ingest_service

router = APIRouter(prefix="/ingest", tags=["ingest"])
settings = get_settings()


@router.post("/{business_date}")
async def ingest_and_audit(
    business_date: date,
    prop: str = Query(default=None, description="código de propiedad (default COWLCR)"),
    run_audit: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Botón "Ingerir + Auditar" de Tab 2 -- re-ingesta los archivos YA SUBIDOS
    por Tab 1 (uploads/inputs/<fecha>) y (opcional) corre la auditoría.

    Bug real corregido (2026-07-03): sin pasar `inputs_dir` explícito, caía al
    default de `ingest_service.INPUTS_ROOT` (goldens/inputs, fixtures de test,
    vacío en producción) en vez de `uploads/inputs` (donde Tab 1 realmente
    guarda los archivos) -- el mismo bug que ya se había corregido para
    `refresh_day()`, pero que seguía latente acá. En producción esto BORRÓ
    datos reales recién subidos (2026-07-02): el usuario subió los archivos
    por Tab 1 (OK), y al apretar "Ingerir + Auditar" en Tab 2 el reemplazo
    total encontró 0 archivos en goldens/inputs y dejó todo en cero."""
    code = prop or settings.DEFAULT_PROPERTY
    uploads_dir = ingest_service.uploads_root() / business_date.isoformat()
    try:
        result = await ingest_service.ingest_day(
            session, business_date, property_code=code, inputs_dir=uploads_dir,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if run_audit:
        result["audit"] = await audit_service.run_audit(session, business_date, property_code=code)
    return result


@router.get("/status")
async def ingest_status(
    year: int = Query(..., description="año calendario, ej. 2026"),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Malla de 365 días × sistema (Tab 1): Incompleto/Listo/Auditado/Cerrado."""
    code = prop or settings.DEFAULT_PROPERTY
    return await ingest_service.day_status_grid(session, year, property_code=code)


@router.post("/{business_date}/upload")
async def upload_and_ingest(
    business_date: date,
    files: list[UploadFile] = File(..., description="Opera XML + Integrity/POS Excel del día"),
    prop: str = Query(default=None, description="código de propiedad (default COWLCR)"),
    run_audit: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Tab 1 — batch real: sube los archivos crudos de un día, clasifica por
    contenido (§2.8) e ingesta. Reemplazo total: pisa lo subido antes para ese
    día (§2.5), no acumula entre cargas."""
    if not files:
        raise HTTPException(status_code=400, detail="No se recibió ningún archivo.")

    code = prop or settings.DEFAULT_PROPERTY
    upload_dir = ingest_service.uploads_root() / business_date.isoformat()
    upload_dir.mkdir(parents=True, exist_ok=True)
    for existing in upload_dir.iterdir():
        if existing.is_file():
            existing.unlink()

    saved = []
    for uf in files:
        if not uf.filename:
            continue
        content = await uf.read()
        (upload_dir / uf.filename).write_bytes(content)
        saved.append(uf.filename)

    try:
        result = await ingest_service.ingest_day(
            session, business_date, property_code=code, inputs_dir=upload_dir,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result["uploaded_files"] = saved
    if run_audit:
        result["audit"] = await audit_service.run_audit(session, business_date, property_code=code)
    return result
