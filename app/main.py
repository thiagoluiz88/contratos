from pathlib import Path
from datetime import date, datetime, time

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import or_
from starlette.middleware.sessions import SessionMiddleware

from .config import (
    SESSION_HTTPS_ONLY,
    SESSION_SECRET,
    STATIC_DIR,
    TEMPLATES_DIR,
    UPLOAD_DIR,
)
from .database import SessionLocal, init_db
from .models import AccessProfile, AuthAuditEvent, Contract, ContractAdditive, ContractFile, ImportBatch, Operator, User
from .services.auth import (
    ADMIN_PROFILES,
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
from .services.ai_analysis import build_contract_analysis, persist_contract_analysis
from .services.uploads import UnsupportedUploadError, append_warning, prepare_contract_upload


app = FastAPI(title="Contracts Intelligence")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.globals["has_profile"] = has_profile
templates.env.globals["ADMIN_PROFILES"] = ADMIN_PROFILES
templates.env.globals["AUDIT_PROFILES"] = AUDIT_PROFILES
templates.env.globals["CONTRACT_WRITE_PROFILES"] = CONTRACT_WRITE_PROFILES
templates.env.globals["FINANCIAL_PROFILES"] = FINANCIAL_PROFILES
SUPPORTED_CONTRACT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
DEFAULT_OPERATOR_NAMES = [
    "Amil",
    "Bradesco SaÃƒÂºde",
    "Hapvida",
    "SulAmÃƒÂ©rica",
    "Unimed",
]


def format_br_date(value):
    return value.strftime("%d/%m/%Y") if value else "-"


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
        init_db()
        db = SessionLocal()
        try:
            ensure_initial_admin(db)
            upgrade_legacy_password_hashes(db)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            print(f"Aviso: nao foi possivel garantir usuario administrador inicial: {exc}")
        finally:
            db.close()
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    except OperationalError as exc:
        print(f"Aviso: nÃƒÂ£o foi possÃƒÂ­vel inicializar o banco automaticamente: {exc}")


@app.get("/health")
def health():
    return {"status": "ok"}


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("user"))


def require_login(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=303)
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
            "title": "Resetar senha" if reset_password else ("Editar usuario" if user_record else "Novo usuario"),
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
            request.session["user"] = user_session_payload(user)
            request.session["remember"] = bool(remember)
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
            notes="Usuario inativo, perfil inativo ou credenciais invalidas.",
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
            "error": "Usuario ou senha invalidos.",
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
            {**context, "error": "Este usuario ou email ja existe."},
            status_code=400,
        )

    if "@" not in email or "." not in email:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "Informe um email valido."},
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
            {**context, "error": "As senhas nao conferem."},
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
        record_auth_event(db, "login", user=user, request=request, success=True, notes="Login automatico apos cadastro.")
        db.commit()
        return RedirectResponse("/dashboard", status_code=303)
    except SQLAlchemyError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": f"Nao foi possivel criar o usuario: {exc}"},
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
            {**context, "error": "As senhas nao conferem."},
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
                notes="Senha atual invalida.",
            )
            db.commit()
            return templates.TemplateResponse(
                request,
                "change_password.html",
                {**context, "error": "Senha atual invalida."},
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
            {**context, "error": f"Nao foi possivel alterar a senha: {exc}"},
            status_code=500,
        )
    finally:
        db.close()


@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem gerenciar usuarios."):
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
                "title": "Usuarios",
                "active_page": "users",
                "user": request.session.get("user"),
                "users": user_rows,
            },
        )
    finally:
        db.close()


@app.get("/users/new", response_class=HTMLResponse)
def user_new_page(request: Request):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem criar usuarios."):
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
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem criar usuarios."):
        return redirect

    db = SessionLocal()
    try:
        profiles = db.query(AccessProfile).order_by(AccessProfile.name).all()
        profile = db.query(AccessProfile).filter(AccessProfile.id == access_profile_id).first()
        if not profile:
            return render_user_form(request, profiles=profiles, error="Perfil obrigatorio.", status_code=400)
        if db.query(User).filter(or_(User.username == username, User.email == email)).first():
            return render_user_form(request, profiles=profiles, error="Usuario ou email ja existe.", status_code=400)
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
        return render_user_form(request, profiles=db.query(AccessProfile).order_by(AccessProfile.name).all(), error=f"Nao foi possivel criar usuario: {exc}", status_code=500)
    finally:
        db.close()


