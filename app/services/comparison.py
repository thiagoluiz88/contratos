from __future__ import annotations

from datetime import date, datetime

from app.models import Contract


FIELDS_TO_COMPARE = [
    ("operator_name", "Operadora"),
    ("contract_number", "Número do contrato"),
    ("start_date", "Início da vigência"),
    ("end_date", "Fim da vigência"),
    ("auto_renewal", "Renovação automática"),
    ("termination_notice_days", "Prazo de denúncia"),
    ("payment_term_days", "Prazo de pagamento"),
    ("payment_trigger", "Marco do pagamento"),
    ("billing_deadline_days", "Prazo de faturamento"),
    ("glosa_deadline_days", "Prazo de glosa"),
    ("glosa_appeal_deadline_days", "Prazo de recurso de glosa"),
    ("glosa_response_deadline_days", "Prazo de resposta da glosa"),
    ("reajust_frequency", "Periodicidade do reajuste"),
    ("reajust_index", "Índice de reajuste"),
    ("medical_fee_table", "Tabela médica"),
    ("medical_fee_table_version", "Versão da CBHPM"),
    ("daily_rate_table", "Diárias e taxas"),
    ("materials_table", "Tabela de materiais"),
    ("materials_table_version", "Versão da SIMPRO"),
    ("medicines_table", "Tabela de medicamentos"),
    ("medicines_table_version", "Versão da Brasíndice"),
    ("classification", "Classificação"),
    ("score_total", "Score"),
]


def compare_contracts(contracts: list[Contract]) -> list[dict]:
    rows = []
    for field, label in FIELDS_TO_COMPARE:
        row = {"field": field, "label": label, "values": []}
        for contract in contracts:
            value = getattr(contract, field)
            if isinstance(value, bool):
                value = "Sim" if value else "Não"
            elif isinstance(value, (date, datetime)):
                value = value.isoformat()
            row["values"].append(value if value not in (None, "") else "—")
        rows.append(row)
    return rows
