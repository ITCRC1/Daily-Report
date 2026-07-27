"""Admin de navegación — prender/apagar tabs elegibles por propiedad.

Los tabs deshabilitados se guardan en app_config (key `nav_disabled_tabs`, JSON
de ids). El app no tiene autenticación, así que tanto el GET como el PUT son
públicos.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import AppConfig, Property

router = APIRouter(prefix="/config", tags=["config"])
settings = get_settings()
_KEY = "nav_disabled_tabs"


class NavConfigIn(BaseModel):
    disabled: list[str] = []


async def _pid(session: AsyncSession, code: str):
    pid = (await session.execute(select(Property.id).where(Property.code == code))).scalar_one_or_none()
    if pid is None:
        raise HTTPException(status_code=400, detail=f"Propiedad '{code}' no existe.")
    return pid


async def _row(session, pid):
    return (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == _KEY)
    )).scalar_one_or_none()


@router.get("/nav")
async def get_nav(prop: str = Query(default=None), session: AsyncSession = Depends(get_session)) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    pid = await _pid(session, code)
    row = await _row(session, pid)
    disabled = json.loads(row.value) if (row and row.value) else []
    return {"disabled": disabled}


@router.put("/nav")
async def set_nav(body: NavConfigIn, prop: str = Query(default=None),
                  session: AsyncSession = Depends(get_session)) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    pid = await _pid(session, code)
    val = json.dumps(body.disabled)
    row = await _row(session, pid)
    if row is None:
        session.add(AppConfig(property_id=pid, key=_KEY, value=val))
    else:
        row.value = val
    await session.commit()
    return {"disabled": body.disabled}
