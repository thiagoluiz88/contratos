from pathlib import Path
from datetime import date, datetime, time
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import func, or_, text
from starlette.middleware.sessions import SessionMiddleware

from .config import (
    BASE_DIR,
    SESSION_MAX_AGE_SECONDS,
    SESSION_HTTPS_ONLY,
    SESSION_SECRET,
    STATIC_DIR,
    TEMPLATES_DIR,
    UPLOAD_DIR,
    ENABLE_SELF_REGISTRATION,
)
from .security import CSRFMiddleware
from .database import SessionLocal
from .models import (
    AccessProfile,
    AuditLog,
    AuthAuditEvent,
    Contract,
    ContractAdditive,
    ContractAdjustment,
    ContractComparison,
    ContractComparisonItem,
    ContractEvent,
    ContractExtraction,
    ContractFile,
    ContractTerm,
    ContractTermSimulation,
    CostAllocationRule,
    CostCenter,
    ImportBatch,
    Operator,
    ProductionImportBatch,
    ProductionImportLayout,
    ProductionImportLayoutMapping,
    ProductionRecord,
    ReferenceTable,
    ReferenceTableItem,
    User,
)
from .services.auth import (
    ADDITIVE_VIEW_PROFILES,
    ADMIN_PROFILES,
    ANALYSIS_VIEW_PROFILES,
    ANALYSIS_WRITE_PROFILES,
    AUDIT_PROFILES,
    CONTRACT_WRITE_PROFILES,
    DEFAULT_REGISTER_PROFILE,
    FINANCIAL_PROFILES,
    PROFILE_ADMIN,
    PROFILE_AUDIT,
    PROFILE_CONTRACTS,
    PROFILE_EXECUTIVE,
    PROFILE_FINANCIAL,
    PROFILE_READ_ONLY,
    ensure_initial_admin,
    get_access_profile,
    has_profile,
    hash_password,
    record_auth_event,
    upgrade_legacy_password_hashes,
    user_session_payload,
    validate_password_strength,
    verify_password,
)

APPLY_APPROVED_EXTRACTION_PROFILES = CONTRACT_WRITE_PROFILES | {PROFILE_EXECUTIVE}
COMMERCIAL_BI_VIEW_PROFILES = {PROFILE_ADMIN, PROFILE_EXECUTIVE, PROFILE_CONTRACTS, PROFILE_FINANCIAL, PROFILE_AUDIT, PROFILE_READ_ONLY}
COMMERCIAL_BI_EXPORT_PROFILES = COMMERCIAL_BI_VIEW_PROFILES - {PROFILE_READ_ONLY}
PRODUCTION_VIEW_PROFILES = {PROFILE_ADMIN, PROFILE_EXECUTIVE, PROFILE_CONTRACTS, PROFILE_FINANCIAL, PROFILE_AUDIT}
PRODUCTION_IMPORT_PROFILES = {PROFILE_ADMIN, PROFILE_CONTRACTS, PROFILE_FINANCIAL}
PRODUCTION_LAYOUT_VIEW_PROFILES = COMMERCIAL_BI_VIEW_PROFILES
PRODUCTION_LAYOUT_MANAGE_PROFILES = PRODUCTION_IMPORT_PROFILES
COST_VIEW_PROFILES = {PROFILE_ADMIN, PROFILE_EXECUTIVE, PROFILE_FINANCIAL, PROFILE_AUDIT, PROFILE_CONTRACTS, PROFILE_READ_ONLY}
COST_MANAGE_PROFILES = {PROFILE_ADMIN, PROFILE_EXECUTIVE, PROFILE_FINANCIAL}


app = FastAPI(title="Contracts Intelligence")
app.add_middleware(CSRFMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
    max_age=SESSION_MAX_AGE_SECONDS,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


def audit_note_display(value: str | None) -> str:
    if not value:
        return "-"
    replacements = {
        "Analise": "Análise",
        "analise": "análise",
        "Usuario": "Usuário",
        "usuario": "usuário",
        "apos": "após",
        "credenciais invalidas": "credenciais inválidas",
        "sem exclusao": "sem exclusão",
        "apos validacao": "após validação",
    }
    text = value
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


templates.env.filters["audit_note_display"] = audit_note_display
templates.env.globals["has_profile"] = has_profile
templates.env.globals["ADMIN_PROFILES"] = ADMIN_PROFILES
templates.env.globals["AUDIT_PROFILES"] = AUDIT_PROFILES
templates.env.globals["CONTRACT_WRITE_PROFILES"] = CONTRACT_WRITE_PROFILES
templates.env.globals["ADDITIVE_VIEW_PROFILES"] = ADDITIVE_VIEW_PROFILES
templates.env.globals["ANALYSIS_VIEW_PROFILES"] = ANALYSIS_VIEW_PROFILES
templates.env.globals["ANALYSIS_WRITE_PROFILES"] = ANALYSIS_WRITE_PROFILES
templates.env.globals["FINANCIAL_PROFILES"] = FINANCIAL_PROFILES
templates.env.globals["APPLY_APPROVED_EXTRACTION_PROFILES"] = APPLY_APPROVED_EXTRACTION_PROFILES
templates.env.globals["COMMERCIAL_BI_VIEW_PROFILES"] = COMMERCIAL_BI_VIEW_PROFILES
templates.env.globals["COMMERCIAL_BI_EXPORT_PROFILES"] = COMMERCIAL_BI_EXPORT_PROFILES
templates.env.globals["PRODUCTION_VIEW_PROFILES"] = PRODUCTION_VIEW_PROFILES
templates.env.globals["PRODUCTION_IMPORT_PROFILES"] = PRODUCTION_IMPORT_PROFILES
templates.env.globals["PRODUCTION_LAYOUT_VIEW_PROFILES"] = PRODUCTION_LAYOUT_VIEW_PROFILES
templates.env.globals["PRODUCTION_LAYOUT_MANAGE_PROFILES"] = PRODUCTION_LAYOUT_MANAGE_PROFILES
templates.env.globals["COST_VIEW_PROFILES"] = COST_VIEW_PROFILES
templates.env.globals["COST_MANAGE_PROFILES"] = COST_MANAGE_PROFILES
templates.env.globals["ENABLE_SELF_REGISTRATION"] = ENABLE_SELF_REGISTRATION
SUPPORTED_CONTRACT_EXTENSIONS = {".pdf", ".docx", ".txt"}
DEFAULT_OPERATOR_NAMES = []

LOG_DIR = BASE_DIR / ".codex-run"
LOG_DIR.mkdir(parents=True, exist_ok=True)
security_logger = logging.getLogger("contracts.security")
if not security_logger.handlers:
    handler = RotatingFileHandler(LOG_DIR / "app-errors.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    security_logger.addHandler(handler)
    security_logger.setLevel(logging.INFO)


def format_br_date(value):
    return value.strftime("%d/%m/%Y") if value else "-"


def parse_optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value and value.strip() else None


def parse_optional_int(value: str | None) -> int | None:
    return int(value) if value and value.strip() else None


def contract_form_data(contract: Contract) -> dict:
    fields = (
        "contract_name",
        "parent_contract_id",
        "contract_type",
        "operator_name",
        "contract_number",
        "status",
        "responsible_name",
        "contract_object",
        "signature_date",
        "start_date",
        "end_date",
        "auto_renewal",
        "renewal_details",
        "termination_notice_days",
        "payment_term_days",
        "payment_trigger",
        "payment_interest_clause",
        "payment_penalty_clause",
        "billing_deadline_days",
        "billing_deadline_description",
        "allows_glosa_unilateral",
        "glosa_deadline_days",
        "glosa_appeal_deadline_days",
        "glosa_response_deadline_days",
        "glosa_clause_summary",
        "reajust_clause_exists",
        "reajust_frequency",
        "reajust_index",
        "reajust_percentage",
        "base_date",
        "reajust_clause_summary",
        "observations",
        "medical_fee_table",
        "medical_fee_table_version",
        "daily_rate_table",
        "materials_table",
        "materials_table_version",
        "medicines_table",
        "medicines_table_version",
    )
    data = {field: getattr(contract, field) for field in fields}
    data["parent_contract_id"] = data["parent_contract_id"] or ""
    for field in ("signature_date", "start_date", "end_date", "base_date"):
        data[field] = data[field].isoformat() if data[field] else ""
    return data


def contract_status(contract: Contract) -> tuple[str, str]:
    if getattr(contract, "status", "active") == "inactive":
        return "Inativo", "expired"
    if getattr(contract, "status", "active") == "draft":
        return "Pendente", "warning"
    if not contract.end_date:
        return "Importado", "imported"

    days_left = (contract.end_date - date.today()).days
    if days_left < 0:
        return "Vencido", "expired"
    if days_left <= 30:
        return "Vencendo", "warning"
    return "Ativo", "active"


def score_class(score: float | None) -> str:
    value = score or 0
    if value >= 80:
        return "good"
    if value >= 60:
        return "caution"
    return "low"


def status_meta(contract: Contract) -> dict:
    label, tone = contract_status(contract)
    return {"label": label, "tone": tone}


def badge_class(risk_level: str | None) -> str:
    normalized = (risk_level or "").lower()
    if "baixo" in normalized:
        return "emerald"
    if "moderado" in normalized:
        return "amber"
    if "alto" in normalized or "crítico" in normalized:
        return "rose"
    return "slate"


templates.env.globals["status_meta"] = status_meta
templates.env.globals["badge_class"] = badge_class


def operator_logo_class(operator_name: str | None) -> str:
    normalized = (operator_name or "").lower()
    if "unimed" in normalized:
        return "unimed"
    if "amil" in normalized:
        return "amil"
    if "bradesco" in normalized:
        return "bradesco"
    if "sul" in normalized:
        return "sulamerica"
    if "hapvida" in normalized:
        return "hapvida"
    return "imported"


def latest_contract_analysis_context(contract_id: int | None = None):
    from .services.ai_analysis import build_contract_analysis

    db = SessionLocal()
    try:
        contracts = db.query(Contract).order_by(Contract.created_at.desc()).all()
        selected_contract = None
        if contract_id is not None:
            selected_contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if selected_contract is None:
            selected_contract = contracts[0] if contracts else None
        return selected_contract, contracts, build_contract_analysis(selected_contract) if selected_contract else None
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    try:
        db = SessionLocal()
        try:
            ensure_initial_admin(db)
            upgrade_legacy_password_hashes(db)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            security_logger.exception("Falha ao garantir administrador inicial")
        finally:
            db.close()
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    except OperationalError as exc:
        security_logger.exception("Falha ao inicializar conexão com o banco")


@app.get("/health")
def health():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        security_logger.exception("Falha no health check do PostgreSQL")
        return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)
    finally:
        db.close()
    return {"status": "ok", "database": "ok"}


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
    session_user = request.session.get("user") or {}
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == session_user.get("id")).first()
        if not user or not user.is_active or (user.access_profile and not user.access_profile.is_active):
            request.session.clear()
            return RedirectResponse("/login", status_code=303)
        request.session["user"] = user_session_payload(user)
        request.session["last_seen"] = datetime.utcnow().isoformat()
    finally:
        db.close()
    return None


def forbidden_response(request: Request, message: str = "Acesso negado."):
    wants_json = "application/json" in request.headers.get("accept", "").lower()
    if wants_json:
        return JSONResponse({"error": message}, status_code=403)
    return templates.TemplateResponse(
        request,
        "forbidden.html",
        {
            "title": "Acesso negado",
            "active_page": None,
            "user": request.session.get("user"),
            "message": message,
        },
        status_code=403,
    )


def require_profiles(request: Request, allowed_profiles: set[str], message: str = "Acesso negado."):
    if redirect := require_login(request):
        return redirect
    if not has_profile(request.session.get("user"), allowed_profiles):
        return forbidden_response(request, message)
    return None


def current_username(request: Request) -> str | None:
    return request.session.get("user", {}).get("username")


def record_service_audit_events(db, request: Request, events) -> None:
    for event in events:
        record_audit_log(
            db,
            request,
            event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            success=event.success,
            details=event.details,
        )


def record_audit_log(
    db,
    request: Request,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    success: bool = True,
    details: str | None = None,
) -> None:
    session_user = request.session.get("user") or {}
    db.add(
        AuditLog(
            user_id=session_user.get("id"),
            username=session_user.get("username"),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            success=success,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details=details,
        )
    )


def csrf_token(request: Request) -> str:
    return request.session.get("csrf_token", "")


templates.env.globals["csrf_token"] = csrf_token


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    security_logger.exception("Erro interno em %s %s", request.method, request.url.path)
    return templates.TemplateResponse(
        request,
        "error_500.html",
        {"title": "Erro interno", "active_page": None, "user": request.session.get("user")},
        status_code=500,
    )


def active_admin_count(db) -> int:
    return (
        db.query(User)
        .join(AccessProfile)
        .filter(User.is_active.is_(True), AccessProfile.name == PROFILE_ADMIN, AccessProfile.is_active.is_(True))
        .count()
    )


def latest_extraction_for_file(db, contract_file_id: int) -> ContractExtraction | None:
    return (
        db.query(ContractExtraction)
        .filter(ContractExtraction.contract_file_id == contract_file_id)
        .order_by(ContractExtraction.created_at.desc())
        .first()
    )


def extraction_payload_from_form(form) -> dict:
    def reviewed_candidate(name: str) -> dict:
        value = str(form.get(name, "")).strip() or None
        return {"value": value, "confidence": 1.0 if value else 0, "evidence": None, "reviewed": True}

    def reviewed_clause(name: str, category: str) -> list[dict]:
        value = str(form.get(name, "")).strip()
        if not value:
            return []
        return [{"categoria": category, "value": value, "confidence": 1.0, "evidence": None, "reviewed": True}]

    return {
        "raw_text_available": None,
        "metadata": {
            "analysis_version": "1.0",
            "analysis_method": "human_review",
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "requires_human_validation": False,
            "human_reviewed": True,
        },
        "contrato": {
            "operadora": reviewed_candidate("contrato_operadora"),
            "razao_social": reviewed_candidate("contrato_razao_social"),
            "cnpj": reviewed_candidate("contrato_cnpj"),
            "registro_ans": reviewed_candidate("contrato_registro_ans"),
            "numero_contrato": reviewed_candidate("contrato_numero"),
            "tipo_contrato": reviewed_candidate("contrato_tipo"),
            "data_assinatura": reviewed_candidate("contrato_data_assinatura"),
            "data_inicio": reviewed_candidate("contrato_data_inicio"),
            "data_fim": reviewed_candidate("contrato_data_fim"),
            "data_base_reajuste": reviewed_candidate("contrato_data_base"),
            "indice_reajuste": reviewed_candidate("contrato_indice"),
            "percentual_reajuste": reviewed_candidate("contrato_percentual"),
        },
        "clausulas_criticas": {
            "prazo_faturamento": reviewed_clause("clausula_prazo_faturamento", "prazo_faturamento"),
            "prazo_recurso_glosa": reviewed_clause("clausula_prazo_recurso_glosa", "prazo_recurso_glosa"),
            "regras_glosa": reviewed_clause("clausula_regras_glosa", "regras_glosa"),
            "regras_autorizacao": reviewed_clause("clausula_regras_autorizacao", "regras_autorizacao"),
            "multas": reviewed_clause("clausula_multas", "multas"),
            "auditoria": reviewed_clause("clausula_auditoria", "auditoria"),
        },
        "condicoes_contratuais": [
            {
                "categoria": str(form.get("condicao_categoria", "")).strip() or None,
                "item": str(form.get("condicao_item", "")).strip() or None,
                "descricao": str(form.get("condicao_descricao", "")).strip() or None,
                "valor": str(form.get("condicao_valor", "")).strip() or None,
                "unidade": str(form.get("condicao_unidade", "")).strip() or None,
                "vigencia_inicio": str(form.get("condicao_vigencia_inicio", "")).strip() or None,
                "vigencia_fim": str(form.get("condicao_vigencia_fim", "")).strip() or None,
                "confidence": 1.0 if str(form.get("condicao_valor", "")).strip() else 0,
                "evidence": None,
                "reviewed": True,
            }
        ],
        "warnings": [],
    }


def candidate_value(value):
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def candidate_confidence(value) -> float:
    if isinstance(value, dict):
        try:
            return float(value.get("confidence") or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def flatten_contract_candidates(payload: dict | None) -> dict:
    return {key: candidate_value(value) for key, value in extraction_section(payload, "contrato").items()}


def clause_value(value) -> str | None:
    if isinstance(value, list):
        chunks = []
        for item in value:
            if isinstance(item, dict):
                chunks.append(item.get("value") or item.get("evidence") or "")
            elif item:
                chunks.append(str(item))
        return "\n".join(chunk for chunk in chunks if chunk).strip() or None
    return candidate_value(value)


def flatten_clause_candidates(payload: dict | None) -> dict:
    return {key: clause_value(value) for key, value in extraction_section(payload, "clausulas_criticas").items()}


def extraction_section(payload: dict | None, section: str) -> dict:
    value = (payload or {}).get(section)
    return value if isinstance(value, dict) else {}


def first_extracted_condition(payload: dict | None) -> dict:
    rows = (payload or {}).get("condicoes_contratuais")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0]
    return {}


def render_user_form(
    request: Request,
    *,
    user_record: User | None = None,
    profiles=None,
    error: str | None = None,
    reset_password: bool = False,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request,
        "user_form.html",
        {
            "title": "Resetar senha" if reset_password else ("Editar usuário" if user_record else "Novo usuário"),
            "active_page": "users",
            "user": request.session.get("user"),
            "user_record": user_record,
            "profiles": profiles or [],
            "error": error,
            "reset_password": reset_password,
        },
        status_code=status_code,
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_logged_in(request):
        return RedirectResponse("/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "username": "", "remember": False, "register_page": False},
    )


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: str | None = Form(default=None),
):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        valid_user = (
            user
            and user.is_active
            and (user.access_profile is None or user.access_profile.is_active)
            and verify_password(password, user.password_hash)
        )
        if valid_user:
            request.session.clear()
            request.session["user"] = user_session_payload(user)
            request.session["remember"] = bool(remember)
            request.session["last_seen"] = datetime.utcnow().isoformat()
            request.session["csrf_token"] = csrf_token(request) or __import__("secrets").token_urlsafe(32)
            record_auth_event(db, "login", user=user, request=request, success=True)
            record_audit_log(db, request, "login", entity_type="user", entity_id=user.id, details=user.username)
            db.commit()
            return RedirectResponse("/dashboard", status_code=303)

        record_auth_event(
            db,
            "login_failed",
            user=user if user else None,
            username=username,
            request=request,
            success=False,
            notes="Usuário inativo, perfil inativo ou credenciais inválidas.",
        )
        record_audit_log(db, request, "login_failed", entity_type="user", entity_id=user.id if user else None, success=False, details=username)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "error": "Usuário ou senha inválidos.",
            "username": username,
            "remember": bool(remember),
            "register_page": False,
        },
        status_code=400,
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if not ENABLE_SELF_REGISTRATION:
        return forbidden_response(request, "Cadastro público desabilitado. Solicite acesso ao administrador.")
    if is_logged_in(request):
        return RedirectResponse("/dashboard", status_code=303)

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "error": None,
            "username": "",
            "remember": False,
            "register_page": True,
            "full_name": "",
            "email": "",
        },
    )


@app.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    if not ENABLE_SELF_REGISTRATION:
        return forbidden_response(request, "Cadastro público desabilitado. Solicite acesso ao administrador.")

    context = {
        "error": None,
        "username": username,
        "remember": False,
        "register_page": True,
        "full_name": full_name,
        "email": email,
    }

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
    finally:
        db.close()

    if existing_user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "Este usuário ou email já existe."},
            status_code=400,
        )

    if "@" not in email or "." not in email:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "Informe um email válido."},
            status_code=400,
        )

    password_error = validate_password_strength(password)
    if password_error:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": password_error},
            status_code=400,
        )

    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "As senhas não conferem."},
            status_code=400,
        )

    db = SessionLocal()
    try:
        profile = get_access_profile(db, DEFAULT_REGISTER_PROFILE) or get_access_profile(db, PROFILE_ADMIN)
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            access_profile_id=profile.id if profile else None,
            is_active=True,
        )
        db.add(user)
        db.flush()
        request.session["user"] = user_session_payload(user)
        record_auth_event(db, "register", user=user, request=request, success=True)
        record_auth_event(db, "login", user=user, request=request, success=True, notes="Login automático após cadastro.")
        db.commit()
        return RedirectResponse("/dashboard", status_code=303)
    except SQLAlchemyError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "Não foi possível criar o usuário."},
            status_code=500,
        )
    finally:
        db.close()


