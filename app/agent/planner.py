"""
Research planner: a small, deterministic classifier that decides which
tools the agent should run for a given question. This is intentionally
rule-based rather than an LLM call, so tool selection is predictable and
cheap. It can be swapped for a model-based classifier later without
changing the orchestrator's interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

DOCUMENT_HINT_PATTERNS = [
    r"\btrial\b",
    r"\bclinical trial\b",
    r"\bstudy (report|document|pdf)\b",
    r"\buploaded\b",
    r"\bthe document\b",
    r"\bthe pdf\b",
    r"\bindexed\b",
]

# Phrases that indicate the user is asking about evidence already surfaced
# earlier in the conversation, rather than introducing a new research topic
# to search for. Running a fresh PubMed/vector search on text like "summarize
# the evidence you found" returns nothing, because the phrase itself isn't a
# medical topic — the actual topic lives in the previous turn.
FOLLOW_UP_PATTERNS = [
    r"\bthe evidence you found\b",
    r"\bevidence you (found|retrieved|gathered)\b",
    r"\bsources you (used|found|cited)\b",
    r"\bwhat you (just )?found\b",
    r"\bsummarize (that|this|the (evidence|sources|findings|results))\b",
    r"\bcite the sources (you )?used\b",
    r"\bthose (sources|studies|papers|findings)\b",
    r"\bthat (last )?(answer|response|result)\b",
]


@dataclass
class ResearchPlan:
    use_pubmed: bool
    use_vector_search: bool
    is_follow_up: bool
    reasoning: str


class ResearchPlanner:
    def plan(self, question: str, vector_store_has_documents: bool) -> ResearchPlan:
        lowered = question.lower()
        mentions_documents = any(re.search(p, lowered) for p in DOCUMENT_HINT_PATTERNS)
        is_follow_up = any(re.search(p, lowered) for p in FOLLOW_UP_PATTERNS)

        if is_follow_up:
            return ResearchPlan(
                use_pubmed=False,
                use_vector_search=False,
                is_follow_up=True,
                reasoning=(
                    "Question refers to evidence already retrieved earlier in this "
                    "session; reusing prior citations instead of running a new search."
                ),
            )

        use_pubmed = True  # PubMed is the default evidence source for research questions
        use_vector_search = vector_store_has_documents  # only search local docs if any exist

        reasoning_parts = ["PubMed search enabled by default for literature evidence."]
        if use_vector_search:
            reasoning_parts.append("Indexed documents are available, so vector search is enabled.")
        else:
            reasoning_parts.append("No indexed documents found, so vector search is skipped.")
        if mentions_documents and not vector_store_has_documents:
            reasoning_parts.append(
                "Question references documents/trials but none are indexed yet."
            )

        return ResearchPlan(
            use_pubmed=use_pubmed,
            use_vector_search=use_vector_search,
            is_follow_up=False,
            reasoning=" ".join(reasoning_parts),
        )
