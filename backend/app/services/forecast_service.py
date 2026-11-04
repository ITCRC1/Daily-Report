"""Forecast (Tab 6.1.1) — gemelo del Budget (Tab 6.1, budget_service).

Mismo ciclo que el presupuesto: se descarga la plantilla Excel (prellenada con
lo ya cargado), se llena offline, se sube de vuelta y eso **reemplaza el año
completo** — y el diario se deriva solo (`fact_forecast`, mismo reparto que
`fact_budget`: mensual ÷ días del mes, con el residual de redondeo al último día
para que Σ diarios = mensual exacto).

Por qué tabla propia y no una columna `kind` sobre budget_monthly: el reemplazo
anual de uno no puede pisar al otro, y `fact_budget` — que ya consumen revenue,
Tab 9 y el OTB — no cambia de forma.
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
from app.models import Department, Forecast, ForecastMonthly, Property

#: La plantilla es la reja ancha compartida con el gemelo (Budget/Forecast).
#: `year_grid.LONG_HEADERS` guarda el layout viejo, que se sigue leyendo.
HEADERS = year_grid.WIDE_HEADERS

# --- Layout "Working" (Ingresos_12M_Working_YYYY.xlsx) -----------------------
# El archivo con que se trabaja el forecast viene TRANSPUESTO: una fila por
# línea de ingreso y una columna por mes. Sus líneas ya existen como filas de
# dim_department, así que se cargan al mismo grano que el Budget (Tab 6.1) y
# quedan en el mismo orden (ordenado por cost_center).
#
# Las 8 salas de F&B (0123..0130) NO están en el archivo -- el forecast lleva
# F&B agregado en Food/Beverage/Misc. No se escriben filas para ellas: así el
# Tab 6.1.1 muestra sólo el F&B que tiene saldo, sin ocho renglones en cero.
# Dos líneas del archivo van a departamentos cuyo output_column NO tiene fila
# en el cuadro de Tab 3 ("Rooms Others" y "Misc. Rev Others"): si se mapean ahí,
# el GRAND TOTAL suma plata que no aparece en ninguna fila -- exactamente el
# descuadre que este sistema vino a eliminar. Por eso el no-show va dentro de
# Rooms y el "Other / Misc Revenue" a MISC-REV, que sí es la fila visible
# "Misc. Revenue". TODO(bismark): confirmar los dos destinos.
WORKING_LINE_TO_DEPT = {
    "Rooms Revenue-": "0110",
    "Rooms Revenue-No Show": "0110",
    "F&B Food": "FB-FOOD",
    "F&B Beverage": "FB-BEV",
    "F&B Miscellaneous": "FB-MISC",
    "SPA": "0140",
    "Tours": "0150",
    "Gift Shop": "0151",
    "Transportation": "0152",
    "Laundry": "0160",
    "Oinn": "0155",
    "Sustainability Fee": "0170",
    "Other / Misc Revenue": "MISC-REV",
}
_WORKING_HEADER = "Línea de ingreso"
_WORKING_TOTAL = "TOTAL INGRESOS"
# Los estadísticos son por MES (no por línea): se guardan en la fila de Rooms,
# igual que hace la plantilla del Budget.
_WORKING_STATS = {
    "Total available Rooms": "available_rooms",
    "Total Rooms Occupied": "rooms_occupied",
    "Total Guests": "guests",
    "% Occupancy": "occupancy_pct",
    "ADR": "adr",
}


def _is_working_layout(ws) -> bool:
    """Distingue el archivo Working del template propio (Dept Code / Mes)."""
    for row in ws.iter_rows(min_row=1, max_row=30, max_col=1, values_only=True):
        if row[0] and str(row[0]).strip() == _WORKING_HEADER:
            return True
    return False


def _parse_working(ws) -> tuple[dict, dict, list[str]]:
    """Devuelve (montos, estadísticos, líneas_no_reconocidas).

    montos:  {(dept_code, month): Decimal}
    stats:   {month: {campo: Decimal}}
    Una celda vacía NO es cero: se omite (no se inventa dato). Un 0 explícito
    sí se carga -- octubre viene en cero a propósito (operación cerrada).
    """
    header_row = None
    for i, row in enumerate(ws.iter_rows(min_row=1, max_col=1, values_only=True), start=1):
        if row[0] and str(row[0]).strip() == _WORKING_HEADER:
            header_row = i
            break
    if header_row is None:
        raise ValueError(f"No se encontró la fila de encabezado '{_WORKING_HEADER}'.")

    amounts: dict = {}
    stats: dict = {}
    unmapped: list[str] = []

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        label = row[0].value
        if label is None:
            continue
        label = str(label).strip()

        if label in _WORKING_STATS:
            field = _WORKING_STATS[label]
            for month in range(1, 13):
                v = row[month].value
                if v is None or v == "":
                    continue
                stats.setdefault(month, {})[field] = Decimal(str(v))
            continue

        if row[0].row <= header_row or label == _WORKING_TOTAL:
            continue

        dept_code = WORKING_LINE_TO_DEPT.get(label)
        if dept_code is None:
            unmapped.append(label)
            continue
        for month in range(1, 13):
            v = row[month].value
            if v is None or v == "":
                continue
            # ACUMULA: dos líneas del archivo (Rooms Revenue- y su no-show)
            # caen en el mismo departamento; asignar en vez de sumar perdería
            # una de las dos sin avisar.
            key = (dept_code, month)
            amounts[key] = amounts.get(key, Decimal("0")) + Decimal(str(v)).quantize(Decimal("0.01"))

    return amounts, stats, unmapped


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
        select(ForecastMonthly).where(ForecastMonthly.property_id == pid, ForecastMonthly.year == year)
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

    return year_grid.build(f"Forecast {year}", filas, stats_por_mes)


async def _replace_year(session: AsyncSession, pid, year: int) -> None:
    await session.execute(delete(ForecastMonthly).where(
        ForecastMonthly.property_id == pid, ForecastMonthly.year == year))
    await session.execute(delete(Forecast).where(
        Forecast.property_id == pid,
        Forecast.date >= date_cls(year, 1, 1), Forecast.date <= date_cls(year, 12, 31)))


async def _upload_working(session: AsyncSession, pid, year: int, ws, by_code: dict) -> dict:
    """Carga el layout Working (línea de ingreso × mes). Escribe SOLO las líneas
    que trae el archivo: las 8 salas de F&B sin saldo no generan renglón.

    ⚠️ Escribe por `_write_year`, igual que la plantilla y que el guardado desde
    la pantalla. Antes tenía su propio `session.add` y eso ya había empezado a
    divergir: ponía Food/Beverage/Misc en cero mientras los otros caminos los
    preservan. Tres escritores del mismo año terminan diciendo tres cosas, y el
    total cuadra en los tres.
    """
    amounts, stats, unmapped = _parse_working(ws)

    faltantes = sorted({c for c, _ in amounts if c not in by_code})
    if faltantes:
        raise ValueError(
            "Estos códigos de departamento no existen en dim_department: "
            f"{', '.join(faltantes)}. Cargalos en Tab 6.3 antes de subir el forecast.")

    orden = sorted({c for c, _ in amounts})
    salida = await _write_year(session, pid, year, amounts, stats, by_code, orden, "working")
    salida["lineas_no_reconocidas"] = sorted(set(unmapped))
    return salida


async def upload_and_replace(session: AsyncSession, year: int, file_bytes: bytes,
                             property_code: str = "COWLCR") -> dict:
    """Sube la plantilla llena: reemplazo total del anio + diario derivado.

    Acepta la reja ANCHA (depto x doce meses, la de hoy) y la LARGA (un renglon
    por depto y mes, la de antes del 2026-11-04). El layout viejo se sigue
    leyendo porque una plantilla bajada la semana pasada tiene que poder
    subirse. El layout Working (linea de
    ingreso x mes) sigue teniendo su propio camino.
    """
    pid = await _property_id(session, property_code)
    by_code = {d.cost_center: d for d in await _departments(session, pid)}

    wb = load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.active
    if _is_working_layout(ws):
        return await _upload_working(session, pid, year, ws, by_code)

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
    filas = (await session.execute(select(ForecastMonthly).where(
        ForecastMonthly.property_id == pid, ForecastMonthly.year == year))).scalars().all()
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
            session.add(ForecastMonthly(
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
                    session.add(Forecast(
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
        select(ForecastMonthly).where(ForecastMonthly.property_id == pid, ForecastMonthly.year == year)
        .order_by(ForecastMonthly.month)
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
    """Forecast diario derivado (fact_forecast) de un mes."""
    pid = await _property_id(session, property_code)
    depts = {d.id: d for d in await _departments(session, pid)}
    days_in_month = calendar.monthrange(year, month)[1]
    rows = (await session.execute(
        select(Forecast).where(
            Forecast.property_id == pid,
            Forecast.date >= date_cls(year, month, 1),
            Forecast.date <= date_cls(year, month, days_in_month),
        ).order_by(Forecast.date)
    )).scalars().all()
    return [{
        "date": r.date.isoformat(),
        "dept_code": depts[r.dept_id].cost_center if r.dept_id in depts else None,
        "dept_name": depts[r.dept_id].outlet_name if r.dept_id in depts else None,
        "amount_usd": float(r.amount_usd),
    } for r in rows]
