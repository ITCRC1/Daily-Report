"""On The Books (Tab 8) — reporte mensual Budget vs OTB + NET GAP.

Reproduce el reporte '1) ONTB' del Excel maestro (validado al centavo):
- Budget por mes: de budget_monthly (Total Revenue = suma de todos los deptos;
  Rooms Only + stats = línea Rooms 0110).
- OTB por mes: del snapshot más reciente de fact_otb_monthly (agregación del
  history_forecast del año completo).
- Sales on Property = Forecast Rooms Only × 12.6% (fórmula F31 del Excel).
- Diff = OTB − Budget. NET GAP = Diff Total Revenue + Sales on Property (J87).
"""
from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BudgetMonthly, Department, OtbDaily, OtbMonthly, Property
from app.services import config_service

# Sales on Property (gasto en propiedad estimado) = Forecast Rooms Only × 12.6%
# (formula F31 del Excel) y el cost center de Rooms (0110). Ambos son defaults
# historicos; el valor efectivo se lee de app_config via config_service
# (editable en Tab 6.9, keys 'ontb_sales_on_property_pct' / 'ontb_rooms_cost_center').


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


def _adr(rev: float, rooms: float) -> float:
    return round(rev / rooms, 2) if rooms else 0.0


def _occ(occ: float, avail: float) -> float:
    return round(occ / avail, 4) if avail else 0.0


async def _resolve_snapshot(session: AsyncSession, pid, table,
                            as_of: date_cls | None, *, tiene=None):
    """Corte más reciente que CUMPLA `tiene`; None si ninguno la cumple.

    Al meter la condición dentro del `max()`, la base devuelve el corte más
    nuevo que sirve y descarta los que no, en orden y de una sola consulta --
    no hace falta recorrerlos de a uno hacia atrás.
    """
    q = select(func.max(table.snapshot_date)).where(table.property_id == pid)
    if as_of is not None:
        q = q.where(table.snapshot_date <= as_of)
    if tiene is not None:
        q = q.where(tiene)
    return (await session.execute(q)).scalar_one_or_none()


async def corte_vigente(session: AsyncSession, pid, table,
                        as_of: date_cls | None = None, *, coherente=None):
    """El corte a usar, y el más reciente que existe. Devuelve `(usado, ultimo)`.

    ⚠️ Antes esto era `max(snapshot_date)` a secas, y eso dejaba que **un corte
    vacío tapara a uno bueno**. Pasó el 2026-11-09: se subió un
    `history_forecast` exportado con el rango de 2025. La ingesta creó el corte
    2026-11-09 con sus filas -- todas de 2025 -- y como era el más reciente se
    lo llevaron puesto las tres pantallas que leen OTB. Noviembre y diciembre
    de 2026 salieron en **$0,00** en Tab 8, en el heatmap y en la hoja 3, con
    el corte del día 5 ahí al lado, intacto, con $243.808,44.

    No había nada que mirar: ni un error, ni un cero sospechoso, sólo un mes
    flojo. Y el archivo tampoco era basura -- era un history_forecast
    legítimo, del año equivocado.

    Owner, 2026-11-10: *«escoge el día anterior, pero si por alguna razón no
    tiene datos debe ir al otro día, y así sucesivamente, hasta encontrar
    datos coherentes»*. Por eso `coherente` no pregunta si el corte EXISTE
    sino si **sirve**: que traiga el período pedido y con plata adentro. Un
    corte con las noches pero el revenue en cero -- los de antes del
    2026-11-06, cuando esas columnas no existían -- tampoco pasa.

    Si NINGUNO sirve se devuelve el más reciente igual: la pantalla muestra lo
    que hay y el aviso explica por qué está en cero. Quedarse sin corte sería
    cambiar una cifra equivocada por una pantalla en blanco.
    """
    usado = await _resolve_snapshot(session, pid, table, as_of, tiene=coherente)
    ultimo = await _resolve_snapshot(session, pid, table, as_of)
    return (usado or ultimo), ultimo


