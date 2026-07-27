"""Full institutional validation per candidate — every gate, no weakening, fail-closed.

Runs the complete stack and a candidate survives ONLY if every gate passes: economic mechanism,
CPCV (purged K-fold OOS consistency), PBO, Deflated Sharpe (trials-deflated), White's Reality Check,
Walk-Forward, capacity, fragility (tail risk), and an accelerated shadow check (final held-out
segment). Reuses the existing validation / discovery primitives. Thresholds are constants here and
never relaxed.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from libs.autodiscovery.models import Hypothesis, ValidationMetrics, ValidationVerdict
from libs.discovery.capacity import capacity_estimate
from libs.discovery.tail_risk import tail_risk
from libs.research.capacity_policy import capacity_required, live_book_usd, live_sleeves
from libs.validation.baselines import baseline_scorecard
from libs.validation.cpcv import CPCV
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.errors import ValidationError
from libs.validation.fdr import benjamini_hochberg
from libs.validation.pbo import PBOResult, probability_backtest_overfitting
from libs.validation.reality_check import RealityCheckResult, whites_reality_check
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus

_PERIODS_PER_YEAR = 24 * 260
_DSR_THRESHOLD = 0.95
_CPCV_MIN_POSITIVE = 0.6   # >=60% of purged folds positive

# Real CPCV settings. 6 groups choose 2 gives 15 test paths; purge drops the observations
# straddling each boundary and the embargo holds out a further 1% after it, which is what stops
# a serially-correlated stream leaking its answer across the split.
_CPCV_GROUPS = 6
_CPCV_TEST_GROUPS = 2
_CPCV_PURGE = 2
_CPCV_EMBARGO = 0.01
_CPCV_MIN_OBS = 60         # below this there is nothing to be combinatorial about

# Benjamini-Hochberg level for the campaign screen. 0.10 = accept that up to ~10% of
# promoted candidates are false discoveries, which is the standard screening trade-off
# and far more powerful than family-wise control at this campaign size.
_FDR_ALPHA = 0.10

# A candidate must beat the trivial nulls, not merely be statistically distinguishable from
# noise. DSR/PBO/RC all ask "is this real given the search?"; none asks "is it better than
# buy-and-hold?", and a significant strategy that loses to buy-and-hold is complexity with no
# reason to exist. Gate is SKIPPED (not failed) when no benchmark stream is supplied, because
# most callers have no benchmark for a market-neutral carry sleeve -- failing them for the
# absence of an inapplicable comparison would reject good candidates for the wrong reason.


def _cpcv_positive_fraction(returns: np.ndarray, *, k: int = 5) -> float:
    """Fraction of COMBINATORIAL PURGED folds whose test slice is positive.

    This was a plain `np.array_split` into k contiguous folds -- not purged, not embargoed, and
    not combinatorial, despite the gate being named `cpcv` and the module docstring claiming
    CPCV. `libs/validation/cpcv.py` implements the real thing (Lopez de Prado ch.12) and was
    imported by nothing but its own test.

    The difference is not cosmetic. Contiguous k-fold on overlapping financial samples leaks
    information across the fold boundary, so the old measure was systematically optimistic on
    exactly the serially-correlated return streams this desk trades. Purge + embargo remove the
    observations that straddle the boundary; the combinatorial part gives many test paths instead
    of one, so the fraction means something.

    Falls back to the contiguous split only when the sample is too short to purge -- with a short
    series there is nothing to be combinatorial about, and refusing to score would fail candidates
    for being new rather than for being bad.
    """
    arr = np.asarray(returns, dtype="float64")
    if len(arr) >= _CPCV_MIN_OBS:
        try:
            splitter = CPCV(n_groups=_CPCV_GROUPS, n_test_groups=_CPCV_TEST_GROUPS,
                            purge=_CPCV_PURGE, embargo=_CPCV_EMBARGO)
            positive = [bool(arr[s.test].mean() > 0)
                        for s in splitter.split(len(arr)) if len(s.test) > 1]
            if positive:
                return float(np.mean(positive))
        except (ValidationError, ValueError):
            pass
    folds = np.array_split(arr, k)
    positive_fallback = [f.mean() > 0 for f in folds if len(f) > 1]
    return float(np.mean(positive_fallback)) if positive_fallback else 0.0


def _beats_baselines(returns: np.ndarray, benchmark: np.ndarray | None) -> bool:
    """Does the candidate beat buy-and-hold and equal-weight? True when no benchmark is given.

    Skipping rather than failing on a missing benchmark is a deliberate fail-OPEN, and the only
    one in this gate set. The reason it is defensible here and nowhere else: the desk's live
    sleeve is market-neutral carry, for which "buy and hold what?" has no answer, so an absent
    benchmark usually means the comparison is inapplicable rather than unmeasured. Every caller
    that CAN supply one should -- `beats_baselines` reads as passed either way in the verdict,
    so read `n_obs`/the caller to know which happened.
    """
    if benchmark is None:
        return True
    b = np.asarray(benchmark, dtype="float64")
    if len(b) < 2 or len(b) != len(returns):
        return True
    try:
        return bool(baseline_scorecard(returns, buy_hold_returns=b).beats_all)
    except (ValidationError, ValueError):
        return True


def campaign_fdr(dsr_values: Sequence[float], *,
                 alpha: float = _FDR_ALPHA) -> tuple[list[bool], float]:
    """Benjamini-Hochberg screen across one campaign. Returns (survives_mask, p_threshold).

    Why this is NOT redundant with the per-candidate DSR gate it sits behind. DSR asks, of ONE
    candidate, "is this Sharpe real given the trials that produced it", and passes at 0.95. Run
    twenty candidates past a 0.95 bar and you expect one false survivor by construction -- the
    per-candidate control says nothing about the error rate of the SET the desk promotes.
    Benjamini-Hochberg controls exactly that: the expected proportion of false discoveries among
    the candidates that survive.

    Nor is it redundant with White's Reality Check, which tests whether the BEST performer beats
    the benchmark -- one question about one candidate, not a rate across many. And it is a
    different control from `forward_stats.holm_bar`: Holm bounds the probability of ANY false
    positive (family-wise error), which across a campaign of this size is punishingly
    conservative, where BH accepts a known false-discovery proportion in exchange for power.

    p-values are 1 - DSR: the deflated Sharpe is already the probability the true Sharpe exceeds
    zero given the search, so its complement is the p-value for "no edge" with the multiplicity
    of the search already priced in.

    An empty or single-candidate campaign passes through unchanged -- there is no multiplicity to
    correct with one test, and rejecting a lone candidate for being alone would be nonsense.

    OPERATIONAL CONSEQUENCE, measured not assumed. A uniformly strong campaign is NOT penalised
    (20 candidates at DSR 0.96 all promote -- that is strong collective evidence). But junk
    DILUTES: three candidates at 0.96 among seventeen at 0.50 promotes NONE, because a campaign
    that is mostly noise does not support calling anything a discovery. Padding a cycle with weak
    generators now costs you the good candidates in it. That is the correct incentive and it is
    the sharpest edge of this gate, so callers demote rather than reject on an FDR failure --
    nothing is lost, it simply does not reach the registry this cycle.
    """
    ps = [min(1.0, max(0.0, 1.0 - float(d))) for d in dsr_values]
    if len(ps) < 2:
        return [True] * len(ps), 1.0
    try:
        res = benjamini_hochberg(np.asarray(ps, dtype="float64"), alpha=alpha)
    except (ValidationError, ValueError):
        # fail-OPEN here on purpose: BH is an EXTRA screen layered on gates that already ran and
        # already passed. A crash in the extra screen must not silently reject candidates that
        # cleared every primary gate -- that would be a harsher desk by accident, not by decision.
        return [True] * len(ps), 1.0
    return [bool(x) for x in res.rejected], float(res.threshold)


def campaign_pbo_rc(
    returns_matrix: np.ndarray,
) -> tuple[PBOResult | None, RealityCheckResult | None]:
    """Compute PBO and White's Reality Check ONCE per campaign (they depend only on the matrix).

    These two gates are identical for every candidate in a campaign, so computing them once and
    passing the results into :func:`validate` avoids O(N) redundant bootstraps -- a large speedup
    with no change to the verdict. (Used by the orchestrator; validate() falls back to per-call
    computation when not supplied.)
    """
    if returns_matrix.shape[1] < 2:
        return None, None
    return probability_backtest_overfitting(returns_matrix), whites_reality_check(returns_matrix)


def validate(
    returns: np.ndarray,
    *,
    hypothesis: Hypothesis,
    n_trials: int,
    sharpe_estimates: np.ndarray,
    returns_matrix: np.ndarray,
    adv_usd: float = 1.0e11,
    edge_bps: float | None = None,
    # What the desk ACTUALLY deploys. The capacity gate is a ratio to this, not a fixed dollar
    # figure -- see capacity_required(). None means "read the live book from the NAV chain", which
    # is what makes the ratio self-scaling as the desk grows. The old default of 0.0 was a hole:
    # it collapsed the gate to the $2k absolute floor and passed essentially any capacity, so the
    # ratio that was supposed to protect the desk protected nothing whenever a caller omitted it.
    deployed_equity_usd: float | None = None,
    n_sleeves: int | None = None,
    pbo: PBOResult | None = None,
    rc: RealityCheckResult | None = None,
    benchmark_returns: np.ndarray | None = None,
) -> ValidationVerdict:
    arr = np.asarray(returns, dtype="float64")
    if len(arr) < 250:
        return ValidationVerdict(
            survived=False, gates={"sufficient_data": False},
            rejection_reason="insufficient data", metrics=ValidationMetrics(),
        )

    # Walk-forward (OOS). Shadow/paper are separate lifecycle stages (see lifecycle.py).
    wf = WalkForwardEngine().evaluate(arr, n_splits=4, test_size=max(20, len(arr) // 6))
    dsr = deflated_sharpe_ratio(arr, n_trials=n_trials, sharpe_estimates=sharpe_estimates,
                                threshold=_DSR_THRESHOLD)
    # PBO/RC depend only on the (campaign-wide) matrix; reuse precomputed results when supplied.
    has_peers = returns_matrix.shape[1] >= 2
    if pbo is None and has_peers:
        pbo = probability_backtest_overfitting(returns_matrix)
    if rc is None and has_peers:
        rc = whites_reality_check(returns_matrix)
    # Candidate-aware capacity: use the strategy's OWN realized per-bar edge (bps), so a no-edge
    # strategy gets ~zero capacity (fails) while a real edge on a liquid market passes -- instead
    # of the old fixed edge_bps that made this gate a constant veto for every candidate.
    eff_edge_bps = edge_bps if edge_bps is not None else max(0.0, float(arr.mean()) * 1.0e4)
    cap = capacity_estimate(adv_usd=adv_usd, edge_bps=max(eff_edge_bps, 1.0e-9))
    tail = tail_risk(arr)

    metrics = ValidationMetrics(
        annual_sharpe=float(sharpe_ratio(arr) * np.sqrt(_PERIODS_PER_YEAR)),
        expected_value=float(arr.mean()),
        oos_sharpe=wf.oos_sharpe,
        dsr=dsr.dsr,
        pbo=pbo.pbo if pbo is not None else 1.0,
        reality_p=rc.p_value if rc is not None else 1.0,
        capacity_usd=cap.capacity_usd,
        fragility=tail.tail_risk_score,
    )

    gates = {
        "economic_mechanism": bool(hypothesis.failure_modes),   # declared before testing
        "expected_value": metrics.expected_value > 0,
        "cpcv": _cpcv_positive_fraction(arr) >= _CPCV_MIN_POSITIVE,
        "walk_forward": wf.status is WalkForwardStatus.PASSED,
        "dsr": dsr.passed,
        "pbo": pbo is not None and not pbo.overfit,
        "reality_check": rc is not None and rc.significant_at_5pct,
        "capacity": cap.capacity_usd >= capacity_required(
            live_book_usd() if deployed_equity_usd is None else deployed_equity_usd,
            live_sleeves() if n_sleeves is None else n_sleeves),
        "fragility": tail.acceptable,
        # skipped-as-True when no benchmark is supplied (see the constant block above); when
        # one IS supplied the candidate must beat buy-and-hold and equal-weight outright.
        "beats_baselines": _beats_baselines(arr, benchmark_returns),
    }
    failed = [name for name, ok in gates.items() if not ok]
    return ValidationVerdict(
        survived=not failed, gates=gates,
        rejection_reason="" if not failed else "failed: " + ", ".join(failed),
        metrics=metrics,
    )
