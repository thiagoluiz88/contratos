from .config import DATABASE_URL
from .database import init_db


if __name__ == "__main__":
    init_db()
    print(f"Banco de dados inicializado em {DATABASE_URL}")