@app.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request):
    if redirect := require_login(request):
        return redirect

    return templates.TemplateResponse(
        request,
        "change_password.html",
        {
            "title": "Trocar senha",
            "active_page": "change_password",
            "user": request.session.get("user"),
            "error": None,
            "success": None,
        },
    )


@app.post("/change-password", response_class=HTMLResponse)
def change_password_submit(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
):
    if redirect := require_login(request):
        return redirect

    context = {
        "title": "Trocar senha",
        "active_page": "change_password",
        "user": request.session.get("user"),
        "error": None,
        "success": None,
    }
    password_error = validate_password_strength(new_password)
    if password_error:
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {**context, "error": password_error},
            status_code=400,
        )
    if new_password != new_password_confirm:
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {**context, "error": "As senhas não conferem."},
            status_code=400,
        )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == current_username(request)).first()
        if not user or not verify_password(current_password, user.password_hash):
            record_auth_event(
                db,
                "password_change_failed",
                user=user,
                username=current_username(request),
                request=request,
                success=False,
                notes="Senha atual inválida.",
            )
            db.commit()
            return templates.TemplateResponse(
                request,
                "change_password.html",
                {**context, "error": "Senha atual inválida."},
                status_code=400,
            )

        user.password_hash = hash_password(new_password)
        request.session["user"] = user_session_payload(user)
        record_auth_event(db, "password_changed", user=user, request=request, success=True)
        db.commit()
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {**context, "user": request.session.get("user"), "success": "Senha alterada com sucesso."},
        )
    except SQLAlchemyError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "change_password.html",
            {**context, "error": "Não foi possível alterar a senha."},
            status_code=500,
        )
    finally:
        db.close()


@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem gerenciar usuários."):
        return redirect

    db = SessionLocal()
    try:
        user_rows = [
            {
                "id": item.id,
                "username": item.username,
                "email": item.email,
                "full_name": item.full_name,
                "is_active": item.is_active,
                "profile": item.access_profile.name if item.access_profile else "-",
                "created_at": item.created_at,
            }
            for item in db.query(User).order_by(User.created_at.desc()).all()
        ]
        return templates.TemplateResponse(
            request,
            "users.html",
            {
                "title": "Usuários",
                "active_page": "users",
                "user": request.session.get("user"),
                "users": user_rows,
            },
        )
    finally:
        db.close()


@app.get("/users/new", response_class=HTMLResponse)
def user_new_page(request: Request):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem criar usuários."):
        return redirect

    db = SessionLocal()
    try:
        return render_user_form(request, profiles=db.query(AccessProfile).order_by(AccessProfile.name).all())
    finally:
        db.close()


@app.post("/users/new", response_class=HTMLResponse)
def user_new_submit(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(default=""),
    email: str = Form(...),
    access_profile_id: int = Form(...),
    password: str = Form(...),
    is_active: str | None = Form(default=None),
):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem criar usuários."):
        return redirect

    db = SessionLocal()
    try:
        profiles = db.query(AccessProfile).order_by(AccessProfile.name).all()
        profile = db.query(AccessProfile).filter(AccessProfile.id == access_profile_id).first()
        if not profile:
            return render_user_form(request, profiles=profiles, error="Perfil obrigatório.", status_code=400)
        if db.query(User).filter(or_(User.username == username, User.email == email)).first():
            return render_user_form(request, profiles=profiles, error="Usuário ou email já existe.", status_code=400)
        password_error = validate_password_strength(password)
        if password_error:
            return render_user_form(request, profiles=profiles, error=password_error, status_code=400)

        user_record = User(
            username=username.strip(),
            full_name=full_name.strip() or None,
            email=email.strip(),
            access_profile_id=access_profile_id,
            password_hash=hash_password(password),
            is_active=bool(is_active),
        )
        db.add(user_record)
        db.flush()
        record_auth_event(db, "user_created", user=user_record, username=user_record.username, request=request, notes=f"Criado por {current_username(request)}.")
        record_audit_log(db, request, "user_created", entity_type="user", entity_id=user_record.id, details=user_record.username)
        db.commit()
        return RedirectResponse("/users", status_code=303)
    except SQLAlchemyError as exc:
        db.rollback()
        return render_user_form(request, profiles=db.query(AccessProfile).order_by(AccessProfile.name).all(), error="Não foi possível criar usuário.", status_code=500)
    finally:
        db.close()


@app.get("/users/{user_id}/edit", response_class=HTMLResponse)
def user_edit_page(request: Request, user_id: int):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem editar usuários."):
        return redirect

    db = SessionLocal()
    try:
        user_record = db.query(User).filter(User.id == user_id).first()
        if not user_record:
            return RedirectResponse("/users", status_code=303)
        return render_user_form(request, user_record=user_record, profiles=db.query(AccessProfile).order_by(AccessProfile.name).all())
    finally:
        db.close()


@app.post("/users/{user_id}/edit", response_class=HTMLResponse)
def user_edit_submit(
    request: Request,
    user_id: int,
    full_name: str = Form(default=""),
    email: str = Form(...),
    access_profile_id: int = Form(...),
    is_active: str | None = Form(default=None),
):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem editar usuários."):
        return redirect

    db = SessionLocal()
    try:
        user_record = db.query(User).filter(User.id == user_id).first()
        profiles = db.query(AccessProfile).order_by(AccessProfile.name).all()
        if not user_record:
            return RedirectResponse("/users", status_code=303)
        if not db.query(AccessProfile).filter(AccessProfile.id == access_profile_id).first():
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Perfil obrigatório.", status_code=400)
        duplicate = db.query(User).filter(User.email == email, User.id != user_id).first()
        if duplicate:
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Email já cadastrado.", status_code=400)
        if user_record.id == request.session.get("user", {}).get("id") and not is_active:
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Você não pode desativar o próprio usuário.", status_code=400)

        old_profile_id = user_record.access_profile_id
        user_record.full_name = full_name.strip() or None
        user_record.email = email.strip()
        user_record.access_profile_id = access_profile_id
        user_record.is_active = bool(is_active)
        if old_profile_id != access_profile_id and active_admin_count(db) == 0:
            db.rollback()
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Não é permitido remover o último Administrador ativo.", status_code=400)

        record_auth_event(db, "user_updated", user=user_record, username=user_record.username, request=request, notes=f"Atualizado por {current_username(request)}.")
        record_audit_log(db, request, "user_updated", entity_type="user", entity_id=user_record.id, details=user_record.username)
        db.commit()
        return RedirectResponse("/users", status_code=303)
    except SQLAlchemyError as exc:
        db.rollback()
        return render_user_form(request, error="Não foi possível editar usuário.", status_code=500)
    finally:
        db.close()


