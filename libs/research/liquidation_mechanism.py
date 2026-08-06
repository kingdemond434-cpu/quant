"""IS THE REVERSION FORCED FLOW, OR IS IT SUPPLY? -- the mechanism, measured before any pattern.

THE HYPOTHESIS IS NOT A CHART SHAPE. It is a claim about WHO is selling: that when price sweeps a
level carrying dense liquidation exposure and fails, the reversion happens because forced-
liquidation flow EXHAUSTS, not because discretionary sellers arrive and then stop. Those two
produce the same candle and completely different expectations, and only one of them is a mechanism
you can size against.

They are separable, which is the whole reason to measure first and mine second:

    forced-liquidation exhaustion          discretionary supply
    OI COLLAPSES across the sweep          OI flat or rising -- new sellers took new positions
    trade-size right tail spikes, STOPS    tail persists after the sweep
    funding extreme and one-sided going in unremarkable
    liquidation prints cluster, then cease absent or diffuse

WHY THIS MODULE EXISTS SEPARATELY FROM THE PATTERN. If mechanism evidence is absent, an edge found
by the pattern search is an UNEXPLAINED EMPIRICAL REGULARITY. It may still be real and it may still
be tradeable, but it is not this hypothesis, and promoting it on this hypothesis's ticket would be
claiming to know why something works when the measurement said otherwise. Kill criterion K7 in the
pre-registration exists precisely to force that distinction rather than let it blur.

EVERY MEASUREMENT HERE IS CAUSAL. A value at bar t uses only bars <= t. The OI-collapse statistic
compares a window ENDING at the sweep against a window ending before it -- never a window that
extends past the bar being judged, which would be the flattering error and would be invisible in
the output.

Pure numpy/pandas. No I/O, no network. Nothing here fetches data; a caller supplies it or the
study reports that it could not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

__all__ = [
    "MechanismEvidence",
    "cohens_d",
    "funding_extremity",
    "liquidation_burst",
    "mechanism_evidence",
    "oi_collapse",
]

#: |d| below which the pre-registration calls the mechanism ABSENT (kill criterion K7). Not a
#: tuning knob: it is written into docs/research/FAILED_BREAKOUT_PREREGISTRATION.md and changing
#: it here without changing that document is how a pre-registration stops binding.
K7_EFFECT_FLOOR = 0.2


@dataclass(frozen=True)
class MechanismEvidence:
    """What was measured, with the verdict SEPARATE from the numbers that produced it."""

    n_swept: int
    n_control: int
    oi_collapse_d: float = float("nan")
    funding_extremity_d: float = float("nan")
    liquidation_burst_d: float = float("nan")
    measurable: tuple[str, ...] = field(default=())
    unmeasurable: tuple[str, ...] = field(default=())
    verdict: str = "UNKNOWN"
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_swept": self.n_swept, "n_control": self.n_control,
            "oi_collapse_d": self.oi_collapse_d,
            "funding_extremity_d": self.funding_extremity_d,
            "liquidation_burst_d": self.liquidation_burst_d,
            "measurable": list(self.measurable), "unmeasurable": list(self.unmeasurable),
            "verdict": self.verdict, "why": self.why,
        }


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Standardised difference in means, pooled SD. NaN when either side is too small to speak.

    EFFECT SIZE RATHER THAN A p-VALUE, DELIBERATELY. With enough bars any difference is
    "significant"; the question K7 asks is whether the difference is LARGE, because a mechanism
    that moves OI by a tenth of a standard deviation is not what drives a reversion.
    """
    a = np.asarray(a, dtype="float64")
    b = np.asarray(b, dtype="float64")
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if a.size < 5 or b.size < 5:
        return float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((a.size - 1) * va + (b.size - 1) * vb) / max(a.size + b.size - 2, 1))
    if not np.isfinite(pooled) or pooled <= 0:
        return float("nan")
    return float((a.mean() - b.mean()) / pooled)


