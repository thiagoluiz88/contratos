from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import ENABLE_SELF_REGISTRATION, MAX_UPLOAD_SIZE_BYTES, UPLOAD_DIR
from app.database import SessionLocal
from app.main import app
from app.models import AccessProfile, AuthAuditEvent, Contract, ImportBatch, Operator, User
from app.services.auth import (
    PROFILE_ADMIN,
    PROFILE_AUDIT,
    PROFILE_CONTRACTS,
    PROFILE_FINANCIAL,
    PROFILE_READ_ONLY,
    hash_password,
)


PASSWORD = "Security!1234"


def expect(response, status: int, action: str) -> None:
    if response.status_code != status:
        raise RuntimeError(f"{action}: esperado HTTP {status}, recebido {response.status_code}: {response.text[:300]}")


def login(client: TestClient, username: str) -> None:
    response = client.post("/login", data={"username": username, "password": PASSWORD}, follow_redirects=False)
    expect(response, 303, f"login de {username}")


def main() -> None:
    marker = f"SEC-{uuid4().hex[:10]}"
    usernames: dict[str, str] = {}
    contract_ids: list[int] = []
    stored_paths: list[Path] = []

    error_path = f"/__security-test-error-{marker}"

    async def security_test_error():
        raise RuntimeError("sensitive-test-detail")

    app.add_api_route(error_path, security_test_error, methods=["GET"])

    db = SessionLocal()
    try:
        for profile_name in (PROFILE_ADMIN, PROFILE_READ_ONLY, PROFILE_CONTRACTS, PROFILE_AUDIT, PROFILE_FINANCIAL):
            profile = db.query(AccessProfile).filter(AccessProfile.name == profile_name).one()
            username = f"{marker}-{profile_name}".lower().replace(" ", "-")
            usernames[profile_name] = username
            db.add(
                User(
                    username=username,
                    email=f"{username}@example.local",
                    password_hash=hash_password(PASSWORD),
                    full_name=f"Teste {profile_name}",
                    access_profile_id=profile.id,
                    is_active=True,
                )
            )
        inactive_profile = AccessProfile(name=f"Inactive {marker}", is_active=False)
        db.add(inactive_profile)
        db.flush()
        db.add(User(username=f"inactive-{marker}", email=f"inactive-{marker}@example.local", password_hash=hash_password(PASSWORD), access_profile_id=inactive_profile.id, is_active=True))
        db.add(User(username=f"disabled-{marker}", email=f"disabled-{marker}@example.local", password_hash=hash_password(PASSWORD), access_profile_id=db.query(AccessProfile).filter(AccessProfile.name == PROFILE_ADMIN).one().id, is_active=False))
        db.commit()
    finally:
        db.close()

    try:
        with TestClient(app) as anonymous:
            expect(anonymous.get("/dashboard", follow_redirects=False), 303, "usuário sem login")
            expect(anonymous.post("/login", data={"username": "none", "password": "none"}), 403, "CSRF sem origem/token")
            anonymous.headers["Origin"] = "http://testserver"
            expect(anonymous.post("/login", data={"username": f"disabled-{marker}", "password": PASSWORD}), 400, "usuário inativo")
            expect(anonymous.post("/login", data={"username": f"inactive-{marker}", "password": PASSWORD}), 400, "perfil inativo")
            register_response = anonymous.post(
                "/register",
                data={"full_name": "Fraco", "email": f"weak-{marker}@example.local", "username": f"weak-{marker}", "password": "123", "password_confirm": "123"},
            )
            expect(register_response, 400 if ENABLE_SELF_REGISTRATION else 403, "politica de cadastro publico")
        with TestClient(app, raise_server_exceptions=False) as error_client:
            response = error_client.get(error_path)
            expect(response, 500, "página amigável de erro")
            assert "sensitive-test-detail" not in response.text

        matrix = [
            (PROFILE_READ_ONLY, "/contracts/import", 403),
            (PROFILE_READ_ONLY, "/contracts/999999/edit", 403),
            (PROFILE_READ_ONLY, "/contracts/999999/delete", 403),
            (PROFILE_CONTRACTS, "/users", 403),
            (PROFILE_CONTRACTS, "/access-profiles", 403),
            (PROFILE_AUDIT, "/users", 403),
            (PROFILE_AUDIT, "/access-profiles", 403),
            (PROFILE_FINANCIAL, "/auth-audit-events", 403),
        ]
        for profile_name, path, status in matrix:
            with TestClient(app, headers={"Origin": "http://testserver"}) as client:
                login(client, usernames[profile_name])
                if path == "/contracts/import":
                    response = client.post(
                        path,
                        data={"operator_name": marker, "import_mode": "contract"},
                        files={"file": ("blocked.txt", BytesIO(b"blocked"), "text/plain")},
                        follow_redirects=False,
                    )
                else:
                    response = client.post(path, follow_redirects=False) if path.endswith(("/edit", "/delete")) else client.get(path)
                expect(response, status, f"autorização {profile_name} em {path}")

        with TestClient(app, headers={"Origin": "http://testserver"}) as admin:
            login_response = admin.post("/login", data={"username": usernames[PROFILE_ADMIN], "password": PASSWORD}, follow_redirects=False)
            expect(login_response, 303, "login administrativo")
            cookie = login_response.headers.get("set-cookie", "").lower()
            assert "httponly" in cookie and "samesite=lax" in cookie and "max-age=28800" in cookie
            logout_response = admin.get("/logout", follow_redirects=False)
            expect(logout_response, 303, "logout administrativo")
            expect(admin.get("/dashboard", follow_redirects=False), 303, "sessão limpa após logout")
            login(admin, usernames[PROFILE_ADMIN])

            response = admin.post(
                "/contracts/import",
                data={"operator_name": marker, "import_mode": "contract"},
                files={"file": ("malware.exe", BytesIO(b"MZ executable"), "application/octet-stream")},
            )
            expect(response, 400, "bloqueio de executável")

            response = admin.post(
                "/contracts/import",
                data={"operator_name": marker, "import_mode": "contract"},
                files={"file": ("large.txt", BytesIO(b"A" * (MAX_UPLOAD_SIZE_BYTES + 1)), "text/plain")},
            )
            expect(response, 400, "bloqueio de arquivo grande")

            response = admin.post(
                "/contracts/import",
                data={"operator_name": marker, "import_mode": "contract"},
                files={"file": ("../../traversal.txt", BytesIO(b"Contrato seguro para teste"), "text/plain")},
            )
            expect(response, 200, "upload com nome de path traversal")
            contract_ids.append(response.json()["id"])

        db = SessionLocal()
        try:
            contract = db.query(Contract).filter(Contract.id == contract_ids[0]).one()
            assert contract.original_filename == "traversal.txt"
            assert Path(contract.stored_filepath).resolve().is_relative_to(UPLOAD_DIR.resolve())
            stored_paths.append(Path(contract.stored_filepath))
            assert db.query(AuthAuditEvent).filter(AuthAuditEvent.event_type.in_(["login", "login_failed"])).count() > 0
        finally:
            db.close()

        assert ".env" in Path(".gitignore").read_text(encoding="utf-8")
        launchers = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in [Path("scripts/start_system.ps1"), Path("Abrir Sistema.bat")])
        assert "127.0.0.1" in launchers and "--reload" not in launchers
        print("AUDITORIA DE SEGURANCA: OK")
    finally:
        db = SessionLocal()
        try:
            db.query(Contract).filter(Contract.id.in_(contract_ids)).delete(synchronize_session=False)
            db.query(ImportBatch).filter(ImportBatch.original_filename.like(f"%{marker}%")).delete(synchronize_session=False)
            db.query(User).filter(User.username.like(f"%{marker.lower()}%")).delete(synchronize_session=False)
            db.query(AccessProfile).filter(AccessProfile.name == f"Inactive {marker}").delete(synchronize_session=False)
            operator = db.query(Operator).filter(Operator.name == marker).first()
            if operator and not operator.contracts:
                db.delete(operator)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        for path in stored_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    main()
