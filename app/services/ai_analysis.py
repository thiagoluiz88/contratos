from __future__ import annotations

from datetime import date
from typing import Any, Callable


HOSPITAL_ANALYSIS_VERSION = "1.0.0"
HOSPITAL_ANALYSIS_NAME = "Analise Inteligente de Contratos Hospitalares"

HOSPITAL_AI_PROFILE = """
Voce e um especialista senior em contratos hospitalares, faturamento hospitalar,
glosas, tabelas de remuneracao, OPME, materiais, medicamentos, honorarios medicos,
operadoras de saude, ANS, TISS/TUSS, CBHPM, SIMPRO, Brasindice e negociacao
contratual hospitalar.

Sua funcao e analisar contratos de prestacao de servicos hospitalares de forma
tecnica, critica e robusta, identificando riscos juridicos, financeiros,
operacionais e assistenciais. A analise deve ser clara, objetiva, profissional
e voltada para tomada de decisao da diretoria hospitalar.
""".strip()

GENERAL_INSTRUCTIONS = [
    "Leia integralmente o contrato enviado pelo usuario.",
    "Nao invente clausulas que nao estejam no contrato.",
    'Quando uma informacao nao estiver localizada, informe: "nao identificado no contrato analisado".',
    "Sempre que possivel, cite a clausula, item, pagina ou trecho correspondente.",
    "Classifique os riscos em: baixo, medio, alto ou critico.",
    "Indique impactos financeiros e operacionais sempre que aplicavel.",
    "Ao final, gere um parecer executivo com recomendacao: aprovar, aprovar com ressalvas, renegociar ou nao aprovar.",
]

REQUIRED_RESPONSE_STRUCTURE = [
    "1. Resumo executivo do contrato",
    "2. Identificacao das partes e vigencia",
    "3. Objeto contratual",
    "4. Analise das clausulas contratuais",
    "5. Analise das tabelas de remuneracao",
    "6. Materiais, medicamentos e OPME",
    "7. Prazos de faturamento, pagamento e recurso de glosa",
    "8. Multas, penalidades e rescisao",
    "9. Reajuste contratual",
    "10. Obrigacoes regulatorias e assistenciais",
    "11. Riscos encontrados",
    "12. Pontos favoraveis ao hospital",
    "13. Pontos desfavoraveis ao hospital",
    "14. Recomendacoes de renegociacao",
    "15. Parecer final",
]

RISK_DEFINITIONS = {
    "baixo": "Clausula clara, equilibrada e com baixo impacto financeiro ou operacional.",
    "medio": "Clausula exige atencao, mas pode ser gerenciada com controle interno ou ajuste pontual.",
    "alto": "Clausula pode gerar prejuizo financeiro, glosa recorrente, inseguranca operacional ou desequilibrio contratual.",
    "critico": "Clausula altamente desfavoravel ao hospital, com risco relevante de perda financeira, judicializacao, inviabilidade contratual ou obrigacao excessiva.",
}

MAIN_PROMPT_TEMPLATE = """
Analise o contrato hospitalar abaixo de forma robusta e tecnica.

CONTRATO:
{{CONTRATO_TEXTO}}

Use obrigatoriamente os seguintes criterios:
1. Identifique partes, vigencia, objeto e abrangencia.
2. Analise clausulas contratuais relevantes.
3. Avalie prazos de faturamento, pagamento, recurso de glosa e resposta da operadora.
4. Analise multas, penalidades, rescisao e obrigacoes das partes.
5. Avalie reajuste, indice, data-base e risco de defasagem.
6. Analise tabelas de remuneracao: CBHPM, SIMPRO, Brasindice, tabela propria, PF, PMC, OPME e taxas.
7. Identifique riscos financeiros, operacionais, juridicos e assistenciais.
8. Classifique cada risco como baixo, medio, alto ou critico.
9. Informe pontos favoraveis e desfavoraveis ao hospital.
10. Sugira clausulas ou pontos para renegociacao.
11. Gere parecer final objetivo para diretoria.

Formato obrigatorio da resposta:

# ANALISE CONTRATUAL HOSPITALAR

## 1. Resumo executivo
## 2. Identificacao do contrato
## 3. Objeto e abrangencia assistencial
## 4. Analise das clausulas contratuais
## 5. Analise das tabelas e remuneracao
## 6. Prazos contratuais
## 7. Glosas e recursos
## 8. Reajuste contratual
## 9. Multas, penalidades e rescisao
## 10. Matriz de riscos
## 11. Pontos favoraveis ao hospital
## 12. Pontos desfavoraveis ao hospital
## 13. Sugestoes de renegociacao
## 14. Parecer final
""".strip()


