"""ledger_opening (anclaje manual de saldo de apertura de ledgers)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE ledger_opening (
          id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          property_id    UUID NOT NULL REFERENCES dim_property(id),
          ledger         TEXT NOT NULL,           -- guest|package|ar|deposit
          effective_date DATE NOT NULL,
          amount         NUMERIC(15,2) NOT NULL DEFAULT 0,
          note           TEXT,
          created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (property_id, ledger, effective_date)
        );
        CREATE INDEX ix_ledopen_eff ON ledger_opening (effective_date);
        CREATE TRIGGER t_ledopen_upd BEFORE UPDATE ON ledger_opening
          FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ledger_opening CASCADE")
