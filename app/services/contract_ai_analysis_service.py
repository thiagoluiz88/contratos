from __future__ import annotations

from app.services.document_processing_service import empty_extraction_payload


AI_PENDING_STATUS = "pendente_integracao_ia"


def build_empty_extraction_schema() -> dict:
    payload = empty_extraction_payload()
    payload["raw_text_available"] = False
    payload["candidate_sections"] = []
    payload["pending_ai_analysis"] = True
    return payload


def prepare_text_for_future_ai(text: str | None, *, max_chars: int = 20000) -> dict:
    prepared = (text or "").strip()
    return {
        "status": AI_PENDING_STATUS,
        "text_available": bool(prepared),
        "character_count": len(prepared),
        "text_preview": prepared[:max_chars] if prepared else None,
        "message": "Integração de IA ainda não habilitada. Texto preparado apenas para etapa futura.",
    }


def analyze_contract_text_pending(text: str | None = None) -> dict:
    return {
        "status": AI_PENDING_STATUS,
        "extracted_json": build_empty_extraction_schema(),
        "prepared_text": prepare_text_for_future_ai(text),
    }
