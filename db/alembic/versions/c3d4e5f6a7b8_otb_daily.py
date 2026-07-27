"""fact_otb_daily (On The Books heatmap, Tab 8.3) -- ocupación diaria del OTB por snapshot

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-06 20:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fact_otb_daily",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("the_date", sa.Date(), nullable=False),
        sa.Column("rooms_sold", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("rooms_avail", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id", "snapshot_date", "the_date"),
    )
    op.create_index(op.f("ix_fact_otb_daily_snapshot_date"), "fact_otb_daily", ["snapshot_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fact_otb_daily_snapshot_date"), table_name="fact_otb_daily")
    op.drop_table("fact_otb_daily")
