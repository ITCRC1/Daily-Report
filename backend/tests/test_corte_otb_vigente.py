# -*- coding: utf-8 -*-
"""Un corte de OTB vacío no puede tapar a uno bueno.

**Lo que pasó el 2026-11-09.** Se subió un `history_forecast` exportado desde
Opera con el rango de fechas de **2025**. La ingesta lo tomó --era un archivo
legítimo-- y creó el corte `2026-11-09` con sus filas, todas de 2025. Como las
tres pantallas que leen OTB resolvían el corte con un `max(snapshot_date)` a
secas, se quedaron con ése:

    Tab 8 On The Books ....... noviembre y diciembre 2026 en $0,00
    heatmap .................. noviembre entero en null
    hoja 3 History/Forecast .. Forecast de 21 días en $0,00

con el corte del **2026-11-05** ahí al lado, intacto, con **$243.808,44** de
noviembre. No hubo error, ni cero sospechoso, ni alerta: sólo un mes flojo en
un reporte que cuadra consigo mismo. Es el modo de falla más caro del sistema.

Owner, 2026-11-10: *«escoge el día anterior, pero si por alguna razón no tiene
datos debe ir al otro día, y así sucesivamente, hasta encontrar datos
coherentes»*.

⚠️ Si alguna de estas pruebas falla, el síntoma NO va a ser una excepción: va a
ser una pantalla en cero que nadie cuestiona. No la relajes.
"""
import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, OtbDaily, OtbMonthly, Property
from app.services.ontb_service import corte_vigente

BUENO = date(2026, 11, 5)      # corte sano: trae 2026 con plata
VACIO = date(2026, 11, 9)      # corte posterior, pero sólo con 2025
PEOR = date(2026, 11, 10)      # todavía más nuevo y todavía más inútil