def oi_collapse(oi: pd.Series, idx: np.ndarray, *, pre: int = 12, post: int = 3) -> np.ndarray:
    """Fractional change in open interest ACROSS each event, as a signed fraction of pre-level.

    THE PRIMARY DISCRIMINATOR. Forced liquidation CLOSES positions, so OI falls. Discretionary
    supply OPENS them, so OI holds or rises. Same candle, opposite sign here.

    `pre` bars ending at the event and `post` bars after it. The post-window is what makes this an
    event study rather than a feature -- it is measured for MECHANISM EVIDENCE only and must never
    be handed to a trading rule, because at signal time those bars have not happened. The study
    keeps them apart; this docstring is where that separation is stated.

    Returns NaN for events too close to either end of the series rather than truncating the
    window, which would silently compare a 12-bar change against a 3-bar one.
    """
    v = pd.to_numeric(oi, errors="coerce").to_numpy(dtype="float64")
    out = np.full(len(idx), np.nan)
    for k, i in enumerate(idx):
        if i - pre < 0 or i + post >= v.size:
            continue
        before = v[i - pre:i + 1]
        after = v[i + 1:i + 1 + post]
        b = np.nanmean(before)
        a = np.nanmean(after)
        if np.isfinite(b) and np.isfinite(a) and b > 0:
            out[k] = (a - b) / b
    return out


def funding_extremity(funding: pd.Series, idx: np.ndarray, *, lookback: int = 500) -> np.ndarray:
    """|z| of the funding rate at each event against its own TRAILING distribution.

    Crowded one-way positioning is the precondition the hypothesis needs: without it there is no
    dense liquidation exposure for a sweep to trigger. Standardised against bars strictly BEFORE
    the event, because a full-sample z-score would let the event's own regime set its baseline --
    the leak that made `book_pressure_vs_funding` lie until it was found on 2026-08-03.
    """
    v = pd.to_numeric(funding, errors="coerce").to_numpy(dtype="float64")
    out = np.full(len(idx), np.nan)
    for k, i in enumerate(idx):
        lo = max(0, i - lookback)
        hist = v[lo:i]                       # strictly prior -- the event never sets its own bar
        hist = hist[np.isfinite(hist)]
        if hist.size < 30 or not np.isfinite(v[i]):
            continue
        sd = hist.std(ddof=1)
        if sd > 0:
            out[k] = abs((v[i] - hist.mean()) / sd)
    return out


def liquidation_burst(liq_notional: pd.Series, idx: np.ndarray, *,
                      window: int = 3, lookback: int = 500) -> np.ndarray:
    """Liquidation notional in the event window, as a multiple of its trailing median.

    The most direct evidence available when the venue publishes it -- and the one most often
    missing, which is why the caller must be able to distinguish "measured and small" from "not
    measured". A NaN here means the venue published nothing; it never means zero liquidations.
    """
    v = pd.to_numeric(liq_notional, errors="coerce").to_numpy(dtype="float64")
    out = np.full(len(idx), np.nan)
    for k, i in enumerate(idx):
        lo = max(0, i - lookback)
        hist = v[lo:i]
        hist = hist[np.isfinite(hist)]
        hi = min(v.size, i + window + 1)
        cur = v[i:hi]
        cur = cur[np.isfinite(cur)]
        if hist.size < 30 or cur.size == 0:
            continue
        med = float(np.median(hist))
        if med > 0:
            # THE DENOMINATOR MUST COUNT THE BARS ACTUALLY SUMMED. `cur` spans i .. i+window
            # INCLUSIVE -- window+1 bars, because the event bar itself belongs in the burst -- and
            # the first version divided by `med * window`. So a perfectly quiet window scored
            # 1.333 instead of 1.0 at window=3, and EVERY burst multiple was inflated by
            # (window+1)/window. That is a 33% overstatement in the flattering direction, applied
            # uniformly, which is exactly the kind of bias no downstream check can see: the
            # ordering of events is untouched, so only the absolute multiple is wrong and it is
            # wrong everywhere at once.
            #
            # `cur.size` rather than `window + 1`, because the slice is truncated at the end of
            # the series -- dividing a 2-bar sum by 4 would understate a burst on the last bars.
            out[k] = float(cur.sum()) / (med * max(cur.size, 1))
    return out


