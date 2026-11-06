"""Seed de master data — Corcovado v1 (CLAUDE.md §7).

Idempotente: se puede correr varias veces (ON CONFLICT DO NOTHING).
Siembra SOLO lo que el spec define exacto y determinístico. Lo que requiere
archivo fuente (DEPT_MAP completo, dim_payment_map, budget_monthly) NO se
inventa: queda como TODO(bismark) documentado abajo.

    python -m app.seed
"""
import asyncio
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import SessionLocal
from app.engine.week_calendar import generate_weeks
from app.models import (
    AppConfig,
    Calendar,
    InventoryTramo,
    MarketCode,
    OperaRevenueCat,
    Property,
    Role,
    RoomCategory,
    RoomCategoryUnitsTramo,
    WeekCalendar,
)

settings = get_settings()

MONTHS_ES = None  # etiquetas en inglés como los goldens (dd-Mon-yyyy)


# ---------------- catálogos exactos del spec ----------------
ROLES = [
    ("admin", "Controller / Administrador"),
    ("income_auditor", "Income Auditor"),
    ("viewer", "Viewer (dueños, solo lectura)"),
]

# §5.2 — categorías de habitación (últimos 2 díg de 4000-0110-…)
# (code2, report_name, opera_short_desc, room_class, integrity_string ref., units)
# room_class CONFIRMADO por Bismark (§5.2, XML STATISTICS). integrity_string es
# solo referencial -- el formato real de cuenta Integrity varía por segmento
# de mercado, no se usa para parsear revenue por categoría (§10, frágil).
ROOM_CATEGORIES = [
    ("01", "Corcovado Deluxe Villas", "Corcovado Deluxe", "FVR", "4000-0110-003-001-001-15-01", 6),
    ("02", "Carate Deluxe Villa", "Carate Deluxe", "FVR2", "4000-0110-006-001-001-15-02", 2),
    ("03", "Agujas Villa", "Agujas Villa", "FVR3", "4000-0110-006-001-001-15-03", 4),
    ("04", "Sirena Suites", "Sirena Suites", "FVR4", "4000-0110-006-001-001-15-04", 8),
    ("05", "Treehouse King", "Treehouse", "OVR", "4000-0110-003-001-001-15-05", 5),
    ("06", "5 Elements Treehouse", "5 Elements", "OVR2", "4000-0110-003-001-001-15-06", 5),
    # SH07 -- 3 villas que entran el 2027-02-01 (owner, 2026-11-06). units=0:
    # hoy no existen, y el 3 va fechado en CATEGORIA_UNIDADES_TRAMOS. El
    # opera_short_desc y el room_class van en None A PROPOSITO -- son las
    # llaves con las que se une al XML de Opera y todavia no esta dada de alta
    # ahi; inventarlas haria que su revenue cayera en "Otros" sin aviso.
    ("07", "Villas Deluxe", None, None, None, 0),
    ("00", "Other Rooms Revenue", None, None, None, None),
]

# ---- inventario CON VIGENCIA (§engine/inventory.py) -------------------------
# El inventario es el divisor de Occupancy% y RevPAR. Guardarlo como un solo
# numero (como hacia app_config.total_rooms) significaba que subirlo a 33 para
# feb-2027 recalculaba el historico entero contra 33 en el acto, sin error y
# sin aviso. Por eso va por tramos: (desde, unidades).
INVENTARIO_TRAMOS = [
    (date(2000, 1, 1), 30, "CWL opera con 30 unidades."),
    (date(2027, 2, 1), 33, "Owner 2026-11-06: entran 3 unidades (SH07 Villas Deluxe)."),
]

# Unidades por categoria, tambien con vigencia: las 3 nuevas no se reparten
# entre las categorias de hoy, son una categoria nueva.
CATEGORIA_UNIDADES_TRAMOS = [
    ("07", date(2027, 2, 1), 3, "Owner 2026-11-06: 3 villas nuevas."),
]

# §5.6 — market codes (catálogo confirmado por Bismark, 2026-07-03 -- reemplaza
# la lista anterior parcial/adivinada). kpi_group = canal de negocio (§3.2,
# Tab 6.8, editable) -- valor por default al sembrar, mismo criterio que
# engine/room_stats.py::DEFAULT_KPI_GROUPS.
MARKET_CODES = [
    ("BAR", "Best Available Rate", "Direct Client"),
    ("COM", "Complimentary / Courtesy", "Direct Client"),
    ("DIR", "Direct Reservation", "Direct Client"),
    ("FNF", "Friends & Family", "Direct Client"),
    ("INHOUSE", "In-House Guest", "INHOUSE"),
    ("OTA", "Online Travel Agency", "OTA"),
    ("SOC", "Social / Special Offer", "Direct Client"),
    ("TA", "Travel Agent", "Travel Agent"),
    ("TAFIT", "Travel Agent FIT", "Travel Agent"),
    ("TAGP", "Travel Agent Group", "Travel Agent"),
    ("WEB", "Website", "Website"),
]

