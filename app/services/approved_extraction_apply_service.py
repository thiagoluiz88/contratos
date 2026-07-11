from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Contract, ContractAdditive, ContractExtraction, ContractTerm, Operator


APPLY_STATUS_PENDING = "pendente"
APPLY_STATUS_APPLIED = "aplicado"
APPLY_STATUS_ERROR = "erro_aplicacao"


@dataclass(slots=True)
class AuditEvent:
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    details: str | None = None
    success: bool = True


@dataclass(slots=True)
class ApplyContext:
    extraction: ContractExtraction
    payload: dict[str, Any]
    summary: dict[str, Any] = field(default_factory=dict)
    audit_events: list[AuditEvent] = field(default_factory=list)


def candidate_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def normalize_reviewed_json(payload: dict | None) -> dict[str, Any]:
    payload = payload or {}
    contract_data = payload.get("contrato") if isinstance(payload.get("contrato"), dict) else {}
    normalized_contract = {key: candidate_value(value) for key, value in contract_data.items()}

    conditions = []
    for row in payload.get("condicoes_contratuais") or []:
        if not isinstance(row, dict):
            continue
        conditions.append({key: candidate_value(value) for key, value in row.items()})

    return {
        "contrato": normalized_contract,
        "clausulas_criticas": payload.get("clausulas_criticas") if isinstance(payload.get("clausulas_criticas"), dict) else {},
        "condicoes_contratuais": conditions,
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }


def normalize_blank(value: Any) -> str | None:
    if value is None:
        return None
    prepared = str(value).strip()
    return prepared or None


def normalize_decimal(value: Any) -> Decimal | None:
    prepared = normalize_blank(value)
    if not prepared:
        return None
    prepared = prepared.replace("R$", "").replace(" ", "")
    if "," in prepared:
        prepared = prepared.replace(".", "").replace(",", ".")
    try:
        return Decimal(prepared)
    except InvalidOperation:
        return None


def normalize_date(value: Any):
    prepared = normalize_blank(value)
    if not prepared:
        return None
    try:
        return datetime.strptime(prepared, "%Y-%m-%d").date()
    except ValueError:
        return None


def add_pending(summary: dict[str, Any], message: str) -> None:
    summary.setdefault("pendencias", []).append(message)


def add_ignored(summary: dict[str, Any], message: str) -> None:
    summary.setdefault("campos_ignorados", []).append(message)


def set_if_empty(target, field_name: str, value: Any, summary: dict[str, Any], label: str | None = None) -> bool:
    if value in (None, ""):
        return False
    current = getattr(target, field_name)
    if current in (None, ""):
        setattr(target, field_name, value)
        summary.setdefault("campos_atualizados", []).append(label or field_name)
        return True
    if str(current) != str(value):
        add_ignored(summary, f"{label or field_name}: ja preenchido; valor aprovado nao sobrescrito.")
    return False


def apply_operator_data(db: Session, ctx: ApplyContext) -> Operator | None:
    data = ctx.payload["contrato"]
    operator_name = normalize_blank(data.get("operadora") or data.get("razao_social"))
    legal_name = normalize_blank(data.get("razao_social"))
    tax_id = normalize_blank(data.get("cnpj"))
    ans_registration = normalize_blank(data.get("registro_ans"))

    operator = None
    if tax_id:
        operator = db.query(Operator).filter(Operator.tax_id == tax_id).first()
    if not operator and operator_name:
        operator = db.query(Operator).filter(func.lower(Operator.name) == operator_name.lower()).first()

    if operator:
        updated = False
        updated |= set_if_empty(operator, "legal_name", legal_name, ctx.summary, "razao_social")
        updated |= set_if_empty(operator, "tax_id", tax_id, ctx.summary, "cnpj")
        updated |= set_if_empty(operator, "ans_registration", ans_registration, ctx.summary, "registro_ans")
        ctx.summary["operadora"] = {"status": "localizada", "id": operator.id, "nome": operator.name}
        if updated:
            ctx.audit_events.append(AuditEvent("operator_updated_from_extraction", "operator", operator.id, operator.name))
        return operator

    if operator_name and (tax_id or legal_name):
        operator = Operator(
            name=operator_name,
            legal_name=legal_name,
            tax_id=tax_id,
            ans_registration=ans_registration,
            notes=f"Criada a partir da extracao aprovada #{ctx.extraction.id}.",
            is_active=True,
        )
        db.add(operator)
        db.flush()
        ctx.summary["operadora"] = {"status": "criada", "id": operator.id, "nome": operator.name}
        ctx.audit_events.append(AuditEvent("operator_created_from_extraction", "operator", operator.id, operator.name))
        return operator

    if operator_name:
        add_pending(ctx.summary, "Operadora sem CNPJ/razao social suficiente para criacao segura; revise cadastro manualmente.")
    else:
        add_pending(ctx.summary, "Operadora nao informada nos dados aprovados.")
    return None


