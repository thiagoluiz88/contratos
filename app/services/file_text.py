from __future__ import annotations

from pathlib import Path

import pdfplumber
import pytesseract
from docx import Document
from pdf2image import convert_from_path


class TextExtractionError(Exception):
    pass


class ExtractionResult(dict):
    text: str
    method: str
    confidence: float


def extract_text_from_file(file_path: str | Path) -> ExtractionResult:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".docx":
        text = _extract_docx(path)
        return ExtractionResult(text=text, method="docx", confidence=0.98)
    if suffix in {".txt", ".md"}:
        return ExtractionResult(text=path.read_text(encoding="utf-8", errors="ignore"), method="text", confidence=0.99)

    raise TextExtractionError(f"Formato não suportado: {suffix}")


def _extract_pdf(path: Path) -> ExtractionResult:
    texts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                texts.append(text)
    extracted = "\n\n".join(texts).strip()
    if extracted:
        return ExtractionResult(text=extracted, method="pdf_text", confidence=0.96)

    # OCR fallback for scanned PDFs.
    return _extract_pdf_via_ocr(path)


def _extract_pdf_via_ocr(path: Path) -> ExtractionResult:
    pages = convert_from_path(str(path), dpi=220)
    texts: list[str] = []
    confidences: list[float] = []
    for image in pages:
        data = pytesseract.image_to_data(image, lang="por", output_type=pytesseract.Output.DICT)
        words = []
        for i, word in enumerate(data.get("text", [])):
            word = (word or "").strip()
            if word:
                words.append(word)
                try:
                    conf = float(data["conf"][i])
                    if conf >= 0:
                        confidences.append(conf)
                except Exception:
                    pass
        if words:
            texts.append(" ".join(words))

    extracted = "\n\n".join(texts).strip()
    if not extracted:
        raise TextExtractionError(
            "Não foi possível extrair texto do PDF. Mesmo com OCR, o conteúdo não ficou legível."
        )
    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.70
    return ExtractionResult(text=extracted, method="pdf_ocr", confidence=round(avg_conf, 2))


def _extract_docx(path: Path) -> str:
    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs).strip()
    if not text:
        raise TextExtractionError("O arquivo DOCX não contém texto legível.")
    return text
