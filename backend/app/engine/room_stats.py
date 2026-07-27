"""Motor de Room Stats (etapa 5) — ADR / Occupancy / Yield por categoría (§5.2, §5.3).

Puro Python. Recibe registros ya cargados (business_date, short_description,
room_revenue, stay_rooms, stay_persons, physical_rooms) de un período (un día
o varios ya filtrados por el caller) y arma el rollup por categoría.

Disponibilidad (§3): Σ physical_rooms del período, NUNCA una constante
hardcodeada — si un día trae menos categorías activas (ej. villas fuera de
servicio), la disponibilidad de ese día baja en consecuencia, honestamente.
"""
from __future__ import annotations

from collections import defaultdict

# Orden y catálogo canónico de categorías (§5.2, dim_room_category.opera_short_desc).
CATEGORY_ORDER = [
    "Corcovado Deluxe", "Carate Deluxe", "Agujas Villa",
    "Sirena Suites", "Treehouse", "5 Elements",
]


# Market codes que NO son revenue (comps / house-use): Complimentary/Courtesy
# e In-House Guest (dim_market_code, seed estable). Se excluyen de las
# estadísticas de tarifa (ADR/Occ) porque distorsionan el ADR -- ocupan
# habitación pero no pagan (§control de tarifas). Se reconcilian aparte.
NON_REVENUE_MARKET_CODES = frozenset({"COM", "INHOUSE"})


