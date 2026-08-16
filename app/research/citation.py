"""
Formats evidence records (PubMed articles and PDF chunks) into a consistent
citation shape for display and for SQLite persistence. Nothing here ever
invents a citation; it only formats data already retrieved from a real
source system.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.research.pubmed_client import PubMedArticle
from app.research.retriever import RetrievedChunk


@dataclass
class Citation:
    source_type: str  # "pubmed" or "document"
    title: str
    identifier: str  # PMID or filename
    url: str
    metadata: dict


def citation_from_pubmed(article: PubMedArticle) -> Citation:
    return Citation(
        source_type="pubmed",
        title=article.title,
        identifier=article.pmid,
        url=article.url,
        metadata={
            "authors": article.authors,
            "journal": article.journal,
            "publication_date": article.publication_date,
            "doi": article.doi,
            "abstract": article.abstract,
        },
    )


def citation_from_chunk(chunk: RetrievedChunk) -> Citation:
    return Citation(
        source_type="document",
        title=chunk.source,
        identifier=f"{chunk.source}#p{chunk.page}",
        url="",
        metadata={
            "page": chunk.page,
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "excerpt": chunk.text,
        },
    )


def format_citation_line(citation: Citation, index: int) -> str:
    if citation.source_type == "pubmed":
        pmid_part = f"PMID {citation.identifier}" if citation.identifier else "PMID unavailable"
        return f"[{index}] {citation.title} — {pmid_part}"
    page = citation.metadata.get("page")
    page_part = f"page {page}" if page else "page unknown"
    return f"[{index}] {citation.title} — {page_part}"
