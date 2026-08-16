"""
Central application configuration.

All tunable values live here and are sourced from environment variables so
that nothing environment-specific is hard-coded into the rest of the
application. Copy .env.example to .env and fill in real values before
running the app.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env once, as early as possible.
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def _load_streamlit_secrets_into_env() -> None:
    """Copy Streamlit Cloud secrets into os.environ for settings lookups."""
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        return

    for key in secrets:
        if key in os.environ and os.environ.get(key):
            continue
        try:
            value = secrets[key]
        except Exception:
            continue
        if isinstance(value, (str, int, float, bool)):
            os.environ[key] = str(value)


_load_streamlit_secrets_into_env()


def _get_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- General ---
    app_name: str = "Autonomous Healthcare Research Agent"
    environment: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    demo_mode: bool = field(default_factory=lambda: _get_bool("DEMO_MODE", False))

    # --- LLM provider ---
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "groq"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "openai/gpt-oss-120b"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_max_tokens: int = field(default_factory=lambda: _get_int("LLM_MAX_TOKENS", 1200))
    llm_temperature: float = field(default_factory=lambda: _get_float("LLM_TEMPERATURE", 0.2))
    llm_timeout_seconds: int = field(default_factory=lambda: _get_int("LLM_TIMEOUT_SECONDS", 60))
    groq_base_url: str = field(
        default_factory=lambda: os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    )

    # --- PubMed / NCBI E-utilities ---
    pubmed_base_url: str = field(
        default_factory=lambda: os.getenv(
            "PUBMED_BASE_URL", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        )
    )
    pubmed_email: str = field(default_factory=lambda: os.getenv("PUBMED_EMAIL", ""))
    pubmed_tool_name: str = field(
        default_factory=lambda: os.getenv("PUBMED_TOOL_NAME", "autonomous-healthcare-agent")
    )
    pubmed_api_key: str = field(default_factory=lambda: os.getenv("PUBMED_API_KEY", ""))
    pubmed_max_results: int = field(default_factory=lambda: _get_int("PUBMED_MAX_RESULTS", 6))
    pubmed_timeout_seconds: int = field(default_factory=lambda: _get_int("PUBMED_TIMEOUT_SECONDS", 15))
    pubmed_max_retries: int = field(default_factory=lambda: _get_int("PUBMED_MAX_RETRIES", 2))

    # --- Embeddings ---
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "local")
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )

    # --- Vector store ---
    chroma_persist_dir: str = field(
        default_factory=lambda: os.getenv(
            "CHROMA_PERSIST_DIR", str(BASE_DIR / "data" / "chroma")
        )
    )
    chroma_collection_name: str = field(
        default_factory=lambda: os.getenv("CHROMA_COLLECTION_NAME", "clinical_documents")
    )
    retrieval_top_k: int = field(default_factory=lambda: _get_int("RETRIEVAL_TOP_K", 5))

    # --- Chunking ---
    chunk_size: int = field(default_factory=lambda: _get_int("CHUNK_SIZE", 900))
    chunk_overlap: int = field(default_factory=lambda: _get_int("CHUNK_OVERLAP", 150))

    # --- PDF source directory ---
    pdf_source_dir: str = field(
        default_factory=lambda: os.getenv("PDF_SOURCE_DIR", str(BASE_DIR / "data" / "pdfs"))
    )

    # --- Database ---
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
        )
    )

    # --- Logging ---
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_file: str = field(
        default_factory=lambda: os.getenv("LOG_FILE", str(BASE_DIR / "data" / "app.log"))
    )

    def validate(self) -> list[str]:
        """Return a list of human-readable configuration warnings (non-fatal)."""
        warnings: list[str] = []
        if not self.demo_mode and not self.llm_api_key:
            warnings.append(
                "LLM_API_KEY is not set. The app will run in demo mode for the LLM step."
            )
        if not self.pubmed_email:
            warnings.append(
                "PUBMED_EMAIL is not set. NCBI requests a contact email for E-utilities usage."
            )
        return warnings


settings = Settings()