def room_stats_rollup(records: list[dict], opening: dict[str, dict] | None = None,
                      comp_by_category: dict[str, dict] | None = None) -> dict:
    """`records`: [{'short_description','room_revenue','stay_rooms',
    'stay_persons','physical_rooms'}, ...]. Categorías fuera del catálogo
    conocido → 'Otros' (excepción visible, §10).

    `opening` (Tab 6.6, §room_stat_opening): semilla opcional por categoría
    -- {'revenue','stay_rooms','stay_persons','physical_rooms'} acumulado
    ANTES de `records` (ej. el ancla YTD editable + días reales posteriores
    ya filtrados por el caller). Sin opening, se comporta igual que siempre.

    `comp_by_category`: comps/in-house por categoría -- {cat: {'stay_rooms',
    'stay_persons','revenue'}} contados desde el XML STATISTICS (market_code
    COM/INHOUSE). Cuando se pasa, las categorías, el `overall` y el ADR/Occ se
    calculan NETOS (sin comps) y se agregan `comps_line` (lo restado) +
    `reconciled` (neto + comps = bruto, cuadra con el resto de reportes). Sin
    este arg el comportamiento es idéntico al histórico. STATISTICS no trae
    monto, así que el revenue del comp es 0: el ADR neto = revenue_bruto /
    (RN_bruto − RN_comp) -- sube, reflejando solo las habitaciones que pagan.
    Los comps se topan al bruto de su categoría (§10, nunca negativos); el
    excedente por desacuerdo entre fuentes va a `comps_unreconciled`."""
    agg: dict[str, dict] = defaultdict(lambda: {
        "revenue": 0.0, "stay_rooms": 0, "stay_persons": 0, "physical_rooms": 0,
    })
    for cat, o in (opening or {}).items():
        a = agg[cat]
        a["revenue"] += float(o.get("revenue") or 0.0)
        a["stay_rooms"] += int(o.get("stay_rooms") or 0)
        a["stay_persons"] += int(o.get("stay_persons") or 0)
        a["physical_rooms"] += int(o.get("physical_rooms") or 0)
    for r in records:
        desc = r.get("short_description") or "Otros"
        key = desc if desc in CATEGORY_ORDER else "Otros"
        a = agg[key]
        a["revenue"] += float(r.get("room_revenue") or 0.0)
        a["stay_rooms"] += int(r.get("stay_rooms") or 0)
        a["stay_persons"] += int(r.get("stay_persons") or 0)
        a["physical_rooms"] += int(r.get("physical_rooms") or 0)

    # Comps/in-house a restar por categoría, topados al bruto de esa categoría
    # (§10: nunca dejar RN neto negativo aunque las fuentes discrepen).
    comps = comp_by_category or {}
    applied: dict[str, dict] = {}
    unreconciled: dict[str, dict] = {}
    for cat, c in comps.items():
        a = agg.get(cat)
        g_rooms = int(a["stay_rooms"]) if a else 0
        g_pers = int(a["stay_persons"]) if a else 0
        g_rev = float(a["revenue"]) if a else 0.0
        req_rooms = int(c.get("stay_rooms") or 0)
        req_pers = int(c.get("stay_persons") or 0)
        applied[cat] = {
            "stay_rooms": min(req_rooms, g_rooms),
            "stay_persons": min(req_pers, g_pers),
            "revenue": min(float(c.get("revenue") or 0.0), g_rev),
        }
        if req_rooms > g_rooms or req_pers > g_pers:
            unreconciled[cat] = {"stay_rooms": max(0, req_rooms - g_rooms),
                                 "stay_persons": max(0, req_pers - g_pers)}

    def _net(cat: str) -> dict:
        a = agg.get(cat, {"revenue": 0.0, "stay_rooms": 0, "stay_persons": 0, "physical_rooms": 0})
        ap = applied.get(cat, {"stay_rooms": 0, "stay_persons": 0, "revenue": 0.0})
        return {
            "revenue": float(a["revenue"]) - ap["revenue"],
            "stay_rooms": int(a["stay_rooms"]) - ap["stay_rooms"],
            "stay_persons": int(a["stay_persons"]) - ap["stay_persons"],
            "physical_rooms": int(a["physical_rooms"]),
        }

    net_all = {cat: _net(cat) for cat in agg}
    overall_revenue = sum(v["revenue"] for v in net_all.values())
    overall_rn = sum(v["stay_rooms"] for v in net_all.values())
    overall_persons = sum(v["stay_persons"] for v in net_all.values())
    overall_available = sum(v["physical_rooms"] for v in net_all.values())
    overall_adr = round(overall_revenue / overall_rn, 2) if overall_rn else 0.0

    categories = []
    for cat in CATEGORY_ORDER:
        a = net_all.get(cat, {"revenue": 0.0, "stay_rooms": 0, "stay_persons": 0, "physical_rooms": 0})
        adr = round(a["revenue"] / a["stay_rooms"], 2) if a["stay_rooms"] else 0.0
        occ = round(a["stay_rooms"] / a["physical_rooms"], 4) if a["physical_rooms"] else 0.0
        yield_idx = round(adr / overall_adr, 2) if overall_adr else 0.0
        revenue_pct = round(a["revenue"] / overall_revenue, 4) if overall_revenue else 0.0
        categories.append({
            "category": cat,
            "revenue": round(a["revenue"], 2),
            "revenue_pct": revenue_pct,
            "stay_rooms": a["stay_rooms"],
            "stay_persons": a["stay_persons"],
            "physical_rooms": a["physical_rooms"],
            "occupancy_pct": occ,
            "adr": adr,
            "yield_index": yield_idx,
        })

    otros = net_all.get("Otros")
    otros_payload = None
    if otros is not None:
        otros_payload = {"revenue": round(otros["revenue"], 2),
                         "stay_rooms": otros["stay_rooms"], "stay_persons": otros["stay_persons"]}

    # Línea de comps/in-house (lo que se restó) -- NO entra al ADR/Occ. Y el
    # reconciliado (neto + comps) = bruto original, la cifra que cuadra con
    # todos los demás reportes (por construcción net+comps==bruto).
    comp_rooms = sum(ap["stay_rooms"] for ap in applied.values())
    comp_persons = sum(ap["stay_persons"] for ap in applied.values())
    comp_revenue = sum(ap["revenue"] for ap in applied.values())
    recon_rn = overall_rn + comp_rooms
    recon_revenue = overall_revenue + comp_revenue

    return {
        "categories": categories,
        "otros": otros_payload,
        "overall": {
            "revenue": round(overall_revenue, 2),
            "stay_rooms": overall_rn,
            "stay_persons": overall_persons,
            "physical_rooms": overall_available,
            "occupancy_pct": round(overall_rn / overall_available, 4) if overall_available else 0.0,
            "adr": overall_adr,
        },
        "comps_line": {
            "stay_rooms": comp_rooms,
            "stay_persons": comp_persons,
            "revenue": round(comp_revenue, 2),
        },
        "reconciled": {
            "revenue": round(recon_revenue, 2),
            "stay_rooms": recon_rn,
            "stay_persons": overall_persons + comp_persons,
            "physical_rooms": overall_available,
            "occupancy_pct": round(recon_rn / overall_available, 4) if overall_available else 0.0,
            "adr": round(recon_revenue / recon_rn, 2) if recon_rn else 0.0,
        },
        "comps_unreconciled": unreconciled or None,
    }


# KPI de canal (§3.2) -- agrupa los market codes de Opera en canales de
# negocio. Editable en Tab 6.8 (dim_market_code.kpi_group); este dict es
# solo el valor por default para cuando el caller no pasa `code_to_group`
# (ej. tests). Un código real sin grupo asignado cae en "Unmapped"
# (excepción visible, §10 -- nunca se descarta ni se adivina el canal).
DEFAULT_KPI_GROUPS: dict[str, list[str]] = {
    "Travel Agent": ["TA", "TAFIT", "TAGP"],
    "Direct Client": ["BAR", "COM", "DIR", "FNF", "SOC"],
    "Website": ["WEB"],
    "OTA": ["OTA"],
    "INHOUSE": ["INHOUSE"],
}
_DEFAULT_CODE_TO_GROUP: dict[str, str] = {
    code: group for group, codes in DEFAULT_KPI_GROUPS.items() for code in codes
}


