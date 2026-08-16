"""
Local, persistent vector store backed by ChromaDB.

Wraps a single collection and exposes only the operations the rest of the
app needs: add, query, duplicate-source check. Keeping this narrow makes it
straightforward to swap in a different vector database later if needed.
"""

from __future__ import annotations

from app.config.settings import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class VectorStoreError(Exception):
    pass


class ChromaStore:
    def __init__(self, persist_dir: str | None = None, collection_name: str | None = None):
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        self.collection_name = collection_name or settings.chroma_collection_name
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        try:
            import chromadb
        except ImportError as exc:
            raise VectorStoreError(
                "chromadb is not installed. Add it to requirements.txt."
            ) from exc

        try:
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise VectorStoreError(f"Failed to initialize vector store: {exc}") from exc

        return self._collection

    def add_documents(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        if not ids:
            return
        collection = self._get_collection()
        try:
            collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        except Exception as exc:
            raise VectorStoreError(f"Failed to add documents to vector store: {exc}") from exc

    def query(
        self,
        query_embedding: list[float],
        top_k: int | None = None,
        where: dict | None = None,
    ) -> list[dict]:
        """Return a list of {text, metadata, distance} results."""
        if not query_embedding:
            return []

        collection = self._get_collection()
        top_k = top_k or settings.retrieval_top_k

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
            )
        except Exception as exc:
            logger.error("Vector store query failed: %s", exc)
            return []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            {"text": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(documents, metadatas, distances)
        ]

    def has_source(self, filename: str) -> bool:
        """Duplicate-prevention check: has this filename already been indexed."""
        try:
            collection = self._get_collection()
            existing = collection.get(where={"source": filename}, limit=1)
            return bool(existing.get("ids"))
        except VectorStoreError:
            return False
        except Exception as exc:
            logger.warning("Duplicate-check query failed, proceeding without it: %s", exc)
            return False

    def count(self) -> int:
        try:
            return self._get_collection().count()
        except Exception:
            return 0
