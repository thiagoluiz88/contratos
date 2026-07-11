from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import Contract, ContractTerm, ProductionRecord
from app.services.contract_terms_comparison_service import fold_text
from app.services.contract_term_pricing_service import calculate_expected_value_for_record


def _key(category, item, unit) -> tuple[str, str, str]:
    return fold_text(category), fold_text(item), fold_text(unit)


def _valid_production(db: Session, *, contract_id: int | None = None, operator_id: int | None = None) -> list[ProductionRecord]:
    query = db.query(ProductionRecord).filter(ProductionRecord.validation_status == "valido")
    if contract_id is not None:
        query = query.filter(ProductionRecord.contract_id == contract_id)
    if operator_id is not None:
        query = query.filter(ProductionRecord.operator_id == operator_id)
    return query.all()


def calculate_contract_estimated_revenue(db: Session, contract_id: int) -> dict[str, Any]:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        return {"status": "contrato_nao_encontrado", "message": "Contrato não encontrado.", "estimated_revenue": None}
    records = _valid_production(db, contract_id=contract_id)
    if not records:
        return {"status": "dados_insuficientes", "message": "Sem produção assistencial válida vinculada ao contrato.", "estimated_revenue": None}
    estimated = Decimal("0")
    matched = 0
    unmatched = 0
    rows = []
    for record in records:
        pricing = calculate_expected_value_for_record(db, record)
        term = pricing.get("term")
        quantity = Decimal(str(record.quantity or 0))
        value = pricing.get("price")
        row_revenue = pricing.get("expected_value")
        if row_revenue is None:
            unmatched += 1
        else:
            matched += 1
            estimated += row_revenue
        rows.append({"production_record_id": record.id, "term_id": term.id if term else None, "term_version": pricing.get("version"), "quantity": quantity, "contract_value": value, "estimated_revenue": row_revenue, "status": pricing["status"], "message": pricing["message"]})
    status = "ok" if matched else "dados_insuficientes"
    return {"status": status, "message": "Receita estimada por quantidade importada e valor contratual vigente; não representa valor final recebido." if matched else "Produção importada sem correspondência em itens contratuais vigentes.", "estimated_revenue": estimated.quantize(Decimal("0.01")) if matched else None, "matched_records": matched, "unmatched_records": unmatched, "rows": rows}


def calculate_operator_estimated_revenue(db: Session, operator_id: int) -> dict[str, Any]:
    contract_ids = [row[0] for row in db.query(Contract.id).filter(Contract.operator_id == operator_id, Contract.status == "active").all()]
    results = [calculate_contract_estimated_revenue(db, contract_id) for contract_id in contract_ids]
    valid = [row for row in results if row["estimated_revenue"] is not None]
    return {"status": "ok" if valid else "dados_insuficientes", "message": "Consolidação estimada dos contratos com produção e correspondência vigentes." if valid else "Sem produção contratualmente comparável para a operadora.", "estimated_revenue": sum((row["estimated_revenue"] for row in valid), Decimal("0")).quantize(Decimal("0.01")) if valid else None, "contracts": results}


def calculate_repricing_impact(db: Session, contract_id: int, percentage) -> dict[str, Any]:
    base = calculate_contract_estimated_revenue(db, contract_id)
    if base["estimated_revenue"] is None:
        return {**base, "repriced_revenue": None, "impact": None}
    rate = Decimal(str(percentage)) / Decimal("100")
    impact = (base["estimated_revenue"] * rate).quantize(Decimal("0.01"))
    return {**base, "percentage": Decimal(str(percentage)), "repriced_revenue": base["estimated_revenue"] + impact, "impact": impact, "message": "Simulação aritmética sobre receita contratual estimada; não altera a tabela oficial."}


def calculate_margin_estimate(db: Session, *, contract_id: int | None = None, operator_id: int | None = None) -> dict[str, Any]:
    records = _valid_production(db, contract_id=contract_id, operator_id=operator_id)
    if not records:
        return {"status": "dados_insuficientes", "message": "Sem produção válida para estimar margem.", "margin_estimate": None}
    without_cost = sum(record.cost_value is None for record in records)
    if without_cost:
        return {"status": "custo_incompleto", "message": f"Custo ausente em {without_cost} registro(s); margem não calculada.", "margin_estimate": None, "records_without_cost": without_cost}
    without_paid = sum(record.paid_value is None for record in records)
    if without_paid:
        return {"status": "receita_incompleta", "message": f"Valor pago ausente em {without_paid} registro(s); margem não calculada.", "margin_estimate": None, "records_without_paid_value": without_paid}
    revenue = sum((Decimal(str(record.paid_value)) for record in records if record.paid_value is not None), Decimal("0"))
    costs = sum((Decimal(str(record.cost_value)) for record in records), Decimal("0"))
    margin = revenue - costs
    return {"status": "estimativa_disponivel", "message": "Margem bruta estimada por valor pago menos custo informado; não representa rentabilidade final.", "paid_value": revenue.quantize(Decimal("0.01")), "cost_value": costs.quantize(Decimal("0.01")), "margin_estimate": margin.quantize(Decimal("0.01"))}


def compare_current_vs_simulated_terms(db: Session, contract_id: int, simulated_terms: list[dict[str, Any]]) -> dict[str, Any]:
    records = _valid_production(db, contract_id=contract_id)
    if not records:
        return {"status": "dados_insuficientes", "message": "Sem produção válida para ponderar a simulação.", "current_revenue": None, "simulated_revenue": None}
    current = db.query(ContractTerm).filter(ContractTerm.contract_id == contract_id, ContractTerm.is_current.is_(True)).all()
    current_map = {_key(term.category, term.title, term.unit): Decimal(str(term.reference_value)) for term in current if term.reference_value is not None}
    simulated_map = {_key(row.get("category") or row.get("categoria"), row.get("title") or row.get("item"), row.get("unit") or row.get("unidade")): Decimal(str(row.get("reference_value") or row.get("valor"))) for row in simulated_terms if row.get("reference_value") is not None or row.get("valor") is not None}
    current_total = simulated_total = Decimal("0")
    matched = 0
    for record in records:
        key = _key(record.category, record.item, record.unit)
        quantity = Decimal(str(record.quantity or 0))
        if key in current_map and key in simulated_map:
            current_total += quantity * current_map[key]
            simulated_total += quantity * simulated_map[key]
            matched += 1
    if not matched:
        return {"status": "dados_insuficientes", "message": "Nenhum item de produção corresponde simultaneamente às tabelas atual e simulada.", "current_revenue": None, "simulated_revenue": None}
    return {"status": "ok", "message": "Impacto estimado com o mesmo volume importado; não aplica a simulação.", "matched_records": matched, "current_revenue": current_total.quantize(Decimal("0.01")), "simulated_revenue": simulated_total.quantize(Decimal("0.01")), "impact": (simulated_total - current_total).quantize(Decimal("0.01"))}


def build_financial_impact_summary(db: Session, *, contract_id: int | None = None, operator_id: int | None = None) -> dict[str, Any]:
    revenue = calculate_contract_estimated_revenue(db, contract_id) if contract_id is not None else calculate_operator_estimated_revenue(db, operator_id) if operator_id is not None else {"status": "dados_insuficientes", "message": "Informe contrato ou operadora.", "estimated_revenue": None}
    margin = calculate_margin_estimate(db, contract_id=contract_id, operator_id=operator_id)
    return {"revenue": revenue, "margin": margin, "disclaimer": "Sem produção assistencial e custos completos, o sistema não deve afirmar rentabilidade real."}
