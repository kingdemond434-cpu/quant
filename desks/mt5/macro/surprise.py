"""SURPRISE AGAINST EXPECTATIONS -- and the sign taken from measurement, never from the sign of z.

THE ARITHMETIC IS THE EASY HALF.

    z = (actual - consensus) / sigma_historical_surprise

Three things it is NOT, each of which is a real mistake this desk could make. It is not
(actual - previous), which is the expected CHANGE and a different quantity -- `libs/regime/
event_state.py` already flags that the desk's calendar vintages carry `forecast` and `previous`
but no `actual`, so the standard surprise is not computable from them today. It is not
(actual - consensus) with no denominator, which makes a 0.1pp CPI miss and a 100k payrolls miss
the same size. And sigma is the standard deviation of THIS RELEASE'S OWN historical surprises,
not of the series -- a release that is always forecast within a whisker and one that is routinely
missed by half a point have very different surprise scales, and pooling them flatters the first
and buries the second.

THE HARD HALF, AND THE POINT OF THE MODULE. z SETS THE MAGNITUDE OF THE INFORMATION. IT DOES NOT
SET THE SIGN OF ANY ASSET'S RESPONSE.

The principal's own test: a hot CPI where real yields barely move and the dollar sells off must
NOT produce a mechanical short-gold. A rule that maps "CPI above consensus" to "gold down" is a
belief about the transmission channel, and the transmission channel is a thing that VARIES --
with the level of real rates, with whether the market reads the print as growth or as policy,
with positioning, with what else printed that morning. What matters is how the market is
interpreting the number, and that is an OBSERVATION.

So `interpret` takes the MEASURED cross-asset factor response and returns factor deltas whose
sign is the measured sign. `mechanical_z_sign` is carried alongside, explicitly labelled as not
used, purely so an auditor can see when the two disagreed -- and the disagreements are the
interesting rows in the ledger, because they are where a rules-based system would have been
wrong. That divergence case is pinned in `desks/mt5/tests/test_macro_surprise_and_priced.py`.

WHEN THE REACTION IS NOT YET MEASURABLE -- the first seconds, or an instrument the desk has no
fast series for -- `interpret` returns UNMEASURED and NO factor delta. It does not fall back to
the sign of z. A layer that falls back to a sign table under time pressure is a sign table.

CONDITIONERS SHRINK, THEY NEVER FLIP. Positioning, liquidity, regime and the pre-event move enter
as multiplicative shrinkage in [0, 1] on the magnitude. Extreme positioning in the direction the
event implies makes the response SMALLER (the trade is crowded), a degraded tape makes it
smaller (the desk cannot execute into it), a large pre-event move makes it smaller (some of it
already happened). None of them can turn a positive measured response negative, because a
conditioner that can flip a sign is a second model smuggled in as an adjustment.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from statistics import fmean, stdev
from typing import Any

from .schema import Status, SurpriseEstimate

#: Historical surprises required before a sigma is usable. Ten is a low bar in absolute terms and
#: a high one in practice: monthly releases take the better part of a year to reach it, which is
#: an honest statement of how long this layer takes to become useful for a given release.
MIN_SURPRISE_N = 10

__all__ = [
    "MIN_SURPRISE_N",
    "Interpretation",
    "interpret",
    "z_score",
]


def z_score(actual: float | None, consensus: float | None,
            history: Sequence[float], *, release_id: str = "") -> SurpriseEstimate:
    """z against the release's own historical surprise distribution.

    `history` is past (actual - consensus) values for THIS release. Thin history returns
    UNMEASURED with the count, never a z computed against a pooled or assumed sigma.
    """
    if actual is None or consensus is None:
        return SurpriseEstimate(
            None, None, len(history), Status.UNMEASURED, actual, consensus, release_id,
            note=("actual and/or consensus absent. The desk's calendar vintages carry forecast "
                  "and previous but no actual (libs/regime/event_state.py) -- a licensed "
                  "calendar with actuals is the acquisition target"))
    vals = [float(h) for h in history if isinstance(h, int | float) and math.isfinite(h)]
    if len(vals) < MIN_SURPRISE_N:
        return SurpriseEstimate(
            None, None, len(vals), Status.UNMEASURED, actual, consensus, release_id,
            note=f"n={len(vals)} historical surprises < MIN_SURPRISE_N={MIN_SURPRISE_N}")
    sd = stdev(vals)
    if sd <= 0:
        return SurpriseEstimate(None, None, len(vals), Status.UNMEASURED, actual, consensus,
                                release_id, note="historical surprise sigma is zero")
    return SurpriseEstimate(
        z=round((float(actual) - float(consensus)) / sd, 4), sigma=round(sd, 8), n=len(vals),
        status=Status.MEASURED, actual=float(actual), consensus=float(consensus),
        release_id=release_id, direction_from="not_used_for_direction",
        note=("magnitude only. The sign of any asset response comes from the measured "
              "cross-asset reaction, never from the sign of z"))


@dataclass(frozen=True)
class Interpretation:
    """What the market is doing with the number, as opposed to what the number says.

    `factor_deltas` carries the SIGNS THE MARKET CHOSE. `mechanical_z_sign` is what a rules
    table would have said and is recorded only so the divergence is visible in the ledger.
    """

    factor_deltas: dict[str, float]
    magnitude: float
    status: str
    shrinkage: float
    mechanical_z_sign: int | None
    direction_from: str
    conditioners: dict[str, float] = field(default_factory=dict)
    note: str = ""

    @property
    def diverges_from_mechanical(self) -> bool:
        """True when at least one measured factor moved opposite to the naive z reading. These
        rows are the ones worth reading: they are where a sign table would have been wrong."""
        if self.mechanical_z_sign is None or not self.factor_deltas:
            return False
        return any(d * self.mechanical_z_sign < 0 for d in self.factor_deltas.values())


def _shrink(value: float | None, *, scale: float, floor: float = 0.0) -> float:
    """Map a conditioner onto a multiplier in [floor, 1]. None -> 1.0 (no opinion, no shrink).

    Exponential rather than linear so an extreme conditioner shrinks hard without ever reaching
    zero or turning negative -- a conditioner may reduce conviction to nearly nothing and may
    never invert it.
    """
    if value is None or not math.isfinite(value):
        return 1.0
    m = math.exp(-abs(float(value)) / max(scale, 1e-9))
    return floor + (1.0 - floor) * m


def interpret(surprise: SurpriseEstimate,
              factor_response: Mapping[str, float] | None,
              *,
              unpriced_fraction: float | None = None,
              positioning_z: float | None = None,
              liquidity_stress: float | None = None,
              pre_event_move_sigma: float | None = None,
              regime_confidence: float | None = None,
              credibility_uncertainty: float = 1.0) -> Interpretation:
    """Turn a measured reaction into factor deltas, conditioned. Refuses when unmeasured.

    `factor_response` is the OBSERVED move of each latent factor in the event window, in sigma,
    from `factors.py`. Absent or empty means the desk has not yet seen how the market took the
    number, and the answer is UNMEASURED with no deltas -- not the sign of z.
    """
    mech = None if surprise.z is None else (1 if surprise.z > 0 else -1 if surprise.z < 0 else 0)
    if not factor_response:
        return Interpretation(
            {}, 0.0, Status.UNMEASURED, 0.0, mech, "none",
            note=("no measured cross-asset reaction yet -- the direction is not inferable from "
                  "the surprise alone and is NOT taken from the sign of z"))

    conditioners = {
        # Crowding: a market already positioned for this outcome has less left to do.
        "positioning": _shrink(positioning_z, scale=2.0, floor=0.2),
        # A stressed tape means the desk cannot execute into the move it forecasts.
        "liquidity": _shrink(liquidity_stress, scale=2.0, floor=0.1),
        # Some of the response happened before the desk arrived.
        "pre_event_move": _shrink(pre_event_move_sigma, scale=3.0, floor=0.1),
        # A regime the desk cannot classify is a regime whose reaction function is unknown.
        "regime_confidence": 1.0 if regime_confidence is None
        else max(0.1, min(1.0, float(regime_confidence))),
        # Contested reports divide conviction; see credibility.combine.
        "credibility": 1.0 / max(1.0, float(credibility_uncertainty)),
        # What is left to trade at all.
        "unpriced": 1.0 if unpriced_fraction is None else max(0.0, min(1.0, unpriced_fraction)),
    }
    shrink = 1.0
    for v in conditioners.values():
        shrink *= v

    deltas = {k: round(float(v) * shrink, 6) for k, v in factor_response.items()
              if isinstance(v, int | float) and math.isfinite(float(v))}
    magnitude = max((abs(v) for v in deltas.values()), default=0.0)
    # Sample-thin surprise does not block interpretation -- the market's reaction is measured
    # whether or not the desk can standardise the print -- but it is recorded, because a
    # magnitude with no surprise scale behind it is a weaker claim and must read as one.
    status = Status.MEASURED if deltas else Status.UNMEASURED
    note = ("direction and sign taken from the MEASURED factor response; z used for magnitude "
            "context only")
    if surprise.status != Status.MEASURED:
        note += "; surprise z UNMEASURED, so the print's own scale is unknown"
    return Interpretation(deltas, round(magnitude, 6), status, round(shrink, 6), mech,
                          "measured_factor_response", conditioners, note)


def summarise(interp: Interpretation, surprise: SurpriseEstimate) -> dict[str, Any]:
    """A row an auditor can read without the code, including the divergence flag."""
    return {
        "z": surprise.z, "z_status": surprise.status, "z_n": surprise.n,
        "direction_from": interp.direction_from,
        "factor_deltas": interp.factor_deltas,
        "magnitude": interp.magnitude,
        "shrinkage": interp.shrinkage,
        "conditioners": {k: round(v, 4) for k, v in interp.conditioners.items()},
        "mechanical_z_sign_NOT_USED": interp.mechanical_z_sign,
        "diverges_from_mechanical": interp.diverges_from_mechanical,
        "status": interp.status,
        "note": interp.note,
    }


def historical_surprises(rows: Sequence[Mapping[str, Any]], release_id: str) -> list[float]:
    """Extract this release's past (actual - consensus) values from ledger-style rows.

    Rows missing either field are SKIPPED rather than defaulted -- a release whose actual was
    never captured contributes nothing to its own sigma, which is why the count travels with
    every estimate.
    """
    out: list[float] = []
    for r in rows:
        if str(r.get("release_id", "")) != release_id:
            continue
        a, c = r.get("actual"), r.get("consensus")
        if isinstance(a, int | float) and isinstance(c, int | float):
            out.append(float(a) - float(c))
    return out


def surprise_scale(history: Sequence[float]) -> tuple[float | None, str]:
    """Mean and sigma of a surprise history, or the reason there is none."""
    vals = [float(h) for h in history if isinstance(h, int | float) and math.isfinite(h)]
    if len(vals) < MIN_SURPRISE_N:
        return None, f"n={len(vals)} < MIN_SURPRISE_N={MIN_SURPRISE_N}"
    sd = stdev(vals)
    return (sd, "") if sd > 0 else (None, "sigma is zero")


def mean_bias(history: Sequence[float]) -> float | None:
    """Systematic forecast bias in this release's consensus, if the sample supports one.

    A consensus that is persistently low is not a stream of surprises; it is a biased forecast,
    and treating its bias as news would have the desk trading the same non-event every month.
    """
    vals = [float(h) for h in history if isinstance(h, int | float) and math.isfinite(h)]
    if len(vals) < MIN_SURPRISE_N:
        return None
    return round(fmean(vals), 8)
