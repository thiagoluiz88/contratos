"""add missing simulation reference id indexes

Revision ID: 9e2a7b6c5d40
Revises: 8d1f2a3b4c50
Create Date: 2026-07-08 00:00:00.000000
"""

from alembic import op


revision = "9e2a7b6c5d40"
down_revision = "8d1f2a3b4c50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_id ON contract_term_simulations (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_tables_id ON reference_tables (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_table_items_id ON reference_table_items (id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_reference_table_items_id")
    op.execute("DROP INDEX IF EXISTS ix_reference_tables_id")
    op.execute("DROP INDEX IF EXISTS ix_contract_term_simulations_id")
