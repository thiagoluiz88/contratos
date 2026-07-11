from datetime import date
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models import ContractTerm, ProductionImportBatch, ProductionRecord
from app.services.financial_impact_service import calculate_contract_estimated_revenue, calculate_margin_estimate, calculate_repricing_impact, compare_current_vs_simulated_terms


@pytest.mark.integration
def test_financial_impact_with_sufficient_data(contract_factory, cleanup_marker):
    contract_id = contract_factory(suffix="IMPACTO")
    db = SessionLocal()
    try:
        db.add(ContractTerm(contract_id=contract_id, category="taxa", title="Sala", reference_value=100, unit="evento", version=1, is_current=True, valid_from=date(2026, 1, 1)))
        batch = ProductionImportBatch(batch_name=f"Impacto {cleanup_marker}", source_type="manual", source_system="planilha", import_status="processado", total_rows=1, valid_rows=1)
        db.add(batch)
        db.flush()
        db.add(ProductionRecord(batch_id=batch.id, contract_id=contract_id, service_date=date(2026, 7, 10), competence_month=date(2026, 7, 1), category="taxa", item="Sala", quantity=3, unit="evento", billed_value=300, paid_value=280, denied_value=20, cost_value=150, source_row_number=2, validation_status="valido"))
        db.commit()
        revenue = calculate_contract_estimated_revenue(db, contract_id)
        assert revenue["estimated_revenue"] == Decimal("300.00")
        repricing = calculate_repricing_impact(db, contract_id, 10)
        assert repricing["impact"] == Decimal("30.00") and repricing["repriced_revenue"] == Decimal("330.00")
        margin = calculate_margin_estimate(db, contract_id=contract_id)
        assert margin["margin_estimate"] == Decimal("130.00")
        simulated = compare_current_vs_simulated_terms(db, contract_id, [{"category": "taxa", "title": "Sala", "unit": "evento", "reference_value": "120"}])
        assert simulated["impact"] == Decimal("60.00")
    finally:
        db.close()


@pytest.mark.integration
def test_financial_impact_reports_missing_volume_and_cost(contract_factory, cleanup_marker):
    empty_contract = contract_factory(suffix="SEM-PRODUCAO")
    db = SessionLocal()
    try:
        assert calculate_contract_estimated_revenue(db, empty_contract)["status"] == "dados_insuficientes"
        batch = ProductionImportBatch(batch_name=f"Sem custo {cleanup_marker}", source_type="manual", source_system="planilha", import_status="processado", total_rows=1, valid_rows=1)
        db.add(batch)
        db.flush()
        db.add(ProductionRecord(batch_id=batch.id, contract_id=empty_contract, category="taxa", item="Sala", quantity=1, unit="evento", paid_value=100, cost_value=None, source_row_number=2, validation_status="valido"))
        db.commit()
        margin = calculate_margin_estimate(db, contract_id=empty_contract)
        assert margin["status"] == "custo_incompleto" and margin["margin_estimate"] is None
    finally:
        db.close()
