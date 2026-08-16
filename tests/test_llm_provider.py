from unittest.mock import MagicMock, patch

import pytest

from app.llm.provider import DemoProvider, GroqProvider, LLMError


def test_demo_provider_returns_labeled_placeholder():
    provider = DemoProvider()
    result = provider.generate("system prompt", "user prompt")
    assert "DEMO MODE" in result
    assert "Key Findings" in result
    assert "Safety Notice" not in result
    assert "Evidence Quality / Limitations" not in result


def test_groq_provider_parses_successful_response():
    provider = GroqProvider()
    provider.api_key = "test-key"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Research Summary\nGenerated answer text."}}]
    }

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = provider.generate("system prompt", "user prompt")

    assert "Generated answer text" in result
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_groq_provider_raises_llm_error_on_network_failure():
    import requests

    provider = GroqProvider()
    provider.api_key = "test-key"

    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("down")):
        with pytest.raises(LLMError):
            provider.generate("system prompt", "user prompt")


def test_groq_provider_raises_llm_error_on_malformed_response():
    provider = GroqProvider()
    provider.api_key = "test-key"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"unexpected": "shape"}

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(LLMError):
            provider.generate("system prompt", "user prompt")


def test_groq_provider_surfaces_api_error_body_eg_decommissioned_model():
    """
    Regression test: this is exactly the failure mode hit in practice when
    a configured model was deprecated server-side. The provider must
    surface the API's actual error text rather than a generic message.
    """
    provider = GroqProvider()
    provider.api_key = "test-key"

    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 400
    mock_response.text = '{"error": {"message": "model has been decommissioned"}}'

    with patch("requests.post", return_value=mock_response):
        with pytest.raises(LLMError, match="decommissioned"):
            provider.generate("system prompt", "user prompt")
