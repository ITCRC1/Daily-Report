"""tips_payout (Tab 7.6) -- pago manual diario a empleados, Collected viene de Integrity

Revision ID: 4b91f8191782
Revises: 0ed1cc1d246e
Create Date: 2026-07-03 16:46:57.500879
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4b91f8191782'
down_revision: Union[str, None] = '0ed1cc1d246e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fact_tips_payout_daily",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("paid_usd", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id", "date"),
    )
    op.create_index(op.f("ix_fact_tips_payout_daily_date"), "fact_tips_payout_daily", ["date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fact_tips_payout_daily_date"), table_name="fact_tips_payout_daily")
    op.drop_table("fact_tips_payout_daily")