@app.get("/users/{user_id}/edit", response_class=HTMLResponse)
def user_edit_page(request: Request, user_id: int):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem editar usuarios."):
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
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem editar usuarios."):
        return redirect

    db = SessionLocal()
    try:
        user_record = db.query(User).filter(User.id == user_id).first()
        profiles = db.query(AccessProfile).order_by(AccessProfile.name).all()
        if not user_record:
            return RedirectResponse("/users", status_code=303)
        if not db.query(AccessProfile).filter(AccessProfile.id == access_profile_id).first():
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Perfil obrigatorio.", status_code=400)
        duplicate = db.query(User).filter(User.email == email, User.id != user_id).first()
        if duplicate:
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Email ja cadastrado.", status_code=400)
        if user_record.id == request.session.get("user", {}).get("id") and not is_active:
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Voce nao pode desativar o proprio usuario.", status_code=400)

        old_profile_id = user_record.access_profile_id
        user_record.full_name = full_name.strip() or None
        user_record.email = email.strip()
        user_record.access_profile_id = access_profile_id
        user_record.is_active = bool(is_active)
        if old_profile_id != access_profile_id and active_admin_count(db) == 0:
            db.rollback()
            return render_user_form(request, user_record=user_record, profiles=profiles, error="Nao e permitido remover o ultimo Administrator ativo.", status_code=400)

        record_auth_event(db, "user_updated", user=user_record, username=user_record.username, request=request, notes=f"Atualizado por {current_username(request)}.")
        db.commit()
        return RedirectResponse("/users", status_code=303)
    except SQLAlchemyError as exc:
        db.rollback()
        return render_user_form(request, error=f"Nao foi possivel editar usuario: {exc}", status_code=500)
    finally:
        db.close()


@app.post("/users/{user_id}/deactivate")
def user_deactivate(request: Request, user_id: int):
    if redirect := require_profiles(request, ADMIN_PROFILES, "Somente administradores podem desativar usuarios."):
        return redirect

    db = SessionLocal()
    try:
        user_record = db.query(User).filter(User.id == user_id).first()
        if not user_record:
            return RedirectResponse("/users", status_code=303)
        if user_record.id == request.session.get("user", {}).get("id"):
            return forbidden_response(request, "Voce nao pode desativar o proprio usuario.")
        if user_record.access_profile and user_record.access_profile.name == PROFILE_ADMIN and active_admin_count(db) <= 1:
            return forbidden_response(request, "Nao e permitido desativar o ultimo Administrator ativo.")
        user_record.is_active = False
        record_auth_event(db, "user_deactivated", user=user_record, username=user_record.username, request=request, notes=f"Desativado por {current_username(request)}.")
        db.commit()
        return RedirectResponse("/users", status_code=303)
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
            return render_user_form(request, user_record=user_record, reset_password=True, error="As senhas nao conferem.", status_code=400)
        user_record.password_hash = hash_password(password)
        record_auth_event(db, "password_reset", user=user_record, username=user_record.username, request=request, notes=f"Reset por {current_username(request)}.")
        db.commit()
        return RedirectResponse("/users", status_code=303)
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
                "title": "Perfis de acesso",
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
            return render_profile_form(request, error="Perfil ja existe.", status_code=400)
        profile = AccessProfile(name=name.strip(), description=description.strip() or None, is_active=bool(is_active))
        db.add(profile)
        db.flush()
        record_auth_event(db, "access_profile_created", username=current_username(request), request=request, notes=f"Perfil criado: {profile.name}.")
        db.commit()
        return RedirectResponse("/access-profiles", status_code=303)
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
            return render_profile_form(request, profile=profile, error="Perfil ja existe.", status_code=400)
        profile.name = name.strip()
        profile.description = description.strip() or None
        profile.is_active = bool(is_active)
        if profile.name == PROFILE_ADMIN and not profile.is_active and active_admin_count(db) > 0:
            db.rollback()
            return render_profile_form(request, profile=profile, error="Nao e permitido desativar o perfil Administrator.", status_code=400)
        record_auth_event(db, "access_profile_updated", username=current_username(request), request=request, notes=f"Perfil atualizado: {profile.name}.")
        db.commit()
        return RedirectResponse("/access-profiles", status_code=303)
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
            return forbidden_response(request, "Nao e permitido desativar o perfil Administrator.")
        profile.is_active = False
        record_auth_event(db, "access_profile_deactivated", username=current_username(request), request=request, notes=f"Perfil desativado: {profile.name}.")
        db.commit()
        return RedirectResponse("/access-profiles", status_code=303)
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
        "Seu perfil nao permite acessar a auditoria.",
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
            "Sem vigencia": 0,
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
            operator_name = contract.operator_name or "Operadora nao informada"
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
                or "Nao identificada"
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
                status_counts["Sem vigencia"] += 1

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
            operator_name = contract.operator_name or "Operadora nÃƒÂ£o informada"
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
                    "reajust_index": contract.adjustment_type or contract.reajust_index or "NÃƒÂ£o identificado",
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
        operator_names.update(DEFAULT_OPERATOR_NAMES)
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
        },
    )


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
                    "Sem ÃƒÂ­ndice definido",
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
        "Seu perfil nao permite editar dados contratuais.",
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
        db.commit()
        return RedirectResponse(f"/contracts/{contract_id}/additional?saved=1", status_code=303)
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
        "Seu perfil nao permite importar ou editar contratos.",
    ):
        return redirect

    selected_operator_name = (operator_name or "").strip()
    is_additive = import_mode == "additive"
    if not selected_operator_name:
        return JSONResponse(
            {
                "error": (
                    "Selecione o convenio do aditivo antes de importar."
                    if is_additive
                    else "Selecione o convenio antes de importar o contrato."
                )
            },
            status_code=400,
        )

    try:
        upload = await prepare_contract_upload(
            file,
            SUPPORTED_CONTRACT_EXTENSIONS,
            "Arquivo DOC salvo. Extracao automatica de DOC legado nao esta disponivel; converta para DOCX/PDF para analise completa.",
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
                            "Nao ha contrato cadastrado para este convenio. "
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
            notes=f"Analise gerada para contrato #{contract.id}.",
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
                "error": "Nao foi possivel gravar o contrato no banco de dados.",
                "detail": str(exc),
            },
            status_code=500,
        )
    except Exception as exc:
        db.rollback()
        return JSONResponse(
            {
                "error": "Nao foi possivel importar o contrato.",
                "detail": str(exc),
            },
            status_code=500,
        )
    finally:
        db.close()


