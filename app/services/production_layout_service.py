from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ProductionImportLayout, ProductionImportLayoutMapping
from app.services.production_import_service import fold_column


TARGET_FIELDS = ("operadora", "contrato", "competencia", "data_atendimento", "categoria", "item", "descricao", "quantidade", "unidade", "valor_faturado", "valor_pago", "valor_glosado", "custo", "guia", "conta", "atendimento", "paciente_referencia")
REQUIRED_TARGET_FIELDS = set(TARGET_FIELDS[:13])
ALLOWED_SYSTEMS = {"tasy", "mv", "philips", "planilha", "outro"}
ALLOWED_TYPES = {"csv", "excel"}
ALLOWED_STATUS = {"ativo", "inativo", "rascunho"}
ALLOWED_TRANSFORMS = {None, "", "strip", "upper", "lower", "digits"}


def normalize_source_columns(columns: list[str]) -> dict[str, str]:
    return {fold_column(column): column for column in columns if column}


def get_required_target_fields() -> set[str]:
    return set(REQUIRED_TARGET_FIELDS)


def validate_layout(layout: ProductionImportLayout) -> dict[str, Any]:
    errors = []
    if not layout.name.strip(): errors.append("Nome do layout é obrigatório.")
    if layout.source_system not in ALLOWED_SYSTEMS: errors.append("Sistema de origem inválido.")
    if layout.source_type not in ALLOWED_TYPES: errors.append("Tipo de origem inválido.")
    if layout.status not in ALLOWED_STATUS: errors.append("Status inválido.")
    targets = [mapping.target_field for mapping in layout.mappings]
    invalid = sorted(set(targets) - set(TARGET_FIELDS))
    duplicates = sorted({target for target in targets if targets.count(target) > 1})
    missing = sorted(REQUIRED_TARGET_FIELDS - set(targets))
    if invalid: errors.append(f"Campos alvo inválidos: {', '.join(invalid)}.")
    if duplicates: errors.append(f"Campos alvo duplicados: {', '.join(duplicates)}.")
    for mapping in layout.mappings:
        if not mapping.source_column.strip() and mapping.default_value in (None, ""): errors.append(f"Origem ausente para {mapping.target_field}.")
        if mapping.transform_rule not in ALLOWED_TRANSFORMS: errors.append(f"Transformação inválida em {mapping.target_field}.")
    return {"valid": not errors and not missing, "errors": errors, "missing_required_fields": missing, "mapped_fields": len(targets)}


def _mapping_records(mappings: list[dict[str, Any]]) -> list[ProductionImportLayoutMapping]:
    records = []
    for row in mappings:
        target = str(row.get("target_field") or "").strip()
        source = str(row.get("source_column") or "").strip()
        default = str(row.get("default_value") or "").strip() or None
        if not target or (not source and default is None):
            continue
        records.append(ProductionImportLayoutMapping(target_field=target, source_column=source, required=bool(row.get("required") or target in REQUIRED_TARGET_FIELDS), default_value=default, transform_rule=str(row.get("transform_rule") or "").strip() or None))
    return records


def create_layout(*, name: str, source_system: str, source_type: str, delimiter: str | None, encoding: str | None, has_header: bool, status: str, mappings: list[dict[str, Any]], created_by: str | None = None, notes: str | None = None) -> ProductionImportLayout:
    db = SessionLocal()
    try:
        layout = ProductionImportLayout(name=name.strip(), source_system=source_system, source_type=source_type, delimiter=delimiter or None, encoding=encoding or None, has_header=has_header, status=status, created_by=created_by, notes=notes, mappings=_mapping_records(mappings))
        validation = validate_layout(layout)
        if validation["errors"]:
            raise ValueError(" ".join(validation["errors"]))
        if status == "ativo" and validation["missing_required_fields"]:
            raise ValueError(f"Layout ativo sem campos obrigatórios: {', '.join(validation['missing_required_fields'])}.")
        db.add(layout); db.commit(); db.refresh(layout); return layout
    except Exception:
        db.rollback(); raise
    finally: db.close()


def update_layout(layout_id: int, **values) -> ProductionImportLayout:
    db = SessionLocal()
    try:
        layout = db.query(ProductionImportLayout).filter(ProductionImportLayout.id == layout_id).first()
        if not layout: raise ValueError("Layout não encontrado.")
        for field in ("name", "source_system", "source_type", "delimiter", "encoding", "has_header", "status", "notes"):
            if field in values: setattr(layout, field, values[field])
        if "mappings" in values:
            layout.mappings.clear(); layout.mappings.extend(_mapping_records(values["mappings"]))
        validation = validate_layout(layout)
        if validation["errors"]: raise ValueError(" ".join(validation["errors"]))
        if layout.status == "ativo" and validation["missing_required_fields"]: raise ValueError(f"Layout ativo sem campos obrigatórios: {', '.join(validation['missing_required_fields'])}.")
        db.commit(); db.refresh(layout); return layout
    except Exception:
        db.rollback(); raise
    finally: db.close()


def list_layouts(db: Session, active_only: bool = False):
    query = db.query(ProductionImportLayout)
    if active_only: query = query.filter(ProductionImportLayout.status == "ativo")
    return query.order_by(ProductionImportLayout.name).all()


def get_layout(db: Session, layout_id: int):
    return db.query(ProductionImportLayout).filter(ProductionImportLayout.id == layout_id).first()


def _transform(value: Any, rule: str | None):
    if value is None: return None
    text = str(value).strip()
    if rule == "upper": return text.upper()
    if rule == "lower": return text.lower()
    if rule == "digits": return "".join(char for char in text if char.isdigit())
    return text


def apply_layout_mapping(row: dict[str, Any], layout: ProductionImportLayout) -> dict[str, Any]:
    sources = normalize_source_columns(list(row.keys()))
    mapped = {}
    for mapping in layout.mappings:
        original = sources.get(fold_column(mapping.source_column))
        value = row.get(original) if original is not None else mapping.default_value
        if value in (None, "") and mapping.default_value is not None: value = mapping.default_value
        mapped[mapping.target_field] = _transform(value, mapping.transform_rule)
    return mapped


def detect_unmapped_columns(columns: list[str], layout: ProductionImportLayout) -> list[str]:
    mapped = {fold_column(mapping.source_column) for mapping in layout.mappings}
    return [column for column in columns if fold_column(column) not in mapped]


def detect_missing_required_columns(columns: list[str], layout: ProductionImportLayout) -> list[str]:
    sources = normalize_source_columns(columns)
    return [mapping.target_field for mapping in layout.mappings if mapping.required and fold_column(mapping.source_column) not in sources and mapping.default_value in (None, "")]


def build_layout_preview(rows: list[dict[str, Any]], layout: ProductionImportLayout, limit: int = 5) -> dict[str, Any]:
    columns = list(rows[0].keys()) if rows else []
    return {"layout": layout, "recognized_columns": [column for column in columns if column not in detect_unmapped_columns(columns, layout)], "unmapped_columns": detect_unmapped_columns(columns, layout), "missing_required_fields": detect_missing_required_columns(columns, layout), "rows": [apply_layout_mapping(row, layout) for row in rows[:limit]]}
