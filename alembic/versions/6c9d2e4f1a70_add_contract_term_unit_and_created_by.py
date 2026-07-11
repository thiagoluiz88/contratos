"""add contract term unit and created by

Revision ID: 6c9d2e4f1a70
Revises: 4b8c1d2e3f90
Create Date: 2026-07-08 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "6c9d2e4f1a70"
down_revision: Union[str, Sequence[str], None] = "4b8c1d2e3f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contract_terms ADD COLUMN IF NOT EXISTS unit VARCHAR(80) NULL")
    op.execute("ALTER TABLE contract_terms ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_terms_unit ON contract_terms (unit)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_contract_terms_unit")
    op.execute("ALTER TABLE contract_terms DROP COLUMN IF EXISTS created_by")
    op.execute("ALTER TABLE contract_terms DROP COLUMN IF EXISTS unit")
