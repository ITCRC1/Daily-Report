"""Parsers de los XML de Opera (portado de reference/auditoria.py, sin pandas).

Funciones puras: reciben rutas de archivo y devuelven listas/dicts de Python.
La carga a la base (fact_opera_txn / _detail / fact_room_stat) va en otra capa.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path


def _f(el, tag, default=0.0) -> float:
    v = el.findtext(tag)
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


def _i(el, tag, default=0) -> int:
    v = el.findtext(tag)
    try:
        return int(v) if v not in (None, "") else default
    except ValueError:
        return default


@dataclass
class OperaHeader:
    tcode: str
    description: str
    type: str  # REVENUE | NON REVENUE | PAYMENT | INTERNAL | PACKAGE
    total: float
    guest_ledger: float
    package_ledger: float
    ar_ledger: float
    deposit_ledger: float


@dataclass
class OperaDetail:
    tcode: str
    description: str
    type: str
    market_code: str
    room_class: str
    trx_amount: float
    trx_guest_ledger: float
    trx_package_ledger: float


def parse_revenue(path: str | Path) -> tuple[list[OperaHeader], list[OperaDetail]]:
    """*REVENUE*.xml → (headers, details). business_date = root @date."""
    root = ET.parse(path).getroot()
    headers: list[OperaHeader] = []
    details: list[OperaDetail] = []
    for tt in root.findall("transaction_total"):
        tcode = (tt.findtext("transaction_code") or "").strip()
        desc = (tt.findtext("description", "") or "").strip()
        ttype = tt.get("transaction_type")
        headers.append(OperaHeader(
            tcode=tcode, description=desc, type=ttype,
            total=_f(tt, "total_amount"),
            guest_ledger=_f(tt, "total_guest_ledger"),
            package_ledger=_f(tt, "total_package_ledger"),
            ar_ledger=_f(tt, "total_ar_ledger"),
            deposit_ledger=_f(tt, "total_deposit_ledger"),
        ))
        for trx in tt.findall("transaction_details/transaction"):
            details.append(OperaDetail(
                tcode=tcode, description=desc, type=ttype,
                market_code=(trx.findtext("market_code", "") or "").strip(),
                room_class=(trx.findtext("room_class", "") or "").strip(),
                trx_amount=_f(trx, "trx_amount"),
                trx_guest_ledger=_f(trx, "trx_guest_ledger"),
                trx_package_ledger=_f(trx, "trx_package_ledger"),
            ))
    return headers, details


@dataclass
class StatRecord:
    market_code: str
    room_class: str
    room_type: str
    rooms: int
    persons: int
    noshow: int
    cancel: int


def parse_statistics(path: str | Path) -> list[StatRecord]:
    """*STATISTICS*.xml → ocupación por market/clase/tipo."""
    root = ET.parse(path).getroot()
    out = []
    for rec in root.findall("statistic_record"):
        out.append(StatRecord(
            market_code=(rec.findtext("market_code", "") or "").strip(),
            room_class=(rec.findtext("room_class", "") or "").strip(),
            room_type=(rec.findtext("room_type", "") or "").strip(),
            rooms=_i(rec, "rooms"),
            persons=_i(rec, "persons"),
            noshow=_i(rec, "noshow_rooms"),
            cancel=_i(rec, "cancel_rooms"),
        ))
    return out


def parse_history_forecast(files: list[str | Path], business_date: date_cls) -> dict:
    """Dos history_forecast → {'total': {...}, 'rooms': {...}}.

    Cada archivo trae el AÑO COMPLETO (365 filas <G_CONSIDERED_DATE>, una por
    día) -- hay que buscar la fila cuyo CONSIDERED_DATE coincide con
    `business_date` del batch, si no la comparación OTB-vs-Revenue no es
    comparable (§10, bug real: antes se tomaba siempre la primera fila del
    archivo = 1-ene, sin importar qué día se estuviera auditando).

    El de MAYOR revenue ESE DÍA = Total (HF full); el menor = Rooms Only (§5.6).
    """
    rows = []
    for f in files:
        root = ET.parse(f).getroot()
        target = None
        for gd in root.findall(".//G_CONSIDERED_DATE"):
            raw = (gd.findtext("CONSIDERED_DATE") or "").strip()
            if not raw:
                continue
            try:
                d = datetime.strptime(raw, "%d-%b-%y").date()
            except ValueError:
                continue
            if d == business_date:
                target = gd
                break
        if target is None:
            continue  # el archivo no trae ese día -- excepción visible, no se fabrica
        rows.append({
            "file": str(f),
            "revenue": _f(target, "REVENUE"),
            "rooms": _i(target, "NO_ROOMS"),
            "persons": _i(target, "NO_PERSONS"),
            "inventory": _i(target, "INVENTORY_ROOMS"),
            "adr": _f(target, "CF_AVERAGE_ROOM_RATE"),
            "occupancy": _f(target, "CF_OCCUPANCY"),
        })
    rows.sort(key=lambda x: x["revenue"], reverse=True)
    result = {}
    if rows:
        result["total"] = rows[0]
    if len(rows) > 1:
        result["rooms"] = rows[1]
    return result


@dataclass
class RoomStatRecord:
    business_date: date_cls
    short_description: str
    room_revenue: float
    stay_rooms: int
    stay_persons: int
    physical_rooms: int


def parse_statroomtype(path: str | Path) -> list[RoomStatRecord]:
    """*statroomtype*.XML → estadísticas de habitación por categoría/día (etapa 5).

    Fuente de ADR/Occ/Yield y de la disponibilidad real del día (§3 modelo:
    'Disponibilidad del día = Σ physical_rooms, no hay constante hardcodeada').
    El archivo trae el AÑO completo; el caller filtra por business_date (§2.8:
    reemplazo total por día, la ingesta es por día, no por archivo completo).
    """
    root = ET.parse(path).getroot()
    out: list[RoomStatRecord] = []
    for rec in root.findall(".//G_D_CHAR"):
        raw_date = (rec.findtext("BUSINESS_DATE") or "").strip()
        if not raw_date:
            continue
        bdate = datetime.strptime(raw_date, "%d-%b-%y").date()
        out.append(RoomStatRecord(
            business_date=bdate,
            short_description=(rec.findtext("SHORT_DESCRIPTION", "") or "").strip(),
            room_revenue=_f(rec, "ROOM_REVENUE"),
            stay_rooms=_i(rec, "STAY_ROOMS"),
            stay_persons=_i(rec, "STAY_PERSONS"),
            physical_rooms=_i(rec, "PHYSICAL_ROOMS"),
        ))
    return out


def find_file(paths: list[str | Path], pattern: str) -> str | None:
    for p in paths:
        if re.search(pattern, Path(p).name, re.IGNORECASE):
            return str(p)
    return None


# --- Trial Balance oficial (OPERA_TrialBalance_*.XML) — Tab 2.2 + saldos 2.3 ---

# Prefijo del campo por ledger en los totales del reporte (CF_/CS_).
_TB_LEDGER_TAG = {
    "guest": "GUEST_LED",
    "package": "PACKAGE_LED",
    "ar": "AR_LED",
    "deposit": "DEPOSIT_LED",
}


def _rf(root, tag, default=0.0) -> float:
    """float de un campo de reporte (aparece 1 vez a nivel TRIAL_BALANCE)."""
    v = root.findtext(f".//{tag}")
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


def parse_trial_balance(path: str | Path) -> tuple[list[dict], dict]:
    """OPERA_TrialBalance_*.XML → (lineas_por_tcode, saldos_por_ledger).

    - lineas: una por G_TRX_CODE, con el neto por ledger (débito + crédito, el
      crédito ya viene NEGATIVO en el archivo). Reemplaza el trial balance que la
      app derivaba de fact_opera_txn (el de Opera incluye pagos/ajustes, no solo
      revenue).
    - saldos: por ledger, apertura=CF_*_YEST, movimiento=CS_*_DEBIT/CREDIT_REP,
      cierre=CF_*_REP (verificado: apertura+movimiento=cierre al centavo).
    """
    root = ET.parse(path).getroot()

    def _led(el, prefix):
        return round(_f(el, f"{prefix}_DEBIT") + _f(el, f"{prefix}_CREDIT"), 2)

    lines: list[dict] = []
    for tt in root.iter("G_TRX_TYPE"):
        ttype = (tt.findtext("TRX_TYPE") or "").strip()
        tdesc = (tt.findtext("TRX_TYPE_DESCRIPTION") or "").strip()
        for c in tt.iter("G_TRX_CODE"):
            lines.append({
                "trx_type": ttype, "trx_type_desc": tdesc,
                "tcode": (c.findtext("TRX_CODE") or "").strip(),
                "description": (c.findtext("DESCRIPTION") or "").strip(),
                "tb_amount": _f(c, "TB_AMOUNT"),
                "net_amount": _f(c, "NET_AMOUNT"),
                "guest_ledger": _led(c, "GUEST_LED"),
                "package_ledger": _led(c, "PACKAGE_LED"),
                "ar_ledger": _led(c, "AR_LED"),
                "deposit_ledger": _led(c, "DEP_LED"),
            })

    balances: dict[str, dict] = {}
    for ledger, tag in _TB_LEDGER_TAG.items():
        opening = _rf(root, f"CF_{tag}_YEST")
        debit = _rf(root, f"CS_{tag}_DEBIT_REP")
        credit = _rf(root, f"CS_{tag}_CREDIT_REP")
        closing = _rf(root, f"CF_{tag}_REP")
        balances[ledger] = {
            "opening": round(opening, 2), "debit": round(debit, 2),
            "credit": round(credit, 2), "closing": round(closing, 2),
        }
    return lines, balances


# --- City Ledger (OPERA_GEN_XMLBO_CITYLEDGER_*.xml) — detalle del AR Ledger ---

def parse_city_ledger(path: str | Path) -> list[dict]:
    """City Ledger → facturas a empresas/agencias (detalle del movimiento AR)."""
    root = ET.parse(path).getroot()
    out: list[dict] = []
    for t in root.iter("transaction"):
        acc = t.find("account_info")
        res = t.find("reservation_info")
        out.append({
            "trx_code": (t.get("trx_code") or "").strip(),
            "transaction_type": (t.get("transaction_type") or "").strip(),
            "bill_no": (t.findtext("bill_no") or "").strip() or None,
            "invoice_no": (t.findtext("invoice_no") or "").strip() or None,
            "amount": _f(t, "amount"),
            "customer_internal_id": (acc.get("customer_internal_id") if acc is not None else None),
            "account_name": (acc.findtext("account_name") if acc is not None else None),
            "account_number": (acc.findtext("account_number") if acc is not None else None),
            "confirmation_no": (res.findtext("confirmation_no") if res is not None else None),
            "arrival_date": (res.findtext("arrival_date") if res is not None else None),
            "departure_date": (res.findtext("departure_date") if res is not None else None),
            "guest_name": (res.findtext("guest_name") if res is not None else None),
        })
    return out


# --- Agregación MENSUAL del history_forecast (On The Books, Tab 8) ---

def history_forecast_monthly(files: list[str | Path]) -> dict:
    """Agrega los history_forecast del AÑO COMPLETO por mes, para el reporte
    On The Books (Budget vs OTB por mes).

    Recibe los 2 archivos (Full Revenue + Only Rooms). Cada uno trae 365 filas
    <G_CONSIDERED_DATE> agrupadas por <G_REC_TYPE> (History vs Forecast). Se
    distingue Full vs Only Rooms por el revenue anual (Full > Only Rooms).

    Devuelve {(year, month): {total_revenue, rooms_only_revenue,
    rooms_only_history, rooms_only_forecast, rooms_occ, guests, rooms_avail}}.
    El forecast puede abarcar >1 año, por eso la clave es (year, month) y no
    sólo el mes. Validado al centavo contra el golden 'ON THE BOOKS MASTER FILE'."""
    def _agg(path):
        """Buckets por (año, mes) -- el forecast puede abarcar >1 año."""
        root = ET.parse(path).getroot()
        rev: dict = {}
        hist: dict = {}
        fcst: dict = {}
        rooms: dict = {}
        pax: dict = {}
        avail: dict = {}
        annual = 0.0
        for rt in root.iter("G_REC_TYPE"):
            is_hist = "hist" in (rt.findtext("REC_TYPE_DESC") or "").strip().lower()
            for gd in rt.iter("G_CONSIDERED_DATE"):
                raw = (gd.findtext("CONSIDERED_DATE") or "").strip()
                if not raw:
                    continue
                try:
                    d = datetime.strptime(raw, "%d-%b-%y").date()
                except ValueError:
                    continue
                ym = (d.year, d.month)
                r = _f(gd, "REVENUE")
                rev[ym] = rev.get(ym, 0.0) + r
                bucket = hist if is_hist else fcst
                bucket[ym] = bucket.get(ym, 0.0) + r
                rooms[ym] = rooms.get(ym, 0.0) + _f(gd, "NO_ROOMS")
                pax[ym] = pax.get(ym, 0.0) + _f(gd, "NO_PERSONS")
                avail[ym] = avail.get(ym, 0.0) + _f(gd, "INVENTORY_ROOMS")
                annual += r
        return {"rev": rev, "hist": hist, "fcst": fcst,
                "rooms": rooms, "pax": pax, "avail": avail, "annual": annual}

    aggs = [_agg(f) for f in files]
    if not aggs:
        return {}
    aggs.sort(key=lambda a: a["annual"], reverse=True)
    full = aggs[0]                       # mayor revenue anual = Total Revenue
    rooms_only = aggs[1] if len(aggs) > 1 else aggs[0]

    # Todos los (año, mes) presentes en cualquiera de los 2 archivos.
    keys = sorted(set(full["rev"]) | set(rooms_only["rev"]))
    out = {}
    for ym in keys:
        out[ym] = {
            "total_revenue": round(full["rev"].get(ym, 0.0), 2),
            "rooms_only_revenue": round(rooms_only["rev"].get(ym, 0.0), 2),
            "rooms_only_history": round(rooms_only["hist"].get(ym, 0.0), 2),
            "rooms_only_forecast": round(rooms_only["fcst"].get(ym, 0.0), 2),
            "rooms_occ": round(full["rooms"].get(ym, 0.0), 2),
            "guests": round(full["pax"].get(ym, 0.0), 2),
            "rooms_avail": round(full["avail"].get(ym, 0.0), 2),
        }
    return out


def history_forecast_daily(files: list[str | Path]) -> dict:
    """Ocupación DIARIA del OTB (para el heatmap, Tab 8.3). Del archivo de mayor
    revenue anual (Full) toma NO_ROOMS (vendidas) e INVENTORY_ROOMS (disponibles)
    por día. Devuelve {iso_date: {rooms_sold, rooms_avail}}."""
    def _annual(path):
        root = ET.parse(path).getroot()
        total = 0.0
        for gd in root.iter("G_CONSIDERED_DATE"):
            total += _f(gd, "REVENUE")
        return total, root

    scored = [(_annual(f)) for f in files]
    if not scored:
        return {}
    scored.sort(key=lambda s: s[0], reverse=True)
    root = scored[0][1]  # Full = mayor revenue anual

    out = {}
    for gd in root.iter("G_CONSIDERED_DATE"):
        raw = (gd.findtext("CONSIDERED_DATE") or "").strip()
        if not raw:
            continue
        try:
            d = datetime.strptime(raw, "%d-%b-%y").date()
        except ValueError:
            continue
        out[d.isoformat()] = {
            "rooms_sold": _f(gd, "NO_ROOMS"),
            "rooms_avail": _f(gd, "INVENTORY_ROOMS"),
        }
    return out
