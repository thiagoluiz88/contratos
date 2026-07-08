from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import ContractTerm, ReferenceTable, ReferenceTableItem
from app.services.contract_terms_comparison_service import fold_text


def get_active_reference_tables(db: Session) -> list[ReferenceTable]:
    return db.query(ReferenceTable).filter(ReferenceTable.status == "active").order_by(ReferenceTable.name.asc()).all()


def calculate_gap_percent(contract_value, reference_value):
    if contract_value is None or reference_value in (None, 0):
        return None
    contract_decimal = Decimal(str(contract_value))
    reference_decimal = Decimal(str(reference_value))
    if reference_decimal == 0:
        return None
    return ((contract_decimal - reference_decimal) / reference_decimal * Decimal("100")).quantize(Decimal("0.01"))


def classify_gap(contract_value, reference_value) -> str:
    gap = calculate_gap_percent(contract_value, reference_value)
    if gap is None:
        return "sem_referencia"
    if gap > 0:
        return "acima_referencia"
    if gap < 0:
        return "abaixo_referencia"
    return "igual_referencia"


def _reference_key(item: ReferenceTableItem) -> tuple[str, str, str]:
    return fold_text(item.category), fold_text(item.item), fold_text(item.unit)


def _contract_key(term: ContractTerm) -> tuple[str, str, str]:
    return fold_text(term.category), fold_text(term.title), fold_text(term.unit)


def compare_terms_with_reference(db: Session, contract_id: int, reference_table_id: int | None = None) -> dict:
    table = None
    if reference_table_id:
        table = db.query(ReferenceTable).filter(ReferenceTable.id == reference_table_id).first()
    if table is None:
        table = db.query(ReferenceTable).filter(ReferenceTable.status == "active").order_by(ReferenceTable.created_at.desc()).first()
    if table is None:
        return {
            "status": "sem_tabela_referencia",
            "message": "Nenhuma tabela de referencia ativa cadastrada.",
            "rows": [],
            "summary": build_reference_gap_summary([]),
        }
    contract_terms = db.query(ContractTerm).filter(ContractTerm.contract_id == contract_id, ContractTerm.is_current.is_(True)).all()
    reference_items = table.items
    reference_by_key = {_reference_key(item): item for item in reference_items}
    rows = []
    for term in contract_terms:
        reference = reference_by_key.get(_contract_key(term))
        rows.append(
            {
                "category": term.category,
                "item": term.title,
                "unit": term.unit,
                "contract_value": term.reference_value,
                "reference_value": reference.value if reference else None,
                "gap_percent": calculate_gap_percent(term.reference_value, reference.value if reference else None),
                "classification": classify_gap(term.reference_value, reference.value if reference else None),
            }
        )
    return {
        "status": "ok",
        "message": "Comparacao executada com tabela de referencia cadastrada.",
        "reference_table": table,
        "rows": rows,
        "summary": build_reference_gap_summary(rows),
    }


def build_reference_gap_summary(rows: list[dict]) -> dict:
    counts = {
        "acima_referencia": 0,
        "igual_referencia": 0,
        "abaixo_referencia": 0,
        "sem_referencia": 0,
    }
    for row in rows:
        counts[row.get("classification", "sem_referencia")] += 1
    return {"total": len(rows), "counts": counts}


def calculate_market_gap(*args, **kwargs):
    return None


def calculate_defasagem_percent(*args, **kwargs):
    return None


def compare_contract_terms_with_reference(*args, **kwargs) -> dict:
    return compare_terms_with_reference(*args, **kwargs)
