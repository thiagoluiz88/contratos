"""normalize document status defaults

Revision ID: 7b6e2c4f9a10
Revises: 2f4c8a9b1d3e
Create Date: 2026-07-03 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "7b6e2c4f9a10"
down_revision: Union[str, Sequence[str], None] = "2f4c8a9b1d3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contract_files ALTER COLUMN processing_status SET DEFAULT 'pendente'")
    op.execute("ALTER TABLE contract_extractions ALTER COLUMN extraction_status SET DEFAULT 'pendente'")
    op.execute("ALTER TABLE contract_extractions ALTER COLUMN review_status SET DEFAULT 'pendente'")
    op.execute("UPDATE contract_files SET processing_status = 'pendente' WHERE processing_status = 'pending'")
    op.execute("UPDATE contract_extractions SET extraction_status = 'pendente' WHERE extraction_status = 'pending'")
    op.execute("UPDATE contract_extractions SET review_status = 'pendente' WHERE review_status = 'pending'")


def downgrade() -> None:
    op.execute("ALTER TABLE contract_files ALTER COLUMN processing_status SET DEFAULT 'pending'")
    op.execute("ALTER TABLE contract_extractions ALTER COLUMN extraction_status SET DEFAULT 'pending'")
    op.execute("ALTER TABLE contract_extractions ALTER COLUMN review_status SET DEFAULT 'pending'")
