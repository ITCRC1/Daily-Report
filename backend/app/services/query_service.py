"""Tab 7.4 -- Power Query: open column-picker report builder, in the spirit of
Opera Cloud's Reporting & Analytics tool, but over our own already-ingested
data (never a live connection to Opera Cloud).

Deliberately NOT a free-text/raw-SQL builder (§security, no query injection
surface) -- each dataset is a fixed allowlist of columns backed by a plain
Python function that already knows how to join/format that table. The client
picks a dataset + which of its columns to show + an optional date range;
the server does the projection.
"""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Budget,
    BudgetMonthly,
    Department,
    IntegrityLine,
    OperaTxn,
    PosCheck,
    PosSummary,
    Property,
)
from app.services import revenue_service, room_stats_service


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Property '{code}' does not exist.")
    return pid


async def _dept_lookup(session: AsyncSession, pid) -> dict:
    depts = (await session.execute(
        select(Department).where(Department.property_id == pid)
    )).scalars().all()
    return {d.id: d for d in depts}


def _n(v) -> float | None:
    return float(v) if v is not None else None


async def _revenue_actual(session, pid, date_from, date_to) -> list[dict]:
    # Combina, día por día, la ingesta real Opera/Integrity (Tabs 1-2, fuente
    # primaria) con el respaldo de la grilla masiva de 6.4 -- mismo criterio
    # que ya usan Tab 3/4 (nunca se suman ambas fuentes el mismo día, §10).
    # Sin esto, un día recién ingestado en Tab 1 aparecía vacío acá.
    return await revenue_service.merged_revenue_actual(session, pid, date_from, date_to)


async def _budget_daily(session, pid, date_from, date_to) -> list[dict]:
    depts = await _dept_lookup(session, pid)
    q = select(Budget).where(Budget.property_id == pid)
    if date_from:
        q = q.where(Budget.date >= date_from)
    if date_to:
        q = q.where(Budget.date <= date_to)
    rows = (await session.execute(q.order_by(Budget.date))).scalars().all()
    return [{
        "date": r.date.isoformat(),
        "dept_code": depts[r.dept_id].cost_center if r.dept_id in depts else None,
        "dept_name": depts[r.dept_id].outlet_name if r.dept_id in depts else None,
        "amount_usd": float(r.amount_usd),
    } for r in rows]


async def _budget_monthly(session, pid, date_from, date_to) -> list[dict]:
    depts = await _dept_lookup(session, pid)
    q = select(BudgetMonthly).where(BudgetMonthly.property_id == pid)
    if date_from:
        q = q.where(BudgetMonthly.year >= date_from.year)
    if date_to:
        q = q.where(BudgetMonthly.year <= date_to.year)
    rows = (await session.execute(
        q.order_by(BudgetMonthly.year, BudgetMonthly.month)
    )).scalars().all()
    return [{
        "year": r.year, "month": r.month,
        "dept_code": depts[r.dept_id].cost_center if r.dept_id in depts else None,
        "dept_name": depts[r.dept_id].outlet_name if r.dept_id in depts else None,
        "amount_usd": float(r.amount_usd),
        "available_rooms": _n(r.available_rooms), "rooms_occupied": _n(r.rooms_occupied),
        "guests": _n(r.guests), "occupancy_pct": _n(r.occupancy_pct), "adr": _n(r.adr),
        "food": float(r.food), "beverage": float(r.beverage), "misc": float(r.misc),
    } for r in rows]


async def _room_stats(session, pid, date_from, date_to) -> list[dict]:
    # Reusa el mismo motor que Tab 7.3 (room_stats_service.daily_view_for_pid)
    # -- el ancla YTD de cada categoría (Tab 6.6) cuenta como un único
    # registro "histórico" fechado en su anchor_date, en vez de dejar vacío
    # todo el rango sin XML statroomtype ingestado.
    return await room_stats_service.daily_view_for_pid(session, pid, date_from, date_to)


