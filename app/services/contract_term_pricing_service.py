from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import ContractTerm, ProductionRecord
from app.services.contract_terms_comparison_service import fold_text


def get_terms_version_for_service_date(db: Session, contract_id: int, service_date) -> dict[str, Any]:
    if not contract_id or not service_date:
        return {"status": "dados_insuficientes", "message": "Contrato e data de atendimento são obrigatórios.", "version": None, "terms": []}
    candidates = db.query(ContractTerm).filter(
        ContractTerm.contract_id == contract_id,
        or_(ContractTerm.valid_from.is_(None), ContractTerm.valid_from <= service_date),
        or_(ContractTerm.valid_until.is_(None), ContractTerm.valid_until >= service_date),
    ).all()
    if not candidates:
        return {"status": "sem_vigencia", "message": "Nenhuma versão contratual vigente na data do atendimento.", "version": None, "terms": []}
    version = max(term.version for term in candidates)
    terms = [term for term in candidates if term.version == version]
    return {"status": "ok", "message": "Versão contratual localizada pela vigência do atendimento.", "version": version, "terms": terms}


def find_matching_contract_term(db: Session, contract_id: int, category, item, unit, service_date) -> dict[str, Any]:
    version = get_terms_version_for_service_date(db, contract_id, service_date)
    if version["status"] != "ok": return {**version, "term": None}
    key = (fold_text(category), fold_text(item), fold_text(unit))
    term = next((candidate for candidate in version["terms"] if (fold_text(candidate.category), fold_text(candidate.title), fold_text(candidate.unit)) == key), None)
    if not term:
        return {"status": "item_nao_encontrado", "message": "Item sem correspondência na versão vigente da data do atendimento.", "version": version["version"], "term": None}
    return {"status": "ok", "message": "Preço histórico localizado.", "version": version["version"], "term": term}


def get_price_for_production_record(db: Session, record: ProductionRecord) -> dict[str, Any]:
    if not record.contract_id or not record.service_date:
        return {"status": "dados_insuficientes", "message": "Produção sem contrato vinculado ou data de atendimento.", "price": None, "term": None}
    match = find_matching_contract_term(db, record.contract_id, record.category, record.item, record.unit, record.service_date)
    if match["status"] != "ok": return {**match, "price": None}
    if match["term"].reference_value is None:
        return {**match, "status": "preco_ausente", "message": "Item vigente sem valor contratual.", "price": None}
    return {**match, "price": Decimal(str(match["term"].reference_value))}


def calculate_expected_value_for_record(db: Session, record: ProductionRecord) -> dict[str, Any]:
    pricing = get_price_for_production_record(db, record)
    if pricing.get("price") is None or record.quantity is None:
        return {**pricing, "status": "dados_insuficientes" if record.quantity is None else pricing["status"], "message": "Quantidade ausente para cálculo." if record.quantity is None else pricing["message"], "expected_value": None}
    expected = Decimal(str(record.quantity)) * pricing["price"]
    return {**pricing, "expected_value": expected.quantize(Decimal("0.01")), "quantity": Decimal(str(record.quantity))}
