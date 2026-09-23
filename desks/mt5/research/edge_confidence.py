#!/usr/bin/env python3
"""SIZE FROM THE LOWER BOUND OF THE EDGE, AND STRESS k_eff TOWARD CRISIS CORRELATION.

Two criticisms from an external review of this desk (2026-09-06) that were correct and are worth
real geometric growth. Most of that review graded a branch that does not exist -- it reported
"zero test files" against a tree carrying 965 of them -- but these two survive scrutiny, so they
are implemented rather than argued with.

    "Size from the LOWER CONFIDENCE BOUND of the edge estimate, not the point estimate."
    "Correlations rise toward 1.0 in crises. Your k_eff is historical."

WHY THE FIRST ONE IS THE BIGGEST ITEM ON THE DESK. Kelly is not symmetric around its optimum.
Overbetting by a factor of two does not cost what underbetting by a factor of two costs -- it
costs far more, and past 2x the optimum the geometric growth rate goes NEGATIVE while the
arithmetic mean still looks fine. So an edge estimated at 0.159R with a standard error of 0.08R
is not "0.159R": it is a distribution whose lower half contains sizes at which the desk is
already overbetting, and sizing on the point estimate spends the whole confidence interval on
one side of the trade.

The fix is arithmetic, not philosophy: size on `mean - z * se`, floor at zero, and let the
sample size do the work. A sleeve with 400 forward observations barely moves; a sleeve with 25
gets cut hard, which is exactly right because 25 observations do not distinguish a 0.159R edge
from no edge at all.

THIS ONLY EVER REDUCES SIZE. It is a tightening, never a loosening, and it can never be used to
justify a larger position than the point estimate would have. That property is fenced.

WHY THE SECOND ONE MATTERS. `independence.py` already takes the 95% UPPER bound on mean pairwise
correlation, which is genuinely conservative and better than most desks manage. But an upper
bound on the HISTORICAL correlation is not a crisis correlation: in a drawdown, dispersion
collapses and sleeves that looked independent for a year move together for a fortnight. Heat
sized on quiet-period independence is heat sized for the period in which it does not matter.

So k_eff is computed twice -- as measured, and under a stated crisis assumption -- and the heat
budget uses the WORSE of the two. The desk gives up some size in calm markets to survive the
regime that actually produces drawdowns.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
REPORT = BASE / "reports" / "EDGE_CONFIDENCE.json"

#: One-sided confidence multiplier on the edge estimate. 1.645 = 95%, matching the multiplier
#: `independence.py` already uses for the correlation upper bound -- the same level applied to
#: both halves of the sizing input, so neither is silently more forgiving than the other.
EDGE_Z = 1.645

#: Correlation every sleeve is assumed to move at under stress. Not a forecast: a floor for
#: sizing. Chosen because in every equity/FX drawdown worth naming, cross-sleeve dispersion
#: collapses to roughly this and does so within days, long before a historical estimator notices.
CRISIS_RHO = 0.8

#: Below this many forward observations the desk declines to size from the edge at all. It is not
#: that the estimate is poor -- it is that its lower bound is almost always negative, so any
#: number produced here would be an artefact of the floor rather than a measurement.
MIN_OBS_FOR_EDGE = 20


@dataclass(frozen=True)
class Edge:
    """A measured edge and the sample it came from. `sd_r` is per-trade, not annualised."""

    name: str
    mean_r: float
    sd_r: float
    n: int


def lower_bound(e: Edge, z: float = EDGE_Z) -> dict[str, Any]:
    """The edge to SIZE on: mean - z * standard error, floored at zero.

    Kelly is not symmetric around its optimum. Overbetting 2x costs far more than underbetting
    2x, and past 2x the geometric growth rate goes negative while the arithmetic mean still looks
    healthy. Sizing on the point estimate spends the entire confidence interval on the side that
    ruins you.
    """
    if e.n < MIN_OBS_FOR_EDGE:
        return {"name": e.name, "size_on": 0.0, "point": round(e.mean_r, 5), "n": e.n,
                "status": "INSUFFICIENT",
                "why": (f"{e.n} forward observations, below {MIN_OBS_FOR_EDGE}. The lower bound "
                        "of an edge this thinly sampled is almost always negative, so any size "
                        "derived from it would be an artefact of the floor rather than a "
                        "measurement")}
    se = e.sd_r / math.sqrt(e.n) if e.n > 0 else float("inf")
    lb = e.mean_r - z * se
    sized = max(0.0, lb)
    haircut = 1.0 - (sized / e.mean_r) if e.mean_r > 0 else 1.0
    return {
        "name": e.name, "size_on": round(sized, 5), "point": round(e.mean_r, 5),
        "lower_bound": round(lb, 5), "std_error": round(se, 5), "n": e.n,
        "haircut": round(haircut, 4), "status": "MEASURED" if sized > 0 else "NO_EDGE_AT_BOUND",
        "why": (f"point {e.mean_r:+.4f}R, se {se:.4f} over {e.n} observations -> size on "
                f"{sized:.4f}R, a {haircut:.0%} haircut"
                if sized > 0 else
                f"the 95% lower bound of a {e.mean_r:+.4f}R edge over {e.n} observations is "
                f"{lb:+.4f}R, which does not exclude zero. Nothing is sized on it"),
    }


def k_eff(n_sleeves: int, rho: float) -> float:
    """Effective independent bets. The same formula independence.py uses, restated for stress."""
    if n_sleeves <= 0:
        return 0.0
    r = max(-0.999, min(0.999, rho))
    return n_sleeves / (1.0 + (n_sleeves - 1) * r)


def stressed_breadth(n_sleeves: int, measured_rho: float,
                     crisis_rho: float = CRISIS_RHO) -> dict[str, Any]:
    """k_eff as measured, and under crisis correlation. The heat budget takes the WORSE.

    An upper bound on the HISTORICAL correlation is not a crisis correlation. In a drawdown,
    dispersion collapses and sleeves that looked independent for a year move together for a
    fortnight -- so heat sized on quiet-period independence is heat sized for the period in which
    it does not matter.
    """
    measured = k_eff(n_sleeves, measured_rho)
    stressed = k_eff(n_sleeves, max(measured_rho, crisis_rho))
    binding = min(measured, stressed)
    return {
        "sleeves": n_sleeves,
        "measured_rho": round(measured_rho, 4), "crisis_rho": crisis_rho,
        "k_eff_measured": round(measured, 4), "k_eff_stressed": round(stressed, 4),
        "k_eff_binding": round(binding, 4),
        "heat_scale_measured": round(math.sqrt(measured), 4),
        "heat_scale_binding": round(math.sqrt(binding), 4),
        "given_up": round(1 - math.sqrt(binding) / math.sqrt(measured), 4) if measured > 0 else 0,
        "why": (f"{n_sleeves} sleeves at a measured rho of {measured_rho:.2f} look like "
                f"{measured:.2f} independent bets; at a crisis rho of {crisis_rho} they are "
                f"{stressed:.2f}. Heat scales with the square root of the WORSE of the two, "
                "which costs size in calm markets and is the only size that survives the regime "
                "that actually produces drawdowns"),
    }


def run() -> dict[str, Any]:
    """A worked pass on the desk's own stated numbers."""
    examples = [
        Edge("hunt5_measured", mean_r=0.159, sd_r=1.10, n=65),
        Edge("hunt5_at_400_obs", mean_r=0.159, sd_r=1.10, n=400),
        Edge("thin_sample", mean_r=0.30, sd_r=1.20, n=12),
    ]
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "edge_z": EDGE_Z, "crisis_rho": CRISIS_RHO, "min_obs": MIN_OBS_FOR_EDGE,
        "edges": [lower_bound(e) for e in examples],
        "breadth": {
            "three_sleeves_quiet": stressed_breadth(3, 0.15),
            "five_sleeves_quiet": stressed_breadth(5, 0.10),
            "already_correlated": stressed_breadth(5, 0.85),
        },
        "direction": ("Both adjustments only ever REDUCE size. Neither can justify a larger "
                      "position than the point estimate and the measured correlation would have "
                      "produced, and that property is fenced rather than promised."),
    }


def main(argv: list[str] | None = None) -> int:
    doc = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"edge confidence: sizing on the {EDGE_Z}-sigma lower bound, crisis rho {CRISIS_RHO}")
    for e in doc["edges"]:
        print(f"   {e['name']:22} point {e['point']:+.4f}R -> size on "
              f"{e['size_on']:+.4f}R  [{e['status']}]")
    for name, b in doc["breadth"].items():
        print(f"   {name:22} k_eff {b['k_eff_measured']:.2f} -> {b['k_eff_binding']:.2f} "
              f"under stress, giving up {b['given_up']:.0%} of heat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
