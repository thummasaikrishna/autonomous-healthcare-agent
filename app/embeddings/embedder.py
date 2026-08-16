"""
Embedding abstraction.

The rest of the application only calls Embedder.embed_documents() /
embed_query(); the concrete provider is chosen here based on configuration
so it can be swapped without touching ingestion or retrieval code.

Default provider is a local sentence-transformers model, which requires no
API key and keeps the demo fully runnable offline.
"""

from __future__ import annotations

from app.config.settings import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingError(Exception):
    pass


class Embedder:
    """Thin wrapper that lazily loads the configured embedding backend."""

    def __init__(self, provider: str | None = None, model_name: str | None = None):
        self.provider = provider or settings.embedding_provider
        self.model_name = model_name or settings.embedding_model
        self._model = None

    def _load_local_model(self):
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers is not installed. Add it to requirements.txt "
                "or set EMBEDDING_PROVIDER to a different backend."
            ) from exc

        logger.info("Loading local embedding model: %s", self.model_name)
        self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.provider == "local":
            model = self._load_local_model()
            vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
            return [vector.tolist() for vector in vectors]
        raise EmbeddingError(f"Unsupported embedding provider: {self.provider}")

    def embed_query(self, text: str) -> list[float]:
        result = self.embed_documents([text])
        return result[0] if result else []
