"""fact_otb_monthly: columna `year` (soporte multi-año en On The Books)

El history_forecast puede abarcar >1 año (ej. snapshot jul-2026 con forecast
hasta Q1-2027). Antes se agrupaba por mes 1-12 sin año -> 2026 y 2027 se
sumaban en el mismo bucket. Se agrega `year` y la unique pasa a incluirlo.
Las filas existentes son todas 2026 (verificado: los XML subidos solo traían
fechas 2026), por eso el default 2026 es correcto para el backfill.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_UQ = "fact_otb_monthly_property_id_snapshot_date_month_key"
_NEW_UQ = "uq_fact_otb_monthly_snap_year_month"


def upgrade() -> None:
    op.add_column(
        "fact_otb_monthly",
        sa.Column("year", sa.Integer(), server_default="2026", nullable=False),
    )
    op.drop_constraint(_OLD_UQ, "fact_otb_monthly", type_="unique")
    op.create_unique_constraint(
        _NEW_UQ, "fact_otb_monthly",
        ["property_id", "snapshot_date", "year", "month"],
    )


def downgrade() -> None:
    op.drop_constraint(_NEW_UQ, "fact_otb_monthly", type_="unique")
    op.create_unique_constraint(
        _OLD_UQ, "fact_otb_monthly",
        ["property_id", "snapshot_date", "month"],
    )
    op.drop_column("fact_otb_monthly", "year")