def build_hospital_contract_prompt(contract_text: str) -> str:
    if not contract_text or len(contract_text.strip()) < 100:
        raise ValueError("Texto do contrato insuficiente para analise.")
    return MAIN_PROMPT_TEMPLATE.replace("{{CONTRATO_TEXTO}}", contract_text)


def build_executive_summary_prompt(contract_text: str) -> str:
    if not contract_text or len(contract_text.strip()) < 100:
        raise ValueError("Texto do contrato insuficiente para resumo executivo.")
    return f"""{HOSPITAL_AI_PROFILE}

Gere um resumo executivo para diretoria com linguagem objetiva, estrategica e financeira.
Limite a resposta a:
- Principais riscos
- Pontos favoraveis
- Impacto financeiro provavel
- Pontos que precisam ser renegociados
- Recomendacao final

CONTRATO:
{contract_text}
"""


def build_operator_email_prompt(contract_text: str) -> str:
    if not contract_text or len(contract_text.strip()) < 100:
        raise ValueError("Texto do contrato insuficiente para elaboracao do e-mail.")
    return f"""{HOSPITAL_AI_PROFILE}

Com base nos riscos identificados no contrato, elabore uma mensagem formal para a operadora
solicitando esclarecimentos e/ou renegociacao dos pontos criticos. A mensagem deve ser
profissional, objetiva e com tom de negociacao.

CONTRATO:
{contract_text}
"""


