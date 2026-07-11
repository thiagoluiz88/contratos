from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.database import SessionLocal
from app.models import ContractExtraction


ANALYSIS_VERSION = "1.0"
ANALYSIS_METHOD = "local_rules"
MAX_TEXT_CHARS = 120_000
MAX_EVIDENCE_CHARS = 700
MAX_CLAUSES_PER_CATEGORY = 6
MAX_FINANCIAL_TERMS = 40

STATUS_TEXT_EXTRACTED = "texto_extraido"
STATUS_ANALYSIS_PENDING = "analise_pendente"
STATUS_ANALYZING = "analisando"
STATUS_CANDIDATES_GENERATED = "candidatos_gerados"
STATUS_AWAITING_VALIDATION = "aguardando_validacao"
STATUS_APPROVED = "aprovado"
STATUS_REJECTED = "rejeitado"
STATUS_ERROR = "erro"

DATE_PATTERN = r"\b(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{2,4})\b"
DATE_RE = re.compile(DATE_PATTERN)
CNPJ_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
CURRENCY_RE = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d{3,},\d{2})")
PERCENT_RE = re.compile(r"\b\d{1,3}(?:[,.]\d{1,4})?\s*%")
INDEX_RE = re.compile(r"\b(IPCA|IGP-?M|IGPM|INPC|VCMH|varia[cÃ§][aÃ£]o de custos m[eÃ©]dico-?hospitalares)\b", re.IGNORECASE)


def candidate(value=None, confidence: float = 0, evidence: str | None = None) -> dict:
    return {
        "value": value,
        "confidence": round(max(0, min(float(confidence), 1)), 2),
        "evidence": trim_evidence(evidence),
    }


def empty_candidate() -> dict:
    return candidate()


def normalize_text(text: str | None) -> str:
    prepared = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    prepared = re.sub(r"[ \t]+", " ", prepared)
    prepared = re.sub(r"\n{3,}", "\n\n", prepared)
    return prepared.strip()


def fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def trim_evidence(value: str | None, *, limit: int = MAX_EVIDENCE_CHARS) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", " ", value).strip()
    return compact[:limit].strip() if compact else None


def iter_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def text_window(text: str, start: int, end: int, *, radius: int = 180) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def normalize_date_value(value: str | None) -> str | None:
    if not value:
        return None
    match = DATE_RE.search(value)
    if not match:
        return None
    day, month, year = match.groups()
    year = f"20{year}" if len(year) == 2 and int(year) < 70 else (f"19{year}" if len(year) == 2 else year)
    try:
        return datetime(int(year), int(month), int(day)).date().isoformat()
    except ValueError:
        return None


def normalize_currency_value(value: str | None) -> str | None:
    if not value:
        return None
    match = CURRENCY_RE.search(value)
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        return f"{Decimal(raw):.2f}"
    except InvalidOperation:
        return None


def normalize_percentage_value(value: str | None) -> str | None:
    if not value:
        return None
    match = PERCENT_RE.search(value)
    if not match:
        return None
    raw = match.group(0).replace("%", "").replace(",", ".").strip()
    try:
        return f"{Decimal(raw):.4f}".rstrip("0").rstrip(".")
    except InvalidOperation:
        return None


def calculate_candidate_confidence(*, label_match: bool = False, context_match: bool = False, normalized: bool = False, exact_pattern: bool = False) -> float:
    score = 0.25
    if label_match:
        score += 0.25
    if context_match:
        score += 0.20
    if normalized:
        score += 0.15
    if exact_pattern:
        score += 0.15
    return min(score, 0.95)


def first_regex_candidate(text: str, patterns: list[re.Pattern], *, normalizer=None, confidence: float = 0.72) -> dict:
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        value = match.group(1).strip() if match.groups() else match.group(0).strip()
        normalized = normalizer(value) if normalizer else value
        if normalized:
            return candidate(normalized, confidence, text_window(text, match.start(), match.end()))
    return empty_candidate()


