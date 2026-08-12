"""EXECUTION-QUALITY DECOMPOSITION -- six components, scored separately (R0334, principal order).

"A mediocre forecast with excellent execution beats the reverse, and a blended score cannot tell
you which one you have." The desk's only discretionary scoreboard is a blended win_rate and mean_R
over the whole sleeve, which cannot distinguish a good thesis exited badly from a bad thesis
rescued by the trailing ladder. This splits the outcome into entry, stop, target, sizing, trade
management and exit timing, and reports each with its own denominator.

WHAT IT REFUSES TO DO, and why each refusal is the point.

NO TARGET EXISTS ON THIS SLEEVE, BY DESIGN. run_conviction_trader.management_plan is explicit --
"there is no take-profit anywhere in here on purpose: the exit is the structure breaking, which is
what lets one trend pay for the losers" -- and derive_stop_pct actively rejects a level on the
profit side. So "target quality" has no ground truth to score. Manufacturing one by inventing a
notional target would be scoring a decision the desk never made; the component reports
UNMEASURABLE-BY-DESIGN and publishes the nearest honest proxy beside it (the forecast's
expected_move_pct against the peak the trade actually reached).

THE STOP CHECK IS A CONSTANT-PASS GATE AND SAYS SO. Measured 2026-08-12: 0 of 17 entries carry a
stop inside the noise band -- because the trader DERIVES the stop from the invalidation level and
widens it past the measured noise floor. A gate that has never once rejected carries zero
information about the trades (L1.49); it measures the constructor, not the decisions. The
informative quantity is the MARGIN by which each stop clears noise, so that is what is scored, and
the constant-pass finding is published rather than reported as a perfect score.

MFE IS HOURLY-SAMPLED AND THEREFORE A LOWER BOUND. The intra-trade R path comes from the resolver's
hourly re-marks, so a peak reached and given back between two marks is invisible. Capture ratio
computed against it is biased UP -- the trade kept a smaller share of its true peak than reported.
Stated on the artifact rather than left for a reader to assume the number is exact.

SIZE IS NOT TOUCHED. R0334 also asks that size auto-reduce as measured expectancy decays. Nothing
here sizes, promotes or gates anything: on 14 paper closes an expectancy estimate is noise, and the
sleeve already owns that decision through its own kill_condition at n=50. Wiring a size response to
this module's output would be sizing on unproven edge, which is the one thing the desk never does.
"""

from __future__ import annotations

import statistics as stats
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

__all__ = ["COMPONENTS", "MIN_N", "Component", "score"]

#: The six components R0334 names, in the order it names them.
COMPONENTS = ("entry_quality", "stop_quality", "target_quality",
              "sizing_quality", "trade_management", "exit_timing")

#: Matches resolve_paper_book.setup_performance -- the desk's standing convention for when a rate
#: over a bucket stops being noise. A component below this publishes INSUFFICIENT, never a number.
MIN_N = 5

MEASURED = "MEASURED"
INSUFFICIENT = "INSUFFICIENT"
BY_DESIGN = "UNMEASURABLE-BY-DESIGN"


@dataclass(frozen=True)
class Component:
    """One axis of execution quality. `value` is None unless state is MEASURED."""

    name: str
    state: str
    value: float | None
    unit: str
    n: int
    why: str
    detail: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "state": self.state, "value": self.value,
                "unit": self.unit, "n": self.n, "why": self.why, "detail": self.detail}


def _thin(name: str, n: int, unit: str, extra: str = "") -> Component:
    return Component(name, INSUFFICIENT, None, unit, n,
                     f"{n} observation(s), fewer than {MIN_N} -- a score on this many is noise "
                     f"wearing a number{extra}", {})


def _median(xs: Sequence[float]) -> float:
    return round(float(stats.median(xs)), 4)


def _r_path(path: Sequence[dict[str, Any]]) -> list[float]:
    """The trade's running R, in mark order. Rows without a numeric R are dropped, not zeroed."""
    out = []
    for row in path:
        r = row.get("realised_R")
        if isinstance(r, (int, float)) and not isinstance(r, bool):
            out.append(float(r))
    return out


