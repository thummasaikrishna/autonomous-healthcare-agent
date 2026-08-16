"""
Streamlit UI for the Autonomous Healthcare Research Agent.

Run with: streamlit run app/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path so `import app...` works when Streamlit
# launches this file (locally and on Streamlit Community Cloud).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from app.agent.research_agent import ResearchAgent
from app.config.settings import settings
from app.database import memory
from app.database.database import init_db
from app.research.document_ingestion import DocumentIngestionPipeline
from app.utils.logging_config import get_logger
from app.vectorstore.chroma_store import ChromaStore

logger = get_logger(__name__)

st.set_page_config(
    page_title="Healthcare Research Agent",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------

def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&family=Inter:wght@400;500;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        .main-title {
            font-family: 'Source Serif 4', serif;
            font-size: 2.1rem;
            font-weight: 700;
            color: #1a2b3c;
            margin-bottom: 0.1rem;
            letter-spacing: -0.01em;
        }

        .subtitle {
            font-family: 'Inter', sans-serif;
            font-size: 0.95rem;
            color: #5b6b7a;
            margin-bottom: 1.4rem;
            font-weight: 400;
        }

        .section-label {
            font-family: 'Source Serif 4', serif;
            font-size: 1.05rem;
            font-weight: 600;
            color: #1a2b3c;
            margin-top: 1.1rem;
            margin-bottom: 0.4rem;
            border-bottom: 1px solid #e4e8eb;
            padding-bottom: 0.25rem;
        }

        .blocked-box {
            background-color: #fbf3ef;
            border-left: 3px solid #b5623a;
            padding: 0.9rem 1.1rem;
            border-radius: 4px;
            color: #5a3520;
        }

        .source-card {
            background-color: #fafbfc;
            border: 1px solid #e4e8eb;
            border-radius: 6px;
            padding: 0.65rem 0.9rem;
            margin-bottom: 0.5rem;
            font-size: 0.87rem;
        }

        .source-title {
            font-weight: 600;
            color: #1a2b3c;
        }

        .source-meta {
            color: #6b7a87;
            font-size: 0.8rem;
        }

        div.stButton > button {
            background-color: #1a2b3c;
            color: white;
            border-radius: 6px;
            border: none;
            padding: 0.5rem 1.3rem;
            font-weight: 500;
        }

        div.stButton > button:hover {
            background-color: #2c4256;
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------

@st.cache_resource
def get_vector_store() -> ChromaStore:
    return ChromaStore()


@st.cache_resource
def get_agent() -> ResearchAgent:
    return ResearchAgent(store=get_vector_store())


@st.cache_resource
def get_ingestion_pipeline() -> DocumentIngestionPipeline:
    return DocumentIngestionPipeline(store=get_vector_store())


def ensure_db() -> None:
    if "db_initialized" not in st.session_state:
        init_db()
        st.session_state["db_initialized"] = True


def ensure_active_session() -> None:
    if "active_session_id" not in st.session_state:
        sessions = memory.list_sessions()
        if sessions:
            st.session_state["active_session_id"] = sessions[0]["id"]
        else:
            st.session_state["active_session_id"] = memory.create_session()


def ensure_page() -> None:
    if "page" not in st.session_state:
        st.session_state["page"] = "home"


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Research Sessions")

        if st.button("Start new session", use_container_width=True):
            new_id = memory.create_session()
            st.session_state["active_session_id"] = new_id
            st.session_state["page"] = "home"
            st.rerun()

        if st.button("Chat History", use_container_width=True):
            st.session_state["page"] = "history"
            st.rerun()

        search_query = st.text_input(
            "Search sessions",
            placeholder="Search sessions...",
            key="session_search_query",
            label_visibility="collapsed",
        )

        st.markdown("---")

        sessions = memory.search_sessions(search_query)
        if not sessions:
            if search_query.strip():
                st.caption("No matching sessions.")
            else:
                st.caption("No sessions yet.")

        for session in sessions:
            label = session["title"] or "Untitled session"
            if len(label) > 42:
                label = label[:39] + "..."
            is_active = (
                session["id"] == st.session_state.get("active_session_id")
                and st.session_state.get("page") == "home"
            )
            prefix = "● " if is_active else "○ "

            col_open, col_delete = st.columns([5, 1])
            with col_open:
                if st.button(
                    prefix + label,
                    key=f"session_{session['id']}",
                    use_container_width=True,
                ):
                    st.session_state["active_session_id"] = session["id"]
                    st.session_state["page"] = "home"
                    st.rerun()
            with col_delete:
                if st.button(
                    "✕",
                    key=f"delete_session_{session['id']}",
                    use_container_width=True,
                    help="Delete this entire session",
                ):
                    deleted_id = session["id"]
                    memory.delete_session(deleted_id)
                    if st.session_state.get("active_session_id") == deleted_id:
                        remaining = memory.list_sessions()
                        if remaining:
                            st.session_state["active_session_id"] = remaining[0]["id"]
                        else:
                            st.session_state["active_session_id"] = memory.create_session()
                        st.session_state["page"] = "home"
                    st.rerun()

        st.markdown("---")
        render_document_upload()


def render_document_upload() -> None:
    st.markdown("### Clinical Documents")
    st.caption("Upload PDFs to search alongside PubMed literature.")

    uploaded_files = st.file_uploader(
        "Upload clinical trial / research PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="pdf_uploader",
    )

    if uploaded_files and st.button("Index uploaded PDFs", use_container_width=True):
        pdf_dir = Path(settings.pdf_source_dir)
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pipeline = get_ingestion_pipeline()

        with st.spinner("Indexing documents..."):
            for uploaded_file in uploaded_files:
                destination = pdf_dir / uploaded_file.name
                with open(destination, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                result = pipeline.ingest_file(destination)
                if result.skipped:
                    st.warning(f"{result.filename}: {result.reason}")
                else:
                    st.success(f"{result.filename}: indexed {result.chunks_indexed} chunks")

        st.rerun()

    store = get_vector_store()
    indexed_count = store.count()
    if indexed_count:
        st.caption(f"{indexed_count} document chunks currently indexed and searchable.")
    else:
        st.caption("No documents indexed yet. PubMed search will still work on its own.")


# ---------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------

def render_chat_history_page() -> None:
    st.markdown('<div class="main-title">Chat History</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Questions you have asked. Delete one to remove only that question and its answer.</div>',
        unsafe_allow_html=True,
    )

    if st.button("← Back to research", use_container_width=False):
        st.session_state["page"] = "home"
        st.rerun()

    question_search = st.text_input(
        "Search questions",
        placeholder="Search a specific question...",
        key="question_history_search",
    )

    questions = memory.list_all_questions(question_search)
    if not questions:
        if question_search.strip():
            st.caption("No matching questions.")
        else:
            st.caption("No questions asked yet.")
        return

    st.markdown("---")
    for item in questions:
        question_text = item["question"]
        display = question_text if len(question_text) <= 140 else question_text[:137] + "..."
        col_q, col_del = st.columns([6, 1])
        with col_q:
            if st.button(
                display,
                key=f"open_question_{item['message_id']}",
                use_container_width=True,
                help="Open the session that contains this question",
            ):
                st.session_state["active_session_id"] = item["session_id"]
                st.session_state["page"] = "home"
                st.rerun()
        with col_del:
            if st.button(
                "✕",
                key=f"delete_question_{item['message_id']}",
                use_container_width=True,
                help="Delete this question and its answer only",
            ):
                memory.delete_question_turn(item["message_id"])
                st.rerun()


def render_history(session_id: str) -> None:
    messages = memory.get_messages(session_id)
    for message in messages:
        with st.chat_message("user" if message["role"] == "user" else "assistant"):
            st.markdown(message["content"])


def _reconstruct_citations(stored_sources: list[dict]):
    """Rebuild Citation objects from a session's persisted source rows."""
    from app.research.citation import Citation

    return [
        Citation(
            source_type=source["source_type"],
            title=source["title"],
            identifier=source["identifier"],
            url=source["url"],
            metadata=source["metadata"],
        )
        for source in stored_sources
    ]


