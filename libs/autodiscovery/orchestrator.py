"""AutoDiscoveryLab — one autonomous research cycle, idempotent / resumable / fail-closed.

A cycle: expand the fixed generator set into declared hypotheses, skip any already tested (dedup),
backtest each on data from an injected provider, run the full validation gauntlet, resolve the
lifecycle status (reject/shadow/paper/registry), archive every outcome to durable memory,
checkpoint, and audit. No real capital is ever allocated. The data provider is injected so the lab
is testable offline; in production it pulls from MT5.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from libs.autodiscovery.generators import net_returns, planned_hypotheses
from libs.autodiscovery.lifecycle import promote
from libs.autodiscovery.memory import CandidateStore
from libs.autodiscovery.models import (
    CandidateStatus,
    CycleResult,
    Family,
    Hypothesis,
    MarketSeries,
)
from libs.autodiscovery.prioritization import prioritize
from libs.autodiscovery.regime import regime_robust
from libs.autodiscovery.validation import campaign_pbo_rc, validate
from libs.core.ids import generate_id
from libs.costs.execution_gap import ExecutionGap, survives_execution_gap
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.validation.dsr import sharpe_ratio

DataProvider = Callable[[str], MarketSeries | None]
CostProvider = Callable[[str], float]  # symbol -> per-turnover (per-side) cost fraction
_MIN_BARS = 250


class AutoDiscoveryLab:
    """Runs autonomous research cycles over the fixed, economically-declared hypothesis universe."""

    def __init__(
        self,
        db: Database,
        data_provider: DataProvider,
        *,
        cost: float = 0.0003,
        cost_provider: CostProvider | None = None,
        families: Sequence[Family] | None = None,
        execution_gap: ExecutionGap | None = None,
        family_trial_budget: int = 120,
    ) -> None:
        self.db = db
        self.data_provider = data_provider
        self.store = CandidateStore(db)
        self.audit = AuditLog(db)
        self.cost = cost
        self.families = families  # None = all 12; a focused set drops crowded families (T0)
        # Per-symbol net-of-cost (committee T1/T2): real calibrated cost per turnover when supplied,
        # else the flat fallback. Backtests are ALWAYS net of cost; this makes it instrument-aware.
        self.cost_provider = cost_provider
        # Demo->live execution-gap stress (committee Lever 2/T4): a REGISTRY-eligible candidate must
        # also stay net-positive when cost is multiplied to a conservative live estimate.
        self.execution_gap = execution_gap or ExecutionGap()
        # pre-registered per-family search size -> the FIXED wall (see _family_trials)
        self.family_trial_budget = int(family_trial_budget)

    def _cost_for(self, symbol: str) -> float:
        return self.cost_provider(symbol) if self.cost_provider is not None else self.cost

    def _effective_trials(self, n_new: int) -> int:
        """Cumulative trial count for cross-campaign DSR deflation: this cycle + all prior."""
        return n_new + self.store.total()

    def _family_trials(self, family: str, n_new_in_family: int, prior: dict) -> int:
        """FIXED-WALL DEFLATION (principal 2026-07-23). The DSR bar must be a WALL, not a ratchet
        that rises every time the desk tests anything -- otherwise objective #2 (maximize
        discovery) mechanically sabotages objective #1 by making every new test harder to pass.

        Two changes make a fixed bar STATISTICALLY LEGITIMATE rather than phantom-edge bait:

        (1) PARTITIONED -- a family is deflated by ITS OWN trials, never the global pool. Testing
            cross-asset can no longer harshen the funding-mechanism bar. This is standard
            per-family error budgeting: the families are pre-registered and economically
            distinct, so their error budgets are genuinely separate.

        (2) PRE-REGISTERED BUDGET -- within a family the deflation uses the DECLARED search size
            (a CONSTANT), so re-running the same space does not move the bar. That is correct on
            the merits: content-hash dedup means a re-run is not new information, and paying a
            deflation penalty for re-running identical hypotheses is double-counting.

        The correction is NOT removed -- it prices the search you PRE-REGISTERED instead of an
        ever-growing global tally. If a family genuinely EXCEEDS its declared budget the bar does
        rise (max() below), because that is real additional searching and hiding it would be
        exactly the meta-overfitting the cumulative counter existed to catch."""
        return max(self.family_trial_budget, n_new_in_family + int(prior.get(str(family), 0)))

    def cycle(self, symbols: Sequence[str]) -> CycleResult:
        campaign_id = generate_id("camp")
        # highest-priority families first; optionally restricted to a focused set (T0)
        plan = prioritize(planned_hypotheses(symbols, families=self.families))

        # 1) Backtest every NEW (non-duplicate) hypothesis for which data is available.
        prepared: list[tuple[Hypothesis, np.ndarray, np.ndarray]] = []
        skipped = 0
        series_cache: dict[str, MarketSeries | None] = {}
        for hyp, spec in plan:
            if self.store.exists(hyp):
                skipped += 1
                continue
            if hyp.symbol not in series_cache:
                series_cache[hyp.symbol] = self.data_provider(hyp.symbol)
            series = series_cache[hyp.symbol]
            if series is None or len(series) < _MIN_BARS:
                continue
            try:
                base_cost = self._cost_for(hyp.symbol)
                positions = spec.fn(series, dict(hyp.params))
                rets = net_returns(series, positions, cost=base_cost)
                stressed = net_returns(series, positions, cost=self.execution_gap.stress(base_cost))
            except Exception:
                continue
            if len(rets) >= _MIN_BARS:
                prepared.append((hyp, rets, stressed))

        result = self._validate_and_archive(campaign_id, prepared, skipped)
        self.store.set_checkpoint("last_campaign", campaign_id)
        self.audit.append(
            "autodiscovery_cycle", actor="autodiscovery_lab",
            inputs={"campaign_id": campaign_id, "generated": result.generated,
                    "tested": result.tested, "survivors": result.survivors,
                    "skipped_duplicate": result.skipped_duplicate},
            outcome=f"{result.survivors} survivors / {result.tested} tested",
        )
        return result

    def _validate_and_archive(
        self,
        campaign_id: str,
        prepared: list[tuple[Hypothesis, np.ndarray, np.ndarray]],
        skipped: int,
    ) -> CycleResult:
        if not prepared:
            return CycleResult(campaign_id=campaign_id, generated=0, tested=0,
                               skipped_duplicate=skipped)
        # Cross-campaign multiple-testing control (committee T3): deflate the DSR by the CUMULATIVE
        # number of trials ever run, not just this campaign's -- otherwise re-running the lab until
        # something passes is undetected meta-overfitting that funds a false survivor.
        n_trials = self._effective_trials(len(prepared))
        # FIXED WALL: group this cycle by family so each hypothesis is judged against its OWN
        # pre-registered budget and its OWN family's Sharpe distribution (internally consistent
        # DSR), never against the global pool of everything the desk has ever tested.
        _fam_new: dict[str, int] = {}
        for _h, _r, _s in prepared:
            _fam_new[str(_h.family)] = _fam_new.get(str(_h.family), 0) + 1
        _fam_prior = self.store.family_counts()
        _fam_trials = {f: self._family_trials(f, n, _fam_prior) for f, n in _fam_new.items()}
        _fam_sharpes = {
            f: np.array([sharpe_ratio(r) for h, r, _ in prepared if str(h.family) == f],
                        dtype="float64")
            for f in _fam_new
        }
        min_len = min(len(r) for _, r, _ in prepared)
        matrix = np.column_stack([r[-min_len:] for _, r, _ in prepared])  # T x N (selection-aware)
        sharpe_estimates = np.array([sharpe_ratio(r) for _, r, _ in prepared], dtype="float64")
        # PBO + Reality Check depend only on the matrix -> compute once, not per candidate (Nx).
        pbo_once, rc_once = campaign_pbo_rc(matrix)

        counts = dict.fromkeys(CandidateStatus, 0)
        for hyp, rets, stressed in prepared:
            _f = str(hyp.family)
            verdict = validate(
                rets, hypothesis=hyp,
                n_trials=_fam_trials.get(_f, n_trials),
                sharpe_estimates=_fam_sharpes.get(_f, sharpe_estimates),
                returns_matrix=matrix, pbo=pbo_once, rc=rc_once,
            )
            status = promote(rets, validation_survived=verdict.survived)
            reason = verdict.rejection_reason
            # Execution-gap gate (Lever 2/T4): REGISTRY requires surviving live-cost stress too.
            if status is CandidateStatus.REGISTRY and not survives_execution_gap(
                float(np.sum(rets)), float(np.sum(stressed))
            ):
                status = CandidateStatus.PAPER
                reason = "failed: execution_gap (edge eroded under live-cost stress)"
            # Regime-robustness gate (Lever 3/T8): REGISTRY requires edge in >=2 vol regimes.
            elif status is CandidateStatus.REGISTRY and not regime_robust(rets):
                status = CandidateStatus.PAPER
                reason = "failed: regime_robustness (edge confined to one volatility regime)"
            counts[status] += 1
            self.store.record(
                campaign_id=campaign_id, hyp=hyp, status=status, metrics=verdict.metrics,
                survived=status is CandidateStatus.REGISTRY,
                rejection_reason=reason,
            )

        reached_shadow = counts[CandidateStatus.SHADOW] + counts[CandidateStatus.PAPER] + \
            counts[CandidateStatus.REGISTRY]
        reached_paper = counts[CandidateStatus.PAPER] + counts[CandidateStatus.REGISTRY]
        return CycleResult(
            campaign_id=campaign_id, generated=n_trials, tested=n_trials,
            skipped_duplicate=skipped, survivors=counts[CandidateStatus.REGISTRY],
            rejected=counts[CandidateStatus.REJECTED], promoted_to_shadow=reached_shadow,
            promoted_to_paper=reached_paper, promoted_to_registry=counts[CandidateStatus.REGISTRY],
        )
