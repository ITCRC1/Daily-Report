# -*- coding: utf-8 -*-
"""Inventario de habitaciones CON VIGENCIA — el divisor de Occupancy% y RevPAR.

El hotel no tiene "un" número de habitaciones: tiene un número POR FECHA. CWL
opera con 30 unidades desde siempre y pasa a 33 el 2027-02-01 (confirmado por
el owner el 2026-11-06).

Por qué el inventario se guarda en tramos y no en un solo valor
---------------------------------------------------------------
El inventario es el DIVISOR de Occupancy% y de RevPAR en TODOS los reportes.
Mientras fue un único `app_config.total_rooms` (sin fecha), editarlo de 30 a 33
para que febrero 2027 saliera bien recalculaba el histórico entero contra 33 en
el mismo instante: el Occ% de 2026 bajaba ~9%, el RevPAR se movía, y no saltaba
ningún error — los reportes seguían cuadrando igual de bien. Una cifra que
cambia sola y en silencio es el modo de falla más caro que tiene este sistema.
Con tramos, agregar el inventario de 2027 no toca ni un día ya cerrado.

Módulo PURO: recibe los tramos ya cargados y no toca la base. El acceso a la
base (y el fallback cuando todavía no hay tramos cargados) vive en
`services/inventory_service.py`.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, timedelta

# Un tramo es (desde, unidades): rige DESDE esa fecha inclusive y hasta el día
# anterior al `desde` del tramo siguiente. No lleva "hasta" a propósito — un
# "hasta" se puede contradecir con el "desde" del que sigue y deja huecos o
# solapes; el borde queda definido una sola vez y no hay forma de que mientan.
Tramo = tuple[date, int]


def unidades_vigentes(tramos: Iterable[Tramo], dia: date) -> int:
    """Unidades que rigen ese día: el tramo más reciente cuyo `desde` ya llegó.

    Un día anterior al primer tramo conocido devuelve las unidades de ese
    primer tramo: del inventario previo no hay registro, y suponer el más
    antiguo conocido es exactamente lo que hacía el valor fijo de siempre
    (no cambia ninguna cifra ya publicada).
    """
    ordenados = sorted(tramos)
    if not ordenados:
        # Sin tramos no hay inventario que repartir. Devolver un 30 de consuelo
        # acá sería volver a esconder un número fijo adentro del motor: el
        # fallback es decisión del servicio, que además puede decir de dónde
        # sacó el número.
        raise ValueError("No hay tramos de inventario cargados.")
    vigente = ordenados[0][1]
    for desde, unidades in ordenados:
        if desde > dia:
            break
        vigente = unidades
    return vigente


def dias_del_rango(desde: date, hasta: date) -> Iterator[date]:
    """Los días de [desde, hasta], ambos inclusive. Vacío si hasta < desde."""
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def noches_disponibles(tramos: Iterable[Tramo], dias: Iterable[date]) -> int:
    """Noches disponibles del período = SUMA de las unidades de cada día.

    NUNCA `unidades × cantidad_de_días`: un período puede cruzar un cambio de
    inventario y la multiplicación lo cobra todo al mismo precio. Con el cambio
    de 2027: enero da 930 (31 × 30) y febrero 924 (28 × 33), pero el Full Year
    2027 da 11.952 — ni 10.950 (todo a 30) ni 12.045 (todo a 33).

    `dias` es una lista de días, no un rango, porque varios reportes cuentan
    sólo los días que tienen ingesta real (los demás no suman disponibilidad).
    """
    tramos = sorted(tramos)  # se ordena una vez y no por día
    return sum(unidades_vigentes(tramos, d) for d in dias)


def noches_disponibles_rango(tramos: Iterable[Tramo], desde: date, hasta: date) -> int:
    """Noches disponibles de todos los días de [desde, hasta], inclusive."""
    return noches_disponibles(tramos, dias_del_rango(desde, hasta))
