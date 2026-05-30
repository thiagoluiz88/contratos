from .config import DB_HOST, DB_NAME, DB_PORT, DB_USER
from .database import init_db


if __name__ == "__main__":
    init_db()
    print(f"Banco de dados inicializado em {DB_HOST}:{DB_PORT}/{DB_NAME} com usuario {DB_USER}")