def apply_contract_data(db: Session, ctx: ApplyContext, operator: Operator | None) -> Contract | None:
    data = ctx.payload["contrato"]
    document = ctx.extraction.contract_file
    contract = ctx.extraction.contract or (db.query(Contract).filter(Contract.id == document.contract_id).first() if document else None)
    if not contract:
        if not (operator and (data.get("tipo_contrato") or data.get("numero_contrato") or data.get("data_inicio"))):
            add_pending(ctx.summary, "Dados minimos insuficientes para criar contrato automaticamente.")
            return None
        contract = Contract(
            contract_name=data.get("numero_contrato") or f"Contrato {operator.name}",
            operator_id=operator.id,
            operator_name=operator.name,
            contract_type=data.get("tipo_contrato"),
            contract_number=data.get("numero_contrato"),
            start_date=normalize_date(data.get("data_inicio")),
            status="active",
        )
        db.add(contract)
        db.flush()
        ctx.summary["contrato"] = {"status": "criado", "id": contract.id, "nome": contract.contract_name}
        ctx.audit_events.append(AuditEvent("contract_created_from_extraction", "contract", contract.id, contract.contract_name))
        return contract

    if operator:
        set_if_empty(contract, "operator_id", operator.id, ctx.summary, "operadora vinculada")
        set_if_empty(contract, "operator_name", operator.name, ctx.summary, "nome da operadora")
    updates = [
        ("contract_number", data.get("numero_contrato"), "numero do contrato"),
        ("contract_type", data.get("tipo_contrato"), "tipo do contrato"),
        ("signature_date", normalize_date(data.get("data_assinatura")), "data de assinatura"),
        ("start_date", normalize_date(data.get("data_inicio")), "data inicio"),
        ("end_date", normalize_date(data.get("data_fim")), "data fim"),
        ("base_date", normalize_date(data.get("data_base_reajuste")), "data-base de reajuste"),
        ("reajust_index", data.get("indice_reajuste"), "indice de reajuste"),
        ("reajust_percentage", normalize_decimal(data.get("percentual_reajuste")), "percentual de reajuste"),
    ]
    for field_name, value, label in updates:
        set_if_empty(contract, field_name, value, ctx.summary, label)
    if data.get("indice_reajuste") or data.get("percentual_reajuste"):
        contract.reajust_clause_exists = True
    ctx.summary["contrato"] = {"status": "atualizado", "id": contract.id, "nome": contract.contract_name}
    ctx.audit_events.append(AuditEvent("contract_updated_from_extraction", "contract", contract.id, contract.contract_name))
    return contract


