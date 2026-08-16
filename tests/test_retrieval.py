from unittest.mock import MagicMock

from app.research.retriever import Retriever, RetrievedChunk
from app.vectorstore.chroma_store import ChromaStore


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def embed_query(self, text):
        return [0.1, 0.2, 0.3]


class FakeStore:
    def __init__(self, results):
        self._results = results

    def query(self, query_embedding, top_k=None, where=None):
        return self._results

    def has_source(self, filename):
        return False

    def count(self):
        return len(self._results)


def test_retrieval_returns_normalized_chunks():
    fake_results = [
        {
            "text": "Chunk about trial outcomes.",
            "metadata": {"source": "trial_001.pdf", "page": 3, "document_id": "doc_1", "chunk_id": "chunk_1"},
            "distance": 0.12,
        }
    ]
    retriever = Retriever(embedder=FakeEmbedder(), store=FakeStore(fake_results))

    results = retriever.retrieve("What were the trial outcomes?")

    assert len(results) == 1
    assert isinstance(results[0], RetrievedChunk)
    assert results[0].source == "trial_001.pdf"
    assert results[0].page == 3
    assert results[0].document_id == "doc_1"


def test_retrieval_empty_query_returns_empty_list():
    retriever = Retriever(embedder=FakeEmbedder(), store=FakeStore([]))
    assert retriever.retrieve("") == []
    assert retriever.retrieve("   ") == []


def test_retrieval_handles_empty_store():
    retriever = Retriever(embedder=FakeEmbedder(), store=FakeStore([]))
    results = retriever.retrieve("any question")
    assert results == []


def test_indexing_via_chroma_store_add_documents(tmp_path):
    store = ChromaStore(persist_dir=str(tmp_path), collection_name="test_collection")
    store.add_documents(
        ids=["c1"],
        texts=["Sample clinical text."],
        embeddings=[[0.1] * 8],
        metadatas=[{"source": "doc.pdf", "page": 1, "document_id": "d1", "chunk_id": "c1"}],
    )
    assert store.count() == 1
    assert store.has_source("doc.pdf") is True
    assert store.has_source("other.pdf") is False
