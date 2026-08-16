from unittest.mock import MagicMock, patch

import requests

from app.research.pubmed_client import PubMedClient, PubMedError

SAMPLE_EFETCH_XML = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <ArticleTitle>Effects of exercise on cardiovascular health</ArticleTitle>
        <Abstract>
          <AbstractText>This study examines cardiovascular outcomes.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Smith</LastName><ForeName>Jane</ForeName></Author>
        </AuthorList>
        <Journal><Title>Journal of Cardiology</Title></Journal>
        <ELocationID EIdType="doi">10.1000/example.doi</ELocationID>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""

SAMPLE_ESEARCH_JSON = {"esearchresult": {"idlist": ["12345678"]}}


def _mock_response(json_data=None, content=None, status=200):
    mock = MagicMock()
    mock.status_code = status
    if json_data is not None:
        mock.json.return_value = json_data
    if content is not None:
        mock.content = content
    mock.raise_for_status = MagicMock()
    return mock


def test_successful_search_and_parsing():
    client = PubMedClient()
    with patch("requests.get") as mock_get:
        mock_get.side_effect = [
            _mock_response(json_data=SAMPLE_ESEARCH_JSON),
            _mock_response(content=SAMPLE_EFETCH_XML),
        ]
        results = client.search("exercise cardiovascular health")

    assert len(results) == 1
    article = results[0]
    assert article.pmid == "12345678"
    assert article.title == "Effects of exercise on cardiovascular health"
    assert article.authors == ["Jane Smith"]
    assert article.doi == "10.1000/example.doi"
    assert article.url.endswith("12345678/")


def test_missing_fields_handled_safely():
    xml = b"""<?xml version="1.0"?>
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>999</PMID>
          <Article>
            <ArticleTitle>Untitled study</ArticleTitle>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>"""

    client = PubMedClient()
    with patch("requests.get") as mock_get:
        mock_get.side_effect = [
            _mock_response(json_data={"esearchresult": {"idlist": ["999"]}}),
            _mock_response(content=xml),
        ]
        results = client.search("some rare query")

    assert len(results) == 1
    assert results[0].abstract == "No abstract available."
    assert results[0].authors == []
    assert results[0].doi == ""


def test_empty_result_returns_empty_list():
    client = PubMedClient()
    with patch("requests.get") as mock_get:
        mock_get.return_value = _mock_response(json_data={"esearchresult": {"idlist": []}})
        results = client.search("an extremely obscure nonsense query xyz123")

    assert results == []


def test_api_failure_does_not_crash():
    client = PubMedClient()
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("network down")
        results = client.search("diabetes treatment")

    assert results == []


def test_never_fabricates_when_esearch_empty():
    client = PubMedClient()
    with patch("requests.get") as mock_get:
        mock_get.return_value = _mock_response(json_data={"esearchresult": {"idlist": []}})
        results = client.search("query with zero hits")
    assert results == []


def test_falls_back_to_simplified_query_when_full_sentence_returns_nothing():
    client = PubMedClient()
    with patch("requests.get") as mock_get:
        mock_get.side_effect = [
            _mock_response(json_data={"esearchresult": {"idlist": []}}),  # full sentence: 0 hits
            _mock_response(json_data=SAMPLE_ESEARCH_JSON),  # simplified keywords: hit
            _mock_response(content=SAMPLE_EFETCH_XML),
        ]
        results = client.search(
            "What does recent scientific literature say about the effectiveness "
            "of GLP-1 receptor agonists for obesity?"
        )

    assert len(results) == 1
    # Confirm the second esearch call used a simplified, keyword-only term.
    second_call_params = mock_get.call_args_list[1].kwargs["params"]
    assert "does" not in second_call_params["term"]
    assert "glp-1" in second_call_params["term"]


def test_simplify_query_strips_filler_words():
    simplified = PubMedClient._simplify_query(
        "What does recent scientific literature say about the effectiveness of "
        "GLP-1 receptor agonists for obesity?"
    )
    assert "does" not in simplified
    assert "recent" not in simplified
    assert "glp-1" in simplified
    assert "obesity" in simplified
