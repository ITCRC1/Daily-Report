# -*- coding: utf-8 -*-
"""Hoja 3 del reporte a dueños — History and Forecast.

Cuida las decisiones que el owner tomó el 2026-11-06 sobre maqueta en mano, que
son justo las que se pierden sin querer al tocar el reporte:

  · el corte es el día del Daily, no la marca History/Forecast del XML de Opera
  · el Occ.% va contra las unidades VIGENTES del hotel, no contra la
    disponibilidad que reporta Opera (que descuenta las fuera de servicio)
  · el ADR de un subtotal es ponderado, no el promedio de los ADR diarios
  · "Arr. Rooms" no va en la hoja
"""
from datetime import date

import pytest

from app.engine.history_forecast import FORECAST, HISTORY, armar_hoja

# Los dos tramos reales de CWL (ver engine/inventory.py).
TRAMOS = [(date(2000, 1, 1), 30), (date(2027, 2, 1), 33)]


def dias(anio, mes, ultimo):
    return [date(anio, mes, n) for n in range(1, ultimo + 1)]


def dato(occ=0.0, pax=0.0, revenue=0.0, rooms_revenue=0.0, adr=0.0, loaded=True):
    return {"occ": occ, "pax": pax, "revenue": revenue,
            "rooms_revenue": rooms_revenue, "adr": adr, "loaded": loaded}


NOV = dias(2026, 11, 30)
CORTE = date(2026, 11, 5)
HIST_NOV = {date(2026, 11, n): dato(occ=10, pax=18, revenue=8000,
                                    rooms_revenue=6000, adr=600) for n in range(1, 6)}
FCST_NOV = {date(2026, 11, n): dato(occ=12, pax=20, revenue=9000,
                                    rooms_revenue=7200, adr=600) for n in range(6, 31)}


# ---------------------------------------------------------------------------
# El corte
# ---------------------------------------------------------------------------

def test_el_corte_es_el_dia_del_daily_y_el_forecast_arranca_al_siguiente():
    """Owner: «si el daily es del día 5, entonces forecast empieza en día 6».

    El corte NO sale de la marca History/Forecast del XML de Opera: si se
    tomara de ahí, un snapshot de Opera más viejo o más nuevo que el Daily
    movería el límite y la hoja contaría días dos veces o ninguna.
    """
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    bloques = {f["day"]: f["block"] for f in h["rows"]}
    assert all(bloques[n] == HISTORY for n in range(1, 6))
    assert all(bloques[n] == FORECAST for n in range(6, 31))
    assert h["totals"]["history"]["days"] == 5
    assert h["totals"]["forecast"]["days"] == 25


def test_el_mes_entero_esta_en_la_hoja_sin_huecos():
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    assert [f["day"] for f in h["rows"]] == list(range(1, 31))


def test_un_daily_del_ultimo_dia_deja_el_forecast_vacio():
    """Cerrado el mes no queda nada por pronosticar, y la hoja no se rompe."""
    h = armar_hoja(NOV, date(2026, 11, 30), HIST_NOV, {}, TRAMOS)
    assert h["totals"]["forecast"]["days"] == 0
    assert h["totals"]["forecast"]["occ_pct"] == 0.0
    assert all(f["block"] == HISTORY for f in h["rows"])


# ---------------------------------------------------------------------------
# Occ.% contra las unidades vigentes
# ---------------------------------------------------------------------------

def test_el_occ_pct_va_contra_las_unidades_del_hotel():
    """10 noches sobre 30 unidades = 33,33%, en los DOS bloques.

    Si se usara el INVENTORY_ROOMS de Opera (que baja a 23 o 28 cuando hay
    habitaciones fuera de servicio) la misma columna se leería con dos
    criterios distintos según el día, y parece un error de la hoja.
    """
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    dia1 = next(f for f in h["rows"] if f["day"] == 1)
    dia6 = next(f for f in h["rows"] if f["day"] == 6)
    assert dia1["units"] == 30 and dia1["occ_pct"] == pytest.approx(10 / 30, abs=1e-4)
    assert dia6["units"] == 30 and dia6["occ_pct"] == pytest.approx(12 / 30, abs=1e-4)