def market_segment_rollup(records: list[dict], code_to_group: dict[str, str] | None = None) -> dict:
    """Tab 3.2 -- rollup de `fact_occupancy_stat` (XML STATISTICS) por
    market_code (§ visibilidad de canal/COM/In-house sobre RN y tarifa).
    `records`: [{'market_code','rooms','persons','noshow_rooms','cancel_rooms'}, ...].
    `code_to_group`: mapeo market_code -> canal KPI (Tab 6.8, dim_market_code.kpi_group);
    si no se pasa, usa DEFAULT_KPI_GROUPS. Sin market_code -> 'Sin Market Code'
    (excepción visible, §10)."""
    code_to_group = code_to_group if code_to_group is not None else _DEFAULT_CODE_TO_GROUP
    agg: dict[str, dict] = defaultdict(lambda: {
        "rooms": 0, "persons": 0, "noshow_rooms": 0, "cancel_rooms": 0,
    })
    for r in records:
        code = r.get("market_code") or "Sin Market Code"
        a = agg[code]
        a["rooms"] += int(r.get("rooms") or 0)
        a["persons"] += int(r.get("persons") or 0)
        a["noshow_rooms"] += int(r.get("noshow_rooms") or 0)
        a["cancel_rooms"] += int(r.get("cancel_rooms") or 0)

    total_rooms = sum(a["rooms"] for a in agg.values())
    rows = [{
        "market_code": code,
        "rooms": a["rooms"], "persons": a["persons"],
        "noshow_rooms": a["noshow_rooms"], "cancel_rooms": a["cancel_rooms"],
        "pct_of_total": round(a["rooms"] / total_rooms, 4) if total_rooms else 0.0,
    } for code, a in sorted(agg.items(), key=lambda kv: -kv[1]["rooms"])]

    # Rollup por KPI de canal (§3.2) -- mismos totales, agrupados por negocio.
    group_agg: dict[str, dict] = defaultdict(lambda: {
        "rooms": 0, "persons": 0, "noshow_rooms": 0, "cancel_rooms": 0, "codes": set(),
    })
    for code, a in agg.items():
        group = code_to_group.get(code, "Unmapped")
        g = group_agg[group]
        g["rooms"] += a["rooms"]; g["persons"] += a["persons"]
        g["noshow_rooms"] += a["noshow_rooms"]; g["cancel_rooms"] += a["cancel_rooms"]
        g["codes"].add(code)
    by_kpi_group = [{
        "kpi_group": group,
        "market_codes": sorted(g["codes"]),
        "rooms": g["rooms"], "persons": g["persons"],
        "noshow_rooms": g["noshow_rooms"], "cancel_rooms": g["cancel_rooms"],
        "pct_of_total": round(g["rooms"] / total_rooms, 4) if total_rooms else 0.0,
    } for group, g in sorted(group_agg.items(), key=lambda kv: -kv[1]["rooms"])]

    return {
        "rows": rows,
        "by_kpi_group": by_kpi_group,
        "total_rooms": total_rooms,
        "total_persons": sum(a["persons"] for a in agg.values()),
    }


def occupancy_rollup(records: list[dict], room_class_to_category: dict[str, str]) -> dict[str, dict]:
    """Tab 3.1 -- rollup de `fact_occupancy_stat` (XML STATISTICS, ingesta
    "oficial" de Opera Daily) por categoría, vía `room_class` (FVR/FVR2/FVR3/
    FVR4/OVR/OVR2, dim_room_category.room_class). `records`:
    [{'room_class','rooms','persons'}, ...]. Sin mapeo conocido → 'Otros'."""
    agg: dict[str, dict] = defaultdict(lambda: {"rooms": 0, "persons": 0})
    for r in records:
        cat = room_class_to_category.get(r.get("room_class") or "", "Otros")
        agg[cat]["rooms"] += int(r.get("rooms") or 0)
        agg[cat]["persons"] += int(r.get("persons") or 0)
    return dict(agg)


