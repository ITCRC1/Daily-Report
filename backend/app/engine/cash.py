"""Motor de Cash (etapa 3) — buckets de dos niveles vía dim_payment_map (§5.5).

Puro Python: recibe líneas de pago ya resueltas (tcode + monto) y el mapa de
pagos (dict tcode -> atributos de dim_payment_map), y devuelve los pivotes por
bucket/banco/marca/canal + los dos totales de cash-relevancia.

Regla de monto (§5.3): Cash Amount USD Eq = Débitos − Créditos (opuesto a
Revenue). El caller (cash_service) ya entrega el monto neto en ese signo.

UNMAPPED (§5.5): un TCode de pago (Opera type=PAYMENT) sin entrada en
dim_payment_map es una EXCEPCIÓN VISIBLE — nunca se descarta en silencio.
Se detecta contra el universo de tcodes de pago, no acá (ver cash_service).
"""
from __future__ import annotations

from collections import defaultdict

# §5.5 — Cash-relevant (amplio): estos bancos/medios cuentan como "cash" del negocio.
CASH_RELEVANT_BANKS = {"BAC", "BCR", "BNCR", "LAF", "CASH", "SINPE", "ROOM", "HOUSE", "AR"}

# §5.5 — Bank-only (estricto, para Bank Recon): tarjeta/transferencia en banco real.
BANK_ONLY_TIPOS = {"Tarjeta", "Transferencia"}
BANK_ONLY_BANKS = {"BAC", "BCR", "BNCR", "LAF"}


def is_cash_relevant(banco_codigo: str | None) -> bool:
    return (banco_codigo or "") in CASH_RELEVANT_BANKS


def is_bank_only(tipo_pago: str | None, banco_codigo: str | None) -> bool:
    return (tipo_pago or "") in BANK_ONLY_TIPOS and (banco_codigo or "") in BANK_ONLY_BANKS


def cash_pivot(lines: list[dict], payment_map: dict[str, dict]) -> dict:
    """`lines`: [{'tcode','amount_usd','amount_crc'}, ya filtradas a tcodes de
    pago existentes en Integrity. `payment_map`: {tcode: {banco_codigo,
    tipo_pago, marca_metodo, canal, cash_flow, report_bucket}}.
    """
    by_bucket: dict[str, float] = defaultdict(float)
    by_bank: dict[str, float] = defaultdict(float)
    by_brand: dict[str, float] = defaultdict(float)
    by_channel: dict[str, float] = defaultdict(float)
    # Desglose de cada dimensión partido por cash_flow (Real Cash vs No-Cash),
    # para poder mostrar EXACTAMENTE qué líneas componen el Real Cash (Tab 5,
    # vista "Composición del Real Cash"). Se parte a nivel de línea -- no se
    # asume que un bucket sea íntegramente real o non (aunque hoy lo sea).
    split_bucket: dict[str, dict] = defaultdict(lambda: {"real": 0.0, "non": 0.0})
    split_bank: dict[str, dict] = defaultdict(lambda: {"real": 0.0, "non": 0.0})
    split_brand: dict[str, dict] = defaultdict(lambda: {"real": 0.0, "non": 0.0})
    split_channel: dict[str, dict] = defaultdict(lambda: {"real": 0.0, "non": 0.0})
    real_cash = 0.0
    non_cash = 0.0
    cash_relevant_total = 0.0
    bank_only_total = 0.0
    total = 0.0

    for ln in lines:
        tcode = ln.get("tcode")
        pm = payment_map.get(tcode)
        if pm is None:
            continue  # no es una línea de pago mapeada (revenue/otro) — se ignora acá
        amt = float(ln.get("amount_usd") or 0.0)
        total += amt
        bkt = pm.get("report_bucket") or "Sin bucket"
        bnk = pm.get("banco_codigo") or "—"
        brd = pm.get("marca_metodo") or "—"
        chn = pm.get("canal") or "—"
        by_bucket[bkt] += amt
        by_bank[bnk] += amt
        by_brand[brd] += amt
        by_channel[chn] += amt
        is_real = (pm.get("cash_flow") or "") == "Real Cash"
        slot = "real" if is_real else "non"
        split_bucket[bkt][slot] += amt
        split_bank[bnk][slot] += amt
        split_brand[brd][slot] += amt
        split_channel[chn][slot] += amt
        if is_real:
            real_cash += amt
        else:
            non_cash += amt
        if is_cash_relevant(pm.get("banco_codigo")):
            cash_relevant_total += amt
        if is_bank_only(pm.get("tipo_pago"), pm.get("banco_codigo")):
            bank_only_total += amt

    def _r(d: dict[str, float]) -> dict[str, float]:
        return {k: round(v, 2) for k, v in d.items()}

    def _rr(d: dict[str, dict]) -> dict[str, dict]:
        return {k: {"real": round(v["real"], 2), "non": round(v["non"], 2)} for k, v in d.items()}

    return {
        "total": round(total, 2),
        "real_cash": round(real_cash, 2),
        "non_cash": round(non_cash, 2),
        "cash_relevant_total": round(cash_relevant_total, 2),
        "bank_only_total": round(bank_only_total, 2),
        "by_bucket": _r(by_bucket),
        "by_bank": _r(by_bank),
        "by_brand": _r(by_brand),
        "by_channel": _r(by_channel),
        "by_bucket_split": _rr(split_bucket),
        "by_bank_split": _rr(split_bank),
        "by_brand_split": _rr(split_brand),
        "by_channel_split": _rr(split_channel),
    }


