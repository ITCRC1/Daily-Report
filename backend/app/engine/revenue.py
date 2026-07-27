"""Motor de Revenue (etapa 2) — pivote de las 12 columnas canónicas (§5.1).

Puro Python, sin dependencias de UI ni de la base. Recibe líneas de revenue
(cuenta USALI 4NNN-0NNN-… + monto USD neto) y las clasifica en:

  (a) columna de salida por OUTLET (4-díg, §5.1b): F&B colapsado en una columna.
  (b) desglose F&B Food/Beverage/Misc por NATURALEZA 9-char (§5.1a).

Regla de monto (§5.3): Revenue USD = Créditos − Débitos. El caller pasa el neto.

Clasificaciones que no caen en el mapa → 'Otros' (excepción VISIBLE, nunca se
descarta ni se recategoriza en silencio — §6.4/§10).
"""
from __future__ import annotations

from collections import defaultdict

# Columnas de salida canónicas (§5.1), en orden de reporte. F&B es una sola
# columna en la tabla principal; el desglose Food/Bev/Misc va aparte.
OUTPUT_COLUMNS = [
    "Rooms", "F&B", "SPA", "Retail-Gift Shop", "Tours", "Transportation",
    "Laundry", "Innoceana", "Crowther Lab", "Sustainable Fee",
]

# Outlet 4-díg (cuenta[5:9]) → columna de salida (DEPT_MAP, §5.1b / §7).
OUTLET_TO_COLUMN = {
    "0110": "Rooms",
    "0140": "SPA",
    "0150": "Tours",
    "0151": "Retail-Gift Shop",
    "0152": "Transportation",
    "0160": "Laundry",
    "0155": "Innoceana",
    "0156": "Crowther Lab",
    "0170": "Sustainable Fee",
    # outlets de F&B → todos colapsan a la columna 'F&B'
    "0123": "F&B", "0124": "F&B", "0125": "F&B", "0126": "F&B",
    "0127": "F&B", "0128": "F&B", "0129": "F&B", "0130": "F&B",
}

# Naturaleza 4-díg (cuenta[:4]) → subcategoría F&B (§5.1a).
# OJO: la 4120 aparece como "NA BEVERAGE" en los datos, pero el spec §5.1a la
# clasifica como FOOD. Se respeta el spec (no inventar — TODO(bismark) si debe
# cambiar a BEVERAGE).
FB_NATURE = {
    "4110": "FOOD", "4120": "FOOD",
    "4125": "BEVERAGE", "4130": "BEVERAGE", "4131": "BEVERAGE",
    "4132": "MISC",
}


def output_column(cuenta: str) -> str:
    """Columna de salida por outlet 4-díg. Fuera del mapa → 'Otros' (visible)."""
    outlet = (cuenta or "")[5:9]
    return OUTLET_TO_COLUMN.get(outlet, "Otros")


def fb_subcategory(cuenta: str) -> str:
    """Subcategoría F&B por naturaleza 4-díg. Default FOOD si no matchea (§5.1a)."""
    return FB_NATURE.get((cuenta or "")[:4], "FOOD")


def daily_revenue(lines: list[dict]) -> dict:
    """Pivote de un día. `lines` = dicts con 'cuenta' y 'amount' (USD neto, cr−db).

    Devuelve columnas canónicas + desglose F&B + total + 'otros' (excepciones).
    """
    by_col: dict[str, float] = defaultdict(float)
    fb: dict[str, float] = defaultdict(float)
    otros: list[dict] = []

    for ln in lines:
        cuenta = str(ln.get("cuenta") or "")
        if not cuenta.startswith("4"):
            continue
        amt = float(ln.get("amount") or 0.0)
        col = output_column(cuenta)
        by_col[col] += amt
        if col == "F&B":
            fb[fb_subcategory(cuenta)] += amt
        elif col == "Otros":
            otros.append({"cuenta": cuenta,
                          "nombre": ln.get("nombre"), "amount": round(amt, 2)})

    columns = {c: round(by_col.get(c, 0.0), 2) for c in OUTPUT_COLUMNS}
    otros_total = round(by_col.get("Otros", 0.0), 2)
    fb_detail = {
        "food": round(fb.get("FOOD", 0.0), 2),
        "beverage": round(fb.get("BEVERAGE", 0.0), 2),
        "misc": round(fb.get("MISC", 0.0), 2),
    }
    total = round(sum(columns.values()) + otros_total, 2)
    return {
        "columns": columns,
        "fb_detail": fb_detail,
        "fb_split_check": round(columns["F&B"]
                                - sum(fb_detail.values()), 2),  # debe ser 0
        "otros_total": otros_total,
        "otros": otros,
        "total": total,
    }


# --- Weekly (Tab 4): mismo outlet, pero 0110 y 0170 se abren por NATURALEZA
# (§5.1a, "ESTA es la canónica") en vez de colapsar todo el outlet en una sola
# columna. Confirmado contra la grilla 'Actual' del golden Weekly (2026-06-08:
# Rooms Others=0, Misc. Rev Others=0 porque ese día no tiene esas naturalezas).
WEEKLY_COLUMNS = [
    "Rooms", "Rooms Others", "F&B", "SPA", "Retail-Gift Shop", "Tours",
    "Transportation", "Laundry", "Innoceana", "Crowther Lab",
    "Sustainable Fee", "Misc. Rev Others",
]