def build_contract_analysis(contract) -> dict[str, Any]:
    failures = []
    critical_clauses = []
    opportunities = []
    next_steps = []

    def add_failure(title, description, risk="Medio", impact="Medio", reference="Contrato", action=None):
        source_excerpt = _find_excerpt(contract.raw_text, [title, reference, description])
        item = {
            "title": title,
            "description": f"{description} Trecho relacionado: {source_excerpt}" if source_excerpt else description,
            "risk": risk,
            "risk_class": _risk_class(risk),
            "impact": impact,
            "reference": reference,
            "action": action or "Revisar redacao e negociar ajuste com a operadora.",
        }
        failures.append(item)
        if risk in {"Critico", "Alto"}:
            critical_clauses.append(item)

    def add_opportunity(title, description, priority="Media"):
        opportunities.append({"title": title, "description": description, "priority": priority})
        next_steps.append({"title": title, "priority": f"Prioridade {priority.lower()}"})

    if not contract.reajust_clause_exists:
        add_failure(
            "Clausula de reajuste nao identificada",
            "O contrato nao apresenta clausula clara de reajuste, periodicidade ou gatilho de aplicacao.",
            "Critico",
            "Alto",
            "Reajuste",
            "Inserir clausula com periodicidade, indice, data-base e forma de aplicacao.",
        )
        add_opportunity("Definir regra objetiva de reajuste", "Negociar indice, data-base e aplicacao automatica.", "Alta")
    elif not contract.reajust_index:
        add_failure(
            "Indice de reajuste nao definido",
            "Ha mencao a reajuste, mas sem indice claro para atualizacao dos valores.",
            "Alto",
            "Alto",
            "Reajuste",
            "Definir indice como IPCA, IGP-M ou outro criterio aceito pelas partes.",
        )

    if not contract.payment_term_days:
        add_failure("Prazo de pagamento nao identificado", "Nao foi encontrado prazo objetivo para pagamento das faturas.", "Alto", "Alto", "Pagamento")
        add_opportunity("Formalizar prazo de pagamento", "Definir prazo maximo apos protocolo da fatura ou nota fiscal.", "Alta")
    elif contract.payment_term_days > 45:
        add_failure("Prazo de pagamento longo", f"Prazo identificado de {contract.payment_term_days} dias, acima do ideal operacional.", "Medio", "Medio", "Pagamento")

    if not contract.billing_deadline_days:
        add_failure("Prazo de faturamento nao identificado", "O contrato nao deixa claro o prazo para apresentacao de faturamento.", "Medio", "Medio", "Faturamento")

    if not contract.glosa_deadline_days:
        add_failure("Prazo de glosa nao identificado", "Nao ha prazo claro para a operadora apresentar glosas.", "Alto", "Alto", "Glosas")
    if not contract.glosa_appeal_deadline_days:
        add_failure("Prazo recursal de glosa nao identificado", "O contrato nao informa prazo para contestacao ou recurso de glosa.", "Medio", "Medio", "Glosas")
    if contract.allows_glosa_unilateral:
        add_failure("Risco de glosa unilateral", "A redacao sugere possibilidade de glosa ampla ou unilateral pela operadora.", "Critico", "Alto", "Glosas")

    _add_hospital_alerts(contract, add_failure, add_opportunity)

    if not contract.start_date or not contract.end_date:
        add_failure("Vigencia incompleta", "Nao foram identificadas datas completas de inicio e termino da vigencia.", "Alto", "Medio", "Vigencia")
    elif contract.end_date < date.today():
        add_failure("Contrato vencido", "A data final de vigencia ja passou.", "Critico", "Alto", "Vigencia")

    if contract.auto_renewal:
        add_failure("Renovacao automatica exige controle", "Ha indicio de renovacao automatica; acompanhe prazo de manifestacao ou denuncia.", "Medio", "Medio", "Renovacao")

    if not contract.termination_notice_days:
        add_failure("Prazo de rescisao nao identificado", "Nao foi encontrado prazo de aviso previo para rescisao ou denuncia.", "Medio", "Medio", "Rescisao")

    if not contract.medical_fee_table:
        add_failure("Tabela medica nao identificada", "Nao foi localizada tabela de honorarios ou referencia assistencial.", "Alto", "Alto", "Tabelas")
        add_opportunity("Definir tabela medica", "Negociar referencia como CBHPM, tabela propria ou anexo de valores.", "Alta")
    if not contract.materials_table:
        add_failure("Tabela de materiais nao identificada", "Nao foi localizada referencia para materiais.", "Medio", "Medio", "Tabelas")
    if not contract.medicines_table:
        add_failure("Tabela de medicamentos nao identificada", "Nao foi localizada referencia para medicamentos.", "Medio", "Medio", "Tabelas")

    if not contract.payment_interest_clause:
        add_opportunity("Prever juros por atraso", "Incluir consequencia financeira para pagamento fora do prazo.", "Media")
    if not contract.payment_penalty_clause:
        add_opportunity("Prever multa por atraso", "Fortalecer protecao financeira em atrasos de pagamento.", "Media")
    add_opportunity("Revisao juridica preventiva", "Validar equilibrio entre obrigacoes, penalidades, rescisao e glosas.", "Alta")

    if not failures:
        add_opportunity("Manter monitoramento periodico", "Contrato bem estruturado; acompanhar vencimento, reajuste e aditivos.", "Media")

    score = _score_from_failures(failures)
    critical_count = sum(1 for item in failures if item["risk"] in {"Critico", "Alto"})
    final_opinion = _final_opinion(score, critical_count)
    recommendation = _recommendation(score, critical_count)
    contract_text = contract.raw_text or ""

    return {
        "version": HOSPITAL_ANALYSIS_VERSION,
        "name": HOSPITAL_ANALYSIS_NAME,
        "profile": HOSPITAL_AI_PROFILE,
        "instructions": GENERAL_INSTRUCTIONS,
        "required_structure": REQUIRED_RESPONSE_STRUCTURE,
        "risk_definitions": RISK_DEFINITIONS,
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
            {"label": "Equilibrio contratual", "score": _dimension_score(score, contract.termination_notice_days, not contract.allows_glosa_unilateral)},
            {"label": "Seguranca juridica", "score": _dimension_score(score, contract.start_date, contract.end_date, contract.termination_notice_days)},
            {"label": "Clareza e objetividade", "score": _dimension_score(score, contract.raw_text, contract.contract_object)},
            {"label": "Protecao financeira", "score": _dimension_score(score, contract.payment_term_days, contract.payment_interest_clause, contract.payment_penalty_clause)},
            {"label": "Tabelas e reajuste", "score": _dimension_score(score, contract.medical_fee_table, contract.reajust_index, contract.reajust_frequency)},
        ],
        "tables": [
            {"label": "Tabela medica", "value": _join_value(contract.medical_fee_table, contract.medical_fee_table_version)},
            {"label": "Diarias e taxas", "value": contract.daily_rate_table or "Nao identificado"},
            {"label": "Materiais", "value": _join_value(contract.materials_table, contract.materials_table_version)},
            {"label": "Medicamentos", "value": _join_value(contract.medicines_table, contract.medicines_table_version)},
            {"label": "OPME", "value": _opme_status(contract.raw_text)},
        ],
        "legal_points": [
            {"label": "Vigencia", "value": _date_range(contract.start_date, contract.end_date)},
            {"label": "Rescisao", "value": f"{contract.termination_notice_days} dias de aviso" if contract.termination_notice_days else "Prazo nao identificado"},
            {"label": "Glosas", "value": contract.glosa_clause_summary or "Criterios nao identificados"},
            {"label": "Pagamento", "value": f"{contract.payment_term_days} dias" if contract.payment_term_days else "Prazo nao identificado"},
            {"label": "Reajuste", "value": contract.reajust_clause_summary or contract.reajust_index or "Regra nao identificada"},
        ],
        "deadlines": _deadline_rows(contract),
        "risk_matrix": _risk_matrix(failures),
        "director_summary": _director_summary(contract, failures, opportunities, score, final_opinion),
        "final_opinion": final_opinion,
        "recommendation": recommendation,
        "ai_prompt": build_hospital_contract_prompt(contract_text) if len(contract_text.strip()) >= 100 else None,
        "executive_summary_prompt": build_executive_summary_prompt(contract_text) if len(contract_text.strip()) >= 100 else None,
        "operator_email_prompt": build_operator_email_prompt(contract_text) if len(contract_text.strip()) >= 100 else None,
        "document_excerpt": _excerpt(contract.raw_text),
    }


