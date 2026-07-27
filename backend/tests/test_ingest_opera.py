"""Tests de los parsers de Opera contra los XML reales del 2026-06-08."""
from pathlib import Path

import pytest

from datetime import date

from app.ingest.opera import (
    find_file,
    parse_history_forecast,
    parse_revenue,
    parse_statistics,
    parse_statroomtype,
)

INP = Path(__file__).resolve().parents[2] / "goldens" / "inputs" / "2026-06-08"
pytestmark = pytest.mark.skipif(not INP.exists(), reason="faltan inputs 2026-06-08")


def test_revenue_accommodation():
    rev = INP / "COWLCR_20260608_REVENUE.xml"
    headers, details = parse_revenue(rev)
    accom = next(h for h in headers if h.tcode == "1000")
    assert accom.type == "REVENUE"
    assert accom.description.lower().startswith("accomo")
    assert accom.total == pytest.approx(5023.96, abs=0.01)
    # los detalles traen market_code para el pivote
    assert any(d.tcode == "1000" and d.market_code for d in details)


def test_statistics_totales():
    stats = parse_statistics(INP / "COWLCR_20260608_STATISTICS.xml")
    assert sum(s.rooms for s in stats) == 13
    assert sum(s.persons for s in stats) == 20


def test_history_forecast_total_vs_rooms():
    files = list(INP.glob("history_forecast*"))
    assert len(files) == 2
    hf = parse_history_forecast(files, date(2026, 6, 8))
    # el de mayor revenue = Total; el menor = Rooms Only
    assert hf["total"]["revenue"] == pytest.approx(9560.02, abs=0.01)
    assert hf["rooms"]["revenue"] == pytest.approx(5023.96, abs=0.01)
    # invariante: Rooms Only == Accommodation del REVENUE.xml
    headers, _ = parse_revenue(INP / "COWLCR_20260608_REVENUE.xml")
    accom = next(h for h in headers if h.tcode == "1000").total
    assert hf["rooms"]["revenue"] == pytest.approx(accom, abs=0.01)


def test_statistics_pivot_por_market():
    """2.4 — la agregación por market code debe reproducir el XML del 06-08."""
    stats = parse_statistics(INP / "COWLCR_20260608_STATISTICS.xml")
    by_market = {}
    for s in stats:
        agg = by_market.setdefault(s.market_code, {"rooms": 0, "persons": 0, "cancel": 0})
        agg["rooms"] += s.rooms; agg["persons"] += s.persons; agg["cancel"] += s.cancel
    assert by_market["TAGP"]["rooms"] == 6
    assert by_market["TAFIT"]["rooms"] == 5
    assert by_market["DIR"]["cancel"] == 1


def test_otb_non_room_revenue():
    """2.5 — diferencia HF full − Rooms Only = ingreso no-alojamiento (§5.6)."""
    hf = parse_history_forecast(list(INP.glob("history_forecast*")), date(2026, 6, 8))
    non_room = round(hf["total"]["revenue"] - hf["rooms"]["revenue"], 2)
    assert non_room == pytest.approx(4536.06, abs=0.01)


def test_statroomtype_dia_06_08():
    """Etapa 5: reconcilia con Rooms del motor de revenue (5023.96) y con
    OccupancyStat del día (RN=13, PAX=20). Ese día solo 4/6 categorías
    reportan physical_rooms (22 de 30) — dato real, no se rellena."""
    recs = parse_statroomtype(INP / "statroomtype_22961647.XML")
    day = [r for r in recs if r.business_date == date(2026, 6, 8)]
    assert len(day) == 4
    assert sum(r.room_revenue for r in day) == pytest.approx(5023.96, abs=0.01)
    assert sum(r.stay_rooms for r in day) == 13
    assert sum(r.stay_persons for r in day) == 20
    assert sum(r.physical_rooms for r in day) == 22
    descs = {r.short_description for r in day}
    assert descs == {"Agujas Villa", "Sirena Suites", "Treehouse", "5 Elements"}


