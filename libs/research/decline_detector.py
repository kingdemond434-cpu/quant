"""DECLINE DETECTION -- turn a price series into the events the rebound book can classify.

THE MISSING HALF OF THE DIP-BUYING STRATEGY, and it is worth being precise about which half.

`libs/research/drawdown_rebound.py` already answers the question that matters: it classifies WHY a
decline happened (forced deleveraging vs repricing vs liquidity withdrawal ...) and estimates the
rebound distribution conditional on that mechanism, refusing to estimate anything for an event it
could not classify. It is the good half and it is untouched here.

What did not exist is anything that FEEDS it. `run_opportunity_books` imports its `summarise` and
reports UNMEASURED, because nothing ever built a `DeclineEvent` from market data. So the desk owned
a dip-buying brain with no eyes: a classifier that had never seen a decline, an estimator with no
history to estimate from, and consequently a `REBOUND_TIMING` return engine with zero
implementation behind it.

This module is the eyes. It detects declines, assembles the observable state each one carries, and
scores what happened next -- and it emits a per-bar SIGNAL the canonical Stage-A screen can judge,
rather than a verdict of its own.

**IT DECIDES NOTHING.** No sizing, no entry, no promotion. `stage_a_screen` rules on the signal and
`run_axis_shadows` runs the forward clock, exactly as for every other candidate. A dip strategy
that graded its own homework would be the one place on this desk where a story about buying crashes
could reach capital without passing the gauntlet -- and buying crashes is precisely the family where
a rule is right often enough to keep running and wrong exactly when the losses are large.

**NO LOOK-AHEAD, ENFORCED BY CONSTRUCTION AND BY TEST.** The signal at bar *i* is built only from
bars <= *i*: an event contributes to the signal at the bar where its low is CONFIRMED, never at the
bar where the decline began. The confirmation rule is `lookback` bars without a new low, so the
earliest a signal can appear is `lookback` bars after the trough -- the price is already off its
low and the strategy is buying the rebound it can see, not the one it would need a time machine to
catch. `tests/research/test_decline_detector.py::test_NO_SIGNAL_USES_A_FUTURE_BAR` shifts the
series and asserts the signal shifts with it.

**UNMEASURED INPUTS STAY UNMEASURED.** Open interest, funding, liquidations and cross-venue prices
are optional: a desk with only OHLCV can still detect a decline, but `classify` will refuse to name
a mechanism without positive evidence and return MIXED_UNKNOWN -- and this module emits NO SIGNAL
for MIXED_UNKNOWN. That is the whole safety property. A dip detector that fired on depth alone is
the rule the rebound book exists to forbid, and the honest consequence is that on OHLCV-only data
this strategy trades rarely or never. Rarely is a measurement; often would be a fabrication.

Stdlib + numpy. import from libs.research.decline_detector.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from libs.research.drawdown_rebound import DeclineEvent, classify

__all__ = [
    "MIN_DEPTH",
    "REBOUND_FAVOURABLE",
    "DetectedDecline",
    "conditional_history",
    "detect_declines",
    "rebound_signal",
]

#: A fall shallower than this is noise on a crypto perp, not an event. Deliberately a FLOOR rather
#: than a tuned parameter: raising it later is a tightening, and the screen's own power gate is
#: what decides whether the resulting sample is large enough to rule on.
MIN_DEPTH = 0.08

#: Mechanisms whose forward distribution the book treats as potentially rebound-favourable. The
#: SET is the strategy's entire directional claim, so it is written once, here, rather than being
#: implied by a threshold somewhere downstream.
#:
#: EXOGENOUS_NEWS_SHOCK IS DELIBERATELY ABSENT and it is the most important omission in this file:
#: informed selling has no reason to exhaust at a particular price, so the "discount" is the
#: market's new estimate of value rather than an overshoot. A rule that cannot tell a cascade from
#: a repricing will buy both, and the repricings are where the large losses live.
#:
#: SYSTEMIC_RISK_OFF is absent for a different reason: it may well rebound, but a systemic event is
#: exactly when every other position in the book is also down, so the marginal E[log W] of adding
#: correlated long exposure there is not the same as the standalone expectancy (L1.58).
REBOUND_FAVOURABLE = frozenset({
    "ENDOGENOUS_LEVERAGE_BUILDUP",
    "LIQUIDITY_WITHDRAWAL",
    "CROSS_VENUE_DISLOCATION",
})


@dataclass(frozen=True)
class DetectedDecline:
    """One detected decline, its classification, and WHERE it may be acted on.

    `confirm_idx` is the index at which the trough is CONFIRMED and is the only bar at which this
    event may contribute to a signal. `low_idx` is kept for diagnostics and must never be used as
    an entry: it is knowable only in hindsight.
    """

    event: DeclineEvent
    mechanism: str
    why: str
    start_idx: int
    low_idx: int
    confirm_idx: int


def _rolling_peak(close: np.ndarray, window: int) -> np.ndarray:
    """Running maximum over the trailing `window` bars, inclusive of the current bar."""
    out = np.empty_like(close)
    for i in range(close.size):
        lo = max(0, i - window + 1)
        out[i] = close[lo:i + 1].max()
    return out


def detect_declines(
    close: np.ndarray,
    *,
    peak_window: int = 30,
    lookback: int = 3,
    min_depth: float = MIN_DEPTH,
    symbol: str = "",
    oi_cleared: np.ndarray | None = None,
    funding: np.ndarray | None = None,
    liquidation_notional: np.ndarray | None = None,
    spread_multiple: np.ndarray | None = None,
    volume_multiple: np.ndarray | None = None,
    cross_venue_divergence: np.ndarray | None = None,
    breadth_down: np.ndarray | None = None,
    news_event: np.ndarray | None = None,
    forced_flow_verdict: str = "",
) -> list[DetectedDecline]:
    """Find declines and classify each through the rebound book.

    Every optional array is per-bar and is read AT THE TROUGH, which is where the state that
    separates a cascade from a repricing is actually observable: OI is cleared during the fall,
    funding was extreme before it, the spread blew out into it. Passing None leaves that field at
    its UNMEASURED default and the classifier will decline to name a mechanism without it.
    """
    close = np.asarray(close, dtype="float64")
    if close.size < peak_window + lookback + 2:
        return []
    peak = _rolling_peak(close, peak_window)
    drawdown = np.where(peak > 0, 1.0 - close / peak, 0.0)

    def _at(arr: np.ndarray | None, i: int, default: float) -> float:
        if arr is None:
            return default
        a = np.asarray(arr, dtype="float64")
        return float(a[i]) if i < a.size and np.isfinite(a[i]) else default

    out: list[DetectedDecline] = []
    i = peak_window
    while i < close.size - lookback:
        if drawdown[i] < min_depth:
            i += 1
            continue
        # Walk to the trough of THIS episode, then require `lookback` bars with no new low before
        # calling it confirmed. That wait is what makes the entry knowable in real time.
        low_idx = i
        j = i
        while j < close.size and (j - low_idx) <= lookback:
            if close[j] < close[low_idx]:
                low_idx = j
            j += 1
        confirm_idx = low_idx + lookback
        if confirm_idx >= close.size:
            break
        start_idx = int(np.argmax(close[max(0, low_idx - peak_window):low_idx + 1])
                        + max(0, low_idx - peak_window))
        ev = DeclineEvent(
            event_id=f"{symbol or 'sym'}:{start_idx}:{low_idx}",
            symbol=symbol,
            depth=float(drawdown[low_idx]),
            duration_minutes=float(max(1, low_idx - start_idx)),
            oi_cleared_fraction=_at(oi_cleared, low_idx, 0.0),
            liquidation_notional=_at(liquidation_notional, low_idx, 0.0),
            funding_before=_at(funding, start_idx, 0.0),
            spread_multiple=_at(spread_multiple, low_idx, 1.0),
            volume_multiple=_at(volume_multiple, low_idx, 1.0),
            cross_venue_divergence=_at(cross_venue_divergence, low_idx, 0.0),
            breadth_down=_at(breadth_down, low_idx, 0.0),
            news_event=bool(_at(news_event, low_idx, 0.0)),
            forced_flow_verdict=forced_flow_verdict,
        )
        mech, why = classify(ev)
        out.append(DetectedDecline(event=ev, mechanism=mech, why=why, start_idx=start_idx,
                                   low_idx=low_idx, confirm_idx=confirm_idx))
        # Resume PAST the confirmation so one long bear leg cannot emit an event every bar.
        i = confirm_idx + 1
    return out


def rebound_signal(n_bars: int, declines: list[DetectedDecline], *,
                   favourable: frozenset[str] = REBOUND_FAVOURABLE) -> np.ndarray:
    """Per-bar signal in {0, 1}: 1 at the confirmation bar of a rebound-favourable decline.

    ZERO IS A REAL ANSWER HERE, not a missing one. Most bars carry no event and most events are
    not classifiable, so the honest signal is sparse -- and `stage_a_screen`'s power gate is what
    decides whether the resulting sample can support a verdict, rather than this module widening
    the rule until the sample looks comfortable.
    """
    sig = np.zeros(int(n_bars), dtype="float64")
    for d in declines:
        if d.mechanism in favourable and 0 <= d.confirm_idx < sig.size:
            sig[d.confirm_idx] = 1.0
    return sig


def conditional_history(
    declines: list[DetectedDecline],
    close: np.ndarray,
    *,
    horizon: int = 24,
) -> dict[str, list[tuple[float, float, float]]]:
    """Realised (bounce, max_adverse, recovery_bars) per mechanism -- the input `rebound_estimate`
    needs and never had.

    Measured from the CONFIRMATION bar, not the low, because that is the only price the strategy
    could have transacted at. Measuring from the low would flatter every number by exactly the
    part of the move that is unreachable.
    """
    close = np.asarray(close, dtype="float64")
    hist: dict[str, list[tuple[float, float, float]]] = {}
    for d in declines:
        a = d.confirm_idx
        b = min(close.size, a + horizon + 1)
        if a >= close.size - 1 or b - a < 2:
            continue
        entry = close[a]
        if entry <= 0:
            continue
        path = close[a + 1:b]
        bounce = float(path.max() / entry - 1.0)
        adverse = float(path.min() / entry - 1.0)
        recovered = np.nonzero(path >= entry)[0]
        rec_bars = float(recovered[0] + 1) if recovered.size else float(b - a)
        hist.setdefault(d.mechanism, []).append((bounce, adverse, rec_bars))
    return hist


def summarise(declines: list[DetectedDecline]) -> dict[str, Any]:
    """Counts by mechanism plus how many are actionable. Reports the REFUSALS as first-class."""
    by: dict[str, int] = {}
    for d in declines:
        by[d.mechanism] = by.get(d.mechanism, 0) + 1
    actionable = sum(v for k, v in by.items() if k in REBOUND_FAVOURABLE)
    return {
        "n_declines": len(declines),
        "by_mechanism": dict(sorted(by.items())),
        "n_actionable": actionable,
        "n_refused": len(declines) - actionable,
        "note": ("A decline the classifier could not attribute is NOT tradeable here. The refused "
                 "count is the safety property working, not a coverage defect -- on OHLCV-only "
                 "data it is expected to be nearly all of them, because the state that separates "
                 "a cascade from a repricing (OI cleared, funding before, liquidations) is not "
                 "in a price series."),
    }


def with_forced_flow(d: DetectedDecline, verdict: str) -> DetectedDecline:
    """Re-classify one decline once `liquidation_mechanism` has ruled on it.

    Kept separate because that module is the strongest single input and is expensive: the detector
    runs over a whole series, the forced-flow verdict is worth computing only for the declines
    that survived the depth filter.
    """
    ev = replace(d.event, forced_flow_verdict=verdict)
    mech, why = classify(ev)
    return replace(d, event=ev, mechanism=mech, why=why)
