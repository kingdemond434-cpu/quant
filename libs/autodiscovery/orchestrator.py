"""AutoDiscoveryLab — one autonomous research cycle, idempotent / resumable / fail-closed.

A cycle: expand the fixed generator set into declared hypotheses, skip any already tested (dedup),
backtest each on data from an injected provider, run the full validation gauntlet, resolve the
lifecycle status (reject/shadow/paper/registry), archive every outcome to durable memory,
checkpoint, and audit. No real capital is ever allocated. The data provider is injected so the lab
is testable offline; in production it pulls from MT5.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.capacity_screen import (
    bank_append,
    banked_hashes,
    build_bank_record,
    screen_reason,
)
from libs.autodiscovery.generators import planned_hypotheses, returns_for
from libs.autodiscovery.lifecycle import promote
from libs.autodiscovery.memory import (
    CandidateSeries,
    CandidateStore,
    bar_epoch,
    content_hash,
)
from libs.autodiscovery.models import (
    CandidateStatus,
    CycleResult,
    Family,
    Hypothesis,
    MarketSeries,
    ValidationMetrics,
    ValidationVerdict,
)
from libs.autodiscovery.novelty import NoveltyGate
from libs.autodiscovery.prioritization import prioritize
from libs.autodiscovery.regime import regime_robust
from libs.autodiscovery.validation import (
    CRYPTO_DAYS_PER_YEAR,
    bars_per_year,
    campaign_fdr,
    stratified_campaign_gates,
    validate,
)
from libs.core.ids import generate_id
from libs.costs.execution_gap import ExecutionGap, survives_execution_gap
from libs.data.timeframe import Timeframe
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
        # THE BAR INTERVAL THE PROVIDER SERVES, and it is REQUIRED (R0086, 2026-08-05). The lab is
        # the seam where the frequency is actually known -- whoever built the provider read the
        # bars -- and it was the one seam that never said so, which is why every candidate this
        # lab has ever stored carries an annual_sharpe annualised with an HOURLY constant
        # (4.135x too large on the D1 crypto default). It feeds two things that must agree:
        # validate()'s annualisation, and the timeframe recorded beside each stored return series.
        bar: Timeframe,
        # The trading calendar the interval sits on: 365 for crypto perps (24/7), ~252 for MT5
        # FX/CFD sessions. Separate from `bar` because they are independent facts -- bar LENGTH and
        # how many days a year the market is open -- not two sources for one number.
        days_per_year: float = CRYPTO_DAYS_PER_YEAR,
        cost: float = 0.0003,
        cost_provider: CostProvider | None = None,
        families: Sequence[Family] | None = None,
        execution_gap: ExecutionGap | None = None,
        family_trial_budget: int = 120,
        capacity_bank: Path | None = None,
        novelty: NoveltyGate | None = None,
    ) -> None:
        self.db = db
        self.data_provider = data_provider
        self.bar = bar
        # Derived ONCE, here, so the number validate() annualises with and the interval stored
        # beside the series cannot drift apart.
        self.periods_per_year = bars_per_year(bar, days_per_year=days_per_year)
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
        # Retirement bank for the pre-scoring capacity screen (None = the repo default,
        # data/capacity_retired_bank.jsonl). Injectable so tests never touch the real bank.
        self.capacity_bank = capacity_bank
        self.novelty = novelty

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

    def _record_scored(self, *, campaign_id: str, hyp: Hypothesis, status: CandidateStatus,
                       metrics: ValidationMetrics, survived: bool, reason: str | None,
                       book_usd: float, n_sleeves: int,
                       series: CandidateSeries) -> str | None:
        """Persist a scored candidate -- unless the capacity screen banks it first.

        THE FACTORY BOUNDARY (§42, 2026-08-05). Returns None when the candidate was stored, else
        the retirement reason it was banked under. A candidate with a MEASURED positive capacity
        the live book cannot fill is appended to the retirement bank (full mechanism, band,
        runway, named resurrection condition -- L1.17) and never persisted as a scored candidate,
        so the store's ranked population cannot re-accumulate unfillable inventory. Unknown
        capacity (0.0) is NOT screened: unmeasured is not unfillable (R0080).

        THE EVIDENCE RIDES WITH THE VERDICT (m0007). ``series`` carries the candidate's net and
        stressed return series into the SAME transaction as the scalar row, for every outcome --
        survivors and REJECTS alike. The rejects matter most: they are the weak-edge pool any
        ensemble path has to draw on, and a weak edge is only judgeable in combination, which
        needs its series and cannot be reconstructed from a Sharpe. The one exit that still
        persists nothing is the capacity bank below, because it writes no candidate row at all --
        a returns row with no candidate to hang off is not evidence, it is an orphan.

        ``series`` is REQUIRED, not optional, so no future caller can quietly reintroduce the
        scalar-only write this whole change exists to end.
        """
        scr = screen_reason(metrics.capacity_usd, hyp.subtype,
                            book_usd=book_usd, n_sleeves=n_sleeves)
        if scr is not None:
            bank_append(build_bank_record(
                candidate_id=generate_id("cand"), family=hyp.family.value, subtype=hyp.subtype,
                symbol=hyp.symbol, params=dict(hyp.params),
                content_hash=content_hash(hyp, self.bar),
                mechanism=hyp.mechanism.value, hypothesis_text=hyp.edge_source,
                failure_modes=list(hyp.failure_modes), capacity_usd=metrics.capacity_usd,
                book_usd=book_usd, n_sleeves=n_sleeves, metrics=metrics.model_dump(),
                campaign_id=campaign_id, status_at_retirement="never-stored (screened at scoring)",
                survived=survived, rejection_reason=reason, reason=scr,
            ), bank=self.capacity_bank)
            return scr
        self.store.record(campaign_id=campaign_id, hyp=hyp, status=status, metrics=metrics,
                          survived=survived, rejection_reason=reason, series=series,
                          bar=self.bar)
        return None

    def cycle(self, symbols: Sequence[str]) -> CycleResult:
        campaign_id = generate_id("camp")
        # highest-priority families first; optionally restricted to a focused set (T0)
        plan = prioritize(planned_hypotheses(symbols, families=self.families))

        # 1) Backtest every NEW (non-duplicate) hypothesis for which data is available.
        prepared: list[tuple[Hypothesis, np.ndarray, np.ndarray]] = []
        skipped = 0
        skipped_redundant = 0
        suppressed: list[dict[str, Any]] = []
        series_cache: dict[str, MarketSeries | None] = {}
        # THE BAR GRID EVERY CANDIDATE ON THIS SYMBOL WAS SCORED ON (m0007). One MarketSeries per
        # symbol serves the whole cycle, so one epoch key per symbol identifies the grid its
        # return series live on -- and stored series may only be aligned against each other when
        # those keys match. Computed here, where the array is known to be the one that was used.
        epochs: dict[str, str] = {}
        # BANKED IS TESTED (§42 capacity screen). A candidate the screen banked was never stored,
        # so `exists` cannot dedup it -- without this rung the factory would re-backtest and
        # re-bank the same unfillable hypothesis every cycle, forever. Resurrection from the bank
        # is a named, deliberate act (L1.16a), never a re-generation.
        _banked = banked_hashes(self.capacity_bank)
        for hyp, spec in plan:
            # DEDUP IS PER-BAR (R0241a). Without `self.bar` here the D1 store answers for every
            # timeframe: `planned_hypotheses` takes no timeframe, so the H8 plan is the SAME
            # tuples as the D1 plan and hashed the same, and every H8 candidate this desk has
            # ever generated was counted as skipped_duplicate before it could be tested.
            if self.store.exists(hyp, self.bar) or content_hash(hyp, self.bar) in _banked:
                skipped += 1
                continue
            if self.novelty is not None:
                novelty = self.novelty.screen(hyp)
                if novelty.is_redundant:
                    skipped_redundant += 1
                    suppressed.append({
                        "family": hyp.family.value, "subtype": hyp.subtype,
                        "symbol": hyp.symbol, "nearest_id": novelty.nearest_id,
                        "similarity": novelty.nearest_similarity,
                        "lesson": novelty.nearest_lesson,
                    })
                    continue
            if hyp.symbol not in series_cache:
                series_cache[hyp.symbol] = self.data_provider(hyp.symbol)
            series = series_cache[hyp.symbol]
            if series is None or len(series) < _MIN_BARS:
                continue
            if hyp.symbol not in epochs:
                epochs[hyp.symbol] = bar_epoch(hyp.symbol, series.close)
            try:
                base_cost = self._cost_for(hyp.symbol)
                positions = spec.fn(series, dict(hyp.params))
                # `returns_for`, never `net_returns` directly. A delta-neutral carry has no spot
                # exposure, so the price path does not error on it -- it quietly reports a
                # direction bet under a carry label. Price specs are unaffected: returns_for hands
                # them the same `net_returns` they have always been scored with.
                score = returns_for(spec)
                rets = score(series, positions, cost=base_cost)
                stressed = score(series, positions, cost=self.execution_gap.stress(base_cost))
            except Exception:
                continue
            if len(rets) >= _MIN_BARS:
                prepared.append((hyp, rets, stressed))

        if suppressed:
            self.audit.append(
                "novelty_gate_suppressed", actor="autodiscovery_lab",
                inputs={"campaign_id": campaign_id, "n": skipped_redundant, "items": suppressed},
                outcome=f"{skipped_redundant} redundant hypothesis(es) skipped before data fetch",
            )
        result = self._validate_and_archive(
            campaign_id, prepared, skipped, epochs, skipped_redundant)

        self.store.set_checkpoint("last_campaign", campaign_id)
        self.audit.append(
            "autodiscovery_cycle", actor="autodiscovery_lab",
            inputs={"campaign_id": campaign_id, "generated": result.generated,
                    "tested": result.tested, "survivors": result.survivors,
                    "skipped_duplicate": result.skipped_duplicate,
                    "skipped_redundant": result.skipped_redundant},
            outcome=f"{result.survivors} survivors / {result.tested} tested",
        )
        return result

    def _validate_and_archive(
        self,
        campaign_id: str,
        prepared: list[tuple[Hypothesis, np.ndarray, np.ndarray]],
        skipped: int,
        epochs: dict[str, str],
        skipped_redundant: int = 0,
    ) -> CycleResult:
        if not prepared:
            return CycleResult(campaign_id=campaign_id, generated=0, tested=0,
                               skipped_duplicate=skipped, skipped_redundant=skipped_redundant)
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
                    "expected_discoveries": strata_plan.expected_discoveries,
                    # R0263: the campaign's own wall-clock, so "does stratification bind the
                    # cycle?" is answered from the record instead of re-argued from a fixture
                    # measured once in a docstring. parallel_speedup is the ceiling a per-stratum
                    # pool could reach -- the remedy the row names, and the one that costs no
                    # statistical resolution, unlike cutting n_boot.
                    "seconds": strata_plan.seconds,
                    "stratum_seconds": list(strata_plan.stratum_seconds),
                    "parallel_speedup": strata_plan.parallel_speedup},
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
                periods_per_year=self.periods_per_year,
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
        # ONE book, ONE sleeve count for the whole campaign's capacity screen -- read once, like
        # check_capacity_hunt does, so every candidate in a cycle is banded against the same desk.
        from libs.research.capacity_policy import live_book_usd, live_sleeves
        _book, _sleeves = live_book_usd(), live_sleeves()
        n_banked = 0
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
            # PRE-SCORING CAPACITY SCREEN (§42, 2026-08-05): the ONLY exit that does not persist.
            # An UNFILLABLE candidate is banked with its full mechanism instead of stored --
            # "screened out before scoring, not carried as candidates".
            # EVERY candidate's series is persisted here -- rejected, shadow, paper, registry
            # alike -- in the same transaction as its scalar row. `epochs[hyp.symbol]` cannot
            # KeyError: a hypothesis only reaches `prepared` after its symbol's series was
            # fetched, and the epoch is recorded on that same pass.
            if self._record_scored(
                campaign_id=campaign_id, hyp=hyp, status=status, metrics=verdict.metrics,
                survived=status is CandidateStatus.REGISTRY, reason=reason,
                book_usd=_book, n_sleeves=_sleeves,
                # THE BAR INTERVAL RIDES WITH THE EVIDENCE (R0086). This wrote NULL until
                # 2026-08-05 -- honestly, because nothing told the lab its own frequency -- and
                # that NULL is now what separates the two populations of stored candidates: a row
                # with a declared timeframe had its annual_sharpe annualised on THIS clock, a row
                # without one was annualised with the deleted hourly constant and is inflated
                # (4.135x on D1). Nothing rewrites the old rows; they are made recognisable.
                series=CandidateSeries(net=rets, stressed=stressed,
                                       epoch_key=epochs[hyp.symbol],
                                       timeframe=self.bar.value),
            ) is not None:
                n_banked += 1
                continue
            counts[status] += 1

        if n_banked:
            self.audit.append(
                "capacity_screen", actor="autodiscovery_lab",
                inputs={"campaign_id": campaign_id, "banked": n_banked,
                        "book_usd": _book, "n_sleeves": _sleeves},
                outcome=(f"{n_banked} candidate(s) unfillable on a ${_book:,.0f} book -> "
                         "retirement bank, never persisted as scored"),
            )

        reached_shadow = counts[CandidateStatus.SHADOW] + counts[CandidateStatus.PAPER] + \
            counts[CandidateStatus.REGISTRY]
        reached_paper = counts[CandidateStatus.PAPER] + counts[CandidateStatus.REGISTRY]
        return CycleResult(
            campaign_id=campaign_id, generated=n_trials, tested=n_trials,
            skipped_duplicate=skipped, skipped_redundant=skipped_redundant,
            survivors=counts[CandidateStatus.REGISTRY],
            rejected=counts[CandidateStatus.REJECTED], promoted_to_shadow=reached_shadow,
            promoted_to_paper=reached_paper, promoted_to_registry=counts[CandidateStatus.REGISTRY],
        )
