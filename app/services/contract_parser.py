from __future__ import annotations

import re
from datetime import date
from typing import Any

from dateutil.parser import parse as date_parse


DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
NUMBER_AFTER_DAYS_RE = re.compile(r"(\d{1,3})\s*(dias?)", re.IGNORECASE)


def parse_contract(text: str, original_filename: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    dates = find_dates(normalized)

    data: dict[str, Any] = {
        "contract_name": build_contract_name(normalized, original_filename),
        "operator_name": extract_operator_name(normalized),
        "contract_number": extract_contract_number(normalized),
        "contract_object": extract_object(normalized),
        "signature_date": extract_signature_date(normalized, dates),
        "start_date": extract_start_date(normalized, dates),
        "end_date": extract_end_date(normalized, dates),
        "auto_renewal": has_auto_renewal(normalized),
        "renewal_details": extract_renewal_details(normalized),
        "termination_notice_days": extract_termination_notice_days(normalized),
        "payment_term_days": extract_payment_term(normalized),
        "payment_trigger": extract_payment_trigger(normalized),
        "payment_interest_clause": contains_any(normalized, ["juros de mora", "juros moratórios", "juros"]),
        "payment_penalty_clause": contains_any(normalized, ["multa por atraso", "multa moratória", "multa"]),
        "billing_deadline_days": extract_billing_deadline(normalized),
        "billing_deadline_description": extract_billing_deadline_clause(normalized),
        "allows_glosa_unilateral": contains_any(
            normalized,
            [
                "poderá glosar",
                "a operadora poderá glosar",
                "a contratante poderá glosar",
                "glosas que entender indevidas",
            ],
        ),
        "glosa_deadline_days": extract_glosa_deadline(normalized),
        "glosa_appeal_deadline_days": extract_glosa_appeal_deadline(normalized),
        "glosa_response_deadline_days": extract_glosa_response_deadline(normalized),
        "glosa_clause_summary": extract_glosa_clause(normalized),
        "reajust_clause_exists": contains_any(normalized, ["reajuste", "revisão anual", "revisão dos valores"]),
        "reajust_frequency": extract_reajust_frequency(normalized),
        "reajust_index": extract_reajust_index(normalized),
        "reajust_clause_summary": extract_reajust_clause(normalized),
        "medical_fee_table": extract_medical_fee_table(normalized),
        "medical_fee_table_version": extract_cbhpm_version(normalized),
        "daily_rate_table": extract_daily_rate_table(normalized),
        "materials_table": extract_materials_table(normalized),
        "materials_table_version": extract_materials_table_version(normalized),
        "medicines_table": extract_medicines_table(normalized),
        "medicines_table_version": extract_medicines_table_version(normalized),
        "raw_text": text,
    }
    return data


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text.lower() for term in terms)


def find_dates(text: str) -> list[date]:
    results: list[date] = []
    for match in DATE_RE.findall(text):
        try:
            dt = date_parse(match, dayfirst=True).date()
            results.append(dt)
        except Exception:
            continue
    unique = []
    seen = set()
    for d in results:
        if d not in seen:
            unique.append(d)
            seen.add(d)
    return unique


def build_contract_name(text: str, original_filename: str) -> str:
    number = extract_contract_number(text)
    operator = extract_operator_name(text)
    if operator and number:
        return f"{operator} - {number}"
    if operator:
        return operator
    return original_filename.rsplit('.', 1)[0]


def first_group(pattern: str, text: str, flags: int = re.IGNORECASE) -> str | None:
    match = re.search(pattern, text, flags)
    if match:
        return match.group(1).strip(" .;:-")
    return None


def extract_operator_name(text: str) -> str | None:
    patterns = [
        r"(?:operadora|contratante)\s*[:\-]\s*([A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç0-9 &.,\-/]{3,100})",
        r"entre\s+o\s+hospital.*?e\s+a\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç0-9 &.,\-/]{3,100})",
    ]
    for p in patterns:
        value = first_group(p, text)
        if value:
            return value[:100]
    return None


def extract_contract_number(text: str) -> str | None:
    patterns = [
        r"(?:contrato|instrumento|termo)\s*(?:n[ºo°\.]?\s*)?([A-Za-z0-9\-/\.]{3,40})",
        r"n[ºo°\.]?\s*do\s*contrato\s*[:\-]?\s*([A-Za-z0-9\-/\.]{3,40})",
    ]
    for p in patterns:
        value = first_group(p, text)
        if value and not value.lower().startswith("de"):
            return value
    return None


def extract_object(text: str) -> str | None:
    return first_group(r"objeto\s*[:\-]\s*(.{20,400}?)(?:cláusula|parágrafo|vigência|assinatura)", text)


