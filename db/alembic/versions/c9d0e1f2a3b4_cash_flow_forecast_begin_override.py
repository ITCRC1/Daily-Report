"""cash_flow_forecast: override editable del Beginning Cash (b1..b12, nullable)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BCOLS = [f"b{m}" for m in range(1, 13)]


def upgrade() -> None:
    for c in _BCOLS:
        op.add_column("cash_flow_forecast", sa.Column(c, sa.Numeric(15, 2), nullable=True))


def downgrade() -> None:
    for c in _BCOLS:
        op.drop_column("cash_flow_forecast", c)
