"""Master Data (Tab 6): CRUD sobre catálogos editables por propiedad.

Alcance de esta pasada: 6.2 Cash Mapping (dim_payment_map) y 6.3 Integrity
Mapping (dim_department). Los sub-tabs 6.1/6.4/6.5/6.6 dependen del layout de
budget_monthly, que sigue BLOQUEADO (TODO bismark) — no se construyen acá.
"""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.week_calendar import build_label, generate_weeks
from app.models import Department, MarketCode, PaymentMap, Property, RoomCategory, WeekCalendar

# Rango que regenera el botón "Recalcular" de Tab 6.10 (mismo que siembra seed.py).
WEEK_CAL_START = date_cls(2025, 1, 1)
WEEK_CAL_END = date_cls(2027, 12, 31)


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


PAYMENT_MAP_FIELDS = [
    "transaction_code", "code", "description", "banco_codigo", "banco_nombre",
    "moneda", "tipo_pago", "marca_metodo", "grupo", "cash_flow", "canal", "report_bucket",
]


def _payment_map_row(r: PaymentMap) -> dict:
    return {"id": str(r.id), **{f: getattr(r, f) for f in PAYMENT_MAP_FIELDS}}


async def list_payment_map(session: AsyncSession, property_code: str = "COWLCR") -> list[dict]:
    pid = await _property_id(session, property_code)
    rows = (await session.execute(
        select(PaymentMap).where(PaymentMap.property_id == pid)
        .order_by(PaymentMap.transaction_code)
    )).scalars().all()
    return [_payment_map_row(r) for r in rows]


