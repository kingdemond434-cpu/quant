"""THE MONKEY TEST, and the exact split of return into exposure and timing.

PROVENANCE. Kevin Davey's strategy-factory material (2026-08-01 batch) and, for the partition,
Timothy Masters via the "four tests" transcript in the same batch. Adopted because both are
NUMBERS-AND-METHOD sources, the category that converts 4/4 on this desk against 0/13 for spoken
mechanisms, and because between them they answer a question the desk's whole gauntlet does not
ask.

WHY THIS IS NOT THE PERMUTATION TEST AGAIN. `libs/validation/bar_permutation` shuffles the DATA
and keeps the rule: "is there information in the ORDER of the bars?" This shuffles the RULE and
keeps the data: "is this rule better than a coin flip that was in the market just as much?" They
fail differently and the desk needs both:

    a rule that is simply long 80% of the time in a bull market
        permutation test  -> p high, because permuting preserves the drift exactly
        monkey test       -> beaten by random 80%-long monkeys, for the same underlying reason
    a rule with genuine timing on a flat market
        permutation test  -> p low
        monkey test       -> beats the monkeys

EXPOSURE MATCHING IS THE WHOLE DESIGN, and without it the test is worthless. Davey's monkey trades
on 47% of days with a 40/60 long/short split -- fixed numbers, which is right for his setup and
wrong here. A monkey that is long 50% of the time cannot say anything useful about a rule that is
long 85% of the time on an asset that tripled: the rule wins on EXPOSURE and the comparison
silently credits it as skill. Each baseline here is drawn to match the real rule's time-in-market
AND its long/short balance, so the only thing left to differ is WHEN.

THE PARTITION IS EXACT, not an approximation, and that is why it is worth having. Strategy return
per bar is ``mean(position * market_return)``, and by the definition of covariance:

    mean(p*r)  ==  mean(p) * mean(r)   +   cov(p, r)
    total      ==  EXPOSURE (drift you get for being there)  +  TIMING (drift you get for being
                                                                 there at the right moments)

No estimation, no simulation, no assumption -- an identity. A rule whose total is 90% exposure is
a leveraged buy-and-hold wearing a strategy's clothes, and the desk's live book has already been
measured as worth 1.31 effective positions, so it does not need another way to own the market
factor. Davey's own championship year makes the same point from the other end: one copper trade
was 95% of the profit.

WHAT IS DELIBERATELY NOT ADOPTED. Davey's beat-the-monkey-90%-of-the-time is a GO/NO-GO gate in
his process. It is not wired as a gate here. The 2026-08-01 audit measured this desk's failure
mode as over-rejection -- the admission floor alone was blocking everything at 4.78 annualised --
and `libs/validation/robustness_filters` records the rule that follows: adding rejection is the
last thing this gauntlet needs. These are reported as diagnostics and ranking inputs.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

#: Davey's threshold for a strategy to have demonstrated an edge over randomness. Recorded as the
#: source's calibration, used for REPORTING rather than as a gate -- see the module docstring.
BEAT_RATE_TARGET = 0.90

#: Below this many baseline draws the beat-rate cannot resolve the 0.90 target: at 50 draws the
#: resolution is 0.02 and the sampling error on a rate near 0.9 is ~0.04, so the number would be
#: reported to a precision it does not have.
MIN_BASELINES = 200

_EPS = 1e-12


def partition_return(positions: np.ndarray, market_returns: np.ndarray) -> dict[str, float]:
    """Split per-bar strategy return into EXPOSURE and TIMING. An identity, not an estimate.

        mean(p*r) == mean(p)*mean(r) + cov(p, r)

    ``exposure`` is what a position-blind version of this rule would have earned by being in the
    market the same fraction of the time; ``timing`` is everything the rule earned by choosing
    WHEN. A high exposure share is not automatically bad -- harvesting a risk premium is a real
    mechanism and the desk declares one (`persistent_long`) -- but it must be NAMED, because a
    rule sold as timing and delivering exposure is a leveraged buy-and-hold and is priced,
    hedged and sized completely differently.

    Positions are lagged by the CALLER. This function does not know whether `positions[i]` was
    knowable at bar i, and silently lagging here would hide a look-ahead bug rather than expose it.
    """
    p = np.asarray(positions, dtype="float64")
    r = np.asarray(market_returns, dtype="float64")
    if len(p) != len(r):
        raise ValueError(f"positions ({len(p)}) and returns ({len(r)}) must be the same length")
    ok = np.isfinite(p) & np.isfinite(r)
    if ok.sum() < 3:
        raise ValueError("need at least 3 finite aligned observations")
    p, r = p[ok], r[ok]

    total = float(np.mean(p * r))
    exposure = float(np.mean(p) * np.mean(r))
    timing = float(np.mean((p - np.mean(p)) * (r - np.mean(r))))
    denom = abs(total)
    return {
        "total_per_bar": total,
        "exposure_per_bar": exposure,
        "timing_per_bar": timing,
        # Shares are UNDEFINED, not zero, when the total is ~0: dividing a real component by a
        # cancelling total produces enormous meaningless percentages.
        "exposure_share": (exposure / total) if denom > _EPS else float("nan"),
        "timing_share": (timing / total) if denom > _EPS else float("nan"),
        "mean_position": float(np.mean(p)),
        "time_in_market": float(np.mean(p != 0.0)),
        "identity_residual": float(total - exposure - timing),
    }


def matched_random_positions(
    positions: np.ndarray, *, rng: np.random.Generator
) -> np.ndarray:
    """A monkey with the SAME exposure as the real rule -- same long count, same short count.

    Built by PERMUTING the real position series rather than drawing fresh Bernoulli values. That
    matches time-in-market and long/short balance EXACTLY rather than in expectation, which
    matters at the sample sizes the desk actually runs: a Bernoulli monkey drawn at p=0.85 over
    2,400 bars still varies by a couple of percent of exposure, and on an asset that tripled that
    slack is worth more than most of the timing effects under test. Permuting removes it entirely,
    so the comparison isolates WHEN and nothing else.
    """
    p = np.asarray(positions, dtype="float64")
    return p[rng.permutation(len(p))]


def monkey_test(
    positions: np.ndarray,
    market_returns: np.ndarray,
    *,
    rng: np.random.Generator,
    n_baselines: int = 1_000,
    statistic: Callable[[np.ndarray], float] | None = None,
) -> dict[str, object]:
    """How often does the real rule beat an exposure-matched monkey?

    RETURNS A BEAT RATE AND A P-VALUE THAT ARE THE SAME NUMBER SEEN TWICE, deliberately. The beat
    rate is Davey's framing ("did it beat the monkey 90% of the time"); the p-value is the
    statistician's, ``(#{monkey >= real} + 1) / (N + 1)``, with the +1 that stops it ever being
    zero. Reporting both means neither reader has to translate, and the identity between them is
    asserted in the tests so they cannot drift apart.

    ``statistic`` defaults to per-bar Sharpe. Any callable of the strategy return series works --
    profit factor, total return -- but note that a statistic which ignores volatility (total
    return, say) makes the exposure matching do ALL the work, and on a trending asset most
    exposure-matched monkeys will then score close to the real rule by construction.
    """
    stat = statistic if statistic is not None else _sharpe
    p = np.asarray(positions, dtype="float64")
    r = np.asarray(market_returns, dtype="float64")
    if len(p) != len(r):
        raise ValueError(f"positions ({len(p)}) and returns ({len(r)}) must be the same length")
    if n_baselines < MIN_BASELINES:
        raise ValueError(
            f"{n_baselines} baselines is below MIN_BASELINES={MIN_BASELINES}: the beat rate "
            f"cannot resolve the {BEAT_RATE_TARGET:.0%} target at that draw count")

    real = float(stat(p * r))
    draws = np.array([stat(matched_random_positions(p, rng=rng) * r)
                      for _ in range(n_baselines)], dtype="float64")
    usable = draws[np.isfinite(draws)]
    if usable.size < MIN_BASELINES // 2:
        return {"unmeasurable": f"only {usable.size} usable baselines", "beat_rate": None,
                "p_value": None, "real_statistic": real if np.isfinite(real) else None}

    beat = float(np.mean(usable < real)) if np.isfinite(real) else 0.0
    pval = float((np.sum(usable >= real) + 1) / (usable.size + 1)) if np.isfinite(real) else 1.0
    return {
        "real_statistic": float(real) if np.isfinite(real) else None,
        "n_baselines": int(usable.size),
        "beat_rate": beat,
        "p_value": pval,
        "baseline_median": float(np.median(usable)),
        "baseline_p95": float(np.percentile(usable, 95)),
        "clears_target": bool(beat >= BEAT_RATE_TARGET),
        "target": BEAT_RATE_TARGET,
        "reading": _read(beat, np.isfinite(real)),
    }


def _sharpe(returns: np.ndarray) -> float:
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    if r.size < 30:
        return float("nan")
    sd = float(np.std(r, ddof=1))
    return float("nan") if sd <= _EPS else float(np.mean(r) / sd)


def _read(beat: float, real_ok: bool) -> str:
    if not real_ok:
        return ("UNMEASURABLE: the real rule produced no usable statistic, so nothing here is "
                "interpretable.")
    if beat >= BEAT_RATE_TARGET:
        return (f"BEATS RANDOM: {beat:.1%} of exposure-matched monkeys did worse. The rule's edge "
                "is in WHEN it is positioned, not in how often -- an equally-exposed coin flip "
                "does not reproduce it.")
    if beat >= 0.5:
        return (f"WEAK: only {beat:.1%} of exposure-matched monkeys did worse (target "
                f"{BEAT_RATE_TARGET:.0%}). The rule is ahead of a coin flip but not by enough to "
                "distinguish timing skill from the luck of one draw.")
    return (f"NO TIMING EDGE: {beat:.1%} of exposure-matched monkeys did worse -- a coin flip "
            "with the same time-in-market does as well or better. Whatever this rule earns comes "
            "from BEING in the market, not from choosing when.")
