"""trial_balance + ledger_balance + city_ledger (Tab 2.2 fuente oficial, Tab 2.3
saldos desde Trial Balance, detalle AR desde City Ledger)

Revision ID: a1b2c3d4e5f6
Revises: 79cf14911f74
Create Date: 2026-07-06 18:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '79cf14911f74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fact_trial_balance",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("trx_type", sa.Text(), nullable=True),
        sa.Column("trx_type_desc", sa.Text(), nullable=True),
        sa.Column("tcode", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tb_amount", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("net_amount", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("guest_ledger", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("package_ledger", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("ar_ledger", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("deposit_ledger", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fact_trial_balance_business_date"), "fact_trial_balance", ["business_date"], unique=False)
    op.create_index(op.f("ix_fact_trial_balance_tcode"), "fact_trial_balance", ["tcode"], unique=False)
    op.create_index(op.f("ix_fact_trial_balance_trx_type"), "fact_trial_balance", ["trx_type"], unique=False)

    op.create_table(
        "fact_ledger_balance",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("ledger", sa.Text(), nullable=False),
        sa.Column("opening", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("debit", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("credit", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("closing", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_id", "business_date", "ledger"),
    )
    op.create_index(op.f("ix_fact_ledger_balance_business_date"), "fact_ledger_balance", ["business_date"], unique=False)

    op.create_table(
        "fact_city_ledger",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("trx_code", sa.Text(), nullable=True),
        sa.Column("transaction_type", sa.Text(), nullable=True),
        sa.Column("bill_no", sa.Text(), nullable=True),
        sa.Column("invoice_no", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), server_default="0", nullable=False),
        sa.Column("customer_internal_id", sa.Text(), nullable=True),
        sa.Column("account_name", sa.Text(), nullable=True),
        sa.Column("account_number", sa.Text(), nullable=True),
        sa.Column("confirmation_no", sa.Text(), nullable=True),
        sa.Column("arrival_date", sa.Text(), nullable=True),
        sa.Column("departure_date", sa.Text(), nullable=True),
        sa.Column("guest_name", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["property_id"], ["dim_property.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fact_city_ledger_business_date"), "fact_city_ledger", ["business_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fact_city_ledger_business_date"), table_name="fact_city_ledger")
    op.drop_table("fact_city_ledger")
    op.drop_index(op.f("ix_fact_ledger_balance_business_date"), table_name="fact_ledger_balance")
    op.drop_table("fact_ledger_balance")
    op.drop_index(op.f("ix_fact_trial_balance_trx_type"), table_name="fact_trial_balance")
    op.drop_index(op.f("ix_fact_trial_balance_tcode"), table_name="fact_trial_balance")
    op.drop_index(op.f("ix_fact_trial_balance_business_date"), table_name="fact_trial_balance")
    op.drop_table("fact_trial_balance")
