from collections.abc import AsyncGenerator

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
