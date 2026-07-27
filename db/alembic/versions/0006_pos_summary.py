"""fact_pos_summary — agregados del día del Excel de Ventas Simphony (sub-tab 2.9).

fact_pos_check (mig 0001) ya guarda el detalle por check. Faltan los totales
de la hoja 'Resumen Ejecutivo' (ventas_netas, cargos_servicio, total_ventas,
voids) y de 'Mapeo Simphony → Opera' (room_charge_confirmado) — no son
re-derivables de fact_pos_check porque salen de hojas distintas del mismo
Excel, no de la lista de checks.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-01
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fact_pos_summary (
          id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          property_id              UUID NOT NULL REFERENCES dim_property(id),
          business_date            DATE NOT NULL,
          source_file              TEXT,
          ventas_netas             NUMERIC(15,2) NOT NULL DEFAULT 0,
          cargos_servicio          NUMERIC(15,2) NOT NULL DEFAULT 0,
          total_ventas             NUMERIC(15,2) NOT NULL DEFAULT 0,
          voids                    NUMERIC(15,2) NOT NULL DEFAULT 0,
          room_charge_confirmado   NUMERIC(15,2) NOT NULL DEFAULT 0,
          UNIQUE (property_id, business_date)
        );
        CREATE INDEX ix_possummary_bdate ON fact_pos_summary (business_date);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fact_pos_summary CASCADE")
