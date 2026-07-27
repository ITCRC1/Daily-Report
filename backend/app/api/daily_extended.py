"""Tab 9 · Daily Extendido."""
from __future__ import annotations

from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services import daily_extended_service

router = APIRouter(prefix="/daily-extended", tags=["daily-extended"])
settings = get_settings()


class SpaTreatmentsIn(BaseModel):
    treatments: int


class FbCustomersIn(BaseModel):
    customers: int


class FbCoversIn(BaseModel):
    outlet: str
    meal_period: str
    covers: int


@router.get("/summary")
async def summary(
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.summary(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rooms-by-segment")
async def rooms_by_segment(
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.rooms_by_segment(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/revenue-detail")
async def revenue_detail(
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.revenue_detail(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fb-by-meal-period")
async def fb_by_meal_period(
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.fb_by_meal_period(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/fb-customers")
async def set_fb_customers(
    body: FbCustomersIn,
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.set_fb_customers(
            session, business_date, body.customers, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/fb-covers")
async def set_fb_covers(
    body: FbCoversIn,
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.set_fb_covers(
            session, business_date, body.outlet, body.meal_period, body.covers,
            property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fb-covers/template")
async def fb_covers_template(
    year: int = Query(...), month: int = Query(..., ge=1, le=12),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    code = prop or settings.DEFAULT_PROPERTY
    try:
        data = await daily_extended_service.build_covers_template(session, year, month, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = f"FB_Covers_{code}_{year}-{month:02d}.xlsx"
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/fb-covers/upload")
async def fb_covers_upload(
    file: UploadFile = File(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.upload_covers_grid(
            session, await file.read(), property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fb-revenue-recap")
async def fb_revenue_recap(
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.fb_revenue_recap(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/beverage-detail")
async def beverage_detail(
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.beverage_detail(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/spa")
async def spa(
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.spa_summary(session, business_date, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/spa/treatments")
async def set_spa_treatments(
    body: SpaTreatmentsIn,
    business_date: date = Query(...),
    prop: str = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    code = prop or settings.DEFAULT_PROPERTY
    try:
        return await daily_extended_service.set_spa_treatments(
            session, business_date, body.treatments, property_code=code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