def test_en_febrero_2027_el_divisor_ya_es_33():
    """Entra SH07 el 2027-02-01: la hoja de febrero divide entre 33 sola."""
    feb = dias(2027, 2, 28)
    hist = {date(2027, 2, n): dato(occ=11) for n in range(1, 4)}
    h = armar_hoja(feb, date(2027, 2, 3), hist, {}, TRAMOS)
    dia1 = next(f for f in h["rows"] if f["day"] == 1)
    assert dia1["units"] == 33
    assert dia1["occ_pct"] == pytest.approx(11 / 33, abs=1e-4)


def test_el_occ_pct_del_subtotal_suma_las_noches_dia_a_dia():
    """5 días de History = 150 noches disponibles (5 x 30), no 30."""
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    hist = h["totals"]["history"]
    assert hist["available"] == 150
    assert hist["occ"] == 50
    assert hist["occ_pct"] == pytest.approx(50 / 150, abs=1e-4)


def test_un_mes_que_cruza_el_cambio_de_inventario_suma_los_dos_tramos():
    """Enero 2027: 31 días a 30 unidades. Febrero: 28 a 33. El total del mes
    no sale de ninguna multiplicación única."""
    ene = armar_hoja(dias(2027, 1, 31), date(2027, 1, 31),
                     {d: dato(occ=1) for d in dias(2027, 1, 31)}, {}, TRAMOS)
    feb = armar_hoja(dias(2027, 2, 28), date(2027, 2, 28),
                     {d: dato(occ=1) for d in dias(2027, 2, 28)}, {}, TRAMOS)
    assert ene["totals"]["month"]["available"] == 930
    assert feb["totals"]["month"]["available"] == 924


# ---------------------------------------------------------------------------
# El ADR del subtotal
# ---------------------------------------------------------------------------

def test_el_adr_del_subtotal_es_ponderado_no_el_promedio_de_los_adr():
    """Un día con 1 noche a $1.000 y otro con 9 a $100 dan $190, no $550.

    El promedio de los ADR diarios le daría a un día casi vacío el mismo peso
    que a uno lleno, y el ADR de la hoja no cuadraría con el revenue.
    """
    d1, d2 = date(2026, 11, 1), date(2026, 11, 2)
    hist = {
        d1: dato(occ=1, rooms_revenue=1000, adr=1000),
        d2: dato(occ=9, rooms_revenue=900, adr=100),
    }
    h = armar_hoja([d1, d2], d2, hist, {}, TRAMOS)
    assert h["totals"]["history"]["adr"] == pytest.approx(190.0, abs=0.01)
    assert h["totals"]["history"]["adr"] != pytest.approx(550.0, abs=0.01)


def test_sin_noches_vendidas_el_adr_es_cero_y_no_revienta():
    d = date(2026, 11, 1)
    h = armar_hoja([d], d, {d: dato(occ=0, rooms_revenue=0)}, {}, TRAMOS)
    assert h["totals"]["month"]["adr"] == 0.0


# ---------------------------------------------------------------------------
# Los totales cierran
# ---------------------------------------------------------------------------

def test_history_mas_forecast_da_el_total_del_mes():
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    t = h["totals"]
    for campo in ("occ", "revenue", "rooms_revenue", "pax", "available", "days"):
        assert t["month"][campo] == pytest.approx(
            t["history"][campo] + t["forecast"][campo], abs=0.01), campo


def test_el_total_del_mes_cuenta_los_30_dias():
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    assert h["totals"]["month"]["days"] == 30
    assert h["totals"]["month"]["available"] == 900


# ---------------------------------------------------------------------------
# Lo que NO va, y lo que se marca
# ---------------------------------------------------------------------------

def test_la_hoja_tiene_las_seis_columnas_del_owner_y_no_lleva_arr_rooms():
    """Owner: «Arr. Rooms no importa, no las pongas en ninguno, quitalo del
    todo». El Daily no registra llegadas: ponerlas obligaría a sacarlas de
    Opera en una hoja que dice que el History viene del Daily."""
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    assert h["columns"] == ["Date", "Total Occ", "Occ.%", "Total Revenue",
                            "ADR Rooms Only", "PAX"]
    assert not any("arr" in k.lower() for k in h["rows"][0])


