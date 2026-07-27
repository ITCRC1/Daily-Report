"""Export to an executive PDF (one page) -- stage 8. Meant to be sent to owners.

Pure function: receives the payloads ALREADY computed (same as Excel/the pages)
and builds the PDF. Doesn't repeat any calculations.
"""
from __future__ import annotations

import unicodedata

from fpdf import FPDF
from fpdf.fonts import FontFace

DARK = (45, 58, 92)      # #2D3A5C
GREEN = (26, 127, 75)    # #1A7F4B
AMBER = (176, 122, 0)
RED = (192, 57, 43)
GREY = (100, 100, 100)


def _safe(text) -> str:
    """Strips accents from any dynamic text (gate.reason, account names,
    etc.) before sending it to fpdf2 -- the core 'helvetica' font doesn't
    reliably support characters outside plain ASCII."""
    if text is None:
        return ""
    text = str(text)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _money(v) -> str:
    if v is None:
        return "-"
    return f"${v:,.2f}"


def build_daily_pdf(revenue: dict, cash: dict, audit: dict,
                    business_date: str, property_code: str) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # --- Header ---
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 9, "SCP Corcovado Wilderness Lodge", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, f"Daily Executive Report - {business_date} ({property_code})",
             new_x="LMARGIN", new_y="NEXT")
    status = audit.get("status") or "abierto"
    gate_ok = audit["gate"]["allowed"]
    status_color = GREEN if status == "cerrado" else AMBER
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*status_color)
    pdf.cell(0, 6, f"Status: {'CLOSED (released to owners)' if status == 'cerrado' else 'OPEN'}"
             + ("" if gate_ok else "  [ALERT] gate blocked - requires override"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # --- Main KPIs (3x2 grid) ---
    kpis = [
        ("Revenue Total (Today)", _money(revenue["grand_total"]["today_actual"]), GREEN),
        ("Real Cash Received", _money(cash["today"]["real_cash"]), (13, 107, 114)),
        ("ADR", _money(revenue["kpis"]["adr"]), DARK),
        ("Occupancy", f"{revenue['kpis']['occupancy_pct'] * 100:.1f}%", DARK),
        ("Open Discrepancies", str(audit["kpis"]["discrepancia"]),
         RED if audit["kpis"]["discrepancia"] else GREEN),
        ("Rooms Occupied / Available",
         f"{revenue['kpis']['rooms_occupied']} / {revenue['kpis']['available_rooms']}", DARK),
    ]
    col_w = 63
    x0 = pdf.get_x()
    for i, (label, value, color) in enumerate(kpis):
        col = i % 3
        if col == 0 and i > 0:
            pdf.ln(20)
        pdf.set_xy(x0 + col * col_w, pdf.get_y())
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(*color)
        pdf.cell(col_w - 4, 8, value, new_x="LEFT", new_y="NEXT")
        pdf.set_xy(x0 + col * col_w, pdf.get_y())
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(col_w - 4, 4, label)
    pdf.ln(14)

    # --- Revenue by center (Today) ---
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 7, "Revenue by Center (Today)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    headings_style = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=DARK)
    with pdf.table(headings_style=headings_style, col_widths=(45, 25, 25, 25),
                  text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT")) as table:
        row = table.row()
        for h in ("Center", "Today Actual", "Today Budget", "Var $"):
            row.cell(h)
        for c in revenue["centers"]:
            row = table.row()
            row.cell(_safe(c["center"]))
            row.cell(_money(c["today_actual"]))
            row.cell(_money(c["today_budget"]))
            row.cell(_money(c["today_var"]))
        row = table.row(style=FontFace(emphasis="BOLD", fill_color=(230, 230, 230)))
        row.cell("GRAND TOTAL")
        row.cell(_money(revenue["grand_total"]["today_actual"]))
        row.cell(_money(revenue["grand_total"]["today_budget"]))
        row.cell(_money(revenue["grand_total"]["today_actual"]))
    pdf.ln(3)

    # --- Cash summary ---
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 7, "Cash - By Bucket (Today)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9)
    with pdf.table(headings_style=headings_style, col_widths=(45, 25),
                  text_align=("LEFT", "RIGHT")) as table:
        row = table.row()
        row.cell("Bucket"); row.cell("Amount")
        for k, v in sorted(cash["today"]["by_bucket"].items(), key=lambda kv: -kv[1]):
            row = table.row()
            row.cell(_safe(k)); row.cell(_money(v))

    # --- Footer ---
    pdf.set_y(-15)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, _safe(
        f"Generated by DAILY-OPS. Gate: {audit['gate']['reason']}"
    ), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
