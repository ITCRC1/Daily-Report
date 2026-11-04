"""Budget (Tab 6.1 Monthly by Department + 6.5 Daily derivado, §2 decisión
cerrada #2): descarga plantilla Excel (prellenada con lo ya cargado) →
Bismark la llena offline → sube de vuelta → reemplazo total del año
("reset anual") → se deriva `fact_budget` día por día (§3, engine/budget.py).

No se adoptó el layout viejo/transpuesto de '12 months Budget 06' (bloqueante
documentado) — esta es una plantilla nueva, propia de la app, mapeada 1:1 al
esquema de budget_monthly. No hace falta el archivo legado para esto.
"""
from __future__ import annotations

import calendar
from datetime import date as date_cls
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.budget import derive_daily_amounts
from app.services import year_grid
from app.models import Budget, BudgetMonthly, Department, Property

#: La plantilla es la reja ancha compartida con el gemelo (Budget/Forecast).
#: `year_grid.LONG_HEADERS` guarda el layout viejo, que se sigue leyendo.
HEADERS = year_grid.WIDE_HEADERS


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _departments(session: AsyncSession, pid) -> list[Department]:
    return (await session.execute(
        select(Department).where(Department.property_id == pid).order_by(Department.cost_center)
    )).scalars().all()


def _n(v) -> float | None:
    return float(v) if v is not None else None


async def build_template(session: AsyncSession, year: int, property_code: str = "COWLCR") -> bytes:
    """Excel prellenado con lo ya cargado para `year` -- un renglon por
    departamento y DOCE COLUMNAS DE MES (owner, 2026-11-04: *«que los meses
    sean columnas»*). El layout largo se sigue leyendo al subir; ver
    `year_grid`."""
    pid = await _property_id(session, property_code)
    depts = await _departments(session, pid)
    existing = (await session.execute(
        select(BudgetMonthly).where(BudgetMonthly.property_id == pid, BudgetMonthly.year == year)
    )).scalars().all()
    by_key = {(str(x.dept_id), x.month): x for x in existing}

    filas = []
    for d in depts:
        montos = []
        for month in range(1, 13):
            x = by_key.get((str(d.id), month))
            montos.append(float(x.amount_usd) if x else 0.0)
        filas.append((d.cost_center, d.outlet_name, montos))

    stats_por_mes: dict[int, dict] = {}
    for x in existing:
        if x.available_rooms is None:
            continue
        stats_por_mes[x.month] = {
            "available_rooms": x.available_rooms, "rooms_occupied": x.rooms_occupied,
            "guests": x.guests, "occupancy_pct": x.occupancy_pct, "adr": x.adr,
        }

    return year_grid.build(f"Budget {year}", filas, stats_por_mes)


async def _replace_year(session: AsyncSession, pid, year: int) -> None:
    await session.execute(delete(BudgetMonthly).where(
        BudgetMonthly.property_id == pid, BudgetMonthly.year == year))
    await session.execute(delete(Budget).where(
        Budget.property_id == pid,
        Budget.date >= date_cls(year, 1, 1), Budget.date <= date_cls(year, 12, 31)))


async def upload_and_replace(session: AsyncSession, year: int, file_bytes: bytes,
                             property_code: str = "COWLCR") -> dict:
    """Sube la plantilla llena: reemplazo total del anio + diario derivado.

    Acepta la reja ANCHA (depto x doce meses, la de hoy) y la LARGA (un renglon
    por depto y mes, la de antes del 2026-11-04). El layout viejo se sigue
    leyendo porque una plantilla bajada la semana pasada tiene que poder
    subirse.
    """
    pid = await _property_id(session, property_code)
    by_code = {d.cost_center: d for d in await _departments(session, pid)}

    wb = load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.active
    ancho = year_grid.es_ancho(ws)
    amounts, stats, orden = year_grid.parse(ws)
    if not amounts:
        raise ValueError(
            "No se encontro la reja en el archivo. Se espera un encabezado "
            "'Dept Code' con las columnas de mes (Jan..Dec), o el layout viejo "
            "con la columna 'Mes'.")
    return await _write_year(session, pid, year, amounts, stats, by_code, orden,
                             "wide" if ancho else "long")


async def _snapshot_fbm(session: AsyncSession, pid, year: int) -> dict:
    """Food/Beverage/Misc de lo ya cargado, por `(dept_id, month)`.

    La reja ancha no tiene columnas para el desglose y la carga es un reemplazo
    TOTAL del anio: sin esta foto, subir la plantilla nueva los pondria en cero
    sin que nada lo avise. Una plantilla que no puede expresar un dato no tiene
    derecho a destruirlo. Ver `year_grid`.
    """
    filas = (await session.execute(select(BudgetMonthly).where(
        BudgetMonthly.property_id == pid, BudgetMonthly.year == year))).scalars().all()
    return {(str(x.dept_id), x.month): (x.food, x.beverage, x.misc) for x in filas}


