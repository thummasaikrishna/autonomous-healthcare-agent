"""
PDF text extraction using PyMuPDF (fitz).

Extracts text page-by-page so that page numbers can be preserved as
metadata all the way through to the vector store and, eventually, to the
sources shown to the user.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz  # PyMuPDF (import name changed from `fitz`; both work, this is current)

from app.utils.logging_config import get_logger
from app.utils.text_utils import clean_text

logger = get_logger(__name__)


class PDFProcessingError(Exception):
    """Raised when a PDF cannot be opened or read."""


@dataclass
class PDFPage:
    page_number: int
    text: str


@dataclass
class ExtractedPDF:
    filename: str
    pages: list[PDFPage]

    @property
    def is_empty(self) -> bool:
        return all(not page.text.strip() for page in self.pages)


def extract_pdf(path: str | Path) -> ExtractedPDF:
    """Extract text from every page of a PDF. Never raises for empty pages."""
    path = Path(path)
    if not path.exists():
        raise PDFProcessingError(f"File not found: {path}")

    try:
        document = fitz.open(path)
    except Exception as exc:
        raise PDFProcessingError(f"Could not open PDF '{path.name}': {exc}") from exc

    pages: list[PDFPage] = []
    try:
        for index in range(document.page_count):
            try:
                page = document.load_page(index)
                raw_text = page.get_text("text")
                pages.append(PDFPage(page_number=index + 1, text=clean_text(raw_text)))
            except Exception as exc:
                logger.warning("Failed to extract page %s of %s: %s", index + 1, path.name, exc)
                pages.append(PDFPage(page_number=index + 1, text=""))
    finally:
        document.close()

    extracted = ExtractedPDF(filename=path.name, pages=pages)
    if extracted.is_empty:
        logger.warning("PDF '%s' produced no extractable text (possibly scanned/image-only).", path.name)

    return extracted


def list_pdf_files(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    if not directory.exists():
        return []
    return sorted(directory.glob("*.pdf"))