# §5.6 — Opera TCode -> categoría (OTB vs Revenue)
OPERA_REVENUE_CAT = {
    "Accommodation": ["1000"],
    "Retail": ["2320", "2321", "2324", "2330", "2490"],
    "Sustainable": ["3005"],
    "Boat": ["3320"],
    "F&B Terra": ["2139", "2140", "2142", "2143", "2149", "2161"],
    "F&B Bosque": ["2224", "2225", "2227", "2228", "2233", "2234", "2245", "2246", "2249"],
    "Packages": ["2500", "2502", "2504", "2507"],
    "Tours": ["3400", "3405", "3406", "3407", "3411"],
}

# §2.7 / §3 — configuración de la app. Default del gate = SUAVE.
APP_CONFIG = [
    ("recon_tolerance", "0.01"),
    ("gate_min_set", "opera,integrity"),
    ("gate_hard", "false"),  # TODO(bismark): confirmar default definitivo suave vs duro.
    # Habitaciones físicas -- los reportes SIEMPRE usan el inventario
    # configurado para Occupancy%/ADR, sin importar qué disponibilidad reporte
    # Opera ese día (§Bismark, confirmado: "no importa si en Opera viajan
    # menos"). Cualquier diferencia real vs Opera se documenta como hallazgo
    # (2.10), nunca se descarta ni se esconde.
    # OJO: este valor YA NO MANDA. El inventario vive con vigencia en
    # `dim_inventario_tramo` (30 hasta 2027-01-31, 33 desde el 02-01) y esto
    # quedó solo como respaldo de una base sin tramos cargados. Editarlo acá
    # no cambia ningún reporte -- y ese es justamente el punto: editado, antes
    # recalculaba el histórico entero en silencio.
    ("total_rooms", "30"),
]

# Rango de calendario a generar (cubre goldens 2026 + YTD de bordes).
CAL_START = date(2025, 1, 1)
CAL_END = date(2027, 12, 31)


def _week_label(d: date) -> tuple[int, date, date, str]:
    """Semana Vie–Jue (corte confirmado por Bismark 2026-07-11, reemplaza el
    corte Lun-Dom anterior; ver `CORTES SEMANALES.xlsx`, W01 2026 = 26-Dic-2025
    a 01-Ene-2026). La semana pertenece al año de su jueves de cierre (igual
    criterio que ISO pero anclado a jueves-fin en vez de jueves-medio); el
    número de semana cuenta desde la primera semana Vie-Jue cuyo jueves cae
    en ese año."""
    days_since_friday = (d.weekday() - 4) % 7   # Mon=0..Sun=6, Friday=4
    week_start = d - timedelta(days=days_since_friday)
    week_end = week_start + timedelta(days=6)   # jueves
    year = week_end.year
    jan1 = date(year, 1, 1)
    days_to_first_thu = (3 - jan1.weekday()) % 7   # Thursday=3
    first_thu = jan1 + timedelta(days=days_to_first_thu)
    first_week_start = first_thu - timedelta(days=6)
    iso_week = (week_start - first_week_start).days // 7 + 1
    label = (
        f"W{iso_week:02d} | {week_start.strftime('%d-%b-%Y')} "
        f"to {week_end.strftime('%d-%b-%Y')}"
    )
    return iso_week, week_start, week_end, label


