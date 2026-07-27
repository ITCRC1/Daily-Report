"""fact_fb_covers: cubiertos (comensales) por outlet F&B x meal period x dia (Tab 9.5)

Reemplaza en granularidad al contador manual unico por dia que vivia en
app_config (`fb_customers:YYYY-MM-DD`). Ese contador legacy se mantiene como
fallback: si un dia no tiene ninguna fila aca, 9.5 sigue usandolo.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fact_fb_covers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("property_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dim_property.id"), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False, index=True),
        sa.Column("outlet", sa.Text(), nullable=False),
        sa.Column("meal_period", sa.Text(), nullable=False),
        sa.Column("covers", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("property_id", "business_date", "outlet", "meal_period",
                            name="uq_fb_covers_cell"),
    )


def downgrade() -> None:
    op.drop_table("fact_fb_covers")