def apply_adjustment_or_addendum(db: Session, ctx: ApplyContext, contract: Contract | None) -> ContractAdditive | None:
    if not contract:
        return None
    document = ctx.extraction.contract_file
    document_type = (document.document_type or document.file_type or "").lower() if document else ""
    if document_type != "aditivo":
        return None
    data = ctx.payload["contrato"]
    additive_number = normalize_blank(data.get("numero_contrato")) or f"Documento-{document.id}"
    additive = (
        db.query(ContractAdditive)
        .filter(ContractAdditive.contract_id == contract.id, ContractAdditive.additive_number == additive_number)
        .first()
    )
    if not additive:
        additive = ContractAdditive(
            contract_id=contract.id,
            additive_number=additive_number,
            additive_type=normalize_blank(data.get("tipo_contrato")) or "aditivo",
            signature_date=normalize_date(data.get("data_assinatura")),
            start_date=normalize_date(data.get("data_inicio")),
            end_date=normalize_date(data.get("data_fim")),
            reajust_index=normalize_blank(data.get("indice_reajuste")),
            original_filename=document.original_filename if document else None,
            stored_filepath=document.stored_filepath if document else None,
            raw_text=ctx.extraction.extracted_text_preview,
            status="active",
        )
        db.add(additive)
        db.flush()
        ctx.summary["aditivo"] = {"status": "criado", "id": additive.id, "numero": additive.additive_number}
        ctx.audit_events.append(AuditEvent("contract_additive_created_from_extraction", "contract_additive", additive.id, additive.additive_number))
    else:
        ctx.summary["aditivo"] = {"status": "localizado", "id": additive.id, "numero": additive.additive_number}
        ctx.audit_events.append(AuditEvent("contract_additive_linked_from_extraction", "contract_additive", additive.id, additive.additive_number))
    return additive


def close_previous_terms_version(db: Session, ctx: ApplyContext, contract_id: int, valid_until) -> int:
    current_terms = db.query(ContractTerm).filter(ContractTerm.contract_id == contract_id, ContractTerm.is_current.is_(True)).all()
    closed = 0
    for term in current_terms:
        term.is_current = False
        term.valid_until = valid_until or term.valid_until
        closed += 1
        ctx.audit_events.append(AuditEvent("contract_term_previous_version_closed", "contract_term", term.id, term.title))
    return closed


def create_new_terms_version(db: Session, ctx: ApplyContext, contract_id: int, conditions: list[dict[str, Any]], version: int) -> int:
    created = 0
    document = ctx.extraction.contract_file
    for row in conditions:
        category = normalize_blank(row.get("categoria")) or "outro"
        item = normalize_blank(row.get("item"))
        description = normalize_blank(row.get("descricao"))
        value = normalize_decimal(row.get("valor"))
        evidence = normalize_blank(row.get("evidence"))
        if not item and not description:
            add_pending(ctx.summary, f"Condicao ignorada sem item/descricao na categoria {category}.")
            continue
        if value is None:
            add_pending(ctx.summary, f"Condicao '{item or description}' ignorada sem valor aprovado.")
            continue
        term = ContractTerm(
            contract_id=contract_id,
            category=category,
            title=item or description[:120],
            description=description,
            reference_value=value,
            unit=normalize_blank(row.get("unidade")),
            version=version,
            valid_from=normalize_date(row.get("vigencia_inicio")),
            valid_until=normalize_date(row.get("vigencia_fim")),
            is_current=True,
            source_type="document_extraction",
            source_document_id=document.id if document else None,
            created_by=ctx.extraction.applied_by or ctx.extraction.reviewed_by,
            rule_text=evidence,
            status="active",
        )
        db.add(term)
        db.flush()
        created += 1
        ctx.audit_events.append(AuditEvent("contract_term_new_version_created", "contract_term", term.id, term.title))
    return created