def test_find_file():
    files = [str(p) for p in INP.iterdir()]
    assert find_file(files, r"REVENUE.*\.xml")
    assert find_file(files, r"STATISTICS.*\.xml")


def test_history_forecast_busca_el_dia_correcto(tmp_path):
    """Bug real: el archivo trae el AÑO COMPLETO (365 <G_CONSIDERED_DATE>, uno
    por día) -- antes se tomaba siempre la primera fila (1-ene) sin importar
    qué día se auditaba, haciendo el OTB-vs-Revenue incomparable para
    cualquier otro día (2.5, reportado por Bismark)."""
    xml = """<?xml version="1.0"?>
    <ROOT><G_HOTEL><G_CONSIDERED_DATE>
      <CONSIDERED_DATE>01-JAN-26</CONSIDERED_DATE>
      <REVENUE>111.11</REVENUE><NO_ROOMS>1</NO_ROOMS><NO_PERSONS>1</NO_PERSONS>
      <INVENTORY_ROOMS>30</INVENTORY_ROOMS><CF_AVERAGE_ROOM_RATE>1</CF_AVERAGE_ROOM_RATE>
      <CF_OCCUPANCY>1</CF_OCCUPANCY>
    </G_CONSIDERED_DATE><G_CONSIDERED_DATE>
      <CONSIDERED_DATE>01-JUL-26</CONSIDERED_DATE>
      <REVENUE>222.22</REVENUE><NO_ROOMS>2</NO_ROOMS><NO_PERSONS>2</NO_PERSONS>
      <INVENTORY_ROOMS>30</INVENTORY_ROOMS><CF_AVERAGE_ROOM_RATE>2</CF_AVERAGE_ROOM_RATE>
      <CF_OCCUPANCY>2</CF_OCCUPANCY>
    </G_CONSIDERED_DATE></G_HOTEL></ROOT>"""
    f = tmp_path / "history_forecast.xml"
    f.write_text(xml)

    hf_jan = parse_history_forecast([f], date(2026, 1, 1))
    assert hf_jan["total"]["revenue"] == pytest.approx(111.11)

    hf_jul = parse_history_forecast([f], date(2026, 7, 1))
    assert hf_jul["total"]["revenue"] == pytest.approx(222.22)


def test_classify_no_confunde_historyforecast_con_revenue(tmp_path):
    """Regresión del bug del 2026-07-04: el archivo
    'OPERA_HistoryForecast_Total Revenue.XML' comparte la palabra 'Revenue' con
    el REVENUE real de Opera y ganaba por orden de `iterdir()` en Linux (Railway),
    dejando Opera en 0 transacciones. `_classify` debe elegir SIEMPRE el REVENUE
    real, sin importar el orden en que el filesystem liste los archivos."""
    from app.services.ingest_service import _classify, _is_forecast

    (tmp_path / "OPERA_GEN_XMLBO_REVENUE_2026-07-04.xml").write_text(
        '<?xml version="1.0"?><revenue date="2026-07-04">'
        "<transaction_total transaction_type=\"REVENUE\">"
        "<transaction_code>1000</transaction_code><description>Accom</description>"
        "<total_amount>100</total_amount></transaction_total></revenue>"
    )
    (tmp_path / "OPERA_HistoryForecast_Total Revenue.XML").write_text(
        '<?xml version="1.0"?><HISTORY_FORECAST></HISTORY_FORECAST>'
    )

    cls = _classify(tmp_path)
    assert Path(cls["revenue"]).name == "OPERA_GEN_XMLBO_REVENUE_2026-07-04.xml"
    headers, _ = parse_revenue(cls["revenue"])
    assert len(headers) == 1  # el forecast daría 0

    assert _is_forecast("OPERA_HistoryForecast_Total Revenue.XML")
    assert _is_forecast("history_forecast (Total + Rooms Only).XML")
    assert not _is_forecast("OPERA_GEN_XMLBO_REVENUE_2026-07-04.xml")


