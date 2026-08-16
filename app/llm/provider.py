"""
LLM provider abstraction.

The rest of the application depends only on LLMProvider.generate(). The
concrete implementation (which vendor, which SDK call) lives in this one
module so the provider can be swapped later without touching the agent,
guardrails, or UI code.

If no API key is configured, the provider falls back to a deterministic
demo mode that returns a clearly-labeled placeholder response built from
whatever evidence was actually retrieved. This keeps the application
runnable end-to-end without any external key, while making it obvious the
answer was not model-generated.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.config.settings import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return a plain-text completion for the given prompts."""
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.model = settings.llm_model
        self.api_key = settings.llm_api_key
        self.max_tokens = settings.llm_max_tokens
        self.timeout = settings.llm_timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError(
                "The 'anthropic' package is not installed. Add it to requirements.txt."
            ) from exc

        try:
            client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout)
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text_parts = [block.text for block in response.content if block.type == "text"]
            return "\n".join(text_parts).strip()
        except Exception as exc:
            raise LLMError(f"Anthropic API call failed: {exc}") from exc


class GroqProvider(LLMProvider):
    """
    Groq's chat completion endpoint is OpenAI-compatible, so a plain HTTP
    call is enough and avoids pulling in an extra SDK dependency.
    """

    def __init__(self):
        self.model = settings.llm_model
        self.api_key = settings.llm_api_key
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature
        self.timeout = settings.llm_timeout_seconds
        self.base_url = settings.groq_base_url

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        import requests

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        last_error: str = ""
        for attempt in range(2):  # one retry for transient failures
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                if not response.ok:
                    # Surface the API's actual error body (e.g. "model
                    # decommissioned", invalid key, rate limit) instead of a
                    # generic message, so misconfiguration is diagnosable
                    # from the logs rather than looking like a random outage.
                    last_error = f"HTTP {response.status_code}: {response.text[:500]}"
                    logger.error("Groq API returned an error (attempt %s): %s", attempt + 1, last_error)
                    if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                        continue
                    raise LLMError(f"Groq API call failed: {last_error}")

                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except requests.exceptions.RequestException as exc:
                last_error = str(exc)
                logger.warning("Groq API request failed (attempt %s): %s", attempt + 1, exc)
                if attempt == 0:
                    continue
                raise LLMError(f"Groq API call failed: {last_error}") from exc
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMError(f"Unexpected Groq API response shape: {exc}") from exc

        raise LLMError(f"Groq API call failed after retry: {last_error}")


class DemoProvider(LLMProvider):
    """
    Deterministic, no-API-key fallback. Produces a clearly labeled summary
    built directly from the evidence passed in the prompt, so the whole
    pipeline remains demonstrable without a live LLM key.
    """

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("Using demo LLM provider (no API key configured).")
        return (
            "[DEMO MODE — no LLM API key configured]\n\n"
            "Research Summary\n"
            "An LLM API key has not been provided, so this is a placeholder "
            "synthesis rather than a generated answer. The retrieval pipeline "
            "(PubMed search and/or document search) ran normally and evidence "
            "was collected; configure LLM_API_KEY to generate a real synthesis "
            "of that evidence.\n\n"
            "Key Findings\n"
            "- Evidence retrieval completed; see Sources below.\n"
            "- No AI-generated interpretation is available in demo mode."
        )


def get_llm_provider() -> LLMProvider:
    if settings.demo_mode or not settings.llm_api_key:
        return DemoProvider()
    if settings.llm_provider == "anthropic":
        return AnthropicProvider()
    if settings.llm_provider == "groq":
        return GroqProvider()
    logger.warning("Unknown LLM_PROVIDER '%s', falling back to demo mode.", settings.llm_provider)
    return DemoProvider()