def mechanism_evidence(swept: np.ndarray, control: np.ndarray, *,
                       oi: pd.Series | None = None,
                       funding: pd.Series | None = None,
                       liq: pd.Series | None = None) -> MechanismEvidence:
    """Compare swept levels against UNSWEPT ones on every channel the data supports.

    THE CONTROL GROUP IS THE POINT AND IT IS EASY TO GET WRONG. The comparison is not
    "before vs after a sweep" -- OI drifts, funding trends, and a before/after split would confirm
    the hypothesis on any series with a trend in it. It is SWEPT LEVELS vs LEVELS THAT WERE NOT
    SWEPT, which holds the "there was a level here" condition fixed and varies only the sweep.

    THE CALLER OWES ONE THING THIS FUNCTION CANNOT ENFORCE: the two arms must be INTERLEAVED IN
    TIME, not drawn from different stretches of the series. `oi_collapse` reports a FRACTIONAL
    change, so on a trending series the same absolute move is a larger fraction wherever the level
    is lower -- and if every swept event sits early and every control late, a pure monotone trend
    with no sweeps at all produces |d| = 0.28 and a CONTRADICTED verdict. Measured, not feared:
    swept=bars 50-150 and control=bars 200-300 on a straight line from 1000 to 500 gives arm means
    of -0.0114 and -0.0145.
    That is the before/after failure returning through the sampling rather than through the
    windows, and it is invisible here because both arms are validly "levels". `run_failed_breakout
    _study` draws its control from the whole index for exactly this reason; any other caller must
    do the same or the verdict is a fact about the trend.

    A channel with no data is reported UNMEASURABLE, never as an effect of zero. Those are
    different findings: one says the mechanism is absent, the other says nobody looked, and the
    pre-registration's K7 fires only on the first.
    """
    measurable: list[str] = []
    unmeasurable: list[str] = []
    ds: dict[str, float] = {}

    for name, series, fn in (("oi_collapse", oi, oi_collapse),
                             ("funding_extremity", funding, funding_extremity),
                             ("liquidation_burst", liq, liquidation_burst)):
        if series is None or len(series) == 0 or not np.isfinite(
                pd.to_numeric(series, errors="coerce").to_numpy(dtype="float64")).any():
            unmeasurable.append(name)
            ds[name] = float("nan")
            continue
        d = cohens_d(fn(series, swept), fn(series, control))
        ds[name] = d
        (measurable if np.isfinite(d) else unmeasurable).append(name)

    if "oi_collapse" in unmeasurable:
        verdict, why = "UNMEASURABLE", (
            "open interest is the PRIMARY discriminator between forced and discretionary flow and "
            "it is not available. Without it the two hypotheses are observationally identical on "
            "this data, so any edge found downstream is an UNEXPLAINED regularity rather than "
            "evidence for this mechanism. Pre-registration K7 cannot be evaluated.")
    elif abs(ds["oi_collapse"]) < K7_EFFECT_FLOOR:
        verdict, why = "ABSENT", (
            f"OI change on swept levels differs from unswept by d={ds['oi_collapse']:+.3f}, inside "
            f"the {K7_EFFECT_FLOOR} floor. Positions are not being closed across the sweep in any "
            "size that could drive a reversion. K7 FIRES: whatever the pattern search finds, it is "
            "not this mechanism.")
    elif ds["oi_collapse"] < 0:
        verdict, why = "PRESENT", (
            f"OI FALLS across swept levels relative to unswept (d={ds['oi_collapse']:+.3f}) -- the "
            "signature of positions being closed involuntarily rather than new supply arriving.")
    else:
        verdict, why = "CONTRADICTED", (
            f"OI RISES across swept levels (d={ds['oi_collapse']:+.3f}). That is the discretionary-"
            "supply signature, the OPPOSITE of the hypothesis: participants are opening positions "
            "into the sweep, not being closed out of them. A pattern edge here would be a "
            "different mechanism than the one pre-registered.")

    return MechanismEvidence(
        n_swept=len(swept), n_control=len(control),
        oi_collapse_d=ds["oi_collapse"], funding_extremity_d=ds["funding_extremity"],
        liquidation_burst_d=ds["liquidation_burst"],
        measurable=tuple(measurable), unmeasurable=tuple(unmeasurable),
        verdict=verdict, why=why)
