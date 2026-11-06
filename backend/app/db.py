from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def ensure_forecast_schema() -> None:
    """Crea `forecast_monthly` / `fact_forecast` si faltan (Tab 6.1.1).

    En este deploy la raíz del build del backend es `backend/`, así que `db/
    alembic` no viaja al contenedor y no hay forma de correr `alembic upgrade`
    allá. Sin las tablas, Tab 3 se cae: `/revenue/{fecha}` consulta
    `fact_forecast` en cada llamada. Esto las crea al arrancar, una sola vez.

    Es idempotente (`checkfirst`) y sólo alcanza a estas dos tablas: no toca
    ninguna otra ni migra nada más. La definición canónica sigue siendo la
    migración `f2a3b4c5d6e7`, que también es idempotente -- correrla después
    contra una base ya inicializada por acá no falla.
    """
    from app.models import Forecast, ForecastMonthly

    tablas = [ForecastMonthly.__table__, Forecast.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=tablas, checkfirst=True
            )
        )


# Las cuatro columnas que la hoja History and Forecast le agrega al OTB diario.
_OTB_DAILY_COLS = ("revenue", "persons", "rooms_revenue", "adr")


async def ensure_inventario_schema() -> None:
    """Pone al día lo que necesita el inventario con vigencia y la hoja 3.

    Mismo motivo que `ensure_forecast_schema`: la raíz del build del backend es
    `backend/`, así que `db/alembic` no viaja al contenedor y allá no hay forma
    de correr `alembic upgrade`. Sin esto, un deploy del código ANTES de correr
    la migración a mano desde la PC deja el Tab 3 devolviendo 500 -- y no al
    arrancar, sino recién cuando alguien abre la pantalla: `dim_inventario_tramo`
    es el divisor de Occupancy% y se consulta en cada llamada.

    Hace tres cosas, todas idempotentes:
      1. crea las dos tablas de tramos si faltan,
      2. le agrega al `fact_otb_daily` existente las columnas de revenue/pax/
         tarifa (create_all NO agrega columnas a una tabla que ya existe),
      3. siembra los dos tramos de inventario SÓLO si la propiedad no tiene
         ninguno -- si no, la tabla quedaría vacía, el cálculo caería al
         `app_config.total_rooms` de siempre y febrero 2027 saldría con 30
         unidades sin que nada lo avise.

    La definición canónica siguen siendo las migraciones `a3b4c5d6e7f8` y
    `b4c5d6e7f8a9`, que también son idempotentes: correrlas después contra una
    base ya inicializada por acá no falla. Lo que ellas hacen y esto no es la
    categoría SH07 y los tramos POR CATEGORÍA, que son catálogo y no rompen
    nada por faltar (cada categoría cae a su `units` de siempre).
    """
    from app.models import InventoryTramo, RoomCategoryUnitsTramo

    tablas = [InventoryTramo.__table__, RoomCategoryUnitsTramo.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=tablas, checkfirst=True
            )
        )

        # 2) columnas nuevas del OTB diario, sólo si la tabla ya existe (en una
        #    base recién creada la hace su propia migración, con todo adentro).
        existe = (await conn.execute(
            text("SELECT to_regclass('fact_otb_daily') IS NOT NULL"))).scalar()
        if existe:
            for col in _OTB_DAILY_COLS:
                await conn.execute(text(
                    f"ALTER TABLE fact_otb_daily ADD COLUMN IF NOT EXISTS "
                    f"{col} NUMERIC(15,2) NOT NULL DEFAULT 0"
                ))

        # 3) tramo "desde siempre": el número que YA regía, sacado del
        #    app_config de cada propiedad. No cambia ninguna cifra publicada.
        await conn.execute(text(
            "INSERT INTO dim_inventario_tramo (property_id, desde, unidades, nota) "
            "SELECT p.id, DATE '2000-01-01', "
            "       COALESCE((SELECT c.value::int FROM app_config c "
            "                 WHERE c.property_id = p.id AND c.key = 'total_rooms' "
            "                   AND c.value <> '' AND c.value !~ '[^0-9]'), 30), "
            "       'Alta automatica al arrancar (ver db.ensure_inventario_schema).' "
            "FROM dim_property p "
            "WHERE NOT EXISTS (SELECT 1 FROM dim_inventario_tramo t "
            "                  WHERE t.property_id = p.id AND t.desde = DATE '2000-01-01')"
        ))
        # Owner 2026-11-06: CWL pasa a 33 unidades el 2027-02-01 (entra SH07).
        await conn.execute(text(
            "INSERT INTO dim_inventario_tramo (property_id, desde, unidades, nota) "
            "SELECT p.id, DATE '2027-02-01', 33, "
            "       'Owner 2026-11-06: entran 3 unidades (SH07 Villas Deluxe).' "
            "FROM dim_property p WHERE p.code = 'COWLCR' "
            "  AND NOT EXISTS (SELECT 1 FROM dim_inventario_tramo t "
            "                  WHERE t.property_id = p.id AND t.desde = DATE '2027-02-01')"
        ))
