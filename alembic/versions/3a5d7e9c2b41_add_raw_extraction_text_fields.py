"""add raw extraction text fields

Revision ID: 3a5d7e9c2b41
Revises: 7b6e2c4f9a10
Create Date: 2026-07-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "3a5d7e9c2b41"
down_revision: Union[str, Sequence[str], None] = "7b6e2c4f9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS extracted_text TEXT NULL")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS extracted_text_preview TEXT NULL")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(80) NULL")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS extraction_warnings TEXT NULL")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS page_count INTEGER NULL")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS character_count INTEGER NOT NULL DEFAULT 0")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_extraction_method ON contract_extractions (extraction_method)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_contract_extractions_extraction_method")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS character_count")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS page_count")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS extraction_warnings")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS extraction_method")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS extracted_text_preview")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS extracted_text")
