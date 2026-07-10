from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Contract, ContractTerm, Operator, ReferenceTable, ReferenceTableItem
from app.services import commercial_bi_service as bi


def create_bi_dataset(marker: str):
    db = SessionLocal()
    try:
        operator_a = Operator(name=f"Operadora A {marker}", tax_id=f"A-{marker}", is_active=True)
        operator_b = Operator(name=f"Operadora B {marker}", tax_id=f"B-{marker}", is_active=True)
        db.add_all([operator_a, operator_b])
        db.flush()
        contract_a = Contract(contract_name=f"{marker}-BI-A", operator_id=operator_a.id, operator_name=operator_a.name, status="active", base_date=date(2026, 1, 1), end_date=date.today() + timedelta(days=60))
        contract_b = Contract(contract_name=f"{marker}-BI-B", operator_id=operator_b.id, operator_name=operator_b.name, status="active", base_date=date(2026, 1, 1))
        contract_empty = Contract(contract_name=f"{marker}-BI-SEM-TABELA", operator_id=operator_a.id, operator_name=operator_a.name, status="active")
        db.add_all([contract_a, contract_b, contract_empty])
        db.flush()
        db.add_all([
            ContractTerm(contract_id=contract_a.id, category="taxa", title="Sala", reference_value=120, unit="evento", version=1, is_current=True, source_type="manual"),
            ContractTerm(contract_id=contract_a.id, category="diária", title="UTI", reference_value=500, unit="dia", version=1, is_current=True, source_type="manual"),
            ContractTerm(contract_id=contract_b.id, category="taxa", title="Sala", reference_value=80, unit="evento", version=1, is_current=True, source_type="manual"),
            ContractTerm(contract_id=contract_b.id, category="diaria", title="UTI", reference_value=550, unit="dia", version=1, is_current=True, source_type="manual"),
        ])
        reference = ReferenceTable(name=f"Referencia BI {marker}", version="teste", status="active")
        db.add(reference)
        db.flush()
        db.add(ReferenceTableItem(reference_table_id=reference.id, category="taxa", item="Sala", value=100, unit="evento"))
        db.commit()
        return operator_a.id, operator_b.id, contract_a.id, contract_b.id, contract_empty.id, reference.id
    finally:
        db.close()


@pytest.mark.integration
def test_summary_ranking_conditions_and_missing_terms(cleanup_marker, monkeypatch):
    operator_a, operator_b, contract_a, contract_b, empty, reference_id = create_bi_dataset(cleanup_marker)
    db = SessionLocal()
    try:
        reference = db.query(ReferenceTable).filter(ReferenceTable.id == reference_id).one()
        monkeypatch.setattr(bi, "get_active_reference_tables", lambda session: [reference])
        summary = bi.get_commercial_dashboard_summary(db)
        assert summary["active_contracts"] >= 3
        assert summary["contracts_with_current_terms"] >= 2
        assert empty in {contract.id for contract in bi.get_contracts_without_current_terms(db)}
        ranking = bi.rank_operators_by_contract_values(db)
        rows = {row["operator"].id: row for row in ranking}
        assert rows[operator_a]["item_count"] == 2
        assert rows[operator_b]["item_count"] == 2
        assert all("score" in rows[operator_id] for operator_id in (operator_a, operator_b))
        conditions = {row["category"]: row for row in bi.get_conditions_by_category(db)}
        assert conditions["taxa"]["highest"].reference_value == 120
        assert conditions["taxa"]["lowest"].reference_value == 80
        assert conditions["pacote"]["status"] == "dados_insuficientes"
    finally:
        db.close()


@pytest.mark.integration
def test_executive_comparison_and_reference_scenarios(cleanup_marker, monkeypatch):
    _, _, contract_a, contract_b, _, reference_id = create_bi_dataset(cleanup_marker)
    db = SessionLocal()
    try:
        comparison = bi.compare_contracts_executive(db, [contract_a, contract_b])
        assert comparison["status"] == "ok"
        sala = next(row for row in comparison["rows"] if row["item"] == "Sala")
        assert sala["highest"] == 120 and sala["lowest"] == 80
        monkeypatch.setattr(bi, "get_active_reference_tables", lambda session: [])
        no_reference = bi.get_contract_terms_score(db, contract_a)
        assert no_reference["reference"]["status"] == "sem_tabela_referencia"
        reference = db.query(ReferenceTable).filter(ReferenceTable.id == reference_id).one()
        monkeypatch.setattr(bi, "get_active_reference_tables", lambda session: [reference])
        with_reference = bi.get_contract_terms_score(db, contract_a)
        counts = with_reference["reference"]["counts"]
        assert counts["acima_referencia"] == 1
        assert counts["sem_referencia"] == 1
    finally:
        db.close()


def test_commercial_bi_routes_are_protected():
    with TestClient(app) as client:
        for path in ("/bi/commercial", "/bi/commercial/operators", "/bi/commercial/compare", "/bi/commercial/export/ranking"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 303
            assert response.headers["location"] == "/login"


@pytest.mark.integration
def test_commercial_bi_pages_csv_and_audit(admin_client, readonly_client, cleanup_marker, admin_username):
    _, _, contract_a, contract_b, _, _ = create_bi_dataset(cleanup_marker)
    assert admin_client.get("/bi/commercial").status_code == 200
    assert admin_client.get("/bi/commercial/operators").status_code == 200
    assert admin_client.get(f"/bi/commercial/compare?contract_ids={contract_a},{contract_b}").status_code == 200
    ranking_csv = admin_client.get("/bi/commercial/export/ranking")
    assert ranking_csv.status_code == 200 and "text/csv" in ranking_csv.headers["content-type"]
    assert "Score Comercial" in ranking_csv.text
    conditions_csv = admin_client.get("/bi/commercial/export/conditions")
    assert conditions_csv.status_code == 200
    comparison_csv = admin_client.get(f"/bi/commercial/compare/export?contract_ids={contract_a},{contract_b}")
    assert comparison_csv.status_code == 200 and "Sala" in comparison_csv.text
    assert readonly_client.get("/bi/commercial").status_code == 200
    assert readonly_client.get("/bi/commercial/export/ranking", follow_redirects=False).status_code == 403
    db = SessionLocal()
    try:
        actions = {log.action for log in db.query(AuditLog).filter(AuditLog.username == admin_username).all()}
        assert {"commercial_bi_viewed", "commercial_bi_comparison_generated", "commercial_bi_ranking_exported", "commercial_bi_conditions_exported", "commercial_bi_comparison_exported"} <= actions
    finally:
        db.close()
