"""add term simulations and reference tables

Revision ID: 8d1f2a3b4c50
Revises: 6c9d2e4f1a70
Create Date: 2026-07-08 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "8d1f2a3b4c50"
down_revision: Union[str, Sequence[str], None] = "6c9d2e4f1a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_term_simulations (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            source_document_id INTEGER NULL REFERENCES contract_files(id) ON DELETE SET NULL,
            source_extraction_id INTEGER NULL REFERENCES contract_extractions(id) ON DELETE SET NULL,
            simulation_name VARCHAR(255) NOT NULL,
            base_version INTEGER NULL,
            simulated_version INTEGER NULL,
            simulation_status VARCHAR(50) NOT NULL DEFAULT 'rascunho',
            simulated_terms_json JSON NOT NULL DEFAULT '[]',
            comparison_summary_json JSON NULL,
            created_by VARCHAR(100) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            reviewed_by VARCHAR(100) NULL,
            reviewed_at TIMESTAMP NULL,
            applied_by VARCHAR(100) NULL,
            applied_at TIMESTAMP NULL,
            notes TEXT NULL,
            error_message TEXT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_contract_id ON contract_term_simulations (contract_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_id ON contract_term_simulations (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_source_document_id ON contract_term_simulations (source_document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_source_extraction_id ON contract_term_simulations (source_extraction_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_base_version ON contract_term_simulations (base_version)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_simulated_version ON contract_term_simulations (simulated_version)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_simulation_status ON contract_term_simulations (simulation_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_term_simulations_created_at ON contract_term_simulations (created_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reference_tables (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            source VARCHAR(255) NULL,
            version VARCHAR(100) NULL,
            valid_from DATE NULL,
            valid_until DATE NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            created_by VARCHAR(100) NULL,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_tables_name ON reference_tables (name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_tables_id ON reference_tables (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_tables_version ON reference_tables (version)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_tables_status ON reference_tables (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_tables_created_at ON reference_tables (created_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reference_table_items (
            id SERIAL PRIMARY KEY,
            reference_table_id INTEGER NOT NULL REFERENCES reference_tables(id) ON DELETE CASCADE,
            category VARCHAR(80) NULL,
            item VARCHAR(255) NOT NULL,
            description TEXT NULL,
            value NUMERIC(12, 2) NULL,
            unit VARCHAR(80) NULL,
            notes TEXT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_table_items_reference_table_id ON reference_table_items (reference_table_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_table_items_id ON reference_table_items (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_table_items_category ON reference_table_items (category)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_table_items_item ON reference_table_items (item)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reference_table_items_unit ON reference_table_items (unit)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reference_table_items")
    op.execute("DROP TABLE IF EXISTS reference_tables")
    op.execute("DROP TABLE IF EXISTS contract_term_simulations")
