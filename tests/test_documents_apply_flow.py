from datetime import date

import pytest

from app.database import SessionLocal
from app.models import Contract, ContractExtraction, ContractFile, ContractTerm, Operator
from app.services.approved_extraction_apply_service import apply_approved_extraction


@pytest.mark.integration
def test_approved_extraction_application_is_idempotent_and_preserves_fields(contract_factory, cleanup_marker):
    contract_id = contract_factory(contract_number="PRESERVAR-123")
    db = SessionLocal()
    try:
        db.add(ContractTerm(contract_id=contract_id, category="taxa", title="Anterior", reference_value=10, unit="evento", version=1, valid_from=date(2025, 1, 1), is_current=True))
        document = ContractFile(contract_id=contract_id, original_filename=f"{cleanup_marker}.txt", stored_filepath=f"tests/{cleanup_marker}.txt", file_type="contract", document_type="contrato")
        db.add(document)
        db.flush()
        extraction = ContractExtraction(
            contract_file_id=document.id,
            contract_id=contract_id,
            extraction_status="concluida",
            review_status="aprovado",
            apply_status="pendente",
            reviewed_by=cleanup_marker.lower(),
            extracted_json={
                "contrato": {"operadora": f"Operadora {cleanup_marker}", "razao_social": f"Operadora {cleanup_marker} SA", "cnpj": f"TEST-{cleanup_marker}", "numero_contrato": "NAO-SOBRESCREVER"},
                "condicoes_contratuais": [{"categoria": "taxa", "item": "Nova", "valor": "25,00", "unidade": "evento", "vigencia_inicio": "2026-01-01"}],
            },
        )
        db.add(extraction)
        db.commit()
        extraction_id = extraction.id
    finally:
        db.close()

    applied, events = apply_approved_extraction(extraction_id, user_id=cleanup_marker.lower())
    assert applied.apply_status == "aplicado"
    assert applied.apply_summary["condicoes"] == {"criadas": 1, "versoes_encerradas": 1, "nova_versao": 2}
    assert any(event.action == "approved_extraction_apply_completed" for event in events)
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).one()
        assert contract.contract_number == "PRESERVAR-123"
        assert contract.operator_id is not None
        operator = db.query(Operator).filter(Operator.id == contract.operator_id).one()
        assert operator.tax_id == f"TEST-{cleanup_marker}"
        assert db.query(ContractTerm).filter(ContractTerm.contract_id == contract_id, ContractTerm.version == 1, ContractTerm.is_current.is_(False)).count() == 1
        assert db.query(ContractTerm).filter(ContractTerm.contract_id == contract_id, ContractTerm.version == 2, ContractTerm.is_current.is_(True)).count() == 1
    finally:
        db.close()

    with pytest.raises(ValueError, match="ja aplicada"):
        apply_approved_extraction(extraction_id, user_id=cleanup_marker.lower())
    db = SessionLocal()
    try:
        assert db.query(ContractExtraction).filter(ContractExtraction.id == extraction_id).one().apply_status == "aplicado"
    finally:
        db.close()