def extract_signature_date(text: str, dates: list[date]) -> date | None:
    value = first_group(r"assinad[oa].{0,25}?em\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text)
    if value:
        try:
            return date_parse(value, dayfirst=True).date()
        except Exception:
            pass
    return dates[0] if dates else None


def extract_start_date(text: str, dates: list[date]) -> date | None:
    value = first_group(r"(?:vigência|início da vigência|início)\s*(?:será|inicia-se|início em|a partir de)?\s*(?:em\s*)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text)
    if value:
        try:
            return date_parse(value, dayfirst=True).date()
        except Exception:
            pass
    return dates[0] if dates else None


def extract_end_date(text: str, dates: list[date]) -> date | None:
    value = first_group(r"(?:até|término em|fim da vigência|vigência até)\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text)
    if value:
        try:
            return date_parse(value, dayfirst=True).date()
        except Exception:
            pass
    return dates[1] if len(dates) > 1 else None


def has_auto_renewal(text: str) -> bool:
    return contains_any(text, ["renovação automática", "renovado automaticamente", "prorrogação automática"])


def extract_renewal_details(text: str) -> str | None:
    return first_group(r"((?:renovação|prorrogação).{0,220}?(?:automática|automaticamente).{0,220}?[\.;])", text)


def extract_termination_notice_days(text: str) -> int | None:
    clause = first_group(r"(?:denúncia|rescisão).{0,100}?(\d{1,3})\s*dias", text)
    return int(clause) if clause else None


def extract_payment_term(text: str) -> int | None:
    clause = first_group(r"pagamento.{0,120}?em\s+até\s+(\d{1,3})\s+dias", text)
    if clause:
        return int(clause)
    clause = first_group(r"pago.{0,120}?em\s+até\s+(\d{1,3})\s+dias", text)
    return int(clause) if clause else None


def extract_payment_trigger(text: str) -> str | None:
    triggers = [
        "apresentação da fatura",
        "apresentação da nota fiscal",
        "recebimento da fatura",
        "protocolo da fatura",
        "processamento da conta",
    ]
    lower = text.lower()
    for t in triggers:
        if t in lower:
            return t
    return None


def extract_billing_deadline(text: str) -> int | None:
    clause = first_group(r"faturamento.{0,120}?(\d{1,3})\s+dias", text)
    if clause:
        return int(clause)
    clause = first_group(r"apresentação da fatura.{0,80}?(\d{1,3})\s+dias", text)
    return int(clause) if clause else None


def extract_billing_deadline_clause(text: str) -> str | None:
    return first_group(r"((?:faturamento|apresentação da fatura).{0,220}?[\.;])", text)


def extract_glosa_deadline(text: str) -> int | None:
    clause = first_group(r"glosa.{0,120}?em\s+até\s+(\d{1,3})\s+dias", text)
    if clause:
        return int(clause)
    clause = first_group(r"prazo.{0,50}?glosa.{0,60}?(\d{1,3})\s+dias", text)
    return int(clause) if clause else None


def extract_glosa_appeal_deadline(text: str) -> int | None:
    clause = first_group(r"(?:recurso de glosa|contestação da glosa|impugnação).{0,120}?(\d{1,3})\s+dias", text)
    return int(clause) if clause else None


def extract_glosa_response_deadline(text: str) -> int | None:
    clause = first_group(r"(?:resposta ao recurso|análise do recurso|julgamento do recurso).{0,120}?(\d{1,3})\s+dias", text)
    return int(clause) if clause else None


def extract_glosa_clause(text: str) -> str | None:
    return first_group(r"((?:glosa|glosas).{0,300}?[\.;])", text)


def extract_reajust_frequency(text: str) -> str | None:
    if contains_any(text, ["anual", "anualmente", "a cada 12 meses"]):
        return "anual"
    if contains_any(text, ["semestral", "a cada 6 meses"]):
        return "semestral"
    return None


def extract_reajust_index(text: str) -> str | None:
    indexes = ["IPCA", "IGP-M", "INPC", "IPC", "FIPE", "IGPM"]
    upper = text.upper()
    for idx in indexes:
        if idx in upper:
            return idx
    return None


def extract_reajust_clause(text: str) -> str | None:
    return first_group(r"((?:reajuste|revisão dos valores).{0,300}?[\.;])", text)


def extract_medical_fee_table(text: str) -> str | None:
    if "CBHPM" in text.upper():
        return "CBHPM"
    if contains_any(text, ["tabela própria", "tabela da operadora"]):
        return "Tabela própria"
    return None


def extract_cbhpm_version(text: str) -> str | None:
    value = first_group(r"CBHPM\s*(?:edição|versão)?\s*(\d{4})", text, flags=re.IGNORECASE)
    return value


def extract_daily_rate_table(text: str) -> str | None:
    if contains_any(text, ["diárias e taxas", "diárias", "taxas hospitalares"]):
        clause = first_group(r"((?:diárias e taxas|taxas hospitalares).{0,160}?[\.;])", text)
        return clause or "Diárias e taxas negociadas entre as partes"
    return None


def extract_materials_table(text: str) -> str | None:
    if "SIMPRO" in text.upper():
        return "SIMPRO"
    return None


def extract_materials_table_version(text: str) -> str | None:
    return first_group(r"SIMPRO\s*(?:edição|versão)?\s*(\d{4})", text, flags=re.IGNORECASE)


def extract_medicines_table(text: str) -> str | None:
    if "BRASÍNDICE" in text.upper() or "BRASINDICE" in text.upper():
        return "Brasíndice"
    return None


def extract_medicines_table_version(text: str) -> str | None:
    return first_group(r"BRAS[ÍI]NDICE\s*(?:edição|versão)?\s*(\d{4})", text, flags=re.IGNORECASE)
