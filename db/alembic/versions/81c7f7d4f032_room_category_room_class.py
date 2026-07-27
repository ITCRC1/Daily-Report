"""room_category_room_class

Revision ID: 81c7f7d4f032
Revises: 8349a6796586
Create Date: 2026-07-02 06:04:27.335213
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '81c7f7d4f032'
down_revision: Union[str, None] = '8349a6796586'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# code2 (dim_room_category) -> room_class (fact_occupancy_stat, XML STATISTICS)
ROOM_CLASS_BY_CODE2 = {
    "01": "FVR",   # Corcovado Deluxe -- inferido por posición, no confirmado en datos
    "02": "FVR2",  # Carate Deluxe -- inferido por posición, no confirmado en datos
    "03": "FVR3",  # Agujas Villa -- CONFIRMADO (room_type AV2QB)
    "04": "FVR4",  # Sirena Suites -- CONFIRMADO (room_type SSQBC)
    "05": "OVR",   # Treehouse -- CONFIRMADO (room_type THKB)
    "06": "OVR2",  # 5 Elements -- inferido por posición, no confirmado en datos
}


def upgrade() -> None:
    op.add_column('dim_room_category', sa.Column('room_class', sa.Text(), nullable=True))
    conn = op.get_bind()
    for code2, room_class in ROOM_CLASS_BY_CODE2.items():
        conn.execute(sa.text(
            "UPDATE dim_room_category SET room_class = :rc WHERE code2 = :c2"
        ), {"rc": room_class, "c2": code2})


def downgrade() -> None:
    op.drop_column('dim_room_category', 'room_class')