async def _write_year(session: AsyncSession, pid, year: int, amounts: dict,
                      stats: dict, by_code: dict, orden: list, layout: str) -> dict:
    """Escribe el anio completo: reemplazo total + derivado diario.

    ⚠️ **Unico camino de escritura.** Lo usan la subida de Excel y el guardado
    desde la pantalla. Si cada uno escribiera por su lado, editar en pantalla y
    subir la plantilla con los mismos numeros podrian dar resultados distintos
    -- y el total seguiria cuadrando, que es como estos errores sobreviven.
    """
    faltantes = sorted({c for c in orden if c not in by_code})
    # Un mes con estadisticos pero sin monto en Rooms igual necesita su fila,
    # porque los estadisticos viven ahi.
    if stats and year_grid.DEPT_STATS in by_code:
        if year_grid.DEPT_STATS not in orden:
            orden = [*orden, year_grid.DEPT_STATS]
        for month in stats:
            amounts.setdefault((year_grid.DEPT_STATS, month), Decimal("0"))

    fbm = await _snapshot_fbm(session, pid, year)
    await _replace_year(session, pid, year)

    cero = (Decimal("0"), Decimal("0"), Decimal("0"))
    loaded = 0
    for code in orden:
        dept = by_code.get(code)
        if dept is None:
            continue
        for month in range(1, 13):
            amount = amounts.get((code, month))
            if amount is None:
                continue
            st = stats.get(month, {}) if code == year_grid.DEPT_STATS else {}
            food, bev, misc = fbm.get((str(dept.id), month), cero)
            session.add(BudgetMonthly(
                property_id=pid, year=year, month=month, dept_id=dept.id,
                amount_usd=amount,
                available_rooms=st.get("available_rooms"),
                rooms_occupied=st.get("rooms_occupied"),
                guests=st.get("guests"),
                occupancy_pct=st.get("occupancy_pct"),
                adr=st.get("adr"),
                food=food, beverage=bev, misc=misc,
            ))
            loaded += 1
            if amount:
                for day_idx, amt in enumerate(derive_daily_amounts(amount, year, month), start=1):
                    session.add(Budget(
                        property_id=pid, date=date_cls(year, month, day_idx),
                        dept_id=dept.id, amount_usd=amt,
                    ))

    await session.commit()
    return {"year": year, "layout": layout, "rows_loaded": loaded,
            "lineas_no_reconocidas": [], "dept_codes_no_reconocidos": faltantes}


async def save_monthly(session: AsyncSession, year: int, payload: dict,
                       property_code: str = "COWLCR") -> dict:
    """Guarda lo editado EN PANTALLA (Tab 6.1 / 6.1.1).

    Owner, 2026-11-04: *«dame la opcion de editar directamente en la pantalla y
    con copy pasted para todo y poder guardar»*.

    Mismo reemplazo total del anio que la subida de Excel, y por el mismo
    `_write_year`: editar en pantalla y bajar la plantilla tienen que dar
    exactamente lo mismo.

    `payload`: `{"rows": [{"dept_code": str, "amounts": [12 numeros]}],
                 "stats": {"available_rooms": [12], ...}}`
    """
    pid = await _property_id(session, property_code)
    by_code = {d.cost_center: d for d in await _departments(session, pid)}

    amounts: dict = {}
    orden: list[str] = []
    for fila in payload.get("rows") or []:
        code = str(fila.get("dept_code") or "").strip()
        if not code:
            continue
        if code not in orden:
            orden.append(code)
        for i, v in enumerate((fila.get("amounts") or [])[:12], start=1):
            amounts[(code, i)] = year_grid._num(v) or Decimal("0")

    stats: dict[int, dict] = {}
    for clave, valores in (payload.get("stats") or {}).items():
        if clave not in {c for _, c in year_grid.STATS}:
            continue
        for i, v in enumerate((valores or [])[:12], start=1):
            # Sin adivinar: la pantalla manda la ocupacion ya en FRACCION.
            # `year_grid.pct` existe para el Excel, donde no hay forma de saber
            # si un 1.2 es 1,2% o 120%; aca si la hay, y una ocupacion de 1,2%
            # --setiembre 2026 tuvo 3,9%-- no puede volverse 120%.
            n = year_grid._num(v)
            if n is not None:
                stats.setdefault(i, {})[clave] = n

    return await _write_year(session, pid, year, amounts, stats, by_code, orden, "screen")


async def monthly_summary(session: AsyncSession, year: int, property_code: str = "COWLCR") -> list[dict]:
    pid = await _property_id(session, property_code)
    depts = {d.id: d for d in await _departments(session, pid)}
    rows = (await session.execute(
        select(BudgetMonthly).where(BudgetMonthly.property_id == pid, BudgetMonthly.year == year)
        .order_by(BudgetMonthly.month)
    )).scalars().all()
    return [{
        "dept_code": depts[r.dept_id].cost_center if r.dept_id in depts else None,
        "dept_name": depts[r.dept_id].outlet_name if r.dept_id in depts else None,
        "month": r.month, "amount_usd": float(r.amount_usd),
        "available_rooms": _n(r.available_rooms), "rooms_occupied": _n(r.rooms_occupied),
        "guests": _n(r.guests), "occupancy_pct": _n(r.occupancy_pct), "adr": _n(r.adr),
        "food": float(r.food), "beverage": float(r.beverage), "misc": float(r.misc),
    } for r in rows]


async def daily_summary(session: AsyncSession, year: int, month: int,
                        property_code: str = "COWLCR") -> list[dict]:
    """6.5 — presupuesto diario derivado (fact_budget) de un mes."""
    pid = await _property_id(session, property_code)
    depts = {d.id: d for d in await _departments(session, pid)}
    days_in_month = calendar.monthrange(year, month)[1]
    rows = (await session.execute(
        select(Budget).where(
            Budget.property_id == pid,
            Budget.date >= date_cls(year, month, 1),
            Budget.date <= date_cls(year, month, days_in_month),
        ).order_by(Budget.date)
    )).scalars().all()
    return [{
        "date": r.date.isoformat(),
        "dept_code": depts[r.dept_id].cost_center if r.dept_id in depts else None,
        "dept_name": depts[r.dept_id].outlet_name if r.dept_id in depts else None,
        "amount_usd": float(r.amount_usd),
    } for r in rows]
