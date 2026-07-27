"""cash_monthly_position: tasas de comisión y retención de tarjeta (POS + Ecommerce)

Para netear el "MTD Cash collected" en Tab 5.2: el bruto (Real Cash) lleva
comisión de tarjeta + retención de tarjeta sobre los canales POS y Ecommerce.
Las 4 tasas se guardan por (property, year, month) — se expresan en PORCENTAJE
(ej. 2.5 = 2.5%). El neto = bruto − base_canal × (comisión% + retención%)/100.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_RATE_COLS = ["pos_commission_pct", "pos_retention_pct",
              "ecom_commission_pct", "ecom_retention_pct"]


def upgrade() -> None:
    for c in _RATE_COLS:
        op.add_column("cash_monthly_position",
                      sa.Column(c, sa.Numeric(6, 4), server_default="0", nullable=False))


def downgrade() -> None:
    for c in _RATE_COLS:
        op.drop_column("cash_monthly_position", c)