async def ontb_report(session: AsyncSession, year: int,
                      property_code: str = "COWLCR",
                      as_of: date_cls | None = None,
                      compare_to: date_cls | None = None) -> dict:
    pid = await _property_id(session, property_code)
    rooms_cc = await config_service.get_param(session, pid, "ontb_rooms_cost_center")
    sop_pct = await config_service.get_float(session, pid, "ontb_sales_on_property_pct")

    rooms_dept = (await session.execute(
        select(Department.id).where(
            Department.property_id == pid, Department.cost_center == rooms_cc)
    )).scalar_one_or_none()

    # --- Budget por mes ---
    budget = {m: {"total_revenue": 0.0, "rooms_only": 0.0, "rooms_avail": 0.0,
                  "rooms_occ": 0.0, "guests": 0.0} for m in range(1, 13)}
    budg_rows = (await session.execute(
        select(BudgetMonthly).where(
            BudgetMonthly.property_id == pid, BudgetMonthly.year == year)
    )).scalars().all()
    for r in budg_rows:
        b = budget[r.month]
        b["total_revenue"] += float(r.amount_usd or 0)
        if r.dept_id == rooms_dept:
            b["rooms_only"] = float(r.amount_usd or 0)
            b["rooms_avail"] = float(r.available_rooms or 0)
            b["rooms_occ"] = float(r.rooms_occupied or 0)
            b["guests"] = float(r.guests or 0)

    # --- OTB: corte FINAL (as_of) y corte INICIAL (compare_to) ---
    # Coherente = trae ESTE año y con plata adentro.
    coherente = and_(OtbMonthly.year == year, OtbMonthly.total_revenue > 0)
    latest, mas_reciente = await corte_vigente(session, pid, OtbMonthly, as_of,
                                               coherente=coherente)
    base = (await corte_vigente(session, pid, OtbMonthly, compare_to,
                                coherente=coherente))[0] if compare_to else None

    async def _otb_by_month(snap):
        if snap is None:
            return {}
        rows = (await session.execute(
            select(OtbMonthly).where(
                OtbMonthly.property_id == pid, OtbMonthly.snapshot_date == snap,
                OtbMonthly.year == year)
        )).scalars().all()
        return {r.month: r for r in rows}

    otb = await _otb_by_month(latest)
    base_otb = await _otb_by_month(base)

    months = []
    for m in range(1, 13):
        b = budget[m]
        o = otb.get(m)
        bt, br, ba, bo, bg = (b["total_revenue"], b["rooms_only"], b["rooms_avail"],
                              b["rooms_occ"], b["guests"])
        if o is not None:
            ot, orr, oo, og, oa, ofc = (float(o.total_revenue), float(o.rooms_only_revenue),
                                        float(o.rooms_occ), float(o.guests),
                                        float(o.rooms_avail), float(o.rooms_only_forecast))
        else:
            ot = orr = oo = og = oa = ofc = 0.0

        sop = round(ofc * sop_pct, 2)
        b_adr_t, b_adr_o, b_oc = _adr(bt, bo), _adr(br, bo), _occ(bo, ba)
        o_adr_t, o_adr_o, o_oc = _adr(ot, oo), _adr(orr, oo), _occ(oo, oa)

        # movimiento vs corte INICIAL (compare_to): cuánto se movió el OTB entre cortes
        pb = base_otb.get(m)
        prev_total = float(pb.total_revenue) if pb is not None else None
        prev_occ = _occ(float(pb.rooms_occ), float(pb.rooms_avail)) if pb is not None else None

        months.append({
            "month": m,
            "budget": {"total_revenue": round(bt, 2), "rooms_only": round(br, 2),
                       "rooms_avail": ba, "rooms_occ": bo, "guests": bg,
                       "adr_total": b_adr_t, "adr_only": b_adr_o, "occ": b_oc},
            "otb": {"total_revenue": round(ot, 2), "rooms_only": round(orr, 2),
                    "rooms_avail": oa, "rooms_occ": oo, "guests": og,
                    "adr_total": o_adr_t, "adr_only": o_adr_o, "occ": o_oc},
            "sales_on_property": sop,
            "diff": {"total_revenue": round(ot - bt, 2), "rooms_only": round(orr - br, 2),
                     "rooms_occ": round(oo - bo, 2), "guests": round(og - bg, 2),
                     "adr_total": round(o_adr_t - b_adr_t, 2),
                     "adr_only": round(o_adr_o - b_adr_o, 2),
                     "occ": round(o_oc - b_oc, 4)},
            "net_gap": round((ot - bt) + sop, 2),
            "prev_total_revenue": round(prev_total, 2) if prev_total is not None else None,
            "otb_move": round(ot - prev_total, 2) if prev_total is not None else None,
            "occ_move": round(o_oc - prev_occ, 4) if prev_occ is not None else None,
        })

    otb_total = round(sum(mm["otb"]["total_revenue"] for mm in months), 2)
    prev_total = sum((mm["prev_total_revenue"] or 0) for mm in months) if base else None
    return {
        "year": year,
        "snapshot_date": latest.isoformat() if latest else None,
        # ⚠️ Si el corte que se usó NO es el más reciente, hay que DECIRLO: el
        # más nuevo existe pero no trae este período, y callarlo es volver al
        # defecto que esto arregla -- una pantalla que no miente pero tampoco
        # avisa de que el archivo de ayer no sirvió.
        "snapshot_mas_reciente": mas_reciente.isoformat() if mas_reciente else None,
        "corte_mas_nuevo_sin_datos": bool(
            mas_reciente and latest and mas_reciente > latest),
        "compare_snapshot_date": base.isoformat() if base else None,
        "months": months,
        "net_gap_total": round(sum(mm["net_gap"] for mm in months), 2),
        "budget_total_revenue": round(sum(mm["budget"]["total_revenue"] for mm in months), 2),
        "otb_total_revenue": otb_total,
        "otb_move_total": round(otb_total - prev_total, 2) if prev_total is not None else None,
    }