@pytest_asyncio.fixture
async def ses():
    """Base de verdad (sqlite en memoria) con los modelos reales: lo que se
    prueba es la CONSULTA, y una consulta no se prueba con diccionarios."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s
    await eng.dispose()


async def _propiedad(ses):
    pid = uuid.uuid4()
    ses.add(Property(id=pid, code="COWLCR", name="Corcovado"))
    await ses.flush()
    return pid


def _mensual(pid, snap, anio, revenue):
    # `id` explícito: la PK usa `gen_random_uuid()` de Postgres y sqlite no la tiene.
    return OtbMonthly(id=uuid.uuid4(),
                      property_id=pid, snapshot_date=snap, year=anio, month=11,
                      total_revenue=revenue, rooms_only_revenue=revenue / 2,
                      rooms_only_history=0, rooms_only_forecast=revenue / 2,
                      rooms_occ=326, guests=633, rooms_avail=900)


def _diario(pid, snap, dia, revenue, rooms_sold=12):
    return OtbDaily(id=uuid.uuid4(),
                    property_id=pid, snapshot_date=snap, the_date=dia,
                    rooms_sold=rooms_sold, rooms_avail=30, revenue=revenue,
                    persons=20, rooms_revenue=revenue * 0.6, adr=450)


# --- el caso real ----------------------------------------------------------

@pytest.mark.asyncio
async def test_el_corte_del_anio_equivocado_no_tapa_al_bueno(ses):
    """El 09 sólo trae 2025. Para 2026 tiene que ganar el 05."""
    pid = await _propiedad(ses)
    ses.add(_mensual(pid, BUENO, 2026, 243808.44))
    ses.add(_mensual(pid, VACIO, 2025, 616450.98))
    await ses.flush()

    usado, ultimo = await corte_vigente(
        ses, pid, OtbMonthly,
        coherente=and_(OtbMonthly.year == 2026, OtbMonthly.total_revenue > 0))

    assert usado == BUENO, "se usó el corte vacío y noviembre sale en $0,00"
    assert ultimo == VACIO, "hay que poder DECIR cuál era el más nuevo"


@pytest.mark.asyncio
async def test_sigue_retrocediendo_mientras_no_encuentre_datos(ses):
    """Owner: «y así sucesivamente, hasta encontrar datos coherentes».

    Dos cortes malos encima del bueno, no uno: el arreglo no puede ser
    "tomar el anteúltimo".
    """
    pid = await _propiedad(ses)
    ses.add(_mensual(pid, BUENO, 2026, 243808.44))
    ses.add(_mensual(pid, VACIO, 2025, 616450.98))
    ses.add(_mensual(pid, PEOR, 2025, 700000.00))
    await ses.flush()

    usado, ultimo = await corte_vigente(
        ses, pid, OtbMonthly,
        coherente=and_(OtbMonthly.year == 2026, OtbMonthly.total_revenue > 0))
    assert usado == BUENO
    assert ultimo == PEOR


@pytest.mark.asyncio
async def test_un_corte_con_el_anio_pero_en_cero_tampoco_sirve(ses):
    """«Coherente» no es «existe»: un corte puede traer el año y no traer plata.

    Son los cargados antes del 2026-11-06, con las noches pero el revenue en
    cero. Si pasaran, la hoja volvería a imprimirse con el total corto.
    """
    pid = await _propiedad(ses)
    ses.add(_mensual(pid, BUENO, 2026, 243808.44))
    ses.add(_mensual(pid, VACIO, 2026, 0.0))
    await ses.flush()

    usado, _ = await corte_vigente(
        ses, pid, OtbMonthly,
        coherente=and_(OtbMonthly.year == 2026, OtbMonthly.total_revenue > 0))
    assert usado == BUENO


@pytest.mark.asyncio
async def test_si_NINGUNO_sirve_se_devuelve_el_mas_reciente(ses):
    """Quedarse sin corte sería cambiar una cifra equivocada por una pantalla
    en blanco. Se muestra lo que hay y el aviso explica el cero."""
    pid = await _propiedad(ses)
    ses.add(_mensual(pid, BUENO, 2025, 10.0))
    ses.add(_mensual(pid, VACIO, 2025, 20.0))
    await ses.flush()

    usado, ultimo = await corte_vigente(
        ses, pid, OtbMonthly,
        coherente=and_(OtbMonthly.year == 2026, OtbMonthly.total_revenue > 0))
    assert usado == VACIO == ultimo


@pytest.mark.asyncio
async def test_el_mas_nuevo_gana_cuando_SI_sirve(ses):
    """El criterio del owner del 2026-11-06 sigue vigente: On The Books es lo
    que hay reservado AHORA, y entre dos cortes buenos manda el más fresco."""
    pid = await _propiedad(ses)
    ses.add(_mensual(pid, BUENO, 2026, 243808.44))
    ses.add(_mensual(pid, VACIO, 2026, 251000.00))
    await ses.flush()

    usado, ultimo = await corte_vigente(
        ses, pid, OtbMonthly,
        coherente=and_(OtbMonthly.year == 2026, OtbMonthly.total_revenue > 0))
    assert usado == VACIO == ultimo


# --- la hoja 3 usa días, no meses ------------------------------------------

@pytest.mark.asyncio
async def test_la_hoja_3_elige_por_los_DIAS_que_necesita(ses):
    """El Forecast pide del 10 al 30 de noviembre. Un corte que no tenga esos
    días no sirve aunque sea el más nuevo."""
    pid = await _propiedad(ses)
    for n in range(10, 31):
        ses.add(_diario(pid, BUENO, date(2026, 11, n), 9000.0))
    for n in range(1, 29):                       # el corte nuevo, pero de 2025
        ses.add(_diario(pid, VACIO, date(2025, 11, n), 5000.0))
    await ses.flush()

    usado, ultimo = await corte_vigente(
        ses, pid, OtbDaily,
        coherente=and_(OtbDaily.the_date.between(date(2026, 11, 10), date(2026, 11, 30)),
                       OtbDaily.revenue > 0))
    assert usado == BUENO
    assert ultimo == VACIO


@pytest.mark.asyncio
async def test_dias_con_noches_pero_sin_revenue_no_cuentan(ses):
    """Los cortes anteriores al 2026-11-06 traen `rooms_sold` y el revenue en
    cero. La hoja saldría con ocupación de verdad y $0 -- cuadra consigo misma
    y miente, impresa."""
    pid = await _propiedad(ses)
    for n in range(10, 31):
        ses.add(_diario(pid, BUENO, date(2026, 11, n), 9000.0))
        ses.add(_diario(pid, VACIO, date(2026, 11, n), 0.0, rooms_sold=12))
    await ses.flush()

    usado, _ = await corte_vigente(
        ses, pid, OtbDaily,
        coherente=and_(OtbDaily.the_date.between(date(2026, 11, 10), date(2026, 11, 30)),
                       OtbDaily.revenue > 0))
    assert usado == BUENO


# --- que nadie vuelva al max() pelado --------------------------------------

def test_ninguna_pantalla_resuelve_el_corte_por_su_cuenta():
    """`corte_vigente` es la única puerta.

    ⚠️ Si aparece un `max(OtbDaily.snapshot_date)` suelto en un servicio, esa
    pantalla vuelve a poder quedarse con un corte vacío mientras las otras dos
    usan el bueno -- y nada avisa, porque las tres siguen cuadrando consigo
    mismas.
    """
    import pathlib
    svc = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"
    for f in svc.glob("*_service.py"):
        src = f.read_text(encoding="utf-8")
        for tabla in ("OtbDaily", "OtbMonthly"):
            crudo = f"func.max({tabla}.snapshot_date)"
            if crudo in src and f.name != "ontb_service.py":
                pytest.fail(f"{f.name} resuelve el corte por su cuenta ({crudo}): "
                            f"tiene que pasar por ontb_service.corte_vigente")
