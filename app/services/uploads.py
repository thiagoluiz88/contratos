from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.config import UPLOAD_DIR
from app.services.contract_parser import parse_contract
from app.services.file_text import TextExtractionError, extract_text_from_file
from app.services.scoring import score_contract


class UnsupportedUploadError(ValueError):
    pass


@dataclass(slots=True)
class PreparedContractUpload:
    original_filename: str
    extension: str
    stored_path: Path
    file_size: int
    raw_text: str | None
    extraction_status: str
    extraction_method: str | None
    extraction_confidence: float | None
    warning: str | None
    parsed: dict
    scoring: dict


async def prepare_contract_upload(
    file: UploadFile,
    supported_extensions: set[str],
    legacy_doc_warning: str,
) -> PreparedContractUpload:
    original_filename = file.filename or "contrato"
    extension = Path(original_filename).suffix.lower()
    if extension not in supported_extensions:
        raise UnsupportedUploadError(
            "Formato nao suportado. Envie PDF, DOCX, DOC, TXT, MD, JPG, PNG ou TIFF."
        )

    stored_path, file_size = await save_upload_file(file, extension)
    raw_text, status, method, confidence, warning = extract_contract_text(
        stored_path,
        extension,
        legacy_doc_warning,
    )
    parsed = parse_contract(raw_text or "", original_filename) if raw_text else default_parse(original_filename, raw_text)

    return PreparedContractUpload(
        original_filename=original_filename,
        extension=extension,
        stored_path=stored_path,
        file_size=file_size,
        raw_text=raw_text,
        extraction_status=status,
        extraction_method=method,
        extraction_confidence=confidence,
        warning=warning,
        parsed=parsed,
        scoring=score_contract(parsed),
    )


async def save_upload_file(file: UploadFile, extension: str) -> tuple[Path, int]:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = UPLOAD_DIR / f"{uuid4().hex}{extension}"
    file_size = 0

    with stored_path.open("wb") as destination:
        while chunk := await file.read(1024 * 1024):
            file_size += len(chunk)
            destination.write(chunk)

    return stored_path, file_size


def extract_contract_text(
    stored_path: Path,
    extension: str,
    legacy_doc_warning: str,
) -> tuple[str | None, str, str | None, float | None, str | None]:
    if extension == ".doc":
        return None, "pending", None, None, legacy_doc_warning

    try:
        extraction = extract_text_from_file(stored_path)
        return (
            extraction.get("text"),
            "completed",
            extraction.get("method"),
            extraction.get("confidence"),
            None,
        )
    except TextExtractionError as exc:
        return None, "failed", None, None, str(exc)


def default_parse(original_filename: str, raw_text: str | None) -> dict:
    return {
        "contract_name": Path(original_filename).stem,
        "operator_name": None,
        "contract_number": None,
        "raw_text": raw_text,
    }


def append_warning(current_warning: str | None, extra_warning: str | None) -> str | None:
    if not extra_warning:
        return current_warning
    if not current_warning:
        return extra_warning
    return f"{current_warning} {extra_warning}"