def test_classify_nombres_automaticos_opera(tmp_path):
    """Los nombres AUTOMÁTICOS de Opera (OPERA_StatisticsRoomType,
    OPERA_HistoryForecast_Default/_TotalRevenue) deben clasificar bien y sin
    colisiones — 'StatisticsRoomType' contiene 'STATISTICS' y antes le ganaba al
    archivo de ocupación real según el orden del filesystem; el forecast
    'HistoryForecast' (sin guion bajo) no matcheaba la detección vieja de OTB."""
    from app.services.ingest_service import _classify

    names = [
        "OPERA_GEN_XMLBO_REVENUE_2026-07-04.xml",
        "OPERA_GEN_XMLBO_STATISTICS_2026-07-04.xml",
        "OPERA_StatisticsRoomType_2026-07-04.xml",
        "OPERA_HistoryForecast_Default_2026-07-04.xml",
        "OPERA_HistoryForecast_TotalRevenue_2026-07-04.xml",
        "OPERA_GEN_XMLBO_BILLS_2026-07-04.xml",
        "OPERA_GEN_XMLBO_CUSTOMER_2026-07-04.xml",
    ]
    # el orden importa para reproducir el bug: room-type ANTES que statistics
    for f in names:
        (tmp_path / f).write_text('<?xml version="1.0"?><root/>')

    cls = _classify(tmp_path)
    assert Path(cls["revenue"]).name == "OPERA_GEN_XMLBO_REVENUE_2026-07-04.xml"
    assert Path(cls["statistics"]).name == "OPERA_GEN_XMLBO_STATISTICS_2026-07-04.xml"
    assert Path(cls["room_stats"]).name == "OPERA_StatisticsRoomType_2026-07-04.xml"
    assert cls["statistics"] != cls["room_stats"]  # sin colisión
    assert sorted(Path(x).name for x in cls["history_forecast"]) == [
        "OPERA_HistoryForecast_Default_2026-07-04.xml",
        "OPERA_HistoryForecast_TotalRevenue_2026-07-04.xml",
    ]
    assert Path(cls["bills"]).name == "OPERA_GEN_XMLBO_BILLS_2026-07-04.xml"
    assert Path(cls["customer"]).name == "OPERA_GEN_XMLBO_CUSTOMER_2026-07-04.xml"