def persist_contract_analysis(db, contract, file_id: int | None = None, created_by: str | None = None):
    from app.models import AIAnalysis, ContractIssue, NegotiationOpportunity

    analysis = build_contract_analysis(contract)
    dimensions = {item["label"]: item["score"] for item in analysis["dimensions"]}
    record = AIAnalysis(
        contract_id=contract.id,
        file_id=file_id,
        status="completed",
        score_total=analysis["score"],
        score_balance=dimensions.get("Equilibrio contratual"),
        score_legal_security=dimensions.get("Seguranca juridica"),
        score_clarity=dimensions.get("Clareza e objetividade"),
        score_financial_protection=dimensions.get("Protecao financeira"),
        score_compliance=analysis["compliance"],
        failures_count=analysis["failures_count"],
        critical_clauses_count=analysis["critical_count"],
        opportunities_count=analysis["opportunities_count"],
        executive_summary=analysis["director_summary"],
        recommendation=analysis["recommendation"],
        raw_result=analysis,
        model_name=f"hospital-analysis-script-{HOSPITAL_ANALYSIS_VERSION}",
        created_by=created_by,
    )
    db.add(record)
    db.flush()

    for item in analysis["failures"]:
        db.add(
            ContractIssue(
                analysis_id=record.id,
                contract_id=contract.id,
                title=item["title"],
                description=item["description"],
                category=item["reference"],
                risk_level=item["risk"],
                impact_level=item["impact"],
                reference=item["reference"],
                recommended_action=item["action"],
            )
        )

    for item in analysis["opportunities"]:
        db.add(
            NegotiationOpportunity(
                analysis_id=record.id,
                contract_id=contract.id,
                title=item["title"],
                description=item["description"],
                priority=item["priority"],
                potential_impact="Financeiro/operacional",
                recommended_action=item["description"],
            )
        )

    return record


