"""Drawdown-aware performance metrics: ulcer index, Martin ratio, return-over-drawdown.

PROVENANCE. neurotrader's chart-pattern mining video supplies the Martin ratio as its objective
function; Kevin Davey's material supplies return-over-max-drawdown >= 2.0 as a system goal
(2026-08-01 batch). Both are numbers-and-method sources.

WHY THE DESK NEEDS A DRAWDOWN-AWARE STATISTIC AT ALL, and it is not a matter of taste. Sharpe
divides by the standard deviation of returns, which is symmetric: it charges an upside surprise
exactly as much as a downside one, and it cannot tell a strategy that lost 30% over three days
from one that lost 30% over eleven months. Those are completely different instruments to own.
This desk has now measured, from three independent directions, that DRAWDOWN is where its real
constraint sits:

    reports/live_book_concentration.json  the live book is worth 1.31 effective positions, so its
                                          drawdowns arrive all at once
    tests/stage14/test_survival_calibration  monte_carlo_survival's dd_limit=0.20 rejects 100% of
                                          the real-edge band at crypto volatility
    external 350,000-backtest BTC sweep   zero walk-forward survivors under a 40% drawdown cap;
                                          the best survivor ran 42% at OOS Sharpe 1.08

A ranking statistic that never looks at drawdown cannot express any of that. `grep -rn ulcer`
across this repo returned nothing before this module.

WHY ULCER RATHER THAN MAX DRAWDOWN. Max drawdown is a single order statistic -- one number from
one moment -- so it is enormously noisy and says nothing about how long the pain lasted. The ulcer
index is the root-mean-square of the drawdown series, so a long shallow trough and a brief deep
one score differently, which matches the thing that actually ends strategies: not the depth a
trader sees once, but the months spent underwater deciding whether to switch it off. Both are
reported here, because max drawdown is what Davey's >= 2.0 rule is written against and silently
substituting a different denominator would make that threshold mean something else.

NOT A GATE. Same rule as the rest of the 2026-08-01 work: the audit measured over-rejection as
this desk's failure mode, so this is a ranking and reporting statistic. Davey's 2.0 is recorded as
the source's calibration, not wired as a rejection.
"""

from __future__ import annotations

import numpy as np

#: Davey's stated system goal: at least $2 of return per $1 of drawdown. RECORDED, NOT ENFORCED.
MARTIN_TARGET_RETURN_OVER_DD = 2.0

_EPS = 1e-12


def drawdown_series(log_returns: np.ndarray) -> np.ndarray:
    """Fractional drawdown from the running peak, per bar. Always in [0, 1).

    Computed from LOG returns by exponentiating the cumulative sum, which is the only arithmetic
    that composes correctly: summing simple returns overstates compounding and would make deep
    drawdowns look shallower than they were.
    """
    r = np.asarray(log_returns, dtype="float64")
    r = r[np.isfinite(r)]
    if r.size == 0:
        return np.zeros(0)
    # THE EQUITY PATH IS ANCHORED AT 1.0 BEFORE THE FIRST RETURN, and this is not bookkeeping.
    # Without the anchor the running peak starts at the equity AFTER bar one, so a strategy that
    # loses on its very first bar reports zero drawdown -- the loss becomes the peak it is
    # measured against. Caught by test_log_returns_compose_so_deep_drawdowns_are_not_understated,
    # where a 100 -> 50 move read as 0.0.
    equity = np.concatenate([[1.0], np.exp(np.cumsum(r))])
    peak = np.maximum.accumulate(equity)
    dd: np.ndarray = 1.0 - equity / peak
    return dd[1:]                       # one drawdown per RETURN bar, peak-anchored at the start


def ulcer_index(log_returns: np.ndarray) -> float:
    """Root-mean-square drawdown. Penalises DEPTH and DURATION together.

    A strategy 5% underwater for two years and one 40% underwater for a week can share a Sharpe
    and share nothing else. This separates them, and it is the denominator of the Martin ratio.
    """
    dd = drawdown_series(log_returns)
    if dd.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(dd ** 2)))


def martin_ratio(log_returns: np.ndarray) -> float:
    """Total log return divided by the ulcer index.

    SIGN IS PRESERVED RATHER THAN FLIPPED. The source's implementation negates the ratio for
    losing series so that "best short pattern" is the minimum -- correct for a pattern SEARCH that
    wants both tails, and wrong as a general statistic, because it makes a bad strategy and a good
    short-side strategy indistinguishable from the number alone. Here a losing series returns a
    negative Martin ratio and means exactly that. A caller mining for short patterns can negate it
    themselves, deliberately.

    NaN WHEN THERE IS NO DRAWDOWN. A series that never drew down has an ulcer index of zero, and
    dividing by it would report infinite risk-adjusted return -- which on any real sample means the
    window was too short to contain a loss, not that the strategy cannot lose.
    """
    r = np.asarray(log_returns, dtype="float64")
    r = r[np.isfinite(r)]
    if r.size < 2:
        return float("nan")
    ui = ulcer_index(r)
    if not np.isfinite(ui) or ui <= _EPS:
        return float("nan")
    return float(np.sum(r) / ui)


def return_over_max_drawdown(log_returns: np.ndarray) -> float:
    """Total log return over peak-to-trough drawdown. The form Davey's >= 2.0 target is written
    against, kept as its own function so the threshold is compared to the statistic it was set
    for rather than to a similar-looking one."""
    r = np.asarray(log_returns, dtype="float64")
    r = r[np.isfinite(r)]
    if r.size < 2:
        return float("nan")
    mdd = float(np.max(drawdown_series(r), initial=0.0))
    if mdd <= _EPS:
        return float("nan")
    return float(np.sum(r) / mdd)


def report(log_returns: np.ndarray) -> dict[str, object]:
    """Every drawdown statistic at once, plus what the source thresholds say about them."""
    r = np.asarray(log_returns, dtype="float64")
    r = r[np.isfinite(r)]
    dd = drawdown_series(r)
    rmdd = return_over_max_drawdown(r)
    mdd = float(np.max(dd, initial=0.0)) if dd.size else float("nan")
    # Longest run of consecutive bars underwater -- the quantity a trader actually experiences,
    # and the one max drawdown is completely silent about.
    underwater = dd > _EPS
    longest = 0
    run = 0
    for u in underwater:
        run = run + 1 if u else 0
        longest = max(longest, run)
    return {
        "n_bars": int(r.size),
        "total_log_return": float(np.sum(r)) if r.size else float("nan"),
        "max_drawdown": mdd,
        "ulcer_index": ulcer_index(r),
        "martin_ratio": martin_ratio(r),
        "return_over_max_drawdown": rmdd,
        "longest_underwater_bars": int(longest),
        "clears_davey_target": (bool(rmdd >= MARTIN_TARGET_RETURN_OVER_DD)
                                if np.isfinite(rmdd) else None),
        "target": MARTIN_TARGET_RETURN_OVER_DD,
        "note": ("return_over_max_drawdown is the statistic Davey's 2.0 target was set against. "
                 "ulcer_index/martin_ratio additionally price how LONG the drawdown lasted, which "
                 "max drawdown cannot see. Recorded as calibration, not wired as a gate."),
    }