@app.post("/users/{user_id}/deactivate")
def user_deactivate(request: Request, user_id: int):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem desativar usuários."):
        return redirect

    db = SessionLocal()
    try:
        user_record = db.query(User).filter(User.id == user_id).first()
        if not user_record:
            return RedirectResponse("/users", status_code=303)
        if user_record.id == request.session.get("user", {}).get("id"):
            return forbidden_response(request, "Você não pode desativar o próprio usuário.")
        if user_record.access_profile and user_record.access_profile.name == PROFILE_ADMIN and active_admin_count(db) <= 1:
            return forbidden_response(request, "Não é permitido desativar o último Administrador ativo.")
        user_record.is_active = False
        record_auth_event(db, "user_deactivated", user=user_record, username=user_record.username, request=request, notes=f"Desativado por {current_username(request)}.")
        record_audit_log(db, request, "user_deactivated", entity_type="user", entity_id=user_record.id, details=user_record.username)
        db.commit()
        return RedirectResponse("/users", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


@app.post("/users/{user_id}/make-admin")
def user_make_admin(request: Request, user_id: int):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem alterar perfis administrativos."):
        return redirect

    db = SessionLocal()
    try:
        user_record = db.query(User).filter(User.id == user_id).first()
        admin_profile = get_access_profile(db, PROFILE_ADMIN)
        if not user_record:
            return RedirectResponse("/users", status_code=303)
        if not admin_profile:
            return forbidden_response(request, "Perfil Administrador não encontrado ou inativo.")
        if user_record.access_profile_id == admin_profile.id:
            return RedirectResponse("/users", status_code=303)

        user_record.access_profile_id = admin_profile.id
        user_record.is_active = True
        record_auth_event(
            db,
            "user_promoted_to_admin",
            user=user_record,
            username=user_record.username,
            request=request,
            notes=f"Promovido a Administrador por {current_username(request)}.",
        )
        record_audit_log(db, request, "user_profile_changed", entity_type="user", entity_id=user_record.id, details=f"{user_record.username} -> {PROFILE_ADMIN}")
        db.commit()
        return RedirectResponse("/users", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/users/{user_id}/reset-password", response_class=HTMLResponse)
def user_reset_password_page(request: Request, user_id: int):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem resetar senhas."):
        return redirect

    db = SessionLocal()
    try:
        user_record = db.query(User).filter(User.id == user_id).first()
        if not user_record:
            return RedirectResponse("/users", status_code=303)
        return render_user_form(request, user_record=user_record, reset_password=True)
    finally:
        db.close()


@app.post("/users/{user_id}/reset-password", response_class=HTMLResponse)
def user_reset_password_submit(
    request: Request,
    user_id: int,
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem resetar senhas."):
        return redirect

    db = SessionLocal()
    try:
        user_record = db.query(User).filter(User.id == user_id).first()
        if not user_record:
            return RedirectResponse("/users", status_code=303)
        password_error = validate_password_strength(password)
        if password_error:
            return render_user_form(request, user_record=user_record, reset_password=True, error=password_error, status_code=400)
        if password != password_confirm:
            return render_user_form(request, user_record=user_record, reset_password=True, error="As senhas não conferem.", status_code=400)
        user_record.password_hash = hash_password(password)
        record_auth_event(db, "password_reset", user=user_record, username=user_record.username, request=request, notes=f"Reset por {current_username(request)}.")
        record_audit_log(db, request, "user_password_reset", entity_type="user", entity_id=user_record.id, details=user_record.username)
        db.commit()
        return RedirectResponse("/users", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/access-profiles", response_class=HTMLResponse)
def access_profiles_page(request: Request):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem gerenciar perfis."):
        return redirect

    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            request,
            "access_profiles.html",
            {
                "title": "Perfis de Acesso",
                "active_page": "access_profiles",
                "user": request.session.get("user"),
                "profiles": db.query(AccessProfile).order_by(AccessProfile.name).all(),
            },
        )
    finally:
        db.close()


def render_profile_form(request: Request, *, profile: AccessProfile | None = None, error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request,
        "access_profile_form.html",
        {
            "title": "Editar perfil" if profile else "Novo perfil",
            "active_page": "access_profiles",
            "user": request.session.get("user"),
            "profile": profile,
            "error": error,
        },
        status_code=status_code,
    )


@app.get("/access-profiles/new", response_class=HTMLResponse)
def access_profile_new_page(request: Request):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem criar perfis."):
        return redirect
    return render_profile_form(request)


@app.post("/access-profiles/new", response_class=HTMLResponse)
def access_profile_new_submit(request: Request, name: str = Form(...), description: str = Form(default=""), is_active: str | None = Form(default=None)):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem criar perfis."):
        return redirect

    db = SessionLocal()
    try:
        if db.query(AccessProfile).filter(AccessProfile.name == name.strip()).first():
            return render_profile_form(request, error="Perfil já existe.", status_code=400)
        profile = AccessProfile(name=name.strip(), description=description.strip() or None, is_active=bool(is_active))
        db.add(profile)
        db.flush()
        record_auth_event(db, "access_profile_created", username=current_username(request), request=request, notes=f"Perfil criado: {profile.name}.")
        record_audit_log(db, request, "access_profile_created", entity_type="access_profile", entity_id=profile.id, details=profile.name)
        db.commit()
        return RedirectResponse("/access-profiles", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/access-profiles/{profile_id}/edit", response_class=HTMLResponse)
def access_profile_edit_page(request: Request, profile_id: int):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem editar perfis."):
        return redirect

    db = SessionLocal()
    try:
        profile = db.query(AccessProfile).filter(AccessProfile.id == profile_id).first()
        if not profile:
            return RedirectResponse("/access-profiles", status_code=303)
        return render_profile_form(request, profile=profile)
    finally:
        db.close()


@app.post("/access-profiles/{profile_id}/edit", response_class=HTMLResponse)
def access_profile_edit_submit(request: Request, profile_id: int, name: str = Form(...), description: str = Form(default=""), is_active: str | None = Form(default=None)):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem editar perfis."):
        return redirect

    db = SessionLocal()
    try:
        profile = db.query(AccessProfile).filter(AccessProfile.id == profile_id).first()
        if not profile:
            return RedirectResponse("/access-profiles", status_code=303)
        if db.query(AccessProfile).filter(AccessProfile.name == name.strip(), AccessProfile.id != profile_id).first():
            return render_profile_form(request, profile=profile, error="Perfil já existe.", status_code=400)
        profile.name = name.strip()
        profile.description = description.strip() or None
        profile.is_active = bool(is_active)
        if profile.name == PROFILE_ADMIN and not profile.is_active and active_admin_count(db) > 0:
            db.rollback()
            return render_profile_form(request, profile=profile, error="Não é permitido desativar o perfil Administrador.", status_code=400)
        record_auth_event(db, "access_profile_updated", username=current_username(request), request=request, notes=f"Perfil atualizado: {profile.name}.")
        record_audit_log(db, request, "access_profile_updated", entity_type="access_profile", entity_id=profile.id, details=profile.name)
        db.commit()
        return RedirectResponse("/access-profiles", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


@app.post("/access-profiles/{profile_id}/deactivate")
def access_profile_deactivate(request: Request, profile_id: int):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem desativar perfis."):
        return redirect

    db = SessionLocal()
    try:
        profile = db.query(AccessProfile).filter(AccessProfile.id == profile_id).first()
        if not profile:
            return RedirectResponse("/access-profiles", status_code=303)
        if profile.name == PROFILE_ADMIN:
            return forbidden_response(request, "Não é permitido desativar o perfil Administrador.")
        profile.is_active = False
        record_auth_event(db, "access_profile_deactivated", username=current_username(request), request=request, notes=f"Perfil desativado: {profile.name}.")
        record_audit_log(db, request, "access_profile_deactivated", entity_type="access_profile", entity_id=profile.id, details=profile.name)
        db.commit()
        return RedirectResponse("/access-profiles", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/auth-audit-events", response_class=HTMLResponse)
def auth_audit_events_page(
    request: Request,
    username: str | None = None,
    event_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    if redirect := require_profiles(
        request,
        AUDIT_PROFILES,
        "Seu perfil não permite acessar a auditoria.",
    ):
        return redirect

    db = SessionLocal()
    try:
        query = db.query(AuthAuditEvent)
        selected_username = (username or "").strip()
        selected_event_type = (event_type or "").strip()
        if selected_username:
            query = query.filter(AuthAuditEvent.username.ilike(f"%{selected_username}%"))
        if selected_event_type:
            query = query.filter(AuthAuditEvent.event_type == selected_event_type)
        if start_date:
            query = query.filter(AuthAuditEvent.created_at >= datetime.combine(date.fromisoformat(start_date), time.min))
        if end_date:
            query = query.filter(AuthAuditEvent.created_at <= datetime.combine(date.fromisoformat(end_date), time.max))

        events = query.order_by(AuthAuditEvent.created_at.desc()).limit(300).all()
        event_types = [
            item[0]
            for item in db.query(AuthAuditEvent.event_type)
            .filter(AuthAuditEvent.event_type.isnot(None))
            .distinct()
            .order_by(AuthAuditEvent.event_type)
            .all()
        ]
        return templates.TemplateResponse(
            request,
            "auth_audit_events.html",
            {
                "title": "Auditoria",
                "active_page": "auth_audit_events",
                "user": request.session.get("user"),
                "events": events,
                "event_types": event_types,
                "filters": {
                    "username": selected_username,
                    "event_type": selected_event_type,
                    "start_date": start_date or "",
                    "end_date": end_date or "",
                },
            },
        )
    finally:
        db.close()


@app.get("/logout")
def logout(request: Request):
    session_user = request.session.get("user") or {}
    username = session_user.get("username")
    if username:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            record_auth_event(db, "logout", user=user, username=username, request=request, success=True)
            record_audit_log(db, request, "logout", entity_type="user", entity_id=user.id if user else None, details=username)
            db.commit()
        except SQLAlchemyError:
            db.rollback()
        finally:
            db.close()
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if redirect := require_login(request):
        return redirect
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    if redirect := require_login(request):
        return redirect

    today = date.today()
    db = SessionLocal()
    try:
        contracts_from_db = db.query(Contract).order_by(Contract.created_at.desc()).all()
        additives_from_db = (
            db.query(ContractAdditive)
            .join(Contract)
            .order_by(ContractAdditive.created_at.desc())
            .all()
        )

        total_contracts = len(contracts_from_db)
        active_contracts = 0
        due_30 = 0
        due_60 = 0
        due_90 = 0
        expired = 0
        no_adjustment = 0
        pending_documents = 0
        score_sum = 0
        scored_count = 0
        operator_counts = {}
        status_counts = {
            "Ativos": 0,
            "Vencendo": 0,
            "Vencidos": 0,
            "Sem vigência": 0,
        }
        expiration_counts = {
            "Vencidos": 0,
            "Ate 30 dias": 0,
            "31 a 60 dias": 0,
            "61 a 90 dias": 0,
            "91 a 120 dias": 0,
            "121 a 150 dias": 0,
            "+150 dias": 0,
        }
        table_counts = {}
        operator_scores = {}
        attention_rows = []

        for contract in contracts_from_db:
            if contract.status == "inactive":
                continue
            operator_name = contract.operator_name or "Operadora não informada"
            operator_counts[operator_name] = operator_counts.get(operator_name, 0) + 1

            score = float(contract.score_total or 0)
            score_sum += score
            scored_count += 1
            operator_scores.setdefault(operator_name, []).append(score)

            table_name = (
                contract.medical_fee_table
                or contract.daily_rate_table
                or contract.materials_table
                or contract.medicines_table
                or "Não identificada"
            )
            table_counts[table_name] = table_counts.get(table_name, 0) + 1

            if not (contract.reajust_index or contract.adjustment_type):
                no_adjustment += 1
            if not contract.files and not contract.stored_filepath:
                pending_documents += 1

            if contract.end_date:
                days_left = (contract.end_date - today).days
                if days_left < 0:
                    expired += 1
                    status_counts["Vencidos"] += 1
                    expiration_counts["Vencidos"] += 1
                    attention_rows.append(
                        {
                            "contract": contract.contract_number or f"Contrato #{contract.id}",
                            "operator": operator_name,
                            "term": format_br_date(contract.end_date),
                            "badge": "red",
                            "reason": "Vencido",
                            "action": "Renovar contrato",
                        }
                    )
                elif days_left <= 30:
                    due_30 += 1
                    due_60 += 1
                    due_90 += 1
                    active_contracts += 1
                    status_counts["Vencendo"] += 1
                    expiration_counts["Ate 30 dias"] += 1
                    attention_rows.append(
                        {
                            "contract": contract.contract_number or f"Contrato #{contract.id}",
                            "operator": operator_name,
                            "term": format_br_date(contract.end_date),
                            "badge": "orange",
                            "reason": f"Vence em {days_left} dias",
                            "action": "Renovar contrato",
                        }
                    )
                elif days_left <= 60:
                    due_60 += 1
                    due_90 += 1
                    active_contracts += 1
                    status_counts["Vencendo"] += 1
                    expiration_counts["31 a 60 dias"] += 1
                    attention_rows.append(
                        {
                            "contract": contract.contract_number or f"Contrato #{contract.id}",
                            "operator": operator_name,
                            "term": format_br_date(contract.end_date),
                            "badge": "yellow",
                            "reason": f"Vence em {days_left} dias",
                            "action": "Planejar renovacao",
                        }
                    )
                else:
                    active_contracts += 1
                    status_counts["Ativos"] += 1
                    if days_left <= 90:
                        due_90 += 1
                        expiration_counts["61 a 90 dias"] += 1
                    elif days_left <= 120:
                        expiration_counts["91 a 120 dias"] += 1
                    elif days_left <= 150:
                        expiration_counts["121 a 150 dias"] += 1
                    else:
                        expiration_counts["+150 dias"] += 1
            else:
                status_counts["Sem vigência"] += 1

            if not (contract.reajust_index or contract.adjustment_type) and len(attention_rows) < 8:
                attention_rows.append(
                    {
                        "contract": contract.contract_number or f"Contrato #{contract.id}",
                        "operator": operator_name,
                        "term": format_br_date(contract.end_date),
                        "badge": "orange",
                        "reason": "Sem reajuste definido",
                        "action": "Revisar clausulas",
                    }
                )

        additive_count = len(additives_from_db)
        pending_additives = sum(1 for additive in additives_from_db if additive.status != "active")
        recent_activities = []
        for contract in contracts_from_db[:5]:
            recent_activities.append(
                {
                    "date": contract.created_at,
                    "title": "Contrato importado",
                    "text": f"{contract.operator_name or 'Operadora'} - {contract.contract_number or contract.contract_name}",
                }
            )
        for additive in additives_from_db[:5]:
            recent_activities.append(
                {
                    "date": additive.created_at,
                    "title": "Aditivo importado",
                    "text": f"{additive.contract.operator_name or 'Operadora'} - {additive.additive_number}",
                }
            )
        recent_activities.sort(key=lambda item: item["date"], reverse=True)
        recent_activities = recent_activities[:5]

        operator_chart_items = sorted(operator_counts.items(), key=lambda item: item[1], reverse=True)[:6]
        table_chart_items = sorted(table_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        score_rows = [
            {
                "operator": operator,
                "score": round(sum(values) / len(values)) if values else 0,
            }
            for operator, values in operator_scores.items()
        ]
        score_rows.sort(key=lambda item: item["score"], reverse=True)

        dashboard_data = {
            "expiration": {
                "labels": list(expiration_counts.keys()),
                "values": list(expiration_counts.values()),
            },
            "operators": {
                "labels": [item[0] for item in operator_chart_items],
                "values": [item[1] for item in operator_chart_items],
                "total": total_contracts,
            },
            "status": {
                "labels": list(status_counts.keys()),
                "values": list(status_counts.values()),
                "total": total_contracts,
            },
            "tables": {
                "labels": [item[0] for item in table_chart_items],
                "values": [item[1] for item in table_chart_items],
                "total": total_contracts,
            },
        }
        metrics = {
            "active_contracts": active_contracts,
            "due_30": due_30,
            "due_60": due_60,
            "due_90": due_90,
            "expired": expired,
            "no_adjustment": no_adjustment,
            "pending_documents": pending_documents,
            "average_score": round(score_sum / scored_count) if scored_count else 0,
            "additive_count": additive_count,
            "pending_additives": pending_additives,
            "total_contracts": total_contracts,
        }
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Painel Executivo",
            "active_page": "dashboard",
            "user": request.session.get("user"),
            "metrics": metrics,
            "dashboard_data": dashboard_data,
            "attention_rows": attention_rows[:8],
            "recent_activities": recent_activities,
            "score_rows": score_rows[:5],
        },
    )


@app.get("/contracts", response_class=HTMLResponse)
def contracts(request: Request):
    if redirect := require_login(request):
        return redirect

    db = SessionLocal()
    try:
        contracts_from_db = db.query(Contract).order_by(Contract.created_at.desc()).all()
        contract_rows = []
        for contract in contracts_from_db:
            status_label, status_class = contract_status(contract)
            operator_name = contract.operator_name or "Operadora não informada"
            contract_rows.append(
                {
                    "id": contract.id,
                    "contract_name": contract.contract_name,
                    "contract_number": contract.contract_number or f"Contrato #{contract.id}",
                    "operator_name": operator_name,
                    "operator_initial": operator_name[:1].upper(),
                    "operator_logo_class": operator_logo_class(operator_name),
                    "responsible_name": contract.responsible_name or "-",
                    "contact_info": contract.contact_info or "-",
                    "original_filename": contract.original_filename or "-",
                    "start_date": format_br_date(contract.start_date),
                    "end_date": format_br_date(contract.end_date),
                    "reajust_index": contract.adjustment_type or contract.reajust_index or "Não identificado",
                    "status_label": status_label,
                    "status_class": status_class,
                    "score": int(contract.score_total or 0),
                    "score_class": score_class(contract.score_total),
                }
            )

        operator_names = {
            name
            for (name,) in db.query(Operator.name).filter(Operator.name.isnot(None)).all()
            if name
        }
        operator_names.update(
            name
            for (name,) in db.query(Contract.operator_name)
            .filter(Contract.operator_name.isnot(None), Contract.operator_name != "")
            .distinct()
            .all()
            if name
        )
        today = date.today()
        active_count = sum(1 for item in contract_rows if item["status_class"] == "active")
        due_30_count = sum(1 for item in contracts_from_db if item.end_date and 0 <= (item.end_date - today).days <= 30)
        expired_count = sum(1 for item in contract_rows if item["status_class"] == "expired")
        score_values = [item["score"] for item in contract_rows]
        average_score = round(sum(score_values) / len(score_values)) if score_values else 0
        operator_counts = {}
        for item in contract_rows:
            operator_counts[item["operator_name"]] = operator_counts.get(item["operator_name"], 0) + 1
        operator_ranking = [
            {"name": name, "count": count}
            for name, count in sorted(operator_counts.items(), key=lambda row: row[1], reverse=True)[:5]
        ]
        contract_statuses = sorted({item["status_label"] for item in contract_rows})
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "contracts.html",
        {
            "title": "Contratos",
            "active_page": "contracts",
            "user": request.session.get("user"),
            "operator_names": sorted(operator_names),
            "contract_rows": contract_rows,
            "contract_count": len(contract_rows),
            "contract_metrics": {
                "active": active_count,
                "due_30": due_30_count,
                "expired": expired_count,
                "average_score": average_score,
            },
            "operator_ranking": operator_ranking,
            "contract_statuses": contract_statuses,
        },
    )


@app.get("/contracts/{contract_id:int}", response_class=HTMLResponse)
def contract_detail(request: Request, contract_id: int, edit: int = 0):
    if redirect := require_login(request):
        return redirect

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
        peers = db.query(Contract).filter(Contract.id != contract_id).order_by(Contract.score_total.desc()).limit(5).all()
        days_until_end = (contract.end_date - date.today()).days if contract.end_date else None
        return templates.TemplateResponse(
            request,
            "contract_detail.html",
            {
                "title": contract.contract_name,
                "active_page": "contracts",
                "user": request.session.get("user"),
                "contract": contract,
                "edit_mode": bool(edit),
                "form_data": contract_form_data(contract),
                "parent_options": db.query(Contract).filter(Contract.id != contract_id, Contract.status != "inactive").order_by(Contract.contract_name.asc()).all(),
                "events": db.query(ContractEvent).filter(ContractEvent.contract_id == contract_id).order_by(ContractEvent.created_at.desc()).all(),
                "peer_contracts": peers,
                "days_until_end": days_until_end,
                "strong_points": (contract.strong_points or "").splitlines(),
                "weak_points": (contract.weak_points or "").splitlines(),
                "alerts_list": (contract.alerts or "").splitlines(),
                "summary_cards": [
                    {"label": "Score", "value": f"{contract.score_total or 0:.1f}", "tone": "blue"},
                    {"label": "Risco", "value": contract.risk_level or "-", "tone": "amber"},
                    {"label": "Eventos", "value": len(contract.events), "tone": "slate"},
                    {"label": "Aditivos", "value": len(contract.additives), "tone": "emerald"},
                ],
            },
        )
    finally:
        db.close()


@app.post("/contracts/{contract_id:int}/edit")
async def contract_edit_submit(request: Request, contract_id: int):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES, "Seu perfil não permite editar contratos."):
        return redirect

    from .services.scoring import score_contract

    form = await request.form()
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)

        text_fields = (
            "contract_name", "contract_type", "operator_name", "contract_number", "status", "responsible_name",
            "contract_object", "renewal_details",
            "payment_trigger", "billing_deadline_description", "glosa_clause_summary", "reajust_frequency",
            "reajust_index", "reajust_clause_summary", "medical_fee_table", "medical_fee_table_version",
            "daily_rate_table", "materials_table", "materials_table_version", "medicines_table",
            "medicines_table_version", "observations",
        )
        integer_fields = (
            "termination_notice_days", "payment_term_days", "billing_deadline_days", "glosa_deadline_days",
            "glosa_appeal_deadline_days", "glosa_response_deadline_days",
        )
        boolean_fields = (
            "auto_renewal", "payment_interest_clause", "payment_penalty_clause", "allows_glosa_unilateral",
            "reajust_clause_exists",
        )
        for field in text_fields:
            setattr(contract, field, str(form.get(field, "")).strip() or None)
        if not contract.status:
            contract.status = "active"
        parent_contract_id = parse_optional_int(form.get("parent_contract_id"))
        contract.parent_contract_id = parent_contract_id if parent_contract_id != contract.id else None
        for field in integer_fields:
            setattr(contract, field, parse_optional_int(form.get(field)))
        for field in ("signature_date", "start_date", "end_date", "base_date"):
            setattr(contract, field, parse_optional_date(form.get(field)))
        percentage = str(form.get("reajust_percentage", "")).replace(",", ".").strip()
        contract.reajust_percentage = float(percentage) if percentage else None
        for field in boolean_fields:
            setattr(contract, field, field in form)

        if not contract.contract_name:
            contract.contract_name = f"Contrato #{contract.id}"
        operator = db.query(Operator).filter(Operator.name == contract.operator_name).first() if contract.operator_name else None
        if contract.operator_name and not operator:
            operator = Operator(name=contract.operator_name)
            db.add(operator)
            db.flush()
        contract.operator_id = operator.id if operator else None

        scoring = score_contract({column.name: getattr(contract, column.name) for column in Contract.__table__.columns})
        for field, value in scoring.items():
            setattr(contract, field, value)
        record_auth_event(db, "contract_updated", username=current_username(request), request=request, notes=f"Contrato #{contract.id} atualizado.")
        record_audit_log(db, request, "contract_updated", entity_type="contract", entity_id=contract.id, details=contract.contract_name)
        db.commit()
        return RedirectResponse(f"/contracts/{contract.id}", status_code=303)
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        return JSONResponse({"error": "Não foi possível atualizar o contrato."}, status_code=400)
    finally:
        db.close()


@app.post("/contracts/{contract_id:int}/events")
def contract_event_submit(
    request: Request,
    contract_id: int,
    event_type: str = Form(default="nota"),
    event_date: str = Form(default=""),
    title: str = Form(...),
    notes: str = Form(default=""),
):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES, "Seu perfil não permite registrar eventos."):
        return redirect

    db = SessionLocal()
    try:
        if not db.query(Contract).filter(Contract.id == contract_id).first():
            return RedirectResponse("/contracts", status_code=303)
        event = ContractEvent(
            contract_id=contract_id,
            event_type=event_type.strip() or "nota",
            event_date=parse_optional_date(event_date),
            title=title.strip(),
            notes=notes.strip() or None,
        )
        db.add(event)
        record_auth_event(db, "contract_event_created", username=current_username(request), request=request, notes=f"Evento criado no contrato #{contract_id}: {event.title}.")
        db.commit()
        db.refresh(event)
        return RedirectResponse(f"/contracts/{contract_id}", status_code=303)
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        return JSONResponse({"error": "Não foi possível registrar o evento."}, status_code=400)
    finally:
        db.close()


@app.post("/contracts/{contract_id:int}/delete")
def contract_delete(request: Request, contract_id: int):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES, "Seu perfil não permite excluir contratos."):
        return redirect

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
        name = contract.contract_name
        contract.status = "inactive"
        record_auth_event(db, "contract_inactivated", username=current_username(request), request=request, notes=f"Contrato #{contract_id} inativado: {name}.")
        record_audit_log(db, request, "contract_inactivated", entity_type="contract", entity_id=contract.id, details=name)
        db.commit()
        return RedirectResponse("/contracts", status_code=303)
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse({"error": "Não foi possível excluir o contrato."}, status_code=500)
    finally:
        db.close()


@app.get("/contracts/import")
def contracts_import_page(request: Request):
    if redirect := require_profiles(
        request,
        CONTRACT_WRITE_PROFILES,
        "Seu perfil não permite importar contratos.",
    ):
        return redirect
    return RedirectResponse("/contracts?newContract=1", status_code=303)


@app.get("/contracts/{contract_id}/additional", response_class=HTMLResponse)
def contract_additional_page(request: Request, contract_id: int, saved: int = 0):
    if redirect := require_login(request):
        return redirect

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)

        return templates.TemplateResponse(
            request,
            "contract_additional.html",
            {
                "title": "Cadastro adicional",
                "active_page": "contracts",
                "user": request.session.get("user"),
                "contract": contract,
                "saved": bool(saved),
                "adjustment_options": [
                    "IPCA",
                    "IGP-M",
                    "INPC",
                    "FIPE",
                    "Sem índice definido",
                    "Pendente",
                    "Outro",
                ],
            },
        )
    finally:
        db.close()


@app.get("/documents", response_class=HTMLResponse)
def documents_page(request: Request, contract_id: int | None = None):
    if redirect := require_login(request):
        return redirect

    db = SessionLocal()
    try:
        query = db.query(ContractFile).join(Contract).order_by(ContractFile.created_at.desc())
        if contract_id:
            query = query.filter(ContractFile.contract_id == contract_id)
        documents = query.all()
        return templates.TemplateResponse(
            request,
            "documents.html",
            {
                "title": "Documentos e Extração",
                "active_page": "documents",
                "user": request.session.get("user"),
                "documents": documents,
                "contracts": db.query(Contract).filter(Contract.status != "inactive").order_by(Contract.contract_name.asc()).all(),
                "selected_contract_id": contract_id,
            },
        )
    finally:
        db.close()


@app.get("/contracts/{contract_id:int}/documents")
def contract_documents_alias(request: Request, contract_id: int):
    return RedirectResponse(f"/documents?contract_id={contract_id}", status_code=303)


@app.post("/documents/upload")
async def document_upload(
    request: Request,
    contract_id: int = Form(...),
    document_type: str = Form(default="contrato"),
    file: UploadFile = File(...),
):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | ANALYSIS_WRITE_PROFILES, "Seu perfil não permite enviar documentos."):
        return redirect

    from .services.document_processing_service import DocumentProcessingError, process_uploaded_document

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return JSONResponse({"error": "Contrato não encontrado."}, status_code=404)
        record_audit_log(db, request, "document_processing_started", entity_type="contract", entity_id=contract.id, details=file.filename)
        record_audit_log(db, request, "text_extraction_started", entity_type="contract", entity_id=contract.id, details=file.filename)
        processed = await process_uploaded_document(
            db,
            contract_id=contract.id,
            document_type=document_type,
            file=file,
            username=current_username(request),
        )
        record_audit_log(db, request, "document_uploaded", entity_type="contract_file", entity_id=processed.contract_file.id, details=processed.contract_file.original_filename)
        if processed.extraction.extracted_text:
            record_audit_log(
                db,
                request,
                "text_extracted",
                entity_type="contract_extraction",
                entity_id=processed.extraction.id,
                details=f"{processed.extraction.character_count} caracteres via {processed.extraction.extraction_method or 'parser local'}",
            )
        elif processed.extraction.extraction_warnings:
            action = "ocr_not_configured" if "OCR local não configurado" in processed.extraction.extraction_warnings else "no_text_detected"
            record_audit_log(db, request, action, entity_type="contract_extraction", entity_id=processed.extraction.id, details=processed.extraction.extraction_warnings)
        record_audit_log(db, request, "document_sent_to_validation", entity_type="contract_extraction", entity_id=processed.extraction.id, details="Extração pendente de validação humana.")
        db.commit()
        return RedirectResponse(f"/documents/{processed.contract_file.id}/validate", status_code=303)
    except DocumentProcessingError as exc:
        db.rollback()
        db = SessionLocal()
        try:
            record_audit_log(db, request, "document_processing_error", entity_type="contract", entity_id=contract_id, success=False, details=str(exc))
            record_audit_log(db, request, "text_extraction_error", entity_type="contract", entity_id=contract_id, success=False, details=str(exc))
            db.commit()
        finally:
            db.close()
        return JSONResponse({"error": str(exc)}, status_code=400)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse({"error": "Não foi possível gravar o documento."}, status_code=500)
    finally:
        db.close()


@app.get("/documents/{document_id:int}", response_class=HTMLResponse)
def document_detail(request: Request, document_id: int, apply_message: str | None = None):
    if redirect := require_login(request):
        return redirect
    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        return templates.TemplateResponse(
            request,
            "document_detail.html",
            {
                "title": "Documento",
                "active_page": "documents",
                "user": request.session.get("user"),
                "document": document,
                "extraction": latest_extraction_for_file(db, document.id),
                "apply_message": apply_message,
            },
        )
    finally:
        db.close()


@app.get("/documents/{document_id:int}/download")
def document_download(request: Request, document_id: int):
    if redirect := require_login(request):
        return redirect
    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        path = Path(document.stored_filepath)
        if not path.exists() or not path.is_file():
            return JSONResponse({"error": "Arquivo não encontrado."}, status_code=404)
        return FileResponse(path, filename=document.original_filename, media_type=document.mime_type or "application/octet-stream")
    finally:
        db.close()


@app.post("/documents/{document_id:int}/analyze")
def document_analyze(request: Request, document_id: int):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | ANALYSIS_WRITE_PROFILES, "Seu perfil nÃ£o permite gerar candidatos."):
        return redirect

    from .services.contract_ai_analysis_service import (
        STATUS_ANALYZING,
        STATUS_AWAITING_VALIDATION,
        STATUS_CANDIDATES_GENERATED,
        STATUS_ERROR,
        analyze_extracted_contract_text,
    )

    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        extraction = latest_extraction_for_file(db, document.id)
        if not extraction:
            extraction = ContractExtraction(
                contract_file_id=document.id,
                contract_id=document.contract_id,
                extraction_status=STATUS_AWAITING_VALIDATION,
                extracted_json={},
                extraction_source="manual",
                created_by=current_username(request),
                review_status="pendente",
            )
            db.add(extraction)
            db.flush()
        if not (extraction.extracted_text or "").strip():
            extraction.extraction_status = STATUS_AWAITING_VALIDATION
            document.processing_status = STATUS_AWAITING_VALIDATION
            record_audit_log(
                db,
                request,
                "interpretive_analysis_no_text",
                entity_type="contract_extraction",
                entity_id=extraction.id,
                success=False,
                details=f"Documento #{document.id} sem texto extraido disponivel.",
            )
            db.commit()
            return RedirectResponse(f"/documents/{document.id}/validate?analysis_message=sem_texto", status_code=303)

        extraction.extraction_status = STATUS_ANALYZING
        document.processing_status = STATUS_ANALYZING
        record_audit_log(
            db,
            request,
            "interpretive_analysis_started",
            entity_type="contract_extraction",
            entity_id=extraction.id,
            details=f"Documento #{document.id}; {extraction.character_count} caracteres.",
        )
        db.commit()
        extraction_id = extraction.id
        document_id_for_redirect = document.id
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse({"error": "NÃ£o foi possÃ­vel iniciar a anÃ¡lise interpretativa."}, status_code=500)
    finally:
        db.close()

    try:
        analyzed = analyze_extracted_contract_text(extraction_id, user_id=current_username(request))
    except Exception:
        db = SessionLocal()
        try:
            document = db.query(ContractFile).filter(ContractFile.id == document_id_for_redirect).first()
            extraction = db.query(ContractExtraction).filter(ContractExtraction.id == extraction_id).first()
            if document:
                document.processing_status = STATUS_ERROR
                document.error_message = "Falha ao gerar candidatos interpretativos."
            if extraction:
                extraction.extraction_status = STATUS_ERROR
                record_audit_log(
                    db,
                    request,
                    "interpretive_analysis_error",
                    entity_type="contract_extraction",
                    entity_id=extraction.id,
                    success=False,
                    details="Falha ao gerar candidatos interpretativos.",
                )
            db.commit()
        finally:
            db.close()
        return RedirectResponse(f"/documents/{document_id_for_redirect}/validate?analysis_message=erro", status_code=303)

    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id_for_redirect).first()
        extraction = db.query(ContractExtraction).filter(ContractExtraction.id == analyzed.id).first()
        if document and extraction:
            document.processing_status = STATUS_AWAITING_VALIDATION
            document.extraction_status = STATUS_CANDIDATES_GENERATED
            document.error_message = None
            payload = extraction.extracted_json or {}
            condition_count = len(payload.get("condicoes_contratuais") or [])
            clause_count = sum(len(value) for value in (payload.get("clausulas_criticas") or {}).values() if isinstance(value, list))
            record_audit_log(
                db,
                request,
                "interpretive_analysis_completed",
                entity_type="contract_extraction",
                entity_id=extraction.id,
                details=f"{condition_count} condicoes e {clause_count} clausulas candidatas.",
            )
            record_audit_log(
                db,
                request,
                "interpretive_candidates_generated",
                entity_type="contract_extraction",
                entity_id=extraction.id,
                details="Candidatos gerados para validacao humana.",
            )
            db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/documents/{document_id_for_redirect}/validate?analysis_message=candidatos_gerados", status_code=303)


