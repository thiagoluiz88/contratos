from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models import ContractTerm, ReferenceTable, ReferenceTableItem
from app.services.reference_table_comparison_service import calculate_gap_percent, classify_gap, compare_terms_with_reference


@pytest.mark.integration
def test_reference_table_creation_and_comparison(contract_factory, cleanup_marker):
    contract_id = contract_factory()
    db = SessionLocal()
    try:
        db.add_all([
            ContractTerm(contract_id=contract_id, category="taxa", title="Acima", reference_value=120, unit="evento", version=1, is_current=True),
            ContractTerm(contract_id=contract_id, category="taxa", title="Abaixo", reference_value=80, unit="evento", version=1, is_current=True),
            ContractTerm(contract_id=contract_id, category="taxa", title="Igual", reference_value=100, unit="evento", version=1, is_current=True),
            ContractTerm(contract_id=contract_id, category="taxa", title="Sem item", reference_value=50, unit="evento", version=1, is_current=True),
        ])
        table = ReferenceTable(name=f"Referencia {cleanup_marker}", version="manual", status="active", created_by=cleanup_marker.lower())
        db.add(table)
        db.flush()
        db.add_all([ReferenceTableItem(reference_table_id=table.id, category="taxa", item=name, value=100, unit="evento") for name in ("Acima", "Abaixo", "Igual")])
        db.commit()
        result = compare_terms_with_reference(db, contract_id, table.id)
        assert result["summary"]["counts"] == {"acima_referencia": 1, "igual_referencia": 1, "abaixo_referencia": 1, "sem_referencia": 1}
    finally:
        db.close()

    assert calculate_gap_percent(120, 100) == Decimal("20.00")
    assert classify_gap(120, 100) == "acima_referencia"
    assert classify_gap(80, 100) == "abaixo_referencia"
    assert classify_gap(100, 100) == "igual_referencia"
    assert classify_gap(100, None) == "sem_referencia"


@pytest.mark.integration
def test_empty_reference_table_returns_no_matches(contract_factory, cleanup_marker):
    contract_id = contract_factory()
    db = SessionLocal()
    try:
        db.add(ContractTerm(contract_id=contract_id, category="taxa", title="Item", reference_value=10, unit="evento", version=1, is_current=True))
        table = ReferenceTable(name=f"Vazia {cleanup_marker}", status="active")
        db.add(table)
        db.commit()
        result = compare_terms_with_reference(db, contract_id, table.id)
        assert result["rows"][0]["classification"] == "sem_referencia"
        assert result["rows"][0]["reference_value"] is None
    finally:
        db.close()
