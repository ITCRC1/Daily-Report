"""tips_payout_kind (Tab 7.6.1 Tip 10% + Tab 7.6.2 Extra Tips) -- distingue el
tipo de gratuidad dentro de fact_tips_payout_daily, un mismo día puede tener
un pago de cada tipo.

Revision ID: 79cf14911f74
Revises: 4b91f8191782
Create Date: 2026-07-03 17:07:45.561368
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '79cf14911f74'
down_revision: Union[str, None] = '4b91f8191782'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "fact_tips_payout_daily",
        sa.Column("kind", sa.Text(), server_default="extra_tips", nullable=False),
    )
    op.drop_constraint("fact_tips_payout_daily_property_id_date_key", "fact_tips_payout_daily", type_="unique")
    op.create_unique_constraint(
        "fact_tips_payout_daily_property_id_kind_date_key",
        "fact_tips_payout_daily", ["property_id", "kind", "date"],
    )


def downgrade() -> None:
    op.drop_constraint("fact_tips_payout_daily_property_id_kind_date_key", "fact_tips_payout_daily", type_="unique")
    op.create_unique_constraint(
        "fact_tips_payout_daily_property_id_date_key", "fact_tips_payout_daily", ["property_id", "date"],
    )
    op.drop_column("fact_tips_payout_daily", "kind")
