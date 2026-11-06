# -*- coding: utf-8 -*-
"""Acceso al inventario de habitaciones CON VIGENCIA (lee `dim_inventario_tramo`).

Esta es la ÚNICA puerta por la que el resto del backend pregunta "cuántas
habitaciones tenía el hotel tal día" y "cuántas noches disponibles tuvo tal
período". Antes cada servicio releía `app_config.total_rooms` por su cuenta
(había tres copias de la misma función) y lo multiplicaba por la cantidad de
días; con el cambio de inventario de feb-2027 esas dos cosas dejan de ser
correctas, así que viven acá y en `engine/inventory.py` (la parte pura).

El criterio de fondo no cambió (§Bismark, confirmado): los reportes SIEMPRE
usan el inventario configurado para Occupancy%/ADR/RevPAR, sin importar qué
disponibilidad reporte Opera ese día -- la diferencia real se documenta como
hallazgo (`run_audit`), nunca mueve el número reportado. Lo que se agrega es
el "desde cuándo".
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date as date_cls

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.inventory import (
    Tramo,
    noches_disponibles as _noches_disponibles,
    noches_disponibles_rango as _noches_disponibles_rango,
    unidades_vigentes,
)
from app.models import AppConfig, InventoryTramo, RoomCategory, RoomCategoryUnitsTramo

# Último recurso, y el ÚNICO lugar del backend donde queda escrito un número de
# habitaciones. Es el mismo default que tenían las tres copias de `_total_rooms`
# que esto reemplaza, para que una base sin tramos cargados (o sin migrar
# todavía) siga devolviendo exactamente lo de antes en vez de romperse.
UNIDADES_FALLBACK = 30


async def tramos(session: AsyncSession, pid) -> list[Tramo]:
    """Tramos (desde, unidades) de la propiedad, de más viejo a más nuevo.

    Si la tabla todavía no tiene filas para esta propiedad se arma un único
    tramo "desde siempre" con `app_config.total_rooms` -- el valor sin fecha
    que regía antes. Así una base vieja no cambia ni una cifra, y el fallback
    queda en un solo lugar en vez de repartido por los servicios.
    """
    rows = (await session.execute(
        select(InventoryTramo).where(InventoryTramo.property_id == pid)
    )).scalars().all()
    if rows:
        return sorted((r.desde, int(r.unidades)) for r in rows)
    return [(date_cls.min, await _total_rooms_legacy(session, pid))]


async def _total_rooms_legacy(session: AsyncSession, pid) -> int:
    """`app_config.total_rooms`, el valor sin fecha de antes de los tramos.

    Se conserva solo como respaldo de `tramos()`. Nadie más debería leerlo:
    es justamente el número que, editado, recalculaba el histórico entero.
    """
    row = (await session.execute(
        select(AppConfig).where(AppConfig.property_id == pid, AppConfig.key == "total_rooms")
    )).scalar_one_or_none()
    try:
        return int(row.value) if row else UNIDADES_FALLBACK
    except (TypeError, ValueError):
        return UNIDADES_FALLBACK


async def unidades(session: AsyncSession, pid, dia: date_cls) -> int:
    """Habitaciones del hotel ESE día (30 hasta 2027-01-31, 33 desde el 02-01)."""
    return unidades_vigentes(await tramos(session, pid), dia)


async def noches_disponibles(session: AsyncSession, pid, dias: Iterable[date_cls]) -> int:
    """Noches disponibles = suma de las unidades de cada uno de esos días.

    `dias` es la lista exacta de días que cuentan, no un rango: varios reportes
    suman disponibilidad sólo de los días con ingesta real.
    """
    return _noches_disponibles(await tramos(session, pid), dias)


async def noches_disponibles_rango(session: AsyncSession, pid,
                                   desde: date_cls, hasta: date_cls) -> int:
    """Noches disponibles de [desde, hasta] inclusive, sumadas día a día."""
    return _noches_disponibles_rango(await tramos(session, pid), desde, hasta)


async def unidades_por_categoria(session: AsyncSession, pid, as_of: date_cls) -> dict[str, int]:
    """Unidades por categoría vigentes ese día, indexadas como las ve el rollup.

    La llave es `opera_short_desc` (que es con lo que viene el XML de Opera y
    con lo que arma las filas `engine/room_stats.py`). SH07 "Villas Deluxe"
    todavía no tiene esa llave -- no está dada de alta en Opera -- así que
    entra por `report_name`: aparece en el total de unidades, que es lo que
    tiene que cuadrar con el inventario de la propiedad, aunque todavía no
    pueda unirse a ninguna fila de Opera.

    Si una categoría no tiene tramos cargados cae a `dim_room_category.units`
    (el valor sin fecha), por el mismo motivo que `tramos()`: una base vieja
    sigue dando lo de antes.
    """
    cats = (await session.execute(
        select(RoomCategory).where(RoomCategory.property_id == pid)
    )).scalars().all()
    filas = (await session.execute(
        select(RoomCategoryUnitsTramo).where(RoomCategoryUnitsTramo.property_id == pid)
    )).scalars().all()

    por_cat: dict = {}
    for f in filas:
        por_cat.setdefault(f.room_category_id, []).append((f.desde, int(f.unidades)))

    out: dict[str, int] = {}
    for c in cats:
        clave = c.opera_short_desc or c.report_name
        if not clave:
            continue
        t = por_cat.get(c.id)
        out[clave] = unidades_vigentes(t, as_of) if t else int(c.units or 0)
    return out
