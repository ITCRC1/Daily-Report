"""audit_finding_dedupe_and_resolution

Revision ID: 8349a6796586
Revises: 90759c1e7ff5
Create Date: 2026-07-02 05:29:35.551452

Agrega dedupe_key (identidad estable de un hallazgo dentro de property+día,
para poder hacer upsert en cada re-auditoría sin pisar estado/resolved_note)
+ resolved_note/resolved_at (comentario amplio al cerrar/cambiar estado).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8349a6796586'
down_revision: Union[str, None] = '90759c1e7ff5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit_finding', sa.Column('dedupe_key', sa.Text(), nullable=True))
    op.add_column('audit_finding', sa.Column('resolved_note', sa.Text(), nullable=True))
    op.add_column('audit_finding', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))

    # backfill de filas existentes (previas a este cambio) con la misma
    # fórmula que va a usar el servicio de acá en más.
    op.execute("""
        UPDATE audit_finding
        SET dedupe_key = COALESCE(source_view, '') || '|' || COALESCE(area, '') || '|'
                          || COALESCE(tcode, '') || '|' || COALESCE(tipo_desviacion, '')
        WHERE dedupe_key IS NULL
    """)

    op.create_unique_constraint(
        'uq_audit_finding_property_date_dedupe',
        'audit_finding', ['property_id', 'business_date', 'dedupe_key'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_audit_finding_property_date_dedupe', 'audit_finding', type_='unique')
    op.drop_column('audit_finding', 'resolved_at')
    op.drop_column('audit_finding', 'resolved_note')
    op.drop_column('audit_finding', 'dedupe_key')