@app.get("/documents/{document_id:int}/validate", response_class=HTMLResponse)
def document_validate_page(request: Request, document_id: int, analysis_message: str | None = None, apply_message: str | None = None):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | ANALYSIS_WRITE_PROFILES, "Seu perfil não permite validar documentos."):
        return redirect
    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        extraction = latest_extraction_for_file(db, document.id)
        if not extraction:
            extraction = ContractExtraction(
                contract_file_id=document.id,
                contract_id=document.contract_id,
                extraction_status="aguardando_validacao",
                extracted_json={},
                extraction_source="manual",
                created_by=current_username(request),
            )
            db.add(extraction)
            db.commit()
            db.refresh(extraction)
        record_audit_log(db, request, "validation_opened", entity_type="contract_extraction", entity_id=extraction.id, details=document.original_filename)
        db.commit()
        payload = extraction.extracted_json or {}
        return templates.TemplateResponse(
            request,
            "document_validate.html",
            {
                "title": "Validação humana",
                "active_page": "documents",
                "user": request.session.get("user"),
                "document": document,
                "extraction": extraction,
                "contract_data": flatten_contract_candidates(payload),
                "contract_candidates": extraction_section(payload, "contrato"),
                "clause_data": flatten_clause_candidates(payload),
                "clause_candidates": extraction_section(payload, "clausulas_criticas"),
                "condition_data": first_extracted_condition(payload),
                "condition_candidates": payload.get("condicoes_contratuais") or [],
                "analysis_metadata": payload.get("metadata") or {},
                "analysis_warnings": payload.get("warnings") or [],
                "analysis_message": analysis_message,
                "apply_message": apply_message,
            },
        )
    finally:
        db.close()


@app.post("/documents/{document_id:int}/validate")
async def document_validate_save(request: Request, document_id: int):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | ANALYSIS_WRITE_PROFILES, "Seu perfil não permite salvar validação."):
        return redirect
    form = await request.form()
    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        extraction = latest_extraction_for_file(db, document.id)
        if not extraction:
            extraction = ContractExtraction(contract_file_id=document.id, contract_id=document.contract_id, extraction_status="pendente", review_status="pendente")
            db.add(extraction)
            db.flush()
        payload = extraction_payload_from_form(form)
        payload["raw_text_available"] = bool(extraction.extracted_text)
        extraction.extracted_json = payload
        extraction.extraction_status = "aguardando_validacao"
        extraction.review_status = "em_revisao"
        extraction.review_notes = str(form.get("review_notes", "")).strip() or None
        document.processing_status = "aguardando_validacao"
        record_audit_log(db, request, "extraction_review_saved", entity_type="contract_extraction", entity_id=extraction.id, details=document.original_filename)
        record_audit_log(db, request, "extracted_fields_updated", entity_type="contract_extraction", entity_id=extraction.id, details="Campos extraídos ajustados manualmente.")
        db.commit()
        return RedirectResponse(f"/documents/{document.id}/validate?saved=1", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse({"error": "Não foi possível salvar a revisão."}, status_code=500)
    finally:
        db.close()


@app.post("/documents/{document_id:int}/approve")
async def document_approve(request: Request, document_id: int):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | ANALYSIS_WRITE_PROFILES, "Seu perfil não permite aprovar extrações."):
        return redirect
    form = await request.form()
    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        extraction = latest_extraction_for_file(db, document.id)
        if not extraction:
            return JSONResponse({"error": "Não há extração para aprovar."}, status_code=400)
        if form:
            payload = extraction_payload_from_form(form)
            payload["raw_text_available"] = bool(extraction.extracted_text)
            extraction.extracted_json = payload
        now = datetime.utcnow()
        extraction.review_status = "aprovado"
        extraction.extraction_status = "aprovado"
        extraction.apply_status = "pendente"
        extraction.apply_error = None
        extraction.reviewed_by = current_username(request)
        extraction.reviewed_at = now
        extraction.review_notes = str(form.get("review_notes", "")).strip() or extraction.review_notes
        document.processing_status = "aprovado"
        document.extraction_status = "aprovado"
        document.approved_by = current_username(request)
        document.approved_at = now
        record_audit_log(db, request, "extraction_approved", entity_type="contract_extraction", entity_id=extraction.id, details=document.original_filename)
        db.commit()
        return RedirectResponse(f"/documents/{document.id}", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse({"error": "Não foi possível aprovar a extração."}, status_code=500)
    finally:
        db.close()


@app.post("/documents/{document_id:int}/apply")
def document_apply_approved_data(request: Request, document_id: int):
    if redirect := require_login(request):
        return redirect
    if not has_profile(request.session.get("user"), APPLY_APPROVED_EXTRACTION_PROFILES):
        db = SessionLocal()
        try:
            document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
            extraction = latest_extraction_for_file(db, document.id) if document else None
            record_audit_log(
                db,
                request,
                "approved_extraction_apply_forbidden",
                entity_type="contract_extraction",
                entity_id=extraction.id if extraction else None,
                success=False,
                details=f"Tentativa sem permissao no documento #{document_id}.",
            )
            db.commit()
        finally:
            db.close()
        return forbidden_response(request, "Seu perfil nÃ£o permite aplicar dados aprovados ao cadastro.")

    from .services.approved_extraction_apply_service import apply_approved_extraction

    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        extraction = latest_extraction_for_file(db, document.id)
        if not extraction:
            return JSONResponse({"error": "NÃ£o hÃ¡ extraÃ§Ã£o para aplicar."}, status_code=400)
        if extraction.review_status != "aprovado":
            record_audit_log(
                db,
                request,
                "approved_extraction_apply_without_approval",
                entity_type="contract_extraction",
                entity_id=extraction.id,
                success=False,
                details="Aplicacao bloqueada: revisao ainda nao aprovada.",
            )
            db.commit()
            return RedirectResponse(f"/documents/{document.id}/validate?apply_message=sem_aprovacao", status_code=303)
        if extraction.apply_status == "aplicado":
            record_audit_log(
                db,
                request,
                "approved_extraction_apply_duplicate_blocked",
                entity_type="contract_extraction",
                entity_id=extraction.id,
                success=False,
                details="Aplicacao duplicada bloqueada.",
            )
            db.commit()
            return RedirectResponse(f"/documents/{document.id}?apply_message=ja_aplicado", status_code=303)
        extraction_id = extraction.id
    finally:
        db.close()

    try:
        applied_extraction, audit_events = apply_approved_extraction(extraction_id, user_id=current_username(request))
    except Exception:
        db = SessionLocal()
        try:
            extraction = db.query(ContractExtraction).filter(ContractExtraction.id == extraction_id).first()
            record_audit_log(
                db,
                request,
                "approved_extraction_apply_error",
                entity_type="contract_extraction",
                entity_id=extraction.id if extraction else extraction_id,
                success=False,
                details="Falha ao aplicar dados aprovados.",
            )
            db.commit()
        finally:
            db.close()
        return RedirectResponse(f"/documents/{document_id}?apply_message=erro", status_code=303)

    db = SessionLocal()
    try:
        for event in audit_events:
            record_audit_log(
                db,
                request,
                event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                success=event.success,
                details=event.details,
            )
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/documents/{document_id}?apply_message=aplicado", status_code=303)


@app.post("/documents/{document_id:int}/reject")
async def document_reject(request: Request, document_id: int):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | ANALYSIS_WRITE_PROFILES, "Seu perfil não permite rejeitar extrações."):
        return redirect
    form = await request.form()
    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        extraction = latest_extraction_for_file(db, document.id)
        if not extraction:
            return JSONResponse({"error": "Não há extração para rejeitar."}, status_code=400)
        reason = str(form.get("review_notes", "")).strip() or "Extração rejeitada na validação humana."
        now = datetime.utcnow()
        extraction.review_status = "rejeitado"
        extraction.extraction_status = "rejeitado"
        extraction.apply_status = "pendente"
        extraction.apply_error = None
        extraction.reviewed_by = current_username(request)
        extraction.reviewed_at = now
        extraction.review_notes = reason
        document.processing_status = "rejeitado"
        document.extraction_status = "rejeitado"
        document.error_message = reason
        record_audit_log(db, request, "extraction_rejected", entity_type="contract_extraction", entity_id=extraction.id, details=reason)
        db.commit()
        return RedirectResponse(f"/documents/{document.id}", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse({"error": "Não foi possível rejeitar a extração."}, status_code=500)
    finally:
        db.close()


@app.post("/contracts/{contract_id}/additional")
def contract_additional_submit(
    request: Request,
    contract_id: int,
    responsible_name: str = Form(default=""),
    contact_info: str = Form(default=""),
    adjustment_type: str = Form(default=""),
):
    if redirect := require_profiles(
        request,
        CONTRACT_WRITE_PROFILES,
        "Seu perfil não permite editar dados contratuais.",
    ):
        return redirect

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)

        contract.responsible_name = responsible_name.strip() or None
        contract.contact_info = contact_info.strip() or None
        contract.adjustment_type = adjustment_type.strip() or None
        contract.reajust_index = contract.adjustment_type or contract.reajust_index
        record_auth_event(db, "contract_updated", username=current_username(request), request=request, notes=f"Cadastro adicional atualizado no contrato #{contract.id}.")
        db.commit()
        return RedirectResponse(f"/contracts/{contract_id}/additional?saved=1", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


@app.post("/contracts/import")
async def import_contract(
    request: Request,
    file: UploadFile = File(...),
    operator_name: str | None = Form(default=None),
    import_mode: str = Form(default="contract"),
):
    if redirect := require_profiles(
        request,
        CONTRACT_WRITE_PROFILES,
        "Seu perfil não permite importar ou editar contratos.",
    ):
        return redirect

    selected_operator_name = (operator_name or "").strip()
    is_additive = import_mode == "additive"
    if not selected_operator_name:
        return JSONResponse(
            {
                "error": (
                    "Selecione o convênio do aditivo antes de importar."
                    if is_additive
                    else "Selecione o convênio antes de importar o contrato."
                )
            },
            status_code=400,
        )

    from .services.uploads import UnsupportedUploadError, append_warning, prepare_contract_upload

    try:
        upload = await prepare_contract_upload(
            file,
            SUPPORTED_CONTRACT_EXTENSIONS,
            "Arquivo DOC salvo. Extração automática de DOC legado não está disponível; converta para DOCX/PDF para análise completa.",
        )
    except UnsupportedUploadError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    parsed = upload.parsed
    warning = upload.warning
    original_filename = upload.original_filename
    stored_path = upload.stored_path
    file_size = upload.file_size
    raw_text = upload.raw_text
    extraction_status = upload.extraction_status
    extraction_method = upload.extraction_method
    extraction_confidence = upload.extraction_confidence
    scoring = upload.scoring

    db = SessionLocal()
    try:
        operator = None
        parsed_operator_name = parsed.get("operator_name")
        contract_number = parsed.get("contract_number")
        contract_name = (
            f"{selected_operator_name} - {contract_number}"
            if contract_number
            else selected_operator_name
        )

        operator = db.query(Operator).filter(Operator.name == selected_operator_name).first()
        if not operator:
            operator = Operator(name=selected_operator_name)
            db.add(operator)
            db.flush()
        if parsed_operator_name and parsed_operator_name != selected_operator_name:
            warning = append_warning(warning, f"Operadora detectada no arquivo: {parsed_operator_name}.")

        if is_additive:
            parent_contract = (
                db.query(Contract)
                .filter(Contract.operator_name == selected_operator_name)
                .order_by(Contract.created_at.desc())
                .first()
            )
            if not parent_contract:
                return JSONResponse(
                    {
                        "error": (
                            "Não há contrato cadastrado para este convênio. "
                            "Cadastre o contrato principal antes de importar o aditivo."
                        )
                    },
                    status_code=400,
                )

            batch = ImportBatch(
                source_type="upload_additive",
                original_filename=original_filename,
                stored_filepath=str(stored_path),
                status="completed" if extraction_status != "failed" else "completed_with_warnings",
                total_records=1,
                imported_records=1,
                failed_records=0 if extraction_status != "failed" else 1,
                notes=warning,
                created_by=current_username(request),
            )
            db.add(batch)
            db.flush()

            additive = ContractAdditive(
                contract_id=parent_contract.id,
                additive_number=contract_number or Path(original_filename).stem,
                additive_type="Aditivo",
                object_summary=parsed.get("contract_object"),
                signature_date=parsed.get("signature_date"),
                start_date=parsed.get("start_date"),
                end_date=parsed.get("end_date"),
                status="active",
                reajust_index=parsed.get("reajust_index"),
                raw_text=raw_text,
                original_filename=original_filename,
                stored_filepath=str(stored_path),
            )
            db.add(additive)
            db.flush()

            contract_file = ContractFile(
                contract_id=parent_contract.id,
                import_batch_id=batch.id,
                file_type="additive",
                original_filename=original_filename,
                stored_filepath=str(stored_path),
                mime_type=file.content_type,
                file_size_bytes=file_size,
                extracted_text=raw_text,
                extraction_status=extraction_status,
                extraction_method=extraction_method,
                processing_status="processed" if extraction_status == "completed" else "error",
                processed_at=datetime.utcnow() if extraction_status == "completed" else None,
                notes=warning,
                error_message=warning if extraction_status == "failed" else None,
                uploaded_by=current_username(request),
            )
            db.add(contract_file)
            db.flush()
            record_auth_event(
                db,
                "contract_uploaded",
                username=current_username(request),
                request=request,
                notes=f"Aditivo enviado: {original_filename}. Contrato base #{parent_contract.id}.",
            )
            record_audit_log(db, request, "document_uploaded", entity_type="contract_file", entity_id=contract_file.id, details=f"Aditivo: {original_filename}")
            record_audit_log(db, request, "contract_additive_created", entity_type="contract_additive", entity_id=additive.id, details=additive.additive_number)
            db.commit()
            db.refresh(additive)

            return JSONResponse(
                {
                    "id": additive.id,
                    "additive_name": additive.additive_number,
                    "contract_id": parent_contract.id,
                    "contract_name": parent_contract.contract_name,
                    "operator_name": selected_operator_name,
                    "filename": original_filename,
                    "stored_filepath": str(stored_path),
                    "extraction_status": extraction_status,
                    "extraction_method": extraction_method,
                    "extraction_confidence": extraction_confidence,
                    "warning": warning,
                }
            )

        batch = ImportBatch(
            source_type="upload",
            original_filename=original_filename,
            stored_filepath=str(stored_path),
            status="completed" if extraction_status != "failed" else "completed_with_warnings",
            total_records=1,
            imported_records=1,
            failed_records=0 if extraction_status != "failed" else 1,
            notes=warning,
            created_by=current_username(request),
        )
        db.add(batch)
        db.flush()

        contract = Contract(
            operator_id=operator.id if operator else None,
            import_batch_id=batch.id,
            contract_name=contract_name,
            operator_name=selected_operator_name,
            contract_number=contract_number,
            contract_object=parsed.get("contract_object"),
            signature_date=parsed.get("signature_date"),
            start_date=parsed.get("start_date"),
            end_date=parsed.get("end_date"),
            auto_renewal=parsed.get("auto_renewal", False),
            renewal_details=parsed.get("renewal_details"),
            termination_notice_days=parsed.get("termination_notice_days"),
            payment_term_days=parsed.get("payment_term_days"),
            payment_trigger=parsed.get("payment_trigger"),
            payment_interest_clause=parsed.get("payment_interest_clause", False),
            payment_penalty_clause=parsed.get("payment_penalty_clause", False),
            billing_deadline_days=parsed.get("billing_deadline_days"),
            billing_deadline_description=parsed.get("billing_deadline_description"),
            allows_glosa_unilateral=parsed.get("allows_glosa_unilateral", False),
            glosa_deadline_days=parsed.get("glosa_deadline_days"),
            glosa_appeal_deadline_days=parsed.get("glosa_appeal_deadline_days"),
            glosa_response_deadline_days=parsed.get("glosa_response_deadline_days"),
            glosa_clause_summary=parsed.get("glosa_clause_summary"),
            reajust_clause_exists=parsed.get("reajust_clause_exists", False),
            reajust_frequency=parsed.get("reajust_frequency"),
            reajust_index=parsed.get("reajust_index"),
            reajust_clause_summary=parsed.get("reajust_clause_summary"),
            medical_fee_table=parsed.get("medical_fee_table"),
            medical_fee_table_version=parsed.get("medical_fee_table_version"),
            daily_rate_table=parsed.get("daily_rate_table"),
            materials_table=parsed.get("materials_table"),
            materials_table_version=parsed.get("materials_table_version"),
            medicines_table=parsed.get("medicines_table"),
            medicines_table_version=parsed.get("medicines_table_version"),
            raw_text=raw_text,
            score_total=scoring["score_total"],
            classification=scoring["classification"],
            risk_level=scoring["risk_level"],
            strong_points=scoring["strong_points"],
            weak_points=scoring["weak_points"],
            alerts=scoring["alerts"],
            extraction_method=extraction_method,
            extraction_confidence=extraction_confidence,
            original_filename=original_filename,
            stored_filepath=str(stored_path),
        )
        db.add(contract)
        db.flush()

        contract_file = ContractFile(
            contract_id=contract.id,
            import_batch_id=batch.id,
            file_type="contract",
            original_filename=original_filename,
            stored_filepath=str(stored_path),
            mime_type=file.content_type,
            file_size_bytes=file_size,
            extracted_text=raw_text,
            extraction_status=extraction_status,
            extraction_method=extraction_method,
            processing_status="processed" if extraction_status == "completed" else "error",
            processed_at=datetime.utcnow() if extraction_status == "completed" else None,
            notes=warning,
            error_message=warning if extraction_status == "failed" else None,
            uploaded_by=current_username(request),
        )
        db.add(contract_file)
        db.flush()
        from .services.ai_analysis import persist_contract_analysis

        persist_contract_analysis(
            db,
            contract,
            file_id=contract_file.id,
            created_by=current_username(request),
        )
        record_auth_event(
            db,
            "contract_uploaded",
            username=current_username(request),
            request=request,
            notes=f"Contrato enviado: {original_filename}. Contrato #{contract.id}.",
        )
        record_auth_event(
            db,
            "contract_analyzed",
            username=current_username(request),
            request=request,
            notes=f"Análise gerada para contrato #{contract.id}.",
        )
        record_audit_log(db, request, "contract_created", entity_type="contract", entity_id=contract.id, details=contract.contract_name)
        record_audit_log(db, request, "document_uploaded", entity_type="contract_file", entity_id=contract_file.id, details=original_filename)
        db.commit()
        db.refresh(contract)

        return JSONResponse(
            {
                "id": contract.id,
                "contract_name": contract.contract_name,
                "contract_number": contract.contract_number,
                "operator_name": contract.operator_name,
                "filename": original_filename,
                "stored_filepath": str(stored_path),
                "extraction_status": extraction_status,
                "extraction_method": extraction_method,
                "extraction_confidence": extraction_confidence,
                "warning": warning,
            }
        )
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse(
            {
                "error": "Não foi possível gravar o contrato no banco de dados.",
            },
            status_code=500,
        )
    except Exception as exc:
        db.rollback()
        return JSONResponse(
            {
                "error": "Não foi possível importar o contrato.",
            },
            status_code=500,
        )
    finally:
        db.close()


@app.get("/operators", response_class=HTMLResponse)
def operators_page(request: Request):
    if redirect := require_login(request):
        return redirect

    db = SessionLocal()
    try:
        operators = db.query(Operator).order_by(Operator.name.asc()).all()
        contract_counts = {
            operator_id: count
            for operator_id, count in db.query(Contract.operator_id, __import__("sqlalchemy").func.count(Contract.id))
            .group_by(Contract.operator_id)
            .all()
            if operator_id
        }
        return templates.TemplateResponse(
            request,
            "operators.html",
            {
                "title": "Operadoras",
                "active_page": "operators",
                "user": request.session.get("user"),
                "operators": operators,
                "contract_counts": contract_counts,
            },
        )
    finally:
        db.close()


@app.get("/operators/new", response_class=HTMLResponse)
def operator_new_page(request: Request):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES, "Seu perfil não permite cadastrar operadoras."):
        return redirect
    return templates.TemplateResponse(
        request,
        "operator_form.html",
        {"title": "Nova operadora", "active_page": "operators", "user": request.session.get("user"), "operator": None, "error": None},
    )


