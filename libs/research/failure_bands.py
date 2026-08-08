"""FAILURE MINING AND NEAR-SURVIVOR BANDS — a killed hypothesis is the most specific thing the
desk knows about where an effect is NOT, and "not here" is information about where it is.

TWO THINGS, ONE MODULE, because they are the same act at different distances from the bar. A band
is a distance; a failure record is why the distance exists. Splitting them would put the fields
that license a follow-up experiment in a different place from the measurement that says whether one
is warranted.

THE BANDS, and the two in the middle are the ones the desk currently cannot see:

    FAR              nowhere near, on any axis          -> retire the FAMILY, not just the cell
    WEAK             directionally right, far from bar   -> cheap axis expansion only
    NEAR             within reach of the bar             -> the highest-value re-test on the desk
    ECON_POSITIVE_STAT_WEAK   makes money, thin sample   -> a SPAN problem, not an edge problem
    STAT_STRONG_ECON_NEGATIVE clears t, loses money      -> a COST problem, not an edge problem
    CLEARED          over the bar                        -> not this module's business

THE LAST TWO BANDS EXIST BECAUSE COLLAPSING THEM INTO "FAILED" DESTROYS THE DIAGNOSIS. A cell that
is economically positive and statistically weak needs more TAPE. A cell that is statistically strong
and economically negative needs cheaper EXECUTION. Both read as "did not survive", and the actions
are not merely different — they are spent in different budgets, on different teams, in different
weeks. This desk has already made that error once in production: `F5 SAMPLE FLOOR` cells were read
as an absence of edge when they were an absence of observations.

WHAT THIS DOES NOT DO. It does not license unlimited mutation. Every descendant inherits the
ancestry's whole trial count -- a near-survivor is near BECAUSE the desk searched a large space, and
re-searching its neighbourhood without carrying that deflation is the most efficient
survivor-manufacturing device available. `near_survivor.hurdle` owns that arithmetic; this module
decides only WHICH cells are worth handing to it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

__all__ = [
    "BANDS",
    "BAND_ACTIONS",
    "FailureRecord",
    "band_of",
    "mine",
    "summarise",
]

#: Ordered by how much attention each deserves, not by distance from the bar. The two diagnostic
#: bands outrank NEAR because they name a CAUSE, and a named cause is cheaper to act on than
#: proximity.
BANDS: tuple[str, ...] = (
    "ECON_POSITIVE_STAT_WEAK",
    "STAT_STRONG_ECON_NEGATIVE",
    "NEAR",
    "WEAK",
    "FAR",
    "CLEARED",
)

BAND_ACTIONS: dict[str, str] = {
    "ECON_POSITIVE_STAT_WEAK": (
        "GET MORE TAPE. The economics work and the sample cannot prove it -- this is a SPAN "
        "problem, and no amount of harness tuning creates observations. Extend the window or widen "
        "the symbol set, then re-test at the ancestry-deflated hurdle"),
    "STAT_STRONG_ECON_NEGATIVE": (
        "ATTACK COST, NOT SIGNAL. The effect is real and the round trip eats it: check maker "
        "conversion, holding period and clip size before touching the expression. A slower version "
        "of the same signal pays the spread fewer times"),
    "NEAR": (
        "RE-TEST WITH ONE CHANGE, at the ancestry-deflated hurdle. Near is the cheapest experiment "
        "the desk owns -- already located, already costed -- and also the easiest place to "
        "manufacture a survivor by trying variants until one passes"),
    "WEAK": (
        "CHEAP AXIS EXPANSION ONLY. Directionally right is not evidence; spend nothing here beyond "
        "adding a data axis the mechanism plausibly needs"),
    "FAR": (
        "RETIRE THE FAMILY, not the cell. A cell far from the bar on every axis is evidence about "
        "its whole neighbourhood, and that is the graveyard entry worth writing"),
    "CLEARED": "over the bar -- validation's business, not failure mining's",
}


@dataclass(frozen=True)
class FailureRecord:
    """A killed cell, with the fields that decide whether a follow-up is warranted.

    EVERY FIELD IS OPTIONAL AND `None` MEANS UNMEASURED, which is the only honest default for a
    record reconstructed from a sweep report. A missing `net_bps` is not a zero-edge cell; a
    missing `n_observations` is not a large sample. Defaulting either to a number would let the
    band classifier answer a question nobody asked it.
    """

    key: str
    t_stat: float | None = None
    net_bps: float | None = None
    hurdle: float | None = None
    n_observations: int | None = None
    kill_criterion: str = ""
    regime: str = ""
    horizon: str = ""
    feature_family: str = ""
    cost_bps: float | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def measurable(self) -> bool:
        return self.t_stat is not None and self.net_bps is not None


def band_of(r: FailureRecord, *, near_fraction: float = 0.75) -> tuple[str, str]:
    """(band, why). UNMEASURED cells get no band, because a band is a claim about a distance.

    `near_fraction` is the share of the hurdle a cell must reach to count as NEAR. It is a
    parameter rather than a constant because the hurdle itself moves with the declared universe,
    and a fixed t-threshold would silently redefine "near" every time the universe grew.
    """
    if not r.measurable or r.hurdle is None:
        return "", ("UNMEASURED -- no band. A band is a claim about DISTANCE from the bar, and a "
                    "cell with no t or no net has no distance. Calling it FAR would convert "
                    "missing data into a negative result, which is WS-005")
    t, net, bar = r.t_stat, r.net_bps, r.hurdle
    assert t is not None and net is not None  # narrowed by `measurable`
    if t >= bar and net > 0:
        return "CLEARED", f"t={t:.2f} >= {bar:.2f} and net {net:+.3f}bp"
    if net > 0 and t < bar:
        thin = r.n_observations is not None and r.n_observations < 250
        if thin or t >= bar * near_fraction:
            return "ECON_POSITIVE_STAT_WEAK", (
                f"net {net:+.3f}bp with t={t:.2f} against {bar:.2f}"
                + (f" on {r.n_observations} observation(s)" if r.n_observations else "")
                + " -- the economics work and the sample cannot prove it")
    if t >= bar and net <= 0:
        return "STAT_STRONG_ECON_NEGATIVE", (
            f"t={t:.2f} clears {bar:.2f} but net is {net:+.3f}bp"
            + (f" against {r.cost_bps:.3f}bp of cost" if r.cost_bps is not None else "")
            + " -- the effect is real and the round trip eats it")
    if t >= bar * near_fraction:
        return "NEAR", f"t={t:.2f} is within {1 - near_fraction:.0%} of {bar:.2f}"
    if t > 0:
        return "WEAK", f"t={t:.2f} is directionally right and far from {bar:.2f}"
    return "FAR", f"t={t:.2f} against {bar:.2f} -- evidence about the whole family"


def mine(records: list[FailureRecord], *, near_fraction: float = 0.75,
         ) -> list[dict[str, object]]:
    """Banded, ranked, each with the action its band licenses and the fields that justify it."""
    out: list[dict[str, object]] = []
    for r in records:
        band, why = band_of(r, near_fraction=near_fraction)
        out.append({
            "key": r.key, "band": band or "UNMEASURED", "why": why,
            "action": BAND_ACTIONS.get(band, "name the missing measurement, then re-band"),
            "t": r.t_stat, "net_bps": r.net_bps, "hurdle": r.hurdle,
            "n": r.n_observations, "kill": r.kill_criterion,
            "regime": r.regime, "horizon": r.horizon, "family": r.feature_family,
        })
    out.sort(key=lambda d: BANDS.index(str(d["band"])) if d["band"] in BANDS else len(BANDS))
    return out


def summarise(records: list[FailureRecord], *, near_fraction: float = 0.75) -> dict[str, object]:
    """Report shape. THE HEADLINE IS THE DIAGNOSTIC SPLIT, not the failure count.

    "1,200 cells failed" is a number nobody can act on. "400 of them failed for want of tape and
    300 for want of cheaper execution" names two projects, in two budgets, and neither of them is
    "search harder".
    """
    rows = mine(records, near_fraction=near_fraction)
    tally = Counter(str(r["band"]) for r in rows)
    span = tally["ECON_POSITIVE_STAT_WEAK"]
    cost = tally["STAT_STRONG_ECON_NEGATIVE"]
    if not rows:
        head = "no failure records -- UNMEASURED, and an empty graveyard is not a clean sweep"
    elif span or cost:
        head = (f"{span} cell(s) blocked by SPAN and {cost} by COST -- two projects in two "
                "budgets, and neither of them is 'search harder'")
    else:
        head = (f"{tally['NEAR']} near, {tally['WEAK']} weak, {tally['FAR']} far; "
                f"{tally['UNMEASURED']} unmeasured")
    return {
        "records": len(records), "tally": dict(tally), "headline": head,
        "banded": rows[:50],
        "note": ("a descendant inherits the ancestry's WHOLE trial count -- near_survivor.hurdle "
                 "owns that arithmetic. This module decides only which cells are worth handing to "
                 "it, and unmeasured cells are handed to nobody"),
    }
