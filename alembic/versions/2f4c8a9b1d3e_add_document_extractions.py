"""add document extraction workflow

Revision ID: 2f4c8a9b1d3e
Revises: 9c7b4a1d2e6f
Create Date: 2026-07-03 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "2f4c8a9b1d3e"
down_revision: Union[str, Sequence[str], None] = "9c7b4a1d2e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contract_files ADD COLUMN IF NOT EXISTS document_type VARCHAR(50) NOT NULL DEFAULT 'contrato'")
    op.execute("ALTER TABLE contract_files ADD COLUMN IF NOT EXISTS approved_by VARCHAR(100) NULL")
    op.execute("ALTER TABLE contract_files ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITHOUT TIME ZONE NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_files_document_type ON contract_files (document_type)")
    op.execute(
        """
        UPDATE contract_files
        SET document_type = CASE
            WHEN file_type = 'additive' THEN 'aditivo'
            WHEN file_type = 'contract' THEN 'contrato'
            ELSE COALESCE(NULLIF(file_type, ''), 'outro')
        END
        WHERE document_type IS NULL OR document_type = 'contrato'
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_extractions (
            id SERIAL PRIMARY KEY,
            contract_file_id INTEGER NOT NULL REFERENCES contract_files(id) ON DELETE CASCADE,
            contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            extraction_status VARCHAR(50) NOT NULL DEFAULT 'pending',
            extracted_json JSON NOT NULL DEFAULT '{}'::json,
            confidence_score DOUBLE PRECISION NULL,
            extraction_source VARCHAR(50) NOT NULL DEFAULT 'manual',
            created_by VARCHAR(100) NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            reviewed_by VARCHAR(100) NULL,
            reviewed_at TIMESTAMP WITHOUT TIME ZONE NULL,
            review_status VARCHAR(50) NOT NULL DEFAULT 'pending',
            review_notes TEXT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_id ON contract_extractions (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_contract_file_id ON contract_extractions (contract_file_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_contract_id ON contract_extractions (contract_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_extraction_status ON contract_extractions (extraction_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_extraction_source ON contract_extractions (extraction_source)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_created_at ON contract_extractions (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_review_status ON contract_extractions (review_status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS contract_extractions")
    op.execute("DROP INDEX IF EXISTS ix_contract_files_document_type")
    op.execute("ALTER TABLE contract_files DROP COLUMN IF EXISTS approved_at")
    op.execute("ALTER TABLE contract_files DROP COLUMN IF EXISTS approved_by")
    op.execute("ALTER TABLE contract_files DROP COLUMN IF EXISTS document_type")
