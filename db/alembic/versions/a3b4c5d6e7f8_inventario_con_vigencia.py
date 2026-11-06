# -*- coding: utf-8 -*-
"""El inventario de habitaciones pasa a tener VIGENCIA (30 -> 33 el 2027-02-01)

El owner confirmó el 2026-11-06 que CWL pasa de 30 a 33 unidades el 2027-02-01:
entra una categoría nueva, SH07 "Villas Deluxe", de 3 unidades.

Por qué no alcanzaba con editar el número
------------------------------------------
El inventario vivía en UN valor sin fecha (`app_config.total_rooms`, default
30) y es el divisor de Occupancy% y RevPAR en todos los reportes. Editarlo de
30 a 33 para que febrero 2027 saliera bien recalculaba el histórico entero
contra 33 en el mismo instante: el Occ% de 2026 bajaba ~9%, el RevPAR se movía,
y no saltaba ningún error -- los reportes seguían cuadrando igual de bien. Una
cifra que cambia sola y en silencio es el modo de falla más caro del sistema.

Esta migración guarda el inventario en tramos (desde, unidades), de modo que
agregar el inventario de 2027 no toca ni un día ya cerrado. Ver
`app/engine/inventory.py` y `tests/test_inventario_vigencia.py`.

La fila SH07 se crea con `opera_short_desc` y `room_class` en NULL A PROPÓSITO:
son las llaves con las que se une al XML de Opera y todavía no están dadas de
alta ahí. Inventarlas sería peor que dejarlas vacías -- si el string no calza
letra por letra, el revenue de esas villas cae en "Otros" sin que nadie lo
note. Se completan cuando Opera tenga la categoría configurada.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-11-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fecha "desde siempre" del primer tramo. El hotel abrió mucho después, pero el
# tramo tiene que cubrir cualquier fecha que un reporte pida hacia atrás sin
# quedarse sin inventario vigente.
_DESDE_SIEMPRE = "2000-01-01"
_DESDE_33 = "2027-02-01"


def upgrade() -> None:
    op.create_table(
        "dim_inventario_tramo",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("property_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dim_property.id"), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("unidades", sa.Integer(), nullable=False),
        sa.Column("nota", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("property_id", "desde", name="uq_inventario_tramo_prop_desde"),
    )
    op.create_index("ix_invtramo_prop", "dim_inventario_tramo", ["property_id"])
    op.create_index("ix_invtramo_desde", "dim_inventario_tramo", ["desde"])

    op.create_table(
        "dim_categoria_unidades_tramo",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                  primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("property_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dim_property.id"), nullable=False),
        sa.Column("room_category_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dim_room_category.id"), nullable=False),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("unidades", sa.Integer(), nullable=False),
        sa.Column("nota", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("room_category_id", "desde", name="uq_cat_unidades_tramo_cat_desde"),
    )
    op.create_index("ix_cattramo_prop", "dim_categoria_unidades_tramo", ["property_id"])
    op.create_index("ix_cattramo_cat", "dim_categoria_unidades_tramo", ["room_category_id"])

    # --- tramo "desde siempre": el numero que YA regia, sin cambiar nada -----
    # Sale del app_config de cada propiedad (no un 30 a ciegas: otra propiedad
    # podria tener otro inventario). Si el valor guardado no es un entero, cae
    # al 30 que el codigo usaba como default.
    op.execute(
        "INSERT INTO dim_inventario_tramo (property_id, desde, unidades, nota) "
        "SELECT p.id, DATE '" + _DESDE_SIEMPRE + "', "
        "       COALESCE((SELECT c.value::int FROM app_config c "
        "                 WHERE c.property_id = p.id AND c.key = 'total_rooms' "
        # Solo digitos, sin anclar con $: asyncpg lee el $ como marcador de
        # parametro y la misma sentencia tiene que servir para los dos drivers.
        "                   AND c.value <> '' AND c.value !~ '[^0-9]'), 30), "
        "       'Backfill del app_config.total_rooms que regia sin fecha. "
        "No cambia ninguna cifra ya publicada.' "
        "FROM dim_property p "
        "ON CONFLICT ON CONSTRAINT uq_inventario_tramo_prop_desde DO NOTHING"
    )

    # --- tramo nuevo: 33 unidades desde feb-2027, solo CWL -------------------
    op.execute(
        "INSERT INTO dim_inventario_tramo (property_id, desde, unidades, nota) "
        "SELECT p.id, DATE '" + _DESDE_33 + "', 33, "
        "       'Owner 2026-11-06: entran 3 unidades (categoria SH07 Villas Deluxe).' "
        "FROM dim_property p WHERE p.code = 'COWLCR' "
        "ON CONFLICT ON CONSTRAINT uq_inventario_tramo_prop_desde DO NOTHING"
    )

    # --- categoria nueva SH07, en CERO unidades por ahora --------------------
    # units = 0 (no 3) porque hoy esas villas no existen: poner 3 en la columna
    # sin fecha es justo el error que esta migracion viene a cerrar. El 3 vive
    # en el tramo de abajo, fechado.
    op.execute(
        "INSERT INTO dim_room_category "
        "       (property_id, code2, report_name, opera_short_desc, room_class, integrity_string, units) "
        "SELECT p.id, '07', 'Villas Deluxe', NULL, NULL, NULL, 0 "
        "FROM dim_property p WHERE p.code = 'COWLCR' "
        "ON CONFLICT (property_id, code2) DO NOTHING"
    )

    # --- tramos por categoria: el estado de hoy, sin mover nada --------------
    op.execute(
        "INSERT INTO dim_categoria_unidades_tramo "
        "       (property_id, room_category_id, desde, unidades, nota) "
        "SELECT rc.property_id, rc.id, DATE '" + _DESDE_SIEMPRE + "', COALESCE(rc.units, 0), "
        "       'Backfill de dim_room_category.units, que regia sin fecha.' "
        "FROM dim_room_category rc "
        "ON CONFLICT ON CONSTRAINT uq_cat_unidades_tramo_cat_desde DO NOTHING"
    )

    op.execute(
        "INSERT INTO dim_categoria_unidades_tramo "
        "       (property_id, room_category_id, desde, unidades, nota) "
        "SELECT rc.property_id, rc.id, DATE '" + _DESDE_33 + "', 3, "
        "       'Owner 2026-11-06: 3 villas nuevas. Falta darla de alta en Opera "
        "(opera_short_desc, room_class).' "
        "FROM dim_room_category rc JOIN dim_property p ON p.id = rc.property_id "
        "WHERE p.code = 'COWLCR' AND rc.code2 = '07' "
        "ON CONFLICT ON CONSTRAINT uq_cat_unidades_tramo_cat_desde DO NOTHING"
    )


def downgrade() -> None:
    # La categoria SH07 la creo esta migracion: se va con ella (sus tramos
    # primero, por la FK).
    op.execute(
        "DELETE FROM dim_categoria_unidades_tramo t "
        "USING dim_room_category rc, dim_property p "
        "WHERE t.room_category_id = rc.id AND rc.property_id = p.id "
        "  AND p.code = 'COWLCR' AND rc.code2 = '07'"
    )
    op.execute(
        "DELETE FROM dim_room_category rc USING dim_property p "
        "WHERE rc.property_id = p.id AND p.code = 'COWLCR' AND rc.code2 = '07'"
    )
    op.drop_index("ix_cattramo_cat", table_name="dim_categoria_unidades_tramo")
    op.drop_index("ix_cattramo_prop", table_name="dim_categoria_unidades_tramo")
    op.drop_table("dim_categoria_unidades_tramo")
    op.drop_index("ix_invtramo_desde", table_name="dim_inventario_tramo")
    op.drop_index("ix_invtramo_prop", table_name="dim_inventario_tramo")
    op.drop_table("dim_inventario_tramo")
