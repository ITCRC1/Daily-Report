"""fact_occupancy_stat + fact_otb (sub-tabs 2.4 Estadísticas y 2.5 OTB vs Revenue)

fact_occupancy_stat: registros del XML STATISTICS de Opera (ocupación por
market code / room class / room type). Distinto de fact_room_stat (etapa 5,
que se alimenta del statroomtype con revenue/físicas).

fact_otb: snapshot de los history_forecast (Total vs Rooms Only, §5.6).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fact_occupancy_stat (
          id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          property_id    UUID NOT NULL REFERENCES dim_property(id),
          business_date  DATE NOT NULL,
          market_code    TEXT,
          room_class     TEXT,
          room_type      TEXT,
          rooms          INTEGER NOT NULL DEFAULT 0,
          persons        INTEGER NOT NULL DEFAULT 0,
          noshow_rooms   INTEGER NOT NULL DEFAULT 0,
          cancel_rooms   INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX ix_occstat_bdate ON fact_occupancy_stat (business_date);
        CREATE INDEX ix_occstat_prop  ON fact_occupancy_stat (property_id);

        CREATE TABLE fact_otb (
          id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          property_id     UUID NOT NULL REFERENCES dim_property(id),
          business_date   DATE NOT NULL,
          scope           TEXT NOT NULL CHECK (scope IN ('total', 'rooms')),
          source_file     TEXT,
          revenue         NUMERIC(15,2) NOT NULL DEFAULT 0,
          no_rooms        INTEGER NOT NULL DEFAULT 0,
          no_persons      INTEGER NOT NULL DEFAULT 0,
          inventory_rooms INTEGER NOT NULL DEFAULT 0,
          adr             NUMERIC(15,4) NOT NULL DEFAULT 0,
          occupancy       NUMERIC(9,4)  NOT NULL DEFAULT 0,
          UNIQUE (property_id, business_date, scope)
        );
        CREATE INDEX ix_otb_bdate ON fact_otb (business_date);
        CREATE INDEX ix_otb_prop  ON fact_otb (property_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fact_otb CASCADE")
    op.execute("DROP TABLE IF EXISTS fact_occupancy_stat CASCADE")
