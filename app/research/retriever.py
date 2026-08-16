"""
Semantic retriever: embeds a user query and searches the vector store,
returning normalized evidence records ready for context construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import settings
from app.embeddings.embedder import Embedder, EmbeddingError
from app.utils.logging_config import get_logger
from app.vectorstore.chroma_store import ChromaStore, VectorStoreError

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    page: int | None
    document_id: str
    chunk_id: str
    distance: float


class Retriever:
    def __init__(self, embedder: Embedder | None = None, store: ChromaStore | None = None):
        self.embedder = embedder or Embedder()
        self.store = store or ChromaStore()

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if not query or not query.strip():
            return []

        try:
            query_embedding = self.embedder.embed_query(query)
        except EmbeddingError as exc:
            logger.error("Embedding failed during retrieval: %s", exc)
            return []

        try:
            raw_results = self.store.query(query_embedding, top_k=top_k or settings.retrieval_top_k)
        except VectorStoreError as exc:
            logger.error("Vector store retrieval failed: %s", exc)
            return []

        chunks = []
        for result in raw_results:
            meta = result.get("metadata") or {}
            chunks.append(
                RetrievedChunk(
                    text=result.get("text", ""),
                    source=meta.get("source", "unknown"),
                    page=meta.get("page"),
                    document_id=meta.get("document_id", ""),
                    chunk_id=meta.get("chunk_id", ""),
                    distance=result.get("distance", 1.0),
                )
            )
        return chunks
