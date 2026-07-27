"""Saldos corrientes de los ledgers (auxiliares) con anclaje editable.

Regla: cierre(d) = apertura(d) + movimiento(d); apertura(d) = cierre(d-1).
El movimiento diario de un ledger = suma de su columna en fact_opera_txn ese día.
El saldo se acumula desde el ANCLAJE manual más reciente (ledger_opening); si no hay
anclaje, acumula desde 0. Editar el anclaje = 'empezar bien' (reinicia la acumulación).
"""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Bill,
    BillLine,
    CityLedgerInvoice,
    LedgerBalance,
    LedgerOpening,
    OperaTxn,
    Property,
    TrialBalanceLine,
)

# ledger -> (label, columna en fact_opera_txn)
LEDGERS: dict[str, tuple[str, str]] = {
    "guest": ("Guest Ledger", "guest_ledger"),
    "package": ("Package Ledger", "package_ledger"),
    "ar": ("AR Ledger", "ar_ledger"),
    "deposit": ("Deposit Ledger", "deposit_ledger"),
}


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _sum_movement(session, pid, col: str, start: date_cls | None, end: date_cls) -> float:
    """Suma de la columna de ledger entre [start, end] inclusive (start None = desde el inicio)."""
    conds = [OperaTxn.property_id == pid, OperaTxn.business_date <= end]
    if start is not None:
        conds.append(OperaTxn.business_date >= start)
    val = (await session.execute(
        select(func.coalesce(func.sum(getattr(OperaTxn, col)), 0)).where(and_(*conds))
    )).scalar_one()
    return float(val)


async def balances_for_day(session: AsyncSession, business_date: date_cls,
                           property_code: str = "COWLCR") -> list[dict]:
    """Apertura / movimiento / cierre por ledger para un día.

    Fuente OFICIAL = fact_ledger_balance (totales del Trial Balance del día:
    apertura/débito/crédito/cierre reportados por Opera). Si ese archivo no se
    ingestó ese día, cae al método viejo: ancla manual (ledger_opening) +
    movimiento acumulado de fact_opera_txn. El ancla queda como respaldo, no se
    borra."""
    pid = await _property_id(session, property_code)
    from datetime import timedelta
    prev = business_date - timedelta(days=1)

    # Saldos oficiales del Trial Balance del día (si se ingestó)
    official = {
        b.ledger: b for b in (await session.execute(
            select(LedgerBalance).where(
                LedgerBalance.property_id == pid,
                LedgerBalance.business_date == business_date)
        )).scalars().all()
    }

    out = []
    for key, (label, col) in LEDGERS.items():
        if key in official:
            b = official[key]
            out.append({
                "ledger": key, "label": label,
                "opening": float(b.opening),
                "movement": round(float(b.debit) + float(b.credit), 2),
                "closing": float(b.closing),
                "anchored": False, "anchor_date": None,
                "note": None, "source": "Trial Balance",
            })
            continue

        # anclaje manual más reciente con effective_date <= business_date
        anchor = (await session.execute(
            select(LedgerOpening)
            .where(LedgerOpening.property_id == pid, LedgerOpening.ledger == key,
                   LedgerOpening.effective_date <= business_date)
            .order_by(LedgerOpening.effective_date.desc())
            .limit(1)
        )).scalar_one_or_none()

        if anchor is not None:
            base = float(anchor.amount)
            anchor_date = anchor.effective_date
            # apertura(d) = base + movimientos en [anchor_date, d-1]
            prior = (await _sum_movement(session, pid, col, anchor_date, prev)
                     if prev >= anchor_date else 0.0)
            opening = round(base + prior, 2)
            anchored, note, adate = True, anchor.note, anchor_date.isoformat()
        else:
            # sin anclaje: apertura = movimientos anteriores al día (desde el inicio)
            opening = round(await _sum_movement(session, pid, col, None, prev), 2)
            anchored, note, adate = False, None, None

        movement = round(await _sum_movement(session, pid, col, business_date, business_date), 2)
        out.append({
            "ledger": key, "label": label,
            "opening": opening, "movement": movement,
            "closing": round(opening + movement, 2),
            "anchored": anchored, "anchor_date": adate, "note": note,
            "source": "Manual anchor" if anchored else "Calculated",
        })
    return out


async def _movement_detail(session, pid, bdate, col: str) -> tuple[list[dict], float]:
    """Detalle del MOVIMIENTO del día por TCode (ata al movimiento del ledger).

    Fuente = Trial Balance oficial si existe (COMPLETO: incluye pagos/ajustes de
    todos los TRX_TYPE, no solo revenue) -> el detalle ata exacto al saldo, que
    también sale del Trial Balance. Si no se ingestó, cae a fact_opera_txn.
    `col` (guest_ledger/package_ledger/ar_ledger/deposit_ledger) existe con el
    mismo nombre en ambas tablas."""
    tb = (await session.execute(
        select(TrialBalanceLine).where(
            TrialBalanceLine.property_id == pid, TrialBalanceLine.business_date == bdate)
        .order_by(TrialBalanceLine.tcode)
    )).scalars().all()
    if tb:
        src = [(t.tcode, t.description, t.trx_type, float(getattr(t, col))) for t in tb]
    else:
        ops = (await session.execute(
            select(OperaTxn).where(OperaTxn.property_id == pid, OperaTxn.business_date == bdate)
            .order_by(OperaTxn.tcode)
        )).scalars().all()
        src = [(o.tcode, o.description, o.type, float(getattr(o, col))) for o in ops]

    out = []
    for tcode, desc, typ, amt in src:
        if abs(amt) >= 0.005:
            out.append({"tcode": tcode, "description": desc, "type": typ,
                        "amount": round(amt, 2)})
    total = round(sum(r["amount"] for r in out), 2)
    return out, total


