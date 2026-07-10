from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import Contract, ContractTerm, ContractTermSimulation, Operator, ProductionImportBatch, ProductionRecord, ReferenceTable
from app.services.contract_terms_comparison_service import fold_text
from app.services.reference_table_comparison_service import compare_terms_with_reference, get_active_reference_tables


EXPECTED_CATEGORIES = ("diaria", "taxa", "pacote", "material", "medicamento", "opme", "honorario", "servico", "outro")
STRATEGIC_CATEGORIES = {"diaria", "taxa", "pacote", "opme", "honorario"}
PENDING_SIMULATION_STATUSES = {"rascunho", "simulada", "em_revisao", "aprovada"}


def normalize_category(value: str | None) -> str:
    folded = fold_text(value)
    aliases = {"diarias": "diaria", "taxas": "taxa", "pacotes": "pacote", "materiais": "material", "medicamentos": "medicamento", "honorarios": "honorario", "servicos": "servico"}
    return aliases.get(folded, folded if folded in EXPECTED_CATEGORIES else "outro")


def _active_contracts(db: Session):
    return db.query(Contract).filter(Contract.status == "active")


def _current_terms(db: Session, contract_id: int | None = None) -> list[ContractTerm]:
    query = db.query(ContractTerm).join(Contract).filter(Contract.status == "active", ContractTerm.is_current.is_(True))
    if contract_id is not None:
        query = query.filter(ContractTerm.contract_id == contract_id)
    return query.all()


def _reference_summary(db: Session, contract_id: int) -> dict[str, Any]:
    tables = get_active_reference_tables(db)
    if not tables:
        return {"status": "sem_tabela_referencia", "message": "Sem tabela de referência cadastrada.", "counts": {"acima_referencia": 0, "igual_referencia": 0, "abaixo_referencia": 0, "sem_referencia": 0}, "matched": 0}
    result = compare_terms_with_reference(db, contract_id, tables[0].id)
    counts = result["summary"]["counts"]
    return {"status": result["status"], "message": result["message"], "counts": counts, "matched": len(result["rows"]) - counts["sem_referencia"], "reference_table": tables[0]}


def get_contract_terms_score(db: Session, contract_id: int) -> dict[str, Any]:
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        return {"status": "contrato_nao_encontrado", "message": "Contrato não encontrado.", "score": 0}
    terms = _current_terms(db, contract_id)
    if not terms:
        return {"status": "sem_termos", "message": "Contrato sem tabela vigente cadastrada.", "contract": contract, "score": 0, "item_count": 0, "category_averages": {}}
    grouped: dict[str, list[Decimal]] = defaultdict(list)
    for term in terms:
        if term.reference_value is not None:
            grouped[normalize_category(term.category)].append(Decimal(str(term.reference_value)))
    averages = {category: (sum(values) / len(values)).quantize(Decimal("0.01")) for category, values in grouped.items() if values}
    strategic = STRATEGIC_CATEGORIES.intersection(grouped)
    reference = _reference_summary(db, contract_id)
    completeness_points = min(len(terms), 10) * 3
    breadth_points = min(len(grouped), 5) * 6
    strategic_points = len(strategic) * 4
    reference_points = round(20 * reference["matched"] / len(terms), 2) if terms else 0
    score = round(completeness_points + breadth_points + strategic_points + reference_points, 2)
    return {"status": "ok", "message": "Índice contratual calculado com condições vigentes; não representa rentabilidade real.", "contract": contract, "score": score, "item_count": len(terms), "category_count": len(grouped), "strategic_categories": sorted(strategic), "category_averages": averages, "reference": reference}


def get_operator_terms_score(db: Session, operator_id: int) -> dict[str, Any]:
    operator = db.query(Operator).filter(Operator.id == operator_id).first()
    if not operator:
        return {"status": "operadora_nao_encontrada", "message": "Operadora não encontrada.", "score": 0}
    contracts = db.query(Contract).filter(Contract.operator_id == operator_id, Contract.status == "active").all()
    scores = [get_contract_terms_score(db, contract.id) for contract in contracts]
    scored = [row for row in scores if row.get("status") == "ok"]
    return {"status": "ok" if scored else "sem_termos", "operator": operator, "contract_count": len(contracts), "contracts_with_terms": len(scored), "item_count": sum(row.get("item_count", 0) for row in scored), "score": round(sum(row["score"] for row in scored) / len(scored), 2) if scored else 0, "contracts": scores}


def rank_operators_by_contract_values(db: Session) -> list[dict[str, Any]]:
    operators = db.query(Operator).filter(Operator.is_active.is_(True)).order_by(Operator.name).all()
    ranking = []
    for operator in operators:
        row = get_operator_terms_score(db, operator.id)
        if row["contract_count"]:
            averages: dict[str, list[Decimal]] = defaultdict(list)
            for contract_score in row["contracts"]:
                for category, value in contract_score.get("category_averages", {}).items():
                    averages[category].append(value)
            row["category_averages"] = {category: (sum(values) / len(values)).quantize(Decimal("0.01")) for category, values in averages.items()}
            ranking.append(row)
    ranking.sort(key=lambda row: (row["score"], row["item_count"], row["operator"].name), reverse=True)
    for position, row in enumerate(ranking, start=1):
        row["position"] = position
    return ranking


