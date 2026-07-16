"""Stage 14 governance — per-allocation gate and portfolio-level kill criteria (fail-closed).

No allocation is permitted unless every rule passes; failing any rule sets the allocation to zero.
Portfolio kill criteria are distinct from per-strategy kills: they can halt the whole book, force
defensive mode, or stop new capital based on portfolio DSR, survival, drawdown, and walk-forward.
"""

from __future__ import annotations

from libs.stage14.models import KillDecision


def portfolio_governance_gate(
    *,
    signal_approved: bool,
    expected_value: float,
    portfolio_contribution: float,
    capacity_available: bool,
    survival_score: float,
    fragility: float,
    correlation_acceptable: bool,
    walk_forward_passed: bool,
    survival_threshold: float = 60.0,
    max_fragility: float = 0.6,
) -> tuple[bool, str]:
    """Return (allowed, reason). Allocation must be zeroed unless allowed is True."""
    if not signal_approved:
        return False, "signal not approved"
    if expected_value <= 0:
        return False, "expected value not positive"
    if portfolio_contribution <= 0:
        return False, "portfolio contribution not positive"
    if not capacity_available:
        return False, "capacity unavailable"
    if survival_score < survival_threshold:
        return False, f"survival score {survival_score:.1f} < {survival_threshold}"
    if fragility > max_fragility:
        return False, f"fragility {fragility:.2f} > {max_fragility}"
    if not correlation_acceptable:
        return False, "portfolio correlation unacceptable"
    if not walk_forward_passed:
        return False, "portfolio walk-forward not passed"
    return True, "approved"


class PortfolioKillCriteria:
    """Portfolio-level halt / defensive / no-new-capital decisions."""

    def __init__(
        self,
        *,
        min_dsr: float = 0.0,
        min_survival_score: float = 50.0,
        max_drawdown: float = 0.20,
    ) -> None:
        self.min_dsr = min_dsr
        self.min_survival_score = min_survival_score
        self.max_drawdown = max_drawdown

    def evaluate(
        self,
        *,
        portfolio_dsr: float,
        survival_score: float,
        drawdown: float,
        walk_forward_passed: bool,
    ) -> KillDecision:
        reasons: list[str] = []
        halt = False
        defensive = False
        no_new_capital = False
        if portfolio_dsr < self.min_dsr:
            halt = True
            reasons.append(f"portfolio DSR {portfolio_dsr:.2f} < {self.min_dsr}")
        if survival_score < self.min_survival_score:
            halt = True
            reasons.append(f"survival score {survival_score:.1f} < {self.min_survival_score}")
        if drawdown > self.max_drawdown:
            defensive = True
            reasons.append(f"drawdown {drawdown:.2%} > {self.max_drawdown:.2%}")
        if not walk_forward_passed:
            no_new_capital = True
            reasons.append("portfolio walk-forward failed")
        return KillDecision(
            halt=halt, defensive_mode=defensive, no_new_capital=no_new_capital, reasons=reasons
        )
