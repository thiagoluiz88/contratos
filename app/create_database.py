from __future__ import annotations

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from .config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


def ensure_database() -> None:
    connection = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
    )
    connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
            exists = cursor.fetchone() is not None
            if not exists:
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
    finally:
        connection.close()


if __name__ == "__main__":
    ensure_database()
    print(f"Banco {DB_NAME} verificado/criado em {DB_HOST}:{DB_PORT}.")
