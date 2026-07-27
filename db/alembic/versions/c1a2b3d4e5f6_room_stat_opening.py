"""room_stat_opening (anclaje manual editable de acumulado YTD por categoría de habitación)

Revision ID: c1a2b3d4e5f6
Revises: 30b220d5aec1
Create Date: 2026-07-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "30b220d5aec1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "room_stat_opening",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("room_category", sa.Text(), nullable=False),
        sa.Column("anchor_date", sa.Date(), nullable=False),
        sa.Column("revenue", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("stay_rooms", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("stay_persons", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("physical_rooms", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id", "room_category"),
    )
    op.create_index(op.f("ix_room_stat_opening_anchor_date"), "room_stat_opening", ["anchor_date"], unique=False)
    op.execute(
        "CREATE TRIGGER t_room_stat_opening_upd BEFORE UPDATE ON room_stat_opening "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS t_room_stat_opening_upd ON room_stat_opening")
    op.drop_index(op.f("ix_room_stat_opening_anchor_date"), table_name="room_stat_opening")
    op.drop_table("room_stat_opening")
