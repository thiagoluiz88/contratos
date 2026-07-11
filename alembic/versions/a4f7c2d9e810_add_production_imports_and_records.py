"""add production imports and records

Revision ID: a4f7c2d9e810
Revises: 9e2a7b6c5d40
Create Date: 2026-07-10 00:00:00.000000
"""

from alembic import op


revision = "a4f7c2d9e810"
down_revision = "9e2a7b6c5d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS production_import_batches (
            id SERIAL PRIMARY KEY,
            batch_name VARCHAR(255) NOT NULL,
            source_type VARCHAR(50) NOT NULL DEFAULT 'csv',
            source_system VARCHAR(50) NOT NULL DEFAULT 'planilha',
            original_filename VARCHAR(255),
            file_path VARCHAR(500),
            import_status VARCHAR(50) NOT NULL DEFAULT 'pendente',
            imported_by VARCHAR(100),
            imported_at TIMESTAMP NOT NULL DEFAULT now(),
            processed_at TIMESTAMP,
            total_rows INTEGER NOT NULL DEFAULT 0,
            valid_rows INTEGER NOT NULL DEFAULT 0,
            invalid_rows INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            notes TEXT
        )
    """)
    for column in ("id", "batch_name", "source_type", "source_system", "import_status", "imported_by", "imported_at"):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_production_import_batches_{column} ON production_import_batches ({column})")
    op.execute("""
        CREATE TABLE IF NOT EXISTS production_records (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER NOT NULL REFERENCES production_import_batches(id) ON DELETE RESTRICT,
            operator_id INTEGER REFERENCES operators(id) ON DELETE SET NULL,
            contract_id INTEGER REFERENCES contracts(id) ON DELETE SET NULL,
            patient_identifier_hash VARCHAR(128),
            attendance_reference VARCHAR(120),
            account_reference VARCHAR(120),
            guide_reference VARCHAR(120),
            service_date DATE,
            competence_month DATE,
            category VARCHAR(80),
            item VARCHAR(255),
            description TEXT,
            quantity NUMERIC(14, 4),
            unit VARCHAR(80),
            billed_value NUMERIC(14, 2),
            paid_value NUMERIC(14, 2),
            denied_value NUMERIC(14, 2),
            cost_value NUMERIC(14, 2),
            source_row_number INTEGER NOT NULL,
            validation_status VARCHAR(50) NOT NULL DEFAULT 'pendente',
            validation_message TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    for column in ("id", "batch_id", "operator_id", "contract_id", "patient_identifier_hash", "attendance_reference", "account_reference", "guide_reference", "service_date", "competence_month", "category", "item", "unit", "validation_status", "created_at"):
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_production_records_{column} ON production_records ({column})")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS production_records")
    op.execute("DROP TABLE IF EXISTS production_import_batches")
