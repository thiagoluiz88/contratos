from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ContractTerm


CHANGE_UNCHANGED = "sem_alteracao"
CHANGE_NEW = "novo"
CHANGE_REMOVED = "removido"
CHANGE_INCREASE = "aumento"
CHANGE_DECREASE = "reducao"
CHANGE_DESCRIPTION = "alteracao_descricao"
CHANGE_UNIT = "alteracao_unidade"
CHANGE_VALIDITY = "alteracao_vigencia"


@dataclass(slots=True)
class TermVersionInfo:
    version: int
    valid_from: Any
    valid_until: Any
    is_current: bool
    item_count: int
    total_value: Decimal
    source_document_id: int | None
    created_by: str | None
    created_at: Any


def fold_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    folded = "".join(char for char in normalized if not unicodedata.combining(char)).lower()
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def term_field(term: ContractTerm | dict | None, attr: str, default=None):
    if term is None:
        return default
    if isinstance(term, dict):
        aliases = {
            "category": ("category", "categoria"),
            "title": ("title", "item"),
            "description": ("description", "descricao"),
            "reference_value": ("reference_value", "valor", "value"),
            "unit": ("unit", "unidade"),
            "valid_from": ("valid_from", "vigencia_inicio"),
            "valid_until": ("valid_until", "vigencia_fim"),
            "id": ("id",),
        }
        for key in aliases.get(attr, (attr,)):
            if key in term:
                return term.get(key)
        return default
    return getattr(term, attr, default)


def normalize_term_key(term: ContractTerm | dict) -> tuple[str, str, str]:
    category = term_field(term, "category")
    title = term_field(term, "title")
    unit = term_field(term, "unit")
    return fold_text(category), fold_text(title), fold_text(unit)


