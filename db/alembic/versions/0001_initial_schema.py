"""initial schema (ejecuta db/schema.sql)

Revision ID: 0001
Revises:
Create Date: 2026-07-01

La 0001 aplica el DDL canónico de db/schema.sql en una sola transacción.
Las migraciones siguientes usarán autogenerate contra los modelos ORM.
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# db/alembic/versions/0001_*.py -> db/schema.sql
SCHEMA_SQL = Path(__file__).resolve().parents[2] / "schema.sql"

# Tablas creadas por schema.sql (para el downgrade).
TABLES = [
    "audit_finding", "audit_run", "fact_pos_check", "fact_opera_txn",
    "fact_budget", "budget_monthly", "fact_room_stat", "stg_integrity_line",
    "app_config", "ingest_day_status", "ingest_batch", "dim_calendar",
    "dim_opera_revenue_cat", "dim_market_code", "dim_payment_map",
    "dim_room_category", "dim_department", "app_user", "role", "dim_property",
]


def upgrade() -> None:
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    op.execute(sql)


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE")
