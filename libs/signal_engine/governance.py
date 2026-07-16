"""Global governance gate — no capital without passing every validation test.

Mirrors the platform-wide rule: a signal may only become BUY/SELL if CPCV, DSR, PBO, Deflated
Sharpe, Reality Check, Capacity, Structural Break, and the live shadow period all pass. The gate
is fail-closed: every verdict defaults to ``False``, so anything unspecified blocks production.
Stage 13.5 consumes these verdicts (from the validation layer); it may not relax the thresholds.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.signal_engine.errors import SignalGovernanceError


class GovernanceVerdict(BaseModel):
    """The eight validation verdicts that gate production capital (fail-closed defaults)."""

    model_config = ConfigDict(frozen=True)

    cpcv_pass: bool = False
    dsr_pass: bool = False
    pbo_pass: bool = False
    deflated_sharpe_pass: bool = False
    reality_check_pass: bool = False
    capacity_pass: bool = False
    structural_break_pass: bool = False
    shadow_period_complete: bool = False


def signal_governance_gate(verdict: GovernanceVerdict) -> bool:
    """True only if every validation gate passes."""
    return bool(
        verdict.cpcv_pass
        and verdict.dsr_pass
        and verdict.pbo_pass
        and verdict.deflated_sharpe_pass
        and verdict.reality_check_pass
        and verdict.capacity_pass
        and verdict.structural_break_pass
        and verdict.shadow_period_complete
    )


def require_governance(verdict: GovernanceVerdict) -> None:
    """Raise :class:`SignalGovernanceError` unless every gate passes."""
    if not signal_governance_gate(verdict):
        raise SignalGovernanceError("signal failed the mandatory validation gauntlet")