def money(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def comparable_date(value):
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def calculate_value_difference(old_value, new_value) -> dict[str, Any]:
    old_decimal = money(old_value)
    new_decimal = money(new_value)
    if old_decimal is None and new_decimal is None:
        return {"amount": None, "percent": None}
    if old_decimal is None or new_decimal is None:
        return {"amount": None, "percent": None}
    amount = new_decimal - old_decimal
    percent = None if old_decimal == 0 else (amount / old_decimal) * Decimal("100")
    return {
        "amount": amount.quantize(Decimal("0.01")),
        "percent": percent.quantize(Decimal("0.01")) if percent is not None else None,
    }


def classify_term_change(old_term: ContractTerm | dict | None, new_term: ContractTerm | dict | None) -> str:
    if old_term is None and new_term is not None:
        return CHANGE_NEW
    if old_term is not None and new_term is None:
        return CHANGE_REMOVED
    if old_term is None or new_term is None:
        return CHANGE_UNCHANGED
    old_value = money(term_field(old_term, "reference_value"))
    new_value = money(term_field(new_term, "reference_value"))
    if old_value is not None and new_value is not None:
        if new_value > old_value:
            return CHANGE_INCREASE
        if new_value < old_value:
            return CHANGE_DECREASE
    if fold_text(term_field(old_term, "unit")) != fold_text(term_field(new_term, "unit")):
        return CHANGE_UNIT
    if fold_text(term_field(old_term, "description") or getattr(old_term, "rule_text", None)) != fold_text(term_field(new_term, "description") or getattr(new_term, "rule_text", None)):
        return CHANGE_DESCRIPTION
    if comparable_date(term_field(old_term, "valid_from")) != comparable_date(term_field(new_term, "valid_from")) or comparable_date(term_field(old_term, "valid_until")) != comparable_date(term_field(new_term, "valid_until")):
        return CHANGE_VALIDITY
    return CHANGE_UNCHANGED


def get_contract_terms_versions(db: Session, contract_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(
            ContractTerm.version,
            func.min(ContractTerm.valid_from),
            func.max(ContractTerm.valid_until),
            func.count(ContractTerm.id),
            func.coalesce(func.sum(ContractTerm.reference_value), 0),
            func.max(ContractTerm.source_document_id),
            func.max(ContractTerm.created_by),
            func.min(ContractTerm.created_at),
            func.bool_or(ContractTerm.is_current),
        )
        .filter(ContractTerm.contract_id == contract_id)
        .group_by(ContractTerm.version)
        .order_by(ContractTerm.version.desc())
        .all()
    )
    return [
        {
            "version": row[0],
            "valid_from": row[1],
            "valid_until": row[2],
            "item_count": row[3],
            "total_value": Decimal(str(row[4] or 0)),
            "source_document_id": row[5],
            "created_by": row[6],
            "created_at": row[7],
            "is_current": bool(row[8]),
        }
        for row in rows
    ]


def get_current_terms(db: Session, contract_id: int) -> list[ContractTerm]:
    return (
        db.query(ContractTerm)
        .filter(ContractTerm.contract_id == contract_id, ContractTerm.is_current.is_(True))
        .order_by(ContractTerm.category.asc(), ContractTerm.title.asc())
        .all()
    )


def get_terms_by_version(db: Session, contract_id: int, version: int) -> list[ContractTerm]:
    return (
        db.query(ContractTerm)
        .filter(ContractTerm.contract_id == contract_id, ContractTerm.version == version)
        .order_by(ContractTerm.category.asc(), ContractTerm.title.asc())
        .all()
    )


def similar_enough(old_term: ContractTerm | dict, new_term: ContractTerm | dict) -> bool:
    if fold_text(term_field(old_term, "category")) != fold_text(term_field(new_term, "category")):
        return False
    old_title = fold_text(term_field(old_term, "title"))
    new_title = fold_text(term_field(new_term, "title"))
    if not old_title or not new_title:
        return False
    return SequenceMatcher(None, old_title, new_title).ratio() >= 0.82


def match_terms(old_terms: list, new_terms: list) -> list[tuple[Any | None, Any | None]]:
    remaining_old = list(old_terms)
    remaining_new = list(new_terms)
    matches: list[tuple[ContractTerm | None, ContractTerm | None]] = []

    for old_term in list(remaining_old):
        old_key = normalize_term_key(old_term)
        exact = next((new for new in remaining_new if normalize_term_key(new) == old_key), None)
        if exact:
            matches.append((old_term, exact))
            remaining_old.remove(old_term)
            remaining_new.remove(exact)

    for old_term in list(remaining_old):
        similar = next((new for new in remaining_new if similar_enough(old_term, new)), None)
        if similar:
            matches.append((old_term, similar))
            remaining_old.remove(old_term)
            remaining_new.remove(similar)

    matches.extend((old, None) for old in remaining_old)
    matches.extend((None, new) for new in remaining_new)
    return matches


def format_decimal(value: Decimal | None) -> str | None:
    return f"{value:.2f}" if value is not None else None


def comparison_row(old_term: ContractTerm | dict | None, new_term: ContractTerm | dict | None) -> dict[str, Any]:
    change_type = classify_term_change(old_term, new_term)
    diff = calculate_value_difference(
        term_field(old_term, "reference_value"),
        term_field(new_term, "reference_value"),
    )
    base = new_term or old_term
    return {
        "category": term_field(base, "category", "-"),
        "item": term_field(base, "title", "-"),
        "unit": (term_field(new_term, "unit") or term_field(old_term, "unit")) or "-",
        "old_value": term_field(old_term, "reference_value"),
        "new_value": term_field(new_term, "reference_value"),
        "difference_amount": diff["amount"],
        "difference_percent": diff["percent"],
        "change_type": change_type,
        "old_valid_from": term_field(old_term, "valid_from"),
        "old_valid_until": term_field(old_term, "valid_until"),
        "new_valid_from": term_field(new_term, "valid_from"),
        "new_valid_until": term_field(new_term, "valid_until"),
        "old_term_id": term_field(old_term, "id"),
        "new_term_id": term_field(new_term, "id"),
    }


def build_comparison_summary(rows: list[dict[str, Any]], old_terms: list[ContractTerm], new_terms: list[ContractTerm]) -> dict[str, Any]:
    counts = {
        CHANGE_UNCHANGED: 0,
        CHANGE_NEW: 0,
        CHANGE_REMOVED: 0,
        CHANGE_INCREASE: 0,
        CHANGE_DECREASE: 0,
        CHANGE_DESCRIPTION: 0,
        CHANGE_UNIT: 0,
        CHANGE_VALIDITY: 0,
    }
    for row in rows:
        counts[row["change_type"]] = counts.get(row["change_type"], 0) + 1
    increases = [row for row in rows if row["change_type"] == CHANGE_INCREASE and row["difference_percent"] is not None]
    reductions = [row for row in rows if row["change_type"] == CHANGE_DECREASE and row["difference_percent"] is not None]
    old_total = sum((money(term_field(term, "reference_value")) or Decimal("0")) for term in old_terms)
    new_total = sum((money(term_field(term, "reference_value")) or Decimal("0")) for term in new_terms)
    return {
        "old_count": len(old_terms),
        "new_count": len(new_terms),
        "counts": counts,
        "largest_increase_percent": max((row["difference_percent"] for row in increases), default=None),
        "largest_decrease_percent": min((row["difference_percent"] for row in reductions), default=None),
        "old_total": old_total,
        "new_total": new_total,
        "estimated_financial_impact": None,
        "impact_message": "Impacto financeiro depende de volume assistencial e ainda nao foi calculado.",
    }


def compare_terms_versions(db: Session, contract_id: int, from_version: int, to_version: int) -> dict[str, Any]:
    old_terms = get_terms_by_version(db, contract_id, from_version)
    new_terms = get_terms_by_version(db, contract_id, to_version)
    rows = [comparison_row(old, new) for old, new in match_terms(old_terms, new_terms)]
    rows.sort(key=lambda row: (row["category"] or "", row["item"] or "", row["change_type"]))
    return {
        "from_version": from_version,
        "to_version": to_version,
        "old_terms": old_terms,
        "new_terms": new_terms,
        "rows": rows,
        "summary": build_comparison_summary(rows, old_terms, new_terms),
    }


def compare_terms_to_simulated(current_terms: list[ContractTerm], simulated_terms: list[dict[str, Any]], *, from_version: int | None = None, simulated_version: int | None = None) -> dict[str, Any]:
    rows = [comparison_row(old, new) for old, new in match_terms(current_terms, simulated_terms)]
    rows.sort(key=lambda row: (row["category"] or "", row["item"] or "", row["change_type"]))
    return {
        "from_version": from_version,
        "to_version": simulated_version,
        "old_terms": current_terms,
        "new_terms": simulated_terms,
        "rows": rows,
        "summary": build_comparison_summary(rows, current_terms, simulated_terms),
    }