def test_parse_trial_balance(tmp_path):
    """Trial Balance: líneas por TCode (neto=debito+credito, credito negativo) +
    saldos por ledger (apertura=YEST, cierre=REP, apertura+mov=cierre)."""
    from app.ingest.opera import parse_trial_balance

    xml = """<?xml version="1.0"?>
    <TRIAL_BALANCE>
      <LIST_G_TRX_TYPE><G_TRX_TYPE>
        <TRX_TYPE>REVENUE</TRX_TYPE><TRX_TYPE_DESCRIPTION>Revenue</TRX_TYPE_DESCRIPTION>
        <LIST_G_TRX_CODE>
          <G_TRX_CODE><TRX_CODE>1000</TRX_CODE><DESCRIPTION>Accom</DESCRIPTION>
            <TB_AMOUNT>1699.64</TB_AMOUNT><NET_AMOUNT>1699.64</NET_AMOUNT>
            <GUEST_LED_DEBIT>1699.64</GUEST_LED_DEBIT><GUEST_LED_CREDIT></GUEST_LED_CREDIT>
            <AR_LED_DEBIT>0</AR_LED_DEBIT><DEP_LED_DEBIT>0</DEP_LED_DEBIT></G_TRX_CODE>
          <G_TRX_CODE><TRX_CODE>3726</TRX_CODE><DESCRIPTION>Payment</DESCRIPTION>
            <TB_AMOUNT>-3611.81</TB_AMOUNT><NET_AMOUNT>-3611.81</NET_AMOUNT>
            <DEP_LED_DEBIT></DEP_LED_DEBIT><DEP_LED_CREDIT>-3611.81</DEP_LED_CREDIT></G_TRX_CODE>
        </LIST_G_TRX_CODE>
      </G_TRX_TYPE></LIST_G_TRX_TYPE>
      <CF_GUEST_LED_YEST>5465.85</CF_GUEST_LED_YEST>
      <CS_GUEST_LED_DEBIT_REP>3431.1</CS_GUEST_LED_DEBIT_REP>
      <CS_GUEST_LED_CREDIT_REP>0</CS_GUEST_LED_CREDIT_REP>
      <CF_GUEST_LED_REP>8896.95</CF_GUEST_LED_REP>
      <CF_DEPOSIT_LED_YEST>-263335.89</CF_DEPOSIT_LED_YEST>
      <CS_DEPOSIT_LED_DEBIT_REP>0</CS_DEPOSIT_LED_DEBIT_REP>
      <CS_DEPOSIT_LED_CREDIT_REP>-3611.81</CS_DEPOSIT_LED_CREDIT_REP>
      <CF_DEPOSIT_LED_REP>-266947.7</CF_DEPOSIT_LED_REP>
      <CF_AR_LED_YEST>0</CF_AR_LED_YEST><CF_AR_LED_REP>0</CF_AR_LED_REP>
      <CS_AR_LED_DEBIT_REP>0</CS_AR_LED_DEBIT_REP><CS_AR_LED_CREDIT_REP>0</CS_AR_LED_CREDIT_REP>
      <CF_PACKAGE_LED_YEST>0</CF_PACKAGE_LED_YEST><CF_PACKAGE_LED_REP>0</CF_PACKAGE_LED_REP>
      <CS_PACKAGE_LED_DEBIT_REP>0</CS_PACKAGE_LED_DEBIT_REP><CS_PACKAGE_LED_CREDIT_REP>0</CS_PACKAGE_LED_CREDIT_REP>
    </TRIAL_BALANCE>"""
    f = tmp_path / "OPERA_TrialBalance_2026-07-04.XML"
    f.write_text(xml)
    lines, bal = parse_trial_balance(f)

    assert len(lines) == 2
    accom = next(l for l in lines if l["tcode"] == "1000")
    assert accom["guest_ledger"] == pytest.approx(1699.64)
    pay = next(l for l in lines if l["tcode"] == "3726")
    assert pay["deposit_ledger"] == pytest.approx(-3611.81)  # credito negativo

    assert bal["guest"]["opening"] == pytest.approx(5465.85)
    assert bal["guest"]["closing"] == pytest.approx(8896.95)
    # apertura + (debito+credito) = cierre
    for lg in ("guest", "deposit", "ar"):
        mov = bal[lg]["debit"] + bal[lg]["credit"]
        assert round(bal[lg]["opening"] + mov, 2) == pytest.approx(bal[lg]["closing"])


def test_parse_city_ledger(tmp_path):
    """City Ledger: facturas a empresas/agencias con cliente, N° factura y reserva."""
    from app.ingest.opera import parse_city_ledger

    xml = """<?xml version="1.0"?>
    <city_ledger hotel_code="COWLCR" date="2026-07-03">
      <transaction trx_code="3773" transaction_type="INVOICE">
        <bill_no>2575</bill_no><invoice_no>391</invoice_no><amount>15681.12</amount>
        <account_info customer_internal_id="22985200">
          <account_name>TRAVEL EXCELLENCE S.A</account_name><account_number>003</account_number>
        </account_info>
        <reservation_info><confirmation_no>590285622</confirmation_no>
          <arrival_date>2026-06-29</arrival_date><departure_date>2026-07-03</departure_date>
          <guest_name>De Haan, Sjoerd</guest_name></reservation_info>
      </transaction>
    </city_ledger>"""
    f = tmp_path / "OPERA_GEN_XMLBO_CITYLEDGER_2026-07-03.xml"
    f.write_text(xml)
    inv = parse_city_ledger(f)
    assert len(inv) == 1
    assert inv[0]["invoice_no"] == "391"
    assert inv[0]["account_name"] == "TRAVEL EXCELLENCE S.A"
    assert inv[0]["amount"] == pytest.approx(15681.12)
    assert inv[0]["guest_name"] == "De Haan, Sjoerd"


