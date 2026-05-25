from pathlib import Path
from uuid import uuid4
from datetime import date

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from .database import SessionLocal, init_db
from .models import Contract, ContractFile, ImportBatch, Operator
from .services.contract_parser import parse_contract
from .services.file_text import TextExtractionError, extract_text_from_file
from .services.ai_analysis import build_contract_analysis, persist_contract_analysis
from .services.scoring import score_contract


APP_USER = "admin"
APP_PASSWORD = "admin123"
SESSION_SECRET = "contracts-intelligence-session-secret"
USERS = {
    APP_USER: {
        "password": APP_PASSWORD,
        "name": "Allan Martins",
        "role": "Administrador",
        "email": "admin@contracts.local",
    }
}


app = FastAPI(title="Contracts Intelligence")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")
UPLOAD_DIR = Path("uploads/contracts")
SUPPORTED_CONTRACT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}
DEFAULT_OPERATOR_NAMES = [
    "Amil",
    "Bradesco Saúde",
    "Hapvida",
    "SulAmérica",
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
    except OperationalError as exc:
        print(f"Aviso: não foi possível inicializar o banco automaticamente: {exc}")


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

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "title": "Painel Executivo",
            "active_page": "dashboard",
            "user": request.session.get("user"),
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
):
    if redirect := require_login(request):
        return redirect

    selected_operator_name = (operator_name or "").strip()
    if not selected_operator_name:
        return JSONResponse(
            {"error": "Selecione o convênio antes de importar o contrato."},
            status_code=400,
        )

    original_filename = file.filename or "contrato"
    extension = Path(original_filename).suffix.lower()
    if extension not in SUPPORTED_CONTRACT_EXTENSIONS:
        return JSONResponse(
            {
                "error": "Formato não suportado. Envie PDF, DOCX, DOC, TXT ou MD.",
            },
            status_code=400,
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    stored_path = UPLOAD_DIR / stored_name
    file_size = 0

    with stored_path.open("wb") as destination:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)
            destination.write(chunk)

    extraction_status = "completed"
    extraction_method = None
    extraction_confidence = None
    raw_text = None
    warning = None

    if extension == ".doc":
        extraction_status = "pending"
        warning = "Arquivo DOC salvo. Extração automática de DOC legado não está disponível; converta para DOCX/PDF para análise completa."
    else:
        try:
            extraction = extract_text_from_file(stored_path)
            raw_text = extraction.get("text")
            extraction_method = extraction.get("method")
            extraction_confidence = extraction.get("confidence")
        except TextExtractionError as exc:
            extraction_status = "failed"
            warning = str(exc)

    parsed = parse_contract(raw_text or "", original_filename) if raw_text else {
        "contract_name": Path(original_filename).stem,
        "operator_name": None,
        "contract_number": None,
        "raw_text": raw_text,
    }
    scoring = score_contract(parsed)

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
            warning = (
                f"{warning} Operadora detectada no arquivo: {parsed_operator_name}."
                if warning
                else f"Operadora detectada no arquivo: {parsed_operator_name}."
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

    return templates.TemplateResponse(
        request,
        "aditivos.html",
        {
            "title": "Aditivos",
            "active_page": "aditivos",
            "user": request.session.get("user"),
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
    if redirect := require_login(request):
        return redirect

    original_filename = file.filename or "contrato"
    extension = Path(original_filename).suffix.lower()
    if extension not in SUPPORTED_CONTRACT_EXTENSIONS:
        return JSONResponse(
            {"error": "Formato não suportado. Envie PDF, DOCX, DOC, TXT ou MD."},
            status_code=400,
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    stored_path = UPLOAD_DIR / stored_name
    file_size = 0

    with stored_path.open("wb") as destination:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)
            destination.write(chunk)

    extraction_status = "completed"
    extraction_method = None
    extraction_confidence = None
    raw_text = None
    warning = None

    if extension == ".doc":
        extraction_status = "pending"
        warning = "Arquivo DOC salvo. Converta para DOCX/PDF para leitura automática completa."
    else:
        try:
            extraction = extract_text_from_file(stored_path)
            raw_text = extraction.get("text")
            extraction_method = extraction.get("method")
            extraction_confidence = extraction.get("confidence")
        except TextExtractionError as exc:
            extraction_status = "failed"
            warning = str(exc)

    parsed = parse_contract(raw_text or "", original_filename) if raw_text else {
        "contract_name": Path(original_filename).stem,
        "operator_name": None,
        "contract_number": None,
        "raw_text": raw_text,
    }
    scoring = score_contract(parsed)
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
            {"error": "Não foi possível gravar o contrato para análise.", "detail": str(exc)},
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
            "title": "Comparações",
            "active_page": "comparacoes",
            "user": request.session.get("user"),
        },
    )
