"""Full institutional validation per candidate — every gate, no weakening, fail-closed.

Runs the complete stack and a candidate survives ONLY if every gate passes: economic mechanism,
CPCV (purged K-fold OOS consistency), PBO, Deflated Sharpe (trials-deflated), White's Reality Check,
Walk-Forward, capacity, fragility (tail risk), and an accelerated shadow check (final held-out
segment). Reuses the existing validation / discovery primitives. Thresholds are constants here and
never relaxed.

ANNUALISATION IS DECLARED BY THE CALLER, NEVER ASSUMED (R0086, fixed 2026-08-05)
-------------------------------------------------------------------------------
This module used to hold ``_PERIODS_PER_YEAR = 24 * 260`` (6240 — HOURLY bars on a 260-session
calendar) and apply ``sqrt(6240)`` to whatever series arrived, while ``validate()`` had no
frequency parameter at all. Every caller that fed anything other than MT5 hourly bars therefore
stored an inflated ``annual_sharpe``:

    DAILY crypto bars (365/yr)   sqrt(6240/365)  = 4.135x too large
    8h funding bars  (1095/yr)   sqrt(6240/1095) = 2.387x too large
    12h bars         (730/yr)    sqrt(6240/730)  = 2.924x too large
    DAILY FX bars    (252/yr)    sqrt(6240/252)  = 4.976x too large

That number is not decoration: ``libs/autodiscovery/memory.py`` persists it for EVERY candidate,
and ``scripts/run_rejection_rescore.py`` ranks the reject-recovery queue by
``max(oos_sharpe, annual_sharpe)``. So the fix is a REQUIRED ``periods_per_year`` argument on
``validate()`` — no default, because any default is a frequency assumption wearing a different
hat, and the one this file used to hold was wrong for every production caller but one.

``periods_per_year=None`` is the ONE thing a default could never be: an explicit declaration that
the series has no bar clock (per-BET returns, e.g. scripts/run_prediction_markets.py). It reports
``annual_sharpe`` as UNMEASURED rather than manufacturing a number — the same treatment
``adv_usd``/``capacity`` got in R0080, and for the same reason.

PRE-FIX STORED ROWS ARE INFLATED AND ARE NOT COMPARABLE TO POST-FIX ONES.
Every ``research_candidates.annual_sharpe`` written before 2026-08-05 was produced by the hourly
constant above, whatever bars the campaign actually ran on; the lab's own default path was D1, so
those rows carry the 4.135x inflation. History is NOT rewritten here —
silently rescaling stored verdicts would destroy the ability to reproduce what the desk decided at
the time — so the two populations are distinguished at the point of writing instead: since this
fix, the lab records the bar interval it scored on in ``candidate_returns.timeframe`` (it used to
write NULL because nothing told the lab its own frequency). A row whose series carries a declared
timeframe was annualised honestly; a NULL is a pre-fix row and its ``annual_sharpe`` must be
divided by ``sqrt(6240/ppy)`` before it can be compared with anything. Ranking the two together
un-adjusted — which the reject queue does — orders old rows ~4x ahead of identical new ones.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

import numpy as np

from libs.autodiscovery.models import Hypothesis, ValidationMetrics, ValidationVerdict
from libs.data.timeframe import Timeframe
from libs.discovery.capacity import capacity_estimate
from libs.discovery.tail_risk import tail_risk

# re-exported for tests/autodiscovery/test_capacity_relative.py. validate()'s own capacity gate
# calls capacity_status() below -- the 10%-slice band (L1.18a). It used to call a local
# _min_capacity_usd() implementing a 2x-of-book multiple; that rule and its constant were deleted
# 2026-08-01 (R0080) rather than left dead, because a spare capacity bar sitting in the file is
# precisely how the desk ended up running two of them at once.
from libs.research.capacity_policy import capacity_required, venue_min_notional_usd  # noqa: F401
from libs.validation.baselines import baseline_scorecard
from libs.validation.campaign_window import (
    CAMPAIGN_ALPHA,
    StrataPlan,
    plan_strata,
    stratum_matrix,
)
from libs.validation.cpcv import CPCV
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.errors import ValidationError
from libs.validation.fdr import benjamini_hochberg
from libs.validation.pbo import PBOResult, probability_backtest_overfitting
from libs.validation.reality_check import RealityCheckResult, whites_reality_check
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus
from libs.validation.robustness_filters import not_too_lucky, sample_adequacy
from libs.validation.screen_select import ScreenSelection, screen_select
from libs.validation.stepwise import (
    CSCVResult,
    StepdownResult,
    cscv_candidate_pbo,
    romano_wolf_stepdown,
)

# DELETED 2026-08-05 (R0086): `_PERIODS_PER_YEAR = 24 * 260`. It was the desk's only frequency
# assumption and it was applied to every series regardless of the bars in it (module docstring).
# The constant is GONE rather than kept as a default, because a default is exactly how a frequency
# assumption survives a fix: `validate()` now REQUIRES the caller to declare its clock, and
# `bars_per_year()` below derives it from a declared bar interval so the declaration is a lookup
# rather than an arithmetic opinion at each call site.
#: Crypto perps trade 24/7 -- there is no weekend and no session, so a daily bar is 1/365th of a
#: year, not 1/252nd. Both calendars are real and the caller picks: this one for crypto, ~252 for
#: MT5 FX/CFD sessions (see `days_per_year`).
CRYPTO_DAYS_PER_YEAR = 365.0
#: MT5 FX/metal/index sessions: ~252 tradeable days a year. The deleted constant used 260, which
#: is weekdays-with-no-holidays; 252 is the desk's own figure everywhere it already annualises MT5
#: series (run_mt5_portfolio, run_crossasset_robust, run_crossasset_shadow, run_mt5_crossasset),
#: and it is the SMALLER of the two, so adopting it here cannot inflate anything.
SESSION_DAYS_PER_YEAR = 252.0
_MINUTES_PER_DAY = 1440.0
#: The admissible band for a declared clock. The ceiling is one-minute bars on a 24/7 year
#: (525,600) -- the finest grid the lake holds -- and the floor is one observation a year, below
#: which "annualising" has nothing to annualise. A value outside it is not a slow or fast clock,
#: it is a units error (per-DAY instead of per-year, a millisecond count, a bar COUNT), and the
#: whole point of R0086 is that a wrong frequency must be refused rather than silently used.
_MIN_PERIODS_PER_YEAR = 1.0
_MAX_PERIODS_PER_YEAR = CRYPTO_DAYS_PER_YEAR * _MINUTES_PER_DAY


def bars_per_year(bar: Timeframe | str, *,
                  days_per_year: float = CRYPTO_DAYS_PER_YEAR) -> float:
    """Observations per year for a DECLARED bar interval — the annualiser's only sanctioned source.

    ``bars_per_year(Timeframe.D1)`` is 365 (crypto, 24/7), ``Timeframe.H8`` is 1095 (the native
    perp-funding clock), ``Timeframe.H1`` is 8760. Pass ``days_per_year=SESSION_DAYS_PER_YEAR``
    for MT5 FX/CFD series, where the market is shut two days a week.

    An unknown interval RAISES. That is the point: the failure this replaces was a validator that
    accepted any series and annualised it with a constant, so the one behaviour this function must
    never have is a fallback. The result is range-checked too, so a nonsense calendar is refused
    HERE -- at the lab's construction, say -- rather than one campaign later inside validate().
    """
    try:
        tf = bar if isinstance(bar, Timeframe) else Timeframe(str(bar).upper())
    except ValueError as exc:
        raise ValidationError(
            f"unknown bar interval {bar!r}; declare one of "
            f"{', '.join(t.value for t in Timeframe)} or pass periods_per_year directly"
        ) from exc
    return _checked_periods_per_year(float(days_per_year) * _MINUTES_PER_DAY / float(tf.minutes))


def _checked_periods_per_year(periods_per_year: float) -> float:
    """The declared clock, or a refusal. Never a repair, never a fallback."""
    try:
        ppy = float(periods_per_year)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"periods_per_year={periods_per_year!r} is not a number; it is a COUNT of bars per "
            "year, not a bar interval -- use bars_per_year(Timeframe.D1) to convert one"
        ) from exc
    if not np.isfinite(ppy) or not (_MIN_PERIODS_PER_YEAR <= ppy <= _MAX_PERIODS_PER_YEAR):
        raise ValidationError(
            f"periods_per_year={periods_per_year!r} is not a bar clock: it must be finite and in "
            f"[{_MIN_PERIODS_PER_YEAR:g}, {_MAX_PERIODS_PER_YEAR:g}] (one bar a year to one-minute "
            "bars 24/7). Use bars_per_year(Timeframe.D1) etc., or periods_per_year=None to declare "
            "that this series has no bar clock and leave annual_sharpe UNMEASURED."
        )
    return ppy


_DSR_THRESHOLD = 0.95
_PBO_THRESHOLD = 0.5       # same bar as PBOResult.overfit; only the ATTRIBUTION changed
# CAPACITY PARITY (principal order 2026-07-30; constitution L1.18/§42 made ARITHMETIC).
# The old bar was a FIXED $100,000 institutional floor. On a desk deploying ~$5k that rejects
# edges it could fill COMPLETELY -- measured 182 of 420 campaign candidates failed with capacity
# among their blockers (reports/gate_histogram.json: capacity 238/420 pass). An edge that can
# absorb 20x the desk's entire book was being called too small. That is capacity PICKINESS, and
# it costs exactly the compounding the desk exists to maximise: a $20k-capacity edge at $5k of
# equity is 100% usable and compounds identically to a $20m one until the quota binds.
# THE RULE: an edge fails capacity ONLY if it cannot absorb a meaningful slice of the desk's OWN
# size. It is then exploited to ITS OWN quota, never deprioritised for being small, and never
# ranked below a larger-capacity edge (L1.18: edges are edges).
# PRINCIPAL CLARIFICATION 2026-07-30: capital deploys from ~$1k and may start as low as ~$100.
# At $100 live, a $300-capacity edge is FULLY usable and must be exploited -- so the floor cannot
# be an institutional round number, it can only be the point where EXECUTION PHYSICS stops working
# (L1.5). Below ~20 venue-minimum notionals there is no room for a few economic round-trips, and
# that -- not a capital-size opinion -- is the only defensible absolute floor.
_DESK_EQUITY_FALLBACK_USD = 1.0e3     # used only when live equity is unreadable
# THE ADMISSION BAND IS A MINIMUM SLICE, NOT A MULTIPLE OF THE BOOK (principal 2026-07-30).
# A multiple was wrong and measurably so: at $1,000 equity a 2x rule marked capacity of $300,
# $800 and even $1,500 as OUTGROWN -- edges that can hold 30%, 80% and 150% of the whole book.
# The book runs MANY edges in parallel (that is the diversification the objective actually wants),
# so an edge never needs to hold the entire book; it needs to hold a slice big enough to matter.
# Consequence, which is the compounding point: the admissible band SLIDES UP with equity and stays
# INCLUSIVE at the small end forever -- at $1k everything from ~$200 up is in; at $50k a
# $300-capacity edge has finally become a rounding error and retires by OUTGROWTH.
_MIN_SLICE_FRACTION = 0.10            # an edge must hold >=10% of the book to be worth a quota
# DELETED 2026-08-01 (R0080): `_CAPACITY_MULTIPLE_OF_EQUITY = 2.0`, "RETAINED only for the
# gauntlet's own headroom bar". That retention is the whole defect -- the gauntlet's own bar WAS
# the desk's capacity bar for every candidate it screened, so "retained only for" described a
# second, stricter, unconstitutional rule quietly outranking the one above it. There is now ONE
# band: capacity_status().
# CAPACITY SINGLE-SOURCE (R0218). The venue minimum notional is MEASURED -- it lives in
# data/capacity_floor.json, written by scripts/capacity_simulator.py off the live exchangeInfo
# endpoints -- and this file used to RESTATE it as a private `= 10.0` literal: the same
# one-policy-many-copies defect §42 records for the capacity band itself. It is now READ from
# that artifact through the capacity-policy leaf, with two deliberate properties:
#   * FALLBACK to the historical 10.0 ONLY when the canonical source is ABSENT or unreadable (e.g. a
#     checkout where the simulator has never run -- venue_min_notional_usd() then returns None). An
#     unmeasured venue must not zero the floor: that would admit dust-sized edges, making an
#     unreadable file the loosest possible answer -- the exact failure _desk_equity_usd documents.
#   * TIGHTEN-ONLY: a measured value may RAISE this floor, never lower it below the fallback. The
#     recorded truth (spot_min 5.0) sits BELOW 10.0, and adopting it outright would LOOSEN the
#     SUB-VIABLE gate. This change is de-duplication of a constant, not a threshold change, so the
#     effective values are unchanged today: $10 venue minimum, $200 viability floor.
_VENUE_MIN_NOTIONAL_FALLBACK_USD = 10.0   # Binance-class minimum order notional
_VENUE_MIN_NOTIONAL_USD = max(venue_min_notional_usd() or _VENUE_MIN_NOTIONAL_FALLBACK_USD,
                              _VENUE_MIN_NOTIONAL_FALLBACK_USD)
_EXEC_VIABILITY_FLOOR_USD = 20.0 * _VENUE_MIN_NOTIONAL_USD   # ~$200: a handful of economic trips


def _desk_equity_usd() -> float:
    """Live deployable equity, read defensively. The capacity bar is RELATIVE to this so it
    scales with the desk instead of freezing an institutional assumption into a seed-stage book.

    ONE SOURCE, AND IT WAS TWO (found by check_utilisation.py, 2026-07-30). This function read
    `data/cashcarry_config.json:capital` while `libs.research.capacity_policy.live_book_usd()` read
    VENUE TRUTH from the NAV chain. Measured the day it was found: config said $4,500, venue truth
    said $13,155. Every capacity band in the desk is a ratio to this number, so the whole gauntlet
    was sizing edges against a book 2.9x smaller than the real one -- ADMITTING edges the desk had
    already outgrown, and reporting them as healthy inventory.

    That is the L1.18a $100,000-floor defect running in the opposite direction, and it is the same
    root cause both times: a capacity threshold evaluated against a number that is not the book.
    check_capacity_single_source fences the capacity POLICY constant; nothing fenced its INPUT.

    ORDER: venue truth -> the live web artifact -> config -> constant. Never zero -- zero would
    make every edge OUTGROWN and empty the shortlist on an unreadable file, and an unreadable file
    must never be the most destructive possible answer.
    """
    import json as _json
    from pathlib import Path as _Path
    try:
        from libs.research.capacity_policy import live_book_usd
        # fallback=0.0 so this rung reports ONLY genuine venue truth. Calling it with its own
        # default would return DEFAULT_BOOK_USD on an unreadable ledger, and a constant dressed as
        # venue truth would outrank the real local config below it -- a silent downgrade of the
        # ladder rather than a fallback through it.
        venue = float(live_book_usd(fallback=0.0))
        if venue > 0:
            return venue
    except (ImportError, OSError, ValueError, TypeError):
        pass
    for src, keys in ((_Path("web/cashcarry_live.json"), ("equity", "net_equity", "deployed")),
                      (_Path("data/cashcarry_config.json"), ("capital", "authorized_capital"))):
        try:
            d = _json.loads(src.read_text("utf-8"))
        except (OSError, _json.JSONDecodeError):
            continue
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
    return _DESK_EQUITY_FALLBACK_USD


def capacity_status(capacity_usd: float, *, equity_usd: float | None = None) -> str:
    """ADMIT / OUTGROWN / SUB-VIABLE -- and the distinction is a lifecycle law, not bookkeeping.

    THE MODEL THE PRINCIPAL SPECIFIED (2026-07-30), and it is how small edges are supposed to end:
    a small-capacity edge is admitted and EXPLOITED TO ITS QUOTA while the book is small; as capital
    compounds past that quota the edge stops being able to hold a meaningful slice and retires by
    OUTGROWTH. That is natural attrition from SUCCESS, not failure --

      * OUTGROWN edges are NEVER graveyarded as dead mechanisms. Nothing was refuted: the mechanism
        was real, it was harvested to exhaustion, and the book simply grew past it. Graveyarding it
        would poison the novelty gate against a mechanism that WORKED, and would corrupt the
        family-level survival statistics that steer future search (L1.17).
      * SUB-VIABLE is the only genuine capacity rejection: the edge cannot support even a handful of
        economic round-trips at venue minimums, so execution physics (L1.5) kills it at ANY equity.
      * Small and large capacity are hunted SIMULTANEOUSLY and never ranked against each other
        (L1.18a). A pipeline that waits for big-capacity edges forfeits the compounding available
        right now, and compounding now is what buys the capital that makes big edges relevant.
    """
    eq = _desk_equity_usd() if equity_usd is None else float(equity_usd)
    if capacity_usd < _EXEC_VIABILITY_FLOOR_USD:
        return "SUB-VIABLE"
    if capacity_usd < eq * _MIN_SLICE_FRACTION:
        return "OUTGROWN"
    return "ADMIT"


def capacity_runway_days(capacity_usd: float, *, equity_usd: float | None = None,
                         growth_rate_annual: float = 1.0) -> float:
    """Days until the book grows past this edge's usable band -- its EXPIRY DATE.

    THE RACE THE PRINCIPAL NAMED (2026-07-30): a small-capacity edge is only worth anything if it
    reaches live BEFORE capital outgrows it. A validation pipeline slower than the runway delivers
    edges that are already rounding errors on arrival, which is not caution -- it is a guaranteed
    zero. So runway is computed and COMPARED to pipeline latency (see `capacity_race`), and the
    forward-slot queue is ordered by EXPIRY, shortest first, because a long-runway edge loses
    nothing by waiting and a short-runway one loses everything.

    growth_rate_annual: continuous growth of equity, 1.0 = 100%/yr. The desk's own target band is
    80-120%/yr (GROWTH_UNLOCK_LADDER), so the default is deliberately the middle of the mandate
    rather than an optimistic number.
    """
    import math
    eq = _desk_equity_usd() if equity_usd is None else float(equity_usd)
    if eq <= 0 or growth_rate_annual <= 0:
        return float("inf")
    # equity at which this edge becomes a rounding error on the book
    outgrow_at = capacity_usd / _MIN_SLICE_FRACTION
    if outgrow_at <= eq:
        return 0.0                                      # already outgrown
    return 365.0 * math.log(outgrow_at / eq) / growth_rate_annual


def capacity_race(capacity_usd: float, *, validation_days: float,
                  equity_usd: float | None = None,
                  growth_rate_annual: float = 1.0) -> dict[str, Any]:
    """Does this edge reach live before the book outgrows it? Verdict + the honest remedy.

    Verdicts:
      REACHES-LIVE   runway exceeds the pipeline latency with margin -- ship it normally.
      TIGHT          it lands with little life left; worth prioritising in the slot queue.
      DOA            it is outgrown before validation could finish. THE REMEDY IS NEVER A SHORTER
                     CLOCK OR A LOWER BAR (L1.6 -- the confirmation bar never loosens). The only
                     honest accelerants are MORE OBSERVATIONS PER DAY (the desk measured this: an
                     8h funding panel carries ~sqrt(3)x the evidence rate of a daily one at
                     vif 1.008, gap #44) and NOT QUEUEING -- run the slot now rather than later.
                     If neither is available the edge is structurally unreachable at this equity
                     and is recorded as such, not silently shelved.
    """
    runway = capacity_runway_days(capacity_usd, equity_usd=equity_usd,
                                  growth_rate_annual=growth_rate_annual)
    if runway <= validation_days:
        verdict = "DOA"
    elif runway < validation_days * 2.0:
        verdict = "TIGHT"
    else:
        verdict = "REACHES-LIVE"
    return {"capacity_usd": capacity_usd, "runway_days": round(runway, 1),
            "validation_days": validation_days, "verdict": verdict,
            "slot_priority": round(runway, 1),      # ascending: shortest runway is served first
            "remedy": ("higher-frequency evidence (8h panel ~sqrt(3)x rate) and/or an immediate "
                       "slot -- never a shorter clock or a lower bar"
                       if verdict != "REACHES-LIVE" else "none needed")}
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


def _beats_baselines(returns: np.ndarray, benchmark: np.ndarray | None,
                     universe: np.ndarray | None = None) -> bool:
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
        return bool(baseline_scorecard(returns, buy_hold_returns=b,
                                       universe_returns=universe).beats_all)
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

    DEPRECATED as a GATE input -- kept for diagnostics and for call sites not yet migrated.

    Both statistics take only the matrix; the candidate's own returns are never an input.  Used as
    per-candidate gates they are therefore campaign CONSTANTS, and the "no change to the verdict"
    that made caching them look free is exactly the defect: every candidate in a batch gets the
    same verdict whatever its merit.  Measured 2026-07-29 on the real 420-candidate campaign --
    PBO 0.6159 (>0.5) and White RC p 0.4220 (>=0.05) -- which alone forced 420/420 rejections.
    Measured on a synthetic campaign containing one strong winner, the same two gates pass EVERY
    pure-noise candidate.  Too strict and too loose, decided by the batch rather than the
    candidate.

    Use :func:`campaign_gate_stats` + ``validate(campaign=..., column=...)`` instead.
    """
    if returns_matrix.shape[1] < 2:
        return None, None
    return probability_backtest_overfitting(returns_matrix), whites_reality_check(returns_matrix)


class CampaignGates:
    """Per-candidate multiplicity statistics for one campaign, computed once.

    Holds the candidate-aware replacements (CSCV rank-consistency, Romano-Wolf stepdown) and the
    legacy campaign statistics, which stay available as diagnostics of the SEARCH PROCEDURE --
    which is the thing they actually measure.
    """

    __slots__ = ("cscv", "legacy_pbo", "legacy_rc", "screen", "stepdown")

    def __init__(
        self,
        cscv: CSCVResult,
        stepdown: StepdownResult,
        legacy_pbo: PBOResult | None,
        legacy_rc: RealityCheckResult | None,
    ) -> None:
        self.cscv = cscv
        self.stepdown = stepdown
        self.legacy_pbo = legacy_pbo
        self.legacy_rc = legacy_rc
        # SCREEN-STAGE SELECTION (gap #71, 2026-07-30). Computed and REPORTED alongside the
        # family-wise verdict; it does NOT change the survival gate here. The measured reason:
        # Romano-Wolf FWER admits 0/420 at every window tested (best adjusted p 0.522 at min-length,
        # 0.089 at max-observation), so as a SCREEN gate it carries zero information about candidate
        # quality -- and a bar that rises with generation volume is what TWO_STAGE_DISCOVERY_LAW
        # forbids. Promotion authority is untouched: forward clocks keep Holm/FWER on <=12 slots.
        self.screen: ScreenSelection | None = None
        with_screen = screen_select(stepdown, q=0.05, method="by") if stepdown else None
        self.screen = with_screen


def campaign_gate_stats(returns_matrix: np.ndarray, *,
                        alpha: float = 0.05) -> CampaignGates | None:
    """One pass over the campaign matrix yielding PER-CANDIDATE pbo / significance verdicts.

    Same thresholds as before (PBO <= 0.5, significance at ``alpha``) -- only the *attribution*
    changes, from one campaign verdict imposed on everyone to a verdict each candidate earns.
    Romano-Wolf still controls family-wise error across all N, so multiplicity is paid for in full.

    ``alpha`` is the level THIS family is tested at, and threading it is what makes a STRATIFIED
    campaign honest rather than a loophole. A campaign cut into k strata runs k families; testing
    each at 5% would give an overall false-positive rate near 1-(1-0.05)^k. Callers that split
    MUST pass CAMPAIGN_ALPHA/k -- see :func:`stratified_campaign_gates`, which is the only
    supported way to do the split and computes the level itself. The default reproduces the
    single-family behaviour exactly, so existing callers are unaffected.
    """
    matrix = np.asarray(returns_matrix, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 2:
        return None
    legacy_pbo, legacy_rc = campaign_pbo_rc(matrix)
    return CampaignGates(
        cscv=cscv_candidate_pbo(matrix),
        stepdown=romano_wolf_stepdown(matrix, alpha=alpha),
        legacy_pbo=legacy_pbo,
        legacy_rc=legacy_rc,
    )


def stratified_campaign_gates(
    return_series: Sequence[np.ndarray],
) -> tuple[list[tuple[CampaignGates, int] | None], StrataPlan]:
    """Per-candidate campaign statistics WITHOUT truncating every candidate to the shortest.

    THE DEFECT THIS REPLACES. Every campaign builder aligned its matrix with ``r[-min_len:]``, so
    ONE short candidate truncated every other. Measured on the desk's own 420-candidate campaign:
    310 observations retained of 1,808 available per candidate -- **82.9% of the data already on
    disk, discarded before a single test ran** (docs/research/gate_power_audit.md section 5).
    That audit measured history length as THE binding constraint on the whole funnel
    (T=310->2500 takes power at true Sharpe 2.0 from 0.00% to 19.58%) while campaign size buys
    nothing (N=420->30 leaves power at 0.00%). The truncation made exactly the wrong trade: it
    spent observations to keep candidates aligned.

    THIS RAISES POWER; IT DOES NOT LOWER A BAR. Each stratum is its own family tested at
    ``CAMPAIGN_ALPHA/k``, so total family-wise error stays at 5% however the campaign is cut --
    every stratum is held to a STRICTER per-family level than the 5% the single campaign used.
    The partition is decided by ``plan_strata`` from LENGTHS ALONE (it never sees a return, a
    Sharpe or a p-value), so no channel exists through which results could shape it. Both
    properties are pinned by tests, because a window chosen after peeking at performance would be
    a selection effect dressed up as a fix.

    Returns ``(per_candidate, plan)`` where ``per_candidate[i]`` is ``(gates, column)`` for the
    stratum candidate *i* was tested in, or **None** when no stratum supports its history. A None
    is NOT a pass and NOT a statistical rejection: callers must record it as *untested*. Letting
    it fall through to the legacy campaign-constant path would be fail-closed but would file a
    data-availability exclusion in the graveyard under a false mechanism of death, which corrupts
    the family survival statistics that steer future search (L1.17).
    """
    series = [np.asarray(r, dtype="float64") for r in return_series]
    plan = plan_strata([len(r) for r in series])
    per_candidate: list[tuple[CampaignGates, int] | None] = [None] * len(series)
    k = max(1, len(plan.strata))
    # R0263 TIMED, PER STRATUM. Romano-Wolf's bootstrap is linear in retained observations, so
    # stratifying buys 180.8x the expected discoveries at roughly 5x the compute -- and that "5x"
    # was a prose comment carrying one hand-measured fixture number (campaign_window.py's COST
    # note), never a field anything could read. An unmeasured cost is the one a reader is free to
    # imagine, in either direction: too cheap and nobody notices the cycle slipping, too dear and
    # somebody "fixes" it by cutting n_boot, which is the resolution of the multiplicity
    # correction and would loosen the bar to buy back seconds.
    # perf_counter, not time.time: this is a DURATION, and a wall-clock that an NTP step can walk
    # backwards is not one. The repo had no timing convention to match -- zero perf_counter calls
    # existed anywhere -- so this picks the correct primitive rather than the nearest habit.
    stratum_seconds: list[float] = []
    t0 = time.perf_counter()
    for s in plan.strata:
        t_s = time.perf_counter()
        gates = campaign_gate_stats(stratum_matrix(series, s), alpha=CAMPAIGN_ALPHA / k)
        stratum_seconds.append(round(time.perf_counter() - t_s, 3))
        if gates is None:                      # cohort of <2 cannot carry multiplicity statistics
            continue
        for column, cand in enumerate(s.keep):  # keep is sorted, matching stratum_matrix's columns
            per_candidate[cand] = (gates, column)
    # The TOTAL is measured independently of the per-stratum sum rather than derived from it, so
    # any time spent between strata shows up as a gap instead of vanishing into the parts.
    plan = plan._replace(seconds=round(time.perf_counter() - t0, 3),
                         stratum_seconds=tuple(stratum_seconds))
    return per_candidate, plan


def validate(
    returns: np.ndarray,
    *,
    # THE BAR CLOCK, DECLARED BY WHOEVER READ THE BARS (R0086, 2026-08-05). REQUIRED and
    # deliberately without a default: the defect this replaces was a module-level constant
    # (24 * 260) applied to every series that arrived, inflating stored annual Sharpe 4.135x on
    # daily bars and 2.387x on 8h bars -- and a default here would be the same constant with a
    # nicer name. `bars_per_year(Timeframe.D1)` is the sanctioned way to compute it.
    #
    # None is an explicit declaration that the series HAS no bar clock -- per-BET returns, where
    # observations are settlements rather than bars (scripts/run_prediction_markets.py). It reports
    # annual_sharpe as UNMEASURED instead of inventing a number, which is the R0080 treatment of
    # adv_usd: a missing input must not be indistinguishable from a measured one downstream.
    periods_per_year: float | None,
    hypothesis: Hypothesis,
    n_trials: int,
    sharpe_estimates: np.ndarray,
    returns_matrix: np.ndarray,
    # PER-SYMBOL DOLLAR ADV. Was `adv_usd: float = 1.0e11` until 2026-08-01 (R0080), and that
    # default is why every capacity figure this desk has ever stored is a fiction: NO production
    # caller passes it, so all 1,673 candidates in the lab store were sized against a HUNDRED
    # BILLION DOLLAR daily volume -- two to four orders of magnitude above any real crypto pair.
    #
    # It is now None-by-default and the capacity gate reports UNMEASURED when it is absent, which
    # is the same treatment `beats_baselines` and `sample_adequacy` already get. A default that
    # silently manufactures a number is strictly worse than no number: it cannot be distinguished
    # from a measurement downstream, and 966 of those 1,673 stored capacities are the identical
    # constant 5.04e-13 -- the arithmetic signature of edge~0 against adv=1e11, sitting in the
    # store looking like 966 independent capacity measurements.
    adv_usd: float | None = None,
    edge_bps: float | None = None,
    pbo: PBOResult | None = None,
    rc: RealityCheckResult | None = None,
    benchmark_returns: np.ndarray | None = None,
    campaign: CampaignGates | None = None,
    column: int | None = None,
    # NUMBER OF ROUND-TRIP TRADES the candidate actually took (wired 2026-08-01).
    #
    # There was NO minimum-trade gate anywhere in this desk's validation, which is a hole a
    # transcript found rather than an audit: a strategy can post a magnificent Sharpe on fifteen
    # trades and the entire gauntlet above has nothing to say about it, because every statistic
    # here is computed per-OBSERVATION and a 5,000-bar series holding one position the whole time
    # has 5,000 observations and one bet.
    #
    # Optional because most existing callers pass a return SERIES and genuinely do not know the
    # trade count. When it is absent the gate is reported as UNMEASURED, never as passed -- see
    # the `unmeasured` field. That distinction exists because of `beats_baselines`, which quietly
    # returned True for every candidate this desk ever screened simply because no caller supplied
    # benchmark_returns, and read as a passed gate in every verdict for months.
    n_trades: int | None = None,
    # SIBLING-BRANCH PER-CANDIDATE SEAM (register #71, merged 2026-08-04). `pc_pbo` / `pc_p` carry
    # ONE candidate's own CSCV-PBO and FWER-adjusted p, computed once per campaign by
    # `libs/validation/per_candidate`. It is the SAME statistic as the `campaign=`/`column=` path
    # through a thinner interface; that path wins when both are supplied. Kept because callers
    # written against this seam must not silently fall back to campaign-wide broadcast verdicts --
    # the exact defect #71 removed.
    pc_pbo: float | None = None,
    pc_p: float | None = None,
    # Sibling-branch names for the baseline gate's inputs. `buy_hold_returns` is an alias for
    # `benchmark_returns` (used only when the latter is absent); `universe_returns` additionally
    # demands the candidate beat the equal-weight universe, a strictly harder baseline.
    buy_hold_returns: np.ndarray | None = None,
    universe_returns: np.ndarray | None = None,
) -> ValidationVerdict:
    # Refused BEFORE anything else, including the length check: a caller with a broken clock has a
    # broken verdict whatever the series length, and raising here means the mistake surfaces at the
    # call site that made it rather than as a quietly wrong number in a report.
    ppy = _checked_periods_per_year(periods_per_year) if periods_per_year is not None else None
    arr = np.asarray(returns, dtype="float64")
    if len(arr) < 250:
        return ValidationVerdict(
            survived=False, gates={"sufficient_data": False},
            rejection_reason="insufficient data", metrics=ValidationMetrics(),
        )

    # Walk-forward (OOS). Shadow/paper are separate lifecycle stages (see lifecycle.py).
    wf = WalkForwardEngine().evaluate(arr, n_splits=4, test_size=max(20, len(arr) // 6))
    # Overfitting / significance. PREFERRED path: per-candidate statistics from `campaign`, which
    # this candidate earns on its own column. SECOND path: `pc_pbo`/`pc_p`, the sibling branch's
    # thinner seam carrying the same per-candidate statistics precomputed by the caller. LEGACY
    # path (neither supplied): the campaign constants, retained only so unmigrated call sites keep
    # their exact prior behaviour.
    has_peers = returns_matrix.shape[1] >= 2
    per_candidate = campaign is not None and column is not None
    pc_supplied = pc_pbo is not None and pc_p is not None
    # THE MULTIPLICITY PENALTY IS PAID ONCE, NOT TWICE (audit 2026-08-01, R0224).
    #
    # DSR is a Probabilistic Sharpe Ratio measured against a DEFLATED benchmark
    # sr0 = expected_max_sharpe(n_trials, ...). That deflation IS a multiplicity correction over
    # the campaign. On the per-candidate path Romano-Wolf ALREADY controls family-wise error over
    # the same N candidates -- so the desk was correcting for the same multiplicity twice and
    # compounding two family-wise bars into one unpassable one.
    #
    # MEASURED, on 240 genuine alphas and 4,800 nulls per effect size (N=420, T=310):
    #     true SR    all gates    without DSR's deflation    false positives
    #        3.0          0.4%                      14.6%    0.000% both ways
    #        5.0          5.8%                      83.8%    0.000% both ways
    #        7.0         32.9%                      99.6%    0.000% both ways
    # Romano-Wolf alone holds the false-positive rate at 0 of 4,800 (95% upper bound 0.08%), so
    # the second deflation bought NO error control and cost up to 78 points of power. Removing
    # BOTH corrections instead sends false positives to 32%, which is why exactly one is kept.
    #
    # WHAT IS DELIBERATELY RETAINED: with n_trials=1 the deflation vanishes but the PSR does not,
    # and PSR adjusts for SKEW and KURTOSIS -- which Romano-Wolf's mean-based bootstrap statistic
    # does not model. A negatively-skewed short-vol payoff can post a beautiful sample Sharpe on
    # a true zero edge; that is the one job here Romano-Wolf cannot do, so the moment-aware half
    # of DSR stays and only the duplicated deflation goes.
    #
    # The LEGACY path keeps the full deflation: nothing else corrects for multiplicity there.
    # `pc_p` is FWER-adjusted by construction (libs/validation/per_candidate), so the R0224 rule
    # applies to that seam identically: the multiplicity penalty is paid once, in Romano-Wolf.
    dsr_trials = 1 if (per_candidate or pc_supplied) else n_trials
    dsr = deflated_sharpe_ratio(arr, n_trials=dsr_trials, sharpe_estimates=sharpe_estimates,
                                threshold=_DSR_THRESHOLD)
    if per_candidate:
        assert campaign is not None and column is not None  # narrowed by per_candidate
        cand_pbo = campaign.cscv.candidate_pbo[column]
        pbo_ok = cand_pbo <= _PBO_THRESHOLD
        sig_ok = campaign.stepdown.rejected[column]
        pbo_value, reality_value = cand_pbo, campaign.stepdown.adjusted_p[column]
    elif pc_supplied:
        assert pc_pbo is not None and pc_p is not None  # narrowed by pc_supplied
        pbo_ok = pc_pbo <= _PBO_THRESHOLD
        sig_ok = pc_p <= 0.05
        pbo_value, reality_value = float(pc_pbo), float(pc_p)
    else:
        if pbo is None and has_peers:
            pbo = probability_backtest_overfitting(returns_matrix)
        if rc is None and has_peers:
            rc = whites_reality_check(returns_matrix)
        pbo_ok = pbo is not None and not pbo.overfit
        sig_ok = rc is not None and rc.significant_at_5pct
        pbo_value = pbo.pbo if pbo is not None else 1.0
        reality_value = rc.p_value if rc is not None else 1.0
    # Candidate-aware capacity: use the strategy's OWN realized per-bar edge (bps), so a no-edge
    # strategy gets ~zero capacity (fails) while a real edge on a liquid market passes -- instead
    # of the old fixed edge_bps that made this gate a constant veto for every candidate.
    #
    # NO ADV, NO CAPACITY NUMBER (R0080). capacity_estimate is linear in adv_usd, so inventing an
    # ADV does not produce an approximate capacity -- it produces an arbitrary one, scaled by
    # whatever constant was chosen. There is no honest capacity without a volume measurement.
    eff_edge_bps = edge_bps if edge_bps is not None else max(0.0, float(arr.mean()) * 1.0e4)
    cap = (capacity_estimate(adv_usd=adv_usd, edge_bps=max(eff_edge_bps, 1.0e-9))
           if adv_usd is not None and adv_usd > 0 else None)
    tail = tail_risk(arr)

    metrics = ValidationMetrics(
        # MULTIPLICATIVE, and against the DECLARED clock: a per-bar Sharpe scales with the square
        # root of the number of bars in a year. 0.0 when no clock was declared -- see `unmeasured`
        # below, which is what stops a zero reading as "no edge".
        annual_sharpe=(float(sharpe_ratio(arr) * np.sqrt(ppy)) if ppy is not None else 0.0),
        expected_value=float(arr.mean()),
        oos_sharpe=wf.oos_sharpe,
        dsr=dsr.dsr,
        pbo=pbo_value,
        reality_p=reality_value,
        capacity_usd=cap.capacity_usd if cap is not None else 0.0,
        fragility=tail.tail_risk_score,
    )

    gates = {
        "economic_mechanism": bool(hypothesis.failure_modes),   # declared before testing
        "expected_value": metrics.expected_value > 0,
        "cpcv": _cpcv_positive_fraction(arr) >= _CPCV_MIN_POSITIVE,
        "walk_forward": wf.status is WalkForwardStatus.PASSED,
        "dsr": dsr.passed,
        "pbo": pbo_ok,
        "reality_check": sig_ok,
        "fragility": tail.acceptable,
        # skipped-as-True when no benchmark is supplied (see the constant block above); when
        # one IS supplied the candidate must beat buy-and-hold and equal-weight outright.
        # `buy_hold_returns` is the sibling branch's name for the same evidence stream; it fills
        # in only when `benchmark_returns` is absent, and `universe_returns` (when supplied)
        # additionally demands the candidate beat the equal-weight universe.
        "beats_baselines": _beats_baselines(
            arr,
            benchmark_returns if benchmark_returns is not None else buy_hold_returns,
            universe=universe_returns),
        # NOT-TOO-LUCKY, wired 2026-08-01. Studentised, never a fixed ratio: the source specified
        # "reject if OOS < 0.3 x IS", and that rule was MEASURED here rejecting 20-40% of genuine
        # alphas at every sample length from 310 to 5,000 bars, because a fixed ratio ignores how
        # noisily each Sharpe was estimated. Re-specified against the standard error of the
        # difference it costs 2.8% of real edges to remove 6.2% of flattered nulls -- roughly 17
        # nulls per real edge lost. It runs unconditionally because validate() now has all four
        # inputs; a report with is_sharpe 0.0 is treated as "nothing to compare" and passes.
        "not_too_lucky": not_too_lucky(
            wf.is_sharpe, wf.oos_sharpe, wf.n_is, wf.n_oos).passed,
    }
    # UNMEASURED IS ITS OWN STATE, and this is the whole lesson of `beats_baselines`. A gate whose
    # input was never supplied has not passed -- nobody looked. Folding that into `gates` as True
    # is how a gate can protect nothing for months while reading green in every artifact. It does
    # NOT block survival (this is a screen with zero promotion authority, and failing a candidate
    # for an input its caller does not have would kill real alphas), but it is impossible to miss.
    unmeasured: list[str] = []
    # NO CLOCK, NO ANNUAL NUMBER. `annual_sharpe` is 0.0 above when the caller declared
    # periods_per_year=None, and a bare 0.0 in the store is indistinguishable from a measured
    # zero-edge candidate -- which is precisely how a 4.135x inflation lived in the metric for
    # months without anyone being able to see it. Saying "nobody looked" is the whole R0086
    # lesson applied to the metric rather than to a gate.
    if periods_per_year is None:
        unmeasured.append("annual_sharpe")
    if n_trades is None:
        unmeasured.append("sample_adequacy")
    else:
        gates["sample_adequacy"] = sample_adequacy(n_trades).passed
    if benchmark_returns is None and buy_hold_returns is None:
        unmeasured.append("beats_baselines")
    # CAPACITY: THE 10%-SLICE BAND, NOT A MULTIPLE OF THE BOOK (R0080, L1.18a).
    #
    # This gate read `cap.capacity_usd >= _min_capacity_usd()`, i.e. capacity >= 2x desk equity.
    # L1.18a names that exact shape as the defect -- "THE BAND IS A MINIMUM SLICE (>=10% of book),
    # NEVER A MULTIPLE OF IT" -- and this file's own comment block has said since 2026-07-30 that
    # the multiple "was wrong and measurably so": at $1,000 equity it marked $300, $800 and $1,500
    # capacities OUTGROWN, edges able to hold 30%, 80% and 150% of the entire book. The band was
    # already implemented correctly in capacity_status() directly above; validate() simply never
    # called it, so the desk ran TWO capacity bars at once and the stricter, unconstitutional one
    # owned the gauntlet.
    #
    # BOTH HALVES LAND TOGETHER ON PURPOSE, because either alone misfires in opposite directions.
    # Swapping the band alone loosens the bar while capacity is still computed from a $100bn ADV
    # fiction. Plumbing real ADV alone shrinks every capacity by 3-4 orders of magnitude while the
    # 2x-multiple bar is still in place, which would fail essentially every candidate -- turning a
    # measurement fix into a systematic killer of exactly the small edges §42 calls this desk's
    # structural advantage.
    #
    # UNMEASURED, NEVER PASSED, when no ADV was supplied. This does not block survival (same rule
    # as sample_adequacy and beats_baselines: a screen with zero promotion authority must not fail
    # a candidate for an input its caller does not have). The honesty gain is the point -- a
    # missing ADV previously produced a confident capacity verdict computed from a constant.
    if cap is None:
        unmeasured.append("capacity")
    else:
        gates["capacity"] = capacity_status(cap.capacity_usd) == "ADMIT"

    # STATIONARITY, FOR THE CANDIDATES WHERE IT DECIDES CORRECTNESS (sibling-branch gate, merged
    # 2026-08-04). A mean-reverting / pairs card rests entirely on the spread being stationary; if
    # it is not, the backtest is fitting a trend and the "reversion" is a random walk that happened
    # to come back. The constitution bans hand-rolled ADF for exactly that reason and
    # `libs/research/stationarity` was written as the sanctioned seam -- then left unwired, so
    # nothing ever asked the question.
    #
    # The backend (statsmodels) is an OPTIONAL dependency, so absence is recorded as UNMEASURED
    # rather than silently skipped: the sibling branch's `pass` honoured "never passed-by-default"
    # but left no trace that nobody looked, which this file's own unmeasured discipline forbids.
    if getattr(hypothesis, "requires_stationarity", False):
        try:
            from libs.research.stationarity import StatsBackendMissing, adf_pvalue
            gates["stationary"] = adf_pvalue(arr) < 0.05
        except (StatsBackendMissing, ImportError, ValueError):
            unmeasured.append("stationary")   # unmeasurable is NOT passed -- and NOT silent

    failed = [name for name, ok in gates.items() if not ok]
    reason = "" if not failed else "failed: " + ", ".join(failed)
    if unmeasured:
        reason = (reason + " | " if reason else "") + "UNMEASURED: " + ", ".join(unmeasured)
    return ValidationVerdict(
        survived=not failed, gates=gates, rejection_reason=reason,
        metrics=metrics, unmeasured=tuple(unmeasured),
    )


def gate_discrimination(gate_results: list[dict[str, bool]]) -> dict[str, dict[str, Any]]:
    """GAP #71 INSTRUMENTATION -- which gates actually DISCRIMINATE, and which are constants.

    THE MEASURED PROBLEM. `pbo` and `reality_check` are computed ONCE per campaign (they are
    properties of the returns matrix, not of any candidate) and then applied as PER-CANDIDATE
    gates. So when campaign PBO is 0.6159 against a 0.50 bar, that gate reads False for every
    candidate in the campaign -- all 420 of them -- no matter how good any individual one is. The
    desk's own numbers: 420 candidates tested, ZERO survivors, while the genuinely per-candidate
    gates discriminated normally (walk_forward 58.1%, fragility 47.9%).

    WHY THIS REPORTS RATHER THAN FIXES. Turning a campaign veto into a rank would LOWER a
    statistical bar, and this desk's standing research directive is explicit -- *"Never reduce
    statistical standards. Only improve efficiency."* The gap register dates the redesign and
    marks it as needing a principal ruling on RANK-not-VETO. So this measures the mechanism
    instead of quietly relaxing it: a gate that passes everything or fails everything carries
    zero information about any individual candidate, and the desk should be able to SEE that
    rather than infer it from an empty survivor list.

    A constant gate is not necessarily wrong. A campaign really can be overfit end to end. What
    is wrong is not knowing which of the two you are looking at.
    """
    if not gate_results:
        return {}
    names = list(gate_results[0])
    n = len(gate_results)
    out: dict[str, dict[str, Any]] = {}
    for g in names:
        passed = sum(1 for r in gate_results if r.get(g))
        rate = passed / n
        constant = passed in (0, n)
        out[g] = {
            "pass_rate": round(rate, 4), "passed": passed, "n": n,
            "discriminates": not constant,
            "note": ("" if not constant else
                     (f"CONSTANT: this gate {'passed' if passed else 'FAILED'} for all {n} "
                      f"candidates, so it carries zero information about any individual one. "
                      + ("A gate failing everything is a campaign-level verdict wearing a "
                         "per-candidate costume -- the whole campaign is being rejected, not "
                         "these candidates." if not passed else
                         "A gate passing everything is not filtering; confirm it is still "
                         "wired to anything."))),
        }
    return out


def blocking_constant_gates(gate_results: list[dict[str, bool]]) -> list[str]:
    """Gates that FAILED every candidate -- the ones that make promotion arithmetically
    impossible regardless of candidate quality. Empty is the healthy state."""
    return [g for g, d in gate_discrimination(gate_results).items()
            if not d["discriminates"] and d["passed"] == 0]


def counterfactual_survivors(
    gate_results: list[dict[str, bool]], waive: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """GAP #71, THE QUESTION A RULING ACTUALLY NEEDS: if these gates were waived, who survives?

    "Should we relax the campaign veto?" is unanswerable in the abstract and trivially answerable
    from the gate matrix -- but only if someone computes it. It was computed ONCE, by hand, and
    the result lives in a recommendation-ledger entry nobody re-reads. This makes it an output of
    every campaign, so the ruling is made against current evidence rather than a remembered one.

    THE MEASURED ANSWER ON THE REAL 420: zero. Waiving `pbo` and `reality_check` produces no
    survivors, because every candidate ALSO failed at least one genuinely per-candidate gate --
    which is precisely what the register's "sole-cause failures EMPTY" was recording. Relaxing
    the veto would not have promoted anything; it would only have changed which failure was
    reported first.

    That is worth knowing in both directions. It says the campaign veto is not, today, the thing
    standing between the desk and a validated alpha -- so relaxing it buys nothing and costs a
    statistical standard. It also says the structural objection to the veto stands on its own
    merits (campaign PBO rises with generation volume, which contradicts the Two-Stage Discovery
    Law's "the confirmation bar never rises with generation") rather than on a promise of
    survivors it cannot keep.

    `independent_estimate` is included as the naive counterfactual for contrast: multiply the
    surviving gates' pass rates as if they were independent. On the real campaign it predicts
    ~9 survivors (0.581 x 0.479 x 0.433 x 0.433 x 0.402 = 2.1% of 420) where the true count is
    ZERO.

    THAT DIRECTION IS THE INFORMATIVE PART, and it is easy to get backwards. Observed BELOW the
    independent estimate means gate PASSES are negatively associated: a candidate that clears one
    gate tends to fail another. Which is what a well-designed battery should look like -- the
    gates are penalising genuinely different failure modes rather than re-measuring one latent
    "quality" score. (If they were positively associated, the good candidates would sweep every
    gate and survivors would EXCEED the independent estimate, which would mean the battery is
    largely one gate wearing five hats.) Across 420 candidates, not one was simultaneously
    profitable, walk-forward-stable, capacity-viable and tail-acceptable.

    Quoting the independent number as an expected yield would badly oversell any relaxation, so
    it is reported beside the true count, never instead of it.
    """
    if not gate_results:
        return {"n": 0, "waived": list(waive), "survivors": 0, "survivor_indices": [],
                "independent_estimate": 0.0, "note": "no candidates -- nothing to counterfact"}
    waived = set(waive)
    n = len(gate_results)
    survivors = [i for i, row in enumerate(gate_results)
                 if all(ok for g, ok in row.items() if g not in waived)]
    remaining = [g for g in gate_results[0] if g not in waived]
    est = 1.0
    for g in remaining:
        est *= sum(1 for r in gate_results if r.get(g)) / n
    return {
        "n": n, "waived": sorted(waived), "survivors": len(survivors),
        "survivor_indices": survivors[:20],
        "independent_estimate": round(est * n, 2),
        "note": ("waiving these gates promotes NOBODY -- every candidate also fails at least one "
                 "gate that genuinely discriminates, so the relaxation buys no survivors and "
                 "costs a statistical standard"
                 if not survivors else
                 f"{len(survivors)}/{n} would survive the waiver; this is a PROMOTION-BAR change "
                 f"and belongs to the principal, not to a screen"),
    }
