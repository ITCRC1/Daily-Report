"""revenue_actual_daily_available_rooms

Revision ID: 90759c1e7ff5
Revises: 3fd4890ca562
Create Date: 2026-07-02 05:02:02.139312
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '90759c1e7ff5'
down_revision: Union[str, None] = '3fd4890ca562'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fact_revenue_actual_daily', sa.Column('available_rooms', sa.Numeric(precision=15, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('fact_revenue_actual_daily', 'available_rooms')
