"""Export (etapa 8): humo — que build_daily_excel/build_daily_pdf no truenen
con datos representativos, incluyendo los dos casos que ya rompieron una vez:
valores None en filas de reconciliación (Excel) y texto con acentos/tildes
dinámico como el `reason` del gate (PDF, fuente core sin soporte Unicode)."""
from app.export.excel import build_daily_excel
from app.export.pdf import build_daily_pdf

REVENUE = {
    "kpis": {"pax": 20, "rooms_occupied": 13, "available_rooms": 22,
             "adr": 386.46, "occupancy_pct": 0.5909},
    "centers": [
        {"center": "Rooms", "today_actual": 5023.96, "today_budget": 0.0,
         "today_var": 5023.96, "mtd_actual": 5023.96, "mtd_budget": 0.0},
        {"center": "F&B", "today_actual": 2005.32, "today_budget": 0.0,
         "today_var": 2005.32, "mtd_actual": 2005.32, "mtd_budget": 0.0},
    ],
    "grand_total": {"today_actual": 9560.02, "today_budget": 0.0,
                    "mtd_actual": 9560.02, "mtd_budget": 0.0},
    "room_categories": [
        {"category": "Agujas Villa", "revenue": 972.29, "stay_rooms": 4,
         "stay_persons": 7, "physical_rooms": 4, "occupancy_pct": 1.0,
         "adr": 243.07, "yield_index": 0.63},
    ],
    "otros": [{"cuenta": "9999-0000", "nombre": "Cuenta rara", "amount": 12.5}],
}
CASH = {
    "today": {
        "real_cash": 317.87, "non_cash": 0.0, "cash_relevant_total": 317.87,
        "bank_only_total": 309.96,
        "by_bucket": {"Cash": 7.91, "BAC Cards POS": 309.96},
        "by_bank": {"CASH": 7.91, "BAC": 309.96},
        "by_brand": {"Cash": 7.91, "MasterCard": 309.96},
        "by_channel": {"Cash": 7.91, "POS": 309.96},
    },
    "unmapped_today": [{"tcode": "9999", "description": "Sin mapear", "opera_total": 50.0}],
}
AUDIT = {
    "status": "abierto",
    "gate": {"gate_hard": False, "allowed": True,
            "reason": "Gate suave: se libera con 2 excepción(es) abierta(s).", "open_issues": 2},
    "kpis": {"ok": 33, "discrepancia": 2, "faltante": 0, "interno": 1},
    "rows": [
        {"tcode": "1000", "description": "Accommodation", "type": "REVENUE",
         "opera": 5023.96, "integrity": 5023.96, "diferencia": 0.0, "estado": "OK"},
        # fila con lados faltantes (None) — el caso que rompió number_format en Excel
        {"tcode": "9999", "description": "Falta en Integrity", "type": "REVENUE",
         "opera": 100.0, "integrity": None, "diferencia": None, "estado": "FALTA EN INTEGRITY"},
    ],
}


def test_build_daily_excel_no_truena():
    content = build_daily_excel(REVENUE, CASH, AUDIT, "2026-06-08", "COWLCR")
    assert content[:2] == b"PK"  # firma de un .xlsx (zip)
    assert len(content) > 1000


def test_build_daily_pdf_no_truena_con_acentos_dinamicos():
    content = build_daily_pdf(REVENUE, CASH, AUDIT, "2026-06-08", "COWLCR")
    assert content[:5] == b"%PDF-"
    assert len(content) > 500