@app.post("/operators/new", response_class=HTMLResponse)
def operator_new_submit(
    request: Request,
    name: str = Form(...),
    tax_id: str = Form(default=""),
    contact_name: str = Form(default=""),
    contact_email: str = Form(default=""),
    contact_phone: str = Form(default=""),
    notes: str = Form(default=""),
    is_active: str | None = Form(default=None),
):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES, "Seu perfil não permite cadastrar operadoras."):
        return redirect
    db = SessionLocal()
    try:
        operator = Operator(
            name=name.strip(),
            tax_id=tax_id.strip() or None,
            contact_name=contact_name.strip() or None,
            contact_email=contact_email.strip() or None,
            contact_phone=contact_phone.strip() or None,
            notes=notes.strip() or None,
            is_active=bool(is_active),
        )
        db.add(operator)
        db.flush()
        record_audit_log(db, request, "operator_created", entity_type="operator", entity_id=operator.id, details=operator.name)
        db.commit()
        return RedirectResponse("/operators", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "operator_form.html",
            {"title": "Nova operadora", "active_page": "operators", "user": request.session.get("user"), "operator": None, "error": "Não foi possível salvar a operadora."},
            status_code=400,
        )
    finally:
        db.close()


@app.get("/operators/{operator_id:int}/edit", response_class=HTMLResponse)
def operator_edit_page(request: Request, operator_id: int):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES, "Seu perfil não permite editar operadoras."):
        return redirect
    db = SessionLocal()
    try:
        operator = db.query(Operator).filter(Operator.id == operator_id).first()
        if not operator:
            return RedirectResponse("/operators", status_code=303)
        return templates.TemplateResponse(
            request,
            "operator_form.html",
            {"title": "Editar operadora", "active_page": "operators", "user": request.session.get("user"), "operator": operator, "error": None},
        )
    finally:
        db.close()


@app.post("/operators/{operator_id:int}/edit", response_class=HTMLResponse)
def operator_edit_submit(
    request: Request,
    operator_id: int,
    name: str = Form(...),
    tax_id: str = Form(default=""),
    contact_name: str = Form(default=""),
    contact_email: str = Form(default=""),
    contact_phone: str = Form(default=""),
    notes: str = Form(default=""),
    is_active: str | None = Form(default=None),
):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES, "Seu perfil não permite editar operadoras."):
        return redirect
    db = SessionLocal()
    try:
        operator = db.query(Operator).filter(Operator.id == operator_id).first()
        if not operator:
            return RedirectResponse("/operators", status_code=303)
        operator.name = name.strip()
        operator.tax_id = tax_id.strip() or None
        operator.contact_name = contact_name.strip() or None
        operator.contact_email = contact_email.strip() or None
        operator.contact_phone = contact_phone.strip() or None
        operator.notes = notes.strip() or None
        operator.is_active = bool(is_active)
        record_audit_log(db, request, "operator_updated", entity_type="operator", entity_id=operator.id, details=operator.name)
        db.commit()
        return RedirectResponse("/operators", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse({"error": "Não foi possível atualizar a operadora."}, status_code=400)
    finally:
        db.close()


@app.get("/contract-terms", response_class=HTMLResponse)
def contract_terms_page(request: Request):
    if redirect := require_login(request):
        return redirect
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            request,
            "contract_terms.html",
            {
                "title": "Condições Contratuais",
                "active_page": "contract_terms",
                "user": request.session.get("user"),
                "contracts": db.query(Contract).filter(Contract.status != "inactive").order_by(Contract.contract_name.asc()).all(),
                "terms": db.query(ContractTerm).join(Contract).order_by(ContractTerm.created_at.desc()).all(),
            },
        )
    finally:
        db.close()


@app.get("/contracts/{contract_id:int}/terms", response_class=HTMLResponse)
def contract_terms_manage(request: Request, contract_id: int, simulation_message: str | None = None):
    if redirect := require_login(request):
        return redirect
    from .services.contract_terms_comparison_service import get_contract_terms_versions, get_current_terms
    from .services.reference_table_comparison_service import get_active_reference_tables

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
        versions = get_contract_terms_versions(db, contract.id)
        current_terms = get_current_terms(db, contract.id)
        current_version = next((version for version in versions if version["is_current"]), versions[0] if versions else None)
        additives = db.query(ContractAdditive).filter(ContractAdditive.contract_id == contract.id).order_by(ContractAdditive.created_at.desc()).all()
        simulations = (
            db.query(ContractTermSimulation)
            .filter(ContractTermSimulation.contract_id == contract.id)
            .order_by(ContractTermSimulation.created_at.desc())
            .limit(5)
            .all()
        )
        reference_tables = get_active_reference_tables(db)
        record_audit_log(db, request, "contract_terms_versions_viewed", entity_type="contract", entity_id=contract.id, details=f"{len(versions)} versao(oes).")
        db.commit()
        return templates.TemplateResponse(
            request,
            "contract_terms_manage.html",
            {
                "title": "Tabelas Contratuais",
                "active_page": "contract_terms",
                "user": request.session.get("user"),
                "contract": contract,
                "versions": versions,
                "current_terms": current_terms,
                "current_version": current_version,
                "additives": additives,
                "simulations": simulations,
                "reference_tables": reference_tables,
                "simulation_message": simulation_message,
            },
        )
    finally:
        db.close()


@app.get("/contracts/{contract_id:int}/terms/versions")
def contract_terms_versions_alias(request: Request, contract_id: int):
    if redirect := require_login(request):
        return redirect
    return RedirectResponse(f"/contracts/{contract_id}/terms", status_code=303)


@app.get("/contracts/{contract_id:int}/terms/compare", response_class=HTMLResponse)
def contract_terms_compare(request: Request, contract_id: int, from_version: int, to_version: int):
    if redirect := require_login(request):
        return redirect
    from .services.contract_terms_comparison_service import compare_terms_versions, get_contract_terms_versions

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
        comparison = compare_terms_versions(db, contract.id, from_version, to_version)
        versions = get_contract_terms_versions(db, contract.id)
        record_audit_log(
            db,
            request,
            "contract_terms_versions_compared",
            entity_type="contract",
            entity_id=contract.id,
            details=f"v{from_version} x v{to_version}; {len(comparison['rows'])} item(ns).",
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "contract_terms_compare.html",
            {
                "title": "Comparar Tabelas",
                "active_page": "contract_terms",
                "user": request.session.get("user"),
                "contract": contract,
                "comparison": comparison,
                "versions": versions,
            },
        )
    finally:
        db.close()


@app.get("/contracts/{contract_id:int}/terms/compare/export")
def contract_terms_compare_export(request: Request, contract_id: int, from_version: int, to_version: int):
    if redirect := require_login(request):
        return redirect
    import csv
    from io import StringIO

    from .services.contract_terms_comparison_service import compare_terms_versions

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
        comparison = compare_terms_versions(db, contract.id, from_version, to_version)
        output = StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Categoria", "Item", "Unidade", "Valor anterior", "Valor novo", "Diferenca R$", "Diferenca %", "Situacao", "Vigencia anterior", "Vigencia nova"])
        for row in comparison["rows"]:
            writer.writerow(
                [
                    row["category"],
                    row["item"],
                    row["unit"],
                    row["old_value"] or "",
                    row["new_value"] or "",
                    row["difference_amount"] or "",
                    row["difference_percent"] or "",
                    row["change_type"],
                    f"{row['old_valid_from'] or '-'} a {row['old_valid_until'] or 'vigente'}",
                    f"{row['new_valid_from'] or '-'} a {row['new_valid_until'] or 'vigente'}",
                ]
            )
        record_audit_log(db, request, "contract_terms_comparison_exported", entity_type="contract", entity_id=contract.id, details=f"v{from_version} x v{to_version}.")
        db.commit()
        filename = f"comparacao_contrato_{contract.id}_v{from_version}_v{to_version}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()


@app.get("/contracts/{contract_id:int}/terms/simulations", response_class=HTMLResponse)
def contract_terms_simulations(request: Request, contract_id: int, simulation_message: str | None = None):
    if redirect := require_login(request):
        return redirect
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
        simulations = (
            db.query(ContractTermSimulation)
            .filter(ContractTermSimulation.contract_id == contract.id)
            .order_by(ContractTermSimulation.created_at.desc())
            .all()
        )
        return templates.TemplateResponse(
            request,
            "contract_terms_simulations.html",
            {
                "title": "Simulacoes de Tabela",
                "active_page": "contract_terms",
                "user": request.session.get("user"),
                "contract": contract,
                "simulations": simulations,
                "simulation_message": simulation_message,
            },
        )
    finally:
        db.close()


@app.get("/contracts/{contract_id:int}/terms/simulations/new", response_class=HTMLResponse)
def contract_terms_simulation_new(request: Request, contract_id: int):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite criar simulacoes de tabela."):
        return redirect
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
        return templates.TemplateResponse(
            request,
            "contract_terms_simulation_form.html",
            {
                "title": "Nova Simulacao",
                "active_page": "contract_terms",
                "user": request.session.get("user"),
                "contract": contract,
                "row_count": 8,
                "base_version": db.query(func.max(ContractTerm.version)).filter(
                    ContractTerm.contract_id == contract.id,
                    ContractTerm.is_current.is_(True),
                ).scalar(),
            },
        )
    finally:
        db.close()


@app.post("/contracts/{contract_id:int}/terms/simulations")
async def contract_terms_simulation_create(request: Request, contract_id: int):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite criar simulacoes de tabela."):
        return redirect
    from .services.contract_terms_simulation_service import create_manual_simulation

    form = await request.form()
    rows = []
    for index in range(1, 21):
        row = {
            "category": str(form.get(f"category_{index}", "")).strip(),
            "title": str(form.get(f"item_{index}", "")).strip(),
            "description": str(form.get(f"description_{index}", "")).strip(),
            "reference_value": str(form.get(f"reference_value_{index}", "")).strip(),
            "unit": str(form.get(f"unit_{index}", "")).strip(),
            "valid_from": str(form.get(f"valid_from_{index}", "")).strip(),
            "valid_until": str(form.get(f"valid_until_{index}", "")).strip(),
        }
        if any(row.values()):
            rows.append(row)

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
    finally:
        db.close()

    try:
        simulation, events = create_manual_simulation(
            contract_id=contract_id,
            simulation_name=str(form.get("simulation_name", "")).strip() or "Simulacao manual",
            terms=rows,
            notes=str(form.get("notes", "")).strip() or None,
            created_by=current_username(request),
            base_version=parse_optional_int(str(form.get("base_version", "")).strip()),
        )
    except ValueError:
        return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/new?simulation_message=erro", status_code=303)

    db = SessionLocal()
    try:
        record_service_audit_events(db, request, events)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation.id}", status_code=303)


@app.post("/documents/{document_id:int}/create-table-simulation")
def document_create_table_simulation(request: Request, document_id: int):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite criar simulacoes de tabela."):
        return redirect
    from .services.contract_terms_simulation_service import create_simulation_from_extraction

    db = SessionLocal()
    try:
        document = db.query(ContractFile).filter(ContractFile.id == document_id).first()
        if not document:
            return RedirectResponse("/documents", status_code=303)
        extraction = latest_extraction_for_file(db, document.id)
        if not extraction or extraction.review_status != "aprovado":
            record_audit_log(
                db,
                request,
                "contract_term_simulation_without_approved_extraction",
                entity_type="contract_file",
                entity_id=document.id,
                success=False,
                details="Simulacao bloqueada: documento sem extracao aprovada.",
            )
            db.commit()
            return RedirectResponse(f"/documents/{document.id}?apply_message=sem_aprovacao", status_code=303)
        extraction_id = extraction.id
        contract_id = document.contract_id
    finally:
        db.close()

    try:
        simulation, events = create_simulation_from_extraction(extraction_id, created_by=current_username(request))
    except ValueError:
        return RedirectResponse(f"/documents/{document_id}?apply_message=erro_simulacao", status_code=303)

    db = SessionLocal()
    try:
        record_service_audit_events(db, request, events)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation.id}", status_code=303)


@app.get("/contracts/{contract_id:int}/terms/simulations/{simulation_id:int}", response_class=HTMLResponse)
def contract_terms_simulation_detail(request: Request, contract_id: int, simulation_id: int, simulation_message: str | None = None):
    if redirect := require_login(request):
        return redirect
    from .services.contract_terms_simulation_service import compare_simulation_with_current_terms

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        simulation = (
            db.query(ContractTermSimulation)
            .filter(ContractTermSimulation.id == simulation_id, ContractTermSimulation.contract_id == contract_id)
            .first()
        )
        if not contract or not simulation:
            return RedirectResponse(f"/contracts/{contract_id}/terms/simulations", status_code=303)
        comparison = compare_simulation_with_current_terms(db, simulation)
        return templates.TemplateResponse(
            request,
            "contract_terms_simulation_detail.html",
            {
                "title": "Simulacao de Tabela",
                "active_page": "contract_terms",
                "user": request.session.get("user"),
                "contract": contract,
                "simulation": simulation,
                "comparison": comparison,
                "simulation_message": simulation_message,
            },
        )
    finally:
        db.close()


@app.post("/contracts/{contract_id:int}/terms/simulations/{simulation_id:int}/approve")
def contract_terms_simulation_approve(request: Request, contract_id: int, simulation_id: int):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite aprovar simulacoes."):
        return redirect
    from .services.contract_terms_simulation_service import approve_simulation

    try:
        simulation, events = approve_simulation(simulation_id, reviewed_by=current_username(request), contract_id=contract_id)
    except ValueError:
        return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation_id}?simulation_message=erro", status_code=303)
    db = SessionLocal()
    try:
        record_service_audit_events(db, request, events)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation.id}?simulation_message=aprovada", status_code=303)


@app.post("/contracts/{contract_id:int}/terms/simulations/{simulation_id:int}/cancel")
def contract_terms_simulation_cancel(request: Request, contract_id: int, simulation_id: int):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite cancelar simulacoes."):
        return redirect
    from .services.contract_terms_simulation_service import cancel_simulation

    try:
        simulation, events = cancel_simulation(simulation_id, reviewed_by=current_username(request), contract_id=contract_id)
    except ValueError:
        db = SessionLocal()
        try:
            record_audit_log(
                db,
                request,
                "contract_term_simulation_cancel_blocked",
                entity_type="contract_term_simulation",
                entity_id=simulation_id,
                success=False,
                details="Cancelamento bloqueado pelo status da simulacao.",
            )
            db.commit()
        finally:
            db.close()
        return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation_id}?simulation_message=cancelamento_bloqueado", status_code=303)
    db = SessionLocal()
    try:
        record_service_audit_events(db, request, events)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation.id}?simulation_message=cancelada", status_code=303)


@app.post("/contracts/{contract_id:int}/terms/simulations/{simulation_id:int}/apply")
def contract_terms_simulation_apply(request: Request, contract_id: int, simulation_id: int):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite aplicar simulacoes."):
        return redirect
    from .services.contract_terms_simulation_service import apply_simulation_to_contract_terms

    db = SessionLocal()
    try:
        simulation = (
            db.query(ContractTermSimulation)
            .filter(ContractTermSimulation.id == simulation_id, ContractTermSimulation.contract_id == contract_id)
            .first()
        )
        if not simulation:
            return RedirectResponse(f"/contracts/{contract_id}/terms/simulations", status_code=303)
        if simulation.simulation_status == "aplicada":
            record_audit_log(
                db,
                request,
                "contract_term_simulation_apply_duplicate_blocked",
                entity_type="contract_term_simulation",
                entity_id=simulation.id,
                success=False,
                details="Aplicacao duplicada bloqueada.",
            )
            db.commit()
            return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation.id}?simulation_message=ja_aplicada", status_code=303)
        if simulation.simulation_status != "aprovada":
            record_audit_log(
                db,
                request,
                "contract_term_simulation_apply_without_approval",
                entity_type="contract_term_simulation",
                entity_id=simulation.id,
                success=False,
                details="Aplicacao bloqueada: simulacao ainda nao aprovada.",
            )
            db.commit()
            return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation.id}?simulation_message=sem_aprovacao", status_code=303)
    finally:
        db.close()

    try:
        simulation, events = apply_simulation_to_contract_terms(simulation_id, applied_by=current_username(request), contract_id=contract_id)
    except ValueError:
        db = SessionLocal()
        try:
            record_audit_log(
                db,
                request,
                "contract_term_simulation_apply_error",
                entity_type="contract_term_simulation",
                entity_id=simulation_id,
                success=False,
                details="Falha controlada ao aplicar simulacao.",
            )
            db.commit()
        finally:
            db.close()
        return RedirectResponse(f"/contracts/{contract_id}/terms/simulations/{simulation_id}?simulation_message=erro_aplicacao", status_code=303)

    db = SessionLocal()
    try:
        record_service_audit_events(db, request, events)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/contracts/{contract_id}/terms?simulation_message=simulacao_aplicada", status_code=303)


@app.get("/contracts/{contract_id:int}/terms/reference-compare", response_class=HTMLResponse)
def contract_terms_reference_compare(request: Request, contract_id: int, reference_table_id: int | None = None):
    if redirect := require_login(request):
        return redirect
    from .services.reference_table_comparison_service import compare_terms_with_reference, get_active_reference_tables

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            return RedirectResponse("/contracts", status_code=303)
        comparison = compare_terms_with_reference(db, contract.id, reference_table_id)
        reference_tables = get_active_reference_tables(db)
        record_audit_log(
            db,
            request,
            "contract_terms_reference_compared",
            entity_type="contract",
            entity_id=contract.id,
            details=f"{len(comparison.get('rows') or [])} item(ns) comparados com referencia.",
        )
        db.commit()
        return templates.TemplateResponse(
            request,
            "contract_terms_reference_compare.html",
            {
                "title": "Comparacao com Referencia",
                "active_page": "contract_terms",
                "user": request.session.get("user"),
                "contract": contract,
                "comparison": comparison,
                "reference_tables": reference_tables,
                "selected_reference_table_id": reference_table_id,
            },
        )
    finally:
        db.close()


@app.get("/reference-tables", response_class=HTMLResponse)
def reference_tables_page(request: Request):
    if redirect := require_login(request):
        return redirect
    db = SessionLocal()
    try:
        tables = db.query(ReferenceTable).order_by(ReferenceTable.created_at.desc()).all()
        item_counts = {
            table.id: db.query(ReferenceTableItem).filter(ReferenceTableItem.reference_table_id == table.id).count()
            for table in tables
        }
        return templates.TemplateResponse(
            request,
            "reference_tables.html",
            {
                "title": "Tabelas de Referencia",
                "active_page": "reference_tables",
                "user": request.session.get("user"),
                "tables": tables,
                "item_counts": item_counts,
            },
        )
    finally:
        db.close()


