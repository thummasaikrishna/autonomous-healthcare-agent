"""
Guardrails AI integration layer.

The project's actual safety enforcement is the deterministic, regex-based
logic in medical_policies.py / input_guard.py / output_guard.py — per the
project requirements, safety must not depend solely on an LLM's judgment.

This module wraps that same deterministic logic as a registered Guardrails
AI validator, so the Guardrails AI framework itself sits on the output path
as an additional, independent compliance layer (useful for teams that want
Guardrails AI's structured validation/reporting on top of the app's own
checks). If the guardrails-ai package is not installed, this module degrades
to a no-op so the rest of the application is unaffected.
"""

from __future__ import annotations

import os

# Guardrails AI initializes an OpenTelemetry exporter at import time that
# tries to reach a hosted collector; in offline/sandboxed environments this
# produces harmless but noisy "403 Forbidden" errors on a background
# thread. The standard OTel SDK env var below disables it before import.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from app.guardrails import medical_policies as policies
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

try:
    from guardrails.settings import settings as _guardrails_settings

    _guardrails_settings.disable_tracing = True
except ImportError:
    pass

try:
    from guardrails.validator_base import (
        FailResult,
        PassResult,
        Validator,
        register_validator,
    )

    GUARDRAILS_AI_AVAILABLE = True

    @register_validator(name="medical-safety-check", data_type="string")
    class MedicalSafetyValidator(Validator):
        """
        Guardrails AI validator that reuses this project's deterministic
        medical-safety pattern checks (diagnostic certainty, prescription
        language, personalized recommendations) rather than an LLM call.
        """

        def validate(self, value: str, metadata: dict) -> "PassResult | FailResult":
            flags = []
            if policies.has_diagnostic_certainty(value):
                flags.append("diagnostic_certainty")
            if policies.has_prescription_language(value):
                flags.append("prescription_language")
            if policies.has_personalized_recommendation(value):
                flags.append("personalized_recommendation")

            if flags:
                return FailResult(
                    error_message=f"Response violates medical safety policy: {', '.join(flags)}",
                    fix_value="This response was withheld for medical safety reasons.",
                )
            return PassResult()

except ImportError:
    GUARDRAILS_AI_AVAILABLE = False
    logger.info("guardrails-ai package not installed; Guardrails AI layer is a no-op.")


def build_guardrails_ai_guard():
    """
    Returns a configured Guardrails AI Guard using MedicalSafetyValidator,
    or None if the guardrails-ai package is unavailable.
    """
    if not GUARDRAILS_AI_AVAILABLE:
        return None
    try:
        from guardrails import Guard

        return Guard().use(MedicalSafetyValidator(on_fail="fix"))
    except Exception as exc:
        logger.warning("Could not build Guardrails AI guard: %s", exc)
        return None


def validate_with_guardrails_ai(text: str) -> tuple[bool, str]:
    """
    Runs text through the Guardrails AI layer if available.
    Returns (passed, possibly_fixed_text). If the package is unavailable,
    always returns (True, text) unchanged — this layer is supplementary,
    not the primary enforcement mechanism.
    """
    guard = build_guardrails_ai_guard()
    if guard is None:
        return True, text

    try:
        outcome = guard.validate(text)
        passed = bool(getattr(outcome, "validation_passed", True))
        fixed_text = getattr(outcome, "validated_output", text) or text
        return passed, fixed_text
    except Exception as exc:
        logger.warning("Guardrails AI validation call failed, passing through: %s", exc)
        return True, text
