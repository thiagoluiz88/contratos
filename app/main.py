from pathlib import Path
from datetime import date

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from .config import (
    APP_PASSWORD,
    APP_USER,
    APP_USER_EMAIL,
    APP_USER_NAME,
    APP_USER_ROLE,
    SESSION_HTTPS_ONLY,
    SESSION_SECRET,
    STATIC_DIR,
    TEMPLATES_DIR,
    UPLOAD_DIR,
)
from .database import SessionLocal, init_db
from .models import Contract, ContractAdditive, ContractFile, ImportBatch, Operator
from .services.ai_analysis import build_contract_analysis, persist_contract_analysis
from .services.uploads import UnsupportedUploadError, append_warning, prepare_contract_upload


USERS = {
    APP_USER: {
        "password": APP_PASSWORD,
        "name": APP_USER_NAME,
        "role": APP_USER_ROLE,
        "email": APP_USER_EMAIL,
    }
}


app = FastAPI(title="Contracts Intelligence")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
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
    user = USERS.get(username)
    if user and user["password"] == password:
        request.session["user"] = {
            "username": username,
            "name": user["name"],
            "role": user["role"],
        }
        request.session["remember"] = bool(remember)
        return RedirectResponse("/dashboard", status_code=303)

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

    if username in USERS:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "Este usuario ja existe."},
            status_code=400,
        )

    if "@" not in email or "." not in email:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "Informe um email valido."},
            status_code=400,
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "A senha deve ter pelo menos 6 caracteres."},
            status_code=400,
        )

    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "login.html",
            {**context, "error": "As senhas nao conferem."},
            status_code=400,
        )

    USERS[username] = {
        "password": password,
        "name": full_name,
        "role": "Administrador",
        "email": email,
    }
    request.session["user"] = {
        "username": username,
        "name": full_name,
        "role": "Administrador",
    }
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
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
    if redirect := require_login(request):
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
    if redirect := require_login(request):
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
                created_by=request.session.get("user", {}).get("username"),
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
                uploaded_by=request.session.get("user", {}).get("username"),
            )
            db.add(contract_file)
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
            created_by=request.session.get("user", {}).get("username"),
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
            uploaded_by=request.session.get("user", {}).get("username"),
        )
        db.add(contract_file)
        db.flush()
        persist_contract_analysis(
            db,
            contract,
            file_id=contract_file.id,
            created_by=request.session.get("user", {}).get("username"),
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
    if redirect := require_login(request):
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
    if redirect := require_login(request):
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
            created_by=request.session.get("user", {}).get("username"),
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
            uploaded_by=request.session.get("user", {}).get("username"),
        )
        db.add(contract_file)
        db.flush()
        persist_contract_analysis(
            db,
            contract,
            file_id=contract_file.id,
            created_by=request.session.get("user", {}).get("username"),
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
    if redirect := require_login(request):
        return redirect

    contract, _, analysis = latest_contract_analysis_context(contract_id)
    if not contract or not analysis:
        return JSONResponse({"error": "Nenhum contrato importado para analisar."}, status_code=404)

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
    if redirect := require_login(request):
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
