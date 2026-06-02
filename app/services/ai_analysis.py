from __future__ import annotations

from datetime import date
from typing import Any, Callable


HOSPITAL_ANALYSIS_VERSION = "1.1.0"
HOSPITAL_ANALYSIS_NAME = "Analise Inteligente de Contratos Hospitalares"

HOSPITAL_AI_PROFILE = """
Voce e um especialista senior em contratos hospitalares, faturamento hospitalar,
glosas, tabelas de remuneracao, OPME, materiais, medicamentos, honorarios medicos,
operadoras de saude, ANS, TISS/TUSS, CBHPM, SIMPRO, Brasindice e negociacao
contratual hospitalar.

Sua funcao e analisar contratos de prestacao de servicos hospitalares sempre
sob a otica de protecao da unidade hospitalar. A analise deve ser tecnica,
critica e robusta, identificando riscos juridicos, financeiros, operacionais
e assistenciais que possam gerar perda financeira, glosa, desequilibrio
contratual, inseguranca juridica ou obrigacoes excessivas para o hospital.
""".strip()

NOT_IDENTIFIED = "não identificado no documento"

GENERAL_INSTRUCTIONS = [
    "Leia integralmente o contrato enviado pelo usuario.",
    "Nao invente clausulas, prazos, indices, regras, valores ou responsabilidades que nao estejam no contrato.",
    f'Quando uma informacao nao estiver localizada, informe exatamente: "{NOT_IDENTIFIED}".',
    "Sempre que possivel, cite a clausula, item, pagina ou trecho correspondente.",
    "Classifique a gravidade dos riscos em: baixo, medio, alto ou critico.",
    "Indique impactos financeiros e operacionais sempre que aplicavel.",
    "Avalie o contrato pela perspectiva do hospital, nao pela perspectiva da operadora.",
    "Ao final, gere parecer executivo com conclusao: aprovar, aprovar com ressalvas, renegociar ou recusar.",
]

REQUIRED_RESPONSE_STRUCTURE = [
    "1. Resumo executivo do contrato",
    "2. Riscos de pagamento",
    "3. Riscos de glosas",
    "4. Riscos de reajuste",
    "5. Materiais, medicamentos e OPME",
    "6. Pacotes, itens inclusos/exclusos e intercorrencias",
    "7. Rescisao, suspensao e inadimplencia",
    "8. Risco juridico e equilibrio contratual",
    "9. Riscos encontrados com impacto financeiro, juridico e operacional",
    "10. Pontos favoraveis ao hospital",
    "11. Pontos desfavoraveis ao hospital",
    "12. Recomendacoes de negociacao",
    "13. Clausulas sugeridas",
    "14. Classificacao geral: baixo, medio, alto ou critico",
    "15. Conclusao: aprovar, aprovar com ressalvas, renegociar ou recusar",
]

RISK_DEFINITIONS = {
    "baixo": "Clausula clara, equilibrada e com baixo impacto financeiro ou operacional.",
    "medio": "Clausula exige atencao, mas pode ser gerenciada com controle interno ou ajuste pontual.",
    "alto": "Clausula pode gerar prejuizo financeiro, glosa recorrente, inseguranca operacional ou desequilibrio contratual.",
    "critico": "Clausula altamente desfavoravel ao hospital, com risco relevante de perda financeira, judicializacao, inviabilidade contratual ou obrigacao excessiva.",
}