# --- 8.3 Daily Heatmap: ocupación diaria del OTB + Risk/Action (reglas del Excel) ---

_MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"]


def _risk_flag(occ: float) -> str:
    """Umbrales exactos del Excel (C8): CRITICAL <15%, HIGH <30%, MID <45%, OK ≥45%."""
    if occ < 0.15:
        return "CRITICAL"
    if occ < 0.30:
        return "HIGH"
    if occ < 0.45:
        return "MID"
    return "OK"


def _action(risk: str) -> str:
    """Excel C10 sin 'Boxed' (marcado manual que no existe en la web):
    CRITICAL→PUSH, HIGH→RATE, MID→WATCH, OK→HOLD."""
    return {"CRITICAL": "PUSH", "HIGH": "RATE", "MID": "WATCH"}.get(risk, "HOLD")


async def ontb_heatmap(session: AsyncSession, year: int,
                       property_code: str = "COWLCR",
                       as_of: date_cls | None = None) -> dict:
    pid = await _property_id(session, property_code)
    rooms_cc = await config_service.get_param(session, pid, "ontb_rooms_cost_center")
    ene1, dic31 = date_cls(year, 1, 1), date_cls(year, 12, 31)
    latest, mas_reciente = await corte_vigente(
        session, pid, OtbDaily, as_of,
        coherente=and_(OtbDaily.the_date.between(ene1, dic31), OtbDaily.rooms_sold > 0))

    rows = []
    if latest is not None:
        rows = (await session.execute(
            select(OtbDaily).where(
                OtbDaily.property_id == pid, OtbDaily.snapshot_date == latest)
        )).scalars().all()
    by_date = {r.the_date: r for r in rows if r.the_date.year == year}

    # Ocupación de BUDGET por mes (línea Rooms 0110): rooms_occupied / available_rooms
    rooms_dept = (await session.execute(
        select(Department.id).where(
            Department.property_id == pid, Department.cost_center == rooms_cc)
    )).scalar_one_or_none()
    budget_m = {m: {"occ": 0.0, "noches": 0.0, "pax": 0.0, "adr": 0.0} for m in range(1, 13)}
    for r in (await session.execute(
        select(BudgetMonthly).where(
            BudgetMonthly.property_id == pid, BudgetMonthly.year == year,
            BudgetMonthly.dept_id == rooms_dept)
    )).scalars().all():
        ro = float(r.rooms_occupied or 0)
        budget_m[r.month] = {
            "occ": _occ(ro, float(r.available_rooms or 0)),
            "noches": ro,
            "pax": float(r.guests or 0),
            "adr": _adr(float(r.amount_usd or 0), ro),   # rooms_only budget / noches
        }

    # OTB mensual (mismo snapshot) para Noches / Pax / ADR por mes
    otb_m = {}
    if latest is not None:
        for r in (await session.execute(
            select(OtbMonthly).where(
                OtbMonthly.property_id == pid, OtbMonthly.snapshot_date == latest,
                OtbMonthly.year == year)
        )).scalars().all():
            otb_m[r.month] = r

    import calendar
    months = []
    for mo in range(1, 13):
        ndays = calendar.monthrange(year, mo)[1]
        days = []
        m_sold = m_avail = 0.0
        for day in range(1, ndays + 1):
            r = by_date.get(date_cls(year, mo, day))
            if r is None:
                days.append({"day": day, "occ": None, "sold": None,
                             "avail": None, "risk": None, "action": None})
                continue
            sold = float(r.rooms_sold)
            avail = float(r.rooms_avail)
            occ = round(sold / avail, 4) if avail else 0.0
            risk = _risk_flag(occ)
            days.append({"day": day, "occ": occ, "sold": sold, "avail": avail,
                         "risk": risk, "action": _action(risk)})
            m_sold += sold
            m_avail += avail
        otb_occ = round(m_sold / m_avail, 4) if m_avail else 0.0
        bm = budget_m[mo]
        b_occ = bm["occ"]
        om = otb_m.get(mo)
        noches = float(om.rooms_occ) if om else m_sold        # room nights vendidas (OTB)
        pax = float(om.guests) if om else 0.0                  # huéspedes (OTB)
        adr = _adr(float(om.rooms_only_revenue), noches) if om else 0.0  # ADR (room rev / noches)
        months.append({
            "month": mo, "name": _MONTH_NAMES[mo - 1], "days": days,
            "otb_occ": otb_occ,               # Forecast (OTB) ocupación mensual
            "budget_occ": b_occ,              # Budget ocupación mensual
            "variance": round(otb_occ - b_occ, 4),  # varianza en puntos %
            "noches": noches, "pax": pax, "adr": adr,          # OTB del mes
            "budget_noches": bm["noches"], "budget_pax": bm["pax"], "budget_adr": bm["adr"],
        })

    return {"year": year, "snapshot_date": latest.isoformat() if latest else None,
            "snapshot_mas_reciente": mas_reciente.isoformat() if mas_reciente else None,
            "corte_mas_nuevo_sin_datos": bool(
                mas_reciente and latest and mas_reciente > latest),
            "months": months}


# --- 8.4 Pacing: total OTB por snapshot semanal (tendencia week-over-week) ---

async def ontb_pacing(session: AsyncSession, property_code: str = "COWLCR",
                      limit: int = 8, year: int | None = None) -> dict:
    pid = await _property_id(session, property_code)
    # total OTB revenue por snapshot (suma de los 12 meses del año pedido)
    q = (select(OtbMonthly.snapshot_date,
                func.sum(OtbMonthly.total_revenue).label("total"))
         .where(OtbMonthly.property_id == pid))
    if year is not None:
        q = q.where(OtbMonthly.year == year)
    rows = (await session.execute(
        q.group_by(OtbMonthly.snapshot_date)
        .order_by(OtbMonthly.snapshot_date.desc())
        .limit(limit)
    )).all()
    snaps = [{"snapshot_date": r.snapshot_date.isoformat(), "otb_total_revenue": float(r.total)}
             for r in rows][::-1]  # cronológico ascendente
    # delta week-over-week
    for i, s in enumerate(snaps):
        s["delta"] = round(s["otb_total_revenue"] - snaps[i - 1]["otb_total_revenue"], 2) if i > 0 else None
    return {"snapshots": snaps, "count": len(snaps)}
