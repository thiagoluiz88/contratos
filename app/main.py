from pathlib import Path
from datetime import date, datetime, time
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import or_
from starlette.middleware.sessions import SessionMiddleware

from .config import (
    BASE_DIR,
    SESSION_MAX_AGE_SECONDS,
    SESSION_HTTPS_ONLY,
    SESSION_SECRET,
    STATIC_DIR,
    TEMPLATES_DIR,
    UPLOAD_DIR,
)
from .security import CSRFMiddleware
from .database import SessionLocal
from .models import (
    AccessProfile,
    AuthAuditEvent,
    Contract,
    ContractAdditive,
    ContractComparison,
    ContractComparisonItem,
    ContractEvent,
    ContractFile,
    ImportBatch,
    Operator,
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
        "operator_name",
        "contract_number",
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
        "reajust_clause_summary",
        "medical_fee_table",
        "medical_fee_table_version",
        "daily_rate_table",
        "materials_table",
        "materials_table_version",
        "medicines_table",
        "medicines_table_version",
    )
    data = {field: getattr(contract, field) for field in fields}
    for field in ("signature_date", "start_date", "end_date"):
        data[field] = data[field].isoformat() if data[field] else ""
    return data


def contract_status(contract: Contract) -> tuple[str, str]:
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
    return {"status": "ok"}


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
        profile = get_access_profile(db, DEFAULT_REGISTER_PROFILE) or get_access_profile(db, "Administrator")
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
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Não é permitido remover o último Administrator ativo.", status_code=400)

        record_auth_event(db, "user_updated", user=user_record, username=user_record.username, request=request, notes=f"Atualizado por {current_username(request)}.")
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
            return forbidden_response(request, "Não é permitido desativar o último Administrator ativo.")
        user_record.is_active = False
        record_auth_event(db, "user_deactivated", user=user_record, username=user_record.username, request=request, notes=f"Desativado por {current_username(request)}.")
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
            return forbidden_response(request, "Perfil Administrator não encontrado ou inativo.")
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
            notes=f"Promovido a Administrator por {current_username(request)}.",
        )
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
            return render_profile_form(request, profile=profile, error="Não é permitido desativar o perfil Administrator.", status_code=400)
        record_auth_event(db, "access_profile_updated", username=current_username(request), request=request, notes=f"Perfil atualizado: {profile.name}.")
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
            return forbidden_response(request, "Não é permitido desativar o perfil Administrator.")
        profile.is_active = False
        record_auth_event(db, "access_profile_deactivated", username=current_username(request), request=request, notes=f"Perfil desativado: {profile.name}.")
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
        expired = 0
        no_adjustment = 0
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
            "expired": expired,
            "no_adjustment": no_adjustment,
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
            "contract_name", "operator_name", "contract_number", "contract_object", "renewal_details",
            "payment_trigger", "billing_deadline_description", "glosa_clause_summary", "reajust_frequency",
            "reajust_index", "reajust_clause_summary", "medical_fee_table", "medical_fee_table_version",
            "daily_rate_table", "materials_table", "materials_table_version", "medicines_table",
            "medicines_table_version",
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
        for field in integer_fields:
            setattr(contract, field, parse_optional_int(form.get(field)))
        for field in ("signature_date", "start_date", "end_date"):
            setattr(contract, field, parse_optional_date(form.get(field)))
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
        db.delete(contract)
        record_auth_event(db, "contract_deleted", username=current_username(request), request=request, notes=f"Contrato #{contract_id} excluído: {name}.")
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
                uploaded_by=current_username(request),
            )
            db.add(contract_file)
            record_auth_event(
                db,
                "contract_uploaded",
                username=current_username(request),
                request=request,
                notes=f"Aditivo enviado: {original_filename}. Contrato base #{parent_contract.id}.",
            )
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
