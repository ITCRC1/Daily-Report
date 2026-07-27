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
    MarketCode,
    OperaRevenueCat,
    Property,
    Role,
    RoomCategory,
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
    ("00", "Other Rooms Revenue", None, None, None, None),
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
    # El hotel tiene 30 habitaciones físicas -- los reportes SIEMPRE usan este
    # número para Occupancy%/ADR, sin importar qué disponibilidad reporte Opera
    # ese día (§Bismark, confirmado: "no importa si en Opera viajan menos").
    # Cualquier diferencia real vs Opera se documenta como hallazgo (2.10),
    # nunca se descarta ni se esconde -- solo no afecta el número reportado.
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