MANDATORY_REVIEW_CHECKLIST = [
    {
        "area": "Pagamento",
        "items": [
            "prazo de pagamento",
            "ausencia de multa/juros por atraso",
            "retencoes indevidas",
            "forma de faturamento",
        ],
    },
    {
        "area": "Glosas",
        "items": [
            "prazo de recurso",
            "prazo de resposta da operadora",
            "glosa sem justificativa",
            "perda de prazo",
            "desconto unilateral",
        ],
    },
    {
        "area": "Reajuste",
        "items": [
            "indice previsto",
            "data-base",
            "ausencia de reajuste",
            "reajuste condicionado a operadora",
        ],
    },
    {
        "area": "Materiais, medicamentos e OPME",
        "items": [
            "referencia SIMPRO",
            "referencia Brasindice",
            "NF + taxa",
            "redutores",
            "ausencia de regra clara",
        ],
    },
    {
        "area": "Pacotes",
        "items": [
            "itens inclusos e exclusos",
            "complicacoes",
            "intercorrencias",
            "permanencia acima do previsto",
            "migracao para tabela propria",
        ],
    },
    {
        "area": "Rescisao",
        "items": [
            "prazo de aviso",
            "penalidades",
            "suspensao de atendimento",
            "inadimplencia",
        ],
    },
    {
        "area": "Risco juridico",
        "items": [
            "clausulas abusivas",
            "obrigacao unilateral",
            "ausencia de equilibrio contratual",
            "responsabilidades excessivas para o hospital",
        ],
    },
]


