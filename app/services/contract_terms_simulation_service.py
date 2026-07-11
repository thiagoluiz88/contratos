from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Contract, ContractExtraction, ContractTerm, ContractTermSimulation
from app.services.contract_terms_comparison_service import compare_terms_to_simulated, get_current_terms


SIM_STATUS_DRAFT = "rascunho"
SIM_STATUS_SIMULATED = "simulada"
SIM_STATUS_REVIEW = "em_revisao"
SIM_STATUS_APPROVED = "aprovada"
SIM_STATUS_APPLIED = "aplicada"
SIM_STATUS_CANCELLED = "cancelada"
SIM_STATUS_ERROR = "erro"


@dataclass(slots=True)
class SimulationAuditEvent:
    action: str
    entity_type: str | None
    entity_id: int | None
    details: str | None = None
    success: bool = True


def normalize_blank(value: Any) -> str | None:
    if value is None:
        return None
    prepared = str(value).strip()
    return prepared or None


def normalize_decimal(value: Any) -> str | None:
    prepared = normalize_blank(value)
    if not prepared:
        return None
    prepared = prepared.replace("R$", "").replace(" ", "")
    if "," in prepared:
        prepared = prepared.replace(".", "").replace(",", ".")
    try:
        return f"{Decimal(prepared):.2f}"
    except InvalidOperation:
        return None


def parse_date(value: Any):
    prepared = normalize_blank(value)
    if not prepared:
        return None
    try:
        return datetime.strptime(prepared, "%Y-%m-%d").date()
    except ValueError:
        return None


def current_base_version(db: Session, contract_id: int) -> int | None:
    return db.query(func.max(ContractTerm.version)).filter(ContractTerm.contract_id == contract_id, ContractTerm.is_current.is_(True)).scalar()


def next_simulated_version(db: Session, contract_id: int) -> int:
    max_version = db.query(func.max(ContractTerm.version)).filter(ContractTerm.contract_id == contract_id).scalar() or 0
    return int(max_version) + 1


def normalize_term_row(row: dict[str, Any]) -> dict[str, Any] | None:
    category = normalize_blank(row.get("category") or row.get("categoria"))
    title = normalize_blank(row.get("title") or row.get("item"))
    description = normalize_blank(row.get("description") or row.get("descricao"))
    value = normalize_decimal(row.get("reference_value") or row.get("valor") or row.get("value"))
    unit = normalize_blank(row.get("unit") or row.get("unidade"))
    valid_from = normalize_blank(row.get("valid_from") or row.get("vigencia_inicio"))
    valid_until = normalize_blank(row.get("valid_until") or row.get("vigencia_fim"))
    if not title and not description:
        return None
    return {
        "category": category or "outro",
        "title": title or description[:120],
        "description": description,
        "reference_value": value,
        "unit": unit,
        "valid_from": valid_from,
        "valid_until": valid_until,
    }