def get_operator_contract_summary(db: Session) -> list[dict[str, Any]]:
    return rank_operators_by_contract_values(db)


def get_contracts_without_current_terms(db: Session) -> list[Contract]:
    ids_with_terms = db.query(ContractTerm.contract_id).filter(ContractTerm.is_current.is_(True)).distinct()
    return _active_contracts(db).filter(~Contract.id.in_(ids_with_terms)).order_by(Contract.contract_name).all()


def get_contracts_without_reference_comparison(db: Session) -> list[Contract]:
    contracts = _active_contracts(db).order_by(Contract.contract_name).all()
    if not get_active_reference_tables(db):
        return contracts
    return [contract for contract in contracts if _reference_summary(db, contract.id)["matched"] == 0]


def _conditions_by_category(db: Session) -> list[dict[str, Any]]:
    terms = [term for term in _current_terms(db) if term.reference_value is not None]
    grouped: dict[str, list[ContractTerm]] = defaultdict(list)
    for term in terms:
        grouped[normalize_category(term.category)].append(term)
    rows = []
    for category in EXPECTED_CATEGORIES:
        category_terms = grouped.get(category, [])
        if not category_terms:
            rows.append({"category": category, "status": "dados_insuficientes", "message": "Sem condições vigentes cadastradas nesta categoria.", "item_count": 0})
            continue
        highest = max(category_terms, key=lambda item: Decimal(str(item.reference_value)))
        lowest = min(category_terms, key=lambda item: Decimal(str(item.reference_value)))
        rows.append({"category": category, "status": "ok" if len(category_terms) >= 2 else "amostra_reduzida", "message": None if len(category_terms) >= 2 else "Apenas uma condição vigente cadastrada.", "item_count": len(category_terms), "highest": highest, "lowest": lowest, "highest_contract": highest.contract, "lowest_contract": lowest.contract})
    return rows


def get_best_terms_by_category(db: Session) -> list[dict[str, Any]]:
    return [{**row, "term": row.get("highest"), "contract": row.get("highest_contract")} for row in _conditions_by_category(db)]


def get_worst_terms_by_category(db: Session) -> list[dict[str, Any]]:
    return [{**row, "term": row.get("lowest"), "contract": row.get("lowest_contract")} for row in _conditions_by_category(db)]


def get_conditions_by_category(db: Session) -> list[dict[str, Any]]:
    return _conditions_by_category(db)


def compare_contracts_executive(db: Session, contract_ids: list[int]) -> dict[str, Any]:
    unique_ids = list(dict.fromkeys(contract_ids))[:10]
    contracts = db.query(Contract).filter(Contract.id.in_(unique_ids)).order_by(Contract.contract_name).all() if unique_ids else []
    terms = db.query(ContractTerm).filter(ContractTerm.contract_id.in_([c.id for c in contracts]), ContractTerm.is_current.is_(True)).all() if contracts else []
    matrix: dict[tuple[str, str, str], dict[str, Any]] = {}
    for term in terms:
        key = (normalize_category(term.category), fold_text(term.title), fold_text(term.unit))
        row = matrix.setdefault(key, {"category": key[0], "item": term.title, "unit": term.unit, "values": {}})
        row["values"][term.contract_id] = term.reference_value
    rows = []
    for row in matrix.values():
        present = [Decimal(str(value)) for value in row["values"].values() if value is not None]
        row["highest"] = max(present) if present else None
        row["lowest"] = min(present) if present else None
        row["missing_contract_ids"] = [contract.id for contract in contracts if contract.id not in row["values"]]
        rows.append(row)
    rows.sort(key=lambda row: (row["category"], fold_text(row["item"]), fold_text(row["unit"])))
    return {"contracts": contracts, "rows": rows, "status": "ok" if len(contracts) >= 2 else "selecao_insuficiente", "message": "Selecione ao menos dois contratos." if len(contracts) < 2 else "Comparação baseada somente em condições oficiais vigentes."}