MAIN_PROMPT_TEMPLATE = """
Analise o contrato hospitalar abaixo de forma robusta e tecnica, sempre sob a
otica de protecao da unidade hospitalar.

CONTRATO:
{{CONTRATO_TEXTO}}

Regras obrigatorias:
- Nao invente informacoes que nao estejam no contrato.
- Se uma clausula, prazo, regra, indice, taxa ou responsabilidade estiver ausente,
  escreva exatamente: "não identificado no documento".
- Nao presuma pratica de mercado como se estivesse contratada.
- Aponte ausencias como risco quando a ausencia reduzir a protecao do hospital.
- Cite clausula, item, pagina ou trecho quando existir base no texto.

Checklist obrigatorio de avaliacao:
1. Pagamento: prazo de pagamento, ausencia de multa/juros por atraso, retencoes indevidas e forma de faturamento.
2. Glosas: prazo de recurso, prazo de resposta da operadora, glosa sem justificativa, perda de prazo e desconto unilateral.
3. Reajuste: indice previsto, data-base, ausencia de reajuste e reajuste condicionado a operadora.
4. Materiais, medicamentos e OPME: SIMPRO, Brasindice, NF + taxa, redutores e ausencia de regra clara.
5. Pacotes: itens inclusos/exclusos, complicacoes, intercorrencias, permanencia acima do previsto e migracao para tabela propria.
6. Rescisao: prazo de aviso, penalidades, suspensao de atendimento e inadimplencia.
7. Risco juridico: clausulas abusivas, obrigacao unilateral, ausencia de equilibrio contratual e responsabilidades excessivas para o hospital.

Formato obrigatorio da resposta:

# ANALISE CONTRATUAL HOSPITALAR

## 1. Resumo executivo
## 2. Riscos encontrados
## 3. Impacto financeiro
## 4. Impacto juridico
## 5. Impacto operacional
## 6. Pagamento
## 7. Glosas
## 8. Reajuste
## 9. Materiais, medicamentos e OPME
## 10. Pacotes
## 11. Rescisao
## 12. Pontos favoraveis ao hospital
## 13. Pontos desfavoraveis ao hospital
## 14. Recomendacoes de negociacao
## 15. Clausulas sugeridas
## 16. Classificacao geral
## 17. Conclusao
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
    suggested_clauses = []

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

    def add_suggested_clause(title, text, area):
        suggested_clauses.append({"title": title, "text": text, "area": area})

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
        add_suggested_clause(
            "Clausula de reajuste anual",
            "Os valores contratados serao reajustados anualmente, na data-base definida entre as partes, por indice objetivo expressamente previsto no contrato, vedada a aplicacao condicionada exclusivamente a aprovacao unilateral da operadora.",
            "Reajuste",
        )
    elif not contract.reajust_index:
        add_failure(
            "Indice de reajuste nao definido",
            "Ha mencao a reajuste, mas sem indice claro para atualizacao dos valores.",
            "Alto",
            "Alto",
            "Reajuste",
            "Definir indice como IPCA, IGP-M ou outro criterio aceito pelas partes.",
        )
    if contract.reajust_clause_exists and not _has_any((contract.raw_text or "").lower(), ["data-base", "data base", "mes base"]):
        add_failure(
            "Data-base de reajuste nao identificada",
            f"A data-base do reajuste esta {NOT_IDENTIFIED}, o que pode gerar defasagem e discussao futura sobre o periodo de aplicacao.",
            "Alto",
            "Alto",
            "Reajuste",
            "Inserir data-base objetiva, periodicidade anual e gatilho automatico de aplicacao.",
        )

    if not contract.payment_term_days:
        add_failure("Prazo de pagamento nao identificado", f"O prazo objetivo para pagamento das faturas esta {NOT_IDENTIFIED}.", "Alto", "Alto", "Pagamento")
        add_opportunity("Formalizar prazo de pagamento", "Definir prazo maximo apos protocolo da fatura ou nota fiscal.", "Alta")
        add_suggested_clause(
            "Clausula de prazo de pagamento",
            "A operadora devera efetuar o pagamento integral das faturas em prazo certo contado do protocolo da fatura e/ou nota fiscal, com incidencia de multa e juros em caso de atraso.",
            "Pagamento",
        )
    elif contract.payment_term_days > 45:
        add_failure("Prazo de pagamento longo", f"Prazo identificado de {contract.payment_term_days} dias, acima do ideal operacional.", "Medio", "Medio", "Pagamento")

    if not contract.billing_deadline_days:
        add_failure("Forma/prazo de faturamento nao identificados", f"A forma de faturamento ou prazo para apresentacao de faturamento esta {NOT_IDENTIFIED}.", "Medio", "Medio", "Faturamento")
    if not contract.payment_interest_clause:
        add_failure(
            "Juros por atraso nao identificados",
            f"A previsao de juros por atraso esta {NOT_IDENTIFIED}. A ausencia reduz a protecao financeira do hospital.",
            "Medio",
            "Medio",
            "Pagamento",
            "Inserir juros de mora por atraso de pagamento.",
        )
    if not contract.payment_penalty_clause:
        add_failure(
            "Multa por atraso nao identificada",
            f"A multa por atraso esta {NOT_IDENTIFIED}. A ausencia enfraquece a cobranca contra inadimplencia da operadora.",
            "Medio",
            "Medio",
            "Pagamento",
            "Inserir multa moratoria sobre valores pagos em atraso.",
        )

    if not contract.glosa_deadline_days:
        add_failure("Prazo de glosa nao identificado", f"O prazo para a operadora apresentar glosas esta {NOT_IDENTIFIED}.", "Alto", "Alto", "Glosas")
    if not contract.glosa_appeal_deadline_days:
        add_failure("Prazo recursal de glosa nao identificado", f"O prazo para contestacao ou recurso de glosa esta {NOT_IDENTIFIED}.", "Medio", "Medio", "Glosas")
        add_suggested_clause(
            "Clausula de recurso de glosa",
            "Toda glosa devera ser apresentada com justificativa individualizada, garantindo-se ao hospital prazo adequado para recurso e prazo certo para resposta da operadora.",
            "Glosas",
        )
    if not contract.glosa_response_deadline_days:
        add_failure(
            "Prazo de resposta da operadora a glosa nao identificado",
            f"O prazo para resposta da operadora aos recursos de glosa esta {NOT_IDENTIFIED}.",
            "Alto",
            "Alto",
            "Glosas",
            "Prever prazo maximo para resposta e pagamento dos valores revertidos.",
        )
    if contract.allows_glosa_unilateral:
        add_failure("Risco de glosa unilateral", "A redacao sugere possibilidade de glosa ampla ou unilateral pela operadora.", "Critico", "Alto", "Glosas")

    _add_mandatory_contract_alerts(contract, add_failure, add_opportunity, add_suggested_clause)
    _add_hospital_alerts(contract, add_failure, add_opportunity)

    if not contract.start_date or not contract.end_date:
        add_failure("Vigencia incompleta", "Nao foram identificadas datas completas de inicio e termino da vigencia.", "Alto", "Medio", "Vigencia")
    elif contract.end_date < date.today():
        add_failure("Contrato vencido", "A data final de vigencia ja passou.", "Critico", "Alto", "Vigencia")

    if contract.auto_renewal:
        add_failure("Renovacao automatica exige controle", "Ha indicio de renovacao automatica; acompanhe prazo de manifestacao ou denuncia.", "Medio", "Medio", "Renovacao")

    if not contract.termination_notice_days:
        add_failure("Prazo de rescisao nao identificado", f"O prazo de aviso previo para rescisao ou denuncia esta {NOT_IDENTIFIED}.", "Medio", "Medio", "Rescisao")
        add_suggested_clause(
            "Clausula de rescisao equilibrada",
            "A rescisao imotivada devera observar aviso previo minimo, preservacao da continuidade assistencial, tratamento dos pacientes em curso e pagamento integral dos servicos prestados.",
            "Rescisao",
        )

    if not contract.medical_fee_table:
        add_failure("Tabela medica nao identificada", "Nao foi localizada tabela de honorarios ou referencia assistencial.", "Alto", "Alto", "Tabelas")
        add_opportunity("Definir tabela medica", "Negociar referencia como CBHPM, tabela propria ou anexo de valores.", "Alta")
    if not contract.materials_table:
        add_failure("Regra de materiais nao identificada", f"A referencia para materiais, como SIMPRO ou NF + taxa, esta {NOT_IDENTIFIED}.", "Medio", "Medio", "Materiais/Medicamentos/OPME")
    if not contract.medicines_table:
        add_failure("Regra de medicamentos nao identificada", f"A referencia para medicamentos, como Brasindice, PMC/PF ou NF + taxa, esta {NOT_IDENTIFIED}.", "Medio", "Medio", "Materiais/Medicamentos/OPME")
        add_suggested_clause(
            "Clausula de materiais, medicamentos e OPME",
            "Materiais, medicamentos e OPME deverao possuir regra objetiva de remuneracao, com referencia expressa, previsao de NF + taxa quando aplicavel e vedacao a redutores nao pactuados.",
            "Materiais/Medicamentos/OPME",
        )
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
            {"label": "Diarias e taxas", "value": contract.daily_rate_table or NOT_IDENTIFIED},
            {"label": "Materiais", "value": _join_value(contract.materials_table, contract.materials_table_version)},
            {"label": "Medicamentos", "value": _join_value(contract.medicines_table, contract.medicines_table_version)},
            {"label": "OPME", "value": _opme_status(contract.raw_text)},
        ],
        "legal_points": [
            {"label": "Vigencia", "value": _date_range(contract.start_date, contract.end_date)},
            {"label": "Rescisao", "value": f"{contract.termination_notice_days} dias de aviso" if contract.termination_notice_days else NOT_IDENTIFIED},
            {"label": "Glosas", "value": contract.glosa_clause_summary or NOT_IDENTIFIED},
            {"label": "Pagamento", "value": f"{contract.payment_term_days} dias" if contract.payment_term_days else NOT_IDENTIFIED},
            {"label": "Reajuste", "value": contract.reajust_clause_summary or contract.reajust_index or NOT_IDENTIFIED},
        ],
        "deadlines": _deadline_rows(contract),
        "risk_matrix": _risk_matrix(failures),
        "mandatory_checklist": _mandatory_checklist_result(contract, failures),
        "suggested_clauses": suggested_clauses[:10],
        "financial_impact": _impact_summary(failures, ["Pagamento", "Faturamento", "Glosas", "Reajuste", "Materiais/Medicamentos/OPME", "Pacotes"]),
        "legal_impact": _impact_summary(failures, ["Risco juridico", "Rescisao", "Vigencia", "Renovacao"]),
        "operational_impact": _impact_summary(failures, ["Pacotes", "Faturamento", "Glosas", "OPME", "Materiais/Medicamentos/OPME"]),
        "favorable_points": _favorable_points(contract),
        "unfavorable_points": _unfavorable_points(failures),
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


def _add_mandatory_contract_alerts(contract, add_failure: Callable, add_opportunity: Callable, add_suggested_clause: Callable) -> None:
    text = (contract.raw_text or "").lower()

    if _has_any(text, ["retencao", "reter", "retenção", "compensacao", "compensação"]):
        add_failure(
            "Possivel retencao ou compensacao de valores",
            "O contrato menciona retencao, compensacao ou mecanismo semelhante. Verifique se ha autorizacao para desconto indevido de valores devidos ao hospital.",
            "Alto",
            "Alto",
            "Pagamento",
            "Limitar retencoes a hipoteses expressas, justificadas e previamente comunicadas, vedando descontos unilaterais.",
        )
    else:
        add_failure(
            "Retencoes indevidas nao tratadas",
            f"A regra que vede retencoes indevidas esta {NOT_IDENTIFIED}.",
            "Medio",
            "Medio",
            "Pagamento",
            "Inserir vedacao a retencoes, compensacoes e descontos nao pactuados.",
        )

    if _has_any(text, ["glosa sem justificativa", "sem justificativa", "desconto unilateral", "descontar unilateralmente"]):
        add_failure(
            "Risco de glosa sem justificativa ou desconto unilateral",
            "A redacao menciona glosa sem justificativa, desconto unilateral ou expressao equivalente.",
            "Critico",
            "Alto",
            "Glosas",
            "Exigir justificativa individualizada e processo de contestacao antes de qualquer desconto.",
        )
    elif not _has_any(text, ["justificativa da glosa", "glosa justificada", "motivo da glosa", "relatorio de glosa"]):
        add_failure(
            "Justificativa obrigatoria de glosa nao identificada",
            f"A obrigacao de justificar glosas esta {NOT_IDENTIFIED}.",
            "Alto",
            "Alto",
            "Glosas",
            "Prever que toda glosa seja motivada, documental e tecnicamente justificavel.",
        )

    if _has_any(text, ["redutor", "redutores", "desagio", "deságio"]):
        add_failure(
            "Redutores sobre materiais, medicamentos ou OPME",
            "O contrato menciona redutores/desagios, o que pode reduzir a remuneracao efetiva do hospital.",
            "Alto",
            "Alto",
            "Materiais/Medicamentos/OPME",
            "Excluir redutores unilaterais ou limitar sua aplicacao com base expressa e auditavel.",
        )
    else:
        add_failure(
            "Regra sobre redutores nao identificada",
            f"A existencia ou vedacao de redutores esta {NOT_IDENTIFIED}.",
            "Medio",
            "Medio",
            "Materiais/Medicamentos/OPME",
            "Prever expressamente que redutores so poderao ser aplicados se negociados em anexo.",
        )

    if _has_any(text, ["opme", "ortese", "protese", "materiais especiais"]):
        if not _has_any(text, ["simpro", "brasindice", "brasíndice", "nota fiscal", "nf + taxa", "nf mais taxa"]):
            add_failure(
                "OPME sem referencia objetiva de remuneracao",
                "Ha mencao a OPME ou materiais especiais, mas nao foi localizada referencia objetiva como SIMPRO, Brasindice ou NF + taxa.",
                "Critico",
                "Alto",
                "Materiais/Medicamentos/OPME",
                "Definir base de remuneracao de OPME, taxa administrativa, autorizacao e documentacao exigida.",
            )
    else:
        add_failure(
            "OPME nao identificado",
            f"A regra de OPME esta {NOT_IDENTIFIED}.",
            "Medio",
            "Medio",
            "Materiais/Medicamentos/OPME",
            "Incluir regra caso o hospital utilize OPME, materiais especiais ou medicamentos de alto custo.",
        )

    if _has_any(text, ["pacote", "pacotes", "diaria global", "diária global"]):
        if not _has_any(text, ["itens inclusos", "itens excluidos", "itens excluídos", "exclusoes", "exclusões"]):
            add_failure(
                "Pacotes sem itens inclusos/exclusos claros",
                "Ha mencao a pacote, mas itens inclusos e exclusos nao foram claramente identificados.",
                "Alto",
                "Alto",
                "Pacotes",
                "Detalhar inclusoes, exclusoes, OPME, medicamentos especiais, complicacoes e intercorrencias.",
            )
        for title, terms in {
            "Complicacoes em pacotes nao identificadas": ["complicacao", "complicações", "complicacoes"],
            "Intercorrencias em pacotes nao identificadas": ["intercorrencia", "intercorrências", "intercorrencias"],
            "Permanencia acima do previsto nao identificada": ["permanencia acima", "permanência acima", "diarias excedentes", "diárias excedentes"],
            "Migracao para tabela propria nao identificada": ["migração para tabela", "migracao para tabela", "tabela propria", "tabela própria"],
        }.items():
            if not _has_any(text, terms):
                add_failure(
                    title,
                    f"A regra correspondente em pacotes esta {NOT_IDENTIFIED}.",
                    "Alto",
                    "Medio",
                    "Pacotes",
                    "Prever tratamento expresso para excecoes de pacote e migracao para tabela aplicavel.",
                )
        add_suggested_clause(
            "Clausula de pacotes",
            "Pacotes deverao discriminar itens inclusos e exclusos, tratamento de complicacoes, intercorrencias, permanencia acima do previsto e migracao para tabela propria ou anexo vigente quando houver extrapolacao clinica.",
            "Pacotes",
        )
    else:
        add_failure(
            "Pacotes nao identificados no documento",
            f"As regras para pacotes, itens inclusos/exclusos, complicacoes e intercorrencias estao {NOT_IDENTIFIED}.",
            "Medio",
            "Medio",
            "Pacotes",
            "Confirmar se o contrato utiliza pacotes; se utilizar, anexar regras detalhadas.",
        )

    if _has_any(text, ["suspensao de atendimento", "suspensão de atendimento", "suspender atendimento"]):
        add_failure(
            "Suspensao de atendimento exige cautela",
            "Ha mencao a suspensao de atendimento. Verifique continuidade assistencial, pacientes em curso e comunicacao previa.",
            "Alto",
            "Alto",
            "Rescisao",
            "Prever transicao assistencial, comunicacao previa e pagamento de atendimentos ja prestados.",
        )
    else:
        add_failure(
            "Suspensao de atendimento nao identificada",
            f"A regra de suspensao de atendimento esta {NOT_IDENTIFIED}.",
            "Medio",
            "Medio",
            "Rescisao",
            "Definir regras para suspensao, inadimplencia, continuidade de pacientes internados e comunicacao previa.",
        )

    if not _has_any(text, ["inadimplencia", "inadimplência", "atraso de pagamento"]):
        add_failure(
            "Inadimplencia da operadora nao tratada",
            f"A regra para inadimplencia da operadora esta {NOT_IDENTIFIED}.",
            "Alto",
            "Alto",
            "Rescisao",
            "Prever consequencias para inadimplencia, cobranca, suspensao segura e rescisao.",
        )

    if _has_any(text, ["a exclusivo criterio", "exclusivo criterio da operadora", "unilateralmente", "sem anuencia do hospital"]):
        add_failure(
            "Obrigacao ou decisao unilateral da operadora",
            "A redacao sugere poder unilateral da operadora, o que pode causar desequilibrio contratual.",
            "Critico",
            "Alto",
            "Risco juridico",
            "Substituir poder unilateral por procedimento bilateral, justificativa formal e possibilidade de contestacao.",
        )

    if _has_any(text, ["responsabilidade integral do hospital", "hospital respondera integralmente", "sem limite de responsabilidade"]):
        add_failure(
            "Responsabilidade excessiva para o hospital",
            "A redacao pode impor responsabilidade ampla ou excessiva ao hospital.",
            "Critico",
            "Alto",
            "Risco juridico",
            "Limitar responsabilidades as obrigacoes diretamente atribuiveis ao hospital e excluir riscos sob controle da operadora.",
        )

    if not _has_any(text, ["equilibrio economico", "equilíbrio econômico", "reequilibrio", "reequilíbrio", "mutuo acordo", "mútuo acordo"]):
        add_failure(
            "Equilibrio contratual nao identificado",
            f"Mecanismo de equilibrio ou reequilibrio contratual esta {NOT_IDENTIFIED}.",
            "Medio",
            "Medio",
            "Risco juridico",
            "Inserir clausula de reequilibrio diante de alteracoes regulatórias, assistenciais ou de custo.",
        )


def _deadline_rows(contract) -> list[dict[str, str]]:
    return [
        {
            "type": "Faturamento",
            "deadline": f"{contract.billing_deadline_days} dias" if contract.billing_deadline_days else NOT_IDENTIFIED,
            "impact": "Risco de glosa administrativa se o prazo for curto ou ausente.",
            "risk": "Medio" if contract.billing_deadline_days else "Alto",
            "recommendation": "Definir prazo operacional compativel com fechamento de contas.",
        },
        {
            "type": "Pagamento",
            "deadline": f"{contract.payment_term_days} dias" if contract.payment_term_days else NOT_IDENTIFIED,
            "impact": "Afeta fluxo de caixa e previsibilidade financeira.",
            "risk": "Alto" if not contract.payment_term_days or contract.payment_term_days > 45 else "Medio",
            "recommendation": "Prever prazo maximo apos protocolo da fatura e penalidade por atraso.",
        },
        {
            "type": "Recurso de glosa",
            "deadline": f"{contract.glosa_appeal_deadline_days} dias" if contract.glosa_appeal_deadline_days else NOT_IDENTIFIED,
            "impact": "Pode reduzir recuperacao de valores glosados.",
            "risk": "Medio" if not contract.glosa_appeal_deadline_days else "Baixo",
            "recommendation": "Formalizar prazo para recurso, resposta e pagamento da glosa revertida.",
        },
        {
            "type": "Resposta da operadora a glosa",
            "deadline": f"{contract.glosa_response_deadline_days} dias" if contract.glosa_response_deadline_days else NOT_IDENTIFIED,
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


def _mandatory_checklist_result(contract, failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = (contract.raw_text or "").lower()
    results = []
    for group in MANDATORY_REVIEW_CHECKLIST:
        missing = []
        found = []
        for item in group["items"]:
            if _check_item_found(contract, text, group["area"], item):
                found.append(item)
            else:
                missing.append(item)
        area_failures = [item for item in failures if item["reference"] == group["area"] or group["area"] in item["reference"]]
        results.append(
            {
                "area": group["area"],
                "found": found,
                "missing": missing,
                "status": "critico" if any(item["risk"] == "Critico" for item in area_failures) else "atencao" if missing or area_failures else "ok",
                "note": NOT_IDENTIFIED if missing else "criterios localizados no documento",
            }
        )
    return results


def _check_item_found(contract, text: str, area: str, item: str) -> bool:
    checks = {
        "prazo de pagamento": bool(contract.payment_term_days),
        "ausencia de multa/juros por atraso": bool(contract.payment_interest_clause and contract.payment_penalty_clause),
        "retencoes indevidas": _has_any(text, ["retencao", "retenção", "compensacao", "compensação", "vedado desconto"]),
        "forma de faturamento": bool(contract.billing_deadline_days or contract.billing_deadline_description or contract.payment_trigger),
        "prazo de recurso": bool(contract.glosa_appeal_deadline_days),
        "prazo de resposta da operadora": bool(contract.glosa_response_deadline_days),
        "glosa sem justificativa": _has_any(text, ["justificativa da glosa", "glosa justificada", "motivo da glosa"]),
        "perda de prazo": _has_any(text, ["perda de prazo", "preclusao", "preclusão", "decadencia", "decadência"]),
        "desconto unilateral": _has_any(text, ["desconto unilateral", "glosa unilateral", "descontar unilateralmente"]),
        "indice previsto": bool(contract.reajust_index),
        "data-base": _has_any(text, ["data-base", "data base", "mes base"]),
        "ausencia de reajuste": bool(contract.reajust_clause_exists),
        "reajuste condicionado a operadora": _has_any(text, ["livre negociacao", "comum acordo", "aprovacao da operadora", "aprovação da operadora"]),
        "referencia SIMPRO": _has_any(text, ["simpro"]),
        "referencia Brasindice": _has_any(text, ["brasindice", "brasíndice"]),
        "NF + taxa": _has_any(text, ["nf + taxa", "nf mais taxa", "nota fiscal acrescida", "taxa administrativa"]),
        "redutores": _has_any(text, ["redutor", "redutores", "desagio", "deságio"]),
        "ausencia de regra clara": bool(contract.materials_table or contract.medicines_table or _has_any(text, ["opme", "ortese", "protese"])),
        "itens inclusos e exclusos": _has_any(text, ["itens inclusos", "itens excluidos", "itens excluídos", "exclusoes", "exclusões"]),
        "complicacoes": _has_any(text, ["complicacao", "complicações", "complicacoes"]),
        "intercorrencias": _has_any(text, ["intercorrencia", "intercorrências", "intercorrencias"]),
        "permanencia acima do previsto": _has_any(text, ["permanencia acima", "permanência acima", "diarias excedentes", "diárias excedentes"]),
        "migracao para tabela propria": _has_any(text, ["migracao para tabela", "migração para tabela", "tabela propria", "tabela própria"]),
        "prazo de aviso": bool(contract.termination_notice_days),
        "penalidades": _has_any(text, ["multa", "penalidade", "penalidades"]),
        "suspensao de atendimento": _has_any(text, ["suspensao de atendimento", "suspensão de atendimento", "suspender atendimento"]),
        "inadimplencia": _has_any(text, ["inadimplencia", "inadimplência", "atraso de pagamento"]),
        "clausulas abusivas": _has_any(text, ["abusiva", "abusivo", "a exclusivo criterio", "unilateralmente"]),
        "obrigacao unilateral": _has_any(text, ["obrigacao unilateral", "obrigação unilateral", "unilateralmente", "exclusivo criterio"]),
        "ausencia de equilibrio contratual": _has_any(text, ["equilibrio", "equilíbrio", "reequilibrio", "reequilíbrio"]),
        "responsabilidades excessivas para o hospital": _has_any(text, ["responsabilidade integral do hospital", "sem limite de responsabilidade", "hospital respondera integralmente"]),
    }
    return checks.get(item, _has_any(text, [item]))


def _impact_summary(failures: list[dict[str, Any]], areas: list[str]) -> str:
    matching = [
        item
        for item in failures
        if any(area.lower() in item["reference"].lower() for area in areas)
    ]
    if not matching:
        return "nao foram identificados impactos relevantes com base no documento analisado"
    top = matching[:4]
    return "; ".join(f"{item['title']} ({item['risk'].lower()})" for item in top)


def _favorable_points(contract) -> list[str]:
    points = []
    if contract.payment_term_days and contract.payment_term_days <= 30:
        points.append("Prazo de pagamento favoravel ao fluxo de caixa hospitalar.")
    if contract.payment_interest_clause:
        points.append("Previsao de juros por atraso identificada.")
    if contract.payment_penalty_clause:
        points.append("Previsao de multa por atraso identificada.")
    if contract.glosa_appeal_deadline_days:
        points.append("Prazo recursal de glosa identificado.")
    if contract.reajust_index:
        points.append("Indice de reajuste identificado.")
    if contract.materials_table or contract.medicines_table:
        points.append("Referencia para materiais ou medicamentos identificada.")
    return points or [NOT_IDENTIFIED]


def _unfavorable_points(failures: list[dict[str, Any]]) -> list[str]:
    points = [f"{item['title']}: {item['description']}" for item in failures[:8]]
    return points or [NOT_IDENTIFIED]


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
    return " ".join(values) if values else NOT_IDENTIFIED


def _date_range(start, end) -> str:
    if start and end:
        return f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}"
    return NOT_IDENTIFIED


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
        return "recusar"
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
