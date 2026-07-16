"""The validation gauntlet — the Skeptic.

Runs the ordered, trials-adjusted gauntlet; a candidate dies at the first stage it fails. The
trials ledger feeds the true (inflated) trial count into the Deflated Sharpe Ratio, so search
throughput cannot manufacture significance. Output is a structured PASS/FAIL verdict.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.costs.scenarios import CostScenario
from libs.store.trials import TrialsLedger
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.economic_prior import economic_prior_gate
from libs.validation.pbo import probability_backtest_overfitting
from libs.validation.reality_check import hansen_spa
from libs.validation.stress_costs import stress_cost_validation


@dataclass
class CandidateEvaluation:
    """All inputs the gauntlet needs to judge one candidate alpha."""

    candidate_id: str
    hypothesis_id: str
    family: str
    returns: np.ndarray  # candidate per-period (net) returns
    strategy_matrix: np.ndarray  # (T x N) returns of all trials, for DSR variance / PBO / SPA
    gross_pnls: Sequence[float]  # per-trade gross PnL
    base_costs: Sequence[float]  # per-trade base cost
    economic_prior: Mapping[str, Any]
    lockbox_returns: np.ndarray | None = None
    n_trials_override: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class StageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    message: str
    detail: dict[str, Any] = {}


class GauntletResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    hypothesis_id: str
    passed: bool
    verdict: str
    n_trials: int
    stages: list[StageResult]

    def __bool__(self) -> bool:
        return self.passed


class Gauntlet:
    """Orchestrates the validation stages with trials-ledger integration."""

    def __init__(
        self,
        *,
        ledger: TrialsLedger | None = None,
        trials_multiplier: float = 7.0,
        dsr_threshold: float = 0.95,
        pbo_threshold: float = 0.5,
        spa_alpha: float = 0.05,
        required_cost_scenario: CostScenario = CostScenario.X3,
        lockbox_min_sharpe: float = 0.0,
    ) -> None:
        self.ledger = ledger
        self.trials_multiplier = trials_multiplier
        self.dsr_threshold = dsr_threshold
        self.pbo_threshold = pbo_threshold
        self.spa_alpha = spa_alpha
        self.required_cost_scenario = required_cost_scenario
        self.lockbox_min_sharpe = lockbox_min_sharpe

    def _resolve_n_trials(self, candidate: CandidateEvaluation, observed_sr: float) -> int:
        if candidate.n_trials_override is not None:
            return max(2, candidate.n_trials_override)
        if self.ledger is not None:
            self.ledger.append(
                candidate.hypothesis_id,
                candidate.family,
                method="gauntlet",
                params={"candidate_id": candidate.candidate_id},
                in_sample_metric=observed_sr,
            )
            true_count = self.ledger.count()
            return max(2, math.ceil(true_count * self.trials_multiplier))
        return 2

    def run(self, candidate: CandidateEvaluation) -> GauntletResult:
        stages: list[StageResult] = []
        observed_sr = sharpe_ratio(candidate.returns)
        n_trials = self._resolve_n_trials(candidate, observed_sr)

        def finalize() -> GauntletResult:
            passed = all(s.passed for s in stages)
            return GauntletResult(
                candidate_id=candidate.candidate_id,
                hypothesis_id=candidate.hypothesis_id,
                passed=passed,
                verdict="PASS" if passed else "FAIL",
                n_trials=n_trials,
                stages=stages,
            )

        # 1) Economic-prior gate (cheapest, runs first)
        prior = economic_prior_gate(candidate.economic_prior)
        stages.append(
            StageResult(
                name="economic_prior", passed=prior.passed, message=prior.message,
                detail={"missing": prior.missing},
            )
        )
        if not prior.passed:
            return finalize()

        # 2) In-sample existence (cost-adjusted screen)
        screen_ok = observed_sr > 0.0
        stages.append(
            StageResult(
                name="in_sample_screen", passed=screen_ok,
                message="net edge exists" if screen_ok else "no in-sample edge",
                detail={"sharpe": observed_sr},
            )
        )
        if not screen_ok:
            return finalize()

        # 3) Deflated Sharpe Ratio (multiple-testing)
        sharpes = np.array(
            [sharpe_ratio(candidate.strategy_matrix[:, k])
             for k in range(candidate.strategy_matrix.shape[1])]
        )
        dsr = deflated_sharpe_ratio(
            candidate.returns, n_trials=n_trials,
            variance_of_sharpes=float(sharpes.var(ddof=1)) if len(sharpes) >= 2 else 1e-6,
            threshold=self.dsr_threshold,
        )
        stages.append(
            StageResult(
                name="deflated_sharpe", passed=dsr.passed,
                message=f"DSR={dsr.dsr:.3f} vs threshold {self.dsr_threshold}",
                detail={"dsr": dsr.dsr, "sr0": dsr.sr0_threshold, "n_trials": n_trials},
            )
        )
        if not dsr.passed:
            return finalize()

        # 4) Probability of Backtest Overfitting
        pbo = probability_backtest_overfitting(candidate.strategy_matrix)
        pbo_ok = pbo.pbo <= self.pbo_threshold
        stages.append(
            StageResult(
                name="pbo", passed=pbo_ok, message=f"PBO={pbo.pbo:.3f}",
                detail={"pbo": pbo.pbo, "n_combinations": pbo.n_combinations},
            )
        )
        if not pbo_ok:
            return finalize()

        # 5) Hansen SPA (selection bias)
        spa = hansen_spa(candidate.strategy_matrix)
        spa_ok = spa.p_value < self.spa_alpha
        stages.append(
            StageResult(
                name="reality_check_spa", passed=spa_ok,
                message=f"SPA p-value={spa.p_value:.3f}",
                detail={"p_value": spa.p_value, "statistic": spa.statistic},
            )
        )
        if not spa_ok:
            return finalize()

        # 6) Stress-cost validation
        stress = stress_cost_validation(
            candidate.gross_pnls, candidate.base_costs,
            required_scenario=self.required_cost_scenario,
        )
        stages.append(
            StageResult(
                name="stress_costs", passed=stress.passed, message=stress.message,
                detail={"required": stress.required_scenario},
            )
        )
        if not stress.passed:
            return finalize()

        # 7) Lockbox confirmation (if a holdout was provided)
        if candidate.lockbox_returns is not None:
            lockbox_sr = sharpe_ratio(candidate.lockbox_returns)
            lockbox_ok = lockbox_sr >= self.lockbox_min_sharpe
            stages.append(
                StageResult(
                    name="lockbox", passed=lockbox_ok,
                    message=f"lockbox Sharpe={lockbox_sr:.3f}",
                    detail={"lockbox_sharpe": lockbox_sr},
                )
            )

        return finalize()
