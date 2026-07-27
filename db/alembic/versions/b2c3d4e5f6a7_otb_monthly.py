"""fact_otb_monthly (On The Books, Tab 8) -- agregado mensual del history_forecast por snapshot

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-06 19:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fact_otb_monthly",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("total_revenue", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("rooms_only_revenue", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("rooms_only_history", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("rooms_only_forecast", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("rooms_occ", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("guests", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("rooms_avail", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id", "snapshot_date", "month"),
    )
    op.create_index(op.f("ix_fact_otb_monthly_snapshot_date"), "fact_otb_monthly", ["snapshot_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fact_otb_monthly_snapshot_date"), table_name="fact_otb_monthly")
    op.drop_table("fact_otb_monthly")
