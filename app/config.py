from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


APP_USER = os.getenv("APP_USER", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "admin123")
APP_USER_NAME = os.getenv("APP_USER_NAME", "Allan Martins")
APP_USER_EMAIL = os.getenv("APP_USER_EMAIL", "admin@contracts.local")
APP_USER_ROLE = os.getenv("APP_USER_ROLE", "Administrador")
SESSION_SECRET = os.getenv("APP_SECRET", "contracts-intelligence-session-secret")
SESSION_HTTPS_ONLY = env_bool("SESSION_HTTPS_ONLY", False)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'contracts.db'}")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads" / "contracts"))
STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
