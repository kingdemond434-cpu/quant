"""Champion/challenger testing — promote a challenger only on hard evidence.

Compares a live champion variant against a challenger and recommends promotion only if the
challenger has passed walk-forward governance and beats the champion on a fail-closed battery of
checks (sample size, Sharpe uplift, drawdown not worse, profit factor not worse). Recommend-only.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VariantMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    sharpe: float
    profit_factor: float
    turnover: float
    max_drawdown: float  # positive magnitude
    n_samples: int


class ABTestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    champion_id: str
    challenger_id: str
    winner_id: str
    promote: bool
    rationale: str
    margins: dict[str, float] = Field(default_factory=dict)


class ChampionChallenger:
    """Decides whether a challenger should replace the champion (fail-closed)."""

    def __init__(
        self,
        *,
        min_samples: int = 100,
        min_sharpe_uplift: float = 0.1,
        max_drawdown_ratio: float = 1.10,
        require_pf_improvement: bool = True,
    ) -> None:
        self.min_samples = min_samples
        self.min_sharpe_uplift = min_sharpe_uplift
        self.max_drawdown_ratio = max_drawdown_ratio
        self.require_pf_improvement = require_pf_improvement

    def compare(
        self,
        champion: VariantMetrics,
        challenger: VariantMetrics,
        *,
        challenger_walk_forward_passed: bool,
    ) -> ABTestResult:
        sharpe_uplift = challenger.sharpe - champion.sharpe
        dd_ok = challenger.max_drawdown <= champion.max_drawdown * self.max_drawdown_ratio
        pf_ok = (
            not self.require_pf_improvement
            or challenger.profit_factor >= champion.profit_factor
        )
        checks = {
            "walk_forward_passed": challenger_walk_forward_passed,
            "enough_samples": challenger.n_samples >= self.min_samples,
            "sharpe_uplift": sharpe_uplift >= self.min_sharpe_uplift,
            "drawdown_not_worse": dd_ok,
            "profit_factor_not_worse": pf_ok,
        }
        promote = all(checks.values())  # fail-closed: every gate must pass
        failed = [name for name, ok in checks.items() if not ok]
        return ABTestResult(
            champion_id=champion.variant_id,
            challenger_id=challenger.variant_id,
            winner_id=challenger.variant_id if promote else champion.variant_id,
            promote=promote,
            rationale="promote challenger" if promote else f"keep champion; failed: {failed}",
            margins={
                "sharpe_uplift": sharpe_uplift,
                "drawdown_ratio": (
                    challenger.max_drawdown / champion.max_drawdown
                    if champion.max_drawdown > 0
                    else 0.0
                ),
                "pf_delta": challenger.profit_factor - champion.profit_factor,
            },
        )
