"""Tabs 7.6.1 (Tip 10%) y 7.6.2 (Extra Tips) -- cuánto se cobró en gratuidades
(Collected, real, desde Integrity) vs cuánto se les pagó a los empleados
(Paid, siempre manual) + saldo pendiente de pagar, corrido día a día.

Dos tipos de gratuidad, cada uno con su cuenta real en Integrity (§
GRATUITY_KINDS): "Tip 10%" es el cargo por servicio 10% obligatorio (Costa
Rica); "Extra Tips" son propinas voluntarias adicionales. El tab 7.6 ("Tips &
Extra Tips") es la SUMA de ambos -- kind especial "all" (§ decisión del
owner, "7.6 es la suma de los dos"), derivado 100% de 7.6.1+7.6.2, sin su
propio pago manual (editar el pago se hace en el tab de cada tipo, 7.6.1 o
7.6.2 -- 7.6 es de solo lectura).

A diferencia de Deposit Ledger (Tab 7.5), acá NO hay ningún día con débito
real a estas cuentas -- el pago a los empleados se hace en efectivo, fuera
de Opera/Integrity, así que "Paid" es SIEMPRE carga manual (`TipsPayoutEntry`,
discriminada por `kind`), incluso en días ya auditados. "Collected" es
siempre el número real cuando el día está ingestado, $0 si no (desde el 1 de
julio de 2026, cuando Daily-Ops empezó a auditar días reales)."""
from __future__ import annotations

from datetime import date as date_cls
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Property, TipsPayoutEntry
from app.services import config_service
from app.services.integrity_account_service import account_by_date, ingested_dates

EARLIEST_DATE = date_cls(2026, 7, 1)

# kind -> (label, cuenta real en Integrity). "extra_tips" es el mismo que ya
# usa el tab original 7.6 (cuenta "TIPS - PAYABLE", tcodes 1054 "F&B EXTRA
# TIPS" + 1055 "EXTRA TIPS-OPERATION"); "service_charge_10" es nuevo (cuenta
# "10% SERVICE CHARGE", confirmada en producción 2026-07-03).
GRATUITY_KINDS: dict[str, dict[str, str]] = {
    "service_charge_10": {"label": "Tip 10%", "account_name": "10% SERVICE CHARGE"},
    "extra_tips": {"label": "Extra Tips", "account_name": "TIPS - PAYABLE"},
}

# "all" (Tab 7.6) no es un tipo real -- es la suma de los dos de arriba,
# derivada siempre, nunca con su propio pago manual.
ALL_KIND = "all"
ALL_KIND_LABEL = "Tips & Extra Tips (combined)"


def _account_name(kind: str) -> str:
    if kind not in GRATUITY_KINDS:
        raise ValueError(f"kind inválido '{kind}'. Válidos: {list(GRATUITY_KINDS)} o '{ALL_KIND}'")
    return GRATUITY_KINDS[kind]["account_name"]


# kind -> key de config_service (Tab 6.9). El default de cada key es el
# account_name de GRATUITY_KINDS, asi que sin override el comportamiento es
# identico; con override, Bismark cambia la cuenta sin re-deploy.
_KIND_TO_CFG = {
    "service_charge_10": "tips_service_charge_account_name",
    "extra_tips": "tips_extra_account_name",
}


async def _account_name_cfg(session: AsyncSession, pid, kind: str) -> str:
    _account_name(kind)  # valida el kind (levanta ValueError si es invalido)
    return await config_service.get_param(session, pid, _KIND_TO_CFG[kind])


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _paid_by_date(session: AsyncSession, pid, kind: str, start: date_cls,
                        end: date_cls) -> dict[date_cls, TipsPayoutEntry]:
    rows = (await session.execute(
        select(TipsPayoutEntry).where(
            TipsPayoutEntry.property_id == pid, TipsPayoutEntry.kind == kind,
            TipsPayoutEntry.date >= start, TipsPayoutEntry.date <= end,
        )
    )).scalars().all()
    return {e.date: e for e in rows}


async def _daily_rows(session: AsyncSession, pid, kind: str, start: date_cls, end: date_cls) -> list[dict]:
    """Una fila por día: Collected real (Integrity, $0 si el día no está
    ingestado) + Paid siempre manual ($0 si no hay entrada). `kind="all"`
    (Tab 7.6) suma las filas de cada tipo real, día por día."""
    if kind == ALL_KIND:
        per_kind = [await _daily_rows(session, pid, k, start, end) for k in GRATUITY_KINDS]
        return [{
            "date": rows_for_day[0]["date"],
            "collected_usd": round(sum(r["collected_usd"] for r in rows_for_day), 2),
            "paid_usd": round(sum(r["paid_usd"] for r in rows_for_day), 2),
            "ingested": any(r["ingested"] for r in rows_for_day),
            "note": None,
        } for rows_for_day in zip(*per_kind)]

    account_name = await _account_name_cfg(session, pid, kind)
    ingested = await ingested_dates(session, pid, start, end)
    collected = await account_by_date(session, pid, account_name, start, end)
    paid = await _paid_by_date(session, pid, kind, start, end)

    rows = []
    d = start
    while d <= end:
        collected_usd = collected.get(d, (0.0, 0.0, 0.0, 0.0))[0] if d in ingested else 0.0
        entry = paid.get(d)
        paid_usd = float(entry.paid_usd) if entry else 0.0
        rows.append({
            "date": d, "collected_usd": round(collected_usd, 2), "paid_usd": round(paid_usd, 2),
            "ingested": d in ingested, "note": entry.note if entry else None,
        })
        d += timedelta(days=1)
    return rows