# Tab 5.1 — Monthly Summary / Transaction Currency Basis: agrupa por TIPO de
# transacción (no por banco/marca) en su moneda NATIVA -- "Cards CRC" y
# "Cards USD" son tcodes distintos (dim_payment_map.moneda), no la misma
# transacción convertida dos veces.
REAL_CASH_TYPES = ("cards", "transfers", "cash", "sinpe")


def _currency_basis_type(pm: dict) -> str:
    if (pm.get("cash_flow") or "") != "Real Cash":
        return "non_cash"
    tipo = pm.get("tipo_pago") or ""
    if tipo == "Tarjeta":
        return "cards"
    if tipo == "Transferencia":
        return "sinpe" if (pm.get("banco_codigo") or "") == "SINPE" else "transfers"
    if tipo == "Efectivo":
        return "cash"
    return "non_cash"


def currency_basis_pivot(lines: list[dict], payment_map: dict[str, dict]) -> dict:
    """Cards/Transfers/Cash/SINPE en su moneda nativa (CRC o USD según
    `dim_payment_map.moneda`) + Non-Cash (AR/Room/House Charge, que no tiene
    moneda nativa real -- dim_payment_map la marca 'INTERNAL' -- se reporta
    siempre en USD, igual que el resto de Tab 5).

    `unmapped_currency` (§10, nunca se pierde en silencio): un tcode Real Cash
    con `moneda` distinta de CRC/USD no debería existir hoy (todo el catálogo
    vigente usa una de esas dos) -- si aparece, el monto igual entra a la
    columna USD para no perderse, y queda listado acá como señal a revisar.
    """
    totals: dict[str, float] = {f"{t}_{c}": 0.0 for t in REAL_CASH_TYPES for c in ("crc", "usd")}
    totals["non_cash_usd"] = 0.0
    unmapped_currency: list[dict] = []

    for ln in lines:
        pm = payment_map.get(ln.get("tcode"))
        if pm is None:
            continue
        bucket = _currency_basis_type(pm)
        if bucket == "non_cash":
            totals["non_cash_usd"] += float(ln.get("amount_usd") or 0.0)
            continue
        moneda = pm.get("moneda")
        if moneda == "CRC":
            totals[f"{bucket}_crc"] += float(ln.get("amount_crc") or 0.0)
        elif moneda == "USD":
            totals[f"{bucket}_usd"] += float(ln.get("amount_usd") or 0.0)
        else:
            totals[f"{bucket}_usd"] += float(ln.get("amount_usd") or 0.0)
            unmapped_currency.append({"tcode": ln.get("tcode"), "amount_usd": ln.get("amount_usd")})

    total_real_cash_usd = sum(totals[f"{t}_usd"] for t in REAL_CASH_TYPES)
    total_non_cash_usd = totals["non_cash_usd"]
    return {
        **{k: round(v, 2) for k, v in totals.items()},
        "total_real_cash_usd": round(total_real_cash_usd, 2),
        "total_non_cash_usd": round(total_non_cash_usd, 2),
        "total_usd": round(total_real_cash_usd + total_non_cash_usd, 2),
        "unmapped_currency": unmapped_currency,
    }


def payment_lines_from_integrity(rows: list[dict]) -> list[dict]:
    """Adapta líneas de stg_integrity_line (ya filtradas por tcode de pago) a
    la entrada de cash_pivot. Monto §5.3: deb − cred (opuesto a revenue)."""
    return [{
        "tcode": r.get("tcode"),
        "amount_usd": float(r.get("deb_usd") or 0.0) - float(r.get("cred_usd") or 0.0),
        "amount_crc": float(r.get("deb_col") or 0.0) - float(r.get("cred_col") or 0.0),
    } for r in rows]
