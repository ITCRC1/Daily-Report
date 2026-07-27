"""fact_bill + fact_bill_line (folios de Opera — detalle auxiliar del Guest Ledger)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fact_bill (
          id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          property_id       UUID NOT NULL REFERENCES dim_property(id),
          business_date     DATE NOT NULL,
          bill_no           TEXT,
          bill_type         TEXT,
          status            TEXT,
          guest_internal_id TEXT,
          guest_name        TEXT,
          total_amount      NUMERIC(15,2) NOT NULL DEFAULT 0
        );
        CREATE INDEX ix_bill_bdate ON fact_bill (business_date);
        CREATE INDEX ix_bill_no    ON fact_bill (bill_no);

        CREATE TABLE fact_bill_line (
          id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          property_id    UUID NOT NULL REFERENCES dim_property(id),
          business_date  DATE NOT NULL,
          bill_no        TEXT,
          trx_code       TEXT,
          trx_date       TEXT,
          net_amount     NUMERIC(15,2) NOT NULL DEFAULT 0,
          debit_amount   NUMERIC(15,2) NOT NULL DEFAULT 0,
          credit_amount  NUMERIC(15,2) NOT NULL DEFAULT 0
        );
        CREATE INDEX ix_billline_bdate ON fact_bill_line (business_date);
        CREATE INDEX ix_billline_no    ON fact_bill_line (bill_no);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fact_bill_line CASCADE")
    op.execute("DROP TABLE IF EXISTS fact_bill CASCADE")
