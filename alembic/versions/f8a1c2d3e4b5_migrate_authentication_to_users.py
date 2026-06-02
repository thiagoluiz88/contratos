"""migrate authentication to users

Revision ID: f8a1c2d3e4b5
Revises: d24610c09828
Create Date: 2026-06-01 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f8a1c2d3e4b5"
down_revision: Union[str, Sequence[str], None] = "d24610c09828"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ADMIN_BCRYPT_HASH = "$2b$12$zzGXJDUsBHytu43mxkVSB.Af9jFDpqwROFbsFqj8gtOVEOrHjUhYe"


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
    op.execute(
        f"""
        INSERT INTO users (access_profile_id, username, email, password_hash, full_name, is_active, created_at, updated_at)
        SELECT access_profiles.id, 'admin', 'admin@contracts.local', '{ADMIN_BCRYPT_HASH}', 'Administrador', true, NOW(), NOW()
        FROM access_profiles
        WHERE access_profiles.name = 'Administrator'
        ON CONFLICT (username) DO UPDATE
        SET access_profile_id = EXCLUDED.access_profile_id,
            is_active = true,
            updated_at = NOW()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM users WHERE username = 'admin' AND email = 'admin@contracts.local'")
    op.execute("DROP TABLE IF EXISTS auth_audit_events")
