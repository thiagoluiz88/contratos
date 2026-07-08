"""add extraction apply tracking

Revision ID: 4b8c1d2e3f90
Revises: 3a5d7e9c2b41
Create Date: 2026-07-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "4b8c1d2e3f90"
down_revision: Union[str, Sequence[str], None] = "3a5d7e9c2b41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS apply_status VARCHAR(50) NOT NULL DEFAULT 'pendente'")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS applied_by VARCHAR(100) NULL")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS applied_at TIMESTAMP NULL")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS apply_summary JSON NULL")
    op.execute("ALTER TABLE contract_extractions ADD COLUMN IF NOT EXISTS apply_error TEXT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_extractions_apply_status ON contract_extractions (apply_status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_contract_extractions_apply_status")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS apply_error")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS apply_summary")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS applied_at")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS applied_by")
    op.execute("ALTER TABLE contract_extractions DROP COLUMN IF EXISTS apply_status")
