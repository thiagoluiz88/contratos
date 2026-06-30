from alembic import command
from alembic.config import Config

from .config import BASE_DIR, DB_HOST, DB_NAME, DB_PORT, DB_USER
from .create_database import ensure_database


if __name__ == "__main__":
    ensure_database()
    alembic_cfg = Config(str(BASE_DIR / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    print(f"Banco de dados migrado em {DB_HOST}:{DB_PORT}/{DB_NAME} com usuario {DB_USER}")