async def _opera_txn(session, pid, date_from, date_to) -> list[dict]:
    q = select(OperaTxn).where(OperaTxn.property_id == pid)
    if date_from:
        q = q.where(OperaTxn.business_date >= date_from)
    if date_to:
        q = q.where(OperaTxn.business_date <= date_to)
    rows = (await session.execute(q.order_by(OperaTxn.business_date, OperaTxn.tcode))).scalars().all()
    return [{
        "date": r.business_date.isoformat(), "tcode": r.tcode, "description": r.description,
        "type": r.type, "total": float(r.total), "guest_ledger": float(r.guest_ledger),
        "package_ledger": float(r.package_ledger), "ar_ledger": float(r.ar_ledger),
        "deposit_ledger": float(r.deposit_ledger),
    } for r in rows]


async def _integrity_lines(session, pid, date_from, date_to) -> list[dict]:
    q = select(IntegrityLine).where(IntegrityLine.property_id == pid)
    if date_from:
        q = q.where(IntegrityLine.business_date >= date_from)
    if date_to:
        q = q.where(IntegrityLine.business_date <= date_to)
    rows = (await session.execute(q.order_by(IntegrityLine.business_date, IntegrityLine.tcode))).scalars().all()
    return [{
        "date": r.business_date.isoformat(), "tcode": r.tcode, "cuenta": r.cuenta,
        "nombre_cuenta": r.nombre_cuenta, "centro_costo": r.centro_costo,
        "referencia": r.referencia, "detalle": r.detalle,
        "deb_usd": float(r.deb_usd), "cred_usd": float(r.cred_usd),
        "source_file": r.source_file,
    } for r in rows]


async def _pos_checks(session, pid, date_from, date_to) -> list[dict]:
    q = select(PosCheck).where(PosCheck.property_id == pid)
    if date_from:
        q = q.where(PosCheck.business_date >= date_from)
    if date_to:
        q = q.where(PosCheck.business_date <= date_to)
    rows = (await session.execute(q.order_by(PosCheck.business_date))).scalars().all()
    return [{
        "date": r.business_date.isoformat(), "restaurant": r.restaurant, "employee": r.employee,
        "check_num": r.check_num, "hora": r.hora, "forma_pago": r.forma_pago,
        "monto": float(r.monto), "is_room_charge": r.is_room_charge,
    } for r in rows]


async def _pos_summary(session, pid, date_from, date_to) -> list[dict]:
    q = select(PosSummary).where(PosSummary.property_id == pid)
    if date_from:
        q = q.where(PosSummary.business_date >= date_from)
    if date_to:
        q = q.where(PosSummary.business_date <= date_to)
    rows = (await session.execute(q.order_by(PosSummary.business_date))).scalars().all()
    return [{
        "date": r.business_date.isoformat(), "ventas_netas": float(r.ventas_netas),
        "cargos_servicio": float(r.cargos_servicio), "total_ventas": float(r.total_ventas),
        "voids": float(r.voids), "room_charge_confirmado": float(r.room_charge_confirmado),
        "source_file": r.source_file,
    } for r in rows]