def detect_document_type(text: str) -> str | None:
    folded = fold_text(text[:5000])
    for value, words in (
        ("aditivo", ("termo aditivo", "aditivo contratual")),
        ("tabela", ("tabela", "tabela de precos", "tabela de valores")),
        ("anexo", ("anexo", "apendice")),
        ("contrato", ("contrato", "instrumento particular")),
    ):
        if any(word in folded for word in words):
            return value
    return None


def extract_contract_metadata(text: str) -> dict:
    metadata = {
        "operadora": empty_candidate(),
        "razao_social": empty_candidate(),
        "cnpj": empty_candidate(),
        "registro_ans": empty_candidate(),
        "numero_contrato": empty_candidate(),
        "tipo_contrato": empty_candidate(),
        "data_assinatura": empty_candidate(),
    }
    metadata["operadora"] = first_regex_candidate(
        text,
        [
            re.compile(r"(?:operadora|contratada)\s*[:\-]\s*([^\n|;.]{3,120})", re.IGNORECASE),
            re.compile(r"(?:plano de sa[uÃº]de|conv[eÃª]nio)\s*[:\-]\s*([^\n|;.]{3,120})", re.IGNORECASE),
        ],
        confidence=0.78,
    )
    metadata["razao_social"] = first_regex_candidate(
        text,
        [re.compile(r"raz[aÃ£]o social\s*[:\-]\s*([^\n|;.]{3,160})", re.IGNORECASE)],
        confidence=0.82,
    )
    cnpj_match = CNPJ_RE.search(text)
    if cnpj_match:
        metadata["cnpj"] = candidate(cnpj_match.group(0), 0.92, text_window(text, cnpj_match.start(), cnpj_match.end()))
    ans_context = re.search(r"(?:registro\s+ANS|ANS)\D{0,30}(\d{6})", text, re.IGNORECASE)
    if ans_context:
        metadata["registro_ans"] = candidate(ans_context.group(1), 0.86, text_window(text, ans_context.start(), ans_context.end()))
    metadata["numero_contrato"] = first_regex_candidate(
        text,
        [
            re.compile(r"(?:contrato|instrumento)\s*(?:n[Âºo.]|numero)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9./\-]{2,40})", re.IGNORECASE),
            re.compile(r"n[Âºo.]\s*(?:do\s*)?contrato\s*[:\-]?\s*([A-Z0-9][A-Z0-9./\-]{2,40})", re.IGNORECASE),
        ],
        confidence=0.72,
    )
    doc_type = detect_document_type(text)
    if doc_type:
        metadata["tipo_contrato"] = candidate(doc_type, 0.70, doc_type)
    signature = re.search(r"(?:assinad[oa]|assinatura|firmado)\D{0,80}" + DATE_PATTERN, text, re.IGNORECASE)
    if signature:
        metadata["data_assinatura"] = candidate(normalize_date_value(signature.group(0)), 0.72, text_window(text, signature.start(), signature.end()))
    return metadata


