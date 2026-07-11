from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AccessProfile, AuditLog, Contract, CostCenter, Operator, ProductionImportBatch, ProductionImportLayout, ProductionRecord, ReferenceTable, User
from app.services.auth import PROFILE_ADMIN, PROFILE_READ_ONLY, hash_password


TEST_PASSWORD = "Tests!12345"


@pytest.fixture
def marker():
    return f"PYTEST-{uuid4().hex[:12]}"


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def cleanup_marker(marker):
    yield marker
    db = SessionLocal()
    try:
        # AuditLog usa referencia logica para entidades; remova-o explicitamente.
        db.query(AuditLog).filter(AuditLog.username.like(f"%{marker.lower()}%")).delete(synchronize_session=False)
        batch_rows = db.query(ProductionImportBatch.id, ProductionImportBatch.file_path).filter(ProductionImportBatch.batch_name.like(f"%{marker}%")).all()
        batch_ids = [row[0] for row in batch_rows]
        if batch_ids:
            db.query(ProductionRecord).filter(ProductionRecord.batch_id.in_(batch_ids)).delete(synchronize_session=False)
            db.query(ProductionImportBatch).filter(ProductionImportBatch.id.in_(batch_ids)).delete(synchronize_session=False)
        db.query(ProductionImportLayout).filter(ProductionImportLayout.name.like(f"%{marker}%")).delete(synchronize_session=False)
        db.query(CostCenter).filter(CostCenter.name.like(f"%{marker}%")).delete(synchronize_session=False)
        contract_ids = [row[0] for row in db.query(Contract.id).filter(Contract.contract_name.like(f"%{marker}%")).all()]
        if contract_ids:
            db.query(Contract).filter(Contract.id.in_(contract_ids)).delete(synchronize_session=False)
        db.query(ReferenceTable).filter(ReferenceTable.name.like(f"%{marker}%")).delete(synchronize_session=False)
        db.query(User).filter(User.username.like(f"%{marker.lower()}%")).delete(synchronize_session=False)
        db.query(Operator).filter(Operator.name.like(f"%{marker}%")).delete(synchronize_session=False)
        db.commit()
        for _, file_path in batch_rows:
            if file_path and "uploads" in Path(file_path).parts:
                Path(file_path).unlink(missing_ok=True)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture
def contract_factory(cleanup_marker):
    created_ids: list[int] = []

    def create(*, suffix: str = "CONTRATO", **fields) -> int:
        db = SessionLocal()
        try:
            contract = Contract(contract_name=f"{cleanup_marker}-{suffix}", operator_name=f"Operadora {cleanup_marker}", **fields)
            db.add(contract)
            db.commit()
            created_ids.append(contract.id)
            return contract.id
        finally:
            db.close()

    return create


def _create_user(marker: str, profile_name: str) -> str:
    username = f"{marker}-{profile_name}".lower().replace(" ", "-")
    db = SessionLocal()
    try:
        profile = db.query(AccessProfile).filter(AccessProfile.name == profile_name).one()
        db.add(User(username=username, email=f"{username}@example.local", password_hash=hash_password(TEST_PASSWORD), full_name="Usuario pytest", access_profile_id=profile.id, is_active=True))
        db.commit()
        return username
    finally:
        db.close()


@pytest.fixture
def admin_username(cleanup_marker):
    return _create_user(cleanup_marker, PROFILE_ADMIN)


@pytest.fixture
def readonly_username(cleanup_marker):
    return _create_user(cleanup_marker, PROFILE_READ_ONLY)


def login(client: TestClient, username: str) -> None:
    client.headers["Origin"] = "http://testserver"
    response = client.post("/login", data={"username": username, "password": TEST_PASSWORD}, follow_redirects=False)
    assert response.status_code == 303, response.text


@pytest.fixture
def admin_client(admin_username):
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        login(client, admin_username)
        yield client


@pytest.fixture
def readonly_client(readonly_username):
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        login(client, readonly_username)
        yield client