def test_classify_trial_balance_y_city_ledger(tmp_path):
    """OPERA_TrialBalance y OPERA_GEN_XMLBO_CITYLEDGER se clasifican en su categoría,
    sin robarle el match a REVENUE/CUSTOMER/etc."""
    from app.services.ingest_service import _classify

    for n in ["OPERA_GEN_XMLBO_REVENUE_2026-07-04.xml",
              "OPERA_GEN_XMLBO_CUSTOMER_2026-07-04.xml",
              "OPERA_TrialBalance_2026-07-04.XML",
              "OPERA_GEN_XMLBO_CITYLEDGER_2026-07-04.xml"]:
        (tmp_path / n).write_text('<?xml version="1.0"?><root/>')
    cls = _classify(tmp_path)
    assert Path(cls["trial_balance"]).name == "OPERA_TrialBalance_2026-07-04.XML"
    assert Path(cls["city_ledger"]).name == "OPERA_GEN_XMLBO_CITYLEDGER_2026-07-04.xml"
    assert Path(cls["revenue"]).name == "OPERA_GEN_XMLBO_REVENUE_2026-07-04.xml"
    assert Path(cls["customer"]).name == "OPERA_GEN_XMLBO_CUSTOMER_2026-07-04.xml"


def test_history_forecast_monthly(tmp_path):
    """Agregación mensual del history_forecast: suma REVENUE por mes, separa
    History vs Forecast, y distingue Full (mayor revenue anual) de Only Rooms."""
    from app.ingest.opera import history_forecast_monthly

    def _wb(hist_rev, fcst_rev):
        return f"""<?xml version="1.0"?><HISTORY_FORECAST><LIST_G_GPAGEID><G_GPAGEID>
        <LIST_G_REC_TYPE>
          <G_REC_TYPE><REC_TYPE_DESC>History</REC_TYPE_DESC><LIST_G_CONSIDERED_DATE>
            <G_CONSIDERED_DATE><CONSIDERED_DATE>15-JAN-26</CONSIDERED_DATE>
              <REVENUE>{hist_rev}</REVENUE><NO_ROOMS>10</NO_ROOMS><NO_PERSONS>20</NO_PERSONS>
              <INVENTORY_ROOMS>30</INVENTORY_ROOMS></G_CONSIDERED_DATE>
          </LIST_G_CONSIDERED_DATE></G_REC_TYPE>
          <G_REC_TYPE><REC_TYPE_DESC>Forecast</REC_TYPE_DESC><LIST_G_CONSIDERED_DATE>
            <G_CONSIDERED_DATE><CONSIDERED_DATE>20-JAN-26</CONSIDERED_DATE>
              <REVENUE>{fcst_rev}</REVENUE><NO_ROOMS>5</NO_ROOMS><NO_PERSONS>8</NO_PERSONS>
              <INVENTORY_ROOMS>30</INVENTORY_ROOMS></G_CONSIDERED_DATE>
          </LIST_G_CONSIDERED_DATE></G_REC_TYPE>
        </LIST_G_REC_TYPE></G_GPAGEID></LIST_G_GPAGEID></HISTORY_FORECAST>"""

    full = tmp_path / "history_forecast Full Revenue.XML"
    rooms = tmp_path / "history_forecast Only Rooms.XML"
    full.write_text(_wb(1000, 500))    # Full: 1500 anual
    rooms.write_text(_wb(600, 300))    # Rooms Only: 900 anual (menor -> Rooms)

    m = history_forecast_monthly([rooms, full])  # orden mezclado a propósito
    # La clave es (year, month): el forecast puede abarcar >1 año (soporte
    # multi-año de On The Books). Las fechas del fixture son de ene-2026.
    jan = m[(2026, 1)]
    assert jan["total_revenue"] == pytest.approx(1500.0)          # Full
    assert jan["rooms_only_revenue"] == pytest.approx(900.0)      # Only Rooms
    assert jan["rooms_only_history"] == pytest.approx(600.0)
    assert jan["rooms_only_forecast"] == pytest.approx(300.0)     # -> Sales on Property
    assert jan["rooms_occ"] == pytest.approx(15.0)                # 10 + 5 (del Full)
    assert jan["guests"] == pytest.approx(28.0)
    assert jan["rooms_avail"] == pytest.approx(60.0)
