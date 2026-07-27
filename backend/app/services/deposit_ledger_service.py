"""Tab 7.5 -- Deposit Ledger (Bank): cuánto entra en depósito y cuánto se
aplica, con saldo pendiente de aplicar corrido + ancla YTD opcional (mismo
patrón que RoomStatOpening/LedgerOpening).

FUENTE REAL (2026-07-03, hallazgo del owner): Integrity ya trae la cuenta
puente de anticipo "ADELANTO HPDS LODGING" (clase 2xxx, Pasivos) -- la MISMA
cuenta que `cash_service` excluye del lado banco para no duplicar la partida
doble (ver `_payment_lines_for_day`, filtro `cuenta.startswith("1")`). Un
CRÉDITO a esa cuenta es un pago que entra como anticipo/depósito sin aplicar
aún (ej. tcode 3726/3740, "PAYMENT ..."); un DÉBITO es esa plata siendo
aplicada/liberada contra el folio (ej. tcode 9910, "DEPOSIT TRANSFER AT
CHECK IN"). Verificado contra producción real: 2026-07-01 débito $3,832.72
(aplicado), 2026-07-02 créditos $4,012.86+$2,696.90 (depositado).

Por eso: un día YA INGESTADO (tiene algún renglón de Integrity) usa este
cálculo real, automático -- nunca hace falta tipearlo. La carga MANUAL
(`DepositLedgerEntry`) es solo el respaldo para días SIN ingesta (antes de
julio 2026, cuando Daily-Ops no estaba en producción) -- mismo criterio
"real gana, nunca se suman las dos fuentes el mismo día" que ya usan
revenue_service/cash_service para sus propios respaldos.

Sin relación con el "Deposit Ledger" de Tab 2.3 (`ledger_service.LEDGERS
["deposit"]`, columna `OperaTxn.deposit_ledger`) -- ese es el ledger PMS de
anticipos/depósitos de HUÉSPEDES, un concepto de negocio distinto que
comparte el nombre por casualidad.
"""
from __future__ import annotations

from datetime import date as date_cls
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DepositLedgerEntry, DepositLedgerOpening, Property
from app.services import config_service
from app.services.integrity_account_service import account_by_date, ingested_dates

# Cuenta puente de anticipo real. Default historico; el valor efectivo se lee
# de app_config via config_service (editable en Tab 6.9, key
# 'deposit_suspense_account_name') -- si Bismark renombra la cuenta en Integrity
# se corrige desde la UI sin re-deploy.

EARLIEST_DATE = date_cls(2020, 1, 1)  # piso razonable para sumar sin ancla


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _get_opening(session: AsyncSession, pid) -> DepositLedgerOpening | None:
    return (await session.execute(
        select(DepositLedgerOpening).where(DepositLedgerOpening.property_id == pid)
    )).scalar_one_or_none()


async def _manual_by_date(session: AsyncSession, pid, start: date_cls,
                          end: date_cls) -> dict[date_cls, DepositLedgerEntry]:
    rows = (await session.execute(
        select(DepositLedgerEntry).where(
            DepositLedgerEntry.property_id == pid,
            DepositLedgerEntry.date >= start, DepositLedgerEntry.date <= end,
        )
    )).scalars().all()
    return {e.date: e for e in rows}


async def _daily_rows(session: AsyncSession, pid, start: date_cls, end: date_cls) -> list[dict]:
    """Una fila por día en [start, end]: real (Integrity) si el día ya está
    ingestado, si no la entrada manual (o $0 si tampoco hay manual) -- nunca
    se suman las dos fuentes el mismo día. La nota manual sobrevive aunque el
    día pase a tener datos reales (permite anotar un día auditado sin pisar
    el monto real)."""
    ingested = await ingested_dates(session, pid, start, end)
    account = await config_service.get_param(session, pid, "deposit_suspense_account_name")
    adelanto = await account_by_date(session, pid, account, start, end)
    manual = await _manual_by_date(session, pid, start, end)

    rows = []
    d = start
    while d <= end:
        if d in ingested:
            deposited, applied, _dep_crc, _app_crc = adelanto.get(d, (0.0, 0.0, 0.0, 0.0))
            source = "audit"
            note = manual[d].note if d in manual else None
        else:
            entry = manual.get(d)
            deposited = float(entry.deposited_usd) if entry else 0.0
            applied = float(entry.applied_usd) if entry else 0.0
            source = "manual" if entry else "none"
            note = entry.note if entry else None
        rows.append({
            "date": d, "deposited_usd": round(deposited, 2), "applied_usd": round(applied, 2),
            "source": source, "note": note,
        })
        d += timedelta(days=1)
    return rows