@app.get("/reference-tables/new", response_class=HTMLResponse)
def reference_table_new(request: Request):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite criar tabela de referencia."):
        return redirect
    return templates.TemplateResponse(
        request,
        "reference_table_form.html",
        {
            "title": "Nova Tabela de Referencia",
            "active_page": "reference_tables",
            "user": request.session.get("user"),
        },
    )


@app.post("/reference-tables")
async def reference_table_create(request: Request):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite criar tabela de referencia."):
        return redirect
    form = await request.form()
    db = SessionLocal()
    try:
        table = ReferenceTable(
            name=str(form.get("name", "")).strip(),
            source=str(form.get("source", "")).strip() or None,
            version=str(form.get("version", "")).strip() or None,
            valid_from=parse_optional_date(str(form.get("valid_from", "")).strip()),
            valid_until=parse_optional_date(str(form.get("valid_until", "")).strip()),
            status=str(form.get("status", "active")).strip() or "active",
            created_by=current_username(request),
        )
        if not table.name:
            return RedirectResponse("/reference-tables/new?reference_message=nome_obrigatorio", status_code=303)
        db.add(table)
        db.flush()
        record_audit_log(db, request, "reference_table_created", entity_type="reference_table", entity_id=table.id, details=table.name)
        db.commit()
        return RedirectResponse("/reference-tables", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse({"error": "Nao foi possivel criar a tabela de referencia."}, status_code=500)
    finally:
        db.close()


@app.post("/reference-tables/{reference_table_id:int}/items")
async def reference_table_item_create(request: Request, reference_table_id: int):
    if redirect := require_profiles(request, APPLY_APPROVED_EXTRACTION_PROFILES, "Seu perfil nao permite editar tabela de referencia."):
        return redirect
    from decimal import Decimal, InvalidOperation

    form = await request.form()
    db = SessionLocal()
    try:
        table = db.query(ReferenceTable).filter(ReferenceTable.id == reference_table_id).first()
        if not table:
            return RedirectResponse("/reference-tables", status_code=303)
        raw_value = str(form.get("value", "")).strip().replace(".", "").replace(",", ".")
        value = None
        if raw_value:
            try:
                value = Decimal(raw_value)
            except InvalidOperation:
                value = None
        item = ReferenceTableItem(
            reference_table_id=table.id,
            category=str(form.get("category", "")).strip() or None,
            item=str(form.get("item", "")).strip(),
            description=str(form.get("description", "")).strip() or None,
            value=value,
            unit=str(form.get("unit", "")).strip() or None,
            notes=str(form.get("notes", "")).strip() or None,
        )
        if not item.item:
            return RedirectResponse("/reference-tables", status_code=303)
        db.add(item)
        db.flush()
        record_audit_log(db, request, "reference_table_item_created", entity_type="reference_table_item", entity_id=item.id, details=item.item)
        db.commit()
        return RedirectResponse("/reference-tables", status_code=303)
    except SQLAlchemyError:
        db.rollback()
        return JSONResponse({"error": "Nao foi possivel criar o item de referencia."}, status_code=500)
    finally:
        db.close()


def production_records_query(db, *, competence: str | None = None, operator_id: int | None = None, contract_id: int | None = None, category: str | None = None, validation_status: str | None = None):
    query = db.query(ProductionRecord)
    competence_date = parse_optional_date(f"{competence}-01") if competence and len(competence) == 7 else None
    if competence_date:
        query = query.filter(ProductionRecord.competence_month == competence_date)
    if operator_id:
        query = query.filter(ProductionRecord.operator_id == operator_id)
    if contract_id:
        query = query.filter(ProductionRecord.contract_id == contract_id)
    if category:
        query = query.filter(ProductionRecord.category == category)
    if validation_status:
        query = query.filter(ProductionRecord.validation_status == validation_status)
    return query


def cost_rule_values(form, created_by=None):
    from decimal import Decimal, InvalidOperation
    def decimal_value(name):
        raw=str(form.get(name,"")).strip().replace(".","").replace(",",".")
        if not raw:return None
        try:return Decimal(raw)
        except InvalidOperation:raise ValueError(f"{name} inválido.")
    return {"cost_center_id":parse_optional_int(str(form.get("cost_center_id",""))),"name":str(form.get("name","")).strip(),"category":str(form.get("category","")).strip() or None,"item":str(form.get("item","")).strip() or None,"allocation_method":str(form.get("allocation_method","")).strip(),"percentage":decimal_value("percentage"),"fixed_value":decimal_value("fixed_value"),"valid_from":parse_optional_date(str(form.get("valid_from",""))),"valid_until":parse_optional_date(str(form.get("valid_until",""))),"status":str(form.get("status","ativo")),"created_by":created_by,"notes":str(form.get("notes","")).strip() or None}


@app.get("/cost-centers",response_class=HTMLResponse)
def cost_centers_page(request:Request):
    if redirect:=require_profiles(request,COST_VIEW_PROFILES,"Seu perfil não permite visualizar centros de custo."):return redirect
    db=SessionLocal()
    try:return templates.TemplateResponse(request,"cost_centers.html",{"title":"Centros de Custo","active_page":"production","user":request.session.get("user"),"centers":db.query(CostCenter).order_by(CostCenter.name).all()})
    finally:db.close()
@app.get("/cost-centers/new",response_class=HTMLResponse)
def cost_center_new(request:Request):
    if redirect:=require_profiles(request,COST_MANAGE_PROFILES,"Seu perfil não permite criar centros de custo."):return redirect
    return templates.TemplateResponse(request,"cost_center_form.html",{"title":"Novo Centro de Custo","active_page":"production","user":request.session.get("user"),"center":None})
@app.post("/cost-centers")
async def cost_center_create(request:Request):
    if redirect:=require_profiles(request,COST_MANAGE_PROFILES,"Seu perfil não permite criar centros de custo."):return redirect
    from .services.cost_allocation_service import create_cost_center
    form=await request.form()
    try:center=create_cost_center(name=form.get("name",""),code=form.get("code",""),status=form.get("status","ativo"),notes=form.get("notes") or None,created_by=current_username(request))
    except ValueError as exc:return JSONResponse({"error":str(exc)},status_code=400)
    db=SessionLocal()
    try:record_audit_log(db,request,"cost_center_created",entity_type="cost_center",entity_id=center.id,details=center.code);db.commit()
    finally:db.close()
    return RedirectResponse(f"/cost-centers/{center.id}",status_code=303)
@app.get("/cost-centers/{center_id:int}",response_class=HTMLResponse)
def cost_center_detail(request:Request,center_id:int):
    if redirect:=require_profiles(request,COST_VIEW_PROFILES,"Seu perfil não permite visualizar centros de custo."):return redirect
    db=SessionLocal()
    try:
        center=db.get(CostCenter,center_id)
        if not center:return RedirectResponse("/cost-centers",status_code=303)
        return templates.TemplateResponse(request,"cost_center_detail.html",{"title":center.name,"active_page":"production","user":request.session.get("user"),"center":center})
    finally:db.close()
@app.get("/cost-centers/{center_id:int}/edit",response_class=HTMLResponse)
def cost_center_edit(request:Request,center_id:int):
    if redirect:=require_profiles(request,COST_MANAGE_PROFILES,"Seu perfil não permite editar centros de custo."):return redirect
    db=SessionLocal()
    try:
        center=db.get(CostCenter,center_id)
        if not center:return RedirectResponse("/cost-centers",status_code=303)
        return templates.TemplateResponse(request,"cost_center_form.html",{"title":"Editar Centro de Custo","active_page":"production","user":request.session.get("user"),"center":center})
    finally:db.close()
@app.post("/cost-centers/{center_id:int}/edit")
async def cost_center_update(request:Request,center_id:int):
    if redirect:=require_profiles(request,COST_MANAGE_PROFILES,"Seu perfil não permite editar centros de custo."):return redirect
    from .services.cost_allocation_service import update_cost_center
    form=await request.form()
    try:center=update_cost_center(center_id,name=str(form.get("name","")),code=str(form.get("code","")),status=str(form.get("status","ativo")),notes=str(form.get("notes","")) or None)
    except ValueError as exc:return JSONResponse({"error":str(exc)},status_code=400)
    db=SessionLocal()
    try:record_audit_log(db,request,"cost_center_updated",entity_type="cost_center",entity_id=center.id,details=center.code);db.commit()
    finally:db.close()
    return RedirectResponse(f"/cost-centers/{center.id}",status_code=303)

@app.get("/cost-allocation-rules",response_class=HTMLResponse)
def cost_rules_page(request:Request):
    if redirect:=require_profiles(request,COST_VIEW_PROFILES,"Seu perfil não permite visualizar regras de rateio."):return redirect
    db=SessionLocal()
    try:return templates.TemplateResponse(request,"cost_allocation_rules.html",{"title":"Regras de Rateio","active_page":"production","user":request.session.get("user"),"rules":db.query(CostAllocationRule).order_by(CostAllocationRule.name).all()})
    finally:db.close()
@app.get("/cost-allocation-rules/new",response_class=HTMLResponse)
def cost_rule_new(request:Request):
    if redirect:=require_profiles(request,COST_MANAGE_PROFILES,"Seu perfil não permite criar regras."):return redirect
    db=SessionLocal()
    try:return templates.TemplateResponse(request,"cost_allocation_rule_form.html",{"title":"Nova Regra","active_page":"production","user":request.session.get("user"),"rule":None,"centers":db.query(CostCenter).filter(CostCenter.status=="ativo").all()})
    finally:db.close()
@app.post("/cost-allocation-rules")
async def cost_rule_create(request:Request):
    if redirect:=require_profiles(request,COST_MANAGE_PROFILES,"Seu perfil não permite criar regras."):return redirect
    from .services.cost_allocation_service import create_allocation_rule
    form=await request.form()
    try:rule=create_allocation_rule(**cost_rule_values(form,current_username(request)))
    except ValueError as exc:return JSONResponse({"error":str(exc)},status_code=400)
    db=SessionLocal()
    try:record_audit_log(db,request,"cost_allocation_rule_created",entity_type="cost_allocation_rule",entity_id=rule.id,details=rule.name);db.commit()
    finally:db.close()
    return RedirectResponse("/cost-allocation-rules",status_code=303)
@app.get("/cost-allocation-rules/{rule_id:int}/edit",response_class=HTMLResponse)
def cost_rule_edit(request:Request,rule_id:int):
    if redirect:=require_profiles(request,COST_MANAGE_PROFILES,"Seu perfil não permite editar regras."):return redirect
    db=SessionLocal()
    try:
        rule=db.get(CostAllocationRule,rule_id)
        if not rule:return RedirectResponse("/cost-allocation-rules",status_code=303)
        return templates.TemplateResponse(request,"cost_allocation_rule_form.html",{"title":"Editar Regra","active_page":"production","user":request.session.get("user"),"rule":rule,"centers":db.query(CostCenter).all()})
    finally:db.close()
@app.post("/cost-allocation-rules/{rule_id:int}/edit")
async def cost_rule_update(request:Request,rule_id:int):
    if redirect:=require_profiles(request,COST_MANAGE_PROFILES,"Seu perfil não permite editar regras."):return redirect
    from .services.cost_allocation_service import update_allocation_rule
    form=await request.form();values=cost_rule_values(form);values.pop("created_by",None)
    try:rule=update_allocation_rule(rule_id,**values)
    except ValueError as exc:return JSONResponse({"error":str(exc)},status_code=400)
    db=SessionLocal()
    try:record_audit_log(db,request,"cost_allocation_rule_updated",entity_type="cost_allocation_rule",entity_id=rule.id,details=rule.name);db.commit()
    finally:db.close()
    return RedirectResponse("/cost-allocation-rules",status_code=303)


@app.get("/production/imports", response_class=HTMLResponse)
def production_imports_page(request: Request):
    if redirect := require_profiles(request, PRODUCTION_VIEW_PROFILES, "Seu perfil não permite acessar importações de produção."):
        return redirect
    db = SessionLocal()
    try:
        batches = db.query(ProductionImportBatch).order_by(ProductionImportBatch.imported_at.desc()).all()
        return templates.TemplateResponse(request, "production_imports.html", {"title": "Importações de Produção", "active_page": "production", "user": request.session.get("user"), "batches": batches})
    finally:
        db.close()


@app.get("/production/imports/preview", response_class=HTMLResponse)
def production_import_preview_form(request: Request):
    if redirect := require_profiles(request, PRODUCTION_IMPORT_PROFILES, "Seu perfil não permite testar importações."):
        return redirect
    db=SessionLocal()
    try:
        layouts=db.query(ProductionImportLayout).filter(ProductionImportLayout.status=="ativo").order_by(ProductionImportLayout.name).all()
        return templates.TemplateResponse(request,"production_import_preview.html",{"title":"Preview de Importação","active_page":"production","user":request.session.get("user"),"layouts":layouts,"preview":None,"error":None})
    finally: db.close()


@app.post("/production/imports/preview", response_class=HTMLResponse)
async def production_import_preview_run(request: Request, file: UploadFile=File(...), layout_id: int|None=Form(default=None), source_system: str=Form(default="planilha"), delimiter: str=Form(default=""), encoding: str=Form(default=""), sheet_name: str=Form(default="")):
    if redirect := require_profiles(request, PRODUCTION_IMPORT_PROFILES, "Seu perfil não permite testar importações."):
        return redirect
    import tempfile
    from .config import MAX_UPLOAD_SIZE_BYTES
    from .services.production_import_service import build_import_preview
    extension=Path(file.filename or "").suffix.lower();temp_path=None;preview=None;error=None
    try:
        if extension not in {".csv",".xlsx"}: raise ValueError("Preview aceita somente CSV ou Excel .xlsx.")
        content=await file.read(MAX_UPLOAD_SIZE_BYTES+1)
        if not content or len(content)>MAX_UPLOAD_SIZE_BYTES: raise ValueError("Arquivo vazio ou acima do limite permitido.")
        handle=tempfile.NamedTemporaryFile(delete=False,suffix=extension);handle.write(content);handle.close();temp_path=Path(handle.name)
        preview=build_import_preview(temp_path,layout_id=layout_id,delimiter=delimiter or None,encoding=encoding or None,sheet_name=sheet_name or None,limit=50)
        db=SessionLocal()
        try: record_audit_log(db,request,"production_import_preview_executed",entity_type="production_import_layout",entity_id=layout_id,details=f"{preview['analyzed_rows']} linha(s); compatível={preview['compatible']}.");db.commit()
        finally: db.close()
    except Exception as exc:
        error=str(exc)
        db=SessionLocal()
        try: record_audit_log(db,request,"production_import_preview_error",entity_type="production_import_layout",entity_id=layout_id,success=False,details="Falha ao analisar arquivo no preview.");db.commit()
        finally: db.close()
    finally:
        if temp_path: temp_path.unlink(missing_ok=True)
    db=SessionLocal()
    try:
        layouts=db.query(ProductionImportLayout).filter(ProductionImportLayout.status=="ativo").order_by(ProductionImportLayout.name).all()
        return templates.TemplateResponse(request,"production_import_preview.html",{"title":"Preview de Importação","active_page":"production","user":request.session.get("user"),"layouts":layouts,"preview":preview,"error":error,"selected_layout_id":layout_id,"source_system":source_system,"delimiter":delimiter,"encoding":encoding,"sheet_name":sheet_name})
    finally: db.close()


def production_layout_mappings_from_form(form) -> list[dict]:
    from .services.production_layout_service import TARGET_FIELDS
    return [{"target_field": field, "source_column": str(form.get(f"source_{field}", "")).strip(), "required": field in set(TARGET_FIELDS[:13]), "default_value": str(form.get(f"default_{field}", "")).strip() or None, "transform_rule": str(form.get(f"transform_{field}", "")).strip() or None} for field in TARGET_FIELDS]


@app.get("/production/layouts", response_class=HTMLResponse)
def production_layouts_page(request: Request):
    if redirect := require_profiles(request, PRODUCTION_LAYOUT_VIEW_PROFILES, "Seu perfil não permite visualizar layouts de importação."):
        return redirect
    db = SessionLocal()
    try:
        layouts = db.query(ProductionImportLayout).order_by(ProductionImportLayout.name).all()
        return templates.TemplateResponse(request, "production_layouts.html", {"title": "Layouts de Importação", "active_page": "production", "user": request.session.get("user"), "layouts": layouts})
    finally: db.close()


@app.get("/production/layouts/new", response_class=HTMLResponse)
def production_layout_new(request: Request):
    if redirect := require_profiles(request, PRODUCTION_LAYOUT_MANAGE_PROFILES, "Seu perfil não permite criar layouts."):
        return redirect
    from .services.production_layout_service import TARGET_FIELDS
    return templates.TemplateResponse(request, "production_layout_form.html", {"title": "Novo Layout", "active_page": "production", "user": request.session.get("user"), "layout": None, "mapping_by_target": {}, "target_fields": TARGET_FIELDS})


@app.post("/production/layouts")
async def production_layout_create(request: Request):
    if redirect := require_profiles(request, PRODUCTION_LAYOUT_MANAGE_PROFILES, "Seu perfil não permite criar layouts."):
        return redirect
    from .services.production_layout_service import create_layout
    form = await request.form()
    try:
        layout = create_layout(name=str(form.get("name", "")), source_system=str(form.get("source_system", "planilha")), source_type=str(form.get("source_type", "csv")), delimiter=str(form.get("delimiter", "")).replace("\\t", "\t") or None, encoding=str(form.get("encoding", "")).strip() or None, has_header=bool(form.get("has_header")), status=str(form.get("status", "rascunho")), mappings=production_layout_mappings_from_form(form), created_by=current_username(request), notes=str(form.get("notes", "")).strip() or None)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    db = SessionLocal()
    try:
        record_audit_log(db, request, "production_import_layout_created", entity_type="production_import_layout", entity_id=layout.id, details=layout.name); db.commit()
    finally: db.close()
    return RedirectResponse(f"/production/layouts/{layout.id}", status_code=303)


@app.get("/production/layouts/{layout_id:int}", response_class=HTMLResponse)
def production_layout_detail(request: Request, layout_id: int):
    if redirect := require_profiles(request, PRODUCTION_LAYOUT_VIEW_PROFILES, "Seu perfil não permite visualizar layouts."):
        return redirect
    from .services.production_layout_service import validate_layout
    db = SessionLocal()
    try:
        layout = db.query(ProductionImportLayout).filter(ProductionImportLayout.id == layout_id).first()
        if not layout: return RedirectResponse("/production/layouts", status_code=303)
        return templates.TemplateResponse(request, "production_layout_detail.html", {"title": layout.name, "active_page": "production", "user": request.session.get("user"), "layout": layout, "validation": validate_layout(layout)})
    finally: db.close()


@app.get("/production/layouts/{layout_id:int}/edit", response_class=HTMLResponse)
def production_layout_edit(request: Request, layout_id: int):
    if redirect := require_profiles(request, PRODUCTION_LAYOUT_MANAGE_PROFILES, "Seu perfil não permite editar layouts."):
        return redirect
    from .services.production_layout_service import TARGET_FIELDS
    db = SessionLocal()
    try:
        layout = db.query(ProductionImportLayout).filter(ProductionImportLayout.id == layout_id).first()
        if not layout: return RedirectResponse("/production/layouts", status_code=303)
        return templates.TemplateResponse(request, "production_layout_form.html", {"title": "Editar Layout", "active_page": "production", "user": request.session.get("user"), "layout": layout, "mapping_by_target": {row.target_field: row for row in layout.mappings}, "target_fields": TARGET_FIELDS})
    finally: db.close()


@app.post("/production/layouts/{layout_id:int}/edit")
async def production_layout_update(request: Request, layout_id: int):
    if redirect := require_profiles(request, PRODUCTION_LAYOUT_MANAGE_PROFILES, "Seu perfil não permite editar layouts."):
        return redirect
    from .services.production_layout_service import update_layout
    form = await request.form()
    try:
        layout = update_layout(layout_id, name=str(form.get("name", "")).strip(), source_system=str(form.get("source_system", "planilha")), source_type=str(form.get("source_type", "csv")), delimiter=str(form.get("delimiter", "")).replace("\\t", "\t") or None, encoding=str(form.get("encoding", "")).strip() or None, has_header=bool(form.get("has_header")), status=str(form.get("status", "rascunho")), notes=str(form.get("notes", "")).strip() or None, mappings=production_layout_mappings_from_form(form))
    except ValueError as exc: return JSONResponse({"error": str(exc)}, status_code=400)
    db = SessionLocal()
    try:
        action = "production_import_layout_status_changed" if layout.status in {"ativo", "inativo"} else "production_import_layout_updated"
        record_audit_log(db, request, action, entity_type="production_import_layout", entity_id=layout.id, details=layout.name); db.commit()
    finally: db.close()
    return RedirectResponse(f"/production/layouts/{layout.id}", status_code=303)


@app.get("/production/imports/new", response_class=HTMLResponse)
def production_import_new(request: Request):
    if redirect := require_profiles(request, PRODUCTION_IMPORT_PROFILES, "Seu perfil não permite importar produção."):
        return redirect
    db = SessionLocal()
    try:
        layouts = db.query(ProductionImportLayout).filter(ProductionImportLayout.status == "ativo").order_by(ProductionImportLayout.name).all()
        return templates.TemplateResponse(request, "production_import_form.html", {"title": "Nova Importação de Produção", "active_page": "production", "user": request.session.get("user"), "layouts": layouts})
    finally: db.close()


@app.post("/production/imports")
async def production_import_create(request: Request, file: UploadFile = File(...), batch_name: str = Form(...), source_system: str = Form(default="planilha"), layout_id: int | None = Form(default=None), notes: str = Form(default="")):
    if redirect := require_profiles(request, PRODUCTION_IMPORT_PROFILES, "Seu perfil não permite importar produção."):
        return redirect
    from .services.production_import_service import create_import_batch, import_file_to_batch
    from .services.uploads import UnsupportedUploadError, save_upload_file

    original_filename = Path(file.filename or "producao.csv").name
    extension = Path(original_filename).suffix.lower()
    if extension not in {".csv", ".xlsx"}:
        return JSONResponse({"error": "Envie CSV ou Excel .xlsx; .xls legado não é suportado."}, status_code=400)
    db = SessionLocal()
    try:
        layout = db.query(ProductionImportLayout).filter(ProductionImportLayout.id == layout_id, ProductionImportLayout.status == "ativo").first() if layout_id else None
        if layout_id and not layout: return JSONResponse({"error": "Layout ativo não encontrado."}, status_code=400)
        if layout and ((extension == ".xlsx") != (layout.source_type == "excel")): return JSONResponse({"error": "Tipo do arquivo não corresponde ao layout selecionado."}, status_code=400)
        if layout: source_system = layout.source_system
    finally: db.close()
    stored_path = None
    try:
        stored_path, _ = await save_upload_file(file, extension)
        batch, created_events = create_import_batch(batch_name=batch_name, source_type="excel" if extension == ".xlsx" else "csv", source_system=source_system, original_filename=original_filename, file_path=str(stored_path), imported_by=current_username(request), notes=notes.strip() or None, layout_id=layout_id)
        batch, processing_events = import_file_to_batch(batch.id, stored_path)
        events = [*created_events, *processing_events]
    except (ValueError, UnsupportedUploadError) as exc:
        db = SessionLocal()
        try:
            batch_record = db.query(ProductionImportBatch).filter(ProductionImportBatch.file_path == str(stored_path)).first() if stored_path else None
            if batch_record:
                batch_record.import_status = "erro"
                batch_record.error_message = str(exc)[:500]
                record_audit_log(db, request, "production_import_batch_error", entity_type="production_import_batch", entity_id=batch_record.id, success=False, details="Falha de validação do arquivo de produção.")
                if extension == ".xlsx":
                    record_audit_log(db, request, "production_excel_import_error", entity_type="production_import_batch", entity_id=batch_record.id, success=False, details="Falha ao ler ou mapear arquivo Excel.")
                if layout_id:
                    record_audit_log(db, request, "production_import_layout_error", entity_type="production_import_layout", entity_id=layout_id, success=False, details=f"Falha de layout no lote #{batch_record.id}.")
                db.commit()
                return RedirectResponse(f"/production/imports/{batch_record.id}", status_code=303)
        finally:
            db.close()
        if stored_path:
            stored_path.unlink(missing_ok=True)
        return JSONResponse({"error": str(exc)}, status_code=400)
    db = SessionLocal()
    try:
        record_service_audit_events(db, request, events)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/production/imports/{batch.id}", status_code=303)


@app.get("/production/imports/{batch_id:int}", response_class=HTMLResponse)
def production_import_detail(request: Request, batch_id: int):
    if redirect := require_profiles(request, PRODUCTION_VIEW_PROFILES, "Seu perfil não permite acessar importações de produção."):
        return redirect
    from .services.production_import_service import build_import_summary
    db = SessionLocal()
    try:
        batch = db.query(ProductionImportBatch).filter(ProductionImportBatch.id == batch_id).first()
        if not batch:
            return RedirectResponse("/production/imports", status_code=303)
        records = db.query(ProductionRecord).filter(ProductionRecord.batch_id == batch.id).order_by(ProductionRecord.source_row_number).limit(500).all()
        return templates.TemplateResponse(request, "production_import_detail.html", {"title": "Detalhe da Importação", "active_page": "production", "user": request.session.get("user"), "batch": batch, "records": records, "summary": build_import_summary(db, batch.id)})
    finally:
        db.close()


@app.post("/production/imports/{batch_id:int}/cancel")
def production_import_cancel(request: Request, batch_id: int):
    if redirect := require_profiles(request, PRODUCTION_IMPORT_PROFILES, "Seu perfil não permite cancelar importações."):
        return redirect
    from .services.production_import_service import cancel_import_batch
    try:
        batch, events = cancel_import_batch(batch_id, cancelled_by=current_username(request))
    except ValueError:
        return RedirectResponse(f"/production/imports/{batch_id}?cancel_message=bloqueado", status_code=303)
    db = SessionLocal()
    try:
        record_service_audit_events(db, request, events)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(f"/production/imports/{batch.id}", status_code=303)


@app.get("/production/records", response_class=HTMLResponse)
def production_records_page(request: Request, competence: str | None = None, operator_id: int | None = None, contract_id: int | None = None, category: str | None = None, validation_status: str | None = None):
    if redirect := require_profiles(request, PRODUCTION_VIEW_PROFILES, "Seu perfil não permite acessar produção consolidada."):
        return redirect
    from .services.financial_impact_service import calculate_margin_estimate
    db = SessionLocal()
    try:
        filtered_query = production_records_query(db, competence=competence, operator_id=operator_id, contract_id=contract_id, category=category, validation_status=validation_status)
        aggregate = filtered_query.with_entities(
            func.count(ProductionRecord.id),
            func.coalesce(func.sum(ProductionRecord.billed_value), 0),
            func.coalesce(func.sum(ProductionRecord.paid_value), 0),
            func.coalesce(func.sum(ProductionRecord.denied_value), 0),
            func.coalesce(func.sum(ProductionRecord.cost_value), 0),
            func.count(ProductionRecord.cost_value),
        ).one()
        records = filtered_query.order_by(ProductionRecord.service_date.desc(), ProductionRecord.id.desc()).limit(1000).all()
        totals = {"count": aggregate[0], "billed": aggregate[1], "paid": aggregate[2], "denied": aggregate[3], "cost": aggregate[4], "records_with_cost": aggregate[5]}
        margin = calculate_margin_estimate(db, contract_id=contract_id, operator_id=operator_id) if contract_id or operator_id else {"status": "filtro_necessario", "message": "Selecione contrato ou operadora para avaliar completude de custo.", "margin_estimate": None}
        record_audit_log(db, request, "production_records_viewed", entity_type="production_records", details=f"{aggregate[0]} registro(s) filtrado(s).")
        db.commit()
        return templates.TemplateResponse(request, "production_records.html", {"title": "Produção Consolidada", "active_page": "production", "user": request.session.get("user"), "records": records, "totals": totals, "margin": margin, "active_allocation_rules": db.query(CostAllocationRule).filter(CostAllocationRule.status=="ativo").count(), "operators": db.query(Operator).filter(Operator.is_active.is_(True)).order_by(Operator.name).all(), "contracts": db.query(Contract).filter(Contract.status == "active").order_by(Contract.contract_name).all(), "categories": [row[0] for row in db.query(ProductionRecord.category).filter(ProductionRecord.category.isnot(None)).distinct().order_by(ProductionRecord.category).all()], "filters": {"competence": competence, "operator_id": operator_id, "contract_id": contract_id, "category": category, "validation_status": validation_status}})
    finally:
        db.close()


@app.get("/production/records/export")
def production_records_export(request: Request, competence: str | None = None, operator_id: int | None = None, contract_id: int | None = None, category: str | None = None, validation_status: str | None = None):
    if redirect := require_profiles(request, PRODUCTION_VIEW_PROFILES, "Seu perfil não permite exportar produção."):
        return redirect
    db = SessionLocal()
    try:
        records = production_records_query(db, competence=competence, operator_id=operator_id, contract_id=contract_id, category=category, validation_status=validation_status).order_by(ProductionRecord.id).all()
        rows = [["Competencia", "Operadora", "Contrato", "Categoria", "Item", "Quantidade", "Unidade", "Valor faturado", "Valor pago", "Valor glosado", "Custo", "Status"]]
        rows.extend([[record.competence_month, record.operator.name if record.operator else "", record.contract.contract_name if record.contract else "", record.category or "", record.item or "", record.quantity or "", record.unit or "", record.billed_value or "", record.paid_value or "", record.denied_value or "", record.cost_value if record.cost_value is not None else "", record.validation_status] for record in records])
        record_audit_log(db, request, "production_records_exported", entity_type="production_records", details=f"{len(records)} registro(s).")
        db.commit()
        return commercial_csv_response(rows, "producao_consolidada.csv")
    finally:
        db.close()


@app.get("/production/records/{record_id:int}/cost-estimate",response_class=HTMLResponse)
def production_record_cost_estimate(request:Request,record_id:int):
    if redirect:=require_profiles(request,COST_VIEW_PROFILES,"Seu perfil não permite consultar estimativas de custo."):return redirect
    from .services.cost_allocation_service import estimate_indirect_cost_for_record
    db=SessionLocal()
    try:
        record=db.get(ProductionRecord,record_id)
        if not record:return RedirectResponse("/production/records",status_code=303)
        estimate=estimate_indirect_cost_for_record(db,record)
        record_audit_log(db,request,"indirect_cost_estimate_viewed",entity_type="production_record",entity_id=record.id,details=f"{len(estimate['rules'])} regra(s) aplicável(is).");db.commit()
        return templates.TemplateResponse(request,"production_cost_estimate.html",{"title":"Estimativa de Custo Indireto","active_page":"production","user":request.session.get("user"),"record":record,"estimate":estimate})
    finally:db.close()


def parse_commercial_contract_ids(raw: str | None) -> list[int]:
    values = []
    for item in (raw or "").split(","):
        try:
            value = int(item.strip())
        except ValueError:
            continue
        if value > 0 and value not in values:
            values.append(value)
    return values[:10]


def commercial_csv_response(rows: list[list], filename: str) -> Response:
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerows(rows)
    return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/bi/commercial", response_class=HTMLResponse)
def commercial_bi_dashboard(request: Request):
    if redirect := require_profiles(request, COMMERCIAL_BI_VIEW_PROFILES, "Seu perfil não permite visualizar o BI Comercial."):
        return redirect
    from .services.commercial_bi_service import build_bi_alerts, get_commercial_dashboard_summary, get_conditions_by_category, rank_operators_by_contract_values

    db = SessionLocal()
    try:
        summary = get_commercial_dashboard_summary(db)
        ranking = rank_operators_by_contract_values(db)
        conditions = get_conditions_by_category(db)
        alerts = build_bi_alerts(db)
        record_audit_log(db, request, "commercial_bi_viewed", entity_type="commercial_bi", details=f"{len(ranking)} operadora(s); {len(alerts)} alerta(s).")
        db.commit()
        return templates.TemplateResponse(request, "commercial_bi.html", {"title": "BI Comercial", "active_page": "commercial_bi", "user": request.session.get("user"), "summary": summary, "ranking": ranking[:10], "conditions": conditions, "alerts": alerts[:30]})
    finally:
        db.close()


@app.get("/bi/commercial/operators", response_class=HTMLResponse)
def commercial_bi_operators(request: Request):
    if redirect := require_profiles(request, COMMERCIAL_BI_VIEW_PROFILES, "Seu perfil não permite visualizar o ranking comercial."):
        return redirect
    from .services.commercial_bi_service import rank_operators_by_contract_values

    db = SessionLocal()
    try:
        ranking = rank_operators_by_contract_values(db)
        return templates.TemplateResponse(request, "commercial_bi_operators.html", {"title": "Ranking de Operadoras", "active_page": "commercial_bi", "user": request.session.get("user"), "ranking": ranking})
    finally:
        db.close()


@app.get("/bi/commercial/compare", response_class=HTMLResponse)
def commercial_bi_compare(request: Request, contract_ids: str | None = None):
    if redirect := require_profiles(request, COMMERCIAL_BI_VIEW_PROFILES, "Seu perfil não permite gerar comparativos comerciais."):
        return redirect
    from .services.commercial_bi_service import compare_contracts_executive

    selected_ids = parse_commercial_contract_ids(contract_ids)
    db = SessionLocal()
    try:
        comparison = compare_contracts_executive(db, selected_ids)
        contracts = db.query(Contract).filter(Contract.status == "active").order_by(Contract.contract_name).all()
        if selected_ids:
            record_audit_log(db, request, "commercial_bi_comparison_generated", entity_type="commercial_bi", details=f"Contratos: {','.join(map(str, selected_ids))}; {len(comparison['rows'])} item(ns).")
            db.commit()
        return templates.TemplateResponse(request, "commercial_bi_compare.html", {"title": "Comparativo Executivo", "active_page": "commercial_bi", "user": request.session.get("user"), "contracts": contracts, "selected_ids": selected_ids, "comparison": comparison})
    finally:
        db.close()


@app.get("/bi/commercial/export/ranking")
def commercial_bi_export_ranking(request: Request):
    if redirect := require_profiles(request, COMMERCIAL_BI_EXPORT_PROFILES, "Seu perfil não permite exportar o ranking comercial."):
        return redirect
    from .services.commercial_bi_service import rank_operators_by_contract_values

    db = SessionLocal()
    try:
        ranking = rank_operators_by_contract_values(db)
        rows = [["Posicao", "Operadora", "Score Comercial", "Contratos ativos", "Contratos com tabela", "Itens vigentes"]]
        rows.extend([[row["position"], row["operator"].name, row["score"], row["contract_count"], row["contracts_with_terms"], row["item_count"]] for row in ranking])
        record_audit_log(db, request, "commercial_bi_ranking_exported", entity_type="commercial_bi", details=f"{len(ranking)} operadora(s).")
        db.commit()
        return commercial_csv_response(rows, "bi_comercial_ranking_operadoras.csv")
    finally:
        db.close()


@app.get("/bi/commercial/export/conditions")
def commercial_bi_export_conditions(request: Request):
    if redirect := require_profiles(request, COMMERCIAL_BI_EXPORT_PROFILES, "Seu perfil não permite exportar condições comerciais."):
        return redirect
    from .services.commercial_bi_service import get_conditions_by_category

    db = SessionLocal()
    try:
        conditions = get_conditions_by_category(db)
        rows = [["Categoria", "Quantidade", "Maior valor", "Operadora maior", "Contrato maior", "Menor valor", "Operadora menor", "Contrato menor", "Situacao"]]
        for row in conditions:
            high_contract, low_contract = row.get("highest_contract"), row.get("lowest_contract")
            rows.append([row["category"], row["item_count"], row.get("highest").reference_value if row.get("highest") else "", high_contract.operator_name if high_contract else "", high_contract.contract_name if high_contract else "", row.get("lowest").reference_value if row.get("lowest") else "", low_contract.operator_name if low_contract else "", low_contract.contract_name if low_contract else "", row["status"]])
        record_audit_log(db, request, "commercial_bi_conditions_exported", entity_type="commercial_bi", details=f"{len(conditions)} categoria(s).")
        db.commit()
        return commercial_csv_response(rows, "bi_comercial_melhores_piores_condicoes.csv")
    finally:
        db.close()


@app.get("/bi/commercial/compare/export")
def commercial_bi_compare_export(request: Request, contract_ids: str | None = None):
    if redirect := require_profiles(request, COMMERCIAL_BI_EXPORT_PROFILES, "Seu perfil não permite exportar comparativos comerciais."):
        return redirect
    from .services.commercial_bi_service import compare_contracts_executive

    selected_ids = parse_commercial_contract_ids(contract_ids)
    db = SessionLocal()
    try:
        comparison = compare_contracts_executive(db, selected_ids)
        rows = [["Categoria", "Item", "Unidade", *[contract.contract_name for contract in comparison["contracts"]], "Maior valor", "Menor valor"]]
        for row in comparison["rows"]:
            rows.append([row["category"], row["item"], row["unit"] or "", *[row["values"].get(contract.id, "") for contract in comparison["contracts"]], row["highest"] or "", row["lowest"] or ""])
        record_audit_log(db, request, "commercial_bi_comparison_exported", entity_type="commercial_bi", details=f"{len(comparison['contracts'])} contrato(s); {len(comparison['rows'])} item(ns).")
        db.commit()
        return commercial_csv_response(rows, "bi_comercial_comparativo_executivo.csv")
    finally:
        db.close()


@app.post("/contract-terms")
def contract_term_create(
    request: Request,
    contract_id: int = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    description: str = Form(default=""),
    reference_value: str = Form(default=""),
    unit: str = Form(default=""),
    deadline_days: str = Form(default=""),
    version: int = Form(default=1),
    valid_from: str = Form(default=""),
    valid_until: str = Form(default=""),
    is_current: str | None = Form(default=None),
    source_type: str = Form(default="manual"),
    rule_text: str = Form(default=""),
):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | FINANCIAL_PROFILES, "Seu perfil não permite registrar condições contratuais."):
        return redirect
    db = SessionLocal()
    try:
        amount = reference_value.replace(".", "").replace(",", ".").strip()
        term = ContractTerm(
            contract_id=contract_id,
            category=category.strip(),
            title=title.strip(),
            description=description.strip() or None,
            reference_value=float(amount) if amount else None,
            unit=unit.strip() or None,
            deadline_days=parse_optional_int(deadline_days),
            version=version,
            valid_from=parse_optional_date(valid_from),
            valid_until=parse_optional_date(valid_until),
            is_current=bool(is_current),
            source_type=source_type.strip() or "manual",
            rule_text=rule_text.strip() or None,
            created_by=current_username(request),
        )
        db.add(term)
        db.flush()
        record_audit_log(db, request, "contract_term_created", entity_type="contract_term", entity_id=term.id, details=term.title)
        db.commit()
        return RedirectResponse("/contract-terms", status_code=303)
    except (SQLAlchemyError, ValueError):
        db.rollback()
        return JSONResponse({"error": "Não foi possível salvar a condição contratual."}, status_code=400)
    finally:
        db.close()


