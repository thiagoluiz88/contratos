from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    if not DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_existing_schema()


def ensure_existing_schema():
    inspector = inspect(engine)
    if "contracts" not in inspector.get_table_names():
        return

    contract_columns = {column["name"] for column in inspector.get_columns("contracts")}
    additions = {
        "operator_id": "INTEGER",
        "import_batch_id": "INTEGER",
        "responsible_name": "VARCHAR(255)",
        "contact_info": "VARCHAR(255)",
        "adjustment_type": "VARCHAR(100)",
    }

    with engine.begin() as connection:
        for column_name, column_type in additions.items():
            if column_name not in contract_columns:
                connection.execute(text(f"ALTER TABLE contracts ADD COLUMN {column_name} {column_type}"))
