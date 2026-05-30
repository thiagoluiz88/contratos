"""initial

Revision ID: 5bdcdc88aa12
Revises: 
Create Date: 2026-05-30 12:17:49.253878

"""
from typing import Sequence, Union

from alembic import op
from app.database import Base
from app import models  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '5bdcdc88aa12'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    Base.metadata.drop_all(bind=op.get_bind())