@app.post("/contract-terms/{term_id:int}/edit")
def contract_term_edit(
    request: Request,
    term_id: int,
    title: str = Form(...),
    description: str = Form(default=""),
    reference_value: str = Form(default=""),
    unit: str = Form(default=""),
    deadline_days: str = Form(default=""),
    version: int = Form(default=1),
    valid_from: str = Form(default=""),
    valid_until: str = Form(default=""),
    is_current: str | None = Form(default=None),
    status: str = Form(default="active"),
    rule_text: str = Form(default=""),
):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | FINANCIAL_PROFILES, "Seu perfil não permite editar condições contratuais."):
        return redirect
    db = SessionLocal()
    try:
        term = db.query(ContractTerm).filter(ContractTerm.id == term_id).first()
        if not term:
            return RedirectResponse("/contract-terms", status_code=303)
        amount = reference_value.replace(".", "").replace(",", ".").strip()
        term.title = title.strip()
        term.description = description.strip() or None
        term.reference_value = float(amount) if amount else None
        term.unit = unit.strip() or None
        term.deadline_days = parse_optional_int(deadline_days)
        term.version = version
        term.valid_from = parse_optional_date(valid_from)
        term.valid_until = parse_optional_date(valid_until)
        term.is_current = bool(is_current)
        term.status = status.strip() or "active"
        term.rule_text = rule_text.strip() or None
        record_audit_log(db, request, "contract_term_updated", entity_type="contract_term", entity_id=term.id, details=term.title)
        db.commit()
        return RedirectResponse("/contract-terms", status_code=303)
    except (SQLAlchemyError, ValueError):
        db.rollback()
        return JSONResponse({"error": "Não foi possível atualizar a condição contratual."}, status_code=400)
    finally:
        db.close()


