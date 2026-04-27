from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader


class PdfExtractionError(RuntimeError):
    """Raised when text cannot be extracted from a PDF."""


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pragma: no cover - pypdf raises many concrete errors
        raise PdfExtractionError("Unable to read PDF attachment") from exc

    text = "\n".join(page.strip() for page in pages if page.strip()).strip()
    if not text:
        raise PdfExtractionError("PDF contained no extractable text")
    return text


def save_pdf(download_dir: Path, loan_id: str, attachment_id: str, pdf_bytes: bytes) -> Path:
    loan_dir = download_dir / safe_path_component(loan_id)
    loan_dir.mkdir(parents=True, exist_ok=True)
    destination = loan_dir / f"{safe_path_component(attachment_id)}.pdf"
    destination.write_bytes(pdf_bytes)
    return destination


def safe_path_component(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ("-", "_", ".") else "_" for char in value)
    return cleaned.strip("._") or "unknown"