def score(entries: Sequence[dict[str, Any]], closes: Sequence[dict[str, Any]],
          paths: dict[str, list[dict[str, Any]]]) -> list[Component]:
    """Six components over the conviction sleeve.

    entries -- rows of data/conviction_book.jsonl (keyed by `at`)
    closes  -- closed marks from data/paper_book_pnl.json carrying realised_R (keyed by `key`)
    paths   -- key -> that trade's hourly re-marks, oldest first
    """
    by_key = {e.get("at"): e for e in entries if e.get("at")}
    out: list[Component] = []

    # ---------------------------------------------------------------- 1. ENTRY QUALITY
    # How much heat the trade took before it ever went favourable, in R. A good entry is close to
    # the level: it should not have to survive a deep excursion first. Measured against the trade's
    # OWN R denominator, so it is comparable across symbols and volatility regimes.
    heat: list[float] = []
    for close in closes:
        rp = _r_path(paths.get(str(close.get("key")), []))
        if rp:
            heat.append(min(rp))
    if len(heat) < MIN_N:
        out.append(_thin("entry_quality", len(heat), "R"))
    else:
        out.append(Component(
            "entry_quality", MEASURED, _median(heat), "R", len(heat),
            "median worst adverse excursion before the trade turned, in R. Less negative is a "
            "better-placed entry; a deep median means entries are being taken away from the level",
            {"worst": round(min(heat), 4), "best": round(max(heat), 4),
             "sampling": "hourly re-marks -- an excursion between two marks is invisible, so the "
                         "true heat is at least this deep"}))

    # ---------------------------------------------------------------- 2. STOP QUALITY
    # The MARGIN by which the stop clears the measured noise floor, not the binary "is it outside".
    # The binary version is a constant-pass gate: the trader derives the stop past the noise floor,
    # so it has never rejected, and a check that never rejects measures the constructor rather
    # than the decisions (L1.49).
    margins: list[float] = []
    inside = 0
    for entry in entries:
        stop = entry.get("stop_pct")
        floor = (entry.get("noise") or {}).get("floor_pct")
        if not isinstance(stop, (int, float)) or not isinstance(floor, (int, float)) or not floor:
            continue
        margins.append(float(stop) / float(floor))
        if stop < floor:
            inside += 1
    if len(margins) < MIN_N:
        out.append(_thin("stop_quality", len(margins), "x noise floor"))
    else:
        out.append(Component(
            "stop_quality", MEASURED, _median(margins), "x noise floor", len(margins),
            "median multiple of the measured noise floor the stop sits at. Below 1.0 the stop is "
            "inside the noise and will be hit by nothing happening",
            {"n_inside_noise": inside,
             "tightest": round(min(margins), 4), "widest": round(max(margins), 4),
             "constant_pass_warning": (
                 f"the binary inside-noise check rejected {inside} of {len(margins)} entries. A "
                 "gate that never rejects carries zero information about the trades (L1.49) -- "
                 "it measures derive_stop_pct doing its job. The margin is the informative "
                 "quantity, which is why it is what is scored."
                 if inside == 0 else
                 f"{inside} of {len(margins)} stops sit INSIDE the noise band -- those are stops "
                 "that will be hit by nothing happening, and each is a defect in its own right")}))

    # ---------------------------------------------------------------- 3. TARGET QUALITY
    # No target exists on this sleeve. The proxy: did the forecast's expected move bracket the peak
    # the trade actually reached? Published as a proxy and labelled one.
    proxy: list[float] = []
    for close in closes:
        ent = by_key.get(str(close.get("key")))
        rp = _r_path(paths.get(str(close.get("key")), []))
        if not ent or not rp:
            continue
        expected = ent.get("expected_move_pct")
        stop_pct = ent.get("stop_pct")
        if not isinstance(expected, (int, float)) or not isinstance(stop_pct, (int, float)):
            continue
        if not stop_pct:
            continue
        expected_r = float(expected) / float(stop_pct)   # the forecast, in the trade's own R units
        if expected_r:
            proxy.append(max(rp) / expected_r)
    detail: dict[str, Any] = {
        "proxy": "peak R reached / forecast move expressed in R",
        "proxy_median": _median(proxy) if len(proxy) >= MIN_N else None,
        "proxy_n": len(proxy),
        "reading": ("above 1.0 the forecast under-called the move that arrived, below 1.0 it "
                    "over-called it. This scores the FORECAST's scale, not a target decision"),
    }
    out.append(Component(
        "target_quality", BY_DESIGN, None, "n/a", len(proxy),
        "this sleeve has no targets on purpose -- management_plan holds until the structure "
        "breaks, and derive_stop_pct refuses a level on the profit side, so there is no target "
        "decision to score. Inventing a notional target would score a decision never made",
        detail))

    # ---------------------------------------------------------------- 4. SIZING QUALITY
    # Was more risk put behind the trades that paid? Rank-agreement between risk taken at entry and
    # R realised. Needs risk to VARY: scoring sizing on a constant risk fraction is scoring nothing.
    pairs: list[tuple[float, float]] = []
    for close in closes:
        ent = by_key.get(str(close.get("key")))
        r = close.get("realised_R")
        if not ent or not isinstance(r, (int, float)):
            continue
        rf = (ent.get("sizing") or {}).get("risk_fraction")
        if isinstance(rf, (int, float)) and rf:
            pairs.append((float(rf), float(r)))
    if len(pairs) < MIN_N:
        out.append(_thin("sizing_quality", len(pairs), "rank corr"))
    elif len({round(p[0], 6) for p in pairs}) < 2:
        out.append(Component(
            "sizing_quality", BY_DESIGN, None, "rank corr", len(pairs),
            "every trade carries the same risk fraction, so there is no sizing decision to score. "
            "A correlation against a constant is undefined, not zero",
            {"risk_fraction": pairs[0][0]}))
    else:
        rho = _spearman([p[0] for p in pairs], [p[1] for p in pairs])
        out.append(Component(
            "sizing_quality", MEASURED, None if rho is None else round(rho, 4), "rank corr",
            len(pairs),
            "rank correlation between risk taken at entry and R realised. Positive means bigger "
            "bets landed on better trades. On this many closes it is a direction, not a finding",
            {"risk_fraction_range": [round(min(p[0] for p in pairs), 6),
                                     round(max(p[0] for p in pairs), 6)]}))

    # ---------------------------------------------------------------- 5. TRADE MANAGEMENT
    # Did the recorded ladder actually get used? stage_reached against the ladder's own depth.
    stages: list[float] = []
    for close in closes:
        reached, top = close.get("stage_reached"), close.get("max_stage")
        if isinstance(reached, (int, float)) and isinstance(top, (int, float)) and top:
            stages.append(float(reached) / float(top))
    if len(stages) < MIN_N:
        out.append(_thin("trade_management", len(stages), "share of ladder"))
    else:
        out.append(Component(
            "trade_management", MEASURED, _median(stages), "share of ladder", len(stages),
            "median share of the recorded add/trail ladder the trade actually climbed. Zero on "
            "most trades means the ladder is a plan the book never reaches, not a plan it declines",
            {"n_never_left_stage_0": sum(1 for s in stages if s == 0.0),
             "n_reached_top": sum(1 for s in stages if s >= 1.0)}))

    # ---------------------------------------------------------------- 6. EXIT TIMING
    # Capture ratio: the share of the peak the trade actually kept. Only defined on trades that
    # HAD a peak -- a trade that never went favourable has no capture to measure, and folding it
    # in as 0.0 would blame the exit for an entry that never worked.
    caps: list[float] = []
    no_peak = 0
    for close in closes:
        rp = _r_path(paths.get(str(close.get("key")), []))
        r = close.get("realised_R")
        if not rp or not isinstance(r, (int, float)):
            continue
        peak = max(rp)
        if peak <= 0:
            no_peak += 1
            continue
        caps.append(float(r) / peak)
    if len(caps) < MIN_N:
        out.append(_thin("exit_timing", len(caps), "capture ratio",
                         f" ({no_peak} trade(s) never went favourable and have no peak to keep)"))
    else:
        out.append(Component(
            "exit_timing", MEASURED, _median(caps), "capture ratio", len(caps),
            "median share of the trade's peak R that survived to the exit. 1.0 means exiting at "
            "the high; low means the trailing rule is giving back what the thesis earned",
            {"n_no_favourable_peak": no_peak,
             "bias": "MFE is hourly-sampled, so the true peak is at least this high and the true "
                     "capture ratio is at most this good"}))

    return out


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Rank correlation. None when either side is constant -- undefined, not zero."""
    n = len(xs)
    if n < 2:
        return None

    def _rank(vals: Sequence[float]) -> list[float]:
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rx, ry = _rank(xs), _rank(ys)
    if len(set(rx)) < 2 or len(set(ry)) < 2:
        return None
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return None if dx == 0 or dy == 0 else num / (dx * dy)
