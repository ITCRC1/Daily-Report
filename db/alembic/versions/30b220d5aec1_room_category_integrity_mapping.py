"""room_category_integrity_mapping

Revision ID: 30b220d5aec1
Revises: 81c7f7d4f032
Create Date: 2026-07-02 08:31:54.181919
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '30b220d5aec1'
down_revision: Union[str, None] = '81c7f7d4f032'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


"""Agrega integrity_string (referencial) + units + confirma room_class.

Bismark confirmó explícitamente el mapeo room_class -> categoría (antes
inferido por posición) y entregó el string de Integrity + Units por
categoría (Tab 6 "Rooms Mapping"). El string es solo informativo -- el
formato real de cuenta en Integrity varía por segmento de mercado, no se usa
para parsear revenue por categoría automáticamente (frágil, §10).
"""
# code2 -> (integrity_string de referencia, units)
DATA_BY_CODE2 = {
    "01": ("4000-0110-003-001-001-15-01", 6),  # Corcovado Deluxe Villas, King bed
    "02": ("4000-0110-006-001-001-15-02", 2),  # Carate Deluxe Villa Double Beds
    "03": ("4000-0110-006-001-001-15-03", 4),  # Agujas Villa 2 Queen Beds
    "04": ("4000-0110-006-001-001-15-04", 8),  # Sirena Suites, Queen Bed (connecting)
    "05": ("4000-0110-003-001-001-15-05", 5),  # Treehouse king bed
    "06": ("4000-0110-003-001-001-15-06", 5),  # 5 Elements Treehouse king bed
}


def upgrade() -> None:
    op.add_column('dim_room_category', sa.Column('integrity_string', sa.Text(), nullable=True))
    op.add_column('dim_room_category', sa.Column('units', sa.Integer(), nullable=True))
    conn = op.get_bind()
    for code2, (integrity_string, units) in DATA_BY_CODE2.items():
        conn.execute(sa.text(
            "UPDATE dim_room_category SET integrity_string = :s, units = :u WHERE code2 = :c2"
        ), {"s": integrity_string, "u": units, "c2": code2})


def downgrade() -> None:
    op.drop_column('dim_room_category', 'units')
    op.drop_column('dim_room_category', 'integrity_string')
