"""deposit_ledger (Tab 7.5) -- entrada manual diaria de depositado/aplicado + ancla opcional

Revision ID: 0ed1cc1d246e
Revises: f1a2b3c4d5e6
Create Date: 2026-07-03 16:06:52.179628
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0ed1cc1d246e'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fact_deposit_ledger_daily",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("deposited_usd", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("applied_usd", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id", "date"),
    )
    op.create_index(op.f("ix_fact_deposit_ledger_daily_date"), "fact_deposit_ledger_daily", ["date"], unique=False)

    op.create_table(
        "deposit_ledger_opening",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("anchor_date", sa.Date(), nullable=False),
        sa.Column("balance_usd", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id"),
    )
    op.execute(
        "CREATE TRIGGER t_deposit_ledger_opening_upd BEFORE UPDATE ON deposit_ledger_opening "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS t_deposit_ledger_opening_upd ON deposit_ledger_opening")
    op.drop_table("deposit_ledger_opening")
    op.drop_index(op.f("ix_fact_deposit_ledger_daily_date"), table_name="fact_deposit_ledger_daily")
    op.drop_table("fact_deposit_ledger_daily")
