from __future__ import annotations

import csv
import hashlib
import io
import os
import shutil
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from .database import Base, engine, get_db
from .models import Contract, ContractEvent
from .services.comparison import compare_contracts
from .services.contract_parser import parse_contract
from .services.file_text import TextExtractionError, extract_text_from_file
from .services.scoring import ALERT_THRESHOLDS, score_contract

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
APP_UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Sistema de Análise Contratual Hospitalar")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("APP_SECRET", "contract-system-secret"))
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
Base.metadata.create_all(bind=engine)

ADMIN_USER = os.getenv("APP_USER", "admin")
ADMIN_PASSWORD_HASH = hashlib.sha256(os.getenv("APP_PASSWORD", "admin123").encode()).hexdigest()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


# ---------- Helpers ----------
def parse_date_input(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_int_input(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_bool_input(value: str | None) -> bool:
    return str(value).lower() in {"1", "true", "on", "sim", "yes"}


def require_auth(request: Request) -> str | None:
    return request.session.get("user")


def maybe_redirect_auth(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=303)
    return None


def days_until(end_date: date | None) -> int | None:
    if not end_date:
        return None
    return (end_date - date.today()).days


RISK_ORDER = {"baixo": 1, "moderado": 2, "alto": 3, "muito alto": 4}


def normalize_text_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


def contract_to_form_data(contract: Contract) -> dict:
    return {
        "contract_name": contract.contract_name or "",
        "operator_name": contract.operator_name or "",
        "contract_number": contract.contract_number or "",
        "contract_object": contract.contract_object or "",
        "signature_date": contract.signature_date.isoformat() if contract.signature_date else "",
        "start_date": contract.start_date.isoformat() if contract.start_date else "",
        "end_date": contract.end_date.isoformat() if contract.end_date else "",
        "auto_renewal": contract.auto_renewal,
        "renewal_details": contract.renewal_details or "",
        "termination_notice_days": contract.termination_notice_days or "",
        "payment_term_days": contract.payment_term_days or "",
        "payment_trigger": contract.payment_trigger or "",
        "payment_interest_clause": contract.payment_interest_clause,
        "payment_penalty_clause": contract.payment_penalty_clause,
        "billing_deadline_days": contract.billing_deadline_days or "",
        "billing_deadline_description": contract.billing_deadline_description or "",
        "allows_glosa_unilateral": contract.allows_glosa_unilateral,
        "glosa_deadline_days": contract.glosa_deadline_days or "",
        "glosa_appeal_deadline_days": contract.glosa_appeal_deadline_days or "",
        "glosa_response_deadline_days": contract.glosa_response_deadline_days or "",
        "glosa_clause_summary": contract.glosa_clause_summary or "",
        "reajust_clause_exists": contract.reajust_clause_exists,
        "reajust_frequency": contract.reajust_frequency or "",
        "reajust_index": contract.reajust_index or "",
        "reajust_clause_summary": contract.reajust_clause_summary or "",
        "medical_fee_table": contract.medical_fee_table or "",
        "medical_fee_table_version": contract.medical_fee_table_version or "",
        "daily_rate_table": contract.daily_rate_table or "",
        "materials_table": contract.materials_table or "",
        "materials_table_version": contract.materials_table_version or "",
        "medicines_table": contract.medicines_table or "",
        "medicines_table_version": contract.medicines_table_version or "",
    }


def apply_contract_form(contract: Contract, form: dict[str, str | bool]) -> dict:
    data = {
        "contract_name": form.get("contract_name") or contract.contract_name,
        "operator_name": form.get("operator_name") or None,
        "contract_number": form.get("contract_number") or None,
        "contract_object": form.get("contract_object") or None,
        "signature_date": parse_date_input(str(form.get("signature_date") or "")),
        "start_date": parse_date_input(str(form.get("start_date") or "")),
        "end_date": parse_date_input(str(form.get("end_date") or "")),
        "auto_renewal": bool(form.get("auto_renewal")),
        "renewal_details": form.get("renewal_details") or None,
        "termination_notice_days": parse_int_input(str(form.get("termination_notice_days") or "")),
        "payment_term_days": parse_int_input(str(form.get("payment_term_days") or "")),
        "payment_trigger": form.get("payment_trigger") or None,
        "payment_interest_clause": bool(form.get("payment_interest_clause")),
        "payment_penalty_clause": bool(form.get("payment_penalty_clause")),
        "billing_deadline_days": parse_int_input(str(form.get("billing_deadline_days") or "")),
        "billing_deadline_description": form.get("billing_deadline_description") or None,
        "allows_glosa_unilateral": bool(form.get("allows_glosa_unilateral")),
        "glosa_deadline_days": parse_int_input(str(form.get("glosa_deadline_days") or "")),
        "glosa_appeal_deadline_days": parse_int_input(str(form.get("glosa_appeal_deadline_days") or "")),
        "glosa_response_deadline_days": parse_int_input(str(form.get("glosa_response_deadline_days") or "")),
        "glosa_clause_summary": form.get("glosa_clause_summary") or None,
        "reajust_clause_exists": bool(form.get("reajust_clause_exists")),
        "reajust_frequency": form.get("reajust_frequency") or None,
        "reajust_index": form.get("reajust_index") or None,
        "reajust_clause_summary": form.get("reajust_clause_summary") or None,
        "medical_fee_table": form.get("medical_fee_table") or None,
        "medical_fee_table_version": form.get("medical_fee_table_version") or None,
        "daily_rate_table": form.get("daily_rate_table") or None,
        "materials_table": form.get("materials_table") or None,
        "materials_table_version": form.get("materials_table_version") or None,
        "medicines_table": form.get("medicines_table") or None,
        "medicines_table_version": form.get("medicines_table_version") or None,
        "raw_text": contract.raw_text,
    }
    return data


def serialize_contract(contract: Contract) -> dict:
    return {
        "id": contract.id,
        "contract_name": contract.contract_name,
        "operator_name": contract.operator_name,
        "contract_number": contract.contract_number,
        "start_date": contract.start_date.isoformat() if contract.start_date else None,
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "days_until_end": days_until(contract.end_date),
        "payment_term_days": contract.payment_term_days,
        "billing_deadline_days": contract.billing_deadline_days,
        "score_total": contract.score_total,
        "classification": contract.classification,
        "risk_level": contract.risk_level,
        "medical_fee_table": contract.medical_fee_table,
        "medical_fee_table_version": contract.medical_fee_table_version,
        "materials_table": contract.materials_table,
        "materials_table_version": contract.materials_table_version,
        "medicines_table": contract.medicines_table,
        "medicines_table_version": contract.medicines_table_version,
        "alerts": normalize_text_list(contract.alerts),
    }


def build_dashboard_metrics(contracts: list[Contract]) -> dict:
    today = date.today()
    total = len(contracts)
    due_30 = due_60 = due_90 = expired = critical = with_auto_renew = without_reajust_index = 0

    status_counts = Counter({"Vigentes": 0, "A vencer": 0, "Vencidos": 0})
    classification_counts = Counter()
    risk_counts = Counter()
    operators = Counter()
    score_distribution = {"0-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    table_mix = Counter()

    for c in contracts:
        if c.operator_name:
            operators[c.operator_name] += 1
        if c.classification:
            classification_counts[c.classification] += 1
        if c.risk_level:
            risk_counts[c.risk_level] += 1
        if c.auto_renewal:
            with_auto_renew += 1
        if c.reajust_clause_exists and not c.reajust_index:
            without_reajust_index += 1
        if c.risk_level in {"alto", "muito alto"}:
            critical += 1

        score = c.score_total or 0
        if score < 40:
            score_distribution["0-39"] += 1
        elif score < 60:
            score_distribution["40-59"] += 1
        elif score < 80:
            score_distribution["60-79"] += 1
        else:
            score_distribution["80-100"] += 1

        parts = [p for p in [c.medical_fee_table, c.materials_table, c.medicines_table] if p]
        if parts:
            table_mix[" + ".join(parts)] += 1

        if c.end_date:
            days = (c.end_date - today).days
            if days < 0:
                expired += 1
                status_counts["Vencidos"] += 1
            else:
                status_counts["Vigentes"] += 1
                if days <= 90:
                    status_counts["A vencer"] += 1
                if days <= 30:
                    due_30 += 1
                if days <= 60:
                    due_60 += 1
                if days <= 90:
                    due_90 += 1

    timeline = [{"label": f"≤ {threshold} dias", "count": sum(1 for c in contracts if c.end_date and 0 <= (c.end_date - today).days <= threshold)} for threshold in ALERT_THRESHOLDS]
    top_operators = [{"label": label, "count": count} for label, count in operators.most_common(8)]
    table_mix_series = [{"label": label, "count": count} for label, count in table_mix.most_common(6)]

    return {
        "total": total,
        "due_30": due_30,
        "due_60": due_60,
        "due_90": due_90,
        "expired": expired,
        "critical": critical,
        "with_auto_renew": with_auto_renew,
        "without_reajust_index": without_reajust_index,
        "status_counts": status_counts,
        "classification_counts": classification_counts,
        "risk_counts": risk_counts,
        "score_distribution": score_distribution,
        "timeline": timeline,
        "top_operators": top_operators,
        "table_mix": table_mix_series,
    }


def fetch_filtered_contracts(db: Session, search: str | None = None, operator: str | None = None, status: str | None = None, risk: str | None = None, start_from: date | None = None, end_to: date | None = None) -> list[Contract]:
    query = db.query(Contract)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Contract.contract_name.ilike(term), Contract.operator_name.ilike(term), Contract.contract_number.ilike(term)))
    if operator:
        query = query.filter(Contract.operator_name == operator)
    if risk:
        query = query.filter(Contract.risk_level == risk)
    if start_from:
        query = query.filter(Contract.end_date >= start_from)
    if end_to:
        query = query.filter(Contract.end_date <= end_to)

    contracts = query.order_by(Contract.created_at.desc()).all()
    if status:
        filtered = []
        for c in contracts:
            d = days_until(c.end_date)
            if status == "vigente" and d is not None and d > 90:
                filtered.append(c)
            elif status == "a_vencer" and d is not None and 0 <= d <= 90:
                filtered.append(c)
            elif status == "vencido" and d is not None and d < 0:
                filtered.append(c)
            elif status == "critico" and c.risk_level in {"alto", "muito alto"}:
                filtered.append(c)
        contracts = filtered
    return contracts


def badge_class(risk_level: str | None) -> str:
    mapping = {None: "slate", "baixo": "emerald", "moderado": "amber", "alto": "rose", "muito alto": "violet"}
    return mapping.get(risk_level, "slate")


def status_meta(contract: Contract) -> dict:
    d = days_until(contract.end_date)
    if d is None:
        return {"label": "Sem vigência", "tone": "slate"}
    if d < 0:
        return {"label": "Vencido", "tone": "rose"}
    if d <= 90:
        return {"label": "A vencer", "tone": "amber"}
    return {"label": "Vigente", "tone": "emerald"}


def parse_upload_to_contract(file: UploadFile) -> dict:
    extension = Path(file.filename).suffix.lower() if file.filename else ""
    if extension not in {".pdf", ".docx", ".txt", ".md"}:
        raise HTTPException(status_code=400, detail="Envie PDF, DOCX, TXT ou MD.")
    stored_name = f"{uuid4().hex}{extension}"
    stored_path = UPLOAD_DIR / stored_name
    with stored_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        extraction = extract_text_from_file(stored_path)
    except TextExtractionError as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    parsed = parse_contract(text=extraction["text"], original_filename=file.filename)
    scored = score_contract(parsed)
    parsed.update(scored)
    parsed["original_filename"] = file.filename
    parsed["stored_filepath"] = str(APP_UPLOAD_DIR / stored_name)
    parsed["extraction_method"] = extraction.get("method")
    parsed["extraction_confidence"] = extraction.get("confidence")
    return parsed


def ensure_contract(db: Session, contract_id: int) -> Contract:
    contract = db.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")
    return contract


def create_pdf_report(contract: Contract, events: list[ContractEvent]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=30, rightMargin=30, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(f"Relatório Contratual - {contract.contract_name}", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Operadora: {contract.operator_name or '-'}", styles["BodyText"]))
    story.append(Paragraph(f"Número: {contract.contract_number or '-'}", styles["BodyText"]))
    story.append(Paragraph(f"Classificação: {contract.classification or '-'} | Score: {contract.score_total or 0}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    data = [
        ["Campo", "Valor"],
        ["Vigência", f"{contract.start_date or '-'} até {contract.end_date or '-'}"],
        ["Pagamento", f"{contract.payment_term_days or '-'} dias"],
        ["Faturamento", f"{contract.billing_deadline_days or '-'} dias"],
        ["Glosa recurso", f"{contract.glosa_appeal_deadline_days or '-'} dias"],
        ["Reajuste", f"{contract.reajust_frequency or '-'} / {contract.reajust_index or '-'}"],
        ["Tabela médica", f"{contract.medical_fee_table or '-'} {contract.medical_fee_table_version or ''}"],
        ["Materiais", f"{contract.materials_table or '-'} {contract.materials_table_version or ''}"],
        ["Medicamentos", f"{contract.medicines_table or '-'} {contract.medicines_table_version or ''}"],
        ["Método de extração", f"{contract.extraction_method or '-'} ({contract.extraction_confidence or 0:.0%})"],
    ]
    table = Table(data, colWidths=[150, 360])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16335f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe4f0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Alertas", styles["Heading2"]))
    for item in normalize_text_list(contract.alerts) or ["Sem alertas registrados."]:
        story.append(Paragraph(f"• {item}", styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Histórico e aditivos", styles["Heading2"]))
    if events:
        for event in events:
            story.append(Paragraph(f"• [{event.event_type}] {event.title} - {event.event_date or event.created_at.date()}", styles["BodyText"]))
            if event.notes:
                story.append(Paragraph(event.notes, styles["BodyText"]))
    else:
        story.append(Paragraph("Nenhum evento cadastrado.", styles["BodyText"]))
    doc.build(story)
    return buffer.getvalue()


templates.env.globals.update(badge_class=badge_class, status_meta=status_meta)


# ---------- Auth ----------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"request": request, "title": "Entrar", "error": False, "login_page": True, "username": "", "remember": False})


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, username: str = Form(...), password: str = Form(...), remember: str | None = Form(default=None)):
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if username == ADMIN_USER and password_hash == ADMIN_PASSWORD_HASH:
        request.session["user"] = username
        request.session["remember"] = bool(remember)
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"request": request, "title": "Entrar", "error": True, "login_page": True, "username": username, "remember": bool(remember)}, status_code=400)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------- Pages ----------
@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contracts = db.query(Contract).order_by(Contract.created_at.desc()).all()
    metrics = build_dashboard_metrics(contracts)
    recent_alerts = []
    for contract in contracts[:12]:
        for alert in normalize_text_list(contract.alerts)[:2]:
            recent_alerts.append({"contract": contract, "text": alert})

    return templates.TemplateResponse(request, "dashboard.html", {"request": request, "title": "Dashboard", "contracts": contracts, "metrics": metrics, "expiring_contracts": sorted([c for c in contracts if days_until(c.end_date) is not None and 0 <= days_until(c.end_date) <= 120], key=lambda c: days_until(c.end_date) or 999999)[:8], "recent_contracts": contracts[:6], "recent_alerts": recent_alerts[:8], "today": date.today()})


@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    if (resp := maybe_redirect_auth(request)):
        return resp
    return templates.TemplateResponse(request, "upload.html", {"request": request, "title": "Upload de contrato"})


@app.post("/contracts/upload")
async def upload_contract(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo inválido.")
    parsed = parse_upload_to_contract(file)
    contract = Contract(**parsed)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    db.add(ContractEvent(contract_id=contract.id, event_type="cadastro", title="Contrato importado", notes=f"Arquivo: {contract.original_filename}"))
    db.commit()
    return RedirectResponse(url=f"/contracts/{contract.id}", status_code=303)


@app.get("/contracts", response_class=HTMLResponse)
def contracts_page(request: Request, db: Session = Depends(get_db), search: str | None = None, operator: str | None = None, status: str | None = Query(default=None), risk: str | None = None, start_from: str | None = None, end_to: str | None = None):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contracts = fetch_filtered_contracts(db, search=search, operator=operator, status=status, risk=risk, start_from=parse_date_input(start_from), end_to=parse_date_input(end_to))
    for contract in contracts:
        contract.days_until_end_view = days_until(contract.end_date)

    total_contracts = len(contracts)
    avg_score = round(sum((c.score_total or 0) for c in contracts) / total_contracts, 1) if total_contracts else 0
    expiring_90 = sum(1 for c in contracts if c.days_until_end_view is not None and 0 <= c.days_until_end_view <= 90)
    critical_count = sum(1 for c in contracts if c.risk_level in {"alto", "muito alto"})
    summary = {
        "total": total_contracts,
        "avg_score": avg_score,
        "expiring_90": expiring_90,
        "critical": critical_count,
        "operators": len({c.operator_name for c in contracts if c.operator_name}),
        "active_filters": sum(1 for value in [search, operator, status, risk, start_from, end_to] if value),
    }
    operators = [row[0] for row in db.query(Contract.operator_name).filter(Contract.operator_name.is_not(None)).distinct().order_by(Contract.operator_name)]
    return templates.TemplateResponse(request, "contracts.html", {"request": request, "title": "Contratos", "contracts": contracts, "operators": operators, "summary": summary, "filters": {"search": search or "", "operator": operator or "", "status": status or "", "risk": risk or "", "start_from": start_from or "", "end_to": end_to or ""}})


@app.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contracts = db.query(Contract).order_by(Contract.created_at.desc()).all()
    rows = []
    for contract in contracts:
        for text in normalize_text_list(contract.alerts):
            rows.append({"contract": contract, "text": text, "priority": RISK_ORDER.get(contract.risk_level or "baixo", 1), "days_until_end": days_until(contract.end_date)})
    rows.sort(key=lambda item: (-item["priority"], item["days_until_end"] if item["days_until_end"] is not None else 999999))
    return templates.TemplateResponse(request, "alerts.html", {"request": request, "title": "Alertas", "alert_rows": rows})


@app.get("/contracts/{contract_id}", response_class=HTMLResponse)
def contract_detail(contract_id: int, request: Request, db: Session = Depends(get_db), edit: int = 0):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contract = ensure_contract(db, contract_id)
    cards = [
        {"label": "Vigência", "value": f"{contract.start_date or '—'} até {contract.end_date or '—'}", "tone": "slate"},
        {"label": "Pagamento", "value": f"{contract.payment_term_days} dias" if contract.payment_term_days else "Não identificado", "tone": "blue"},
        {"label": "Faturamento", "value": f"{contract.billing_deadline_days} dias" if contract.billing_deadline_days else "Não identificado", "tone": "teal"},
        {"label": "Glosa", "value": f"Recurso em {contract.glosa_appeal_deadline_days} dias" if contract.glosa_appeal_deadline_days else "Não identificado", "tone": "amber"},
    ]
    peer_contracts = db.query(Contract).filter(Contract.id != contract.id).order_by(Contract.score_total.desc()).limit(6).all()
    events = db.query(ContractEvent).filter(ContractEvent.contract_id == contract.id).order_by(ContractEvent.created_at.desc()).all()
    return templates.TemplateResponse(request, "contract_detail.html", {"request": request, "title": contract.contract_name, "contract": contract, "summary_cards": cards, "alerts_list": normalize_text_list(contract.alerts), "strong_points": normalize_text_list(contract.strong_points), "weak_points": normalize_text_list(contract.weak_points), "peer_contracts": peer_contracts, "days_until_end": days_until(contract.end_date), "events": events, "edit_mode": bool(edit), "form_data": contract_to_form_data(contract)})


@app.post("/contracts/{contract_id}/edit")
def update_contract(contract_id: int, request: Request, db: Session = Depends(get_db), contract_name: str = Form(...), operator_name: str = Form(""), contract_number: str = Form(""), contract_object: str = Form(""), signature_date: str = Form(""), start_date: str = Form(""), end_date: str = Form(""), auto_renewal: str | None = Form(None), renewal_details: str = Form(""), termination_notice_days: str = Form(""), payment_term_days: str = Form(""), payment_trigger: str = Form(""), payment_interest_clause: str | None = Form(None), payment_penalty_clause: str | None = Form(None), billing_deadline_days: str = Form(""), billing_deadline_description: str = Form(""), allows_glosa_unilateral: str | None = Form(None), glosa_deadline_days: str = Form(""), glosa_appeal_deadline_days: str = Form(""), glosa_response_deadline_days: str = Form(""), glosa_clause_summary: str = Form(""), reajust_clause_exists: str | None = Form(None), reajust_frequency: str = Form(""), reajust_index: str = Form(""), reajust_clause_summary: str = Form(""), medical_fee_table: str = Form(""), medical_fee_table_version: str = Form(""), daily_rate_table: str = Form(""), materials_table: str = Form(""), materials_table_version: str = Form(""), medicines_table: str = Form(""), medicines_table_version: str = Form("")):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contract = ensure_contract(db, contract_id)
    form = {
        "contract_name": contract_name, "operator_name": operator_name, "contract_number": contract_number, "contract_object": contract_object,
        "signature_date": signature_date, "start_date": start_date, "end_date": end_date, "auto_renewal": parse_bool_input(auto_renewal),
        "renewal_details": renewal_details, "termination_notice_days": termination_notice_days, "payment_term_days": payment_term_days,
        "payment_trigger": payment_trigger, "payment_interest_clause": parse_bool_input(payment_interest_clause), "payment_penalty_clause": parse_bool_input(payment_penalty_clause),
        "billing_deadline_days": billing_deadline_days, "billing_deadline_description": billing_deadline_description,
        "allows_glosa_unilateral": parse_bool_input(allows_glosa_unilateral), "glosa_deadline_days": glosa_deadline_days,
        "glosa_appeal_deadline_days": glosa_appeal_deadline_days, "glosa_response_deadline_days": glosa_response_deadline_days,
        "glosa_clause_summary": glosa_clause_summary, "reajust_clause_exists": parse_bool_input(reajust_clause_exists),
        "reajust_frequency": reajust_frequency, "reajust_index": reajust_index, "reajust_clause_summary": reajust_clause_summary,
        "medical_fee_table": medical_fee_table, "medical_fee_table_version": medical_fee_table_version, "daily_rate_table": daily_rate_table,
        "materials_table": materials_table, "materials_table_version": materials_table_version,
        "medicines_table": medicines_table, "medicines_table_version": medicines_table_version,
    }
    data = apply_contract_form(contract, form)
    scored = score_contract(data)
    data.update(scored)
    for key, value in data.items():
        setattr(contract, key, value)
    db.add(contract)
    db.commit()
    db.add(ContractEvent(contract_id=contract.id, event_type="edicao", title="Cadastro revisado manualmente", notes="Campos ajustados na tela de edição."))
    db.commit()
    return RedirectResponse(f"/contracts/{contract.id}", status_code=303)


@app.post("/contracts/{contract_id}/events")
def add_contract_event(contract_id: int, request: Request, db: Session = Depends(get_db), event_type: str = Form(...), title: str = Form(...), event_date: str = Form(""), notes: str = Form("")):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contract = ensure_contract(db, contract_id)
    event = ContractEvent(contract_id=contract.id, event_type=event_type, title=title, event_date=parse_date_input(event_date), notes=notes or None)
    db.add(event)
    db.commit()
    return RedirectResponse(f"/contracts/{contract.id}", status_code=303)


@app.get("/compare", response_class=HTMLResponse)
def compare_builder_page(request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contracts = db.query(Contract).order_by(Contract.created_at.desc()).all()
    return templates.TemplateResponse(request, "compare_builder.html", {"request": request, "title": "Comparar contratos", "contracts": contracts})


@app.get("/compare/result", response_class=HTMLResponse)
def compare_result_page(request: Request, ids: str, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    try:
        id_list = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="IDs inválidos.") from exc
    contracts = db.query(Contract).filter(Contract.id.in_(id_list)).all()
    if len(contracts) < 2:
        raise HTTPException(status_code=400, detail="Selecione pelo menos 2 contratos.")
    comparison_rows = compare_contracts(contracts)
    return templates.TemplateResponse(request, "comparison.html", {"request": request, "title": "Comparação de contratos", "contracts": contracts, "comparison_rows": comparison_rows})


@app.get("/contracts/export.csv")
def export_contracts_csv(request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contracts = db.query(Contract).order_by(Contract.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Operadora", "Contrato", "Número", "Início", "Fim", "Score", "Classificação", "Risco", "Tabela médica", "Materiais", "Medicamentos"])
    for c in contracts:
        writer.writerow([c.id, c.operator_name or "", c.contract_name or "", c.contract_number or "", c.start_date or "", c.end_date or "", c.score_total or 0, c.classification or "", c.risk_level or "", c.medical_fee_table or "", c.materials_table or "", c.medicines_table or ""])
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=contratos.csv"})


@app.get("/contracts/export.xlsx")
def export_contracts_xlsx(request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    wb = Workbook()
    ws = wb.active
    ws.title = "Contratos"
    headers = ["ID", "Operadora", "Contrato", "Número", "Início", "Fim", "Score", "Classificação", "Risco", "Pagamento", "Faturamento", "Glosa recurso", "Reajuste", "Tabela médica", "Materiais", "Medicamentos"]
    ws.append(headers)
    for c in db.query(Contract).order_by(Contract.created_at.desc()).all():
        ws.append([c.id, c.operator_name or "", c.contract_name or "", c.contract_number or "", str(c.start_date or ""), str(c.end_date or ""), c.score_total or 0, c.classification or "", c.risk_level or "", c.payment_term_days or "", c.billing_deadline_days or "", c.glosa_appeal_deadline_days or "", c.reajust_index or c.reajust_frequency or "", c.medical_fee_table or "", c.materials_table or "", c.medicines_table or ""])
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=contratos.xlsx"})


@app.get("/contracts/{contract_id}/report.pdf")
def export_contract_pdf(contract_id: int, request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contract = ensure_contract(db, contract_id)
    events = db.query(ContractEvent).filter(ContractEvent.contract_id == contract.id).order_by(ContractEvent.created_at.desc()).all()
    pdf = create_pdf_report(contract, events)
    filename = f"contrato_{contract.id}.pdf"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/contracts/{contract_id}/delete")
def delete_contract(contract_id: int, request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contract = ensure_contract(db, contract_id)
    if contract.stored_filepath:
        (BASE_DIR / contract.stored_filepath).unlink(missing_ok=True)
    db.query(ContractEvent).filter(ContractEvent.contract_id == contract.id).delete()
    db.delete(contract)
    db.commit()
    return RedirectResponse(url="/contracts", status_code=303)


# ---------- APIs ----------
@app.get("/api/contracts")
def list_contracts(request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contracts = db.query(Contract).order_by(Contract.created_at.desc()).all()
    return [serialize_contract(c) for c in contracts]


@app.get("/api/dashboard")
def dashboard_api(request: Request, db: Session = Depends(get_db)):
    if (resp := maybe_redirect_auth(request)):
        return resp
    contracts = db.query(Contract).order_by(Contract.created_at.desc()).all()
    return build_dashboard_metrics(contracts)