def opera_daily_vs_history(occupancy_records: list[dict], room_stat_records: list[dict],
                           room_class_to_category: dict[str, str],
                           revenue_daily_by_category: dict[str, float] | None = None,
                           comp_by_category: dict[str, dict] | None = None) -> dict:
    """Tab 3.1 -- Opera Daily (STATISTICS + Integrity Room Revenue, "oficial")
    vs Opera History (statroomtype, "para confirmar") por categoría.
    Diferencia visible, nunca se descarta ni se recategoriza en silencio (§10).

    `revenue_daily_by_category`: Integrity Room Revenue por categoría (vía
    sufijo de cuenta 01-06, confirmado por Bismark -- engine/revenue.py
    ::room_revenue_by_category), clave 'Otros' para lo fuera del mapa
    (Other Rooms Revenue, GL 4000 con sufijo >06). None/vacío si el día no
    tiene ingesta real de Integrity (no se fabrica).

    `comp_by_category`: comps/in-house por categoría (market_code COM/INHOUSE
    del XML STATISTICS). Cuando se pasa, RN/Pax de AMBOS lados (Daily e History)
    se muestran NETOS (comps restados y topados al bruto de cada lado, §10), y
    se agregan `comps` (línea que se restó) + `reconciled` (neto + comps =
    bruto, cuadra con las estadísticas §5.2 y Tab 2.4). Revenue no se toca:
    los comps no aportan monto. Sin el arg, comportamiento idéntico al histórico."""
    daily = occupancy_rollup(occupancy_records, room_class_to_category)
    history = room_stats_rollup(room_stat_records)
    history_by_cat = {c["category"]: c for c in history["categories"]}
    revenue_daily_by_category = revenue_daily_by_category or {}
    comps = comp_by_category or {}

    rows = []
    comp_rn_d = comp_rn_h = comp_pax_d = comp_pax_h = 0
    for cat in CATEGORY_ORDER:
        d = daily.get(cat, {"rooms": 0, "persons": 0})
        h = history_by_cat.get(cat, {"stay_rooms": 0, "stay_persons": 0, "revenue": 0.0})
        c = comps.get(cat, {"stay_rooms": 0, "stay_persons": 0})
        # Comps topados al bruto de cada lado por separado (las fuentes pueden
        # discrepar; nunca dejar neto negativo).
        cd_rn = min(int(c.get("stay_rooms") or 0), d["rooms"])
        cd_pax = min(int(c.get("stay_persons") or 0), d["persons"])
        ch_rn = min(int(c.get("stay_rooms") or 0), h["stay_rooms"])
        ch_pax = min(int(c.get("stay_persons") or 0), h["stay_persons"])
        comp_rn_d += cd_rn; comp_rn_h += ch_rn; comp_pax_d += cd_pax; comp_pax_h += ch_pax
        rn_daily = d["rooms"] - cd_rn
        rn_history = h["stay_rooms"] - ch_rn
        pax_daily = d["persons"] - cd_pax
        pax_history = h["stay_persons"] - ch_pax
        rev_daily = round(revenue_daily_by_category.get(cat, 0.0), 2)
        rev_history = round(h.get("revenue", 0.0), 2)
        rows.append({
            "category": cat,
            "rn_daily": rn_daily, "rn_history": rn_history,
            "rn_diff": rn_daily - rn_history,
            "pax_daily": pax_daily, "pax_history": pax_history,
            "pax_diff": pax_daily - pax_history,
            "revenue_daily": rev_daily, "revenue_history": rev_history,
            "revenue_diff": round(rev_daily - rev_history, 2),
        })

    revenue_history_total = round(sum(r["revenue_history"] for r in rows), 2)
    revenue_daily_total = round(sum(r["revenue_daily"] for r in rows) + revenue_daily_by_category.get("Otros", 0.0), 2)
    otros_daily = daily.get("Otros")
    net_rn_daily = sum(r["rn_daily"] for r in rows)
    net_rn_history = sum(r["rn_history"] for r in rows)
    net_pax_daily = sum(r["pax_daily"] for r in rows)
    net_pax_history = sum(r["pax_history"] for r in rows)
    return {
        "rows": rows,
        "otros_daily": otros_daily,
        "otros_revenue_daily": round(revenue_daily_by_category.get("Otros", 0.0), 2),
        "revenue": {
            "daily_total": revenue_daily_total, "history_total": revenue_history_total,
            "diff": round(revenue_daily_total - revenue_history_total, 2),
        },
        "totals": {
            "rn_daily": net_rn_daily, "rn_history": net_rn_history,
            "pax_daily": net_pax_daily, "pax_history": net_pax_history,
        },
        # Línea de comps/in-house restada (RN/Pax por lado) -- fuera del cruce.
        "comps": {
            "rn_daily": comp_rn_d, "rn_history": comp_rn_h,
            "pax_daily": comp_pax_d, "pax_history": comp_pax_h,
        },
        # Neto + comps = bruto: cuadra con las estadísticas §5.2 y Tab 2.4.
        "reconciled": {
            "rn_daily": net_rn_daily + comp_rn_d, "rn_history": net_rn_history + comp_rn_h,
            "pax_daily": net_pax_daily + comp_pax_d, "pax_history": net_pax_history + comp_pax_h,
        },
    }
