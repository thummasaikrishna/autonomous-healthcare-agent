from unittest.mock import MagicMock

from app.agent.research_agent import ResearchAgent
from app.research.pubmed_client import PubMedArticle


def _make_agent_with_mocks(pubmed_results=None, document_results=None):
    agent = ResearchAgent.__new__(ResearchAgent)  # bypass __init__ to inject mocks directly

    from app.guardrails.input_guard import InputGuard
    from app.guardrails.output_guard import OutputGuard
    from app.agent.planner import ResearchPlanner
    from app.agent.synthesizer import Synthesizer
    from app.llm.provider import DemoProvider

    agent.input_guard = InputGuard()
    agent.output_guard = OutputGuard()
    agent.planner = ResearchPlanner()
    agent.synthesizer = Synthesizer(DemoProvider())

    agent.pubmed_client = MagicMock()
    agent.pubmed_client.search.return_value = pubmed_results or []

    agent.retriever = MagicMock()
    agent.retriever.retrieve.return_value = document_results or []

    agent.store = MagicMock()
    agent.store.count.return_value = len(document_results or [])

    return agent


def test_tool_selection_uses_pubmed_by_default():
    article = PubMedArticle(
        pmid="1", title="Test paper", authors=["A"], abstract="Abstract text",
        journal="J", publication_date="2023", doi="", url="https://pubmed.ncbi.nlm.nih.gov/1/"
    )
    agent = _make_agent_with_mocks(pubmed_results=[article])

    result = agent.run("What does research say about hypertension management?")

    agent.pubmed_client.search.assert_called_once()
    assert result.blocked is False
    assert len(result.citations) == 1


def test_evidence_collection_empty_returns_insufficient_evidence_message():
    agent = _make_agent_with_mocks(pubmed_results=[], document_results=[])

    result = agent.run("What does research say about an extremely obscure topic?")

    assert result.blocked is False
    assert "Insufficient evidence" in result.answer
    assert result.citations == []


def test_input_guardrail_blocks_before_tool_execution():
    agent = _make_agent_with_mocks()

    result = agent.run("Do I have diabetes based on these symptoms?")

    assert result.blocked is True
    agent.pubmed_client.search.assert_not_called()
    agent.retriever.retrieve.assert_not_called()


def test_failure_handling_when_pubmed_raises():
    agent = _make_agent_with_mocks()
    agent.pubmed_client.search.side_effect = Exception("simulated network failure")

    # The agent should catch unexpected tool failures and still return a
    # usable (non-crashing) result rather than propagating the exception.
    result = agent.run("What does research say about asthma triggers?")

    assert result.blocked is False
    assert "Insufficient evidence" in result.answer


def test_follow_up_question_reuses_prior_citations_without_new_search():
    from app.research.citation import Citation

    agent = _make_agent_with_mocks()
    prior = [
        Citation(
            source_type="pubmed",
            title="Aspirin and cardiovascular outcomes",
            identifier="123456",
            url="https://pubmed.ncbi.nlm.nih.gov/123456/",
            metadata={"journal": "Cardiology Today", "publication_date": "2022", "abstract": "..."},
        )
    ]

    result = agent.run("Give me a concise summary of the evidence you found and cite the sources used.", prior_citations=prior)

    agent.pubmed_client.search.assert_not_called()
    agent.retriever.retrieve.assert_not_called()
    assert result.blocked is False
    assert len(result.citations) == 1


def test_follow_up_question_with_no_prior_citations_says_so():
    agent = _make_agent_with_mocks()

    result = agent.run("Summarize the evidence you found.", prior_citations=[])

    assert result.blocked is False
    assert "no prior evidence" in result.answer.lower()