def extract_dates_and_deadlines(text: str) -> dict:
    data = {"data_inicio": empty_candidate(), "data_fim": empty_candidate(), "data_base_reajuste": empty_candidate(), "prazos": []}
    patterns = {
        "data_inicio": re.compile(r"(?:in[iÃ­]cio da vig[eÃª]ncia|vig[eÃª]ncia inicial|a partir de)\D{0,80}" + DATE_PATTERN, re.IGNORECASE),
        "data_fim": re.compile(r"(?:fim da vig[eÃª]ncia|t[eÃ©]rmino da vig[eÃª]ncia|vig[eÃª]ncia final|at[eÃ©])\D{0,80}" + DATE_PATTERN, re.IGNORECASE),
        "data_base_reajuste": re.compile(r"(?:data-?base|base de reajuste)\D{0,80}" + DATE_PATTERN, re.IGNORECASE),
    }
    for field, pattern in patterns.items():
        match = pattern.search(text)
        if match:
            data[field] = candidate(normalize_date_value(match.group(0)), 0.78, text_window(text, match.start(), match.end()))
    seen = set()
    for match in re.finditer(r"(.{0,80}\b(?:prazo|dias|pagamento|faturamento|glosa|notifica[cÃ§][aÃ£]o|rescis[aÃ£]o)\b.{0,120})", text, re.IGNORECASE):
        evidence = trim_evidence(match.group(1), limit=360)
        key = fold_text(evidence or "")
        if evidence and key not in seen:
            seen.add(key)
            data["prazos"].append({"categoria": "prazo", "confidence": 0.58, "evidence": evidence})
        if len(data["prazos"]) >= 12:
            break
    return data


def extract_adjustment_indexes(text: str) -> dict:
    result = {"indice_reajuste": empty_candidate(), "percentual_reajuste": empty_candidate()}
    for match in INDEX_RE.finditer(text):
        evidence = text_window(text, match.start(), match.end())
        if "reajust" in fold_text(evidence) or "indice" in fold_text(evidence) or "data-base" in fold_text(evidence):
            result["indice_reajuste"] = candidate(match.group(1).upper().replace("IGPM", "IGP-M"), 0.86, evidence)
            percent = PERCENT_RE.search(evidence)
            if percent:
                result["percentual_reajuste"] = candidate(normalize_percentage_value(percent.group(0)), 0.76, evidence)
            break
    if not result["percentual_reajuste"]["value"]:
        match = re.search(r"(?:reajust[ea]|percentual|acr[eÃ©]scimo)\D{0,80}" + PERCENT_RE.pattern, text, re.IGNORECASE)
        if match:
            result["percentual_reajuste"] = candidate(normalize_percentage_value(match.group(0)), 0.70, text_window(text, match.start(), match.end()))
    return result


CLAUSE_RULES = {
    "prazo_faturamento": ("faturamento", "envio de faturamento", "conta hospitalar", "apresentacao da conta", "apresentaÃ§Ã£o da conta"),
    "prazo_pagamento": ("pagamento", "prazo de pagamento", "dias para pagamento"),
    "prazo_recurso_glosa": ("recurso de glosa", "contestacao de glosa", "contestaÃ§Ã£o de glosa", "prazo para recurso"),
    "regras_glosa": ("glosa", "glosar", "recurso de glosa"),
    "regras_autorizacao": ("autorizacao", "autorizaÃ§Ã£o", "senha", "pre-autorizacao", "prÃ©-autorizaÃ§Ã£o", "guia autorizada"),
    "multas": ("multa", "penalidade", "juros moratorios", "juros moratÃ³rios", "mora"),
    "auditoria": ("auditoria", "auditoria medica", "auditoria mÃ©dica", "auditoria de enfermagem"),
    "rescisao": ("rescisao", "rescisÃ£o", "resilir", "denuncia", "denÃºncia", "notificacao previa", "notificaÃ§Ã£o prÃ©via"),
    "opme": ("opme", "ortese", "Ã³rtese", "protese", "prÃ³tese", "material especial"),
    "materiais_medicamentos": ("material", "medicamento", "medicamentos", "materiais"),
    "pacotes": ("pacote", "pacotes"),
    "diarias_taxas": ("diaria", "diÃ¡ria", "taxa", "taxas"),
    "honorarios": ("honorario", "honorÃ¡rio", "honorarios medicos", "honorÃ¡rios mÃ©dicos"),
}


