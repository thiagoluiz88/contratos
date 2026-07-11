from io import BytesIO

import pytest

from app.database import SessionLocal
from app.models import AuditLog, Contract, Operator, ProductionImportBatch, ProductionRecord
from app.services.production_import_service import cancel_import_batch, create_import_batch, import_csv_to_batch, parse_csv


CSV_HEADER = "operadora;contrato;competencia;data_atendimento;categoria;item;descricao;quantidade;unidade;valor_faturado;valor_pago;valor_glosado;custo;guia;conta;atendimento;paciente_referencia\n"


def create_operator_contract(marker):
    db = SessionLocal()
    try:
        operator = Operator(name=f"Operadora Produção {marker}", tax_id="12.345.678/0001-99", is_active=True)
        db.add(operator)
        db.flush()
        contract = Contract(contract_name=f"{marker}-PRODUCAO", contract_number=f"CTR-{marker}", operator_id=operator.id, operator_name=operator.name, status="active")
        db.add(contract)
        db.commit()
        return operator.id, contract.id, operator.name, contract.contract_number
    finally:
        db.close()


@pytest.mark.integration
def test_csv_import_valid_invalid_resolution_and_totals(cleanup_marker, tmp_path):
    operator_id, contract_id, operator_name, contract_number = create_operator_contract(cleanup_marker)
    path = tmp_path / "production.csv"
    path.write_text(CSV_HEADER + f"12.345.678/0001-99;{contract_number};2026-07;10/07/2026;taxa;Sala;Taxa de sala;2;evento;200,00;180,00;20,00;80,00;G1;C1;A1;REF-1\n" + "Não localizada;Contrato ausente;competencia-invalida;;taxa;;Linha inválida;0;evento;abc;;;;;;;REF-2\n", encoding="utf-8")
    assert len(parse_csv(path)) == 2
    batch, _ = create_import_batch(batch_name=f"Lote {cleanup_marker}", original_filename=path.name, file_path=str(path), imported_by=cleanup_marker.lower())
    processed, events = import_csv_to_batch(batch.id, path)
    assert processed.import_status == "processado"
    assert (processed.total_rows, processed.valid_rows, processed.invalid_rows) == (2, 1, 1)
    assert any(event.action == "production_record_invalid_detected" for event in events)
    db = SessionLocal()
    try:
        valid = db.query(ProductionRecord).filter(ProductionRecord.batch_id == batch.id, ProductionRecord.validation_status == "valido").one()
        invalid = db.query(ProductionRecord).filter(ProductionRecord.batch_id == batch.id, ProductionRecord.validation_status == "pendente").one()
        assert valid.operator_id == operator_id and valid.contract_id == contract_id
        assert valid.patient_identifier_hash and "REF-1" not in valid.patient_identifier_hash
        assert (valid.billed_value, valid.paid_value, valid.denied_value, valid.cost_value) == (200, 180, 20, 80)
        assert invalid.contract_id is None and invalid.validation_message
        assert valid.source_row_number == 2 and invalid.source_row_number == 3
    finally:
        db.close()
    with pytest.raises(ValueError, match="reprocessamento"):
        import_csv_to_batch(batch.id, path)
    with pytest.raises(ValueError, match="Somente lote"):
        cancel_import_batch(batch.id)


@pytest.mark.integration
def test_pending_batch_can_be_cancelled(cleanup_marker):
    batch, _ = create_import_batch(batch_name=f"Cancelar {cleanup_marker}", source_type="manual")
    cancelled, events = cancel_import_batch(batch.id, cancelled_by=cleanup_marker.lower())
    assert cancelled.import_status == "cancelado"
    assert events[0].action == "production_import_batch_cancelled"


@pytest.mark.integration
def test_routes_csv_permissions_and_audit(admin_client, readonly_client, cleanup_marker, admin_username):
    _, _, operator_name, contract_number = create_operator_contract(cleanup_marker)
    content = CSV_HEADER + f"{operator_name};{contract_number};2026-07;2026-07-10;taxa;Sala;Taxa;2;evento;200;180;20;80;;;;REF\n"
    response = admin_client.post("/production/imports", data={"batch_name": f"Rota {cleanup_marker}", "source_system": "planilha"}, files={"file": ("producao.csv", BytesIO(content.encode()), "text/csv")}, follow_redirects=False)
    assert response.status_code == 303
    batch_id = int(response.headers["location"].split("/")[-1])
    assert admin_client.get("/production/imports").status_code == 200
    assert admin_client.get(f"/production/imports/{batch_id}").status_code == 200
    assert admin_client.get("/production/records").status_code == 200
    exported = admin_client.get("/production/records/export")
    assert exported.status_code == 200 and "text/csv" in exported.headers["content-type"] and "Sala" in exported.text
    assert readonly_client.get("/production/records", follow_redirects=False).status_code == 403
    assert readonly_client.get("/production/imports/new", follow_redirects=False).status_code == 403
    db = SessionLocal()
    try:
        actions = {row.action for row in db.query(AuditLog).filter(AuditLog.username == admin_username).all()}
        assert {"production_import_batch_created", "production_import_file_received", "production_import_batch_processed", "production_records_viewed", "production_records_exported"} <= actions
    finally:
        db.close()


def test_production_routes_require_authentication():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        for path in ("/production/imports", "/production/imports/new", "/production/records", "/production/records/export"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 303 and response.headers["location"] == "/login"