async def ledger_detail(session: AsyncSession, business_date: date_cls, ledger: str,
                        property_code: str = "COWLCR") -> dict:
    """Detalle auxiliar de un ledger:
    - movement_detail: TCodes que movieron el ledger hoy (ata al movimiento) — los 4 ledgers.
    - folios: documentos que respaldan (Guest = fact_bill; AR = City Ledger; etc.).
    """
    if ledger not in LEDGERS:
        raise ValueError(f"Ledger inválido '{ledger}'.")
    pid = await _property_id(session, property_code)
    col = LEDGERS[ledger][1]

    movement_detail, movement_total = await _movement_detail(session, pid, business_date, col)
    base = {"ledger": ledger, "movement_detail": movement_detail,
            "movement_total": movement_total}

    if ledger == "ar":
        # Detalle del AR Ledger = facturas del City Ledger (empresas/agencias).
        # La suma del día ata al MOVIMIENTO del AR (verificado: $18,853.72 el 07-03).
        invoices = (await session.execute(
            select(CityLedgerInvoice).where(
                CityLedgerInvoice.property_id == pid,
                CityLedgerInvoice.business_date == business_date)
            .order_by(CityLedgerInvoice.invoice_no)
        )).scalars().all()
        folios = [{
            "invoice_no": inv.invoice_no, "bill_no": inv.bill_no,
            "account_name": inv.account_name, "account_number": inv.account_number,
            "amount": float(inv.amount), "guest_name": inv.guest_name,
            "arrival_date": inv.arrival_date, "departure_date": inv.departure_date,
            "confirmation_no": inv.confirmation_no,
        } for inv in invoices]
        folio_total = round(sum(f["amount"] for f in folios), 2)
        ties = abs(folio_total - movement_total) < 0.01
        return {
            **base, "folios": folios, "folio_total": folio_total,
            "ties_to_movement": ties,
            "note": ("Facturas del City Ledger (empresas/agencias). El total debe "
                     "atar al movimiento del AR Ledger del día."
                     + ("" if ties or not folios else
                        f" ⚠ No ata: facturas {folio_total} vs movimiento {movement_total}.")),
        }

    if ledger != "guest":
        return {**base, "folios": [], "folio_total": 0.0,
                "note": "Detalle del movimiento por TCode (ata al movimiento del día). "
                        "El detalle de documentos/saldo de este ledger no viene en el export "
                        "del día (Deposit/Package requieren su reporte de Opera)."}

    bills = (await session.execute(
        select(Bill).where(Bill.property_id == pid, Bill.business_date == business_date)
        .order_by(Bill.bill_no)
    )).scalars().all()
    lines = (await session.execute(
        select(BillLine).where(BillLine.property_id == pid, BillLine.business_date == business_date)
    )).scalars().all()
    by_bill: dict[str, list] = {}
    for ln in lines:
        by_bill.setdefault(ln.bill_no, []).append({
            "trx_code": ln.trx_code, "trx_date": ln.trx_date,
            "net_amount": float(ln.net_amount),
            "debit_amount": float(ln.debit_amount),
            "credit_amount": float(ln.credit_amount),
        })
    folios = [{
        "bill_no": b.bill_no, "guest_name": b.guest_name,
        "guest_internal_id": b.guest_internal_id, "status": b.status,
        "total_amount": float(b.total_amount), "lines": by_bill.get(b.bill_no, []),
    } for b in bills]
    folio_total = round(sum(f["total_amount"] for f in folios), 2)
    return {
        **base, "folios": folios, "folio_total": folio_total,
        "note": "Movimiento por TCode (ata al movimiento del día). Folios = cuentas "
                "liquidadas del día (Opera BILLS); su total atan a los pagos, no al movimiento "
                "bruto del Guest Ledger (que incluye cargos a huéspedes in-house).",
    }


async def set_opening(session: AsyncSession, business_date: date_cls, ledger: str,
                      amount: float, note: str | None = None,
                      property_code: str = "COWLCR") -> dict:
    """Fija/edita el saldo de apertura de un ledger en una fecha (re-ancla)."""
    if ledger not in LEDGERS:
        raise ValueError(f"Ledger inválido '{ledger}'. Válidos: {list(LEDGERS)}")
    pid = await _property_id(session, property_code)
    await session.execute(
        pg_insert(LedgerOpening)
        .values(property_id=pid, ledger=ledger, effective_date=business_date,
                amount=amount, note=note)
        .on_conflict_do_update(
            index_elements=["property_id", "ledger", "effective_date"],
            set_={"amount": amount, "note": note},
        )
    )
    await session.commit()
    return {"ledger": ledger, "effective_date": business_date.isoformat(),
            "amount": amount, "note": note}
