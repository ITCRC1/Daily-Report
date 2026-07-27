"""Alembic env — corre migraciones sync (psycopg2) contra la base daily_ops.

Carga el .env del backend para tomar DATABASE_URL_SYNC y agrega el backend al
sys.path para que las migraciones puedan importar los modelos si lo necesitan.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# rutas: db/alembic/env.py -> raíz del repo
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

load_dotenv(BACKEND / ".env")

config = context.config
db_url = os.getenv("DATABASE_URL_SYNC")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata para autogenerate en migraciones futuras (la 0001 usa raw SQL).
try:
    from app.db import Base  # noqa: E402
    import app.models  # noqa: F401,E402

    target_metadata = Base.metadata
except Exception:  # pragma: no cover - autogenerate opcional
    target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
