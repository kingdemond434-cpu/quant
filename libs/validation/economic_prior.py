"""Economic-Prior Gate — the CRO's six questions, encoded.

The cheapest, highest-leverage filter: before any candidate consumes the expensive gauntlet it
must carry a structured artifact answering why it should work, why it might fail, why it might
be overfit, why it might decay, how decay is detected, and what replaces it. No artifact, no
validation budget. A blind statistical pattern with no mechanism is rejected here.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic import ValidationError as PydanticValidationError

REQUIRED_FIELDS = (
    "why_it_works",
    "why_it_might_fail",
    "why_overfit",
    "why_decay",
    "how_detect_decay",
    "what_replaces_it",
)


class MechanismType(StrEnum):
    STRUCTURAL = "structural"
    BEHAVIORAL = "behavioral"
    RISK_PREMIUM = "risk_premium"
    LIQUIDITY = "liquidity"


class EconomicPrior(BaseModel):
    """The mandatory six-question artifact."""

    model_config = ConfigDict(frozen=True)

    mechanism: MechanismType
    why_it_works: str
    why_it_might_fail: str
    why_overfit: str
    why_decay: str
    how_detect_decay: str
    what_replaces_it: str

    @field_validator(*REQUIRED_FIELDS)
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("answer must be non-empty")
        return value.strip()


class PriorGateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    missing: list[str]
    message: str

    def __bool__(self) -> bool:
        return self.passed


def economic_prior_gate(prior: Mapping[str, Any] | EconomicPrior) -> PriorGateResult:
    """Validate an economic-prior artifact. Missing mechanism or any blank answer fails."""
    if isinstance(prior, EconomicPrior):
        return PriorGateResult(passed=True, missing=[], message="economic prior complete")
    data = dict(prior)
    missing: list[str] = []
    if not data.get("mechanism"):
        missing.append("mechanism")
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    if missing:
        return PriorGateResult(
            passed=False, missing=missing, message=f"incomplete economic prior: {missing}"
        )
    try:
        EconomicPrior(**data)
    except PydanticValidationError as exc:
        return PriorGateResult(passed=False, missing=["invalid"], message=str(exc))
    return PriorGateResult(passed=True, missing=[], message="economic prior complete")
