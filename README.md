# Autonomous Healthcare Research Agent

An evidence-grounded research assistant for medical and scientific literature, built around retrieval-augmented generation, PubMed search, and deterministic medical safety guardrails.

This is a research and educational information tool. It does not diagnose conditions, prescribe medication, or recommend personal treatment.

## Live Demo

Try the deployed app here: [https://autonomoushealthcareagent.streamlit.app/](https://autonomoushealthcareagent.streamlit.app/)

---

## Problem Statement

Researchers, students, and clinicians often need to quickly understand what published literature says about a topic — without wading through dozens of abstracts or risking an AI system that quietly hallucinates a citation or slips into giving medical advice it has no business giving.

This project builds a research assistant that searches PubMed and a locally indexed set of clinical-trial documents, grounds every answer in retrieved evidence, and enforces safety boundaries through deterministic rules rather than hoping the language model behaves.

## Motivation

Most "AI health assistant" demos either:

- hallucinate citations that don't exist, or
- happily answer "do I have X" as if they were a clinician.

This project is built specifically to avoid both failure modes: sources are only ever ones that were actually returned by PubMed or actually indexed from a PDF, and unsafe requests are caught by pattern-based guardrails that don't depend on the LLM choosing to refuse.

## Features

- Natural-language research questions answered with evidence-grounded synthesis
- Live PubMed search via the official NCBI E-utilities API
- Local clinical-trial PDF ingestion, chunking, and semantic search
- Retrieval-Augmented Generation (RAG) pipeline combining both evidence sources
- Deterministic input guardrails (blocks diagnosis, prescription, personalized treatment, and emergency requests before any tool runs)
- Deterministic output guardrails (rejects diagnostic certainty, prescription language, or unsupported claims in generated answers)
- Full source citations with PMID, DOI, journal, and page-level document references
- Persistent session memory in SQLite (sessions, messages, queries, sources)
- Clean Streamlit interface with session history
- Graceful handling of API failures, malformed PDFs, and empty results
- Automated test suite covering every major component

## Architecture

```
USER
  |
  v
STREAMLIT UI
  |
  v
INPUT SAFETY GUARDRAIL
  |
  v
RESEARCH AGENT / ORCHESTRATOR
  |
  +----------------------+
  |                       |
  v                       v
PUBMED SEARCH          VECTOR RETRIEVAL
  |                       |
  v                       v
SCIENTIFIC LITERATURE   CLINICAL-TRIAL / PDF KNOWLEDGE BASE
  |                       |
  +-----------+-----------+
              |
              v
        EVIDENCE SET
              |
              v
        LLM SYNTHESIS
              |
              v
       OUTPUT GUARDRAIL
              |
              v
   FINAL ANSWER + SOURCES
              |
              v
        SQLITE MEMORY
```

Every layer is a plain Python module with a narrow interface, so each one can be tested and reasoned about independently.

## Technology Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Scientific data | NCBI E-utilities (PubMed) |
| PDF processing | PyMuPDF |
| Embeddings | sentence-transformers (local, no API key required) |
| Vector database | ChromaDB (local, persistent) |
| LLM | Groq API, behind a provider abstraction |
| Guardrails | Guardrails AI + deterministic medical safety patterns |
| Database | SQLite + SQLAlchemy |
| Configuration | python-dotenv |
| Testing | pytest |

## System Workflow

1. User enters a question in the Streamlit chat input.
2. The input guardrail checks for diagnosis, prescription, personalized treatment, or emergency patterns. Unsafe requests are redirected immediately, before any external call is made.
3. The research planner decides which tools to run (PubMed is always tried; vector search runs if documents have been indexed).
4. The PubMed client searches NCBI and parses real article records.
5. The retriever embeds the question and searches the vector store for relevant document chunks.
6. Evidence from both sources is normalized into a single context block.
7. The LLM synthesizes a structured answer using only that evidence.
8. The output guardrail scans the generated answer for diagnostic certainty, prescription language, or personalized recommendations, and replaces the answer with a safe fallback if any are found.
9. Sources are attached to the answer and displayed with full metadata.
10. The question, answer, and sources are persisted to SQLite.
11. Streamlit renders the conversation and source cards.

## RAG Explanation

Retrieval-Augmented Generation means the language model is given retrieved evidence as part of its prompt and instructed to answer only from that evidence, rather than relying on what it memorized during training. Here, evidence comes from two retrieval paths — a live PubMed search and a semantic search over locally indexed PDFs — which are merged into one evidence block before the LLM ever sees the question. If no evidence is retrieved, the system says so explicitly instead of generating an answer anyway.

## Agent Explanation

The "agent" here is a controlled, deterministic orchestrator, not a free-roaming multi-agent system. It performs a fixed sequence of steps — guardrail check, plan, tool execution, synthesis, guardrail check again — and every step is a plain function call. This keeps the system's behavior predictable and easy to explain, while still genuinely coordinating multiple tools rather than just wrapping a single LLM call.

## Guardrails Explanation

Guardrails are implemented as regular-expression pattern matchers over specific phrasings, not as LLM judgment calls. This is deliberate: an LLM can be argued into ignoring an instruction, but a deterministic pattern match either fires or it doesn't. There are two layers:

- **Input guardrail** — screens the user's question before any tool runs. Catches diagnosis requests ("do I have..."), prescription requests ("what dosage should I take"), personalized treatment requests ("what should I do for my..."), and emergencies ("severe chest pain").
- **Output guardrail** — screens the LLM's generated answer before it is shown. Catches diagnostic certainty language, prescription language, and personalized recommendation language that might slip through despite the system prompt's instructions.

A research question like "what does the literature say about diabetes diagnostic criteria" is explicitly allowed — the guardrails are designed to distinguish personal medical requests from legitimate research questions, not to block all medical topics.

## Database Design

Four tables, managed through SQLAlchemy models in `app/database/models.py`:

- **sessions** — one row per research session
- **messages** — chat turns (user/assistant) tied to a session
- **research_queries** — each research question asked, tied to a session
- **sources** — citations tied to a research query, storing title, source type, identifier (PMID or filename), URL, and JSON-encoded metadata

All access goes through `app/database/memory.py`, which is the only module that issues queries against the models.

## Installation

```bash
git clone <your-repository-url>
cd autonomous-healthcare-agent
python3 -m venv .venv
source .venv/bin/activate       # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and fill in at least `PUBMED_EMAIL` and, if you want live AI-generated synthesis rather than demo mode, `LLM_API_KEY`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_PROVIDER` | no | Currently supports `anthropic` |
| `LLM_MODEL` | no | Model name, default `claude-sonnet-4-6` |
| `LLM_API_KEY` | recommended | Without it, the app runs the LLM step in demo mode |
| `PUBMED_EMAIL` | recommended | NCBI asks for a contact email on E-utilities requests |
| `PUBMED_API_KEY` | no | Optional, raises your NCBI rate limit |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` | no | Defaults to a free local sentence-transformers model |
| `CHROMA_PERSIST_DIR` | no | Where the vector database is stored on disk |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | no | PDF chunking parameters |
| `RETRIEVAL_TOP_K` | no | How many document chunks to retrieve per question |
| `DATABASE_URL` | no | Defaults to a local SQLite file |
| `DEMO_MODE` | no | Forces the LLM step into demo mode even if a key is set |

See `.env.example` for the complete list with defaults.

## Running the Application

```bash
streamlit run app/main.py
```

The app opens in your browser, typically at `http://localhost:8501`.

## PDF Ingestion Instructions

1. Place PDF files (clinical trial reports, research papers, etc.) into `data/pdfs/`.
2. Run the ingestion script:

```bash
python -m app.research.document_ingestion
```

Or trigger it programmatically:

```python
from app.research.document_ingestion import DocumentIngestionPipeline
pipeline = DocumentIngestionPipeline()
results = pipeline.ingest_directory()
for r in results:
    print(r)
```

Each PDF is extracted page-by-page, chunked, embedded, and stored in the local ChromaDB collection along with its source filename and page number, so every retrieved chunk stays traceable back to its origin. Already-indexed files are skipped automatically, and scanned/image-only PDFs (which produce no extractable text) are skipped with a clear reason rather than silently failing.

## Testing

```bash
pytest
```

Or for verbose output:

```bash
pytest -v
```

Tests use mocks for all external services (PubMed HTTP calls, the LLM, the embedding model where relevant), so the suite runs without any API key or network access.

## Example Queries

- "What does the research literature say about the effectiveness of intermittent fasting on metabolic markers?"
- "Summarize recent clinical trial findings on GLP-1 receptor agonists for weight management."
- "What are the diagnostic criteria for type 2 diabetes used in major studies?"
- "What does the evidence say about statin use and cardiovascular risk reduction?"
- "Compare findings on aerobic versus resistance exercise for blood pressure control."

## Safety Limitations

This system is explicitly **not** a diagnostic or treatment tool. It:

- does not determine whether any individual has a medical condition
- does not provide personalized medication dosages
- does not recommend a personal treatment plan
- does not manage medical emergencies
- may still occasionally over- or under-trigger a guardrail pattern, since the patterns are deterministic regular expressions rather than a full natural-language understanding system

If input or output guardrails misfire on a legitimate research question, that is a known trade-off of using deterministic pattern matching for safety-critical behavior rather than relying solely on an LLM's judgment.

## Known Limitations

- PubMed search quality depends on NCBI's own relevance ranking; it is not a substitute for a systematic literature review.
- The local embedding model is a general-purpose sentence embedding model, not one fine-tuned specifically for biomedical text.
- Guardrail patterns are English-language and phrasing-specific; sufficiently unusual phrasing could evade a pattern or, conversely, trigger a false positive on a legitimate research question.
- The demo LLM fallback (used when no API key is configured) does not generate a real synthesis — it clearly labels itself as a placeholder.
- No user authentication; sessions are local to the machine running the SQLite database.

## Future Improvements

- User authentication and multi-user session isolation
- Migration path to PostgreSQL for production deployments
- Cloud deployment (containerization, managed vector DB)
- Formal evaluation harness for retrieval quality and answer faithfulness
- Application monitoring and alerting
- Source quality/recency ranking
- Additional scientific databases beyond PubMed (e.g. ClinicalTrials.gov, Cochrane)
- More advanced retrieval strategies (hybrid search, re-ranking)
- Human-in-the-loop review workflow for sensitive queries

## Project Structure

```
autonomous-healthcare-agent/
    app/
        main.py                     Streamlit entry point
        config/settings.py          Central configuration
        agent/
            research_agent.py       Orchestrator
            planner.py               Tool-selection logic
            synthesizer.py           Prompt construction + LLM call
        research/
            pubmed_client.py         NCBI E-utilities client
            pdf_processor.py         PDF text extraction
            document_ingestion.py    PDF -> chunks -> embeddings -> vector store
            retriever.py             Semantic search
            citation.py              Citation formatting
        embeddings/embedder.py       Embedding provider abstraction
        vectorstore/chroma_store.py  ChromaDB wrapper
        guardrails/
            input_guard.py
            output_guard.py
            medical_policies.py      Pattern definitions
            validators.py
        database/
            database.py              Engine/session setup
            models.py                SQLAlchemy models
            memory.py                CRUD operations
        llm/provider.py              LLM abstraction (Anthropic + demo mode)
        utils/
            logging_config.py
            text_utils.py
    data/
        pdfs/                        Drop PDFs here for ingestion
        chroma/                      Persistent vector database
    tests/                           pytest suite
    docs/                            Concept reference notes
    .env.example
    .gitignore
    requirements.txt
    pytest.ini
    README.md
```

## Resume-Ready Description

> Built an end-to-end healthcare research assistant combining Retrieval-Augmented Generation, live PubMed integration, and local clinical-document search, with deterministic medical safety guardrails to prevent diagnostic, prescription, or personalized treatment claims. Implemented a modular Python architecture (PDF ingestion, embeddings, vector search, LLM abstraction, SQLite persistence, Streamlit UI) with a full pytest suite covering retrieval, guardrails, database, and agent orchestration.

---

For a conceptual reference on the individual technologies used in this project (REST APIs, embeddings, vector databases, RAG, guardrails, and more), see `docs/concepts.md`. For interview/viva-style questions and answers about design decisions, see `docs/interview_prep.md`.