def _add_hospital_alerts(contract, add_failure: Callable, add_opportunity: Callable) -> None:
    text = (contract.raw_text or "").lower()

    if contract.reajust_clause_exists and not contract.reajust_index and _has_any(text, ["livre negociacao", "comum acordo"]):
        add_failure(
            "Reajuste apenas por livre negociacao",
            "A redacao indica reajuste dependente de negociacao futura, sem garantia de atualizacao anual.",
            "Alto",
            "Alto",
            "Reajuste",
            "Negociar indice objetivo, periodicidade anual, data-base e aplicacao sobre tabelas anexas.",
        )

    if _has_any(text, ["opme", "ortese", "protese", "materiais especiais"]) and not _has_any(text, ["taxa administrativa", "taxa de administracao"]):
        add_failure(
            "OPME sem taxa administrativa identificada",
            "Ha mencao a OPME ou materiais especiais, mas nao foi localizada taxa administrativa.",
            "Alto",
            "Alto",
            "OPME",
            "Prever taxa administrativa sobre OPME, regra de nota fiscal, autorizacao previa e rastreabilidade.",
        )
        add_opportunity("Renegociar taxa de OPME", "Incluir percentual ou taxa administrativa para cobrir custos operacionais.", "Alta")

    if _has_any(text, ["medicamento restrito", "medicamento de uso restrito", "alto custo"]) and _has_any(text, ["medicamento comum", "pmc"]):
        add_failure(
            "Medicamentos restritos tratados como medicamentos comuns",
            "A forma de remuneracao pode nao cobrir custo real de medicamentos restritos ou de alto custo.",
            "Alto",
            "Alto",
            "Medicamentos",
            "Separar regra para medicamentos restritos, alto custo, quimioterapicos, fracionamento e diluicao.",
        )

    if _has_any(text, ["auditoria"]) and not contract.payment_term_days:
        add_failure(
            "Pagamento condicionado a auditoria sem prazo",
            "Ha referencia a auditoria, mas nao foi identificado prazo objetivo para pagamento.",
            "Critico",
            "Alto",
            "Pagamento",
            "Fixar prazo maximo de auditoria, prazo de pagamento e consequencia para atraso.",
        )


def _deadline_rows(contract) -> list[dict[str, str]]:
    return [
        {
            "type": "Faturamento",
            "deadline": f"{contract.billing_deadline_days} dias" if contract.billing_deadline_days else "Nao identificado",
            "impact": "Risco de glosa administrativa se o prazo for curto ou ausente.",
            "risk": "Medio" if contract.billing_deadline_days else "Alto",
            "recommendation": "Definir prazo operacional compativel com fechamento de contas.",
        },
        {
            "type": "Pagamento",
            "deadline": f"{contract.payment_term_days} dias" if contract.payment_term_days else "Nao identificado",
            "impact": "Afeta fluxo de caixa e previsibilidade financeira.",
            "risk": "Alto" if not contract.payment_term_days or contract.payment_term_days > 45 else "Medio",
            "recommendation": "Prever prazo maximo apos protocolo da fatura e penalidade por atraso.",
        },
        {
            "type": "Recurso de glosa",
            "deadline": f"{contract.glosa_appeal_deadline_days} dias" if contract.glosa_appeal_deadline_days else "Nao identificado",
            "impact": "Pode reduzir recuperacao de valores glosados.",
            "risk": "Medio" if not contract.glosa_appeal_deadline_days else "Baixo",
            "recommendation": "Formalizar prazo para recurso, resposta e pagamento da glosa revertida.",
        },
        {
            "type": "Resposta da operadora a glosa",
            "deadline": f"{contract.glosa_response_deadline_days} dias" if contract.glosa_response_deadline_days else "Nao identificado",
            "impact": "Valores podem ficar pendentes por tempo indeterminado.",
            "risk": "Alto" if not contract.glosa_response_deadline_days else "Medio",
            "recommendation": "Incluir prazo de resposta e pagamento da glosa acatada.",
        },
    ]


