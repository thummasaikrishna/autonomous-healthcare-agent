"""
PubMed client built on the official NCBI E-utilities (esearch + efetch).

Design goals:
- Never fabricate a paper. If NCBI returns nothing, we return an empty list.
- Fail gracefully on network errors, timeouts, and malformed XML.
- Keep the returned data shape simple and predictable for the rest of the app.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict

import requests

from app.config.settings import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Words that carry no medical/topical meaning on their own. PubMed's
# Automatic Term Mapping treats unrecognized words as required free-text
# terms ANDed together, so a full natural-language question ("What does
# recent scientific literature say about...") can return zero hits even on
# a well-studied topic, simply because words like "does" or "say" don't
# literally appear in any abstract. Stripping these before a fallback retry
# fixes that without needing the caller to phrase queries in a special way.
_STOPWORDS = {
    "a", "an", "the", "of", "for", "and", "or", "in", "on", "at", "to", "is",
    "are", "was", "were", "what", "does", "do", "did", "say", "says", "about",
    "tell", "me", "please", "can", "you", "give", "information", "research",
    "literature", "scientific", "summarize", "summary", "concise", "evidence",
    "found", "cite", "sources", "used", "that", "this", "with", "from", "by",
    "as", "be", "been", "being", "it", "its", "their", "there", "how", "which",
    "who", "when", "where", "why", "known", "recent", "recently", "current",
}


class PubMedError(Exception):
    """Raised when PubMed cannot be reached or returns something unusable."""


@dataclass
class PubMedArticle:
    pmid: str
    title: str
    authors: list[str]
    abstract: str
    journal: str
    publication_date: str
    doi: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


class PubMedClient:
    """Thin, defensive wrapper around NCBI E-utilities."""

    def __init__(self):
        self.base_url = settings.pubmed_base_url
        self.email = settings.pubmed_email
        self.tool = settings.pubmed_tool_name
        self.api_key = settings.pubmed_api_key
        self.timeout = settings.pubmed_timeout_seconds
        self.max_retries = settings.pubmed_max_retries

    def _common_params(self) -> dict:
        params = {"tool": self.tool, "email": self.email or "researcher@example.com"}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _request(self, endpoint: str, params: dict) -> requests.Response:
        url = f"{self.base_url}/{endpoint}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout as exc:
                last_error = exc
                logger.warning("PubMed request timed out (attempt %s)", attempt + 1)
            except requests.exceptions.RequestException as exc:
                last_error = exc
                logger.warning("PubMed request failed (attempt %s): %s", attempt + 1, exc)

            if attempt < self.max_retries:
                time.sleep(0.5 * (attempt + 1))

        raise PubMedError(f"PubMed request to {endpoint} failed: {last_error}")

    @staticmethod
    def _simplify_query(query: str) -> str:
        """Strip filler/question words down to the meaningful keyword terms."""
        cleaned = re.sub(r"[?!.,;:]", " ", query.lower())
        words = [w for w in cleaned.split() if w not in _STOPWORDS and len(w) > 1]
        simplified = " ".join(words)
        return simplified if simplified.strip() else query

    def search(self, query: str, max_results: int | None = None) -> list[PubMedArticle]:
        """
        Search PubMed for a natural-language query and return parsed articles.
        Returns an empty list (never raises to the caller for empty results).

        If the query as-written returns nothing, a simplified keyword-only
        version is tried once before giving up, since PubMed's term mapping
        often can't handle full natural-language sentences.
        """
        if not query or not query.strip():
            return []

        limit = max_results or settings.pubmed_max_results

        try:
            pmids = self._esearch(query, limit)

            if not pmids:
                simplified = self._simplify_query(query)
                if simplified.strip().lower() != query.strip().lower():
                    logger.info(
                        "PubMed returned no results for the full query; retrying with "
                        "simplified terms: '%s'",
                        simplified,
                    )
                    pmids = self._esearch(simplified, limit)

            if not pmids:
                logger.info("PubMed returned no results for query: %s", query)
                return []

            return self._efetch(pmids)
        except PubMedError as exc:
            logger.error("PubMed search failed: %s", exc)
            return []

    def _esearch(self, query: str, limit: int) -> list[str]:
        params = {
            **self._common_params(),
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": limit,
            "sort": "relevance",
        }
        response = self._request("esearch.fcgi", params)
        try:
            data = response.json()
            return data.get("esearchresult", {}).get("idlist", [])
        except ValueError as exc:
            raise PubMedError(f"Malformed esearch JSON response: {exc}") from exc

    def _efetch(self, pmids: list[str]) -> list[PubMedArticle]:
        params = {
            **self._common_params(),
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        response = self._request("efetch.fcgi", params)
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise PubMedError(f"Malformed efetch XML response: {exc}") from exc

        articles: list[PubMedArticle] = []
        for article_node in root.findall(".//PubmedArticle"):
            try:
                articles.append(self._parse_article(article_node))
            except Exception as exc:  # defensive: one bad record shouldn't kill the batch
                logger.warning("Skipping unparsable PubMed record: %s", exc)
        return articles

    @staticmethod
    def _text_or_default(node, path, default=""):
        found = node.find(path)
        if found is not None and found.text:
            return found.text.strip()
        return default

    def _parse_article(self, node: ET.Element) -> PubMedArticle:
        medline = node.find("MedlineCitation")
        article = medline.find("Article") if medline is not None else None

        pmid = self._text_or_default(medline, "PMID", "")

        title = self._text_or_default(article, "ArticleTitle", "Untitled")

        abstract_parts = []
        if article is not None:
            for abstract_text in article.findall(".//AbstractText"):
                if abstract_text.text:
                    abstract_parts.append(abstract_text.text.strip())
        abstract = " ".join(abstract_parts) if abstract_parts else "No abstract available."

        authors: list[str] = []
        if article is not None:
            for author in article.findall(".//AuthorList/Author"):
                last = author.find("LastName")
                fore = author.find("ForeName")
                if last is not None and last.text:
                    name = last.text
                    if fore is not None and fore.text:
                        name = f"{fore.text} {name}"
                    authors.append(name)

        journal = ""
        if article is not None:
            journal = self._text_or_default(article, "Journal/Title", "")

        pub_year = self._text_or_default(article, ".//PubDate/Year", "")
        pub_medline_date = self._text_or_default(article, ".//PubDate/MedlineDate", "")
        publication_date = pub_year or pub_medline_date or "Unknown"

        doi = ""
        if article is not None:
            for id_node in article.findall(".//ELocationID"):
                if id_node.get("EIdType") == "doi" and id_node.text:
                    doi = id_node.text.strip()
                    break

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        return PubMedArticle(
            pmid=pmid,
            title=title,
            authors=authors,
            abstract=abstract,
            journal=journal,
            publication_date=publication_date,
            doi=doi,
            url=url,
        )
