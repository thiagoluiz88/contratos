from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile

from app.config import MAX_UPLOAD_SIZE_BYTES, UPLOAD_DIR
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
    original_filename = Path(file.filename or "contrato").name
    extension = Path(original_filename).suffix.lower()
    if extension not in supported_extensions:
        raise UnsupportedUploadError(
            "Formato não suportado. Envie PDF, DOCX ou TXT."
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

    try:
        with stored_path.open("xb") as destination:
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > MAX_UPLOAD_SIZE_BYTES:
                    raise UnsupportedUploadError(f"Arquivo excede o limite de {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.")
                destination.write(chunk)
        validate_file_content(stored_path, extension)
    except Exception:
        try:
            stored_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return stored_path, file_size


def validate_file_content(stored_path: Path, extension: str) -> None:
    header = stored_path.read_bytes()[:8]
    if extension == ".pdf" and not header.startswith(b"%PDF-"):
        raise UnsupportedUploadError("O conteúdo do arquivo não corresponde a um PDF válido.")
    if extension == ".docx":
        if not header.startswith(b"PK\x03\x04"):
            raise UnsupportedUploadError("O conteúdo do arquivo não corresponde a um DOCX válido.")
        try:
            with ZipFile(stored_path) as archive:
                if "[Content_Types].xml" not in archive.namelist() or "word/document.xml" not in archive.namelist():
                    raise UnsupportedUploadError("O conteúdo do arquivo não corresponde a um DOCX válido.")
        except BadZipFile as exc:
            raise UnsupportedUploadError("O conteúdo do arquivo não corresponde a um DOCX válido.") from exc
    if extension == ".txt" and b"\x00" in stored_path.read_bytes()[:4096]:
        raise UnsupportedUploadError("Arquivo TXT inválido ou binário.")


def extract_contract_text(
    stored_path: Path,
    extension: str,
    legacy_doc_warning: str,
) -> tuple[str | None, str, str | None, float | None, str | None]:
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
