"""fact_opera_txn_detail (trx por market_code / room_class)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-01

Nueva tabla para el pivote 'Ingresos x Market Code' y el desglose por room class.
A partir de la 0001 (baseline en db/schema.sql), los cambios van como migraciones
incrementales; los modelos ORM son la fuente de verdad.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fact_opera_txn_detail (
          id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          property_id        UUID NOT NULL REFERENCES dim_property(id),
          business_date      DATE NOT NULL,
          tcode              TEXT,
          description        TEXT,
          type               TEXT,
          market_code        TEXT,
          room_class         TEXT,
          trx_amount         NUMERIC(15,2) NOT NULL DEFAULT 0,
          trx_guest_ledger   NUMERIC(15,2) NOT NULL DEFAULT 0,
          trx_package_ledger NUMERIC(15,2) NOT NULL DEFAULT 0
        );
        CREATE INDEX ix_operadet_bdate ON fact_opera_txn_detail (business_date);
        CREATE INDEX ix_operadet_prop  ON fact_opera_txn_detail (property_id);
        CREATE INDEX ix_operadet_tcode ON fact_opera_txn_detail (tcode);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fact_opera_txn_detail CASCADE")
