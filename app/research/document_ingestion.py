"""
Document ingestion pipeline: PDF -> clean text -> chunks -> embeddings -> vector store.

This module wires together pdf_processor, text_utils, the embedder, and the
vector store. It is intentionally a plain, sequential pipeline rather than a
framework, so it stays easy to trace and debug.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config.settings import settings
from app.embeddings.embedder import Embedder
from app.research.pdf_processor import extract_pdf, list_pdf_files, PDFProcessingError
from app.utils.logging_config import get_logger
from app.utils.text_utils import chunk_text, new_id
from app.vectorstore.chroma_store import ChromaStore

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    filename: str
    chunks_indexed: int
    skipped: bool
    reason: str = ""


class DocumentIngestionPipeline:
    def __init__(self, embedder: Embedder | None = None, store: ChromaStore | None = None):
        self.embedder = embedder or Embedder()
        self.store = store or ChromaStore()

    def ingest_directory(self, directory: str | Path | None = None) -> list[IngestionResult]:
        directory = directory or settings.pdf_source_dir
        pdf_paths = list_pdf_files(directory)

        if not pdf_paths:
            logger.info("No PDF files found in %s", directory)
            return []

        results = []
        for path in pdf_paths:
            results.append(self.ingest_file(path))
        return results

    def ingest_file(self, path: str | Path) -> IngestionResult:
        path = Path(path)
        document_id = new_id("doc_")

        try:
            extracted = extract_pdf(path)
        except PDFProcessingError as exc:
            logger.error("Skipping unreadable PDF %s: %s", path.name, exc)
            return IngestionResult(filename=path.name, chunks_indexed=0, skipped=True, reason=str(exc))

        if extracted.is_empty:
            return IngestionResult(
                filename=path.name,
                chunks_indexed=0,
                skipped=True,
                reason="No extractable text (file may be a scanned image).",
            )

        if self.store.has_source(path.name):
            return IngestionResult(
                filename=path.name,
                chunks_indexed=0,
                skipped=True,
                reason="Already indexed (duplicate source).",
            )

        chunk_records = []
        for page in extracted.pages:
            page_chunks = chunk_text(
                page.text,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            for chunk in page_chunks:
                chunk_id = new_id("chunk_")
                chunk_records.append(
                    {
                        "id": chunk_id,
                        "text": chunk,
                        "metadata": {
                            "source": path.name,
                            "page": page.page_number,
                            "document_id": document_id,
                            "chunk_id": chunk_id,
                        },
                    }
                )

        if not chunk_records:
            return IngestionResult(
                filename=path.name, chunks_indexed=0, skipped=True, reason="No chunks produced."
            )

        texts = [record["text"] for record in chunk_records]
        embeddings = self.embedder.embed_documents(texts)

        self.store.add_documents(
            ids=[record["id"] for record in chunk_records],
            texts=texts,
            embeddings=embeddings,
            metadatas=[record["metadata"] for record in chunk_records],
        )

        logger.info("Indexed %s chunks from %s", len(chunk_records), path.name)
        return IngestionResult(filename=path.name, chunks_indexed=len(chunk_records), skipped=False)
