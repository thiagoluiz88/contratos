import pytest

from app.database import SessionLocal
from app.models import AuditLog, ContractExtraction, ContractFile, ContractTerm


@pytest.mark.integration
def test_simulation_reference_and_blocked_attempt_audit(admin_client, contract_factory, cleanup_marker, admin_username):
    contract_id = contract_factory()
    db = SessionLocal()
    try:
        db.add(ContractTerm(contract_id=contract_id, category="taxa", title="Base", reference_value=10, unit="evento", version=1, is_current=True))
        db.commit()
    finally:
        db.close()

    response = admin_client.post(
        f"/contracts/{contract_id}/terms/simulations",
        data={"simulation_name": f"Audit {cleanup_marker}", "base_version": "1", "category_1": "taxa", "item_1": "Base", "reference_value_1": "12", "unit_1": "evento"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    simulation_id = int(response.headers["location"].rstrip("/").split("/")[-1])
    blocked = admin_client.post(f"/contracts/{contract_id}/terms/simulations/{simulation_id}/apply", follow_redirects=False)
    assert blocked.status_code == 303
    assert admin_client.post(f"/contracts/{contract_id}/terms/simulations/{simulation_id}/approve", follow_redirects=False).status_code == 303
    assert admin_client.post(f"/contracts/{contract_id}/terms/simulations/{simulation_id}/apply", follow_redirects=False).status_code == 303
    assert admin_client.post("/reference-tables", data={"name": f"Ref {cleanup_marker}", "version": "manual", "status": "active"}, follow_redirects=False).status_code == 303

    db = SessionLocal()
    try:
        document = ContractFile(contract_id=contract_id, original_filename=f"audit-{cleanup_marker}.txt", stored_filepath=f"tests/audit-{cleanup_marker}.txt", file_type="contract", document_type="contrato")
        db.add(document)
        db.flush()
        extraction = ContractExtraction(
            contract_file_id=document.id,
            contract_id=contract_id,
            extraction_status="concluida",
            review_status="aprovado",
            apply_status="pendente",
            reviewed_by=admin_username,
            extracted_json={"contrato": {}, "condicoes_contratuais": [{"categoria": "taxa", "item": "Extraida", "valor": "15", "unidade": "evento"}]},
        )
        db.add(extraction)
        db.commit()
        document_id = document.id
    finally:
        db.close()
    assert admin_client.post(f"/documents/{document_id}/apply", follow_redirects=False).status_code == 303

    expected = {
        "contract_term_simulation_created",
        "contract_term_simulation_apply_without_approval",
        "contract_term_simulation_approved",
        "contract_term_simulation_previous_version_closed",
        "contract_term_simulation_new_official_version_created",
        "contract_term_simulation_applied",
        "reference_table_created",
        "approved_extraction_apply_started",
        "approved_extraction_apply_completed",
    }
    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter(AuditLog.username == admin_username).all()
        actions = {log.action for log in logs}
        assert expected <= actions
        for log in logs:
            if log.action in expected:
                assert log.username == admin_username
                assert log.entity_type
    finally:
        db.close()