def build_bi_alerts(db: Session) -> list[dict[str, Any]]:
    today = date.today()
    active = _active_contracts(db).all()
    without_terms = {contract.id for contract in get_contracts_without_current_terms(db)}
    term_counts: dict[int, int] = defaultdict(int)
    for term in _current_terms(db):
        term_counts[term.contract_id] += 1
    pending_contracts = {row[0] for row in db.query(ContractTermSimulation.contract_id).filter(ContractTermSimulation.simulation_status.in_(PENDING_SIMULATION_STATUSES)).distinct().all()}
    alerts = []
    for contract in active:
        if contract.id in without_terms:
            alerts.append({"type": "sem_tabela", "severity": "high", "contract": contract, "message": "Contrato ativo sem tabela vigente."})
        elif term_counts[contract.id] < 3:
            alerts.append({"type": "poucas_condicoes", "severity": "medium", "contract": contract, "message": f"Apenas {term_counts[contract.id]} condição(ões) vigente(s)."})
        if not contract.base_date:
            alerts.append({"type": "sem_data_base", "severity": "medium", "contract": contract, "message": "Contrato sem data-base de reajuste."})
        if contract.end_date and today <= contract.end_date <= today + timedelta(days=90) and contract.id not in pending_contracts:
            alerts.append({"type": "vencimento_sem_simulacao", "severity": "high", "contract": contract, "message": "Contrato vence em até 90 dias e não possui simulação pendente."})
        if not contract.operator_id:
            alerts.append({"type": "sem_operadora", "severity": "high", "contract": contract, "message": "Contrato sem operadora vinculada."})
    for operator in db.query(Operator).filter(Operator.is_active.is_(True), Operator.tax_id.is_(None)).all():
        alerts.append({"type": "operadora_sem_cnpj", "severity": "medium", "operator": operator, "message": "Operadora ativa sem CNPJ cadastrado."})
    for term in _current_terms(db):
        if not term.source_document_id and not term.source_type:
            alerts.append({"type": "termo_sem_origem", "severity": "low", "contract": term.contract, "message": f"Condição vigente '{term.title}' sem referência de origem/documento."})
    contracts_with_production = {row[0] for row in db.query(ProductionRecord.contract_id).filter(ProductionRecord.contract_id.isnot(None)).distinct().all()}
    for contract_id in ({term.contract_id for term in _current_terms(db)} - contracts_with_production):
        contract = next((item for item in active if item.id == contract_id), None)
        if contract:
            alerts.append({"type": "tabela_sem_producao", "severity": "medium", "contract": contract, "message": "Contrato com tabela vigente, mas sem produção importada."})
    unlinked_operator_ids = {row[0] for row in db.query(ProductionRecord.operator_id).filter(ProductionRecord.operator_id.isnot(None), ProductionRecord.contract_id.is_(None)).distinct().all()}
    for operator in db.query(Operator).filter(Operator.id.in_(unlinked_operator_ids)).all() if unlinked_operator_ids else []:
        alerts.append({"type": "producao_sem_contrato", "severity": "high", "operator": operator, "message": "Operadora possui produção importada sem contrato vinculado."})
    without_cost = db.query(ProductionRecord).filter(ProductionRecord.cost_value.is_(None)).count()
    if without_cost:
        alerts.append({"type": "producao_sem_custo", "severity": "medium", "message": f"{without_cost} registro(s) de produção sem custo informado."})
    invalid = db.query(ProductionRecord).filter(ProductionRecord.validation_status != "valido").count()
    if invalid:
        alerts.append({"type": "producao_invalida", "severity": "high", "message": f"{invalid} registro(s) de produção com pendência de validação."})
    return alerts


def get_commercial_dashboard_summary(db: Session) -> dict[str, Any]:
    active_contracts = _active_contracts(db).all()
    current_terms = _current_terms(db)
    with_terms = {term.contract_id for term in current_terms}
    without_reference = get_contracts_without_reference_comparison(db)
    active_references = get_active_reference_tables(db)
    simulations = db.query(ContractTermSimulation).filter(ContractTermSimulation.simulation_status.in_(PENDING_SIMULATION_STATUSES)).count()
    production_records = db.query(ProductionRecord).count()
    processed_batches = db.query(ProductionImportBatch).filter(ProductionImportBatch.import_status == "processado").count()
    def production_total(field):
        value = db.query(getattr(ProductionRecord, field)).all()
        return sum((Decimal(str(row[0])) for row in value if row[0] is not None), Decimal("0")).quantize(Decimal("0.01"))
    records_with_cost = db.query(ProductionRecord).filter(ProductionRecord.cost_value.isnot(None)).count()
    return {
        "active_operators": db.query(Operator).filter(Operator.is_active.is_(True)).count(),
        "active_contracts": len(active_contracts),
        "contracts_with_current_terms": len(with_terms),
        "contracts_without_current_terms": len(active_contracts) - len(with_terms),
        "current_terms": len(current_terms),
        "contracts_with_reference_match": len(active_contracts) - len(without_reference) if active_references else 0,
        "contracts_without_reference_match": len(without_reference),
        "pending_simulations": simulations,
        "production_records": production_records,
        "processed_production_batches": processed_batches,
        "imported_billed_value": production_total("billed_value"),
        "imported_paid_value": production_total("paid_value"),
        "imported_denied_value": production_total("denied_value"),
        "imported_cost_value": production_total("cost_value") if records_with_cost else None,
        "production_records_with_cost": records_with_cost,
        "reference_status": "ok" if active_references else "sem_tabela_referencia",
        "reference_message": None if active_references else "Sem tabela de referência cadastrada.",
        "disclaimer": "Rentabilidade real depende de produção/volume assistencial e custos. O ranking representa condições contratuais cadastradas, não margem real.",
    }
