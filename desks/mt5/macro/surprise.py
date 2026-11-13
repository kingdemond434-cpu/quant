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
    "composite_z",
    "interpret",
    "surprise_family",
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


def _finite(x: Any) -> float | None:
    if isinstance(x, bool) or not isinstance(x, int | float):
        return None
    return float(x) if math.isfinite(float(x)) else None


def _unmeasured(why: str) -> dict[str, Any]:
    return {"value": Status.UNMEASURED, "why": why}


def surprise_family(actual: float | None, consensus: float | None, *,
                    history: Sequence[float] = (),
                    high: float | None = None, low: float | None = None,
                    previous_first: float | None = None,
                    previous_revised: float | None = None,
                    model_expectation: float | None = None,
                    model_history: Sequence[float] = (),
                    peer_z: Sequence[float] = (),
                    priced_fraction: float | None = None,
                    conditioning: Mapping[str, Any] | None = None,
                    release_id: str = "") -> dict[str, Any]:
    """Every standardised variant of one release's surprise, each MEASURED or named UNMEASURED.

    THE PRINCIPAL'S LIST (2026-10-05, "ECONOMIC SURPRISE LAYER"): actual - consensus, the
    release-specific z, and the dispersion-, revision-, component-, relative-country-,
    percentile-, market-implied-, nowcast-, regime- and positioning-conditioned variants. All of
    them are MAGNITUDES. None of them carries a direction for any asset: the sign of a response is
    measured (`interpret`), never derived here.

      raw                  actual - consensus
      z_release            raw / sd(this release's own past raw surprises)   (z_score)
      dispersion_adjusted  raw / ((high - low) / 4): the survey range as a +/-2 sd band
      revision_adjusted    raw + (previous_revised - previous_first): the news in the prior
                           print's revision arrives on the same release and in the same units
      percentile           where raw sits in this release's own past surprises (0..1)
      nowcast_relative     actual - model expectation, and its z against the model's own past
                           errors -- a surprise that needs no survey, so it has decades of history
      relative_country     z_release - mean(z of the same release type elsewhere, same window)
      market_implied       raw x (1 - the fraction already priced before publication), when the
                           priced fraction was measured (`macro.priced`)
      conditioning         the regime and positioning state AT the release, carried as keys a
                           measurement can bucket on; they never rescale or re-sign the value
    """
    a, c = _finite(actual), _finite(consensus)
    hist = [h for h in (_finite(x) for x in history) if h is not None]
    out: dict[str, Any] = {"release_id": release_id, "actual": a, "consensus": c,
                           "direction_from": "not_used_for_direction"}
    raw = (a - c) if a is not None and c is not None else None
    out["raw"] = round(raw, 10) if raw is not None else _unmeasured("actual or consensus absent")
    est = z_score(a, c, hist, release_id=release_id)
    out["z_release"] = (est.z if est.z is not None else _unmeasured(est.note))
    out["z_history_n"] = est.n
    hi, lo = _finite(high), _finite(low)
    if raw is None:
        out["dispersion_adjusted"] = _unmeasured("no raw surprise")
    elif hi is None or lo is None:
        out["dispersion_adjusted"] = _unmeasured(
            "no lawful survey high/low for this release (the free calendar publishes a median "
            "only); a licensed survey range is the acquisition target")
    elif hi - lo <= 0:
        out["dispersion_adjusted"] = _unmeasured("survey range is zero")
    else:
        out["dispersion_adjusted"] = round(raw / ((hi - lo) / 4.0), 6)
    pf, pr = _finite(previous_first), _finite(previous_revised)
    out["previous_revision"] = (round(pr - pf, 10) if pf is not None and pr is not None
                                else _unmeasured("prior period's first print or its revision "
                                                 "absent"))
    out["revision_adjusted"] = (round(raw + (pr - pf), 10)
                                if raw is not None and pf is not None and pr is not None
                                else _unmeasured("needs raw and the prior print's revision"))
    if raw is not None and len(hist) >= MIN_SURPRISE_N:
        below = sum(1 for h in hist if h < raw) + 0.5 * sum(1 for h in hist if h == raw)
        out["percentile"] = round(below / len(hist), 4)
    else:
        out["percentile"] = _unmeasured(f"n={len(hist)} past surprises < {MIN_SURPRISE_N}")
    m = _finite(model_expectation)
    mhist = [h for h in (_finite(x) for x in model_history) if h is not None]
    if a is None or m is None:
        out["nowcast_relative"] = _unmeasured("no actual or no model expectation")
        out["nowcast_z"] = _unmeasured("no nowcast surprise")
    else:
        out["nowcast_relative"] = round(a - m, 10)
        nz = z_score(a, m, mhist, release_id=f"{release_id}|nowcast")
        out["nowcast_z"] = nz.z if nz.z is not None else _unmeasured(nz.note)
    zr = est.z
    peers = [p for p in (_finite(x) for x in peer_z) if p is not None]
    out["relative_country"] = (round(zr - fmean(peers), 4) if zr is not None and peers else
                               _unmeasured("no z for this release or no peer-country z of the "
                                           "same release type in the window"))
    pfrac = _finite(priced_fraction)
    out["market_implied"] = (round(raw * (1.0 - min(1.0, max(0.0, pfrac))), 10)
                             if raw is not None and pfrac is not None else
                             _unmeasured("the pre-publication priced fraction was not measured "
                                         "(macro.priced needs a fast series for the release's "
                                         "instruments)"))
    cond = dict(conditioning or {})
    out["conditioning"] = {"regime": cond.get("regime", Status.UNMEASURED),
                           "positioning": cond.get("positioning", Status.UNMEASURED),
                           "rule": "bucket keys for a measurement; never a rescale or a sign"}
    return out


def composite_z(zs: Mapping[str, float | None]) -> dict[str, Any]:
    """COMPONENT-WEIGHTED surprise of releases printed at one instant (payrolls, unemployment
    and earnings at 08:30 ET on the first Friday). Equal weights, DECLARED: a weight fitted to
    the reaction would be a direction smuggled in. Needs at least two measured components."""
    got = {k: float(v) for k, v in zs.items() if _finite(v) is not None}
    if len(got) < 2:
        return {"value": Status.UNMEASURED, "components": sorted(got),
                "why": f"{len(got)} measured component z(s) at this instant; two are needed"}
    return {"value": round(fmean(got.values()), 4), "components": sorted(got),
            "weights": "equal (declared)"}


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
