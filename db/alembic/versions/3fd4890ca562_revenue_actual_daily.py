"""revenue_actual_daily

Revision ID: 3fd4890ca562
Revises: 0006
Create Date: 2026-07-02 04:46:42.641412

Solo agrega fact_revenue_actual_daily (Tab 6.4) -- el resto del diff de
autogenerate era ruido de convención de nombres de índices preexistentes,
no relacionado con este cambio.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3fd4890ca562'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('fact_revenue_actual_daily',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('property_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('dept_id', sa.UUID(), nullable=True),
        sa.Column('amount_usd', sa.Numeric(precision=15, scale=2), server_default='0', nullable=False),
        sa.Column('rooms_sold', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('total_pax', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.ForeignKeyConstraint(['dept_id'], ['dim_department.id'], ),
        sa.ForeignKeyConstraint(['property_id'], ['dim_property.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fact_revenue_actual_daily_date'), 'fact_revenue_actual_daily', ['date'], unique=False)
    op.create_index(op.f('ix_fact_revenue_actual_daily_property_id'), 'fact_revenue_actual_daily', ['property_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fact_revenue_actual_daily_property_id'), table_name='fact_revenue_actual_daily')
    op.drop_index(op.f('ix_fact_revenue_actual_daily_date'), table_name='fact_revenue_actual_daily')
    op.drop_table('fact_revenue_actual_daily')