def _risk_matrix(failures: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "risk": item["title"],
            "area": item["reference"],
            "classification": item["risk"],
            "impact": item["impact"],
            "recommendation": item["action"],
        }
        for item in failures
    ]


def _director_summary(contract, failures: list[dict[str, Any]], opportunities: list[dict[str, Any]], score: int, final_opinion: str) -> str:
    top_risks = failures[:3]
    top_opportunities = opportunities[:3]
    risks_text = "; ".join(item["title"] for item in top_risks) or "sem riscos relevantes identificados"
    opportunities_text = "; ".join(item["title"] for item in top_opportunities) or "manter monitoramento contratual"
    operator = contract.operator_name or "operadora nao informada"
    return (
        f"Contrato {contract.contract_name} da {operator} com score {score}/100. "
        f"Principais riscos: {risks_text}. "
        f"Pontos de negociacao: {opportunities_text}. "
        f"Parecer final: {final_opinion}."
    )


def _risk_class(risk: str) -> str:
    return {"Critico": "critical", "Alto": "high", "Medio": "medium", "Baixo": "low"}.get(risk, "medium")


def _score_from_failures(failures: list[dict[str, Any]]) -> int:
    penalty = 0
    for item in failures:
        penalty += {"Critico": 18, "Alto": 12, "Medio": 7, "Baixo": 3}.get(item["risk"], 4)
    return max(18, min(96, 100 - penalty))


def _risk_label(score: int) -> str:
    if score >= 80:
        return "Baixo"
    if score >= 60:
        return "Moderado"
    if score >= 40:
        return "Alto"
    return "Critico"


def _dimension_score(base: int, *signals) -> int:
    bonus = sum(8 for signal in signals if signal)
    missing = sum(7 for signal in signals if not signal)
    return max(20, min(96, base + bonus - missing))


def _join_value(*parts) -> str:
    values = [str(part) for part in parts if part]
    return " ".join(values) if values else "Nao identificado"


def _date_range(start, end) -> str:
    if start and end:
        return f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}"
    return "Vigencia incompleta"


def _excerpt(text: str | None) -> str:
    if not text:
        return "Texto integral nao disponivel para exibicao."
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
        return "Recomenda-se revisao juridica antes de assinar ou renovar. Priorize reajuste, glosas, pagamento, rescisao e tabelas."
    if critical_count:
        return "Contrato utilizavel com ressalvas. Negocie os pontos criticos antes da renovacao ou novo aditivo."
    return "Contrato com boa estrutura geral. Mantenha monitoramento de vencimento, reajuste e obrigacoes operacionais."


def _final_opinion(score: int, critical_count: int) -> str:
    if critical_count >= 4 or score < 45:
        return "nao aprovar"
    if critical_count >= 2 or score < 65:
        return "renegociar"
    if critical_count or score < 80:
        return "aprovar com ressalvas"
    return "aprovar"


def _opme_status(text: str | None) -> str:
    lowered = (text or "").lower()
    if not _has_any(lowered, ["opme", "ortese", "protese", "materiais especiais"]):
        return "Nao identificado"
    if _has_any(lowered, ["taxa administrativa", "taxa de administracao"]):
        return "OPME com regra/taxa administrativa identificada"
    return "OPME mencionada sem taxa administrativa identificada"


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)
