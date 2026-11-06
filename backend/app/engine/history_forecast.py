# -*- coding: utf-8 -*-
"""Hoja 3 del reporte a dueños — History and Forecast del mes.

Replica el *History and Forecast* de Opera recortado a lo que pidió el owner
el 2026-11-06, sobre maqueta en mano. Seis columnas, en este orden:

    Date · Total Occ · Occ.% · Total Revenue · ADR Rooms Only · PAX

Decisiones del owner, todas explícitas:

- **El corte es el día del Daily.** *«si el daily es del día 5, entonces
  forecast empieza en día 6 hasta el final del mes»*. History = del 1 al día
  del reporte; Forecast = del siguiente al último del mes. No se usa la marca
  History/Forecast del XML de Opera para partir: el corte lo manda la app.
- **History SIEMPRE del Daily** -- *«history siempre viene del daily»*: son
  datos reales, ya cerrados. El Forecast sale del `history_forecast` de Opera.
- **ADR Rooms Only**, no el ADR del revenue total: es una tarifa de
  habitación.
- **Arr. Rooms: fuera.** *«no importa, no las pongas en ninguno»*. El Daily no
  registra llegadas; existe en el XML de Opera y no se usa.
- **PAX**, no "Adl. & Ch.".
- **Occ.% contra las unidades vigentes del hotel, en los dos bloques.** NO
  contra el `INVENTORY_ROOMS` de Opera, que descuenta las fuera de servicio y
  cambia día a día (23, 28...): con él la misma columna se leería con dos
  criterios y parece un error. Ver `engine/inventory.py`.

⚠️ El ADR de un subtotal es un promedio PONDERADO (Σ revenue de habitación /
Σ noches vendidas), nunca el promedio de los ADR de cada día: un día con una
noche vendida pesaría igual que uno lleno.

Módulo puro: recibe los días ya cargados y no toca la base.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date as date_cls

from app.engine.inventory import Tramo, noches_disponibles, unidades_vigentes

HISTORY = "History"
FORECAST = "Forecast"

# Las seis columnas, en el orden que las aprobó el owner.
COLUMNAS = ["Date", "Total Occ", "Occ.%", "Total Revenue", "ADR Rooms Only", "PAX"]

_VACIO = {"occ": 0.0, "pax": 0.0, "revenue": 0.0, "rooms_revenue": 0.0, "adr": 0.0}


def _fila(d: date_cls, bloque: str, dato: dict, tramos: Iterable[Tramo]) -> dict:
    unidades = unidades_vigentes(tramos, d)
    occ = float(dato.get("occ") or 0.0)
    return {
        "date": d.isoformat(),
        "day": d.day,
        "dow": d.strftime("%a"),
        "block": bloque,
        "units": unidades,
        "occ": round(occ, 2),
        # Contra las unidades vigentes del hotel, no contra la disponibilidad
        # que reporte Opera ese día (ver el encabezado del módulo).
        "occ_pct": round(occ / unidades, 4) if unidades else 0.0,
        "revenue": round(float(dato.get("revenue") or 0.0), 2),
        "rooms_revenue": round(float(dato.get("rooms_revenue") or 0.0), 2),
        "adr": round(float(dato.get("adr") or 0.0), 2),
        "pax": round(float(dato.get("pax") or 0.0), 2),
        # Un día del History sin nada cargado sale en cero. Se marca en vez de
        # mostrarlo como un día flojo: un cero que no se distingue de un cero
        # real es la clase de dato que nadie cuestiona.
        "loaded": bool(dato.get("loaded", True)),
    }


def _total(filas: list[dict], tramos: Iterable[Tramo]) -> dict:
    """Los totales de un bloque. SIN rótulo: el texto que se muestra lo arma
    quien dibuja. Este módulo calcula; que devolviera "History — 5 días
    cerrados" metía castellano dentro del cálculo y obligaba a desplegar el
    backend para cambiar una palabra de una pantalla que está en inglés."""
    occ = sum(f["occ"] for f in filas)
    rooms_rev = sum(f["rooms_revenue"] for f in filas)
    disponibles = noches_disponibles(tramos, [date_cls.fromisoformat(f["date"]) for f in filas])
    return {
        "days": len(filas),
        "available": disponibles,
        "occ": round(occ, 2),
        "occ_pct": round(occ / disponibles, 4) if disponibles else 0.0,
        "revenue": round(sum(f["revenue"] for f in filas), 2),
        "rooms_revenue": round(rooms_rev, 2),
        # Ponderado, no promedio de promedios.
        "adr": round(rooms_rev / occ, 2) if occ else 0.0,
        "pax": round(sum(f["pax"] for f in filas), 2),
    }


def armar_hoja(dias: list[date_cls], corte: date_cls, history: dict, forecast: dict,
               tramos: Iterable[Tramo]) -> dict:
    """Arma las filas del mes y las tres líneas de totales.

    `dias`   todos los días del mes, en orden.
    `corte`  el día del Daily: hasta ahí es History, desde el siguiente Forecast.
    `history` / `forecast`  {date: {occ, pax, revenue, rooms_revenue, adr, loaded}}
    `tramos` inventario con vigencia (ver engine/inventory.py).
    """
    tramos = sorted(tramos)
    filas = []
    for d in dias:
        if d <= corte:
            filas.append(_fila(d, HISTORY, history.get(d, {**_VACIO, "loaded": False}), tramos))
        else:
            filas.append(_fila(d, FORECAST, forecast.get(d, _VACIO), tramos))

    hist = [f for f in filas if f["block"] == HISTORY]
    fcst = [f for f in filas if f["block"] == FORECAST]

    # ⚠️ Un snapshot de OTB cargado ANTES de que el OTB diario guardara revenue,
    # pax y tarifa trae las habitaciones vendidas pero esas tres columnas en 0.
    # La hoja saldría con ocupación de verdad y $0 de revenue, y el TOTAL del
    # mes quedaría corto sin decir por qué -- justo la cifra que cuadra consigo
    # misma y miente. Se detecta y se avisa: hay que volver a subir el
    # history_forecast de ese mes.
    otb_sin_revenue = (any(f["occ"] for f in fcst)
                       and not any(f["revenue"] for f in fcst))

    return {
        "columns": COLUMNAS,
        "rows": filas,
        "totals": {
            "history": _total(hist, tramos),
            "forecast": _total(fcst, tramos),
            "month": _total(filas, tramos),
        },
        "otb_sin_revenue": otb_sin_revenue,
    }
