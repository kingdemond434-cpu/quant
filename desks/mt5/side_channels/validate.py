"""Pipeline Stage 2: Validation — statistical gauntlet on historical data."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BASE = Path(__file__).resolve().parent.parent.parent
HYPOTHESES_DIR = BASE / "hypotheses"
REPORTS_DIR = BASE / "reports"


@dataclass
class GateResult:
    """Result of a single gate evaluation."""
    gate: str
    passed: bool
    metrics: dict[str, Any]
    classification: str  # validity | power


@dataclass
class ValidationResult:
    """Complete validation result for a hypothesis."""
    hypothesis_id: str
    gates: dict[str, GateResult]
    validity_pass: bool
    power_deficiencies: list[str]
    status: str  # PASSED | VALIDITY_FAILED | POWER_DEFICIENT


def validate_hypothesis(hypothesis_id: str) -> ValidationResult:
    """Run the full 10-gate validation on a hypothesis.

    Delegates to qquant_gates.py / universal_gate.py for actual computation.
    """
    # Load hypothesis
    hyp_path = HYPOTHESES_DIR / f"{hypothesis_id}.yaml"
    if not hyp_path.exists():
        raise FileNotFoundError(f"Hypothesis not found: {hypothesis_id}")

    with open(hyp_path, "r", encoding="utf-8") as f:
        hyp = yaml.safe_load(f)

    # Run validation via existing gate machinery
    # This would call qquant_gates.main() or universal_gate.main()
    # For now, return a stub that integrates with existing system

    # The actual implementation would:
    # 1. Load data for hypothesis symbols
    # 2. Generate signals for each parameter combination
    # 3. Run backtests
    # 4. Compute all 10 gate statistics
    # 5. Classify as validity/power
    # 6. Return structured result

    # This is a placeholder - the real work happens in qquant_gates.py
    return ValidationResult(
        hypothesis_id=hypothesis_id,
        gates={},
        validity_pass=False,
        power_deficiencies=[],
        status="PENDING"
    )


def run_validation(hypothesis_ids: list[str]) -> list[ValidationResult]:
    """Run validation for multiple hypotheses."""
    return [validate_hypothesis(hid) for hid in hypothesis_ids]


if __name__ == "__main__":
    import sys
    ids = sys.argv[1:] if len(sys.argv) > 1 else []
    for r in run_validation(ids):
        print(f"{r.hypothesis_id}: {r.status}")