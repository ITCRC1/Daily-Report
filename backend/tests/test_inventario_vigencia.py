# -*- coding: utf-8 -*-
"""Inventario de habitaciones con vigencia — el divisor de Occupancy% y RevPAR.

Estas pruebas cuidan un defecto concreto y silencioso: el inventario vivía en
un solo valor sin fecha (`app_config.total_rooms`), así que subirlo de 30 a 33
para que febrero 2027 saliera bien recalculaba TODO el histórico contra 33 en
el mismo instante. No había error ni alerta -- los reportes seguían cuadrando
y el Occ% de 2026 simplemente aparecía ~9% más bajo que el día anterior.

`test_agregar_el_tramo_de_2027_no_mueve_un_mes_ya_cerrado` es la que protege
contra eso; las demás cuidan el borde y la suma día a día.
"""
from datetime import date

import pytest

from app.engine.inventory import (
    dias_del_rango,
    noches_disponibles,
    noches_disponibles_rango,
    unidades_vigentes,
)

# Los dos tramos reales de CWL (owner, 2026-11-06).
TRAMOS = [
    (date(2000, 1, 1), 30),
    (date(2027, 2, 1), 33),
]

# El estado ANTERIOR al cambio: lo único que el sistema sabía antes de que el
# owner confirmara febrero. Se usa para comprobar que agregar el tramo nuevo
# no mueve nada de lo ya publicado.
TRAMOS_ANTES = [(date(2000, 1, 1), 30)]


# ---------------------------------------------------------------------------
# El borde
# ---------------------------------------------------------------------------

def test_el_cambio_de_inventario_arranca_el_1_de_febrero_y_no_antes():
    """El 2027-01-31 todavía son 30 y el 2027-02-01 ya son 33.

    Un tramo que arrancara un día antes (o después) metería 3 habitaciones de
    más en enero -- o de menos en febrero -- y el Occ% de ese mes saldría mal
    sin que nada lo marque.
    """
    assert unidades_vigentes(TRAMOS, date(2027, 1, 31)) == 30
    assert unidades_vigentes(TRAMOS, date(2027, 2, 1)) == 33


def test_un_dia_cualquiera_del_pasado_sigue_dando_30():
    assert unidades_vigentes(TRAMOS, date(2026, 6, 8)) == 30
    assert unidades_vigentes(TRAMOS, date(2025, 12, 31)) == 30


def test_un_dia_muy_posterior_se_queda_en_el_ultimo_tramo():
    """Sin tramo siguiente, el último sigue rigiendo -- no se queda sin valor."""
    assert unidades_vigentes(TRAMOS, date(2030, 7, 4)) == 33


def test_los_tramos_desordenados_dan_el_mismo_resultado():
    """El orden en que vienen de la base no puede cambiar la respuesta."""
    revueltos = list(reversed(TRAMOS))
    assert unidades_vigentes(revueltos, date(2027, 1, 31)) == 30
    assert unidades_vigentes(revueltos, date(2027, 2, 1)) == 33


def test_sin_tramos_cargados_falla_en_vez_de_inventar_un_30():
    """Quedarse callado devolviendo 30 sería volver a esconder un número fijo
    adentro del motor. El fallback es decisión del servicio, que además puede
    decir de dónde sacó el número."""
    with pytest.raises(ValueError):
        unidades_vigentes([], date(2026, 6, 8))


# ---------------------------------------------------------------------------
# La suma día a día (nunca unidades x días)
# ---------------------------------------------------------------------------

def test_enero_2027_da_930_y_febrero_924():
    """Cada mes a su propio inventario: 31 x 30 y 28 x 33."""
    assert noches_disponibles_rango(TRAMOS, date(2027, 1, 1), date(2027, 1, 31)) == 930
    assert noches_disponibles_rango(TRAMOS, date(2027, 2, 1), date(2027, 2, 28)) == 924


