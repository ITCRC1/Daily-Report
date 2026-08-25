"""forecast_monthly + fact_forecast (Tab 6.1.1 Forecast)

El Forecast es el gemelo del Budget (Tab 6.1): mensual por departamento,
cargado con el mismo ciclo plantilla → llenar offline → subir → reemplazo total
del año, y con el diario DERIVADO igual que `fact_budget` (mensual ÷ días del
mes, residual de redondeo al último día para que Σ diarios = mensual exacto).

Va en tablas propias en vez de una columna `kind` sobre budget_monthly: así el
reemplazo anual de uno no puede pisar al otro, y `fact_budget` — que ya consumen
revenue, Tab 9 y el OTB — no cambia de forma. ADITIVA: no toca nada existente.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-25 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotente a propósito: en el deploy de Railway la raíz del build del
    # backend es `backend/`, así que alembic no llega al contenedor y las tablas
    # las crea el arranque del app (`db.ensure_forecast_schema`). Correr esta
    # migración después, contra una base ya inicializada así, no debe fallar.
    existentes = set(sa.inspect(op.get_bind()).get_table_names())

    if "forecast_monthly" not in existentes:
        _crear_forecast_monthly()
    if "fact_forecast" not in existentes:
        _crear_fact_forecast()


def _crear_forecast_monthly() -> None:
    op.create_table(
        "forecast_monthly",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("property_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dim_property.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("dept_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dim_department.id")),
        sa.Column("amount_usd", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("available_rooms", sa.Numeric(15, 2)),
        sa.Column("rooms_occupied", sa.Numeric(15, 2)),
        sa.Column("guests", sa.Numeric(15, 2)),
        sa.Column("occupancy_pct", sa.Numeric(9, 4)),
        sa.Column("adr", sa.Numeric(15, 2)),
        sa.Column("food", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("beverage", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("misc", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_fcstmon_month"),
    )
    op.create_index("ix_fcstmon_prop", "forecast_monthly", ["property_id"])
    op.create_index("ix_fcstmon_dept", "forecast_monthly", ["dept_id"])


# derivado = forecast_monthly / días_del_mes; residual → último día
def _crear_fact_forecast() -> None:
    op.create_table(
        "fact_forecast",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("property_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dim_property.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("dept_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dim_department.id")),
        sa.Column("amount_usd", sa.Numeric(15, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_factfcst_date", "fact_forecast", ["date"])
    op.create_index("ix_factfcst_prop", "fact_forecast", ["property_id"])
    op.create_index("ix_factfcst_dept", "fact_forecast", ["dept_id"])


def downgrade() -> None:
    op.drop_table("fact_forecast")
    op.drop_table("forecast_monthly")
