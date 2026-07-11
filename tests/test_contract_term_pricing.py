from datetime import date
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models import ContractTerm, ProductionImportBatch, ProductionRecord
from app.services.contract_term_pricing_service import calculate_expected_value_for_record, find_matching_contract_term, get_terms_version_for_service_date


@pytest.mark.integration
def test_historical_version_and_price_selection(contract_factory, cleanup_marker):
    contract_id = contract_factory(suffix="HISTORICO")
    db = SessionLocal()
    try:
        db.add_all([
            ContractTerm(contract_id=contract_id, category="taxa", title="Sala", unit="evento", reference_value=100, version=1, valid_from=date(2025, 1, 1), valid_until=date(2025, 12, 31), is_current=False),
            ContractTerm(contract_id=contract_id, category="taxa", title="Sala", unit="evento", reference_value=130, version=2, valid_from=date(2026, 1, 1), valid_until=None, is_current=True),
        ])
        batch = ProductionImportBatch(batch_name=f"Preço {cleanup_marker}", source_type="manual", source_system="planilha", import_status="processado")
        db.add(batch); db.flush()
        old = ProductionRecord(batch_id=batch.id, contract_id=contract_id, service_date=date(2025, 6, 1), category="taxa", item="Sala", unit="evento", quantity=2, source_row_number=2, validation_status="valido")
        current = ProductionRecord(batch_id=batch.id, contract_id=contract_id, service_date=date(2026, 6, 1), category="taxa", item="Sala", unit="evento", quantity=3, source_row_number=3, validation_status="valido")
        db.add_all([old, current]); db.commit()
        assert get_terms_version_for_service_date(db, contract_id, old.service_date)["version"] == 1
        assert find_matching_contract_term(db, contract_id, "taxa", "Sala", "evento", current.service_date)["term"].reference_value == 130
        assert calculate_expected_value_for_record(db, old)["expected_value"] == Decimal("200.00")
        assert calculate_expected_value_for_record(db, current)["expected_value"] == Decimal("390.00")
    finally: db.close()


@pytest.mark.integration
def test_historical_price_returns_clear_pending(contract_factory, cleanup_marker):
    contract_id = contract_factory(suffix="SEM-PRECO")
    db = SessionLocal()
    try:
        batch = ProductionImportBatch(batch_name=f"Sem preço {cleanup_marker}", source_type="manual", source_system="planilha", import_status="processado")
        db.add(batch); db.flush()
        record = ProductionRecord(batch_id=batch.id, contract_id=contract_id, service_date=date(2020, 1, 1), category="taxa", item="Ausente", unit="evento", quantity=1, source_row_number=2, validation_status="valido")
        db.add(record); db.commit()
        result = calculate_expected_value_for_record(db, record)
        assert result["expected_value"] is None and result["status"] == "sem_vigencia"
        record.service_date = None; db.commit()
        assert calculate_expected_value_for_record(db, record)["status"] == "dados_insuficientes"
    finally: db.close()
