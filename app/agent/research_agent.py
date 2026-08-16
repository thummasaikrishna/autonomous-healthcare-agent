"""
Research agent / orchestrator.

Coordinates the full pipeline for a single user question:
input guardrail -> plan -> PubMed / vector retrieval -> synthesize ->
output guardrail -> structured result.

This is a controlled, deterministic orchestrator (not a free-form
multi-agent system). Each step is a plain function call, which keeps the
flow easy to trace, test, and explain.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agent.planner import ResearchPlanner
from app.agent.synthesizer import Synthesizer
from app.guardrails.input_guard import InputGuard
from app.guardrails.output_guard import OutputGuard
from app.guardrails.validators import GuardrailCategory
from app.llm.provider import get_llm_provider
from app.research.citation import Citation
from app.research.pubmed_client import PubMedClient
from app.research.retriever import Retriever
from app.utils.logging_config import get_logger
from app.vectorstore.chroma_store import ChromaStore

logger = get_logger(__name__)


@dataclass
class ResearchResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""
    plan_reasoning: str = ""


class ResearchAgent:
    def __init__(
        self,
        pubmed_client: PubMedClient | None = None,
        retriever: Retriever | None = None,
        store: ChromaStore | None = None,
    ):
        self.input_guard = InputGuard()
        self.output_guard = OutputGuard()
        self.planner = ResearchPlanner()
        self.pubmed_client = pubmed_client or PubMedClient()
        self.store = store or ChromaStore()
        # Share the same store instance with the retriever so the
        # "has documents been indexed" check and the actual retrieval always
        # see the same underlying vector collection.
        self.retriever = retriever or Retriever(store=self.store)
        self.synthesizer = Synthesizer(get_llm_provider())

    def run(self, question: str, prior_citations: list[Citation] | None = None) -> ResearchResult:
        # Step 1: input guardrail
        input_result = self.input_guard.evaluate(question)
        if not input_result.allowed:
            logger.info("Question blocked by input guardrail: %s", input_result.category)
            return ResearchResult(
                answer=input_result.message,
                blocked=True,
                block_reason=input_result.category.value,
            )

        # Step 2: plan
        has_documents = self.store.count() > 0
        plan = self.planner.plan(question, vector_store_has_documents=has_documents)
        logger.info("Research plan: %s", plan.reasoning)

        # Step 2b: follow-up questions reuse prior evidence instead of
        # searching again on text that isn't itself a research topic.
        if plan.is_follow_up:
            answer, citations = self.synthesizer.synthesize_from_prior_citations(
                question, prior_citations or []
            )
            output_result = self.output_guard.evaluate(answer)
            if not output_result.allowed:
                return ResearchResult(
                    answer=output_result.message,
                    citations=[],
                    blocked=True,
                    block_reason=GuardrailCategory.UNSAFE_OUTPUT.value,
                    plan_reasoning=plan.reasoning,
                )
            return ResearchResult(
                answer=answer, citations=citations, blocked=False, plan_reasoning=plan.reasoning
            )

        # Step 3: execute tools (each wrapped so one tool failure doesn't crash the request)
        pubmed_evidence = []
        if plan.use_pubmed:
            try:
                pubmed_evidence = self.pubmed_client.search(question)
            except Exception as exc:
                logger.error("PubMed tool failed unexpectedly: %s", exc)
                pubmed_evidence = []

        document_evidence = []
        if plan.use_vector_search:
            try:
                document_evidence = self.retriever.retrieve(question)
            except Exception as exc:
                logger.error("Vector retrieval tool failed unexpectedly: %s", exc)
                document_evidence = []

        # Step 4: synthesize
        answer, citations = self.synthesizer.synthesize(question, pubmed_evidence, document_evidence)

        # Step 5: output guardrail
        output_result = self.output_guard.evaluate(answer)
        if not output_result.allowed:
            logger.warning("Answer blocked by output guardrail: %s", output_result.flags)
            return ResearchResult(
                answer=output_result.message,
                citations=[],
                blocked=True,
                block_reason=GuardrailCategory.UNSAFE_OUTPUT.value,
                plan_reasoning=plan.reasoning,
            )

        return ResearchResult(
            answer=answer,
            citations=citations,
            blocked=False,
            plan_reasoning=plan.reasoning,
        )
