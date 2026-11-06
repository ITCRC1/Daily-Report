# -*- coding: utf-8 -*-
"""fact_otb_daily: revenue, pax y la tarifa del archivo Only Rooms

La hoja History and Forecast (hoja 3 del reporte a dueños) necesita seis
columnas por día: Date, Total Occ, Occ.%, Total Revenue, ADR Rooms Only y PAX.
De esas, el OTB sólo guardaba las habitaciones vendidas y las disponibles --
`history_forecast_daily()` leía el XML entero y tiraba el resto, y además
descartaba el segundo archivo (Only Rooms), que es de donde sale la tarifa.

Se agregan cuatro columnas:
  revenue        REVENUE del archivo Full       -> Total Revenue del Forecast
  persons        NO_PERSONS del archivo Full    -> PAX
  rooms_revenue  REVENUE del Only Rooms         -> para el ADR del subtotal
  adr            CF_AVERAGE_ROOM_RATE Only Rooms-> ADR Rooms Only del día

`rooms_revenue` va además del `adr` porque el ADR de un subtotal es un promedio
PONDERADO (Σ revenue de habitación / Σ noches vendidas), no el promedio de los
ADR de cada día.

Los snapshots YA cargados quedan en 0 en las cuatro: el dato no está en la base,
está en el XML. Para que un snapshot viejo traiga Forecast hay que volver a
subirlo. No se rellena con nada -- un 0 se ve, un número inventado no.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-11-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = ("revenue", "persons", "rooms_revenue", "adr")


def upgrade() -> None:
    for col in _COLS:
        op.add_column(
            "fact_otb_daily",
            sa.Column(col, sa.Numeric(15, 2), server_default="0", nullable=False),
        )


def downgrade() -> None:
    for col in reversed(_COLS):
        op.drop_column("fact_otb_daily", col)
