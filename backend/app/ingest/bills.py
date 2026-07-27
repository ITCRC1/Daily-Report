"""Parsers de BILLS.xml (folios) y CUSTOMER.xml (nombres) — detalle auxiliar de ledgers."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


def _f(el, tag, default=0.0) -> float:
    v = el.findtext(tag)
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        return default


def parse_customers(path: str | Path) -> dict[str, str]:
    """CUSTOMER.xml → {internal_id: 'Apellido, Nombre'}."""
    root = ET.parse(path).getroot()
    out = {}
    for c in root.findall("customer"):
        cid = c.get("internal_id")
        name = (c.findtext("name", "") or "").strip()
        if cid:
            out[cid] = name
    return out


@dataclass
class BillLine:
    trx_code: str
    trx_date: str
    net_amount: float
    debit_amount: float
    credit_amount: float


@dataclass
class Bill:
    bill_no: str
    bill_type: str
    status: str
    guest_internal_id: str
    guest_name: str
    total_amount: float
    lines: list[BillLine] = field(default_factory=list)


def parse_bills(path: str | Path, customers: dict[str, str] | None = None) -> list[Bill]:
    """BILLS.xml → folios con su detalle de transacciones. Nombre desde CUSTOMER si existe."""
    customers = customers or {}
    root = ET.parse(path).getroot()
    bills: list[Bill] = []
    for b in root.findall("bill"):
        gid = (b.findtext("guest_internal_id", "") or b.get("customer_internal_id", "") or "").strip()
        # nombre: preferir CUSTOMER; si no, reservation_info/guest_name
        name = customers.get(gid) or (b.findtext("reservation_info/guest_name", "") or "").strip()
        lines = []
        for t in b.findall("bill_detail/transaction"):
            lines.append(BillLine(
                trx_code=(t.findtext("trx_code", "") or "").strip(),
                trx_date=(t.findtext("trx_date", "") or "").strip(),
                net_amount=_f(t, "net_amount"),
                debit_amount=_f(t, "debit_amount"),
                credit_amount=_f(t, "credit_amount"),
            ))
        bills.append(Bill(
            bill_no=(b.findtext("bill_no", "") or "").strip(),
            bill_type=(b.findtext("bill_type", "") or "").strip(),
            status=(b.findtext("status", "") or "").strip(),
            guest_internal_id=gid,
            guest_name=name,
            total_amount=_f(b, "total_amount"),
            lines=lines,
        ))
    return bills
