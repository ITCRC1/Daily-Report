import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import ensure_forecast_schema, ensure_inventario_schema, get_session
from app.models import Property

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lo que la base necesita y alembic no puede poner allá: la raíz del build
    del backend es `backend/`, así que `db/alembic` no viaja al contenedor.

    Las dos funciones son idempotentes y arrancan en orden: tablas del Forecast
    (Tab 6.1.1) y después el inventario con vigencia + las columnas nuevas del
    OTB diario (hoja 3). Ver `db.ensure_forecast_schema` y
    `db.ensure_inventario_schema`."""
    await ensure_forecast_schema()
    await ensure_inventario_schema()
    yield


app = FastAPI(
    title="DAILY-OPS API",
    version="0.1.0",
    description="Revenue diario/semanal, cash y auditoría · Corcovado Wilderness Lodge",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Sin esto, el navegador no expone Content-Disposition a fetch().headers
    # en requests cross-origin (frontend y backend en hosts distintos) -- los
    # downloads (Excel/PDF de Tab 2, template de Tab 6.1, Power Query) igual
    # funcionan, pero el nombre de archivo real del backend se pierde.
    expose_headers=["Content-Disposition"],
)

# App SIN autenticación (decisión del owner, 2026-07-27): no hay login, ni
# password compartido, ni usuarios/roles. Todos los endpoints son públicos para
# quien alcance la URL. El control de acceso, si hace falta, va por fuera (red
# privada, VPN o un proxy adelante).


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    """Ping + verifica conexión a Postgres. Lo usa Railway para el healthcheck.

    Devuelve además en qué migración está la BASE (`alembic_base`) y de qué
    commit es el código (`git_sha`). Acá las migraciones NO corren solas en el
    deploy (el startCommand es sólo uvicorn): hay que correr `alembic upgrade`
    a mano contra la base. Sin esto no había forma de mirar desde afuera si la
    base ya tiene lo que el código nuevo espera -- y un código que llega antes
    que su migración no falla al arrancar, falla recién cuando alguien abre el
    Tab 3 y le sale 500.

    Nunca revienta: si no puede leer la versión devuelve None. Un healthcheck
    que falla bloquea el deploy, y esto es informativo.
    """
    await session.execute(text("SELECT 1"))
    try:
        base = (await session.execute(
            text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
    except Exception:  # noqa: BLE001 -- informativo, no puede tumbar el healthcheck
        base = None
    return {
        "status": "ok",
        "db": "up",
        "alembic_base": base,
        "git_sha": os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
    }


@app.get("/properties")
async def list_properties(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.execute(select(Property).order_by(Property.code))).scalars().all()
    return [{"id": str(p.id), "code": p.code, "name": p.name, "activa": p.activa} for p in rows]


from app.api import audit, budget, cash, comps, daily_extended, deposit_ledger, export, forecast, ingest, iva, ledgers, market_codes, master_data, nav_config, ontb, reporting, revenue, revenue_actual, tips  # noqa: E402

app.include_router(ingest.router)          # etapa 1 (ingesta) + dispara etapa 4
app.include_router(audit.router)           # etapa 4 (reconciliación) + gate/refresh (etapa 8)
app.include_router(ledgers.router)         # 2.3 ledgers (saldos corrientes + apertura editable)
app.include_router(revenue.router)         # etapa 2 (Daily/Weekly Revenue Report)
app.include_router(cash.router)            # etapa 3 (Daily Cash from Operation)
app.include_router(export.router)          # etapa 8 (export Excel + PDF)
app.include_router(master_data.router)     # Tab 6 — 6.2 Cash Mapping + 6.3 Integrity Mapping
app.include_router(budget.router)          # Tab 6.1 Monthly Budget + 6.5 Daily derivado
app.include_router(forecast.router)        # Tab 6.1.1 Forecast mensual + diario derivado
app.include_router(revenue_actual.router)  # Tab 6.4 Revenue real diario por depto (Year to Date)
app.include_router(reporting.router)       # Tab 7.4 Power Query
app.include_router(deposit_ledger.router)  # Tab 7.5 Deposit Ledger (Bank, manual)
app.include_router(tips.router)            # Tab 7.6 Tips & Extra Tips
app.include_router(iva.router)             # Tab 7.7 IVA 13%
app.include_router(comps.router)           # Tab 7.8 YTD Comps + 7.9 Daily Comps por tipo
app.include_router(market_codes.router)    # Tab 7.10 Market Codes (Pax/Rooms/Room Rev/Rev Total)
app.include_router(nav_config.router)      # Admin — prender/apagar tabs
app.include_router(daily_extended.router)  # Tab 9 Daily Extendido
app.include_router(ontb.router)            # Tab 8 On The Books (Budget vs OTB mensual)
