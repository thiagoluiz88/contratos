from __future__ import annotations

from datetime import date
from typing import Any


def build_contract_analysis(contract) -> dict[str, Any]:
    failures = []
    critical_clauses = []
    opportunities = []
    next_steps = []

    def add_failure(title, description, risk="Médio", impact="Médio", reference="Contrato", action=None):
        source_excerpt = _find_excerpt(contract.raw_text, [title, reference, description])
        item = {
            "title": title,
            "description": f"{description} Trecho relacionado: {source_excerpt}" if source_excerpt else description,
            "risk": risk,
            "risk_class": _risk_class(risk),
            "impact": impact,
            "reference": reference,
            "action": action or "Revisar redação e negociar ajuste com a operadora.",
        }
        failures.append(item)
        if risk in {"Crítico", "Alto"}:
            critical_clauses.append(item)

    def add_opportunity(title, description, priority="Média"):
        opportunities.append({"title": title, "description": description, "priority": priority})
        next_steps.append({"title": title, "priority": f"Prioridade {priority.lower()}"})

    if not contract.reajust_clause_exists:
        add_failure(
            "Cláusula de reajuste não identificada",
            "O contrato não apresenta cláusula clara de reajuste, periodicidade ou gatilho de aplicação.",
            "Crítico",
            "Alto",
            "Reajuste",
            "Inserir cláusula com periodicidade, índice, data-base e forma de aplicação.",
        )
        add_opportunity("Definir regra objetiva de reajuste", "Negociar índice, data-base e aplicação automática.", "Alta")
    elif not contract.reajust_index:
        add_failure(
            "Índice de reajuste não definido",
            "Há menção a reajuste, mas sem índice claro para atualização dos valores.",
            "Alto",
            "Alto",
            "Reajuste",
            "Definir índice como IPCA, IGP-M ou outro critério aceito pelas partes.",
        )

    if not contract.payment_term_days:
        add_failure("Prazo de pagamento não identificado", "Não foi encontrado prazo objetivo para pagamento das faturas.", "Alto", "Alto", "Pagamento")
        add_opportunity("Formalizar prazo de pagamento", "Definir prazo máximo após protocolo da fatura ou nota fiscal.", "Alta")
    elif contract.payment_term_days > 45:
        add_failure("Prazo de pagamento longo", f"Prazo identificado de {contract.payment_term_days} dias, acima do ideal operacional.", "Médio", "Médio", "Pagamento")

    if not contract.billing_deadline_days:
        add_failure("Prazo de faturamento não identificado", "O contrato não deixa claro o prazo para apresentação de faturamento.", "Médio", "Médio", "Faturamento")

    if not contract.glosa_deadline_days:
        add_failure("Prazo de glosa não identificado", "Não há prazo claro para a operadora apresentar glosas.", "Alto", "Alto", "Glosas")
    if not contract.glosa_appeal_deadline_days:
        add_failure("Prazo recursal de glosa não identificado", "O contrato não informa prazo para contestação ou recurso de glosa.", "Médio", "Médio", "Glosas")
    if contract.allows_glosa_unilateral:
        add_failure("Risco de glosa unilateral", "A redação sugere possibilidade de glosa ampla ou unilateral pela operadora.", "Crítico", "Alto", "Glosas")

    if not contract.start_date or not contract.end_date:
        add_failure("Vigência incompleta", "Não foram identificadas datas completas de início e término da vigência.", "Alto", "Médio", "Vigência")
    elif contract.end_date < date.today():
        add_failure("Contrato vencido", "A data final de vigência já passou.", "Crítico", "Alto", "Vigência")

    if contract.auto_renewal:
        add_failure("Renovação automática exige controle", "Há indício de renovação automática; acompanhe prazo de manifestação ou denúncia.", "Médio", "Médio", "Renovação")

    if not contract.termination_notice_days:
        add_failure("Prazo de rescisão não identificado", "Não foi encontrado prazo de aviso prévio para rescisão ou denúncia.", "Médio", "Médio", "Rescisão")

    if not contract.medical_fee_table:
        add_failure("Tabela médica não identificada", "Não foi localizada tabela de honorários ou referência assistencial.", "Alto", "Alto", "Tabelas")
        add_opportunity("Definir tabela médica", "Negociar referência como CBHPM, tabela própria ou anexo de valores.", "Alta")
    if not contract.materials_table:
        add_failure("Tabela de materiais não identificada", "Não foi localizada referência para materiais.", "Médio", "Médio", "Tabelas")
    if not contract.medicines_table:
        add_failure("Tabela de medicamentos não identificada", "Não foi localizada referência para medicamentos.", "Médio", "Médio", "Tabelas")

    if not contract.payment_interest_clause:
        add_opportunity("Prever juros por atraso", "Incluir consequência financeira para pagamento fora do prazo.", "Média")
    if not contract.payment_penalty_clause:
        add_opportunity("Prever multa por atraso", "Fortalecer proteção financeira em atrasos de pagamento.", "Média")
    add_opportunity("Revisão jurídica preventiva", "Validar equilíbrio entre obrigações, penalidades, rescisão e glosas.", "Alta")

    if not failures:
        add_opportunity("Manter monitoramento periódico", "Contrato bem estruturado; acompanhar vencimento, reajuste e aditivos.", "Média")

    score = _score_from_failures(failures)
    critical_count = sum(1 for item in failures if item["risk"] in {"Crítico", "Alto"})

    return {
        "score": score,
        "risk_label": _risk_label(score),
        "failures": failures,
        "critical_clauses": critical_clauses[:8],
        "opportunities": opportunities[:8],
        "next_steps": next_steps[:6],
        "failures_count": len(failures),
        "critical_count": critical_count,
        "opportunities_count": len(opportunities),
        "compliance": max(35, min(96, score + 12)),
        "dimensions": [
            {"label": "Equilíbrio contratual", "score": _dimension_score(score, contract.termination_notice_days, not contract.allows_glosa_unilateral)},
            {"label": "Segurança jurídica", "score": _dimension_score(score, contract.start_date, contract.end_date, contract.termination_notice_days)},
            {"label": "Clareza e objetividade", "score": _dimension_score(score, contract.raw_text, contract.contract_object)},
            {"label": "Proteção financeira", "score": _dimension_score(score, contract.payment_term_days, contract.payment_interest_clause, contract.payment_penalty_clause)},
            {"label": "Tabelas e reajuste", "score": _dimension_score(score, contract.medical_fee_table, contract.reajust_index, contract.reajust_frequency)},
        ],
        "tables": [
            {"label": "Tabela médica", "value": _join_value(contract.medical_fee_table, contract.medical_fee_table_version)},
            {"label": "Diárias e taxas", "value": contract.daily_rate_table or "Não identificado"},
            {"label": "Materiais", "value": _join_value(contract.materials_table, contract.materials_table_version)},
            {"label": "Medicamentos", "value": _join_value(contract.medicines_table, contract.medicines_table_version)},
        ],
        "legal_points": [
            {"label": "Vigência", "value": _date_range(contract.start_date, contract.end_date)},
            {"label": "Rescisão", "value": f"{contract.termination_notice_days} dias de aviso" if contract.termination_notice_days else "Prazo não identificado"},
            {"label": "Glosas", "value": contract.glosa_clause_summary or "Critérios não identificados"},
            {"label": "Pagamento", "value": f"{contract.payment_term_days} dias" if contract.payment_term_days else "Prazo não identificado"},
            {"label": "Reajuste", "value": contract.reajust_clause_summary or contract.reajust_index or "Regra não identificada"},
        ],
        "recommendation": _recommendation(score, critical_count),
        "document_excerpt": _excerpt(contract.raw_text),
    }