def test_un_periodo_que_cruza_el_cambio_suma_dia_a_dia():
    """Del 2027-01-30 al 2027-02-02: dos días a 30 y dos a 33, no cuatro a uno
    solo. Multiplicar daría 120 o 132; lo correcto es 126."""
    cruce = noches_disponibles_rango(TRAMOS, date(2027, 1, 30), date(2027, 2, 2))
    assert cruce == 2 * 30 + 2 * 33 == 126


def test_el_full_year_2027_no_sale_de_ninguna_multiplicacion():
    """11.952 = 31 días a 30 + 334 a 33. Ni 10.950 (todo a 30) ni 12.045 (todo
    a 33): el Full Year 2027 es justo el reporte que una multiplicación rompe,
    y es el primero que va a pedir la hoja History and Forecast."""
    anio = noches_disponibles_rango(TRAMOS, date(2027, 1, 1), date(2027, 12, 31))
    assert anio == 11952
    assert anio != 33 * 365
    assert anio != 30 * 365


def test_se_suman_solo_los_dias_que_se_le_pasan():
    """Varios reportes cuentan disponibilidad sólo de los días con ingesta
    real. La función recibe esos días sueltos, no un rango."""
    dias_con_datos = [date(2027, 1, 31), date(2027, 2, 1), date(2027, 2, 15)]
    assert noches_disponibles(TRAMOS, dias_con_datos) == 30 + 33 + 33


def test_un_rango_al_reves_no_cuenta_dias():
    assert list(dias_del_rango(date(2027, 2, 2), date(2027, 2, 1))) == []
    assert noches_disponibles_rango(TRAMOS, date(2027, 2, 2), date(2027, 2, 1)) == 0


def test_un_solo_dia_es_un_dia():
    assert noches_disponibles_rango(TRAMOS, date(2026, 6, 8), date(2026, 6, 8)) == 30


# ---------------------------------------------------------------------------
# La que protege el histórico (el riesgo de fondo)
# ---------------------------------------------------------------------------

def test_agregar_el_tramo_de_2027_no_mueve_un_mes_ya_cerrado():
    """Cargar el inventario de febrero 2027 no puede cambiar junio 2026.

    Este es el defecto caro: con un solo número sin fecha, subirlo a 33
    recalculaba hacia atrás en silencio. Si esta prueba falla, algún mes ya
    cerrado y ya enviado a los dueños cambió de Occupancy% solo.
    """
    for primero, ultimo in [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 6, 1), date(2026, 6, 30)),
        (date(2026, 12, 1), date(2026, 12, 31)),
    ]:
        antes = noches_disponibles_rango(TRAMOS_ANTES, primero, ultimo)
        despues = noches_disponibles_rango(TRAMOS, primero, ultimo)
        assert despues == antes, f"{primero:%Y-%m} cambió de {antes} a {despues} noches"


def test_el_occupancy_de_un_mes_cerrado_no_se_mueve():
    """Lo mismo pero en la cifra que de verdad se publica.

    Junio 2026: 565 noches vendidas sobre 900 disponibles = 62,78%. Con el
    número viejo sin fecha subido a 33 habría caído a 57,07% -- casi 6 puntos,
    de un día para el otro, sin que nada lo avise.
    """
    rn_vendidas = 565
    junio = (date(2026, 6, 1), date(2026, 6, 30))

    occ_antes = rn_vendidas / noches_disponibles_rango(TRAMOS_ANTES, *junio)
    occ_despues = rn_vendidas / noches_disponibles_rango(TRAMOS, *junio)
    assert occ_despues == pytest.approx(occ_antes, abs=1e-9)
    assert occ_despues == pytest.approx(0.6278, abs=0.0001)

    # Y así se vería el daño si el inventario no tuviera fecha:
    occ_con_el_numero_pisado = rn_vendidas / (33 * 30)
    assert occ_con_el_numero_pisado == pytest.approx(0.5707, abs=0.0001)
    assert abs(occ_antes - occ_con_el_numero_pisado) > 0.05