def validate_simulated_terms(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    valid = []
    warnings = []
    for index, row in enumerate(rows, start=1):
        normalized = normalize_term_row(row)
        if not normalized:
            warnings.append(f"Linha {index} ignorada: item ou descricao obrigatorio.")
            continue
        if normalized["reference_value"] is None:
            warnings.append(f"Linha {index} sem valor aprovado: {normalized['title']}.")
        valid_from = parse_date(normalized.get("valid_from"))
        valid_until = parse_date(normalized.get("valid_until"))
        if normalized.get("valid_from") and valid_from is None:
            warnings.append(f"Linha {index} com inicio de vigencia invalido: {normalized['title']}.")
        if normalized.get("valid_until") and valid_until is None:
            warnings.append(f"Linha {index} com fim de vigencia invalido: {normalized['title']}.")
        if valid_from and valid_until and valid_until < valid_from:
            warnings.append(f"Linha {index} com fim de vigencia anterior ao inicio: {normalized['title']}.")
        valid.append(normalized)
    return valid, warnings


def build_simulation_summary(db: Session, simulation: ContractTermSimulation) -> dict[str, Any]:
    current_terms = get_current_terms(db, simulation.contract_id)
    comparison = compare_terms_to_simulated(
        current_terms,
        list(simulation.simulated_terms_json or []),
        from_version=simulation.base_version,
        simulated_version=simulation.simulated_version,
    )
    return {
        "item_count": len(simulation.simulated_terms_json or []),
        "comparison": comparison["summary"],
        "warnings": (simulation.comparison_summary_json or {}).get("warnings", []),
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    return value


def _save_comparison_summary(db: Session, simulation: ContractTermSimulation, warnings: list[str] | None = None) -> None:
    current_terms = get_current_terms(db, simulation.contract_id)
    comparison = compare_terms_to_simulated(
        current_terms,
        list(simulation.simulated_terms_json or []),
        from_version=simulation.base_version,
        simulated_version=simulation.simulated_version,
    )
    simulation.comparison_summary_json = {
        "summary": json_safe(comparison["summary"]),
        "rows": json_safe(comparison["rows"]),
        "warnings": warnings or [],
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def create_manual_simulation(
    *,
    contract_id: int,
    simulation_name: str,
    terms: list[dict[str, Any]],
    notes: str | None = None,
    created_by: str | None = None,
    base_version: int | None = None,
) -> tuple[ContractTermSimulation, list[SimulationAuditEvent]]:
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError("Contrato nao encontrado.")
        valid_terms, warnings = validate_simulated_terms(terms)
        simulation = ContractTermSimulation(
            contract_id=contract.id,
            simulation_name=simulation_name.strip() or f"Simulacao contrato {contract.id}",
            base_version=base_version if base_version is not None else current_base_version(db, contract.id),
            simulated_version=next_simulated_version(db, contract.id),
            simulation_status=SIM_STATUS_SIMULATED,
            simulated_terms_json=valid_terms,
            created_by=created_by,
            notes=notes,
        )
        db.add(simulation)
        db.flush()
        _save_comparison_summary(db, simulation, warnings)
        db.commit()
        db.refresh(simulation)
        return simulation, [SimulationAuditEvent("contract_term_simulation_created", "contract_term_simulation", simulation.id, simulation.simulation_name)]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_simulation_from_extraction(extraction_id: int, *, created_by: str | None = None) -> tuple[ContractTermSimulation, list[SimulationAuditEvent]]:
    db = SessionLocal()
    try:
        extraction = db.query(ContractExtraction).filter(ContractExtraction.id == extraction_id).first()
        if not extraction:
            raise ValueError("Extracao nao encontrada.")
        if extraction.review_status != "aprovado":
            raise ValueError("Somente extracoes aprovadas podem gerar simulacao.")
        rows = list((extraction.extracted_json or {}).get("condicoes_contratuais") or [])
        valid_terms, warnings = validate_simulated_terms(rows)
        simulation = ContractTermSimulation(
            contract_id=extraction.contract_id,
            source_document_id=extraction.contract_file_id,
            source_extraction_id=extraction.id,
            simulation_name=f"Simulacao a partir de {extraction.contract_file.original_filename if extraction.contract_file else 'extracao'}",
            base_version=current_base_version(db, extraction.contract_id),
            simulated_version=next_simulated_version(db, extraction.contract_id),
            simulation_status=SIM_STATUS_SIMULATED,
            simulated_terms_json=valid_terms,
            created_by=created_by,
            notes="Criada a partir de extracao aprovada.",
        )
        db.add(simulation)
        db.flush()
        _save_comparison_summary(db, simulation, warnings)
        db.commit()
        db.refresh(simulation)
        return simulation, [SimulationAuditEvent("contract_term_simulation_created_from_extraction", "contract_term_simulation", simulation.id, simulation.simulation_name)]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_simulation(db: Session, simulation_id: int) -> ContractTermSimulation | None:
    return db.query(ContractTermSimulation).filter(ContractTermSimulation.id == simulation_id).first()


def compare_simulation_with_current_terms(db: Session, simulation: ContractTermSimulation) -> dict[str, Any]:
    return compare_terms_to_simulated(
        get_current_terms(db, simulation.contract_id),
        list(simulation.simulated_terms_json or []),
        from_version=simulation.base_version,
        simulated_version=simulation.simulated_version,
    )


def approve_simulation(simulation_id: int, *, reviewed_by: str | None = None, contract_id: int | None = None) -> tuple[ContractTermSimulation, list[SimulationAuditEvent]]:
    db = SessionLocal()
    try:
        simulation = get_simulation(db, simulation_id)
        if not simulation:
            raise ValueError("Simulacao nao encontrada.")
        if contract_id is not None and simulation.contract_id != contract_id:
            raise ValueError("Simulacao nao pertence ao contrato informado.")
        if simulation.simulation_status in {SIM_STATUS_APPLIED, SIM_STATUS_CANCELLED}:
            raise ValueError("Simulacao nao pode ser aprovada neste status.")
        simulation.simulation_status = SIM_STATUS_APPROVED
        simulation.reviewed_by = reviewed_by
        simulation.reviewed_at = datetime.utcnow()
        db.commit()
        db.refresh(simulation)
        return simulation, [SimulationAuditEvent("contract_term_simulation_approved", "contract_term_simulation", simulation.id, simulation.simulation_name)]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cancel_simulation(simulation_id: int, *, reviewed_by: str | None = None, contract_id: int | None = None) -> tuple[ContractTermSimulation, list[SimulationAuditEvent]]:
    db = SessionLocal()
    try:
        simulation = get_simulation(db, simulation_id)
        if not simulation:
            raise ValueError("Simulacao nao encontrada.")
        if contract_id is not None and simulation.contract_id != contract_id:
            raise ValueError("Simulacao nao pertence ao contrato informado.")
        if simulation.simulation_status == SIM_STATUS_APPLIED:
            raise ValueError("Simulacao aplicada nao pode ser cancelada.")
        simulation.simulation_status = SIM_STATUS_CANCELLED
        simulation.reviewed_by = reviewed_by
        simulation.reviewed_at = datetime.utcnow()
        db.commit()
        db.refresh(simulation)
        return simulation, [SimulationAuditEvent("contract_term_simulation_cancelled", "contract_term_simulation", simulation.id, simulation.simulation_name)]
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def apply_simulation_to_contract_terms(simulation_id: int, *, applied_by: str | None = None, contract_id: int | None = None) -> tuple[ContractTermSimulation, list[SimulationAuditEvent]]:
    db = SessionLocal()
    events: list[SimulationAuditEvent] = []
    application_started = False
    try:
        simulation = get_simulation(db, simulation_id)
        if not simulation:
            raise ValueError("Simulacao nao encontrada.")
        if contract_id is not None and simulation.contract_id != contract_id:
            raise ValueError("Simulacao nao pertence ao contrato informado.")
        if simulation.simulation_status != SIM_STATUS_APPROVED:
            raise ValueError("Somente simulacao aprovada pode ser aplicada.")
        # O numero proposto pode ter ficado obsoleto se outra simulacao foi aplicada
        # depois da criacao. A versao oficial e sempre calculada no momento da aplicacao.
        version = next_simulated_version(db, simulation.contract_id)
        creatable_rows = [
            row
            for row in (simulation.simulated_terms_json or [])
            if row.get("reference_value") is not None and (row.get("title") or row.get("description"))
        ]
        if not creatable_rows:
            raise ValueError("Simulacao sem itens validos para aplicar.")
        application_started = True
        current_terms = db.query(ContractTerm).filter(ContractTerm.contract_id == simulation.contract_id, ContractTerm.is_current.is_(True)).all()
        valid_from = next((parse_date(row.get("valid_from")) for row in creatable_rows if parse_date(row.get("valid_from"))), None) or date.today()
        for term in current_terms:
            term.is_current = False
            term.valid_until = valid_from
            events.append(SimulationAuditEvent("contract_term_simulation_previous_version_closed", "contract_term", term.id, term.title))
        created_count = 0
        for row in creatable_rows:
            term = ContractTerm(
                contract_id=simulation.contract_id,
                category=row.get("category") or "outro",
                title=row.get("title") or row.get("description") or "Item simulado",
                description=row.get("description"),
                reference_value=Decimal(str(row.get("reference_value"))),
                unit=row.get("unit"),
                version=version,
                valid_from=parse_date(row.get("valid_from")),
                valid_until=parse_date(row.get("valid_until")),
                is_current=True,
                source_type="simulation",
                source_document_id=simulation.source_document_id,
                created_by=applied_by or simulation.created_by,
                status="active",
            )
            db.add(term)
            db.flush()
            created_count += 1
            events.append(SimulationAuditEvent("contract_term_simulation_new_official_version_created", "contract_term", term.id, term.title))
        simulation.simulation_status = SIM_STATUS_APPLIED
        simulation.simulated_version = version
        simulation.applied_by = applied_by
        simulation.applied_at = datetime.utcnow()
        simulation.error_message = None
        summary = simulation.comparison_summary_json or {}
        summary["applied_terms"] = created_count
        summary["applied_version"] = version
        simulation.comparison_summary_json = summary
        events.append(SimulationAuditEvent("contract_term_simulation_applied", "contract_term_simulation", simulation.id, f"v{version}; {created_count} item(ns)."))
        db.commit()
        db.refresh(simulation)
        return simulation, events
    except Exception as exc:
        db.rollback()
        simulation = db.query(ContractTermSimulation).filter(ContractTermSimulation.id == simulation_id).first()
        if simulation and application_started:
            simulation.simulation_status = SIM_STATUS_ERROR
            simulation.error_message = "Falha ao aplicar simulacao."
            db.commit()
        raise exc
    finally:
        db.close()
