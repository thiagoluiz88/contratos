from __future__ import annotations

from datetime import date


ALERT_THRESHOLDS = [120, 90, 60, 30]


def score_contract(data: dict) -> dict:
    score = 0.0
    strong_points: list[str] = []
    weak_points: list[str] = []
    alerts: list[str] = []

    # 1. Vigência e renovação - 15
    vigencia_score = 0
    if data.get("start_date") and data.get("end_date"):
        vigencia_score += 8
        strong_points.append("Vigência com início e término identificados.")
    else:
        weak_points.append("Vigência incompleta ou não identificada.")

    if data.get("termination_notice_days"):
        vigencia_score += 4
        strong_points.append("Prazo de denúncia/rescisão identificado.")
    else:
        weak_points.append("Prazo de denúncia/rescisão não identificado.")

    if data.get("auto_renewal"):
        alerts.append("Contrato com renovação automática: acompanhar prazo de manifestação.")
    else:
        vigencia_score += 3

    score += min(vigencia_score, 15)

    # 2. Pagamento - 20
    pagamento_score = 0
    payment_term = data.get("payment_term_days")
    if payment_term is None:
        weak_points.append("Prazo de pagamento não identificado.")
    else:
        if payment_term <= 30:
            pagamento_score += 18
            strong_points.append("Prazo de pagamento favorável.")
        elif payment_term <= 60:
            pagamento_score += 12
            strong_points.append("Prazo de pagamento aceitável.")
        else:
            pagamento_score += 6
            weak_points.append("Prazo de pagamento longo.")

    if data.get("payment_interest_clause"):
        pagamento_score += 1
    else:
        weak_points.append("Cláusula de juros por atraso não identificada.")

    if data.get("payment_penalty_clause"):
        pagamento_score += 1
    else:
        weak_points.append("Cláusula de multa por atraso não identificada.")

    score += min(pagamento_score, 20)

    # 3. Faturamento - 15
    faturamento_score = 0
    billing = data.get("billing_deadline_days")
    if billing is None:
        weak_points.append("Prazo de faturamento não identificado.")
    else:
        if billing >= 30:
            faturamento_score += 15
            strong_points.append("Prazo de faturamento confortável.")
        elif billing >= 15:
            faturamento_score += 10
            strong_points.append("Prazo de faturamento razoável.")
        else:
            faturamento_score += 4
            weak_points.append("Prazo de faturamento curto e com risco operacional.")
    score += min(faturamento_score, 15)

    # 4. Glosa - 20
    glosa_score = 0
    if data.get("glosa_deadline_days"):
        glosa_score += 6
        strong_points.append("Prazo para glosa identificado.")
    else:
        weak_points.append("Prazo para glosa não identificado.")

    if data.get("glosa_appeal_deadline_days"):
        glosa_score += 6
        strong_points.append("Prazo recursal de glosa identificado.")
    else:
        weak_points.append("Prazo recursal de glosa não identificado.")

    if data.get("glosa_response_deadline_days"):
        glosa_score += 5
        strong_points.append("Prazo de resposta ao recurso de glosa identificado.")
    else:
        weak_points.append("Prazo de resposta ao recurso de glosa não identificado.")

    if data.get("allows_glosa_unilateral"):
        weak_points.append("Redação sugere glosa unilateral ou excessivamente ampla.")
        alerts.append("Atenção para cláusula de glosa ampla ou unilateral.")
    else:
        glosa_score += 3

    score += min(glosa_score, 20)

    # 5. Tabelas - 15
    tabelas_score = 0
    if data.get("medical_fee_table"):
        tabelas_score += 5
    else:
        weak_points.append("Tabela de honorários médicos não identificada.")

    if data.get("materials_table"):
        tabelas_score += 5
    else:
        weak_points.append("Tabela de materiais não identificada.")

    if data.get("medicines_table"):
        tabelas_score += 5
    else:
        weak_points.append("Tabela de medicamentos não identificada.")

    if data.get("medical_fee_table") == "CBHPM" and not data.get("medical_fee_table_version"):
        alerts.append("CBHPM identificada sem edição/versão clara.")
        weak_points.append("CBHPM sem edição/versão identificada.")

    score += min(tabelas_score, 15)

    # 6. Reajuste - 15
    reajuste_score = 0
    if data.get("reajust_clause_exists"):
        reajuste_score += 5
        strong_points.append("Cláusula de reajuste identificada.")
    else:
        weak_points.append("Cláusula de reajuste não identificada.")

    if data.get("reajust_frequency"):
        reajuste_score += 5
    else:
        weak_points.append("Periodicidade de reajuste não identificada.")

    if data.get("reajust_index"):
        reajuste_score += 5
        strong_points.append("Índice de reajuste identificado.")
    else:
        weak_points.append("Índice de reajuste não identificado.")
        if data.get("reajust_clause_exists"):
            alerts.append("Há cláusula de reajuste, mas sem índice claramente definido.")

    score += min(reajuste_score, 15)

    # Alertas de vencimento
    today = date.today()
    end_date = data.get("end_date")
    if end_date:
        days_left = (end_date - today).days
        if days_left < 0:
            alerts.append("Contrato vencido.")
        else:
            for threshold in ALERT_THRESHOLDS:
                if days_left <= threshold:
                    alerts.append(f"Contrato vence em {days_left} dias.")
                    break

    classification, risk_level = classify(score)

    return {
        "score_total": round(score, 2),
        "classification": classification,
        "risk_level": risk_level,
        "strong_points": "\n".join(deduplicate(strong_points)),
        "weak_points": "\n".join(deduplicate(weak_points)),
        "alerts": "\n".join(deduplicate(alerts)),
    }



def classify(score: float) -> tuple[str, str]:
    if score >= 80:
        return "Favorável", "baixo"
    if score >= 60:
        return "Aceitável com atenção", "moderado"
    if score >= 40:
        return "Desfavorável", "alto"
    return "Crítico", "muito alto"



def deduplicate(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            output.append(normalized)
            seen.add(normalized)
    return output