async def _net_range(session: AsyncSession, pid, start: date_cls, end: date_cls) -> float:
    """Σ(deposited-applied) en [start,end] sin materializar fila por día
    (usado para acumular el saldo antes del rango visible -- puede cubrir
    meses/años, no hace falta iterar día por día en Python para esto)."""
    ingested = await ingested_dates(session, pid, start, end)
    account = await config_service.get_param(session, pid, "deposit_suspense_account_name")
    adelanto = await account_by_date(session, pid, account, start, end)
    manual = await _manual_by_date(session, pid, start, end)
    net = sum(dep - app for dep, app, _dep_crc, _app_crc in adelanto.values())
    net += sum(float(e.deposited_usd) - float(e.applied_usd)
               for d, e in manual.items() if d not in ingested)
    return net


async def _balance_through(session: AsyncSession, pid, through: date_cls) -> float:
    """Saldo pendiente de aplicar HASTA `through` inclusive -- ancla (solo si
    su fecha ya pasó) + movimiento real DESPUÉS del ancla. Un `through`
    ANTERIOR al ancla la ignora correctamente (mismo criterio ya validado en
    room_stats_service.room_stats_ytd)."""
    opening = await _get_opening(session, pid)
    if opening is not None and opening.anchor_date <= through:
        base = float(opening.balance_usd)
        start_after = opening.anchor_date + timedelta(days=1)
        if start_after > through:
            return round(base, 2)
        return round(base + await _net_range(session, pid, start_after, through), 2)
    if EARLIEST_DATE > through:
        return 0.0
    return round(await _net_range(session, pid, EARLIEST_DATE, through), 2)


async def ledger_range(session: AsyncSession, start: date_cls, end: date_cls,
                       property_code: str = "COWLCR") -> dict:
    """Saldo de apertura del rango + una fila por día (real o manual según
    corresponda) con saldo corrido + saldo de cierre."""
    if end < start:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")
    pid = await _property_id(session, property_code)
    opening_balance = await _balance_through(session, pid, start - timedelta(days=1))
    daily = await _daily_rows(session, pid, start, end)

    running = opening_balance
    rows = []
    for r in daily:
        running = round(running + r["deposited_usd"] - r["applied_usd"], 2)
        rows.append({
            "date": r["date"].isoformat(), "deposited_usd": r["deposited_usd"],
            "applied_usd": r["applied_usd"], "balance_usd": running,
            "note": r["note"], "source": r["source"],
        })

    opening = await _get_opening(session, pid)
    return {
        "start": start.isoformat(), "end": end.isoformat(),
        "opening_balance": opening_balance, "closing_balance": running,
        "rows": rows,
        "anchor": None if opening is None else {
            "anchor_date": opening.anchor_date.isoformat(),
            "balance_usd": float(opening.balance_usd), "note": opening.note,
        },
    }


async def set_entry(session: AsyncSession, entry_date: date_cls, deposited_usd: float,
                    applied_usd: float, note: str | None = None,
                    property_code: str = "COWLCR") -> dict:
    """Alta/edición de la entrada manual de un día (upsert -- un registro por
    fecha). Para un día ya ingestado, `deposited_usd`/`applied_usd` quedan
    guardados pero `ledger_range()` los ignora (el real siempre gana) -- solo
    la `note` se usa en ese caso."""
    pid = await _property_id(session, property_code)
    await session.execute(
        pg_insert(DepositLedgerEntry)
        .values(property_id=pid, date=entry_date, deposited_usd=deposited_usd,
                applied_usd=applied_usd, note=note)
        .on_conflict_do_update(
            index_elements=["property_id", "date"],
            set_={"deposited_usd": deposited_usd, "applied_usd": applied_usd, "note": note},
        )
    )
    await session.commit()
    return {"date": entry_date.isoformat(), "deposited_usd": deposited_usd,
            "applied_usd": applied_usd, "note": note}


async def delete_entry(session: AsyncSession, entry_date: date_cls,
                       property_code: str = "COWLCR") -> None:
    pid = await _property_id(session, property_code)
    await session.execute(
        delete(DepositLedgerEntry).where(
            DepositLedgerEntry.property_id == pid, DepositLedgerEntry.date == entry_date,
        )
    )
    await session.commit()


async def get_opening(session: AsyncSession, property_code: str = "COWLCR") -> dict | None:
    pid = await _property_id(session, property_code)
    opening = await _get_opening(session, pid)
    if opening is None:
        return None
    return {"anchor_date": opening.anchor_date.isoformat(),
            "balance_usd": float(opening.balance_usd), "note": opening.note}


async def set_opening(session: AsyncSession, anchor_date: date_cls, balance_usd: float,
                      note: str | None = None, property_code: str = "COWLCR") -> dict:
    """Fija/edita el ancla YTD (un solo ancla por propiedad -- se edita in
    place cuando el owner cargue o corrija el corte de junio)."""
    pid = await _property_id(session, property_code)
    await session.execute(
        pg_insert(DepositLedgerOpening)
        .values(property_id=pid, anchor_date=anchor_date, balance_usd=balance_usd, note=note)
        .on_conflict_do_update(
            index_elements=["property_id"],
            set_={"anchor_date": anchor_date, "balance_usd": balance_usd, "note": note},
        )
    )
    await session.commit()
    return {"anchor_date": anchor_date.isoformat(), "balance_usd": balance_usd, "note": note}
