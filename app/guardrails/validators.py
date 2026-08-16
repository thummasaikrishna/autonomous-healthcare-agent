"""
Validator dataclasses shared by input_guard and output_guard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GuardrailCategory(str, Enum):
    SAFE = "safe"
    DIAGNOSIS_REQUEST = "diagnosis_request"
    PRESCRIPTION_REQUEST = "prescription_request"
    PERSONALIZED_TREATMENT_REQUEST = "personalized_treatment_request"
    EMERGENCY = "emergency"
    UNSAFE_OUTPUT = "unsafe_output"


@dataclass
class GuardrailResult:
    allowed: bool
    category: GuardrailCategory
    message: str = ""
    flags: list[str] = field(default_factory=list)