def extract_critical_clauses(text: str) -> dict:
    lines = iter_lines(text)
    result = {category: [] for category in CLAUSE_RULES}
    seen: set[tuple[str, str]] = set()
    for index, line in enumerate(lines):
        folded = fold_text(line)
        for category, keywords in CLAUSE_RULES.items():
            if len(result[category]) >= MAX_CLAUSES_PER_CATEGORY:
                continue
            if not any(fold_text(keyword) in folded for keyword in keywords):
                continue
            evidence = trim_evidence(" ".join(lines[max(0, index - 1) : min(len(lines), index + 2)]), limit=480)
            key = (category, fold_text(evidence or ""))
            if evidence and key not in seen:
                seen.add(key)
                confidence = 0.74 if any(word in folded for word in ("clausula", "prazo", "regra", "autorizacao", "auditoria")) else 0.62
                result[category].append({"categoria": category, "confidence": confidence, "evidence": evidence})
    return result


FINANCIAL_CATEGORY_KEYWORDS = {
    "diaria": ("diaria", "diÃ¡ria", "uti", "enfermaria", "apartamento", "bercario", "berÃ§Ã¡rio"),
    "taxa": ("taxa", "sala cirurgica", "sala cirÃºrgica", "taxa de sala", "equipamento", "gases medicinais"),
    "pacote": ("pacote", "pacotes"),
    "material": ("material", "materiais"),
    "medicamento": ("medicamento", "medicamentos"),
    "OPME": ("opme", "ortese", "Ã³rtese", "protese", "prÃ³tese", "material especial"),
    "honorario": ("honorario", "honorÃ¡rio", "honorarios", "honorÃ¡rios", "porte"),
    "servico": ("servico", "serviÃ§o", "procedimento", "exame"),
}


def infer_financial_category(context: str) -> tuple[str | None, str | None, float]:
    folded = fold_text(context)
    for category, keywords in FINANCIAL_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if fold_text(keyword) in folded:
                return category, keyword, 0.72
    return None, None, 0.38


def infer_unit(context: str) -> str | None:
    folded = fold_text(context)
    if "diaria" in folded:
        return "diaria"
    if "unitario" in folded or "valor unitario" in folded:
        return "unitario"
    if "pacote" in folded:
        return "pacote"
    if "porte" in folded:
        return "porte"
    return None


def first_date_in_text(text: str) -> str | None:
    match = DATE_RE.search(text)
    return normalize_date_value(match.group(0)) if match else None