def test_un_dia_del_history_sin_cargar_queda_marcado():
    """Un cero que no se distingue de un cero real es un dato que nadie
    cuestiona. El día sin datos sale en cero PERO marcado."""
    falta = date(2026, 11, 3)
    hist = {d: v for d, v in HIST_NOV.items() if d != falta}
    h = armar_hoja(NOV, CORTE, hist, FCST_NOV, TRAMOS)
    fila = next(f for f in h["rows"] if f["day"] == 3)
    assert fila["loaded"] is False
    assert fila["revenue"] == 0.0
    assert all(f["loaded"] for f in h["rows"] if f["day"] in (1, 2, 4, 5))


def test_los_dias_de_forecast_no_se_marcan_como_sin_cargar():
    """El Forecast no es algo que falte cargar: es lo que todavía no pasó."""
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    assert all(f["loaded"] for f in h["rows"] if f["block"] == FORECAST)


# ---------------------------------------------------------------------------
# La ingesta que alimenta el bloque Forecast
# ---------------------------------------------------------------------------
# Viven acá y no en test_ingest_opera.py porque ese archivo entero se saltea
# cuando faltan los XML golden del 2026-06-08 (`pytestmark` de módulo), y estas
# dos se arman su propio XML en tmp_path: no tienen por qué saltearse.

def test_history_forecast_daily_lee_los_dos_archivos(tmp_path):
    """Día por día: revenue y pax del Full, pero la TARIFA del Only Rooms.

    Antes esta función leía sólo el archivo Full y descartaba el otro entero,
    y de los campos del día guardaba únicamente NO_ROOMS e INVENTORY_ROOMS.
    Con eso el bloque Forecast de la hoja History and Forecast (hoja 3 del
    reporte a dueños) no tenía ni revenue, ni PAX, ni ADR -- y el ADR del
    revenue TOTAL no es una tarifa de habitación: ahí está la diferencia entre
    $1.017 y $1.400 la noche.
    """
    from app.ingest.opera import history_forecast_daily

    def _wb(rev, adr):
        return f"""<?xml version="1.0"?><HISTORY_FORECAST><LIST_G_GPAGEID><G_GPAGEID>
        <LIST_G_REC_TYPE>
          <G_REC_TYPE><REC_TYPE_DESC>Forecast</REC_TYPE_DESC><LIST_G_CONSIDERED_DATE>
            <G_CONSIDERED_DATE><CONSIDERED_DATE>20-JAN-26</CONSIDERED_DATE>
              <REVENUE>{rev}</REVENUE><NO_ROOMS>6</NO_ROOMS><NO_PERSONS>11</NO_PERSONS>
              <INVENTORY_ROOMS>28</INVENTORY_ROOMS>
              <CF_AVERAGE_ROOM_RATE>{adr}</CF_AVERAGE_ROOM_RATE></G_CONSIDERED_DATE>
          </LIST_G_CONSIDERED_DATE></G_REC_TYPE>
        </LIST_G_REC_TYPE></G_GPAGEID></LIST_G_GPAGEID></HISTORY_FORECAST>"""

    full = tmp_path / "history_forecast Full Revenue.XML"
    rooms = tmp_path / "history_forecast Only Rooms.XML"
    full.write_text(_wb(9000, 1500))   # Full: 9000 anual
    rooms.write_text(_wb(7200, 1200))  # Only Rooms: 7200 anual (menor -> Rooms)

    d = history_forecast_daily([rooms, full])["2026-01-20"]   # orden mezclado
    assert d["revenue"] == pytest.approx(9000.0)        # Full
    assert d["persons"] == pytest.approx(11.0)          # Full
    assert d["rooms_sold"] == pytest.approx(6.0)        # Full
    assert d["rooms_revenue"] == pytest.approx(7200.0)  # Only Rooms
    assert d["adr"] == pytest.approx(1200.0)            # Only Rooms, NO el 1500 del Full


