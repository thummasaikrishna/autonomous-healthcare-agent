"""
Deterministic pattern definitions for medical safety guardrails.

These are intentionally rule-based (not LLM-based) so that safety behavior
is predictable, testable, and does not depend on the LLM choosing to follow
instructions. The LLM is a synthesis engine here, not the safety mechanism.

Patterns are deliberately broad, covering multiple natural phrasings of the
same underlying request, since real users rarely phrase things in the exact
canonical form. Where regex phrasing coverage isn't reliable enough (e.g.
detecting an in-progress medical emergency described across several
symptoms), a small keyword-combination heuristic is used instead.
"""

from __future__ import annotations

import re

# --- Input categories -------------------------------------------------

DIAGNOSIS_PATTERNS = [
    r"\bdo i have\b",
    r"\bdo you think i have\b",
    r"\bcould i have\b",
    r"\bmight i have\b",
    r"\bdo i possibly have\b",
    r"\bwhat do i have\b",
    r"\bwhat disease do i have\b",
    r"\bwhat('?s| is) wrong with me\b",
    r"\bwhat('?s| is) causing my\b",
    r"\bam i (sick|ill|dying)\b",
    r"\bcan you diagnose\b",
    r"\bdiagnose (me|my|us)\b",
    r"\bidentify my condition\b",
    r"\bwhat condition do i have\b",
    r"\bwhat condition (do|might|could) i (have|be experiencing)\b",
    r"\bbased on (my|these) symptoms.*(do i have|what.*have)\b",
    r"\btell me what('s| is) wrong with me\b",
]

PRESCRIPTION_PATTERNS = [
    r"\bwhat (dose|dosage) (of|should|do|i)\b",
    r"\b(dose|dosage) (should i|i should)\b",
    r"\bhow much .* (should i take|mg|milligrams|ml)\b",
    r"\bwhat medication should i take\b",
    r"\bwhich (medication|drug|antibiotic|pill|medicine) should i (take|use)\b",
    r"\bexactly which (antibiotic|medication|drug|medicine|pill)\b",
    r"\bprescribe\b",
    r"\bcan you prescribe\b",
    r"\bwhat drug should i take\b",
    r"\bhow many (pills|tablets|mg)\b",
]

PERSONALIZED_TREATMENT_PATTERNS = [
    r"\bwhat treatment should i (personally )?use\b",
    r"\bwhat should i do (about|for) my\b",
    r"\bhow (should|do) i treat my\b",
    r"\bwhat('?s| is) the best treatment for me\b",
    r"\bshould i (take|start|stop) .*(medication|treatment|therapy)\b",
    r"\bwhat treatment plan\b.*\bfor me\b",
    r"\bwhich (medication|drug|treatment|therapy) should i (personally )?(start|take|use|begin)\b",
    r"\bshould i (personally )?(start|begin) taking\b",
    r"\bwhat should i (personally )?take\b",
    r"\bwhat('?s| is) right for me\b",
]

EMERGENCY_PATTERNS = [
    r"\bsevere chest pain\b",
    r"\bcan'?t breathe\b",
    r"\bcannot breathe\b",
    r"\bdifficulty breathing\b",
    r"\btrouble breathing\b",
    r"\bsuicidal\b",
    r"\bsuicidal thoughts\b",
    r"\bwant to (kill myself|die|hurt myself|end my life)\b",
    r"\bheart attack\b.*\b(now|right now|happening)\b",
    r"\bstroke\b.*\b(now|right now|happening|symptoms)\b",
    r"\bsevere bleeding\b",
    r"\boverdose\b",
    r"\banaphylaxis\b",
    r"\ballergic reaction\b.*\b(severe|now|right now|can'?t breathe)\b",
    r"\bnot breathing\b",
    r"\bunconscious\b",
    r"\bslurred speech\b",
    r"\bface (is )?drooping\b",
    r"\bsudden numbness\b",
    r"\bpoisoned\b",
    r"\bvomiting blood\b",
    r"\bcoughing up blood\b",
]

# Symptom keywords that, when several appear together in a first-person,
# present-tense description, indicate someone may be describing a live
# emergency rather than asking an abstract research question. This catches
# phrasing that no single canonical pattern above would match, e.g.
# "I have chest pain, sweating, nausea and shortness of breath."
ACUTE_SYMPTOM_KEYWORDS = [
    "chest pain",
    "shortness of breath",
    "difficulty breathing",
    "trouble breathing",
    "sweating",
    "nausea",
    "vomiting",
    "left arm pain",
    "jaw pain",
    "severe headache",
    "sudden numbness",
    "slurred speech",
    "face drooping",
    "fainting",
    "dizziness",
    "severe abdominal pain",
    "coughing up blood",
    "vomiting blood",
]

FIRST_PERSON_SYMPTOM_PATTERN = re.compile(
    r"^\s*i\b|\bi (have|am having|feel|am experiencing|am feeling)\b"
)

# --- Output validation --------------------------------------------------

DIAGNOSTIC_CERTAINTY_PATTERNS = [
    r"\byou (have|are suffering from)\b",
    r"\byou definitely have\b",
    r"\bthis (confirms|proves) you have\b",
    r"\byour diagnosis is\b",
]

PRESCRIPTION_LANGUAGE_PATTERNS = [
    r"\byou should take \d+\s?(mg|milligrams|ml)\b",
    r"\btake \d+\s?(mg|milligrams|ml) of\b",
    r"\bi prescribe\b",
    r"\byour dosage should be\b",
]

PERSONALIZED_RECOMMENDATION_PATTERNS = [
    r"\byou should (start|stop|take|use) .*(medication|drug|therapy)\b",
    r"\bi recommend you (take|start|stop|use)\b",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def _count_acute_symptoms(text: str) -> int:
    lowered = text.lower()
    return sum(1 for keyword in ACUTE_SYMPTOM_KEYWORDS if keyword in lowered)


def is_diagnosis_request(text: str) -> bool:
    return _matches_any(text, DIAGNOSIS_PATTERNS)


def is_prescription_request(text: str) -> bool:
    return _matches_any(text, PRESCRIPTION_PATTERNS)


def is_personalized_treatment_request(text: str) -> bool:
    return _matches_any(text, PERSONALIZED_TREATMENT_PATTERNS)


def is_emergency_request(text: str) -> bool:
    if _matches_any(text, EMERGENCY_PATTERNS):
        return True

    # Two or more acute symptoms described in the first person suggests a
    # real-time emergency being described, even without a canonical phrase.
    if FIRST_PERSON_SYMPTOM_PATTERN.search(text.lower()) and _count_acute_symptoms(text) >= 2:
        return True

    return False


def has_diagnostic_certainty(text: str) -> bool:
    return _matches_any(text, DIAGNOSTIC_CERTAINTY_PATTERNS)


def has_prescription_language(text: str) -> bool:
    return _matches_any(text, PRESCRIPTION_LANGUAGE_PATTERNS)


def has_personalized_recommendation(text: str) -> bool:
    return _matches_any(text, PERSONALIZED_RECOMMENDATION_PATTERNS)
