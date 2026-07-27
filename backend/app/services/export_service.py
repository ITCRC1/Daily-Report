"""Orquesta el export del día (etapa 8): junta Revenue+Cash+Auditoría ya
calculados por sus propios servicios y delega el armado del archivo a
app/export/excel.py o app/export/pdf.py. No repite ningún cálculo.
"""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy.ext.asyncio import AsyncSession

from app.export.excel import build_daily_excel
from app.export.pdf import build_daily_pdf
from app.services import audit_service, cash_service, revenue_service


async def _gather(session: AsyncSession, business_date: date_cls, property_code: str):
    revenue = await revenue_service.daily_report(session, business_date, property_code=property_code)
    cash = await cash_service.daily_cash(session, business_date, property_code=property_code)
    audit = await audit_service.get_audit(session, business_date, property_code=property_code)
    return revenue, cash, audit


async def daily_excel(session: AsyncSession, business_date: date_cls,
                      property_code: str = "COWLCR") -> bytes:
    revenue, cash, audit = await _gather(session, business_date, property_code)
    return build_daily_excel(revenue, cash, audit, business_date.isoformat(), property_code)


async def daily_pdf(session: AsyncSession, business_date: date_cls,
                    property_code: str = "COWLCR") -> bytes:
    revenue, cash, audit = await _gather(session, business_date, property_code)
    return build_daily_pdf(revenue, cash, audit, business_date.isoformat(), property_code)
