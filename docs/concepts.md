# Concept Reference

Short, project-grounded explanations of the core ideas behind this system. Each entry connects the concept back to where it's actually used in the codebase.

## REST / API

A REST API exposes operations over HTTP using standard verbs (GET, POST, etc.) against resource-like URLs. This project calls two REST-style APIs: NCBI's E-utilities (`app/research/pubmed_client.py`) and the Anthropic Messages API (`app/llm/provider.py`). Both are accessed with plain HTTP requests wrapped in timeout and retry logic rather than a heavyweight SDK-specific abstraction, so failures are easy to reason about.

## PubMed API (NCBI E-utilities)

NCBI E-utilities is the official programmatic interface to PubMed. This project uses two endpoints: `esearch.fcgi` to get a list of PubMed IDs matching a query, and `efetch.fcgi` to retrieve full article records (title, abstract, authors, journal, DOI) for those IDs. Using the official API means every returned paper is real — the client never invents a result.

## Embeddings

An embedding is a numeric vector representation of text such that semantically similar text produces vectors that are close together in that vector space. This project uses a sentence-transformers model to embed both PDF chunks (at ingestion time) and user questions (at query time), so that "meaning-similar" text can be found even when the wording differs. See `app/embeddings/embedder.py`.

## Vector Databases

A vector database stores embeddings alongside their source metadata and supports fast nearest-neighbor search — given a query vector, it returns the most similar stored vectors. This project uses ChromaDB in persistent local mode (`app/vectorstore/chroma_store.py`), so indexed documents survive an application restart without needing an external database server.

## Semantic Search

Semantic search means retrieving results based on meaning rather than exact keyword matches. Here, it's implemented as: embed the query, ask the vector store for the closest stored chunk embeddings, and return those chunks with their original source metadata intact.

## Chunking

Chunking splits long documents into smaller pieces before embedding, because embedding models have limited input length and because retrieval works better with focused, topically coherent pieces of text. `app/utils/text_utils.py` implements sentence-boundary-aware chunking with configurable size and overlap, so a chunk boundary is less likely to cut a sentence in half.

## RAG (Retrieval-Augmented Generation)

RAG means retrieving relevant information first, then giving that information to a language model as context so the model's answer is grounded in real, retrieved evidence rather than solely relying on what the model memorized during training. This project's RAG pipeline merges PubMed results and vector-store document chunks into one evidence block, which is then handed to the LLM with strict instructions to only use that evidence.

## LLM (Large Language Model)

An LLM is used here purely as a synthesis engine — it turns structured evidence into a readable, organized answer. It is explicitly not trusted as the safety mechanism; that job belongs to the deterministic guardrails, because an LLM can be persuaded to ignore instructions in ways a regex match cannot.

## Hallucination

Hallucination is when a language model generates plausible-sounding but false information — including citations to papers that don't exist. This project mitigates hallucination in two ways: the prompt instructs the model to use only the provided evidence and never invent a citation, and the evidence itself is only ever real data pulled from PubMed or an indexed PDF — there is no code path that invents a source.

## Agent Orchestration

An "agent" in this project is a deterministic sequence of steps (guardrail check, plan, tool calls, synthesis, guardrail check) implemented as plain function calls in `app/agent/research_agent.py`. It is not an open-ended, self-directed multi-agent system; the term here refers to coordinated tool use, not autonomy in a stronger sense.

## Guardrails

Guardrails are safety checks applied before and after the LLM step. Input guardrails screen the user's question for diagnosis, prescription, personalized treatment, or emergency requests. Output guardrails screen the generated answer for diagnostic certainty, prescription language, or personalized recommendations. Both are implemented as regular-expression pattern matching (`app/guardrails/medical_policies.py`), which makes their behavior predictable and testable.

## Input Validation

Beyond safety guardrails, input validation covers basic sanity checks — for example, rejecting an empty question before any tool call is made.

## Output Validation

After the LLM generates a response, the output guardrail re-checks the text itself (not just the original question) for unsafe language, since a model can occasionally produce unsafe phrasing even when the input looked benign.

## SQLite

SQLite is a lightweight, file-based relational database requiring no separate server process, which makes it a good fit for a single-machine research tool. This project stores sessions, messages, research queries, and sources in SQLite (`data/app.db` by default).

## SQLAlchemy

SQLAlchemy is a Python ORM (object-relational mapper) that lets database tables be defined as Python classes (`app/database/models.py`) and queried with Python rather than raw SQL strings, while still ultimately generating SQL under the hood.

## Streamlit

Streamlit is a Python framework for building data/AI application UIs without writing separate frontend code. This project uses it for the chat interface, session sidebar, and source display (`app/main.py`).
