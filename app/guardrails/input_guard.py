"""
Input guardrail: evaluates a user's question BEFORE any research runs.

The goal is to distinguish legitimate research questions (allowed) from
requests for personal diagnosis, dosage, personalized treatment, or
emergency management (redirected to a safe, fixed response) — without
blocking medical topics wholesale.
"""

from __future__ import annotations

from app.guardrails import medical_policies as policies
from app.guardrails.validators import GuardrailCategory, GuardrailResult
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


EMERGENCY_MESSAGE = (
    "This appears to describe a possible medical emergency. This tool cannot "
    "provide emergency medical care. Please contact your local emergency "
    "services number immediately or go to the nearest emergency department. "
    "If you are in the United States, you can call or text 988 for a mental "
    "health crisis, or 911 for a medical emergency."
)

DIAGNOSIS_MESSAGE = (
    "This tool cannot determine whether you personally have a medical "
    "condition. It can summarize what published research says about a "
    "topic — for example, diagnostic criteria used in studies, or how a "
    "condition is generally characterized in the literature. Please consult "
    "a licensed clinician for a personal diagnosis. You're welcome to "
    "rephrase your question as a research question."
)

PRESCRIPTION_MESSAGE = (
    "This tool cannot provide personalized medication dosage instructions. "
    "Dosage decisions depend on individual medical history and must come "
    "from a licensed prescriber or pharmacist. I can summarize general "
    "research findings about a medication if you'd like — just ask about "
    "the research rather than a personal dose."
)

PERSONALIZED_TREATMENT_MESSAGE = (
    "This tool cannot recommend a personal treatment plan. Treatment "
    "decisions require an individualized evaluation by a licensed clinician "
    "who knows your medical history. I can summarize what research studies "
    "have found about treatment approaches for a condition in general, if "
    "that would help."
)


class InputGuard:
    def evaluate(self, question: str) -> GuardrailResult:
        if not question or not question.strip():
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.SAFE,
                message="Please enter a research question.",
            )

        # Emergency check takes priority over everything else.
        if policies.is_emergency_request(question):
            logger.info("Input guardrail: emergency pattern detected.")
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.EMERGENCY,
                message=EMERGENCY_MESSAGE,
                flags=["emergency"],
            )

        if policies.is_diagnosis_request(question):
            logger.info("Input guardrail: diagnosis request detected.")
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.DIAGNOSIS_REQUEST,
                message=DIAGNOSIS_MESSAGE,
                flags=["diagnosis_request"],
            )

        if policies.is_prescription_request(question):
            logger.info("Input guardrail: prescription request detected.")
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.PRESCRIPTION_REQUEST,
                message=PRESCRIPTION_MESSAGE,
                flags=["prescription_request"],
            )

        if policies.is_personalized_treatment_request(question):
            logger.info("Input guardrail: personalized treatment request detected.")
            return GuardrailResult(
                allowed=False,
                category=GuardrailCategory.PERSONALIZED_TREATMENT_REQUEST,
                message=PERSONALIZED_TREATMENT_MESSAGE,
                flags=["personalized_treatment_request"],
            )

        return GuardrailResult(allowed=True, category=GuardrailCategory.SAFE)
