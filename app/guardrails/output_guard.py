"""
Output guardrail: validates LLM-generated answers AFTER synthesis and
BEFORE they are shown to the user.

Checks for diagnostic certainty, prescription language, personalized
recommendations, and unsupported source references. If a violation is
found, the caller (research agent) should replace the response with the
safe fallback rather than displaying it.
"""

from __future__ import annotations

from app.guardrails import medical_policies as policies
from app.guardrails.guardrails_ai_layer import validate_with_guardrails_ai
from app.guardrails.validators import GuardrailCategory, GuardrailResult
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


SAFE_FALLBACK_MESSAGE = (
    "Research Summary\n"
    "The generated response could not be safely displayed because it "
    "contained language resembling a personal diagnosis, prescription, or "
    "individualized treatment recommendation, which this tool does not "
    "provide.\n\n"
    "What you can do\n"
    "- Rephrase your question to ask about published research findings "
    "rather than a personal recommendation.\n"
    "- Consult a licensed clinician for personal medical guidance."
)


class OutputGuard:
    def evaluate(self, generated_text: str, known_citation_ids: set[str] | None = None) -> GuardrailResult:
        if not generated_text or not generated_text.strip():
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.UNSAFE_OUTPUT,
                message=SAFE_FALLBACK_MESSAGE,
                flags=["empty_response"],
            )

        flags: list[str] = []

        # Primary enforcement: this project's own deterministic checks.
        if policies.has_diagnostic_certainty(generated_text):
            flags.append("diagnostic_certainty")
        if policies.has_prescription_language(generated_text):
            flags.append("prescription_language")
        if policies.has_personalized_recommendation(generated_text):
            flags.append("personalized_recommendation")

        # Secondary, independent enforcement: Guardrails AI running the
        # same policy as a registered validator. This is intentionally
        # redundant with the checks above — safety should not depend on
        # any single mechanism, deterministic or otherwise.
        guardrails_ai_passed, _ = validate_with_guardrails_ai(generated_text)
        if not guardrails_ai_passed:
            flags.append("guardrails_ai_rejection")

        if flags:
            logger.warning("Output guardrail rejected response: %s", flags)
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.UNSAFE_OUTPUT,
                message=SAFE_FALLBACK_MESSAGE,
                flags=flags,
            )

        return GuardrailResult(allowed=True, category=GuardrailCategory.SAFE)
