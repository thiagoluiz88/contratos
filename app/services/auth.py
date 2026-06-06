from __future__ import annotations

import bcrypt
import os
import re
from sqlalchemy.orm import Session

from app.models import AccessProfile, AuthAuditEvent, User


INITIAL_ADMIN_EMAIL = "admin@contracts.local"
INITIAL_ADMIN_NAME = "Administrador"
INITIAL_ADMIN_USERNAME = "admin"
PROFILE_ADMIN = "Administrator"
PROFILE_EXECUTIVE = "Executive Board"
PROFILE_CONTRACTS = "Contracts"
PROFILE_FINANCIAL = "Financial"
PROFILE_AUDIT = "Audit"
PROFILE_READ_ONLY = "Read Only"
INITIAL_ADMIN_PROFILE = PROFILE_ADMIN
DEFAULT_REGISTER_PROFILE = PROFILE_READ_ONLY
BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")
MIN_PASSWORD_LENGTH = 10
ADMIN_PROFILES = {PROFILE_ADMIN}
CONTRACT_WRITE_PROFILES = {PROFILE_ADMIN, PROFILE_CONTRACTS}
ADDITIVE_VIEW_PROFILES = {PROFILE_ADMIN, PROFILE_CONTRACTS, PROFILE_AUDIT}
ANALYSIS_VIEW_PROFILES = {PROFILE_ADMIN, PROFILE_CONTRACTS, PROFILE_AUDIT, PROFILE_READ_ONLY}
ANALYSIS_WRITE_PROFILES = {PROFILE_ADMIN, PROFILE_CONTRACTS, PROFILE_AUDIT}
FINANCIAL_PROFILES = {PROFILE_ADMIN, PROFILE_FINANCIAL}
AUDIT_PROFILES = {PROFILE_ADMIN, PROFILE_AUDIT}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def validate_password_strength(password: str) -> str | None:
    if not password:
        return "A senha nao pode ficar vazia."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
    if not re.search(r"[A-Z]", password):
        return "A senha deve conter pelo menos uma letra maiúscula."
    if not re.search(r"[a-z]", password):
        return "A senha deve conter pelo menos uma letra minúscula."
    if not re.search(r"\d", password):
        return "A senha deve conter pelo menos um número."
    if not re.search(r"[^A-Za-z0-9]", password):
        return "A senha deve conter pelo menos um caractere especial."
    return None


def is_bcrypt_hash(password_hash: str | None) -> bool:
    return bool(password_hash and password_hash.startswith(BCRYPT_PREFIXES))


def upgrade_legacy_password_hashes(db: Session) -> int:
    upgraded = 0
    for user in db.query(User).all():
        if not is_bcrypt_hash(user.password_hash):
            user.password_hash = hash_password(user.password_hash)
            upgraded += 1
    return upgraded


def get_access_profile(db: Session, name: str) -> AccessProfile | None:
    return db.query(AccessProfile).filter(AccessProfile.name == name, AccessProfile.is_active.is_(True)).first()


def user_session_payload(user: User) -> dict:
    profile_name = user.access_profile.name if user.access_profile else None
    return {
        "id": user.id,
        "username": user.username,
        "name": user.full_name or user.username,
        "role": profile_name or "Usuario",
        "access_profile": profile_name,
        "access_profile_id": user.access_profile_id,
    }


def has_profile(session_user: dict | None, allowed_profiles: set[str]) -> bool:
    profile_name = (session_user or {}).get("access_profile") or (session_user or {}).get("role")
    return profile_name in allowed_profiles


def record_auth_event(
    db: Session,
    event_type: str,
    *,
    user: User | None = None,
    username: str | None = None,
    request=None,
    success: bool = True,
    notes: str | None = None,
) -> None:
    client_host = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    db.add(
        AuthAuditEvent(
            user_id=user.id if user else None,
            username=username or (user.username if user else None),
            event_type=event_type,
            success=success,
            ip_address=client_host,
            user_agent=user_agent,
            notes=notes,
        )
    )


def ensure_initial_admin(db: Session) -> None:
    profile = get_access_profile(db, INITIAL_ADMIN_PROFILE)
    if not profile:
        profile = AccessProfile(
            name=INITIAL_ADMIN_PROFILE,
            description="Full administrative access.",
            is_active=True,
        )
        db.add(profile)
        db.flush()

    admin = db.query(User).filter(User.username == INITIAL_ADMIN_USERNAME).first()
    if admin:
        if admin.access_profile_id is None:
            admin.access_profile_id = profile.id
        return

    initial_password = os.getenv("INITIAL_ADMIN_PASSWORD")
    if not initial_password:
        raise RuntimeError("Defina INITIAL_ADMIN_PASSWORD no .env para criar o administrador inicial.")
    password_error = validate_password_strength(initial_password)
    if password_error:
        raise RuntimeError(f"INITIAL_ADMIN_PASSWORD inválida: {password_error}")

    db.add(
        User(
            username=INITIAL_ADMIN_USERNAME,
            email=INITIAL_ADMIN_EMAIL,
            password_hash=hash_password(initial_password),
            full_name=INITIAL_ADMIN_NAME,
            access_profile_id=profile.id,
            is_active=True,
        )
    )
