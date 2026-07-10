"""add production import layouts

Revision ID: b7e3f1a6c920
Revises: a4f7c2d9e810
"""
from alembic import op

revision = "b7e3f1a6c920"
down_revision = "a4f7c2d9e810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE IF NOT EXISTS production_import_layouts (
        id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL, source_system VARCHAR(50) NOT NULL DEFAULT 'planilha',
        source_type VARCHAR(50) NOT NULL DEFAULT 'csv', delimiter VARCHAR(10), encoding VARCHAR(50),
        has_header BOOLEAN NOT NULL DEFAULT true, status VARCHAR(50) NOT NULL DEFAULT 'rascunho',
        created_by VARCHAR(100), created_at TIMESTAMP NOT NULL DEFAULT now(), updated_at TIMESTAMP NOT NULL DEFAULT now(), notes TEXT)""")
    for column in ("id", "name", "source_system", "source_type", "status", "created_at"):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_production_import_layouts_{column} ON production_import_layouts ({column})")
    op.execute("""CREATE TABLE IF NOT EXISTS production_import_layout_mappings (
        id SERIAL PRIMARY KEY, layout_id INTEGER NOT NULL REFERENCES production_import_layouts(id) ON DELETE CASCADE,
        target_field VARCHAR(80) NOT NULL, source_column VARCHAR(255) NOT NULL, required BOOLEAN NOT NULL DEFAULT false,
        default_value TEXT, transform_rule VARCHAR(80), created_at TIMESTAMP NOT NULL DEFAULT now())""")
    for column in ("id", "layout_id", "target_field"):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_production_import_layout_mappings_{column} ON production_import_layout_mappings ({column})")
    op.execute("ALTER TABLE production_import_batches ADD COLUMN IF NOT EXISTS layout_id INTEGER REFERENCES production_import_layouts(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE production_import_batches ADD COLUMN IF NOT EXISTS import_summary_json JSON")
    op.execute("CREATE INDEX IF NOT EXISTS ix_production_import_batches_layout_id ON production_import_batches (layout_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_production_import_batches_layout_id")
    op.execute("ALTER TABLE production_import_batches DROP COLUMN IF EXISTS import_summary_json")
    op.execute("ALTER TABLE production_import_batches DROP COLUMN IF EXISTS layout_id")
    op.execute("DROP TABLE IF EXISTS production_import_layout_mappings")
    op.execute("DROP TABLE IF EXISTS production_import_layouts")
