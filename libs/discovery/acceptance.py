"""Institutional acceptance gates.

No alpha enters production unless it passes the full battery (DSR, CPCV, PBO, walk-forward,
holdout, cost stress, parameter stability, fragility, capacity, tail risk, stress scenarios,
regime robustness). No portfolio enters production unless survival > 95% and max drawdown < 20%
on top of the statistical gates. Fail closed: any failing gate rejects.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AcceptanceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    reasons: list[str]

    def __bool__(self) -> bool:
        return self.passed


def alpha_acceptance(
    *,
    dsr_pass: bool,
    pbo_pass: bool,
    cpcv_pass: bool,
    walk_forward_pass: bool,
    holdout_pass: bool,
    cost_pass: bool,
    parameter_stability_pass: bool,
    fragility_pass: bool,
    capacity_pass: bool,
    tail_pass: bool,
    stress_pass: bool,
    regime_pass: bool,
) -> AcceptanceResult:
    """Gate a single alpha against every institutional requirement."""
    gates = {
        "dsr": dsr_pass,
        "pbo": pbo_pass,
        "cpcv": cpcv_pass,
        "walk_forward": walk_forward_pass,
        "holdout": holdout_pass,
        "cost_stress": cost_pass,
        "parameter_stability": parameter_stability_pass,
        "fragility": fragility_pass,
        "capacity": capacity_pass,
        "tail_risk": tail_pass,
        "stress_scenario": stress_pass,
        "regime_robustness": regime_pass,
    }
    reasons = [name for name, ok in gates.items() if not ok]
    return AcceptanceResult(passed=not reasons, reasons=reasons)


def portfolio_acceptance(
    *,
    survival_probability: float,
    max_drawdown: float,
    dsr_pass: bool,
    cpcv_pass: bool,
    pbo_pass: bool,
    walk_forward_pass: bool,
    holdout_pass: bool,
    tail_pass: bool,
    stress_pass: bool,
    failure_independent: bool,
    family_balanced: bool,
    regime_diversified: bool,
    survival_min: float = 0.95,
    dd_limit: float = 0.20,
) -> AcceptanceResult:
    """Gate a portfolio: survival/drawdown plus the statistical and structural requirements."""
    gates = {
        "survival>95%": survival_probability >= survival_min,
        "max_drawdown<20%": max_drawdown < dd_limit,
        "dsr": dsr_pass,
        "cpcv": cpcv_pass,
        "pbo": pbo_pass,
        "walk_forward": walk_forward_pass,
        "holdout": holdout_pass,
        "tail_risk": tail_pass,
        "stress_scenario": stress_pass,
        "failure_dependency": failure_independent,
        "family_concentration": family_balanced,
        "regime_diversification": regime_diversified,
    }
    reasons = [name for name, ok in gates.items() if not ok]
    return AcceptanceResult(passed=not reasons, reasons=reasons)