_ROOMS_NATURE = "4000"
_MISC_REV_OTHERS_NATURE = {"4800", "4820", "4850"}
_SUSTAINABILITY_NATURE = "4880"

# Sufijo de 2 dígitos final de la cuenta (nature 4000 + outlet 0110, Room
# Revenue) -> code2 de dim_room_category. CONFIRMADO por Bismark y verificado
# contra Integrity real: el sufijo es estable (AGUJAS QUEEN siempre -03,
# SIRENA -04, TREEHOUSE -05) aunque los segmentos del medio (mercado/canal:
# 003/004/005/006/020…) varíen. Cualquier sufijo fuera de 01-06 -> "Other
# Rooms Revenue" (code2 '00'), no se descarta (§10).
ROOM_CATEGORY_SUFFIXES = {"01", "02", "03", "04", "05", "06"}


def room_category_suffix(cuenta: str) -> str | None:
    """Sufijo de 2 dígitos de una cuenta de Room Revenue (nature 4000, outlet
    0110). None si la cuenta no es de Rooms. '00' si es Rooms pero el sufijo
    no matchea ninguna categoría conocida (Other Rooms Revenue, §Bismark)."""
    cuenta = cuenta or ""
    if cuenta[:4] != _ROOMS_NATURE or cuenta[5:9] != "0110":
        return None
    suffix = cuenta.rsplit("-", 1)[-1]
    return suffix if suffix in ROOM_CATEGORY_SUFFIXES else "00"


def room_revenue_by_category(lines: list[dict]) -> dict[str, float]:
    """Suma Room Revenue (§5.3, cred-deb) por code2 de dim_room_category, vía
    el sufijo de cuenta. `lines`: salida de `lines_from_integrity`."""
    totals: dict[str, float] = defaultdict(float)
    for ln in lines:
        code2 = room_category_suffix(str(ln.get("cuenta") or ""))
        if code2 is not None:
            totals[code2] += float(ln.get("amount") or 0.0)
    return dict(totals)


def weekly_output_column(cuenta: str) -> str:
    """Columna de salida para el Weekly: como output_column(), pero abre 0110
    en Rooms/Rooms Others y 0170 en Sustainable Fee/Misc. Rev Others por
    naturaleza 9-char (§5.1a)."""
    cuenta = cuenta or ""
    outlet = cuenta[5:9]
    nature = cuenta[:4]
    if outlet == "0110":
        return "Rooms" if nature == _ROOMS_NATURE else "Rooms Others"
    if outlet == "0170":
        if nature == _SUSTAINABILITY_NATURE:
            return "Sustainable Fee"
        if nature in _MISC_REV_OTHERS_NATURE:
            return "Misc. Rev Others"
        return "Misc. Rev Others"  # residual del outlet, no descartar (§10)
    return OUTLET_TO_COLUMN.get(outlet, "Otros")


def weekly_pivot(lines: list[dict]) -> dict:
    """Pivote (día o rango ya agregado) para el Weekly: 12 columnas (Rooms
    abierto + F&B colapsado con detalle + Sustainable Fee abierto) + Otros."""
    by_col: dict[str, float] = defaultdict(float)
    fb: dict[str, float] = defaultdict(float)
    otros: list[dict] = []

    for ln in lines:
        cuenta = str(ln.get("cuenta") or "")
        if not cuenta.startswith("4"):
            continue
        amt = float(ln.get("amount") or 0.0)
        col = weekly_output_column(cuenta)
        by_col[col] += amt
        if col == "F&B":
            fb[fb_subcategory(cuenta)] += amt
        elif col == "Otros":
            otros.append({"cuenta": cuenta,
                          "nombre": ln.get("nombre"), "amount": round(amt, 2)})

    columns = {c: round(by_col.get(c, 0.0), 2) for c in WEEKLY_COLUMNS}
    otros_total = round(by_col.get("Otros", 0.0), 2)
    fb_detail = {
        "food": round(fb.get("FOOD", 0.0), 2),
        "beverage": round(fb.get("BEVERAGE", 0.0), 2),
        "misc": round(fb.get("MISC", 0.0), 2),
    }
    total = round(sum(columns.values()) + otros_total, 2)
    return {
        "columns": columns, "fb_detail": fb_detail,
        "otros_total": otros_total, "otros": otros, "total": total,
    }


def lines_from_integrity(integ_rows: list[dict]) -> list[dict]:
    """Adapta líneas de stg_integrity_line → entrada de daily_revenue (§5.3)."""
    return [{
        "cuenta": r.get("cuenta"),
        "nombre": r.get("nombre_cuenta"),
        "amount": float(r.get("cred_usd") or 0.0) - float(r.get("deb_usd") or 0.0),
    } for r in integ_rows]
