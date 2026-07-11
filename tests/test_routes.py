import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import ContractTerm
from app.services.contract_terms_simulation_service import create_manual_simulation


PROTECTED_PATHS = [
    "/contracts/999999999/terms",
    "/contracts/999999999/terms/versions",
    "/contracts/999999999/terms/compare?from_version=1&to_version=2",
    "/contracts/999999999/terms/simulations",
    "/contracts/999999999/terms/simulations/new",
    "/contracts/999999999/terms/simulations/999999999",
    "/reference-tables",
]


def test_health_and_anonymous_redirects():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        for path in PROTECTED_PATHS:
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"] == "/login"


@pytest.mark.integration
def test_authenticated_module_2_pages(admin_client, contract_factory, cleanup_marker):
    contract_id = contract_factory()
    db = SessionLocal()
    try:
        db.add(ContractTerm(contract_id=contract_id, category="taxa", title="Base", reference_value=10, unit="evento", version=1, is_current=True))
        db.commit()
    finally:
        db.close()
    simulation, _ = create_manual_simulation(contract_id=contract_id, simulation_name=f"Rotas {cleanup_marker}", terms=[{"category": "taxa", "title": "Base", "reference_value": "11", "unit": "evento"}])
    paths = [
        f"/contracts/{contract_id}/terms",
        f"/contracts/{contract_id}/terms/compare?from_version=1&to_version=1",
        f"/contracts/{contract_id}/terms/simulations",
        f"/contracts/{contract_id}/terms/simulations/new",
        f"/contracts/{contract_id}/terms/simulations/{simulation.id}",
        "/reference-tables",
    ]
    for path in paths:
        response = admin_client.get(path, follow_redirects=False)
        assert response.status_code == 200, (path, response.status_code, response.text[:200])
    versions = admin_client.get(f"/contracts/{contract_id}/terms/versions", follow_redirects=False)
    assert versions.status_code == 303
    assert versions.headers["location"] == f"/contracts/{contract_id}/terms"
