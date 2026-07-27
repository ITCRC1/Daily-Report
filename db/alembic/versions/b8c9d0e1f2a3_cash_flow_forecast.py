"""cash_flow_forecast (Tab 5.2 panel derecho — Full Year Cash Flow Forecast)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NCOLS = [f"n{m}" for m in range(1, 13)]


def upgrade() -> None:
    op.create_table(
        "cash_flow_forecast",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("opening", sa.Numeric(15, 2), server_default="0", nullable=False),
        *[sa.Column(c, sa.Numeric(15, 2), server_default="0", nullable=False) for c in _NCOLS],
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id", "year", "scenario"),
    )


def downgrade() -> None:
    op.drop_table("cash_flow_forecast")
