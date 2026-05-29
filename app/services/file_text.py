from __future__ import annotations

from pathlib import Path

import pdfplumber
from docx import Document


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
    if suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        return _extract_image_via_ocr(path)

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
    try:
        from pdf2image import convert_from_path
        from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError

        pages = convert_from_path(str(path), dpi=220)
    except ImportError as exc:
        raise TextExtractionError(
            "PDF sem texto detectado, mas o OCR esta desativado neste container. "
            "Reconstrua com INSTALL_OCR=true para ler PDFs escaneados."
        ) from exc
    except (PDFInfoNotInstalledError, PDFPageCountError, PDFSyntaxError) as exc:
        raise TextExtractionError(
            "PDF sem texto detectado, mas o OCR de PDF precisa do Poppler instalado e configurado no PATH."
        ) from exc
    return _extract_images_via_ocr(pages, method="pdf_ocr")


def _extract_image_via_ocr(path: Path) -> ExtractionResult:
    try:
        from PIL import Image
    except ImportError as exc:
        raise TextExtractionError(
            "OCR de imagem esta desativado neste container. "
            "Reconstrua com INSTALL_OCR=true para ler imagens."
        ) from exc

    with Image.open(path) as image:
        return _extract_images_via_ocr([image.copy()], method="image_ocr")


def _extract_images_via_ocr(images, method: str) -> ExtractionResult:
    try:
        import pytesseract
    except ImportError as exc:
        raise TextExtractionError(
            "OCR esta desativado neste container. Reconstrua com INSTALL_OCR=true para habilitar Tesseract."
        ) from exc

    texts: list[str] = []
    confidences: list[float] = []
    for image in images:
        try:
            data = pytesseract.image_to_data(image, lang="por", output_type=pytesseract.Output.DICT)
        except pytesseract.TesseractNotFoundError as exc:
            raise TextExtractionError(
                "OCR indisponivel: Tesseract nao esta instalado ou nao esta configurado no PATH."
            ) from exc
        except pytesseract.TesseractError as exc:
            raise TextExtractionError(f"OCR nao conseguiu ler o arquivo: {exc}") from exc
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
            "Nao foi possivel extrair texto do arquivo. Mesmo com OCR, o conteudo nao ficou legivel."
        )
    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.70
    return ExtractionResult(text=extracted, method=method, confidence=round(avg_conf, 2))


def _extract_docx(path: Path) -> str:
    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs).strip()
    if not text:
        raise TextExtractionError("O arquivo DOCX não contém texto legível.")
    return text