def unique_strings(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        key = fold_text(value)
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def extract_financial_terms(text: str) -> tuple[list[dict], list[str]]:
    terms: list[dict] = []
    warnings: list[str] = []
    seen = set()
    for match in CURRENCY_RE.finditer(text):
        context = text_window(text, match.start(), match.end(), radius=150)
        category, keyword, confidence = infer_financial_category(context)
        value = normalize_currency_value(match.group(0))
        evidence = trim_evidence(context, limit=420)
        if not value or not evidence:
            continue
        key = (category or "sem_contexto", value, fold_text(evidence))
        if key in seen:
            continue
        seen.add(key)
        if not category:
            warnings.append(f"Valor financeiro sem contexto suficiente: {match.group(0)}")
            category = "outro"
        terms.append(
            {
                "categoria": category,
                "item": keyword,
                "descricao": evidence,
                "valor": value,
                "unidade": infer_unit(context),
                "vigencia_inicio": first_date_in_text(context),
                "vigencia_fim": None,
                "confidence": confidence,
                "evidence": evidence,
            }
        )
        if len(terms) >= MAX_FINANCIAL_TERMS:
            warnings.append("Limite de candidatos financeiros atingido; revise o texto completo na validacao humana.")
            break
    return terms, unique_strings(warnings)


def build_candidate_json(
    *,
    text: str,
    metadata: dict,
    dates: dict,
    adjustments: dict,
    clauses: dict,
    financial_terms: list[dict],
    warnings: list[str],
) -> dict:
    return {
        "metadata": {
            "analysis_version": ANALYSIS_VERSION,
            "analysis_method": ANALYSIS_METHOD,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "requires_human_validation": True,
            "analyzed_characters": len(text),
            "max_text_characters": MAX_TEXT_CHARS,
        },
        "contrato": {
            "operadora": metadata.get("operadora", empty_candidate()),
            "razao_social": metadata.get("razao_social", empty_candidate()),
            "cnpj": metadata.get("cnpj", empty_candidate()),
            "registro_ans": metadata.get("registro_ans", empty_candidate()),
            "numero_contrato": metadata.get("numero_contrato", empty_candidate()),
            "tipo_contrato": metadata.get("tipo_contrato", empty_candidate()),
            "data_assinatura": metadata.get("data_assinatura", empty_candidate()),
            "data_inicio": dates.get("data_inicio", empty_candidate()),
            "data_fim": dates.get("data_fim", empty_candidate()),
            "data_base_reajuste": dates.get("data_base_reajuste", empty_candidate()),
            "indice_reajuste": adjustments.get("indice_reajuste", empty_candidate()),
            "percentual_reajuste": adjustments.get("percentual_reajuste", empty_candidate()),
        },
        "clausulas_criticas": clauses,
        "prazos": dates.get("prazos", []),
        "condicoes_contratuais": financial_terms,
        "warnings": warnings,
    }


def analyze_text_to_candidates(text: str | None) -> dict:
    prepared = normalize_text(text)
    warnings: list[str] = []
    if not prepared:
        return build_candidate_json(
            text="",
            metadata={},
            dates={},
            adjustments={},
            clauses={category: [] for category in CLAUSE_RULES},
            financial_terms=[],
            warnings=["Texto extraido indisponivel para analise interpretativa."],
        )
    if len(prepared) > MAX_TEXT_CHARS:
        prepared = prepared[:MAX_TEXT_CHARS]
        warnings.append("Texto limitado para analise local; revise o documento completo na validacao humana.")
    metadata = extract_contract_metadata(prepared)
    dates = extract_dates_and_deadlines(prepared)
    adjustments = extract_adjustment_indexes(prepared)
    clauses = extract_critical_clauses(prepared)
    financial_terms, financial_warnings = extract_financial_terms(prepared)
    warnings.extend(financial_warnings)
    return build_candidate_json(
        text=prepared,
        metadata=metadata,
        dates=dates,
        adjustments=adjustments,
        clauses=clauses,
        financial_terms=financial_terms,
        warnings=unique_strings(warnings),
    )


def append_warning(existing: str | None, warning: str) -> str:
    values = [line.strip() for line in (existing or "").splitlines() if line.strip()]
    values.append(warning)
    return "\n".join(unique_strings(values))


def analyze_extracted_contract_text(extraction_id: int, user_id: str | None = None) -> ContractExtraction:
    db = SessionLocal()
    try:
        extraction = db.query(ContractExtraction).filter(ContractExtraction.id == extraction_id).first()
        if not extraction:
            raise ValueError("Extracao nao encontrada.")
        if not (extraction.extracted_text or "").strip():
            extraction.extraction_status = STATUS_AWAITING_VALIDATION
            extraction.review_status = "pendente"
            extraction.extracted_json = analyze_text_to_candidates(None)
            extraction.extraction_warnings = append_warning(extraction.extraction_warnings, "Analise interpretativa nao executada: texto extraido indisponivel.")
            db.commit()
            db.refresh(extraction)
            return extraction
        extraction.extraction_status = STATUS_ANALYZING
        db.flush()
        extraction.extracted_json = analyze_text_to_candidates(extraction.extracted_text)
        extraction.extraction_status = STATUS_CANDIDATES_GENERATED
        extraction.review_status = "pendente"
        extraction.extraction_source = ANALYSIS_METHOD
        extraction.reviewed_by = None
        extraction.reviewed_at = None
        if user_id and not extraction.created_by:
            extraction.created_by = user_id
        db.commit()
        db.refresh(extraction)
        return extraction
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
