"""Reconciliación Opera ↔ Integrity (núcleo, §5.4 — portado de auditoria.py).

Función pura: recibe headers de Opera y filas agregadas de Integrity (por tcode),
devuelve la lista reconciliada con diferencia, estado y categoría, más KPIs.
"""
from __future__ import annotations

from dataclasses import dataclass

TOL = 0.01

CAT_MAP = {
    "REVENUE": "Revenue", "NON REVENUE": "Non-Revenue", "PAYMENT": "Payments",
    "INTERNAL": "Internal", "PACKAGE": "Packages",
}
TYPE_ORDER = ["REVENUE", "NON REVENUE", "PAYMENT", "INTERNAL", "PACKAGE"]


@dataclass
class ReconRow:
    tcode: str
    description: str
    type: str | None
    categoria: str
    opera: float | None
    integrity: float | None
    diferencia: float | None
    estado: str  # OK | DISCREPANCIA | FALTA EN INTEGRITY | FALTA EN OPERA | INTERNO
    cuenta: str
    nombre: str


def reconcile(opera_headers, integrity_rows, tol: float = TOL) -> list[ReconRow]:
    """opera_headers: list[OperaHeader]; integrity_rows: list[dict] (por tcode)."""
    ops = {h.tcode: h for h in opera_headers}
    ints = {r["tcode"]: r for r in integrity_rows}
    all_tcodes = list(dict.fromkeys(list(ops) + list(ints)))  # preserva orden, sin dups

    out: list[ReconRow] = []
    for tc in all_tcodes:
        op = ops.get(tc)
        it = ints.get(tc)
        ttype = op.type if op else None
        opera_amt = op.total if op else None

        # lado Integrity según regla de signo (§5.4): PAYMENT usa -int_db; el resto int_cr
        is_payment = op is not None and op.type == "PAYMENT"
        if it is None:
            integ_amt = None
        elif is_payment:
            integ_amt = -it["int_db"]
        else:
            integ_amt = it["int_cr"]

        # diferencia = integ - opera (solo cuando ambos lados existen)
        dif = round(integ_amt - (opera_amt or 0.0), 2) if (op and it) else None

        # estado
        if op is not None and it is None:
            estado = "INTERNO" if ttype in ("INTERNAL", "PACKAGE") else "FALTA EN INTEGRITY"
        elif op is None and it is not None:
            estado = "FALTA EN OPERA"
        else:
            estado = "OK" if abs(dif) < tol else "DISCREPANCIA"

        out.append(ReconRow(
            tcode=tc,
            description=op.description if op else "",
            type=ttype,
            categoria=CAT_MAP.get(ttype, "Uncategorized"),
            opera=opera_amt,
            integrity=integ_amt,
            diferencia=dif,
            estado=estado,
            cuenta=(it["cuenta"] if it else ""),
            nombre=(it["nombre"] if it else ""),
        ))

    out.sort(key=lambda r: (TYPE_ORDER.index(r.type) if r.type in TYPE_ORDER else 99, r.tcode))
    return out


def recon_kpis(rows: list[ReconRow]) -> dict:
    return {
        "ok": sum(1 for r in rows if r.estado == "OK"),
        "discrepancia": sum(1 for r in rows if r.estado == "DISCREPANCIA"),
        "faltante": sum(1 for r in rows if r.estado in ("FALTA EN INTEGRITY", "FALTA EN OPERA")),
        "interno": sum(1 for r in rows if r.estado == "INTERNO"),
    }
