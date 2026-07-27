"""Servicio de Cash (etapa 3, Tab 5 — Daily Cash from Operation).

Universo de pagos = headers de Opera con type='PAYMENT' (mismo criterio que la
auditoría §5.4). Cada tcode de pago se resuelve contra dim_payment_map; si no
hay entrada, es UNMAPPED (§5.5, excepción visible, nunca se descarta). El
monto real sale de stg_integrity_line (deb − cred, §5.3), no de Opera (que
usa el signo opuesto para el guest ledger).

No hay reporte de depósitos aplicados ni balance bancario corriendo — no hay
(ni va a haber) un insumo de banco/depósitos que permita calcularlos (decisión
2026-07-03, Bismark). "Real Cash" del día es el número definitivo, no un proxy
de algo pendiente.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date as date_cls
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.cash import cash_pivot, currency_basis_pivot, payment_lines_from_integrity
from app.models import Calendar, IntegrityLine, OperaTxn, PaymentMap, Property


async def _property_id(session: AsyncSession, code: str):
    pid = (await session.execute(
        select(Property.id).where(Property.code == code)
    )).scalar_one_or_none()
    if pid is None:
        raise ValueError(f"Propiedad '{code}' no existe.")
    return pid


async def _payment_map(session: AsyncSession, pid) -> dict[str, dict]:
    rows = (await session.execute(
        select(PaymentMap).where(PaymentMap.property_id == pid)
    )).scalars().all()
    return {r.transaction_code: {
        "banco_codigo": r.banco_codigo, "tipo_pago": r.tipo_pago,
        "marca_metodo": r.marca_metodo, "canal": r.canal,
        "cash_flow": r.cash_flow, "report_bucket": r.report_bucket,
        "description": r.description, "moneda": r.moneda,
    } for r in rows}


async def _payment_lines_for_day(session: AsyncSession, pid, bdate) -> tuple[list[dict], list]:
    """Líneas de pago (Integrity, lado banco) + universo de tcodes de pago
    (Opera type=PAYMENT) de un día -- compartido por todos los pivotes de
    Tab 5 (bucket y currency-basis) para no duplicar la regla de partida
    doble en dos lugares."""
    opera_payments = (await session.execute(
        select(OperaTxn).where(
            OperaTxn.property_id == pid, OperaTxn.business_date == bdate,
            OperaTxn.type == "PAYMENT",
        )
    )).scalars().all()
    payment_tcodes = {o.tcode for o in opera_payments}

    integ = []
    if payment_tcodes:
        # Un TCode de pago normalmente trae UNA sola línea de Integrity (el
        # lado banco/caja, cuenta clase "1xxx" -- Activos). Pero un pago que
        # pasa por una cuenta puente (ej. ADELANTO/anticipo, clase "2xxx" --
        # Pasivos) trae AMBAS patas de la partida doble bajo el MISMO tcode
        # (débito al banco + crédito al puente) -- sumar deb-cred de las 2
        # líneas da CERO (se cancelan), perdiendo el monto real de caja.
        # Filtrar a la pata "1xxx" (mismo criterio de naturaleza por prefijo
        # de cuenta que ya usa engine/revenue.py para Clase 4=Revenue) aísla
        # el lado banco, sea que el tcode tenga 1 o 2 líneas.
        integ = (await session.execute(
            select(IntegrityLine).where(
                IntegrityLine.property_id == pid, IntegrityLine.business_date == bdate,
                IntegrityLine.tcode.in_(payment_tcodes),
                IntegrityLine.cuenta.startswith("1"),
            )
        )).scalars().all()
    lines = payment_lines_from_integrity([{
        "tcode": ln.tcode, "deb_usd": ln.deb_usd, "cred_usd": ln.cred_usd,
        "deb_col": ln.deb_col, "cred_col": ln.cred_col,
    } for ln in integ])
    return lines, opera_payments


async def _cash_for_day(session: AsyncSession, pid, bdate, payment_map: dict) -> dict:
    """Pivote de un día: opera (universo de tcodes PAYMENT) + integrity (montos)."""
    lines, opera_payments = await _payment_lines_for_day(session, pid, bdate)

    unmapped = [{
        "tcode": o.tcode, "description": o.description, "opera_total": float(o.total),
    } for o in opera_payments if o.tcode not in payment_map]

    pivot = cash_pivot(lines, payment_map)
    return {"pivot": pivot, "unmapped": unmapped}


def _merge_pivots(pivots: list[dict]) -> dict:
    total = real_cash = non_cash = cash_relevant = bank_only = 0.0
    by_bucket: dict[str, float] = defaultdict(float)
    by_bank: dict[str, float] = defaultdict(float)
    by_brand: dict[str, float] = defaultdict(float)
    by_channel: dict[str, float] = defaultdict(float)
    split_bucket: dict[str, dict] = defaultdict(lambda: {"real": 0.0, "non": 0.0})
    split_bank: dict[str, dict] = defaultdict(lambda: {"real": 0.0, "non": 0.0})
    split_brand: dict[str, dict] = defaultdict(lambda: {"real": 0.0, "non": 0.0})
    split_channel: dict[str, dict] = defaultdict(lambda: {"real": 0.0, "non": 0.0})
    for p in pivots:
        total += p["total"]; real_cash += p["real_cash"]; non_cash += p["non_cash"]
        cash_relevant += p["cash_relevant_total"]; bank_only += p["bank_only_total"]
        for k, v in p["by_bucket"].items(): by_bucket[k] += v
        for k, v in p["by_bank"].items(): by_bank[k] += v
        for k, v in p["by_brand"].items(): by_brand[k] += v
        for k, v in p["by_channel"].items(): by_channel[k] += v
        for dst, src in ((split_bucket, "by_bucket_split"), (split_bank, "by_bank_split"),
                         (split_brand, "by_brand_split"), (split_channel, "by_channel_split")):
            for k, v in p.get(src, {}).items():
                dst[k]["real"] += v["real"]; dst[k]["non"] += v["non"]

    def _r(d: dict) -> dict:
        return {k: round(v, 2) for k, v in d.items()}

    def _rr(d: dict) -> dict:
        return {k: {"real": round(v["real"], 2), "non": round(v["non"], 2)} for k, v in d.items()}

    return {
        "total": round(total, 2), "real_cash": round(real_cash, 2),
        "non_cash": round(non_cash, 2), "cash_relevant_total": round(cash_relevant, 2),
        "bank_only_total": round(bank_only, 2),
        "by_bucket": _r(by_bucket), "by_bank": _r(by_bank),
        "by_brand": _r(by_brand), "by_channel": _r(by_channel),
        "by_bucket_split": _rr(split_bucket), "by_bank_split": _rr(split_bank),
        "by_brand_split": _rr(split_brand), "by_channel_split": _rr(split_channel),
    }


async def _days_with_data(session, pid, start, end) -> list[date_cls]:
    """Días con algún renglón de Integrity en el rango (no necesariamente de pago)."""
    rows = (await session.execute(
        select(IntegrityLine.business_date).where(
            IntegrityLine.property_id == pid,
            IntegrityLine.business_date >= start, IntegrityLine.business_date <= end,
        ).distinct()
    )).scalars().all()
    return sorted(rows)


async def _cash_for_range(session, pid, start, end, payment_map: dict) -> dict:
    """Pivote agregado sobre un rango de días (los que tengan datos cargados)."""
    days = await _days_with_data(session, pid, start, end)
    pivots, unmapped = [], []
    for d in days:
        r = await _cash_for_day(session, pid, d, payment_map)
        pivots.append(r["pivot"])
        unmapped.extend(r["unmapped"])
    return {"pivot": _merge_pivots(pivots), "unmapped": unmapped, "days_loaded": len(days)}


async def daily_cash(session: AsyncSession, business_date: date_cls,
                     property_code: str = "COWLCR") -> dict:
    """Daily Cash from Operation: Today + MTD, buckets de dos niveles (§5.5)."""
    pid = await _property_id(session, property_code)
    payment_map = await _payment_map(session, pid)

    today = await _cash_for_day(session, pid, business_date, payment_map)
    mtd = await _cash_for_range(session, pid, business_date.replace(day=1), business_date, payment_map)

    return {
        "business_date": business_date.isoformat(),
        "property": property_code,
        "days_loaded_mtd": mtd["days_loaded"] or 1,
        "today": today["pivot"],
        "mtd": mtd["pivot"],
        "unmapped_today": today["unmapped"],
        "unmapped_mtd": mtd["unmapped"],
    }


async def weekly_cash(session: AsyncSession, business_date: date_cls,
                      property_code: str = "COWLCR") -> dict:
    """Weekly Cash: semana Lun-Dom (dim_calendar) + YTD, mismo criterio que Revenue Weekly."""
    pid = await _property_id(session, property_code)
    payment_map = await _payment_map(session, pid)

    cal = (await session.execute(
        select(Calendar).where(Calendar.date == business_date)
    )).scalar_one_or_none()
    if cal is None:
        raise ValueError(f"'{business_date}' no está en dim_calendar (corré el seed).")

    year_start = business_date.replace(month=1, day=1)
    week = await _cash_for_range(session, pid, cal.week_start, cal.week_end, payment_map)
    ytd = await _cash_for_range(session, pid, year_start, cal.week_end, payment_map)

    return {
        "business_date": business_date.isoformat(),
        "property": property_code,
        "week": {"iso_week": cal.iso_week, "week_start": cal.week_start.isoformat(),
                 "week_end": cal.week_end.isoformat(), "label": cal.week_label},
        "days_loaded_week": week["days_loaded"], "days_loaded_ytd": ytd["days_loaded"],
        "weekly": week["pivot"],
        "ytd": ytd["pivot"],
        "unmapped_weekly": week["unmapped"],
        "unmapped_ytd": ytd["unmapped"],
    }


async def monthly_currency_summary(session: AsyncSession, year: int,
                                   property_code: str = "COWLCR") -> dict:
    """Tab 5.1 -- Monthly Summary / Transaction Currency Basis: Cards/Transfers/
    Cash/SINPE en su moneda nativa + Non-Cash (siempre USD), mes a mes + YTD.

    Se calcula 100% desde la ingesta real día a día (misma fuente que el
    resto de Tab 5) -- un mes sin ningún día ingestado da todo en $0, igual
    que ya se ve en cualquier otra vista de la app antes de que haya datos.
    No hay carga del histórico manual pre-Daily-Ops (decisión 2026-07-03):
    una sola fuente de verdad, sin mezclar Excel viejo con ingesta real."""
    pid = await _property_id(session, property_code)
    payment_map = await _payment_map(session, pid)

    months = []
    ytd_lines: list[dict] = []
    for m in range(1, 13):
        start = date_cls(year, m, 1)
        end = (date_cls(year, m + 1, 1) - timedelta(days=1)) if m < 12 else date_cls(year, 12, 31)
        days = await _days_with_data(session, pid, start, end)
        month_lines: list[dict] = []
        for d in days:
            lines, _ = await _payment_lines_for_day(session, pid, d)
            month_lines.extend(lines)
        ytd_lines.extend(month_lines)
        row = currency_basis_pivot(month_lines, payment_map)
        row["month"] = start.strftime("%b-%y")
        row["days_loaded"] = len(days)
        months.append(row)

    ytd = currency_basis_pivot(ytd_lines, payment_map)
    ytd["days_loaded"] = sum(r["days_loaded"] for r in months)
    return {"year": year, "property": property_code, "months": months, "ytd": ytd}


# --- Tab 5.2 Monthly Cash Position -----------------------------------------
import calendar  # noqa: E402
from decimal import Decimal  # noqa: E402

from app.models import AppConfig, MonthlyCashPosition  # noqa: E402

_MCP_EDITABLE = ["opening", "other_collections", "pay_vendors", "pay_capital",
                 "pay_payroll", "pay_social_security", "pay_ins", "pay_hacienda",
                 "other_pay_1", "other_pay_2", "other_pay_3", "other_pay_4"]
_MCP_PAYMENTS = ["pay_vendors", "pay_capital", "pay_payroll", "pay_social_security",
                 "pay_ins", "pay_hacienda", "other_pay_1", "other_pay_2", "other_pay_3", "other_pay_4"]
# Tasas (en %) para netear el bruto: comisión + retención de tarjeta, por canal.
_MCP_RATES = ["pos_commission_pct", "pos_retention_pct",
              "ecom_commission_pct", "ecom_retention_pct"]

# Labels EDITABLES de las 4 líneas "Other Payment" — globales por propiedad
# (aplican a todos los meses), guardados en app_config.
_MCP_LABEL_KEY = {"other_pay_1": "cash_pos_label_1", "other_pay_2": "cash_pos_label_2",
                  "other_pay_3": "cash_pos_label_3", "other_pay_4": "cash_pos_label_4"}
_MCP_LABEL_DEFAULT = {"other_pay_1": "Other Payment #1", "other_pay_2": "Other Payment #2",
                      "other_pay_3": "Other Payment #3", "other_pay_4": "Other Payment #4"}


async def _mcp_labels(session: AsyncSession, pid) -> dict:
    rows = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid,
                                AppConfig.key.in_(list(_MCP_LABEL_KEY.values())))
    )).scalars().all()
    by_key = {r.key: r.value for r in rows}
    return {f: (by_key.get(k) or _MCP_LABEL_DEFAULT[f]) for f, k in _MCP_LABEL_KEY.items()}


async def _save_mcp_labels(session: AsyncSession, pid, labels: dict) -> None:
    for f, cfgkey in _MCP_LABEL_KEY.items():
        v = labels.get(f)
        if v is None:
            continue
        v = str(v).strip() or _MCP_LABEL_DEFAULT[f]
        row = (await session.execute(
            select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == cfgkey)
        )).scalar_one_or_none()
        if row is None:
            session.add(AppConfig(property_id=pid, key=cfgkey, value=v))
        else:
            row.value = v


async def monthly_position(session: AsyncSession, year: int, month: int,
                           property_code: str = "COWLCR",
                           as_of: date_cls | None = None) -> dict:
    """Tab 5.2: líneas editables (guardadas) + "MTD Cash collected from the
    Operation" = Real Cash MTD (cash_flow='Real Cash', NO AR/Non-Cash) + Month
    Balance computado."""
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(MonthlyCashPosition).where(
            MonthlyCashPosition.property_id == pid,
            MonthlyCashPosition.year == year, MonthlyCashPosition.month == month)
    )).scalar_one_or_none()
    vals = {k: (float(getattr(row, k)) if row else 0.0) for k in _MCP_EDITABLE}
    rates = {k: (float(getattr(row, k)) if row else 0.0) for k in _MCP_RATES}

    # Arrastre de tasas (pedido del owner: las comisiones/retención no cambian
    # normalmente, son las mismas por mucho tiempo). Si este mes NO tiene tasas
    # propias (todas en 0), hereda las del mes ANTERIOR más reciente que sí las
    # tenga. Las bases (POS/Ecommerce) siguen siendo las de ESTE mes -- sólo se
    # heredan los porcentajes. Al guardar el mes con cualquier cambio, quedan
    # explícitas y dejan de heredarse.
    rates_inherited_from = None
    if not any(rates.values()):
        prior = (await session.execute(
            select(MonthlyCashPosition).where(
                MonthlyCashPosition.property_id == pid,
                ((MonthlyCashPosition.year < year) |
                 ((MonthlyCashPosition.year == year) & (MonthlyCashPosition.month < month))),
            ).order_by(MonthlyCashPosition.year.desc(), MonthlyCashPosition.month.desc())
        )).scalars().all()
        for p in prior:
            pr = {k: float(getattr(p, k)) for k in _MCP_RATES}
            if any(pr.values()):
                rates = pr
                rates_inherited_from = f"{p.year}-{p.month:02d}"
                break

    month_start = date_cls(year, month, 1)
    month_end = date_cls(year, month, calendar.monthrange(year, month)[1])
    to = min(as_of, month_end) if as_of else month_end
    real_cash = 0.0
    channel_split: dict = {}
    if to >= month_start:
        pm = await _payment_map(session, pid)
        rng = await _cash_for_range(session, pid, month_start, to, pm)
        real_cash = rng["pivot"]["real_cash"]
        channel_split = rng["pivot"].get("by_channel_split", {})

    # Base de comisión/retención = Real Cash cobrado por tarjeta en cada canal.
    # (Wire/Cash/Internal NO llevan comisión de tarjeta.) Se identifica el canal
    # por su nombre en dim_payment_map: 'POS' y 'Ecommerce'.
    def _chan_real(pred) -> float:
        return sum(v.get("real", 0.0) for k, v in channel_split.items() if pred((k or "").lower()))
    pos_base = _chan_real(lambda k: k == "pos")
    ecom_base = _chan_real(lambda k: k.startswith("ecom"))
    pos_fee = pos_base * (rates["pos_commission_pct"] + rates["pos_retention_pct"]) / 100.0
    ecom_fee = ecom_base * (rates["ecom_commission_pct"] + rates["ecom_retention_pct"]) / 100.0
    total_fees = pos_fee + ecom_fee
    net_operation = real_cash - total_fees

    payments = sum(vals[k] for k in _MCP_PAYMENTS)
    # El NETO (después de comisiones + retención de tarjeta) es el que alimenta
    # el Month Balance / cash flow -- no el bruto.
    balance = vals["opening"] + net_operation + vals["other_collections"] - payments
    return {
        "year": year, "month": month, "as_of": to.isoformat(),
        "mtd_operation": round(net_operation, 2),        # el que alimenta el balance (= neto)
        "mtd_operation_gross": round(real_cash, 2),
        "mtd_operation_net": round(net_operation, 2),
        "card_fees": {
            "pos_base": round(pos_base, 2), "ecom_base": round(ecom_base, 2),
            "pos_fee": round(pos_fee, 2), "ecom_fee": round(ecom_fee, 2),
            "total_fees": round(total_fees, 2),
            "rates_inherited_from": rates_inherited_from,
            **{k: round(rates[k], 4) for k in _MCP_RATES},
        },
        **{k: round(vals[k], 2) for k in _MCP_EDITABLE},
        "labels": await _mcp_labels(session, pid),
        "total_payments": round(payments, 2),
        "month_balance": round(balance, 2),
    }


async def save_monthly_position(session: AsyncSession, year: int, month: int,
                                values: dict, property_code: str = "COWLCR",
                                as_of: date_cls | None = None,
                                labels: dict | None = None) -> dict:
    pid = await _property_id(session, property_code)
    row = (await session.execute(
        select(MonthlyCashPosition).where(
            MonthlyCashPosition.property_id == pid,
            MonthlyCashPosition.year == year, MonthlyCashPosition.month == month)
    )).scalar_one_or_none()
    if row is None:
        row = MonthlyCashPosition(property_id=pid, year=year, month=month)
        session.add(row)
    for k in _MCP_EDITABLE:
        if values.get(k) is not None:
            setattr(row, k, Decimal(str(values[k])))
    for k in _MCP_RATES:
        if values.get(k) is not None:
            setattr(row, k, Decimal(str(values[k])))
    if labels:
        await _save_mcp_labels(session, pid, labels)
    await session.commit()
    return await monthly_position(session, year, month, property_code=property_code, as_of=as_of)
