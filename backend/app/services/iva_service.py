"""Tab 7.7 -- IVA 13%: impuesto de ventas devengado por día, real desde
Integrity (cuenta "VAT - CREDITS (IVA DEVENGADO - INGRESOS) - 13%", tcodes
1050 "IVA 13%" y 1051 "IVA 13% POS"). Puramente informativo -- no hay
"aplicado"/pagado que trackear acá (el pago del IVA al fisco es un trámite
aparte, fuera de alcance de este tab), así que no hace falta carga manual.

Se muestra en USD y CRC (el IVA en Costa Rica se declara/paga en colones,
aunque el resto de la app trabaja en USD)."""
from __future__ import annotations

from datetime import date as date_cls
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Property
from app.services import config_service
from app.services.integrity_account_service import account_by_date, ingested_dates

# Default historico; el valor efectivo se lee de app_config via config_service
# (editable en Tab 6.9). Ver PARAM_DEFS['iva_account_name'].


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _daily_rows(session: AsyncSession, pid, start: date_cls, end: date_cls) -> list[dict]:
    ingested = await ingested_dates(session, pid, start, end)
    iva_account = await config_service.get_param(session, pid, "iva_account_name")
    accrued = await account_by_date(session, pid, iva_account, start, end)

    rows = []
    d = start
    while d <= end:
        credit_usd, _debit_usd, credit_crc, _debit_crc = accrued.get(d, (0.0, 0.0, 0.0, 0.0)) if d in ingested else (0.0, 0.0, 0.0, 0.0)
        rows.append({
            "date": d.isoformat(), "accrued_usd": round(credit_usd, 2), "accrued_crc": round(credit_crc, 2),
            "ingested": d in ingested,
        })
        d += timedelta(days=1)
    return rows


async def range_view(session: AsyncSession, start: date_cls, end: date_cls,
                     property_code: str = "COWLCR") -> dict:
    if end < start:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")
    pid = await _property_id(session, property_code)
    rows = await _daily_rows(session, pid, start, end)
    total_usd = round(sum(r["accrued_usd"] for r in rows), 2)
    total_crc = round(sum(r["accrued_crc"] for r in rows), 2)
    return {"start": start.isoformat(), "end": end.isoformat(),
            "rows": rows, "total_usd": total_usd, "total_crc": total_crc}


async def today_mtd(session: AsyncSession, business_date: date_cls,
                    property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    today_rows = await _daily_rows(session, pid, business_date, business_date)
    month_start = business_date.replace(day=1)
    mtd_rows = await _daily_rows(session, pid, month_start, business_date)
    return {
        "business_date": business_date.isoformat(),
        "today": {"accrued_usd": today_rows[0]["accrued_usd"], "accrued_crc": today_rows[0]["accrued_crc"]},
        "mtd": {
            "accrued_usd": round(sum(r["accrued_usd"] for r in mtd_rows), 2),
            "accrued_crc": round(sum(r["accrued_crc"] for r in mtd_rows), 2),
        },
    }