def render_sources(citations) -> None:
    if not citations:
        st.caption("No sources were used for this response.")
        return

    st.markdown('<div class="section-label">Sources</div>', unsafe_allow_html=True)
    for index, citation in enumerate(citations, start=1):
        if citation.source_type == "pubmed":
            meta = citation.metadata
            authors = ", ".join(meta.get("authors", [])[:3])
            authors_suffix = " et al." if len(meta.get("authors", [])) > 3 else ""
            st.markdown(
                f"""<div class="source-card">
                <span class="source-title">[{index}] {citation.title}</span><br/>
                <span class="source-meta">{authors}{authors_suffix} — {meta.get('journal', 'Unknown journal')}
                ({meta.get('publication_date', 'n.d.')})</span><br/>
                <span class="source-meta">PMID: {citation.identifier or 'n/a'}
                {' · DOI: ' + meta['doi'] if meta.get('doi') else ''}</span>
                </div>""",
                unsafe_allow_html=True,
            )
            if citation.url:
                st.markdown(f"[View on PubMed]({citation.url})")
        else:
            meta = citation.metadata
            st.markdown(
                f"""<div class="source-card">
                <span class="source-title">[{index}] {citation.title}</span><br/>
                <span class="source-meta">Indexed document — page {meta.get('page', 'unknown')}</span>
                </div>""",
                unsafe_allow_html=True,
            )


def render_main() -> None:
    st.markdown('<div class="main-title">Autonomous Healthcare Research Agent</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Evidence-grounded research assistant for scientific and clinical literature.</div>',
        unsafe_allow_html=True,
    )
    st.caption("If a language model doesn't work, wait for 16 minutes and try again.")

    session_id = st.session_state["active_session_id"]
    render_history(session_id)

    question = st.chat_input("Ask a medical research question...")

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        memory.add_message(session_id, "user", question)

        # Give the agent access to the citations from this session's most
        # recent research query, so genuine follow-up questions ("summarize
        # the evidence you found") can be answered without a fresh search.
        history = memory.get_query_history(session_id)
        prior_citations = _reconstruct_citations(history[-1]["sources"]) if history else []

        with st.chat_message("assistant"):
            with st.spinner("Researching..."):
                agent = get_agent()
                result = agent.run(question, prior_citations=prior_citations)

            if result.blocked:
                st.markdown(f'<div class="blocked-box">{result.answer}</div>', unsafe_allow_html=True)
            else:
                st.markdown(result.answer)
                render_sources(result.citations)

            memory.add_message(session_id, "assistant", result.answer)
            if not result.blocked and result.citations:
                memory.save_query_with_sources(session_id, question, result.citations)

        # Auto-title the session from the first question.
        session_meta = memory.get_session(session_id)
        if session_meta and session_meta["title"] == "New Research Session":
            memory.rename_session(session_id, question[:60])


def main() -> None:
    inject_css()
    ensure_db()
    ensure_active_session()
    ensure_page()
    render_sidebar()
    if st.session_state["page"] == "history":
        render_chat_history_page()
    else:
        render_main()


if __name__ == "__main__":
    main()