async def seed() -> None:
    async with SessionLocal() as s:
        # --- propiedad (primero: todo cuelga de aquí) ---
        await s.execute(
            pg_insert(Property)
            .values(code=settings.DEFAULT_PROPERTY, name="Corcovado Wilderness Lodge",
                    hotel_code=settings.DEFAULT_PROPERTY, activa=True)
            .on_conflict_do_nothing(index_elements=["code"])
        )
        await s.flush()
        prop = (await s.execute(
            select(Property).where(Property.code == settings.DEFAULT_PROPERTY)
        )).scalar_one()
        pid = prop.id

        # --- roles ---
        for code, name in ROLES:
            await s.execute(
                pg_insert(Role).values(code=code, name=name)
                .on_conflict_do_nothing(index_elements=["code"])
            )

        # --- app_config ---
        for key, value in APP_CONFIG:
            await s.execute(
                pg_insert(AppConfig).values(property_id=pid, key=key, value=value)
                .on_conflict_do_nothing(index_elements=["property_id", "key"])
            )

        # --- room categories ---
        for code2, report_name, opera, room_class, integrity_string, units in ROOM_CATEGORIES:
            await s.execute(
                pg_insert(RoomCategory).values(
                    property_id=pid, code2=code2, report_name=report_name, opera_short_desc=opera,
                    room_class=room_class, integrity_string=integrity_string, units=units,
                ).on_conflict_do_nothing(index_elements=["property_id", "code2"])
            )

        # --- inventario con vigencia ---
        # Se siembra DESPUES de room categories porque los tramos por categoria
        # necesitan el id de la fila. El tramo "desde siempre" de cada
        # categoria sale de su propio `units`, para no repetir el numero.
        for desde, unidades, nota in INVENTARIO_TRAMOS:
            await s.execute(
                pg_insert(InventoryTramo).values(
                    property_id=pid, desde=desde, unidades=unidades, nota=nota,
                ).on_conflict_do_nothing(index_elements=["property_id", "desde"])
            )
        cat_ids = {
            c.code2: c.id for c in (await s.execute(
                select(RoomCategory).where(RoomCategory.property_id == pid)
            )).scalars().all()
        }
        for code2, report_name, opera, room_class, integrity_string, units in ROOM_CATEGORIES:
            if code2 not in cat_ids:
                continue
            await s.execute(
                pg_insert(RoomCategoryUnitsTramo).values(
                    property_id=pid, room_category_id=cat_ids[code2],
                    desde=date(2000, 1, 1), unidades=(units or 0),
                    nota="Inventario de la categoria desde siempre.",
                ).on_conflict_do_nothing(index_elements=["room_category_id", "desde"])
            )
        for code2, desde, unidades, nota in CATEGORIA_UNIDADES_TRAMOS:
            if code2 not in cat_ids:
                continue
            await s.execute(
                pg_insert(RoomCategoryUnitsTramo).values(
                    property_id=pid, room_category_id=cat_ids[code2],
                    desde=desde, unidades=unidades, nota=nota,
                ).on_conflict_do_nothing(index_elements=["room_category_id", "desde"])
            )

        # --- market codes ---
        # DO NOTHING (2026-07-03): ahora es editable en Tab 6.8 -- re-correr
        # el seed solo debe insertar códigos nuevos que falten, nunca pisar
        # una edición manual de nombre/canal ya hecha desde la UI.
        for code, name, kpi_group in MARKET_CODES:
            await s.execute(
                pg_insert(MarketCode).values(property_id=pid, code=code, name=name, kpi_group=kpi_group)
                .on_conflict_do_nothing(index_elements=["property_id", "code"])
            )

        # --- opera revenue cat ---
        for categoria, tcodes in OPERA_REVENUE_CAT.items():
            for tc in tcodes:
                await s.execute(
                    pg_insert(OperaRevenueCat).values(property_id=pid, tcode=tc, categoria=categoria)
                    .on_conflict_do_nothing(index_elements=["property_id", "tcode", "categoria"])
                )

        # --- calendario por día (dim_calendar, Vie–Jue, sin huecos) ---
        # NO se toca: coexiste con dim_week_calendar (variantes de reporting).
        d = CAL_START
        rows = []
        while d <= CAL_END:
            iso_week, ws, we, label = _week_label(d)
            rows.append({
                "date": d, "iso_week": iso_week, "week_start": ws, "week_end": we,
                "week_label": label, "month": d.month, "year": d.year,
            })
            d += timedelta(days=1)
        for chunk_start in range(0, len(rows), 500):
            await s.execute(
                pg_insert(Calendar).values(rows[chunk_start:chunk_start + 500])
                .on_conflict_do_nothing(index_elements=["date"])
            )

        # --- calendario semanal EDITABLE (dim_week_calendar, Tab 6.10) ---
        # Semilla = corte estándar Vie–Jue; después cada fila es editable y
        # Tab 4 (Weekly Revenue) lee de acá. DO NOTHING: re-correr el seed no
        # pisa ediciones manuales ya hechas desde la UI.
        week_rows = [{"property_id": pid, **w} for w in generate_weeks(CAL_START, CAL_END)]
        await s.execute(
            pg_insert(WeekCalendar).values(week_rows)
            .on_conflict_do_nothing(index_elements=["property_id", "week_start"])
        )

        await s.commit()

    print("Seed OK: propiedad, roles, app_config, room_categories, market_codes, "
          "opera_revenue_cat, calendar, week_calendar.")
    print("PENDIENTE (requiere archivo fuente - TODO(bismark)):")
    print("  - dim_department  : DEPT_MAP 9-char completo (Power Query)")
    print("  - dim_payment_map : hoja Mapping/tblMapping del libro de Cash")
    print("  - budget_monthly  : plantilla mensual por departamento")


if __name__ == "__main__":
    asyncio.run(seed())
