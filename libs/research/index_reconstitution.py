"""INDEX RECONSTITUTION FLOW -- pre-registered, in full, before any number is computed.

Census gap #1 (score 0.4800, NO-CANDIDATE): the highest-ranked mechanism on the desk and never
screened. Everything below is the pre-registration. It is written here, dated, before a single
event has been fetched, so there is nothing to tune after seeing a result.

THE MECHANISM. An index change is a dated, PRE-ANNOUNCED, price-insensitive order of known
DIRECTION and approximately known SIZE. A tracking fund's mandate forces it to hold the index as
published; a manager who declines is running tracking error they are contractually not permitted to
run. Whoever supplies that liquidity is paid for immediacy by a buyer who cannot wait and cannot
negotiate. The edge lives BETWEEN announcement and effective date and DIES with the flow -- it is
compensation for absorbing a mandate, not a forecast of value.

WHO IS FORCED TO TRADE. The tracking fund, ETP or structured product. Named, and it is the reason
this is a mechanism rather than a pattern: the counterparty's obligation is contractual and public.

THE CONSTRUCTIONS, declared 2026-08-15, all three or none:
  C1 ANNOUNCEMENT-TO-EFFECTIVE DRIFT. Long adds / short deletes from the close after the
     announcement to the close before the effective date. The core claim.
  C2 EFFECTIVE-DATE REVERSAL. The opposite leg from the effective close forward `REVERSAL_DAYS`.
     If C1 is real, part of it must give back -- an inclusion effect with NO reversal is more
     likely a value story than a flow story, and the pair distinguishes them.
  C3 SIZE-CONDITIONED C1, split at the median announced weight change. Flow compensation should
     scale with the flow; if it does not, the mechanism claim is weakened even when C1 is positive.

HORIZONS. Fixed: the announcement->effective window as published per event (variable by design --
it is the mechanism's own clock, not a parameter), and REVERSAL_DAYS = 5 after the effective date.

ALIGNMENT. Both legs use the CLOSE strictly AFTER the announcement instant. An announcement is
public at a moment, not on a date, and using the announcement day's own close would put the
position on the bar that carries the news -- an in-sample artifact that has killed more event
studies on this desk than any other single error.

BENCHMARK. Each event's return is measured in EXCESS of the same-window return of the index's
non-changing members. An index add during a rally is not evidence of anything, and the market
factor is exactly what both legs share.

MULTIPLICITY. Three constructions, charged as m=3 within the `index_reconstitution_flow` family
under the family partition. It does not touch any other family's bar.

KILL CRITERIA, binding BEFORE the run:
  * C1 excess return not distinguishable from zero at the family's Holm bar -> REFUTED.
  * fewer than MIN_EVENTS usable events -> UNDERPOWERED, never REFUTED. A null on a sample too
    small to detect the effect is a statement about the sample.
  * C1 positive and C2 showing NO reversal -> the flow interpretation is NOT supported; report as
    an anomaly requiring a different mechanism, not as a win for this one.

WHY IT IS UNSCREENED RATHER THAN DEAD. The data is free and public -- index methodology documents
publish announcement and effective dates, and constituent lists are published before and after each
review. Nobody had fetched them. That is a collection gap, and a collection gap that has never been
attempted is the cheapest kind of gap there is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from statistics import NormalDist
from typing import Any

import numpy as np

__all__ = [
    "MIN_EVENTS",
    "N_CONSTRUCTIONS",
    "REVERSAL_DAYS",
    "ReconEvent",
    "event_excess_return",
    "run_screen",
    "window_return",
]

#: Days after the effective date over which C2 measures the give-back. Fixed here, before any data.
REVERSAL_DAYS = 5

#: Below this the screen reports UNDERPOWERED and never REFUTED. A null on a sample too small to
#: detect the effect is a statement about the sample, not about the market (L1.28a).
MIN_EVENTS = 20

#: C1, C2, C3. The multiplicity this screen charges within its own family.
N_CONSTRUCTIONS = 3


@dataclass(frozen=True)
class ReconEvent:
    """One index change, as published. Every field comes from the methodology document."""

    symbol: str
    index_name: str
    announced_at: datetime
    effective_at: datetime
    direction: int                 # +1 add, -1 delete
    weight_change: float = 0.0     # announced index weight delta, for C3

    @property
    def valid(self) -> bool:
        return (self.direction in (1, -1) and bool(self.symbol)
                and self.effective_at > self.announced_at)


def window_return(stamps: tuple[datetime, ...], closes: np.ndarray,
                  start: datetime, end: datetime) -> float | None:
    """Close-to-close return over (start, end], using the first close STRICTLY AFTER `start`.

    STRICTLY AFTER IS THE WHOLE ALIGNMENT RULE. An announcement is public at a moment, not on a
    date; entering on the announcement day's own close puts the position on the bar that carries
    the news and manufactures the effect being measured. Returns None rather than a number when
    either side of the window has no bar -- a window that could not be formed is UNMEASURED, and
    substituting the nearest available bar silently changes the horizon.
    """
    if len(stamps) != len(closes) or not len(closes):
        return None
    lo = next((i for i, t in enumerate(stamps) if t > start), None)
    if lo is None:
        return None
    hi = None
    for i in range(len(stamps) - 1, -1, -1):
        if stamps[i] <= end:
            hi = i
            break
    if hi is None or hi <= lo:
        return None
    p0, p1 = float(closes[lo]), float(closes[hi])
    if not (math.isfinite(p0) and math.isfinite(p1)) or p0 <= 0:
        return None
    return p1 / p0 - 1.0


def event_excess_return(ev: ReconEvent, panel: dict[str, tuple[tuple[datetime, ...], np.ndarray]],
                        benchmark: list[str], *, start: datetime, end: datetime) -> float | None:
    """The event's return in EXCESS of the same-window return of non-changing members.

    An index add during a rally is not evidence of anything. The benchmark is the market factor
    both legs share, and differencing it away is what separates a flow claim from a beta claim.
    Returns None when the event leg OR the benchmark cannot be formed -- a raw return published
    as an excess return is the same defect as a missing benchmark, one step later.
    """
    own = panel.get(ev.symbol)
    if own is None:
        return None
    r = window_return(own[0], own[1], start, end)
    if r is None:
        return None
    raw = [window_return(*panel[s], start, end) for s in benchmark
           if s in panel and s != ev.symbol]
    peers: list[float] = [x for x in raw if x is not None]
    if not peers:
        return None
    return float(ev.direction) * (r - float(np.mean(peers)))


def _stat(xs: list[float]) -> dict[str, Any]:
    """Mean, its standard error, and the one-sided t. No threshold is applied here -- the bar
    belongs to the family cohort, and a module that carried its own would be a second bar."""
    n = len(xs)
    if n < 2:
        return {"n": n, "mean": None, "se": None, "t": None}
    a = np.asarray(xs, dtype="float64")
    se = float(a.std(ddof=1)) / math.sqrt(n)
    return {"n": n, "mean": round(float(a.mean()), 6),
            "se": round(se, 6),
            "t": round(float(a.mean()) / se, 3) if se > 0 else None}


def run_screen(events: list[ReconEvent],
               panel: dict[str, tuple[tuple[datetime, ...], np.ndarray]],
               benchmark: list[str] | None = None,
               *, alpha: float = 0.05) -> dict[str, Any]:
    """All three constructions, or a stated refusal. NO THRESHOLD IS TUNED HERE.

    The bar comes from the family cohort via `family_multiplicity`, so admitting this screen costs
    the `index_reconstitution_flow` family its own multiplicity and costs no other family anything.
    """
    from libs.validation.family_multiplicity import bh_bar

    usable = [e for e in events if e.valid]
    bench = benchmark or sorted(panel)
    rep: dict[str, Any] = {
        "class": "index_reconstitution_flow",
        "n_events_supplied": len(events), "n_events_valid": len(usable),
        "constructions": N_CONSTRUCTIONS, "reversal_days": REVERSAL_DAYS,
        "holm_bar_within_family": bh_bar(N_CONSTRUCTIONS, 1, alpha=alpha),
        "prereg": ("libs/research/index_reconstitution module docstring, dated 2026-08-15, "
                   "written before any event was fetched"),
    }
    if not panel:
        rep["status"] = "NOT-READABLE-HERE"
        rep["verdict"] = "UNMEASURED"
        rep["why"] = ("no daily price panel supplied. Build it with scripts/build_daily_panel.py; "
                      "an event study with no prices is not a null result, it is no result")
        return rep

    c1: list[float] = []
    c2: list[float] = []
    sizes: list[tuple[float, float]] = []
    for e in usable:
        r1 = event_excess_return(e, panel, bench, start=e.announced_at, end=e.effective_at)
        if r1 is not None:
            c1.append(r1)
            sizes.append((abs(e.weight_change), r1))
        end2 = e.effective_at.replace() + (e.effective_at - e.effective_at)
        # C2's window is REVERSAL_DAYS of bars after the effective close, taken off the panel's own
        # clock rather than a calendar arithmetic that would silently include non-trading days.
        own = panel.get(e.symbol)
        if own is not None:
            after = [t for t in own[0] if t > e.effective_at]
            if len(after) >= REVERSAL_DAYS:
                end2 = after[REVERSAL_DAYS - 1]
                r2 = event_excess_return(e, panel, bench, start=e.effective_at, end=end2)
                if r2 is not None:
                    c2.append(-r2)      # the REVERSAL leg: opposite sign to C1 by construction

    rep["C1_announcement_to_effective"] = _stat(c1)
    rep["C2_effective_reversal"] = _stat(c2)
    if sizes:
        med = float(np.median([s for s, _ in sizes]))
        rep["C3_size_conditioned"] = {
            "median_abs_weight_change": round(med, 6),
            "large": _stat([r for s, r in sizes if s >= med]),
            "small": _stat([r for s, r in sizes if s < med]),
        }

    n1 = rep["C1_announcement_to_effective"]["n"]
    if n1 < MIN_EVENTS:
        rep["status"] = "UNDERPOWERED"
        rep["verdict"] = "UNMEASURED"
        rep["why"] = (f"{n1} usable event(s) against MIN_EVENTS={MIN_EVENTS}. A null on a sample "
                      "too small to detect the effect is a statement about the sample. NOT "
                      "REFUTED -- this cell has not been tested, and recording it as a kill would "
                      "retire the desk's highest-ranked mechanism on no evidence")
        return rep

    t1 = rep["C1_announcement_to_effective"]["t"]
    bar = rep["holm_bar_within_family"]
    rep["status"] = "RUN"
    # AN UNDEFINED STATISTIC IS NOT A REFUTATION. `t` is None when the sample has zero dispersion,
    # so the standard error is zero and the ratio does not exist. Folding that into "below the bar"
    # reports a REFUTED verdict for a sample that is degenerate rather than null -- and it reads
    # identically to a real kill in every artifact downstream. That is WS-005 on the verdict field.
    if t1 is None:
        rep["status"] = "DEGENERATE"
        rep["verdict"] = "UNMEASURED"
        rep["why"] = ("C1 has zero dispersion, so its standard error is zero and t does not "
                      "exist. NOT refuted -- an undefined statistic is not evidence of no effect. "
                      "Inspect the panel: identical returns across events usually means one "
                      "series was joined to every event")
        return rep
    if t1 < bar:
        rep["verdict"] = "REFUTED"
        rep["why"] = f"C1 t={t1} below the family bar {bar}; the drift is not distinguishable"
        return rep
    t2 = rep["C2_effective_reversal"]["t"]
    if t2 is None or t2 < bar:
        rep["verdict"] = "ANOMALY-NOT-FLOW"
        rep["why"] = ("C1 clears its bar and C2 shows NO reversal. An inclusion effect that never "
                      "gives back is more likely a value story than a flow story, so the FLOW "
                      "mechanism is not supported even though the return is there. Reported as an "
                      "anomaly needing a different mechanism, never as a win for this one")
        return rep
    rep["verdict"] = "SURVIVES-STAGE-A"
    rep["why"] = (f"C1 t={t1} and the C2 reversal t={t2} both clear the family bar {bar}. "
                  "STAGE A ONLY -- zero promotion authority. This earns a forward clock, not "
                  "capital")
    return rep


def holm_reference(alpha: float = 0.05) -> float:
    """The one-sided z this screen is judged against, exposed so a caller can print it beside a
    result rather than re-deriving it and disagreeing by a rounding."""
    return round(NormalDist().inv_cdf(1.0 - alpha / N_CONSTRUCTIONS), 2)