def _risk_class(risk: str) -> str:
    return {"Crítico": "critical", "Alto": "high", "Médio": "medium"}.get(risk, "medium")


def _score_from_failures(failures: list[dict[str, Any]]) -> int:
    penalty = 0
    for item in failures:
        penalty += {"Crítico": 18, "Alto": 12, "Médio": 7}.get(item["risk"], 4)
    return max(18, min(96, 100 - penalty))


def _risk_label(score: int) -> str:
    if score >= 80:
        return "Baixo"
    if score >= 60:
        return "Moderado"
    if score >= 40:
        return "Alto"
    return "Crítico"


def _dimension_score(base: int, *signals) -> int:
    bonus = sum(8 for signal in signals if signal)
    missing = sum(7 for signal in signals if not signal)
    return max(20, min(96, base + bonus - missing))


def _join_value(*parts) -> str:
    values = [str(part) for part in parts if part]
    return " ".join(values) if values else "Não identificado"


def _date_range(start, end) -> str:
    if start and end:
        return f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}"
    return "Vigência incompleta"


def _excerpt(text: str | None) -> str:
    if not text:
        return "Texto integral não disponível para exibição."
    return text[:1200].strip()


def _find_excerpt(text: str | None, terms: list[str]) -> str | None:
    if not text:
        return None

    lowered = text.lower()
    candidates = []
    for term in terms:
        for word in str(term).replace("-", " ").split():
            clean = word.strip(".,;:()[]{}").lower()
            if len(clean) >= 5:
                candidates.append(clean)

    for candidate in candidates:
        index = lowered.find(candidate)
        if index >= 0:
            start = max(0, index - 90)
            end = min(len(text), index + 220)
            excerpt = " ".join(text[start:end].split())
            return f"...{excerpt}..."
    return None


def _recommendation(score: int, critical_count: int) -> str:
    if critical_count >= 3 or score < 50:
        return "Recomenda-se revisão jurídica antes de assinar ou renovar. Priorize reajuste, glosas, pagamento, rescisão e tabelas."
    if critical_count:
        return "Contrato utilizável com ressalvas. Negocie os pontos críticos antes da renovação ou novo aditivo."
    return "Contrato com boa estrutura geral. Mantenha monitoramento de vencimento, reajuste e obrigações operacionais."
