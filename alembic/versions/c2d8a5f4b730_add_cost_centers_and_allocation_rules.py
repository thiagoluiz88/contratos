"""add cost centers and allocation rules

Revision ID: c2d8a5f4b730
Revises: b7e3f1a6c920
"""
from alembic import op

revision = "c2d8a5f4b730"
down_revision = "b7e3f1a6c920"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE IF NOT EXISTS cost_centers (
        id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, code VARCHAR(100) NOT NULL UNIQUE,
        status VARCHAR(50) NOT NULL DEFAULT 'ativo', notes TEXT, created_by VARCHAR(100),
        created_at TIMESTAMP NOT NULL DEFAULT now(), updated_at TIMESTAMP NOT NULL DEFAULT now())""")
    for column in ("id", "name", "code", "status", "created_at"):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_cost_centers_{column} ON cost_centers ({column})")
    op.execute("""CREATE TABLE IF NOT EXISTS cost_allocation_rules (
        id SERIAL PRIMARY KEY, cost_center_id INTEGER NOT NULL REFERENCES cost_centers(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL, category VARCHAR(80), item VARCHAR(255), allocation_method VARCHAR(50) NOT NULL,
        percentage NUMERIC(8,4), fixed_value NUMERIC(14,2), valid_from DATE NOT NULL, valid_until DATE,
        status VARCHAR(50) NOT NULL DEFAULT 'ativo', created_by VARCHAR(100), created_at TIMESTAMP NOT NULL DEFAULT now(),
        updated_at TIMESTAMP NOT NULL DEFAULT now(), notes TEXT)""")
    for column in ("id", "cost_center_id", "name", "category", "item", "allocation_method", "valid_from", "status", "created_at"):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_cost_allocation_rules_{column} ON cost_allocation_rules ({column})")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cost_allocation_rules")
    op.execute("DROP TABLE IF EXISTS cost_centers")
