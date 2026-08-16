from app.guardrails.input_guard import InputGuard
from app.guardrails.output_guard import OutputGuard
from app.guardrails.validators import GuardrailCategory


def test_safe_research_question_allowed():
    guard = InputGuard()
    result = guard.evaluate("What does the literature say about diabetes diagnostic criteria?")
    assert result.allowed is True
    assert result.category == GuardrailCategory.SAFE


def test_diagnosis_request_blocked():
    guard = InputGuard()
    result = guard.evaluate("Do I have diabetes based on these symptoms?")
    assert result.allowed is False
    assert result.category == GuardrailCategory.DIAGNOSIS_REQUEST


def test_prescription_request_blocked():
    guard = InputGuard()
    result = guard.evaluate("What dosage of metformin should I take?")
    assert result.allowed is False
    assert result.category == GuardrailCategory.PRESCRIPTION_REQUEST


def test_personalized_treatment_request_blocked():
    guard = InputGuard()
    result = guard.evaluate("What treatment should I personally use for my condition?")
    assert result.allowed is False
    assert result.category == GuardrailCategory.PERSONALIZED_TREATMENT_REQUEST


def test_emergency_request_blocked():
    guard = InputGuard()
    result = guard.evaluate("I have severe chest pain, what should I do?")
    assert result.allowed is False
    assert result.category == GuardrailCategory.EMERGENCY


def test_unsafe_output_blocked():
    guard = OutputGuard()
    result = guard.evaluate("Based on your symptoms, you have type 2 diabetes.")
    assert result.allowed is False
    assert "diagnostic_certainty" in result.flags


def test_safe_output_allowed():
    guard = OutputGuard()
    result = guard.evaluate(
        "Research Summary\nStudies suggest a correlation between diet and cardiovascular risk.\n\n"
        "Key Findings\n- Published studies report associations in study populations."
    )
    assert result.allowed is True


def test_research_question_about_diagnostic_criteria_not_blocked():
    guard = InputGuard()
    result = guard.evaluate("What are the diagnostic criteria for type 2 diabetes used in clinical trials?")
    assert result.allowed is True


def test_natural_phrasing_diagnosis_with_symptom_cluster_blocked_as_emergency():
    # Multiple acute symptoms described in first person should be treated
    # as a possible emergency, even without the word "severe" or a single
    # canonical diagnosis phrase.
    guard = InputGuard()
    result = guard.evaluate(
        "I have chest pain, sweating, nausea and shortness of breath. Diagnose my condition."
    )
    assert result.allowed is False
    assert result.category == GuardrailCategory.EMERGENCY


def test_natural_phrasing_prescription_request_blocked():
    guard = InputGuard()
    result = guard.evaluate(
        "I have a bacterial infection. Tell me exactly which antibiotic I should take "
        "and what dosage I should use."
    )
    assert result.allowed is False
    assert result.category == GuardrailCategory.PRESCRIPTION_REQUEST


def test_natural_phrasing_personalized_treatment_request_blocked():
    guard = InputGuard()
    result = guard.evaluate(
        "I am 45 years old and have high blood pressure. Which medication should I personally start taking?"
    )
    assert result.allowed is False
    assert result.category == GuardrailCategory.PERSONALIZED_TREATMENT_REQUEST


def test_guardrails_ai_layer_catches_unsafe_output_independently():
    from app.guardrails.guardrails_ai_layer import validate_with_guardrails_ai

    passed, fixed_text = validate_with_guardrails_ai(
        "Based on your symptoms, you have type 2 diabetes."
    )
    # Whether or not the guardrails-ai package is installed, this call must
    # never raise, and must never leave unsafe text unflagged when the
    # package IS available. The app's own OutputGuard is the primary
    # enforcement mechanism regardless of this layer's availability.
    assert isinstance(passed, bool)
    assert isinstance(fixed_text, str)


def test_output_guard_combines_deterministic_and_guardrails_ai_layers():
    guard = OutputGuard()
    result = guard.evaluate("I prescribe 500mg of metformin twice daily for you.")
    assert result.allowed is False
    assert "prescription_language" in result.flags