def test_history_forecast_daily_conserva_el_inventory_rooms_de_opera(tmp_path):
    """`rooms_avail` sigue siendo el INVENTORY_ROOMS de Opera porque el heatmap
    (Tab 8.3) lo usa -- pero ⚠️ el Occ.% del reporte NO lo usa: va contra las
    unidades vigentes del hotel (30, aquí Opera dice 28 porque descuenta las
    fuera de servicio). Si alguien lo enchufa al Occ.%, la misma columna pasa
    a leerse con dos criterios según el día."""
    from app.ingest.opera import history_forecast_daily

    xml = tmp_path / "history_forecast.xml"
    xml.write_text("""<?xml version="1.0"?><HISTORY_FORECAST><LIST_G_GPAGEID><G_GPAGEID>
      <LIST_G_REC_TYPE><G_REC_TYPE><LIST_G_CONSIDERED_DATE>
        <G_CONSIDERED_DATE><CONSIDERED_DATE>20-JAN-26</CONSIDERED_DATE>
          <REVENUE>100</REVENUE><NO_ROOMS>6</NO_ROOMS><INVENTORY_ROOMS>28</INVENTORY_ROOMS>
        </G_CONSIDERED_DATE>
      </LIST_G_CONSIDERED_DATE></G_REC_TYPE></LIST_G_REC_TYPE></G_GPAGEID></LIST_G_GPAGEID></HISTORY_FORECAST>""")
    d = history_forecast_daily([xml])["2026-01-20"]
    assert d["rooms_avail"] == pytest.approx(28.0)
    # Un solo archivo: el Only Rooms no existe, así que la tarifa queda en 0 y
    # no se inventa dividiendo el revenue total.
    assert d["adr"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# El OTB viejo, sin revenue
# ---------------------------------------------------------------------------

def test_avisa_cuando_el_otb_tiene_noches_pero_no_revenue():
    """Los snapshots cargados antes de que el OTB diario guardara revenue traen
    las habitaciones vendidas y las otras tres columnas en 0.

    Sin aviso, la hoja sale con ocupación de verdad y $0 de revenue, y el TOTAL
    del mes queda corto sin que nada lo señale: cuadra consigo misma y miente.
    Hay que volver a subir el history_forecast de ese mes.
    """
    viejo = {date(2026, 11, n): dato(occ=12, pax=0, revenue=0, rooms_revenue=0, adr=0)
             for n in range(6, 31)}
    h = armar_hoja(NOV, CORTE, HIST_NOV, viejo, TRAMOS)
    assert h["otb_sin_revenue"] is True
    # La ocupación sí está, y por eso el cero de revenue se nota tanto.
    assert h["totals"]["forecast"]["occ"] > 0
    assert h["totals"]["forecast"]["revenue"] == 0.0


def test_no_avisa_cuando_el_otb_esta_completo():
    h = armar_hoja(NOV, CORTE, HIST_NOV, FCST_NOV, TRAMOS)
    assert h["otb_sin_revenue"] is False


def test_no_avisa_cuando_directamente_no_hay_otb():
    """Mes cerrado o sin OTB: no hay nada que volver a subir, no es el mismo
    problema y no tiene que gritar lo mismo."""
    h = armar_hoja(NOV, CORTE, HIST_NOV, {}, TRAMOS)
    assert h["otb_sin_revenue"] is False


def test_un_dia_cargado_en_cero_no_se_marca_como_sin_cargar():
    """Octubre es el mes que CWL cierra: hay ingesta y los números dan cero.

    Marcarlo "sin cargar" hacía que la hoja se contradijera con el encabezado
    del propio reporte ("3 día(s) cargados en el mes") y mandaba a resubir algo
    que ya estaba. Un día cerrado no es un día que falte.
    """
    oct_ = dias(2026, 10, 31)
    # Los cuatro primeros estan ingestados; el 1 tiene una venta suelta y el
    # resto, cero -- el hotel esta cerrado.
    hist = {date(2026, 10, 1): dato(revenue=3.52, loaded=True)}
    hist.update({date(2026, 10, n): dato(loaded=True) for n in (2, 3, 4)})
    h = armar_hoja(oct_, date(2026, 10, 4), hist, {}, TRAMOS)

    cargados = [f for f in h["rows"] if f["block"] == HISTORY and f["loaded"]]
    assert len(cargados) == 4, "los cuatro dias estan ingestados, cero o no"
    assert all(f["revenue"] == 0.0 for f in cargados if f["day"] != 1)
    assert h["totals"]["history"]["revenue"] == pytest.approx(3.52, abs=0.01)
