"""Estimation-error-shrunk Kelly -- the fraction that actually maximizes E[log wealth].

    shrink = S^2 / (S^2 + SE(S)^2)        (Bayesian shrinkage toward a zero-edge prior)
    fraction_of_kelly = shrink            (ramps continuously as evidence accumulates)

with SE from Lo (2002): SE(S_daily) = sqrt((1 + S_daily^2 / 2) / N), annualized. Pooling
shadow + live forward days grows N daily, so size compounds with evidence automatically:
no rungs, no calendar, nothing to skip. Reference behaviour (S_ann ~ 2.3): ~0.17x Kelly
at day 15, ~0.36x at 40, ~0.55x at 90, ~0.71x at 180. A day-40 fast-track (needs S ~ 5)
starts at ~0.73x -- strong evidence self-authorizes size, weak evidence cannot.

WHY THE SHRINK IS RIGHT -- CORRECTED 2026-08-13 (R0432). THE FORMULA IS UNCHANGED AND THIS
IS NOT AN ARGUMENT TO BET MORE. What changed is the reason attached to it, because the
reason that used to be here is measurably false and a false rationale calibrates a real
knob in the wrong direction.

THE RETIRED RATIONALE: "Kelly's penalty for overbetting is asymmetric, so betting naive
full Kelly on an ESTIMATED edge has lower expected compounding than the shrunk fraction."
Measured and refuted by `scripts/study_absorbing_kelly.py` CONTROL A, 12/12 cells: with an
unbiased mu, estimation noise ALONE leaves the growth optimum at exactly f* = 1.00. It is
not a simulation artifact -- E[log W_T] = T(L*mu - L^2 sigma^2 / 2) is LINEAR in mu, so
averaging over symmetric parameter noise about a correct mean cannot move the argmax at
all. The asymmetry is real but it already lives inside the quadratic term; it is not a
second effect that noise switches on.

THE RATIONALE THAT SURVIVES: S-hat is not unbiased for the quantity being bet on. Edges
reach this function BECAUSE they measured well, so the estimate carries a winner's curse
and the correct input is the POSTERIOR MEAN of the edge under a prior that most candidates
have none -- strictly below S-hat. S^2/(S^2 + SE^2) is exactly the James-Stein /
normal-posterior shrinkage factor toward a zero-edge prior, so the form was right for a
reason nobody had written down. The desk's prior is very strong: 420 screened, 0 survivors.

DECIDED, NOT DEFERRED: THE SCREEN'S TRIAL COUNT IS NOT FED IN, AND MUST NOT BE. R0432 asked
whether the 420-trial multiplicity count should tighten the shrink for heavily-selected
candidates. It should not, and the reason is a property of the INPUT rather than a judgement
about strength: this function is fed `fwd_sharpe` / `fwd_days` (dynamic_leverage.py:112) --
the pre-registered FORWARD clock, measured on data that took no part in the screen's
selection. Charging the screen's winner's curse against an estimate that did not undergo it
prices the same selection twice, which is the duplicated-multiplicity error this desk has
already paid for once in validation (turnover penalised twice because nobody checked whether
it was in the number). The two-stage discovery law is what makes this safe: the screen has
zero promotion authority, so its multiplicity is spent there and not carried forward.

WHAT IS GENUINELY UNPRICED, AND IS A DIFFERENT AND SMALLER QUANTITY: promotion selects on
FORWARD evidence, over at most MAX_FORWARD_SLOTS=12 concurrent slots. Holm corrects the
p-value of that decision; it does not de-bias the effect SIZE this function then sizes on,
so a candidate that just cleared the bar still has an upward-biased forward Sharpe. The
relevant selection intensity is best-of-12, not best-of-420. Whether S^2/(S^2+SE^2) already
absorbs it is an empirical question that needs its own study and is rowed separately --
NOT assumed either way here, and any change it produces can only be TIGHTER.
"""

from __future__ import annotations

import math

_PPY = 365.0


def sharpe_se(sharpe_ann: float, n_days: float, *, ppy: float = _PPY) -> float:
    """Lo (2002) standard error of the ANNUALIZED Sharpe estimated from n daily returns."""
    if n_days <= 1:
        return float("inf")
    s_daily = sharpe_ann / math.sqrt(ppy)
    se_daily = math.sqrt((1.0 + 0.5 * s_daily * s_daily) / n_days)
    return se_daily * math.sqrt(ppy)


def shrink_fraction(sharpe_ann: float, n_days: float, *, vif: float = 1.0,
                    ppy: float = _PPY) -> float:
    """Fraction of full Kelly that maximizes expected log growth under estimation error.

    0 when the edge is unproven (S <= 0 or < 5 effective days); -> 1 asymptotically as
    evidence accumulates. Monotone in S and N, anti-monotone in vif.

    ``vif``: variance-inflation factor for autocorrelated returns (round-2 external review,
    2026-07-12 — the SE must live on the SAME effective sample size as the NW t-stat, or the
    sizing over-trusts sticky returns exactly where the significance test distrusts them).
    Pass forward_stats.autocorr_factor(returns); effective N = N / vif.
    """
    n_eff = n_days / max(1.0, vif)
    if sharpe_ann <= 0.0 or n_eff < 5:
        return 0.0
    se = sharpe_se(sharpe_ann, n_eff, ppy=ppy)
    if not math.isfinite(se) or se <= 0.0:
        return 0.0
    s2 = sharpe_ann * sharpe_ann
    return round(s2 / (s2 + se * se), 4)


def shrunk_kelly(kelly: float, sharpe_ann: float, n_days: float,
                 *, vif: float = 1.0, floor: float = 0.0, ppy: float = _PPY) -> float:
    """The deployable Kelly multiple: shrink * kelly, floored at an operational minimum."""
    return max(floor, shrink_fraction(sharpe_ann, n_days, vif=vif, ppy=ppy) * max(0.0, kelly))


def first_inversion_cap(fraction: float, live_days: float,
                        inversion_survived: bool, nav: float = 0.0) -> float:
    """Carry-book live probation cap, DYNAMIC by scale (principal-adopted 2026-07-12;
    NAV-scaling added same day on round-2/3 reviewer consensus that the trade is
    scale-dependent -- marginal insurance at $5k, clearly correct at $500k): until the LIVE
    book has survived one funding-inversion episode -- >=1 day of negative aggregate realized
    funding (venue income truth) with episode drawdown <= 2x model expectation -- OR 60 live
    days have elapsed (whichever first), deploy at a NAV-scaled fraction of the authorized
    size: 0.75x below $25k (light drag where the insurance is nearly free anyway), 0.6x to
    $100k, 0.5x above. Self-expiring: zero effect from day 60 forever. Rationale: the single
    most common carry-desk death is meeting the first inversion at maximum size; this buys
    the first observation of the core adverse regime at a scale-appropriate discount."""
    if inversion_survived or live_days >= 60.0:
        return fraction
    probation = 0.75 if nav < 25_000 else 0.6 if nav < 100_000 else 0.5
    return probation * fraction
