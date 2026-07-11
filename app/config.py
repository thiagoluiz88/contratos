from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SESSION_SECRET = os.getenv("APP_SECRET", "")
SESSION_HTTPS_ONLY = env_bool("SESSION_HTTPS_ONLY", False)
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", "28800"))
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(20 * 1024 * 1024)))
ENABLE_SELF_REGISTRATION = env_bool("ENABLE_SELF_REGISTRATION", False)
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_PUBLIC_HOST = os.getenv("APP_PUBLIC_HOST", APP_HOST)

if len(SESSION_SECRET) < 32 or SESSION_SECRET in {"contracts-intelligence-session-secret", "troque-esta-chave-por-uma-chave-forte"}:
    raise RuntimeError("APP_SECRET deve ser uma chave aleatoria forte com pelo menos 32 caracteres.")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "contratos_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not DB_PASSWORD or DB_PASSWORD in {"definir_no_env_local", "defina_no_arquivo_env_local", "<definir_no_.env>"}:
    raise RuntimeError("DB_PASSWORD deve ser definido no arquivo .env ou nas variaveis de ambiente.")

DATABASE_URL = (
    f"postgresql+psycopg2://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads" / "contracts"))
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
