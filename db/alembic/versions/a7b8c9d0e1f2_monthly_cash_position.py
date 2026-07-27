"""cash_monthly_position (Tab 5.2 Monthly Cash Position — líneas editables por mes)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = ["opening", "other_collections", "pay_vendors", "pay_capital", "pay_payroll",
         "pay_social_security", "pay_ins", "pay_hacienda",
         "other_pay_1", "other_pay_2", "other_pay_3", "other_pay_4"]


def upgrade() -> None:
    op.create_table(
        "cash_monthly_position",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        *[sa.Column(c, sa.Numeric(15, 2), server_default="0", nullable=False) for c in _COLS],
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id", "year", "month"),
    )


def downgrade() -> None:
    op.drop_table("cash_monthly_position")