async def _net_range(session: AsyncSession, pid, kind: str, start: date_cls, end: date_cls) -> float:
    """Σ(collected-paid) en [start,end] sin materializar fila por día.
    `kind="all"` suma el neto de cada tipo real."""
    if kind == ALL_KIND:
        return sum([await _net_range(session, pid, k, start, end) for k in GRATUITY_KINDS])
    account_name = await _account_name_cfg(session, pid, kind)
    ingested = await ingested_dates(session, pid, start, end)
    collected = await account_by_date(session, pid, account_name, start, end)
    paid = await _paid_by_date(session, pid, kind, start, end)
    net = sum(v[0] for d, v in collected.items() if d in ingested)
    net -= sum(float(e.paid_usd) for e in paid.values())
    return net


async def ledger_range(session: AsyncSession, kind: str, start: date_cls, end: date_cls,
                       property_code: str = "COWLCR") -> dict:
    """Saldo de apertura del rango (desde 2026-07-01, cuando empieza la
    ingesta real) + una fila por día + saldo de cierre."""
    if end < start:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")
    pid = await _property_id(session, property_code)
    opening_balance = 0.0
    if start > EARLIEST_DATE:
        opening_balance = round(await _net_range(session, pid, kind, EARLIEST_DATE, start - timedelta(days=1)), 2)
    daily = await _daily_rows(session, pid, kind, start, end)

    running = opening_balance
    rows = []
    for r in daily:
        running = round(running + r["collected_usd"] - r["paid_usd"], 2)
        rows.append({
            "date": r["date"].isoformat(), "collected_usd": r["collected_usd"],
            "paid_usd": r["paid_usd"], "balance_usd": running,
            "note": r["note"], "ingested": r["ingested"],
        })
    label = ALL_KIND_LABEL if kind == ALL_KIND else GRATUITY_KINDS[kind]["label"]
    return {
        "kind": kind, "label": label,
        "start": start.isoformat(), "end": end.isoformat(),
        "opening_balance": opening_balance, "closing_balance": running, "rows": rows,
    }


async def today_mtd(session: AsyncSession, kind: str, business_date: date_cls,
                    property_code: str = "COWLCR") -> dict:
    """KPIs rápidos Today + MTD (Collected/Paid/Balance corrido)."""
    pid = await _property_id(session, property_code)
    month_start = max(business_date.replace(day=1), EARLIEST_DATE)

    today_rows = await _daily_rows(session, pid, kind, business_date, business_date)
    today = today_rows[0]

    mtd_rows = await _daily_rows(session, pid, kind, month_start, business_date) if month_start <= business_date else []
    mtd_collected = round(sum(r["collected_usd"] for r in mtd_rows), 2)
    mtd_paid = round(sum(r["paid_usd"] for r in mtd_rows), 2)

    opening_balance = 0.0
    if month_start > EARLIEST_DATE:
        opening_balance = round(await _net_range(session, pid, kind, EARLIEST_DATE, month_start - timedelta(days=1)), 2)

    return {
        "business_date": business_date.isoformat(),
        "today": {"collected_usd": today["collected_usd"], "paid_usd": today["paid_usd"]},
        "mtd": {"collected_usd": mtd_collected, "paid_usd": mtd_paid},
        "balance_usd": round(opening_balance + mtd_collected - mtd_paid, 2),
    }


async def set_payout(session: AsyncSession, kind: str, entry_date: date_cls, paid_usd: float,
                     note: str | None = None, property_code: str = "COWLCR") -> dict:
    """Alta/edición del pago manual a empleados de un día, por tipo (upsert).
    `kind="all"` (Tab 7.6) es de solo lectura -- editar el pago se hace en el
    tab de cada tipo real (7.6.1 o 7.6.2)."""
    if kind == ALL_KIND:
        raise ValueError(f"'{ALL_KIND}' es la suma de los dos tipos, de solo lectura -- "
                          "editá el pago en Tip 10% o Extra Tips.")
    _account_name(kind)  # valida el kind
    pid = await _property_id(session, property_code)
    await session.execute(
        pg_insert(TipsPayoutEntry)
        .values(property_id=pid, kind=kind, date=entry_date, paid_usd=paid_usd, note=note)
        .on_conflict_do_update(
            index_elements=["property_id", "kind", "date"],
            set_={"paid_usd": paid_usd, "note": note},
        )
    )
    await session.commit()
    return {"kind": kind, "date": entry_date.isoformat(), "paid_usd": paid_usd, "note": note}