@app.get("/adjustments", response_class=HTMLResponse)
def adjustments_page(request: Request):
    if redirect := require_profiles(request, ADDITIVE_VIEW_PROFILES | FINANCIAL_PROFILES, "Seu perfil não permite acessar reajustes e aditivos."):
        return redirect
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            request,
            "adjustments.html",
            {
                "title": "Reajustes e Aditivos",
                "active_page": "adjustments",
                "user": request.session.get("user"),
                "contracts": db.query(Contract).filter(Contract.status != "inactive").order_by(Contract.contract_name.asc()).all(),
                "adjustments": db.query(ContractAdjustment).join(Contract).order_by(ContractAdjustment.created_at.desc()).all(),
                "additives": db.query(ContractAdditive).join(Contract).order_by(ContractAdditive.created_at.desc()).all(),
            },
        )
    finally:
        db.close()


@app.post("/adjustments")
def adjustment_create(
    request: Request,
    contract_id: int = Form(...),
    reference_year: int = Form(...),
    adjustment_date: str = Form(default=""),
    adjustment_index: str = Form(default=""),
    applied_percentage: str = Form(default=""),
    requested_percentage: str = Form(default=""),
    status: str = Form(default="pending"),
    justification: str = Form(default=""),
    notes: str = Form(default=""),
):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | FINANCIAL_PROFILES, "Seu perfil não permite registrar reajustes."):
        return redirect
    db = SessionLocal()
    try:
        def pct(value: str):
            value = value.replace(",", ".").strip()
            return float(value) if value else None

        adjustment = ContractAdjustment(
            contract_id=contract_id,
            reference_year=reference_year,
            adjustment_date=parse_optional_date(adjustment_date),
            adjustment_index=adjustment_index.strip() or None,
            applied_percentage=pct(applied_percentage),
            requested_percentage=pct(requested_percentage),
            status=status.strip() or "pending",
            justification=justification.strip() or None,
            notes=notes.strip() or None,
        )
        db.add(adjustment)
        db.flush()
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if contract:
            contract.reajust_index = adjustment.adjustment_index or contract.reajust_index
            contract.reajust_percentage = adjustment.applied_percentage or contract.reajust_percentage
            contract.base_date = adjustment.adjustment_date or contract.base_date
        record_audit_log(db, request, "contract_adjustment_created", entity_type="contract_adjustment", entity_id=adjustment.id, details=adjustment.adjustment_index)
        db.commit()
        return RedirectResponse("/adjustments", status_code=303)
    except (SQLAlchemyError, ValueError):
        db.rollback()
        return JSONResponse({"error": "Não foi possível salvar o reajuste."}, status_code=400)
    finally:
        db.close()


@app.post("/adjustments/{adjustment_id:int}/edit")
def adjustment_edit(
    request: Request,
    adjustment_id: int,
    adjustment_date: str = Form(default=""),
    adjustment_index: str = Form(default=""),
    applied_percentage: str = Form(default=""),
    requested_percentage: str = Form(default=""),
    status: str = Form(default="pending"),
    justification: str = Form(default=""),
    notes: str = Form(default=""),
):
    if redirect := require_profiles(request, CONTRACT_WRITE_PROFILES | FINANCIAL_PROFILES, "Seu perfil não permite editar reajustes."):
        return redirect
    db = SessionLocal()
    try:
        def pct(value: str):
            value = value.replace(",", ".").strip()
            return float(value) if value else None

        adjustment = db.query(ContractAdjustment).filter(ContractAdjustment.id == adjustment_id).first()
        if not adjustment:
            return RedirectResponse("/adjustments", status_code=303)
        adjustment.adjustment_date = parse_optional_date(adjustment_date)
        adjustment.adjustment_index = adjustment_index.strip() or None
        adjustment.applied_percentage = pct(applied_percentage)
        adjustment.requested_percentage = pct(requested_percentage)
        adjustment.status = status.strip() or "pending"
        adjustment.justification = justification.strip() or None
        adjustment.notes = notes.strip() or None
        record_audit_log(db, request, "contract_adjustment_updated", entity_type="contract_adjustment", entity_id=adjustment.id, details=adjustment.adjustment_index)
        db.commit()
        return RedirectResponse("/adjustments", status_code=303)
    except (SQLAlchemyError, ValueError):
        db.rollback()
        return JSONResponse({"error": "Não foi possível atualizar o reajuste."}, status_code=400)
    finally:
        db.close()


@app.get("/audit-logs", response_class=HTMLResponse)
def audit_logs_page(request: Request):
    if redirect := require_profiles(request, AUDIT_PROFILES, "Seu perfil não permite acessar auditoria."):
        return redirect
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            request,
            "audit_logs.html",
            {
                "title": "Auditoria",
                "active_page": "audit_logs",
                "user": request.session.get("user"),
                "logs": db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(300).all(),
            },
        )
    finally:
        db.close()


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Seu perfil não permite acessar configurações."):
        return redirect
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"title": "Configurações", "active_page": "settings", "user": request.session.get("user")},
    )


@app.get("/aditivos", response_class=HTMLResponse)
def aditivos(request: Request):
    if redirect := require_profiles(
        request,
        ADDITIVE_VIEW_PROFILES,
        "Seu perfil não permite acessar aditivos.",
    ):
        return redirect

    db = SessionLocal()
    try:
        additive_rows = []
        additives_from_db = (
            db.query(ContractAdditive)
            .join(Contract)
            .order_by(ContractAdditive.created_at.desc())
            .all()
        )
        for additive in additives_from_db:
            contract = additive.contract
            operator_name = contract.operator_name or "Operadora não informada"
            additive_rows.append(
                {
                    "id": additive.id,
                    "additive_number": additive.additive_number,
                    "additive_type": additive.additive_type or "Aditivo",
                    "object_summary": additive.object_summary or additive.original_filename or "-",
                    "signature_date": format_br_date(additive.signature_date),
                    "start_date": format_br_date(additive.start_date),
                    "end_date": format_br_date(additive.end_date),
                    "status_label": "Ativo" if additive.status == "active" else additive.status.title(),
                    "status_class": "active" if additive.status == "active" else "document",
                    "reajust_index": additive.reajust_index,
                    "responsible_name": additive.responsible_name or "-",
                    "responsible_role": additive.responsible_role or "Cadastro do aditivo",
                    "contract_number": contract.contract_number or f"Contrato #{contract.id}",
                    "contract_name": contract.contract_name,
                    "operator_name": operator_name,
                    "operator_initial": operator_name[:1].upper(),
                    "operator_logo_class": operator_logo_class(operator_name),
                    "original_filename": additive.original_filename or "-",
                }
            )

        operator_names = {
            name
            for (name,) in db.query(Contract.operator_name)
            .filter(Contract.operator_name.isnot(None), Contract.operator_name != "")
            .distinct()
            .all()
            if name
        }
        active_count = sum(1 for item in additive_rows if item["status_class"] == "active")
        pending_count = sum(1 for item in additive_rows if "pend" in item["status_label"].lower())
        document_count = sum(1 for item in additive_rows if "document" in item["status_label"].lower())
        type_counts = {}
        for item in additive_rows:
            type_counts[item["additive_type"]] = type_counts.get(item["additive_type"], 0) + 1
        total_types = sum(type_counts.values()) or 1
        additive_type_summary = [
            {"name": name, "count": count, "percent": round((count / total_types) * 100, 1)}
            for name, count in sorted(type_counts.items(), key=lambda row: row[1], reverse=True)
        ]
        additive_filter_options = {
            "contracts": sorted({item["contract_number"] for item in additive_rows}),
            "operators": sorted({item["operator_name"] for item in additive_rows}),
            "types": sorted({item["additive_type"] for item in additive_rows}),
            "statuses": sorted({item["status_label"] for item in additive_rows}),
        }
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "aditivos.html",
        {
            "title": "Aditivos",
            "active_page": "aditivos",
            "user": request.session.get("user"),
            "additive_rows": additive_rows,
            "additive_count": len(additive_rows),
            "operator_names": sorted(operator_names),
            "additive_metrics": {
                "active": active_count,
                "pending": pending_count,
                "documents": document_count,
            },
            "additive_type_summary": additive_type_summary,
            "additive_filter_options": additive_filter_options,
        },
    )


@app.get("/analises-ia", response_class=HTMLResponse)
def analises_ia(request: Request, contract_id: int | None = None):
    if redirect := require_profiles(
        request,
        ANALYSIS_VIEW_PROFILES,
        "Seu perfil não permite acessar análises contratuais.",
    ):
        return redirect

    selected_contract, contracts, analysis = latest_contract_analysis_context(contract_id)
    return templates.TemplateResponse(
        request,
        "analises_ia.html",
        {
            "title": "Análises por IA",
            "active_page": "analises_ia",
            "user": request.session.get("user"),
            "contract": selected_contract,
            "contracts": contracts,
            "analysis": analysis,
            "format_br_date": format_br_date,
        },
    )


@app.post("/analises-ia/upload")
async def analises_ia_upload(request: Request, file: UploadFile = File(...)):
    if redirect := require_profiles(
        request,
        ANALYSIS_WRITE_PROFILES,
        "Seu perfil não permite importar ou reprocessar análises.",
    ):
        return redirect

    from .services.uploads import UnsupportedUploadError, prepare_contract_upload

    try:
        upload = await prepare_contract_upload(
            file,
            SUPPORTED_CONTRACT_EXTENSIONS,
            "Arquivo DOC salvo. Converta para DOCX/PDF para leitura automatica completa.",
        )
    except UnsupportedUploadError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    parsed = upload.parsed
    scoring = upload.scoring
    original_filename = upload.original_filename
    stored_path = upload.stored_path
    file_size = upload.file_size
    raw_text = upload.raw_text
    extraction_status = upload.extraction_status
    extraction_method = upload.extraction_method
    extraction_confidence = upload.extraction_confidence
    warning = upload.warning
    operator_name = parsed.get("operator_name") or Path(original_filename).stem

    db = SessionLocal()
    try:
        operator = db.query(Operator).filter(Operator.name == operator_name).first()
        if not operator:
            operator = Operator(name=operator_name)
            db.add(operator)
            db.flush()

        batch = ImportBatch(
            source_type="ai_upload",
            original_filename=original_filename,
            stored_filepath=str(stored_path),
            status="completed" if extraction_status != "failed" else "completed_with_warnings",
            total_records=1,
            imported_records=1,
            failed_records=0 if extraction_status != "failed" else 1,
            notes=warning,
            created_by=current_username(request),
        )
        db.add(batch)
        db.flush()

        contract = Contract(
            operator_id=operator.id if operator else None,
            import_batch_id=batch.id,
            contract_name=parsed.get("contract_name") or Path(original_filename).stem,
            operator_name=operator_name,
            contract_number=parsed.get("contract_number"),
            contract_object=parsed.get("contract_object"),
            signature_date=parsed.get("signature_date"),
            start_date=parsed.get("start_date"),
            end_date=parsed.get("end_date"),
            auto_renewal=parsed.get("auto_renewal", False),
            renewal_details=parsed.get("renewal_details"),
            termination_notice_days=parsed.get("termination_notice_days"),
            payment_term_days=parsed.get("payment_term_days"),
            payment_trigger=parsed.get("payment_trigger"),
            payment_interest_clause=parsed.get("payment_interest_clause", False),
            payment_penalty_clause=parsed.get("payment_penalty_clause", False),
            billing_deadline_days=parsed.get("billing_deadline_days"),
            billing_deadline_description=parsed.get("billing_deadline_description"),
            allows_glosa_unilateral=parsed.get("allows_glosa_unilateral", False),
            glosa_deadline_days=parsed.get("glosa_deadline_days"),
            glosa_appeal_deadline_days=parsed.get("glosa_appeal_deadline_days"),
            glosa_response_deadline_days=parsed.get("glosa_response_deadline_days"),
            glosa_clause_summary=parsed.get("glosa_clause_summary"),
            reajust_clause_exists=parsed.get("reajust_clause_exists", False),
            reajust_frequency=parsed.get("reajust_frequency"),
            reajust_index=parsed.get("reajust_index"),
            reajust_clause_summary=parsed.get("reajust_clause_summary"),
            medical_fee_table=parsed.get("medical_fee_table"),
            medical_fee_table_version=parsed.get("medical_fee_table_version"),
            daily_rate_table=parsed.get("daily_rate_table"),
            materials_table=parsed.get("materials_table"),
            materials_table_version=parsed.get("materials_table_version"),
            medicines_table=parsed.get("medicines_table"),
            medicines_table_version=parsed.get("medicines_table_version"),
            raw_text=raw_text,
            score_total=scoring["score_total"],
            classification=scoring["classification"],
            risk_level=scoring["risk_level"],
            strong_points=scoring["strong_points"],
            weak_points=scoring["weak_points"],
            alerts=scoring["alerts"],
            extraction_method=extraction_method,
            extraction_confidence=extraction_confidence,
            original_filename=original_filename,
            stored_filepath=str(stored_path),
        )
        db.add(contract)
        db.flush()

        contract_file = ContractFile(
            contract_id=contract.id,
            import_batch_id=batch.id,
            file_type="contract",
            original_filename=original_filename,
            stored_filepath=str(stored_path),
            mime_type=file.content_type,
            file_size_bytes=file_size,
            extracted_text=raw_text,
            extraction_status=extraction_status,
            extraction_method=extraction_method,
            processing_status="processed" if extraction_status == "completed" else "error",
            processed_at=datetime.utcnow() if extraction_status == "completed" else None,
            notes=warning,
            error_message=warning if extraction_status == "failed" else None,
            uploaded_by=current_username(request),
        )
        db.add(contract_file)
        db.flush()
        from .services.ai_analysis import persist_contract_analysis

        persist_contract_analysis(
            db,
            contract,
            file_id=contract_file.id,
            created_by=current_username(request),
        )
        record_auth_event(
            db,
            "contract_uploaded",
            username=current_username(request),
            request=request,
            notes=f"Contrato enviado para análise IA: {original_filename}. Contrato #{contract.id}.",
        )
        record_auth_event(
            db,
            "contract_analyzed",
            username=current_username(request),
            request=request,
            notes=f"Análise IA gerada para contrato #{contract.id}.",
        )
        record_audit_log(db, request, "contract_created", entity_type="contract", entity_id=contract.id, details=contract.contract_name)
        record_audit_log(db, request, "document_uploaded", entity_type="contract_file", entity_id=contract_file.id, details=original_filename)
        db.commit()

        return JSONResponse(
            {
                "id": contract.id,
                "filename": original_filename,
                "contract_name": contract.contract_name,
                "operator_name": contract.operator_name,
                "analysis_url": f"/analises-ia?contract_id={contract.id}",
                "warning": warning,
            }
        )
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse(
            {"error": "Não foi possível gravar o contrato para análise."},
            status_code=500,
        )
    finally:
        db.close()



@app.post("/analises-ia/run")
def analises_ia_run(request: Request, contract_id: int | None = None):
    if redirect := require_profiles(
        request,
        ANALYSIS_WRITE_PROFILES,
        "Seu perfil não permite executar análises contratuais.",
    ):
        return redirect

    db = SessionLocal()
    try:
        query = db.query(Contract)
        contract = query.filter(Contract.id == contract_id).first() if contract_id else query.order_by(Contract.created_at.desc()).first()
        if not contract:
            return JSONResponse({"error": "Nenhum contrato importado para analisar."}, status_code=404)
        from .services.ai_analysis import build_contract_analysis, persist_contract_analysis

        persisted = persist_contract_analysis(db, contract, created_by=current_username(request))
        analysis = build_contract_analysis(contract)
        record_auth_event(
            db,
            "contract_analyzed",
            username=current_username(request),
            request=request,
            notes=f"Análise reprocessada para contrato #{contract.id}.",
        )
        db.commit()
        db.refresh(persisted)
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse({"error": "Não foi possível persistir a análise."}, status_code=500)
    finally:
        db.close()

    return JSONResponse(
        {
            "score": analysis["score"],
            "falhas": analysis["failures_count"],
            "clausulas_criticas": analysis["critical_count"],
            "oportunidades": analysis["opportunities_count"],
        }
    )


@app.get("/comparacoes", response_class=HTMLResponse)
def comparacoes(request: Request):
    if redirect := require_profiles(
        request,
        FINANCIAL_PROFILES,
        "Seu perfil não permite acessar comparações financeiras.",
    ):
        return redirect

    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            request,
            "comparacoes.html",
            {
                "title": "Comparações",
                "active_page": "comparacoes",
                "user": request.session.get("user"),
                "contracts": db.query(Contract).order_by(Contract.created_at.desc()).all(),
                "comparisons": db.query(ContractComparison).order_by(ContractComparison.created_at.desc()).all(),
            },
        )
    finally:
        db.close()


@app.get("/comparisons")
def comparisons_alias(request: Request):
    return RedirectResponse("/comparacoes", status_code=303)


@app.post("/comparacoes")
async def comparison_create(request: Request):
    if redirect := require_profiles(
        request,
        FINANCIAL_PROFILES,
        "Seu perfil não permite criar comparações financeiras.",
    ):
        return redirect

    from .services.comparison import compare_contracts

    form = await request.form()
    try:
        contract_ids = list(dict.fromkeys(int(value) for value in form.getlist("contract_ids")))
    except ValueError:
        return JSONResponse({"error": "Seleção de contratos inválida."}, status_code=400)
    if len(contract_ids) < 2:
        return JSONResponse({"error": "Selecione pelo menos dois contratos."}, status_code=400)

    db = SessionLocal()
    try:
        contracts = db.query(Contract).filter(Contract.id.in_(contract_ids)).all()
        by_id = {contract.id: contract for contract in contracts}
        ordered_contracts = [by_id[contract_id] for contract_id in contract_ids if contract_id in by_id]
        if len(ordered_contracts) != len(contract_ids):
            return JSONResponse({"error": "Um dos contratos selecionados não existe."}, status_code=404)

        rows = compare_contracts(ordered_contracts)
        best = max(ordered_contracts, key=lambda item: item.score_total or 0)
        comparison = ContractComparison(
            title=str(form.get("title", "")).strip() or f"Comparação {datetime.now():%d/%m/%Y %H:%M}",
            status="completed",
            criteria_count=len(rows),
            best_contract_id=best.id,
            summary=f"Melhor score: {best.contract_name} ({best.score_total or 0:.1f}).",
            result_payload={"rows": rows, "contract_ids": contract_ids},
            created_by=current_username(request),
        )
        db.add(comparison)
        db.flush()
        for position, contract in enumerate(ordered_contracts, start=1):
            db.add(
                ContractComparisonItem(
                    comparison_id=comparison.id,
                    contract_id=contract.id,
                    position=position,
                    score=contract.score_total,
                    metrics_payload={"contract_name": contract.contract_name, "operator_name": contract.operator_name},
                )
            )
        record_auth_event(db, "contract_comparison_created", username=current_username(request), request=request, notes=f"Comparação #{comparison.id} criada com {len(ordered_contracts)} contratos.")
        db.commit()
        db.refresh(comparison)
        return RedirectResponse(f"/comparacoes?created={comparison.id}", status_code=303)
    except SQLAlchemyError as exc:
        db.rollback()
        return JSONResponse({"error": "Não foi possível salvar a comparação."}, status_code=500)
    finally:
        db.close()
