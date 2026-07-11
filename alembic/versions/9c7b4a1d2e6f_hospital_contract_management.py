"""hospital contract management adaptation

Revision ID: 9c7b4a1d2e6f
Revises: f8a1c2d3e4b5
Create Date: 2026-07-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "9c7b4a1d2e6f"
down_revision: Union[str, Sequence[str], None] = "f8a1c2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE operators ADD COLUMN IF NOT EXISTS notes TEXT NULL")

    op.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS parent_contract_id INTEGER NULL")
    op.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS contract_type VARCHAR(100) NULL")
    op.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'active'")
    op.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS reajust_percentage NUMERIC(8, 4) NULL")
    op.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS base_date DATE NULL")
    op.execute("ALTER TABLE contracts ADD COLUMN IF NOT EXISTS observations TEXT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contracts_parent_contract_id ON contracts (parent_contract_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contracts_contract_type ON contracts (contract_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contracts_status ON contracts (status)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_contracts_parent_contract_id_contracts'
            ) THEN
                ALTER TABLE contracts
                ADD CONSTRAINT fk_contracts_parent_contract_id_contracts
                FOREIGN KEY (parent_contract_id) REFERENCES contracts(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE contract_adjustments ADD COLUMN IF NOT EXISTS adjustment_date DATE NULL")
    op.execute("ALTER TABLE contract_adjustments ADD COLUMN IF NOT EXISTS justification TEXT NULL")
    op.execute("ALTER TABLE contract_adjustments ADD COLUMN IF NOT EXISTS document_file_id INTEGER NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_adjustments_document_file_id ON contract_adjustments (document_file_id)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_contract_adjustments_document_file_id_contract_files'
            ) THEN
                ALTER TABLE contract_adjustments
                ADD CONSTRAINT fk_contract_adjustments_document_file_id_contract_files
                FOREIGN KEY (document_file_id) REFERENCES contract_files(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_terms (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            category VARCHAR(80) NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT NULL,
            reference_value NUMERIC(12, 2) NULL,
            deadline_days INTEGER NULL,
            rule_text TEXT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            valid_from DATE NULL,
            valid_until DATE NULL,
            is_current BOOLEAN NOT NULL DEFAULT TRUE,
            source_type VARCHAR(50) NULL,
            source_document_id INTEGER NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_terms_id ON contract_terms (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_terms_contract_id ON contract_terms (contract_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_terms_category ON contract_terms (category)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_terms_is_current ON contract_terms (is_current)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_terms_source_type ON contract_terms (source_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_terms_source_document_id ON contract_terms (source_document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_terms_status ON contract_terms (status)")
    op.execute("ALTER TABLE contract_terms ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE contract_terms ADD COLUMN IF NOT EXISTS valid_from DATE NULL")
    op.execute("ALTER TABLE contract_terms ADD COLUMN IF NOT EXISTS valid_until DATE NULL")
    op.execute("ALTER TABLE contract_terms ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("ALTER TABLE contract_terms ADD COLUMN IF NOT EXISTS source_type VARCHAR(50) NULL")
    op.execute("ALTER TABLE contract_terms ADD COLUMN IF NOT EXISTS source_document_id INTEGER NULL")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_contract_terms_source_document_id_contract_files'
            ) THEN
                ALTER TABLE contract_terms
                ADD CONSTRAINT fk_contract_terms_source_document_id_contract_files
                FOREIGN KEY (source_document_id) REFERENCES contract_files(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )

    op.execute("ALTER TABLE contract_files ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) NOT NULL DEFAULT 'pending'")
    op.execute("ALTER TABLE contract_files ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITHOUT TIME ZONE NULL")
    op.execute("ALTER TABLE contract_files ADD COLUMN IF NOT EXISTS notes TEXT NULL")
    op.execute("ALTER TABLE contract_files ADD COLUMN IF NOT EXISTS error_message TEXT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_files_processing_status ON contract_files (processing_status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
            username VARCHAR(100) NULL,
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(80) NULL,
            entity_id INTEGER NULL,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            ip_address VARCHAR(80) NULL,
            user_agent TEXT NULL,
            details TEXT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_id ON audit_logs (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_username ON audit_logs (username)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs (entity_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_id ON audit_logs (entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_success ON audit_logs (success)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)")

    op.execute(
        """
        UPDATE access_profiles
        SET name = CASE name
            WHEN 'Administrator' THEN 'Administrador'
            WHEN 'Executive Board' THEN 'Diretoria'
            WHEN 'Contracts' THEN 'Contratos'
            WHEN 'Financial' THEN 'Financeiro'
            WHEN 'Audit' THEN 'Auditoria'
            WHEN 'Read Only' THEN 'Somente leitura'
            ELSE name
        END,
        description = CASE name
            WHEN 'Administrator' THEN 'Acesso administrativo completo.'
            WHEN 'Executive Board' THEN 'Visao executiva para diretoria.'
            WHEN 'Contracts' THEN 'Gestao operacional de contratos.'
            WHEN 'Financial' THEN 'Analise financeira e condicoes comerciais.'
            WHEN 'Audit' THEN 'Auditoria e conformidade.'
            WHEN 'Read Only' THEN 'Acesso somente leitura.'
            ELSE description
        END,
        updated_at = NOW()
        WHERE name IN ('Administrator', 'Executive Board', 'Contracts', 'Financial', 'Audit', 'Read Only')
        """
    )
    op.execute(
        """
        INSERT INTO access_profiles (name, description, is_active, created_at, updated_at)
        VALUES
            ('Administrador', 'Acesso administrativo completo.', true, NOW(), NOW()),
            ('Diretoria', 'Visao executiva para diretoria.', true, NOW(), NOW()),
            ('Contratos', 'Gestao operacional de contratos.', true, NOW(), NOW()),
            ('Financeiro', 'Analise financeira e condicoes comerciais.', true, NOW(), NOW()),
            ('Auditoria', 'Auditoria e conformidade.', true, NOW(), NOW()),
            ('Somente leitura', 'Acesso somente leitura.', true, NOW(), NOW())
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs")
    op.execute("DROP TABLE IF EXISTS contract_terms")
    op.execute("DROP INDEX IF EXISTS ix_contract_files_processing_status")
    op.execute("ALTER TABLE contract_files DROP COLUMN IF EXISTS error_message")
    op.execute("ALTER TABLE contract_files DROP COLUMN IF EXISTS notes")
    op.execute("ALTER TABLE contract_files DROP COLUMN IF EXISTS processed_at")
    op.execute("ALTER TABLE contract_files DROP COLUMN IF EXISTS processing_status")
    op.execute("ALTER TABLE contract_adjustments DROP CONSTRAINT IF EXISTS fk_contract_adjustments_document_file_id_contract_files")
    op.execute("DROP INDEX IF EXISTS ix_contract_adjustments_document_file_id")
    op.execute("ALTER TABLE contract_adjustments DROP COLUMN IF EXISTS document_file_id")
    op.execute("ALTER TABLE contract_adjustments DROP COLUMN IF EXISTS justification")
    op.execute("ALTER TABLE contract_adjustments DROP COLUMN IF EXISTS adjustment_date")
    op.execute("DROP INDEX IF EXISTS ix_contracts_status")
    op.execute("DROP INDEX IF EXISTS ix_contracts_contract_type")
    op.execute("ALTER TABLE contracts DROP CONSTRAINT IF EXISTS fk_contracts_parent_contract_id_contracts")
    op.execute("DROP INDEX IF EXISTS ix_contracts_parent_contract_id")
    op.execute("ALTER TABLE contracts DROP COLUMN IF EXISTS observations")
    op.execute("ALTER TABLE contracts DROP COLUMN IF EXISTS base_date")
    op.execute("ALTER TABLE contracts DROP COLUMN IF EXISTS reajust_percentage")
    op.execute("ALTER TABLE contracts DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE contracts DROP COLUMN IF EXISTS contract_type")
    op.execute("ALTER TABLE contracts DROP COLUMN IF EXISTS parent_contract_id")
    op.execute("ALTER TABLE operators DROP COLUMN IF EXISTS notes")