async def create_payment_map(session: AsyncSession, data: dict, property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    row = PaymentMap(property_id=pid, **{f: data.get(f) for f in PAYMENT_MAP_FIELDS})
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Ya existe un mapeo para el TCode '{data.get('transaction_code')}'.")
    return _payment_map_row(row)


async def update_payment_map(session: AsyncSession, row_id: str, data: dict,
                             property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(PaymentMap).where(PaymentMap.id == row_id, PaymentMap.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe el mapeo '{row_id}'.")
    for f in PAYMENT_MAP_FIELDS:
        if f in data:
            setattr(row, f, data[f])
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Ya existe un mapeo para el TCode '{data.get('transaction_code')}'.")
    return _payment_map_row(row)


async def delete_payment_map(session: AsyncSession, row_id: str, property_code: str = "COWLCR") -> None:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(PaymentMap).where(PaymentMap.id == row_id, PaymentMap.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe el mapeo '{row_id}'.")
    await session.delete(row)
    await session.commit()


DEPARTMENT_FIELDS = ["cuenta_nature", "cost_center", "outlet_name", "output_column"]


def _department_row(r: Department) -> dict:
    return {"id": str(r.id), **{f: getattr(r, f) for f in DEPARTMENT_FIELDS}}


async def list_departments(session: AsyncSession, property_code: str = "COWLCR") -> list[dict]:
    pid = await _property_id(session, property_code)
    rows = (await session.execute(
        select(Department).where(Department.property_id == pid)
        .order_by(Department.cost_center)
    )).scalars().all()
    return [_department_row(r) for r in rows]


async def create_department(session: AsyncSession, data: dict, property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    if not (data.get("output_column") or "").strip():
        raise ValueError("output_column es obligatorio.")
    row = Department(property_id=pid, **{f: data.get(f) for f in DEPARTMENT_FIELDS})
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError("Ya existe un departamento con esa naturaleza + centro de costo.")
    return _department_row(row)


async def update_department(session: AsyncSession, row_id: str, data: dict,
                            property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(Department).where(Department.id == row_id, Department.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe el departamento '{row_id}'.")
    for f in DEPARTMENT_FIELDS:
        if f in data:
            setattr(row, f, data[f])
    if not (row.output_column or "").strip():
        raise ValueError("output_column es obligatorio.")
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError("Ya existe un departamento con esa naturaleza + centro de costo.")
    return _department_row(row)


async def delete_department(session: AsyncSession, row_id: str, property_code: str = "COWLCR") -> None:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(Department).where(Department.id == row_id, Department.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe el departamento '{row_id}'.")
    await session.delete(row)
    await session.commit()


# --- 6.7 Rooms Mapping (dim_room_category) --------------------------------
# code2 (Opera, "01".."06") + room_class (XML STATISTICS, FVR/OVR…) +
# integrity_string (referencial, no se usa para parsear revenue -- §10) +
# units (habitaciones físicas por categoría).
ROOM_CATEGORY_FIELDS = ["code2", "report_name", "opera_short_desc", "room_class", "integrity_string", "units"]


def _room_category_row(r: RoomCategory) -> dict:
    return {"id": str(r.id), **{f: getattr(r, f) for f in ROOM_CATEGORY_FIELDS}}


async def list_room_categories(session: AsyncSession, property_code: str = "COWLCR") -> list[dict]:
    pid = await _property_id(session, property_code)
    rows = (await session.execute(
        select(RoomCategory).where(RoomCategory.property_id == pid).order_by(RoomCategory.code2)
    )).scalars().all()
    return [_room_category_row(r) for r in rows]


async def create_room_category(session: AsyncSession, data: dict, property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    if not (data.get("code2") or "").strip():
        raise ValueError("code2 es obligatorio.")
    row = RoomCategory(property_id=pid, **{f: data.get(f) for f in ROOM_CATEGORY_FIELDS})
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Ya existe una categoría con code2 '{data.get('code2')}'.")
    return _room_category_row(row)


async def update_room_category(session: AsyncSession, row_id: str, data: dict,
                               property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(RoomCategory).where(RoomCategory.id == row_id, RoomCategory.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe la categoría '{row_id}'.")
    for f in ROOM_CATEGORY_FIELDS:
        if f in data:
            setattr(row, f, data[f])
    if not (row.code2 or "").strip():
        raise ValueError("code2 es obligatorio.")
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Ya existe una categoría con code2 '{data.get('code2')}'.")
    return _room_category_row(row)


async def delete_room_category(session: AsyncSession, row_id: str, property_code: str = "COWLCR") -> None:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(RoomCategory).where(RoomCategory.id == row_id, RoomCategory.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe la categoría '{row_id}'.")
    await session.delete(row)
    await session.commit()


# --- 6.8 Market Codes Mapping (dim_market_code) ----------------------------
# code (Opera market_code, ej. "TAFIT") + name (nombre real) + kpi_group
# (canal de negocio, §3.2 -- Travel Agent/Direct Client/Website/OTA/INHOUSE,
# o cualquier otro texto libre; un código sin kpi_group cae en "Unmapped"
# en el rollup de Tab 3.2, nunca se pierde en silencio, §10).
MARKET_CODE_FIELDS = ["code", "name", "kpi_group"]


def _market_code_row(r: MarketCode) -> dict:
    return {"id": str(r.id), **{f: getattr(r, f) for f in MARKET_CODE_FIELDS}}


async def list_market_codes(session: AsyncSession, property_code: str = "COWLCR") -> list[dict]:
    pid = await _property_id(session, property_code)
    rows = (await session.execute(
        select(MarketCode).where(MarketCode.property_id == pid).order_by(MarketCode.code)
    )).scalars().all()
    return [_market_code_row(r) for r in rows]


async def create_market_code(session: AsyncSession, data: dict, property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    if not (data.get("code") or "").strip():
        raise ValueError("code es obligatorio.")
    row = MarketCode(property_id=pid, **{f: data.get(f) for f in MARKET_CODE_FIELDS})
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Ya existe un market code '{data.get('code')}'.")
    return _market_code_row(row)


async def update_market_code(session: AsyncSession, row_id: str, data: dict,
                             property_code: str = "COWLCR") -> dict:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(MarketCode).where(MarketCode.id == row_id, MarketCode.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe el market code '{row_id}'.")
    for f in MARKET_CODE_FIELDS:
        if f in data:
            setattr(row, f, data[f])
    if not (row.code or "").strip():
        raise ValueError("code es obligatorio.")
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Ya existe un market code '{data.get('code')}'.")
    return _market_code_row(row)


async def delete_market_code(session: AsyncSession, row_id: str, property_code: str = "COWLCR") -> None:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(MarketCode).where(MarketCode.id == row_id, MarketCode.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe el market code '{row_id}'.")
    await session.delete(row)
    await session.commit()


# --- 6.10 Weekly Calendar (dim_week_calendar) ------------------------------
# Cortes semanales EDITABLES (fecha inicio/fin); el label se re-deriva solo.
# Fuente de los rangos de Tab 4 (Weekly Revenue). Tabla APARTE de dim_calendar.
def _week_calendar_row(r: WeekCalendar) -> dict:
    # week_num sale como STRING: el frontend (EditableTable / paneles) trata las
    # celdas como texto; un int crudo rompería un eventual .trim().
    return {
        "id": str(r.id), "week_num": str(r.week_num),
        "week_start": r.week_start.isoformat(), "week_end": r.week_end.isoformat(),
        "week_label": r.week_label,
    }


async def list_weeks(session: AsyncSession, property_code: str = "COWLCR") -> list[dict]:
    pid = await _property_id(session, property_code)
    rows = (await session.execute(
        select(WeekCalendar).where(WeekCalendar.property_id == pid).order_by(WeekCalendar.week_start)
    )).scalars().all()
    return [_week_calendar_row(r) for r in rows]


def _parse_date(raw, current: date_cls) -> date_cls:
    if raw in (None, ""):
        return current
    try:
        return date_cls.fromisoformat(str(raw).strip())
    except ValueError:
        raise ValueError(f"Fecha inválida: '{raw}' (formato esperado AAAA-MM-DD).")


async def update_week(session: AsyncSession, row_id: str, data: dict, property_code: str = "COWLCR") -> dict:
    """Edita el rango (inicio/fin) de una semana. `week_num` es la identidad
    (no cambia); `week_label` se re-deriva automáticamente de num+fechas."""
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(WeekCalendar).where(WeekCalendar.id == row_id, WeekCalendar.property_id == pid)
    )).scalar_one_or_none()
    if row is None:
        raise ValueError(f"No existe la semana '{row_id}'.")

    week_start = _parse_date(data.get("week_start"), row.week_start)
    week_end = _parse_date(data.get("week_end"), row.week_end)
    if week_end < week_start:
        raise ValueError("La fecha de fin no puede ser anterior a la de inicio.")

    row.week_start = week_start
    row.week_end = week_end
    row.week_label = build_label(row.week_num, week_start, week_end)  # auto
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ValueError(f"Ya existe una semana que arranca el '{week_start.isoformat()}'.")
    return _week_calendar_row(row)


async def recalculate_weeks(session: AsyncSession, property_code: str = "COWLCR") -> dict:
    """Reset total: borra las semanas de la propiedad y las regenera desde el
    corte estándar Vie-Jue. Descarta cualquier ajuste manual (acción esperada
    de un botón 'Recalcular')."""
    pid = await _property_id(session, property_code)
    await session.execute(delete(WeekCalendar).where(WeekCalendar.property_id == pid))
    weeks = generate_weeks(WEEK_CAL_START, WEEK_CAL_END)
    session.add_all([
        WeekCalendar(property_id=pid, week_num=w["week_num"], week_start=w["week_start"],
                     week_end=w["week_end"], week_label=w["week_label"])
        for w in weeks
    ])
    await session.commit()
    return {"count": len(weeks)}
