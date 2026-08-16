"""
Synthesizer: builds the grounded prompt from collected evidence and calls
the LLM provider. Also defines the system prompt that instructs the model
to stay grounded in the retrieved evidence and avoid unsafe claims.
"""

from __future__ import annotations

from app.llm.provider import LLMProvider, LLMError
from app.research.citation import Citation, format_citation_line
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a medical research synthesis assistant. You help \
users understand published scientific and clinical research. You are NOT a \
diagnostic tool and you do not provide medical advice.

Rules you must follow strictly:
1. Base your answer only on the evidence provided in the prompt. Do not use \
outside knowledge to state specific facts, statistics, or study findings.
2. Never invent a citation, paper title, author, PMID, DOI, or trial name. \
Only reference the sources given to you.
3. Never state or imply that the user personally has a medical condition.
4. Never provide a specific medication dosage for the user to take.
5. Never recommend a specific personal treatment plan.
6. Clearly separate what the evidence shows from your own interpretation.
7. If the evidence provided is insufficient or empty, say so explicitly \
rather than filling the gap with assumptions.
8. Do not include an "Evidence Quality / Limitations" section.
9. Do not include a "Safety Notice" section or any similar disclaimer block.

Respond using this structure:

Research Summary
<2-4 sentence evidence-based synthesis>

Key Findings
- <finding 1>
- <finding 2>
- <finding 3>
"""


def build_evidence_block(pubmed_evidence: list, document_evidence: list) -> tuple[str, list[Citation]]:
    """Build the evidence text block for the prompt and the ordered citation list."""
    from app.research.citation import citation_from_pubmed, citation_from_chunk

    citations: list[Citation] = []
    lines: list[str] = []

    if pubmed_evidence:
        lines.append("PubMed literature:")
        for article in pubmed_evidence:
            citation = citation_from_pubmed(article)
            citations.append(citation)
            index = len(citations)
            lines.append(f"[{index}] Title: {article.title}")
            lines.append(f"    Journal: {article.journal or 'Unknown'} ({article.publication_date})")
            lines.append(f"    Abstract: {article.abstract}")
            lines.append("")

    if document_evidence:
        lines.append("Indexed clinical document excerpts:")
        for chunk in document_evidence:
            citation = citation_from_chunk(chunk)
            citations.append(citation)
            index = len(citations)
            lines.append(f"[{index}] Source: {chunk.source} (page {chunk.page})")
            lines.append(f"    Excerpt: {chunk.text}")
            lines.append("")

    if not lines:
        return "No evidence was retrieved for this question.", citations

    return "\n".join(lines), citations


def build_evidence_block_from_prior_citations(citations: list[Citation]) -> str:
    """
    Rebuild an evidence block from already-persisted citations (e.g. sources
    attached to the previous research query in this session), so a genuine
    follow-up question ("summarize the evidence you found") can be answered
    without re-running a fresh, and likely unrelated, PubMed/vector search.
    """
    lines: list[str] = []
    for index, citation in enumerate(citations, start=1):
        if citation.source_type == "pubmed":
            journal = citation.metadata.get("journal", "Unknown")
            date = citation.metadata.get("publication_date", "n.d.")
            abstract = citation.metadata.get("abstract", "No abstract available.")
            lines.append(f"[{index}] Title: {citation.title}")
            lines.append(f"    Journal: {journal} ({date})")
            lines.append(f"    Abstract: {abstract}")
        else:
            page = citation.metadata.get("page", "unknown")
            excerpt = citation.metadata.get("excerpt", "")
            lines.append(f"[{index}] Source: {citation.title} (page {page})")
            lines.append(f"    Excerpt: {excerpt}")
        lines.append("")

    if not lines:
        return "No prior evidence is available in this session."
    return "\n".join(lines)


class Synthesizer:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    def synthesize(self, question: str, pubmed_evidence: list, document_evidence: list) -> tuple[str, list[Citation]]:
        evidence_block, citations = build_evidence_block(pubmed_evidence, document_evidence)

        if not citations:
            return (
                "Research Summary\n"
                "Insufficient evidence was retrieved to support a response to this "
                "question. No relevant PubMed articles or indexed documents were found.\n\n"
                "Key Findings\n"
                "- No supporting evidence was located.\n"
                "- Try rephrasing the question or broadening the topic.",
                citations,
            )

        user_prompt = (
            f"User research question:\n{question}\n\n"
            f"Evidence:\n{evidence_block}\n\n"
            "Using only the evidence above, produce the structured response described "
            "in your instructions. Refer to sources by their bracketed number, e.g. [1]."
        )

        try:
            answer = self.llm_provider.generate(SYSTEM_PROMPT, user_prompt)
        except LLMError as exc:
            logger.error("LLM synthesis failed: %s", exc)
            answer = (
                "Research Summary\n"
                "The response could not be generated due to a temporary issue with "
                "the language model service. Relevant evidence was retrieved and is "
                "listed in Sources below."
            )

        return answer, citations

    @staticmethod
    def format_sources(citations: list[Citation]) -> str:
        if not citations:
            return "No sources available."
        return "\n".join(format_citation_line(c, i + 1) for i, c in enumerate(citations))

    def synthesize_from_prior_citations(
        self, question: str, citations: list[Citation]
    ) -> tuple[str, list[Citation]]:
        """
        Answer a follow-up question (e.g. "summarize the evidence you found")
        using citations already retrieved earlier in this session, instead of
        running a fresh search on a question that has no medical topic of its
        own to search for.
        """
        if not citations:
            return (
                "Research Summary\n"
                "There is no prior evidence in this session to summarize yet. "
                "Ask a research question first.",
                [],
            )

        evidence_block = build_evidence_block_from_prior_citations(citations)
        user_prompt = (
            f"User follow-up request:\n{question}\n\n"
            f"Previously retrieved evidence from this session:\n{evidence_block}\n\n"
            "Using only the evidence above, produce the structured response described "
            "in your instructions. Refer to sources by their bracketed number, e.g. [1]."
        )

        try:
            answer = self.llm_provider.generate(SYSTEM_PROMPT, user_prompt)
        except LLMError as exc:
            logger.error("LLM synthesis (from prior citations) failed: %s", exc)
            answer = (
                "Research Summary\n"
                "The response could not be generated due to a temporary issue with "
                "the language model service. The previously retrieved sources are "
                "listed below."
            )

        return answer, citations
