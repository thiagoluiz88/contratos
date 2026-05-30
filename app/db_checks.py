from __future__ import annotations

from sqlalchemy import text

from .database import engine


def check_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def check_persistence() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS db_health_check (id INTEGER PRIMARY KEY, value TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO db_health_check (id, value) VALUES (1, 'inserted') ON CONFLICT (id) DO UPDATE SET value = EXCLUDED.value"))
        value = connection.execute(text("SELECT value FROM db_health_check WHERE id = 1")).scalar_one()
        if value != "inserted":
            raise RuntimeError("Falha ao validar SELECT no PostgreSQL.")
        connection.execute(text("UPDATE db_health_check SET value = 'updated' WHERE id = 1"))
        value = connection.execute(text("SELECT value FROM db_health_check WHERE id = 1")).scalar_one()
        if value != "updated":
            raise RuntimeError("Falha ao validar UPDATE no PostgreSQL.")
        connection.execute(text("DELETE FROM db_health_check WHERE id = 1"))


if __name__ == "__main__":
    check_connection()
    check_persistence()
    print("Conexao e persistencia PostgreSQL OK.")