@app.get("/aditivos", response_class=HTMLResponse)
def aditivos(request: Request):
    if redirect := require_login(request):
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
            operator_name = contract.operator_name or "Operadora nao informada"
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
        operator_names.update(DEFAULT_OPERATOR_NAMES)
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
        },
    )


@app.get("/analises-ia", response_class=HTMLResponse)
def analises_ia(request: Request, contract_id: int | None = None):
    if redirect := require_profiles(
        request,
        AUDIT_PROFILES,
        "Seu perfil nao permite acessar analises e auditoria.",
    ):
        return redirect

    selected_contract, contracts, analysis = latest_contract_analysis_context(contract_id)
    return templates.TemplateResponse(
        request,
        "analises_ia.html",
        {
            "title": "AnÃƒÂ¡lises por IA",
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
        AUDIT_PROFILES,
        "Seu perfil nao permite executar analises e auditoria.",
    ):
        return redirect

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
            notes=f"Contrato enviado para analise IA: {original_filename}. Contrato #{contract.id}.",
        )
        record_auth_event(
            db,
            "contract_analyzed",
            username=current_username(request),
            request=request,
            notes=f"Analise IA gerada para contrato #{contract.id}.",
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
            {"error": "NÃƒÂ£o foi possÃƒÂ­vel gravar o contrato para anÃƒÂ¡lise.", "detail": str(exc)},
            status_code=500,
        )
    finally:
        db.close()



@app.post("/analises-ia/run")
def analises_ia_run(request: Request, contract_id: int | None = None):
    if redirect := require_profiles(
        request,
        AUDIT_PROFILES,
        "Seu perfil nao permite executar analises e auditoria.",
    ):
        return redirect

    contract, _, analysis = latest_contract_analysis_context(contract_id)
    if not contract or not analysis:
        return JSONResponse({"error": "Nenhum contrato importado para analisar."}, status_code=404)

    db = SessionLocal()
    try:
        record_auth_event(
            db,
            "contract_analyzed",
            username=current_username(request),
            request=request,
            notes=f"Analise reprocessada para contrato #{contract.id}.",
        )
        db.commit()
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
        "Seu perfil nao permite acessar comparacoes financeiras.",
    ):
        return redirect

    return templates.TemplateResponse(
        request,
        "comparacoes.html",
        {
            "title": "ComparaÃƒÂ§ÃƒÂµes",
            "active_page": "comparacoes",
            "user": request.session.get("user"),
        },
    )
