"""EXECUTION COST AS AN ALLOCATOR INPUT, priced at the hour each sleeve actually fills.

    "Eventually this should be C_i = f(symbol, hour, spread, vol, event, liquidity, size,
     direction, order type, latency). Now make it AUTHORITY-BEARING. If gross alpha = +0.15R and
     expected execution = -0.06R, allocator sees +0.09R. If current conditions imply -0.18R
     execution: +0.15 - 0.18 = -0.03R, allocation becomes zero automatically. No generic 'avoid
     bad spreads' rule required."                          -- the principal, 2026-09-07

THE DEFECT, AND IT IS ONE LITERAL. `pf_allocator.py` built every sleeve's evidence with

    cost_r=0.05,

-- one constant, every sleeve, every symbol, every hour. The allocator that decides this desk's
capital believed a session-range breakout on EURZAR filling at 01:00 and a gold bracket on an
administered spread carry identical execution risk.

THE DESK HAD ALREADY MEASURED THAT THIS IS FALSE, in `research/cost_surface.py` (L1.5 / L1.28a),
and the measurement reached the gauntlet and never reached the allocator:

    symbol   pooled scalar   spread on its OWN fill bars   error
    USDZAR       329 pts              2028 pts            6.16x
    EURZAR       310 pts              1918 pts            6.19x

Both hold ten-gate certificates and both were on live forward clocks. Re-priced at their own
fill-hour spread at the desk's declared honest 2x baseline, BOTH ARE LOSING SLEEVES. The
allocator was sizing them on returns charged at a number six times too small.

WHAT THIS MODULE COMPUTES, and the one quantity in it that is trustworthy.

The replayed R multiples were charged at the POOLED median spread -- that is the L1.5 defect, and
it is a fact about how the returns were produced. So

    ratio = measured spread at the sleeve's own fill hour / the pooled spread it was charged at

is EXACTLY the factor by which the charge is wrong, and it is measured on both sides. It needs no
stop distance, no contract size and no assumption: it is one measured number divided by another
measured number from the same instrument.

    cost_bias_r = base_cost_r * (ratio - 1)      R per trade the replay UNDER-charged

is then subtracted from the sleeve's posterior mean, deterministically, in proportion to how
often it trades. Positive bias means the sleeve is more expensive than its own returns say and
the allocator now sees it. That is the whole of "authority-bearing": no rule about spreads, no
veto, no threshold -- the growth arithmetic simply gets the right number and a sleeve whose edge
does not survive its own fill hour stops being funded because it stops being profitable.

THE BASE IS THE WEAK HALF AND THE CLIP IS THERE BECAUSE OF IT. `base_cost_r` is a desk-wide
scalar (0.05R), not a per-sleeve measurement, so while `ratio` is measured on both sides the
PRODUCT inherits the base's error. EURZAR's raw ratio at hour 0 is 12.8, which would imply a
0.59R per-trade correction -- larger than most of this desk's entire edges. That may well be
right (it is what `cost_surface` independently concluded), but it must not be applied on the
strength of a scalar nobody measured per sleeve. So the ratio is clipped at `MAX_RATIO` and the
UNCLIPPED value is reported beside it, so the true size of the problem stays legible and the
applied correction stays defensible. The clip is a statement about the base, not about the
spread.

REFUSAL IS THE DEFAULT AND IT COSTS NOTHING. No surface, no reading at that hour, an unknown fill
hour, an administered spread with no hour structure: all return a bias of 0.0, which is exactly
the behaviour before this module existed. A sleeve the desk cannot price is not thereby cheap and
is not thereby expensive -- it is unpriced, and it is NAMED as unpriced so the gap is countable.

THE DENOMINATOR IS TODAY'S REGISTRY, NOT THE SURFACE'S COPY OF IT. `cost_surface` snapshots
`pooled_median_spread_pts` out of the registry at BUILD time, so the file on disk carries whatever
the registry said that day. Reading the snapshot made the 2026-09-07 spread repair invisible --
27 symbols were corrected and every ratio still compared against the pre-repair value, so the
instrument went on pricing nothing. The question is how wrong the charge is TODAY.

THIS NEVER MAKES A SLEEVE CHEAPER THAN ITS RETURNS SAY. `ratio < 1` -- a sleeve filling at an hour
CHEAPER than the pooled scalar it was charged -- is real and `cost_surface` calls it "the
false-null direction, the only one this desk has no instrument for". It is reported, and it is
NOT applied as a credit: crediting it would raise a sleeve's mean on the strength of a cost model,
which is sizing up on a modelling assumption. Under-charging is corrected; over-charging is
reported and left for the replay to fix at source, where it belongs.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "BASE_COST_R",
    "MAX_RATIO",
    "SESSION_FILL_HOUR",
    "cost_ratio",
    "costs_for",
    "fill_hour",
]

MEASURED, UNMEASURED, REGISTRY_DEFECT = "MEASURED", "UNMEASURED", "REGISTRY_DEFECT"

#: The desk-wide per-trade cost scale the allocator has always used. Kept as the BASE so this
#: module changes the DISPERSION across sleeves and not the desk's overall cost level -- a module
#: that quietly moved the level as well would be two changes wearing one name.
BASE_COST_R = 0.05

#: The largest under-charge factor that may be APPLIED. Not a belief about spreads -- the surface
#: measures ratios above 12 and they are real -- but about `BASE_COST_R`, which is a scalar and
#: not a per-sleeve measurement. Multiplying a measured 12.8 by an unmeasured base produces a
#: correction larger than most of this desk's edges on the strength of the unmeasured half. The
#: unclipped ratio is always reported.
MAX_RATIO = 5.0

#: Broker-hour a session sleeve fills at, from the selector its certificate carries. These are the
#: desk's own session definitions; the hour is the FIRST hour of the window, because that is where
#: a breakout or a gap sleeve places its order and where the spread it pays is measured.
#: A sleeve whose selector is not here has an UNKNOWN fill hour and is refused, not guessed.
SESSION_FILL_HOUR: dict[str, int] = {
    "asia": 1, "tokyo": 1, "sydney": 22,
    "london": 8, "europe": 8, "morning": 8,
    "ny": 13, "newyork": 13, "us": 13, "afternoon": 13,
    "overnight": 0, "rollover": 0, "close": 21,
}

_TOKEN = re.compile(r"[^a-z0-9]+")


def fill_hour(selector: str | None, sleeve: str | None = None) -> tuple[int | None, str]:
    """The broker hour this sleeve fills at, or None with the reason. Never a guess.

    A guessed fill hour is worse than no fill hour: it prices the sleeve at an hour it does not
    trade and produces a confident correction in an arbitrary direction. `cost_surface.spread_pts`
    makes the same choice for the same reason -- "a caller that has not said WHEN it fills has not
    asked this question".
    """
    for src in (selector, sleeve):
        if not src:
            continue
        for tok in _TOKEN.split(str(src).lower()):
            if tok in SESSION_FILL_HOUR:
                return SESSION_FILL_HOUR[tok], f"fill hour {SESSION_FILL_HOUR[tok]:02d} from '{tok}'"
    return None, "no session selector names a fill hour; the sleeve is left unpriced"


def cost_ratio(surface: Mapping[str, Any] | None, symbol: str,
               hour: int | None,
               registry: Mapping[str, Any] | None = None) -> tuple[float | None, str,
                                                                   dict[str, Any]]:
    """measured spread at `hour` / the pooled spread the replay actually charged.

    Returns (ratio, why, detail); ratio None is a refusal, and on this desk's current data it is
    a refusal for almost everything. THAT IS THE MEASUREMENT, not a failure of this function --
    see `PROVENANCE` below.
    """
    if not surface:
        return None, "no cost surface on this host", {}
    if hour is None:
        return None, "unknown fill hour", {}
    sym = (surface.get("symbols") or {}).get(str(symbol))
    if not sym:
        return None, f"{symbol} is not in the cost surface", {}

    # PROVENANCE FIRST, AND IT REFUSES ALMOST EVERYTHING TODAY. Measured 2026-09-07 on
    # `data/universe/universe.json`: 241 of 251 symbols carry NO `_provenance` entry for
    # `median_spread_pts` at all. `universe_registry.py` explains why -- three producers write
    # that field with three different meanings ("fetch_universe: median of the H1 spread column;
    # expand_universe: symbol_info.spread; download_all: symbol_info.spread"), and a
    # point-in-time snapshot is not a median. GBPJPY carries 1.0 beside a
    # `spread_pts_at_collection` of 7.0 and measured hourly medians of 13-50.
    #
    # WITHOUT PROVENANCE THE RATIO IS NOT A COST ERROR, IT IS TWO DIFFERENT QUANTITIES DIVIDED.
    # Applying it would have shifted 28 sleeves' posterior means down by up to 0.20R per trade on
    # the strength of a producer inconsistency the desk had already documented. So the number the
    # allocator is charged is refused unless the registry says where its spread came from.
    #
    # THIS IS NOT A PERMANENT REFUSAL AND NEEDS NOBODY TO REMEMBER IT. The moment a symbol's
    # spread is written with a recorded source -- ten already are, from `realized_fills` -- that
    # symbol prices, with no edit here.
    if registry is not None:
        row = (registry.get(str(symbol)) or {}) if isinstance(registry, Mapping) else {}
        src = ((row.get("_provenance") or {}).get("median_spread_pts") or {}).get("source")
        if not src:
            return None, (f"{symbol}: the registry records NO provenance for median_spread_pts, "
                          "so the number the replay charged cannot be attributed to a producer "
                          "and the ratio against it is not a cost measurement. 241 of 251 "
                          "symbols are in this state; `universe_registry` documents the "
                          "three-producer flip that causes it."), {"no_provenance": True}
    # THE DENOMINATOR IS READ LIVE FROM THE REGISTRY, NOT FROM THE SURFACE'S COPY OF IT.
    # `cost_surface` copies `pooled_median_spread_pts` out of the registry AT BUILD TIME, so the
    # surface on disk carries whatever the registry said on the day it was built (2026-08-29
    # here). The question this function asks is "how wrong is the number the replay is charging
    # TODAY", so today's registry is the only correct denominator -- and reading the snapshot
    # instead made the repair of 2026-09-07 invisible: 27 symbols had their spread corrected and
    # every ratio still compared against the pre-repair value.
    reg_row = ((registry.get(str(symbol)) or {}) if isinstance(registry, Mapping) else {})
    pooled = reg_row.get("median_spread_pts")
    pooled_src = "registry (live)"
    if not isinstance(pooled, (int, float)):
        pooled = sym.get("pooled_median_spread_pts")
        pooled_src = "cost surface snapshot"
    cell = (sym.get("hours") or {}).get(str(int(hour)))
    if not isinstance(pooled, (int, float)) or float(pooled) <= 0:
        return None, (f"{symbol}: the registry's median_spread_pts is "
                      f"{pooled!r} -- a REGISTRY DEFECT, not a free instrument. "
                      "`universe_registry` documents this producer flip ('EURUSD reads 12 under "
                      "one producer and 0 under the next'); measured on this surface it affects "
                      "54 of 195 symbols including AUDUSD, AUDJPY, EURCHF and EURCAD. Refused: "
                      "a ratio against zero is not a cost measurement."), {}

    # THE TWO SIDES MUST BE THE SAME QUANTITY BEFORE THEIR RATIO MEANS ANYTHING, and this guard
    # is the whole difference between an execution correction and a units artifact.
    #
    # `pooled_median_spread_pts` is copied from the universe REGISTRY -- the number the replay
    # actually charged -- while the hourly p50s are measured from the H1 bars. When the registry
    # row is sound the pooled scalar lands inside the hourly range (136 of 195 symbols do). When
    # it does not, the ratio is measuring a scale flip and not a spread: GBPJPY carries a pooled
    # 1.0 pt against hourly medians of 13-50, which would read as a 15x under-charge on a MAJOR
    # cross -- flatly contradicting `cost_surface`'s own finding that "the error concentrates in
    # the crosses and exotics" while the majors "return clean".
    #
    # Applying that would have shifted 28 sleeves' posterior means down on a producer bug. It is
    # refused and NAMED, which turns a dangerous correction into a diagnostic.
    measured_hours = [float(r["p50"]) for r in (sym.get("hours") or {}).values()
                      if isinstance(r, Mapping) and str(r.get("status")) == MEASURED
                      and isinstance(r.get("p50"), (int, float))]
    if measured_hours and float(pooled) < min(measured_hours) * (1.0 - 1e-9):
        return None, (f"{symbol}: the registry charges {float(pooled):.1f} pts, BELOW the "
                      f"cheapest hour this desk measured ({min(measured_hours):.1f} pts). A "
                      "median cannot sit under every value it is the median of, so the two "
                      "numbers are not the same quantity -- a registry scale flip, refused "
                      "rather than priced as a cost error."), {"registry_defect": True}
    if not cell or str(cell.get("status")) != MEASURED:
        return None, f"{symbol} hour {hour:02d} is not MEASURED in the surface", {}
    at_hour = cell.get("p50")
    if not isinstance(at_hour, (int, float)) or not math.isfinite(float(at_hour)):
        return None, f"{symbol} hour {hour:02d} carries no median spread", {}
    r = float(at_hour) / float(pooled)
    if not math.isfinite(r) or r <= 0:
        return None, f"{symbol} hour {hour:02d} produced a non-finite ratio", {}
    detail = {"spread_at_hour_pts": float(at_hour), "pooled_spread_pts": float(pooled),
              "pooled_source": pooled_src,
              "hour": int(hour), "administered": str(sym.get("administered", "")) == "True",
              "stress_p90_over_p50": sym.get("stress_p90_over_p50")}
    detail["spread_provenance"] = (
        ((((registry or {}).get(str(symbol)) or {}).get("_provenance") or {})
         .get("median_spread_pts") or {}).get("source") if registry is not None else None)
    return r, (f"{symbol} fills at {hour:02d} where the median spread is {at_hour:.0f} pts "
               f"against the {pooled:.0f} pts the replay charged ({r:.2f}x)"), detail


def costs_for(sleeves: Sequence[Mapping[str, Any]],
              surface: Mapping[str, Any] | None, *,
              registry: Mapping[str, Any] | None = None,
              base_cost_r: float = BASE_COST_R,
              max_ratio: float = MAX_RATIO) -> dict[str, Any]:
    """Per-sleeve execution cost bias, in R per trade, with every refusal named.

    Each entry of `sleeves` needs `name`, `symbol`, and either `selector` or a name that carries
    a session token. Returns `{name: {cost_bias_r, cost_r, ratio, ratio_raw, source, why, ...}}`
    plus a `summary` block, because the COUNT of unpriced sleeves is the finding that decides
    whether this instrument is working: a run that prices three of sixty has not measured
    execution, it has measured three sleeves.
    """
    out: dict[str, Any] = {}
    n_measured = n_under = n_over = n_clipped = n_registry_defect = n_no_provenance = 0
    defect_symbols: set[str] = set()
    worst: tuple[float, str] | None = None
    for s in sleeves:
        name = str(s.get("name") or "")
        if not name:
            continue
        sym = str(s.get("symbol") or "")
        hour, hour_why = fill_hour(s.get("selector"), name)
        ratio, why, detail = cost_ratio(surface, sym, hour, registry)
        if ratio is None:
            if detail.get("no_provenance"):
                n_no_provenance += 1
            bad_registry = bool(detail.get("registry_defect")) or "REGISTRY DEFECT" in why
            if bad_registry:
                n_registry_defect += 1
                defect_symbols.add(sym)
            out[name] = {"cost_bias_r": 0.0, "cost_r": float(base_cost_r), "ratio": None,
                         "source": REGISTRY_DEFECT if bad_registry else UNMEASURED,
                         "why": f"{hour_why}; {why}"}
            continue
        n_measured += 1
        applied = min(float(ratio), float(max_ratio))
        if applied < ratio:
            n_clipped += 1
        # NEVER A CREDIT. A ratio below 1 says the replay OVER-charged this sleeve, which is real
        # and is reported -- but applying it would raise the sleeve's mean on the strength of a
        # cost model, and sizing up on a model is the one direction this desk does not take from
        # an instrument that has never been validated against a real fill.
        bias = float(base_cost_r) * max(0.0, applied - 1.0)
        if ratio > 1.0:
            n_under += 1
            if worst is None or ratio > worst[0]:
                worst = (float(ratio), name)
        elif ratio < 1.0:
            n_over += 1
        out[name] = {
            "cost_bias_r": round(bias, 6),
            # The uncertainty scale moves with the level: a sleeve whose cost is 3x what was
            # charged is not merely more expensive, it is more UNCERTAINLY expensive.
            "cost_r": round(float(base_cost_r) * applied, 6),
            "ratio": round(applied, 4), "ratio_raw": round(float(ratio), 4),
            "clipped": bool(applied < ratio),
            "source": MEASURED, "why": why, **detail,
        }
    n = len(out)
    summary = {
        "n_sleeves": n, "n_measured": n_measured, "n_unpriced": n - n_measured,
        "n_undercharged": n_under, "n_overcharged": n_over, "n_clipped": n_clipped,
        # THE SECOND DEFECT THIS INSTRUMENT FOUND, and it is worse than the one it was built for.
        # A symbol whose registry spread is 0, or below every hour this desk measured, is not a
        # cheap instrument -- it is a broken registry row, and `universe_registry` already
        # documents the producer flip that causes it. Counted and named here because these
        # sleeves are UNPRICED for cost, which means every backtest, gauntlet and certificate on
        # them was scored against a spread nobody can defend.
        "n_registry_defect": n_registry_defect,
        "registry_defect_symbols": sorted(defect_symbols),
        # THE BLOCKING GAP, countable. Every one of these sleeves is charged a spread the
        # registry cannot attribute to any producer -- which means its backtest, its gauntlet
        # verdict and its certificate were all scored against a number nobody can defend.
        # Repairing the registry, not editing this module, is what turns execution into an
        # allocator input.
        "n_no_spread_provenance": n_no_provenance,
        "worst_undercharge": (None if worst is None
                              else {"sleeve": worst[1], "ratio": round(worst[0], 3)}),
        "base_cost_r": float(base_cost_r), "max_ratio": float(max_ratio),
        "rule": ("cost_bias_r = base_cost_r * (min(ratio, max_ratio) - 1), subtracted from the "
                 "posterior mean in proportion to how often the sleeve trades. The RATIO is "
                 "measured on both sides from one artifact; the BASE is a desk-wide scalar, which "
                 "is why the product is clipped and the raw ratio reported. An over-charged "
                 "sleeve is reported and never credited -- correcting it belongs in the replay, "
                 "at source."),
    }
    if n and n_measured == 0:
        summary["verdict"] = ("UNMEASURED: not one sleeve could be priced at its own fill hour. "
                              "Execution is not an allocator input on this host.")
    return {"sleeves": out, "summary": summary}
