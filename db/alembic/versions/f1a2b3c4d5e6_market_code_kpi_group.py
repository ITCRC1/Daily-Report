"""market_code_kpi_group

Revision ID: f1a2b3c4d5e6
Revises: c1a2b3d4e5f6
Create Date: 2026-07-03 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Canal de negocio (§3.2 KPI) por market_code, confirmado por Bismark 2026-07-03.
KPI_GROUP_BY_CODE = {
    "TA": "Travel Agent", "TAFIT": "Travel Agent", "TAGP": "Travel Agent",
    "BAR": "Direct Client", "COM": "Direct Client", "DIR": "Direct Client",
    "FNF": "Direct Client", "SOC": "Direct Client",
    "WEB": "Website",
    "OTA": "OTA",
    "INHOUSE": "INHOUSE",
}


def upgrade() -> None:
    op.add_column('dim_market_code', sa.Column('kpi_group', sa.Text(), nullable=True))
    conn = op.get_bind()
    for code, group in KPI_GROUP_BY_CODE.items():
        conn.execute(sa.text(
            "UPDATE dim_market_code SET kpi_group = :g WHERE code = :c"
        ), {"g": group, "c": code})


def downgrade() -> None:
    op.drop_column('dim_market_code', 'kpi_group')
