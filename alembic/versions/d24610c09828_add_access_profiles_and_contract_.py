"""add access profiles and contract support tables

Revision ID: d24610c09828
Revises: 5bdcdc88aa12
Create Date: 2026-05-30 12:33:45.441374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd24610c09828'
down_revision: Union[str, Sequence[str], None] = '5bdcdc88aa12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The initial revision historically used Base.metadata.create_all(), so a
    # fresh database may already have these tables before this revision runs.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS access_profiles (
            id SERIAL PRIMARY KEY,
            name VARCHAR(120) NOT NULL UNIQUE,
            description TEXT NULL,
            is_active BOOLEAN NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_access_profiles_id ON access_profiles (id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_access_profiles_name ON access_profiles (name)")
    op.execute(
        """
        INSERT INTO access_profiles (name, description, is_active, created_at, updated_at)
        VALUES
            ('Administrator', 'Full administrative access.', true, NOW(), NOW()),
            ('Executive Board', 'Executive visibility for strategic indicators.', true, NOW(), NOW()),
            ('Contracts', 'Contract management and operational access.', true, NOW(), NOW()),
            ('Financial', 'Financial analysis and remuneration table access.', true, NOW(), NOW()),
            ('Audit', 'Audit and compliance review access.', true, NOW(), NOW()),
            ('Read Only', 'Read-only access to contract information.', true, NOW(), NOW())
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contract_adjustments (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            reference_year INTEGER NOT NULL,
            adjustment_index VARCHAR(100) NULL,
            applied_percentage NUMERIC(8, 4) NULL,
            requested_percentage NUMERIC(8, 4) NULL,
            request_date DATE NULL,
            approval_date DATE NULL,
            status VARCHAR(50) NOT NULL,
            notes TEXT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_adjustments_contract_id ON contract_adjustments (contract_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_adjustments_id ON contract_adjustments (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_adjustments_reference_year ON contract_adjustments (reference_year)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_contract_adjustments_status ON contract_adjustments (status)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS materials_medicines_rules (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            item_type VARCHAR(80) NOT NULL,
            billing_reference VARCHAR(80) NOT NULL,
            addition_percentage NUMERIC(8, 4) NULL,
            reduction_percentage NUMERIC(8, 4) NULL,
            rule_description TEXT NULL,
            notes TEXT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_materials_medicines_rules_billing_reference ON materials_medicines_rules (billing_reference)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_materials_medicines_rules_contract_id ON materials_medicines_rules (contract_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_materials_medicines_rules_id ON materials_medicines_rules (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_materials_medicines_rules_item_type ON materials_medicines_rules (item_type)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS remuneration_tables (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            table_type VARCHAR(50) NOT NULL,
            reference_source VARCHAR(255) NULL,
            start_date DATE NULL,
            end_date DATE NULL,
            source VARCHAR(100) NULL,
            notes TEXT NULL,
            is_active BOOLEAN NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_remuneration_tables_contract_id ON remuneration_tables (contract_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_remuneration_tables_id ON remuneration_tables (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_remuneration_tables_name ON remuneration_tables (name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_remuneration_tables_table_type ON remuneration_tables (table_type)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS remuneration_table_items (
            id SERIAL PRIMARY KEY,
            remuneration_table_id INTEGER NOT NULL REFERENCES remuneration_tables(id) ON DELETE CASCADE,
            code VARCHAR(100) NULL,
            description TEXT NOT NULL,
            unit VARCHAR(50) NULL,
            current_value NUMERIC(12, 2) NULL,
            proposed_value NUMERIC(12, 2) NULL,
            adjustment_percentage NUMERIC(8, 4) NULL,
            billing_rule TEXT NULL,
            notes TEXT NULL,
            is_active BOOLEAN NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_remuneration_table_items_code ON remuneration_table_items (code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_remuneration_table_items_id ON remuneration_table_items (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_remuneration_table_items_remuneration_table_id ON remuneration_table_items (remuneration_table_id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS negotiation_messages (
            id SERIAL PRIMARY KEY,
            negotiation_opportunity_id INTEGER NOT NULL REFERENCES negotiation_opportunities(id) ON DELETE CASCADE,
            user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
            message_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            channel VARCHAR(50) NOT NULL,
            subject VARCHAR(255) NULL,
            message TEXT NOT NULL,
            contract_file_id INTEGER NULL REFERENCES contract_files(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_negotiation_messages_channel ON negotiation_messages (channel)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_negotiation_messages_contract_file_id ON negotiation_messages (contract_file_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_negotiation_messages_id ON negotiation_messages (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_negotiation_messages_message_date ON negotiation_messages (message_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_negotiation_messages_negotiation_opportunity_id ON negotiation_messages (negotiation_opportunity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_negotiation_messages_user_id ON negotiation_messages (user_id)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS access_profile_id INTEGER NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_access_profile_id ON users (access_profile_id)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_users_access_profile_id_access_profiles'
            ) THEN
                ALTER TABLE users
                ADD CONSTRAINT fk_users_access_profile_id_access_profiles
                FOREIGN KEY (access_profile_id) REFERENCES access_profiles(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute("DELETE FROM contracts WHERE contract_number = 'TEST-PG-LOCAL-001'")
    op.execute(
        """
        DELETE FROM operators
        WHERE name = 'Operadora Teste PostgreSQL'
          AND NOT EXISTS (
              SELECT 1 FROM contracts WHERE contracts.operator_id = operators.id
          )
        """
    )
    op.execute("DROP TABLE IF EXISTS db_health_check")
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('fk_users_access_profile_id_access_profiles', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_access_profile_id'), table_name='users')
    op.drop_column('users', 'access_profile_id')
    op.drop_index(op.f('ix_negotiation_messages_user_id'), table_name='negotiation_messages')
    op.drop_index(op.f('ix_negotiation_messages_negotiation_opportunity_id'), table_name='negotiation_messages')
    op.drop_index(op.f('ix_negotiation_messages_message_date'), table_name='negotiation_messages')
    op.drop_index(op.f('ix_negotiation_messages_id'), table_name='negotiation_messages')
    op.drop_index(op.f('ix_negotiation_messages_contract_file_id'), table_name='negotiation_messages')
    op.drop_index(op.f('ix_negotiation_messages_channel'), table_name='negotiation_messages')
    op.drop_table('negotiation_messages')
    op.drop_index(op.f('ix_remuneration_table_items_remuneration_table_id'), table_name='remuneration_table_items')
    op.drop_index(op.f('ix_remuneration_table_items_id'), table_name='remuneration_table_items')
    op.drop_index(op.f('ix_remuneration_table_items_code'), table_name='remuneration_table_items')
    op.drop_table('remuneration_table_items')
    op.drop_index(op.f('ix_remuneration_tables_table_type'), table_name='remuneration_tables')
    op.drop_index(op.f('ix_remuneration_tables_name'), table_name='remuneration_tables')
    op.drop_index(op.f('ix_remuneration_tables_id'), table_name='remuneration_tables')
    op.drop_index(op.f('ix_remuneration_tables_contract_id'), table_name='remuneration_tables')
    op.drop_table('remuneration_tables')
    op.drop_index(op.f('ix_materials_medicines_rules_item_type'), table_name='materials_medicines_rules')
    op.drop_index(op.f('ix_materials_medicines_rules_id'), table_name='materials_medicines_rules')
    op.drop_index(op.f('ix_materials_medicines_rules_contract_id'), table_name='materials_medicines_rules')
    op.drop_index(op.f('ix_materials_medicines_rules_billing_reference'), table_name='materials_medicines_rules')
    op.drop_table('materials_medicines_rules')
    op.drop_index(op.f('ix_contract_adjustments_status'), table_name='contract_adjustments')
    op.drop_index(op.f('ix_contract_adjustments_reference_year'), table_name='contract_adjustments')
    op.drop_index(op.f('ix_contract_adjustments_id'), table_name='contract_adjustments')
    op.drop_index(op.f('ix_contract_adjustments_contract_id'), table_name='contract_adjustments')
    op.drop_table('contract_adjustments')
    op.drop_index(op.f('ix_access_profiles_name'), table_name='access_profiles')
    op.drop_index(op.f('ix_access_profiles_id'), table_name='access_profiles')
    op.drop_table('access_profiles')
    # ### end Alembic commands ###