def apply_contract_terms(db: Session, ctx: ApplyContext, contract: Contract | None) -> None:
    if not contract:
        add_pending(ctx.summary, "Condicoes contratuais nao aplicadas porque nao ha contrato vinculado.")
        return
    conditions = ctx.payload.get("condicoes_contratuais") or []
    valid_conditions = [row for row in conditions if isinstance(row, dict)]
    if not valid_conditions:
        ctx.summary["condicoes"] = {"criadas": 0, "versoes_encerradas": 0, "nova_versao": None}
        return
    creatable_conditions = []
    for row in valid_conditions:
        item = normalize_blank(row.get("item"))
        description = normalize_blank(row.get("descricao"))
        value = normalize_decimal(row.get("valor"))
        if not item and not description:
            add_pending(ctx.summary, f"Condicao ignorada sem item/descricao na categoria {normalize_blank(row.get('categoria')) or 'outro'}.")
            continue
        if value is None:
            add_pending(ctx.summary, f"Condicao '{item or description}' ignorada sem valor aprovado.")
            continue
        creatable_conditions.append(row)
    if not creatable_conditions:
        ctx.summary["condicoes"] = {"criadas": 0, "versoes_encerradas": 0, "nova_versao": None}
        return
    max_version = db.query(func.max(ContractTerm.version)).filter(ContractTerm.contract_id == contract.id).scalar() or 0
    next_version = int(max_version) + 1
    valid_from = next((normalize_date(row.get("vigencia_inicio")) for row in creatable_conditions if normalize_date(row.get("vigencia_inicio"))), None)
    closed = close_previous_terms_version(db, ctx, contract.id, valid_from)
    created = create_new_terms_version(db, ctx, contract.id, creatable_conditions, next_version)
    ctx.summary["condicoes"] = {"criadas": created, "versoes_encerradas": closed, "nova_versao": next_version if created else None}


def build_apply_summary(ctx: ApplyContext) -> dict[str, Any]:
    summary = ctx.summary
    summary.setdefault("pendencias", [])
    summary.setdefault("campos_ignorados", [])
    summary["audit_events"] = len(ctx.audit_events)
    summary["applied_at"] = datetime.utcnow().isoformat(timespec="seconds")
    return summary


def apply_approved_extraction(extraction_id: int, user_id: str | None = None) -> tuple[ContractExtraction, list[AuditEvent]]:
    db = SessionLocal()
    application_started = False
    try:
        extraction = db.query(ContractExtraction).filter(ContractExtraction.id == extraction_id).first()
        if not extraction:
            raise ValueError("Extracao nao encontrada.")
        if extraction.review_status != "aprovado":
            raise ValueError("Somente extracoes aprovadas podem ser aplicadas.")
        if extraction.apply_status == APPLY_STATUS_APPLIED:
            raise ValueError("Extracao ja aplicada ao cadastro.")

        extraction.applied_by = user_id
        application_started = True
        ctx = ApplyContext(extraction=extraction, payload=normalize_reviewed_json(extraction.extracted_json))
        ctx.audit_events.append(AuditEvent("approved_extraction_apply_started", "contract_extraction", extraction.id, "Aplicacao iniciada."))
        operator = apply_operator_data(db, ctx)
        contract = apply_contract_data(db, ctx, operator)
        apply_adjustment_or_addendum(db, ctx, contract)
        apply_contract_terms(db, ctx, contract)

        now = datetime.utcnow()
        extraction.apply_status = APPLY_STATUS_APPLIED
        extraction.applied_at = now
        extraction.apply_error = None
        extraction.apply_summary = build_apply_summary(ctx)
        ctx.audit_events.append(AuditEvent("approved_extraction_apply_completed", "contract_extraction", extraction.id, "Aplicacao concluida."))
        if extraction.apply_summary.get("pendencias"):
            ctx.audit_events.append(AuditEvent("approved_extraction_apply_pending_items", "contract_extraction", extraction.id, f"{len(extraction.apply_summary['pendencias'])} pendencia(s)."))
        db.commit()
        db.refresh(extraction)
        return extraction, ctx.audit_events
    except Exception as exc:
        db.rollback()
        extraction = db.query(ContractExtraction).filter(ContractExtraction.id == extraction_id).first()
        if extraction and application_started:
            extraction.apply_status = APPLY_STATUS_ERROR
            extraction.apply_error = "Falha ao aplicar dados aprovados."
            extraction.apply_summary = {"erros": ["Falha ao aplicar dados aprovados."], "pendencias": []}
            db.commit()
        raise exc
    finally:
        db.close()
