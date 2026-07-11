"""migrate authentication to users

Revision ID: f8a1c2d3e4b5
Revises: d24610c09828
Create Date: 2026-06-01 14:40:00.000000

"""
from typing import Sequence, Union
import os

import bcrypt
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "f8a1c2d3e4b5"
down_revision: Union[str, Sequence[str], None] = "d24610c09828"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_audit_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
            username VARCHAR(100) NULL,
            event_type VARCHAR(50) NOT NULL,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            ip_address VARCHAR(80) NULL,
            user_agent TEXT NULL,
            notes TEXT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_audit_events_id ON auth_audit_events (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_audit_events_user_id ON auth_audit_events (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_audit_events_username ON auth_audit_events (username)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_audit_events_event_type ON auth_audit_events (event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_audit_events_success ON auth_audit_events (success)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_auth_audit_events_created_at ON auth_audit_events (created_at)")

    op.execute(
        """
        INSERT INTO access_profiles (name, description, is_active, created_at, updated_at)
        VALUES ('Administrator', 'Full administrative access.', true, NOW(), NOW())
        ON CONFLICT (name) DO UPDATE
        SET is_active = true,
            updated_at = NOW()
        """
    )
    initial_password = os.getenv("INITIAL_ADMIN_PASSWORD")
    if not initial_password:
        raise RuntimeError("Defina INITIAL_ADMIN_PASSWORD antes de aplicar a migration de autenticação.")
    password_hash = bcrypt.hashpw(initial_password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    op.get_bind().execute(
        text(
            """
        INSERT INTO users (access_profile_id, username, email, password_hash, full_name, is_active, created_at, updated_at)
        SELECT access_profiles.id, 'admin', 'admin@contracts.local', :password_hash, 'Administrador', true, NOW(), NOW()
        FROM access_profiles
        WHERE access_profiles.name = 'Administrator'
        ON CONFLICT (username) DO UPDATE
        SET access_profile_id = EXCLUDED.access_profile_id,
            is_active = true,
            updated_at = NOW()
        """
        ),
        {"password_hash": password_hash},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM users WHERE username = 'admin' AND email = 'admin@contracts.local'")
    op.execute("DROP TABLE IF EXISTS auth_audit_events")
