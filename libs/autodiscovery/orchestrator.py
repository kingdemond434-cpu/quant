"""AutoDiscoveryLab — one autonomous research cycle, idempotent / resumable / fail-closed.

A cycle: expand the fixed generator set into declared hypotheses, skip any already tested (dedup),
backtest each on data from an injected provider, run the full validation gauntlet, resolve the
lifecycle status (reject/shadow/paper/registry), archive every outcome to durable memory,
checkpoint, and audit. No real capital is ever allocated. The data provider is injected so the lab
is testable offline; in production it pulls from MT5.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

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
    ValidationMetrics,
    ValidationVerdict,
)
from libs.autodiscovery.prioritization import prioritize
from libs.autodiscovery.regime import regime_robust
from libs.autodiscovery.validation import (
    campaign_fdr,
    stratified_campaign_gates,
    validate,
)
from libs.core.ids import generate_id
from libs.costs.execution_gap import ExecutionGap, survives_execution_gap
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.validation.campaign_window import CAMPAIGN_ALPHA
from libs.validation.dsr import sharpe_ratio
from libs.validation.lockbox import LockedHoldout

DataProvider = Callable[[str], MarketSeries | None]
CostProvider = Callable[[str], float]  # symbol -> per-turnover (per-side) cost fraction
_MIN_BARS = 250
# Sealed final slice, never seen by validation, opened exactly once at the promotion
# decision. 20% rather than the module default 30%: at _MIN_BARS=250 a 30% holdout
# would need 358 bars before any candidate qualified, so the discipline would almost
# never apply. A holdout that never engages is not a holdout either.
_LOCKBOX_FRACTION = 0.20


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

    def _family_trials(self, family: str, n_new_in_family: int, prior: dict[str, Any]) -> int:
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
        # STRATIFIED BY AVAILABLE HISTORY, not truncated to the shortest candidate. The old rule
        # was `matrix = column_stack([r[-min_len:] ...])`, which let ONE short candidate truncate
        # every other: measured on this desk's own 420-candidate campaign, 310 observations kept
        # of 1,808 available -- 82.9% of the data on disk discarded before a test ran. The gate
        # audit (docs/research/gate_power_audit.md s5) measured history length as THE binding
        # constraint (T=310->2500 moves power at true Sharpe 2.0 from 0.00% to 19.58%) while
        # cohort size buys nothing (N=420->30 stays at 0.00%). Each stratum is its own family at
        # CAMPAIGN_ALPHA/k, so family-wise error stays at 5% -- this raises POWER, it lowers no
        # bar. The partition sees lengths only, never a return or a p-value.
        gates_by_candidate, strata_plan = stratified_campaign_gates(
            [r for _, r, _ in prepared])
        # NO SILENT CAPS. Stratification tests every candidate its own history supports and leaves
        # the rest UNTESTED -- on the desk's real 420-candidate campaign that is 308 tested and
        # 112 not. Untested-and-said-so beats tested-at-0.25%-power, but only if it is said: an
        # unreported exclusion reads downstream as "the campaign covered everything".
        self.audit.append(
            "campaign_strata", actor="autodiscovery_lab",
            inputs={"campaign_id": campaign_id, "n_candidates": strata_plan.n_candidates,
                    "n_tested": strata_plan.n_tested,
                    "n_untested": strata_plan.n_candidates - strata_plan.n_tested,
                    "obs_retained": strata_plan.obs_retained,
                    "obs_available": strata_plan.obs_available,
                    "strata_alpha": CAMPAIGN_ALPHA / max(1, len(strata_plan.strata)),
                    "expected_discoveries": strata_plan.expected_discoveries},
            outcome=strata_plan.why,
        )
        min_len = min(len(r) for _, r, _ in prepared)
        matrix = np.column_stack([r[-min_len:] for _, r, _ in prepared])  # legacy diagnostics only
        sharpe_estimates = np.array([sharpe_ratio(r) for _, r, _ in prepared], dtype="float64")
        # PER-CANDIDATE multiplicity statistics, computed in ONE pass over the matrix (not Nx).
        # The predecessor hoisted campaign_pbo_rc() out of the loop for the same speed reason, but
        # PBO and White's Reality Check take ONLY the matrix -- the candidate's own returns are
        # never an input -- so as per-candidate gates they were campaign CONSTANTS. Measured on
        # this exact 420-candidate campaign: PBO 0.6159 (>0.5) and White RC p 0.4220 (>=0.05),
        # which alone forced 420/420 rejections regardless of any candidate's merit. CSCV
        # rank-consistency + Romano-Wolf stepdown replace them with a verdict each candidate earns
        # on its OWN column, and Romano-Wolf still controls family-wise error across all N, so
        # multiplicity is paid in full. Thresholds are UNCHANGED (PBO <= 0.5, significance at 5%);
        # only the attribution changed. Calibration proof: tests/validation/test_stepwise.py
        # (all-null campaign must not manufacture survivors; a known winner must be reachable).
        # Column mapping VERIFIED (both branches independently): matrix columns are
        # column_stack'd from `prepared` in order, and the enumerate below walks that same
        # list, so the loop index IS the candidate's column. Wired at all 19 legacy call
        # sites in the 07-29 closure cycle, not just here.
        # ---------------------------------------------------------------- PASS 1: validate
        # Two passes, because the campaign-level FDR screen cannot be applied until every
        # candidate has a p-value. Promotion moved to pass 2. `col` now indexes into the STRATUM
        # this candidate was tested in (gates_by_candidate above), not one global matrix.
        _Box = LockedHoldout[np.ndarray]
        evaluated: list[tuple[Hypothesis, np.ndarray, np.ndarray, Any, _Box | None]] = []
        for col, (hyp, rets, stressed) in enumerate(prepared):
            _f = str(hyp.family)
            # The FIXED WALL is the family-scoped TRIAL COUNT. The sharpe array is only the
            # dispersion input for the DSR variance term: a family contributing a single
            # hypothesis this cycle cannot estimate a variance from one point, so fall back to
            # the campaign-wide dispersion. That keeps the wall fixed without ever handing
            # deflated_sharpe_ratio a degenerate (len<2) sample.
            _sh = _fam_sharpes.get(_f)
            if _sh is None or len(_sh) < 2:
                _sh = sharpe_estimates
            # LOCKBOX (spec: a final slice openable exactly once). Validation runs on the
            # RESEARCH portion only; the holdout is opened once in pass 2 at the promotion
            # decision. Applied only when the research portion still clears _MIN_BARS on its
            # own, so a candidate is never failed for being short rather than for being bad.
            box: LockedHoldout[np.ndarray] | None = None
            research = rets
            if len(rets) >= int(_MIN_BARS / (1.0 - _LOCKBOX_FRACTION)) + 1:
                box = LockedHoldout(rets, holdout_fraction=_LOCKBOX_FRACTION)
                research = box.research()
            # UNTESTED IS NOT REJECTED. A candidate whose history no stratum supports gets an
            # explicit not-tested verdict. Passing campaign=None would be fail-CLOSED (it falls
            # to the legacy campaign-constant path, which measured PBO 0.6159 / RC p 0.4220 and
            # rejects everyone) -- safe, but it would file a DATA-AVAILABILITY exclusion in the
            # graveyard under a statistical mechanism of death, corrupting the family survival
            # statistics that steer future search. Say what actually happened instead.
            _stratum = gates_by_candidate[col]
            if _stratum is None:
                evaluated.append((hyp, rets, stressed, ValidationVerdict(
                    survived=False, gates={"campaign_stratum": False},
                    rejection_reason=("not tested: no stratum supports this candidate's "
                                      f"history ({len(rets)} obs)"),
                    metrics=ValidationMetrics(),
                ), box))
                continue
            _gates, _col = _stratum
            verdict = validate(
                research, hypothesis=hyp,
                n_trials=_fam_trials.get(_f, n_trials),
                sharpe_estimates=_sh,
                returns_matrix=matrix, campaign=_gates, column=_col,
            )
            evaluated.append((hyp, rets, stressed, verdict, box))

        # ------------------------------------------------- CAMPAIGN FDR (Benjamini-Hochberg)
        # Every candidate here already cleared a 0.95 per-candidate DSR bar. Run twenty past
        # that bar and you expect one false survivor by construction: the per-candidate control
        # says nothing about the error rate of the SET being promoted. This does.
        # UNTESTED CANDIDATES ARE NOT IN THE FDR FAMILY. Benjamini-Hochberg's m must be the number
        # of hypotheses actually TESTED: a candidate no stratum could support has no p-value, and
        # its default metrics would enter as dsr=0.0 -> p=1.0. Leaving those in would inflate m
        # from 308 to 420 on the desk's real campaign, tightening the BH threshold by 308/420 and
        # diluting the screen exactly as its own docstring warns junk does -- suppressing real
        # discoveries with tests that were never run. Fail-CLOSED is not automatically safe here:
        # a bar that rejects everything carries no information (gate-optimality duty).
        _tested_idx = [i for i, e in enumerate(evaluated) if gates_by_candidate[i] is not None]
        _pass_tested, fdr_threshold = campaign_fdr(
            [evaluated[i][3].metrics.dsr for i in _tested_idx])
        fdr_pass = [False] * len(evaluated)
        for _slot, _cand in enumerate(_tested_idx):
            fdr_pass[_cand] = _pass_tested[_slot]

        # ---------------------------------------------------------------- PASS 2: promote
        counts = dict.fromkeys(CandidateStatus, 0)
        for i, (hyp, rets, stressed, verdict, box) in enumerate(evaluated):
            status = promote(rets, validation_survived=verdict.survived)
            reason = verdict.rejection_reason
            # FDR screen: a candidate that survived every gate but does not clear the campaign's
            # BH threshold is demoted, not rejected -- it may be real, and paper will tell us.
            if status is CandidateStatus.REGISTRY and not fdr_pass[i]:
                status = CandidateStatus.PAPER
                reason = (f"failed: campaign_fdr (BH threshold p<={fdr_threshold:.4g} across "
                          f"{len(evaluated)} candidates)")
            # LOCKBOX: opened exactly ONCE, here, and only for a candidate that would otherwise
            # reach the registry. Opening it for candidates already rejected would burn the
            # holdout's independence for no decision.
            elif status is CandidateStatus.REGISTRY and box is not None:
                held = box.open_lockbox()
                if float(np.mean(held)) <= 0.0:
                    status = CandidateStatus.PAPER
                    reason = ("failed: lockbox (edge absent in the sealed final "
                              f"{_LOCKBOX_FRACTION:.0%} never used for validation)")
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