# key -> (label, loader, columns [(key, label, type), ...])
# type is display-only metadata for the frontend (currency/count/percent/bool/
# date/text) -- it never affects the query itself, only how a cell/total is
# formatted (§ "que todo tenga moneda").
DATASETS: dict[str, dict] = {
    "revenue_actual": {
        "label": "Revenue Actual Daily (Tab 6.4/7.1)", "loader": _revenue_actual,
        "columns": [
            ("date", "Date", "date"), ("dept_code", "Dept Code", "text"), ("dept_name", "Dept Name", "text"),
            ("amount_usd", "Amount (USD)", "currency"), ("rooms_sold", "Rooms Sold", "count"),
            ("total_pax", "Total Pax", "count"), ("available_rooms", "Available Rooms", "count"),
        ],
    },
    "budget_daily": {
        "label": "Daily Budget, derived (Tab 6.5/7.2)", "loader": _budget_daily,
        "columns": [
            ("date", "Date", "date"), ("dept_code", "Dept Code", "text"), ("dept_name", "Dept Name", "text"),
            ("amount_usd", "Amount (USD)", "currency"),
        ],
    },
    "budget_monthly": {
        "label": "Monthly Budget (Tab 6.1)", "loader": _budget_monthly,
        "columns": [
            ("year", "Year", "text"), ("month", "Month", "text"),
            ("dept_code", "Dept Code", "text"), ("dept_name", "Dept Name", "text"),
            ("amount_usd", "Amount (USD)", "currency"), ("available_rooms", "Available Rooms", "count"),
            ("rooms_occupied", "Rooms Occupied", "count"), ("guests", "Guests", "count"),
            ("occupancy_pct", "Occupancy %", "percent"), ("adr", "ADR", "currency"),
            ("food", "Food", "currency"), ("beverage", "Beverage", "currency"), ("misc", "Misc", "currency"),
        ],
    },
    "room_stats": {
        "label": "Room Stats Daily (Tab 6.6/7.3)", "loader": _room_stats,
        "columns": [
            ("date", "Date", "date"), ("category", "Category", "text"), ("revenue", "Revenue", "currency"),
            ("stay_rooms", "RN", "count"), ("stay_persons", "Pax", "count"), ("physical_rooms", "Available", "count"),
        ],
    },
    "opera_txn": {
        "label": "Opera Transactions (raw, fact_opera_txn)", "loader": _opera_txn,
        "columns": [
            ("date", "Date", "date"), ("tcode", "TCode", "text"), ("description", "Description", "text"),
            ("type", "Type", "text"), ("total", "Total", "currency"), ("guest_ledger", "Guest Ledger", "currency"),
            ("package_ledger", "Package Ledger", "currency"), ("ar_ledger", "AR Ledger", "currency"),
            ("deposit_ledger", "Deposit Ledger", "currency"),
        ],
    },
    "integrity_lines": {
        "label": "Integrity Lines (raw, stg_integrity_line)", "loader": _integrity_lines,
        "columns": [
            ("date", "Date", "date"), ("tcode", "TCode", "text"), ("cuenta", "Account", "text"),
            ("nombre_cuenta", "Account Name", "text"), ("centro_costo", "Cost Center", "text"),
            ("referencia", "Reference", "text"), ("detalle", "Detail", "text"),
            ("deb_usd", "Debit (USD)", "currency"), ("cred_usd", "Credit (USD)", "currency"),
            ("source_file", "Source File", "text"),
        ],
    },
    "pos_checks": {
        "label": "Simphony POS Checks (raw, fact_pos_check)", "loader": _pos_checks,
        "columns": [
            ("date", "Date", "date"), ("restaurant", "Restaurant", "text"), ("employee", "Employee", "text"),
            ("check_num", "Check #", "text"), ("hora", "Time", "text"), ("forma_pago", "Payment Method", "text"),
            ("monto", "Amount", "currency"), ("is_room_charge", "Is Room Charge", "bool"),
        ],
    },
    "pos_summary": {
        "label": "Simphony POS Summary (raw, fact_pos_summary)", "loader": _pos_summary,
        "columns": [
            ("date", "Date", "date"), ("ventas_netas", "Net Sales", "currency"),
            ("cargos_servicio", "Service Charges", "currency"), ("total_ventas", "Total Sales", "currency"),
            ("voids", "Voids", "currency"), ("room_charge_confirmado", "Room Charges Confirmed", "currency"),
            ("source_file", "Source File", "text"),
        ],
    },
}


def list_datasets() -> list[dict]:
    """Catalog for the 7.4 frontend -- dataset keys/labels + their available columns."""
    return [
        {"key": key, "label": ds["label"],
         "columns": [{"key": ck, "label": cl, "type": ct} for ck, cl, ct in ds["columns"]]}
        for key, ds in DATASETS.items()
    ]


async def run_query(session: AsyncSession, dataset: str, columns: list[str],
                    date_from: date_cls | None, date_to: date_cls | None,
                    property_code: str = "COWLCR") -> list[dict]:
    ds = DATASETS.get(dataset)
    if ds is None:
        raise ValueError(f"Unknown dataset '{dataset}'.")
    valid_keys = {ck for ck, _, _ in ds["columns"]}
    chosen = [c for c in columns if c in valid_keys] or [ck for ck, _, _ in ds["columns"]]
    pid = await _property_id(session, property_code)
    rows = await ds["loader"](session, pid, date_from, date_to)
    return [{c: r.get(c) for c in chosen} for r in rows]
