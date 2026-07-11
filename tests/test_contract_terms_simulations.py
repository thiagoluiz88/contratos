from datetime import date
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models import ContractTerm
from app.services.contract_terms_simulation_service import (
    apply_simulation_to_contract_terms,
    approve_simulation,
    cancel_simulation,
    compare_simulation_with_current_terms,
    create_manual_simulation,
    get_simulation,
)


def add_term(contract_id, title, value, *, unit="evento", valid_from=date(2026, 1, 1)):
    db = SessionLocal()
    try:
        term = ContractTerm(contract_id=contract_id, category="teste", title=title, reference_value=value, unit=unit, version=1, valid_from=valid_from, is_current=True, status="active")
        db.add(term)
        db.commit()
    finally:
        db.close()


@pytest.mark.integration
def test_simulation_comparison_application_and_history(contract_factory, cleanup_marker):
    contract_id = contract_factory()
    for title, value in [("Igual", 10), ("Aumenta", 20), ("Reduz", 30), ("Vigencia", 40), ("Removido", 50)]:
        add_term(contract_id, title, value)
    rows = [
        {"category": "teste", "title": "Igual", "reference_value": "10", "unit": "evento", "valid_from": "2026-01-01"},
        {"category": "teste", "title": "Aumenta", "reference_value": "25", "unit": "evento", "valid_from": "2026-01-01"},
        {"category": "teste", "title": "Reduz", "reference_value": "25", "unit": "evento", "valid_from": "2026-01-01"},
        {"category": "teste", "title": "Vigencia", "reference_value": "40", "unit": "evento", "valid_from": "2026-02-01"},
        {"category": "teste", "title": "Novo", "reference_value": "60", "unit": "evento"},
        {"category": "teste", "title": "Invalido", "reference_value": "nao-e-numero", "unit": "evento"},
    ]
    simulation, _ = create_manual_simulation(contract_id=contract_id, simulation_name=f"Sim {cleanup_marker}", terms=rows, created_by=cleanup_marker.lower())
    db = SessionLocal()
    try:
        persisted = get_simulation(db, simulation.id)
        comparison = compare_simulation_with_current_terms(db, persisted)
        counts = comparison["summary"]["counts"]
        assert counts["sem_alteracao"] == 1
        assert counts["novo"] == 2  # inclui o item pendente, ainda visivel na simulacao
        assert counts["removido"] == 1
        assert counts["aumento"] == 1
        assert counts["reducao"] == 1
        assert counts["alteracao_vigencia"] == 1
        assert persisted.comparison_summary_json["warnings"]
    finally:
        db.close()

    approve_simulation(simulation.id, reviewed_by=cleanup_marker.lower(), contract_id=contract_id)
    applied, _ = apply_simulation_to_contract_terms(simulation.id, applied_by=cleanup_marker.lower(), contract_id=contract_id)
    assert applied.simulation_status == "aplicada"
    db = SessionLocal()
    try:
        old = db.query(ContractTerm).filter(ContractTerm.contract_id == contract_id, ContractTerm.version == 1).all()
        new = db.query(ContractTerm).filter(ContractTerm.contract_id == contract_id, ContractTerm.version == 2).all()
        assert len(old) == 5 and all(not row.is_current and row.valid_until for row in old)
        assert len(new) == 5 and all(row.is_current for row in new)
        assert {row.title for row in new} == {"Igual", "Aumenta", "Reduz", "Vigencia", "Novo"}
        assert db.query(ContractTerm).filter(ContractTerm.contract_id == contract_id).count() == 10
    finally:
        db.close()


@pytest.mark.integration
def test_simulation_blocking_rules(contract_factory, cleanup_marker):
    first = contract_factory(suffix="A")
    second = contract_factory(suffix="B")
    add_term(first, "Base", Decimal("100"))
    simulation, _ = create_manual_simulation(contract_id=first, simulation_name=f"Bloqueios {cleanup_marker}", terms=[{"category": "teste", "title": "Base", "reference_value": "110", "unit": "evento"}])
    with pytest.raises(ValueError, match="aprovada"):
        apply_simulation_to_contract_terms(simulation.id, contract_id=first)
    with pytest.raises(ValueError, match="nao pertence"):
        approve_simulation(simulation.id, contract_id=second)
    approve_simulation(simulation.id, contract_id=first)
    apply_simulation_to_contract_terms(simulation.id, contract_id=first)
    with pytest.raises(ValueError, match="aprovada"):
        apply_simulation_to_contract_terms(simulation.id, contract_id=first)
    db = SessionLocal()
    try:
        assert get_simulation(db, simulation.id).simulation_status == "aplicada"
    finally:
        db.close()
    with pytest.raises(ValueError, match="nao pode ser cancelada"):
        cancel_simulation(simulation.id, contract_id=first)
    with pytest.raises(ValueError, match="nao encontrada"):
        approve_simulation(999999999, contract_id=first)
    with pytest.raises(ValueError, match="Contrato nao encontrado"):
        create_manual_simulation(contract_id=999999999, simulation_name="inexistente", terms=[])


@pytest.mark.integration
def test_read_only_user_cannot_apply(admin_client, readonly_client, contract_factory, cleanup_marker):
    contract_id = contract_factory()
    add_term(contract_id, "Base", 10)
    simulation, _ = create_manual_simulation(contract_id=contract_id, simulation_name=f"Permissao {cleanup_marker}", terms=[{"category": "teste", "title": "Base", "reference_value": "12", "unit": "evento"}])
    approve_simulation(simulation.id, contract_id=contract_id)
    response = readonly_client.post(f"/contracts/{contract_id}/terms/simulations/{simulation.id}/apply", follow_redirects=False)
    assert response.status_code == 403
    db = SessionLocal()
    try:
        assert get_simulation(db, simulation.id).simulation_status == "aprovada"
    finally:
        db.close()

