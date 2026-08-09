#!/usr/bin/env python3
"""STAGE-A SCREEN: cross-venue funding SETTLEMENT-CALENDAR mismatch (R0121, §42 capacity lens).

THE PRE-REGISTERED HYPOTHESIS, stated before any number was looked at. Venues settle perpetual
funding at fixed UTC stamps. If two venues' stamps are OFFSET, a delta-neutral pair (long perp on
one venue, short perp on the other) can be opened after venue B's stamp and closed before venue
B's next one while straddling exactly one of venue A's -- collecting one full settlement and paying
none. The edge would be structural rather than a price view: it exists purely because the calendars
differ, and it is exactly the kind of small, calendar-shaped edge that is too fiddly for a fund
(§42) and therefore plausibly unarbitraged.

THE PREMISE IS TESTABLE BEFORE THE ECONOMICS ARE, AND IT IS TESTED FIRST. "The calendars differ"
has two very different meanings and only one of them supports the trade:
  * NESTED -- both venues anchor to the same instant and one simply settles more often. Binance's
    4h grid (00/04/08/12/16/20 UTC) is a strict SUPERSET of its 8h grid (00/08/16). Every 8h stamp
    coincides with a 4h stamp, so no window contains one and not the other. The mechanism is
    GEOMETRICALLY IMPOSSIBLE here however attractive the funding rates look.
  * OFFSET -- the grids are genuinely displaced in phase. Only then does a capture window exist.
This distinction is measured from the stamps themselves rather than assumed from a venue's docs,
because `fundingIntervalHours` is fetched nowhere in this repo and `libs/data/multiexchange.py`'s
own docstring asserts "8h funding" for two venues that also run 4h and 1h symbols. A CONFIGURED
CONSTANT IS NOT EVIDENCE OF A CADENCE (L1.46).

WHAT THIS SCREEN REFUSES TO DO. It does not invent the cost of a leg it has never executed. The
desk's measured cost model (`data/cost_model.json`) covers Binance spot+perp pairs and nothing
else, so for any second venue the round-trip cost is UNMEASURED -- and the screen's headline output
is therefore a BREAKEVEN THRESHOLD ("this pays only if the second leg round-trips below X bps")
rather than a verdict computed from a fee schedule recalled from memory. A screen that quotes a
number it did not measure is how a dead mechanism gets a forward slot.

ZERO PROMOTION AUTHORITY (L1.6). Stage A screens; it never promotes and never sizes.

    python scripts/screen_funding_interval_mismatch.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd  # noqa: E402

from libs.alpha_factory.hypothesis_novelty import PriorIdea, hypothesis_novelty  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_SETTLEMENTS = _ROOT / "data/funding_settlements"
_BITMEX = _ROOT / "data/bitmex_funding.jsonl"
_COST_MODEL = _ROOT / "data/cost_model.json"
_OUT = _ROOT / "reports/screen_funding_interval_mismatch.json"

#: Symbols with fewer settlements than this cannot support a phase claim.
_MIN_SETTLEMENTS = 50

#: A series is usable if at least this share of its stamps land at ONE phase of a grid at its own
#: measured interval -- WHICHEVER phase that is. Testing for phase 0 specifically would be exactly
#: backwards: an OFFSET venue has ~zero share at phase 0 by definition, so a phase-0 usability test
#: silently discards the only case this screen exists to find. (It did, on the first run: BitMEX is
#: 100% consistent at phase 4.0 and was dropped as NO-DATA.) A series that CHANGED interval
#: mid-history is the thing being excluded, and it shows up as a LOW dominant share.
_ON_GRID_MIN = 0.95

_STATEMENT = (
    "cross-venue perpetual funding settlement-calendar mismatch: hold a delta-neutral perp pair "
    "across venue A's funding stamp and exit before venue B's, collecting one settlement while "
    "paying none, because the venues' settlement grids are offset in phase"
)

#: The graveyard this must not re-dig. Cross-venue funding has been screened here before.
_PRIORS = (
    PriorIdea(id="R0115_funding_spread",
              statement="cross-venue funding rate SPREAD: capture the level difference between "
                        "two venues' funding rates on the same symbol",
              features=("funding", "cross-venue", "spread", "level"),
              lesson="a LEVEL/spread ask -- different mechanism from a settlement-PHASE ask, but "
                     "the same two legs and the same two round trips have to be paid"),
    PriorIdea(id="kimchi_premium",
              statement="cross-venue price premium between a domestic and an offshore venue "
                        "captured by holding both legs",
              features=("cross-venue", "premium", "two-leg"),
              lesson="REFUTED at full 8.2y depth; the early positive was a timestamp artifact -- "
                     "never cite it as a positive result"),
    PriorIdea(id="carry_fee_pathology",
              statement="hold a spot+perp carry pair and collect funding across settlements",
              features=("funding", "carry", "two-leg", "round-trip"),
              lesson="88.3% of the live carry book's loss was FEES (70.5bps realised vs ~5bps "
                     "venue taker max) -- any short-hold two-leg mechanism is cost-dominated "
                     "until proven otherwise"),
)


def _phase_profile(stamps: pd.Series) -> dict[str, Any]:
    """Interval and grid phase MEASURED from the stamps -- never read from a venue's docs."""
    t = pd.to_datetime(stamps, utc=True).sort_values()
    if len(t) < _MIN_SETTLEMENTS:
        return {"n": len(t), "usable": False, "why": "too few settlements for a phase claim"}
    interval_h = float((t.diff().dropna().dt.total_seconds() / 3600.0).median())
    if not (interval_h > 0):
        return {"n": len(t), "usable": False, "why": "no positive median interval"}
    hours = (t.dt.hour * 60 + t.dt.minute) / 60.0
    phase = (hours % interval_h).round(2)
    share = phase.value_counts(normalize=True)
    dominant = float(share.iloc[0])
    return {
        "n": len(t), "usable": dominant >= _ON_GRID_MIN,
        "interval_h": round(interval_h, 3),
        "dominant_phase_h": float(share.index[0]),
        "share_at_dominant_phase": round(dominant, 4),
        "share_on_utc_midnight_grid": round(float(share.get(0.0, 0.0)), 4),
        "why": ("" if dominant >= _ON_GRID_MIN else
                "stamps are not consistently on one grid -- most likely the venue CHANGED this "
                "symbol's interval mid-history, so a single-interval phase claim does not hold"),
        "first": t.iloc[0].isoformat(), "last": t.iloc[-1].isoformat(),
    }


def _grid_stamps(phase_h: float, interval_h: float | None) -> str:
    """The UTC hours a grid actually fires at, DERIVED from its measured phase and interval.

    Written out rather than described because "a 4h offset" is ambiguous about direction while
    "04/12/20 against 00/08/16" is not -- and because deriving it means the sentence cannot go on
    asserting a venue's calendar after that venue moves it.
    """
    if not interval_h or interval_h <= 0:
        return "?"
    n = max(1, round(24.0 / float(interval_h)))
    return "/".join(f"{(phase_h + i * float(interval_h)) % 24:02.0f}" for i in range(n))


def _phase_offset(other_phase: float, base_phases: set[float]) -> float:
    """Smallest displacement between a venue's grid phase and the reference venue's MEASURED ones.

    THE BUG THIS EXISTS TO PREVENT: the first version wrote `offset = bm_phase - 0.0`, which is an
    offset only while Binance happens to sit at phase 0. It reads a venue's ABSOLUTE phase as
    though it were a DIFFERENCE, so the day Binance re-anchors -- the precise event this screen is
    scheduled to catch -- the headline number would silently keep quoting BitMEX's own phase and
    the report would claim an offset that no longer exists. The nearest phase is the right
    reference because a window must avoid EVERY reference stamp, not just the closest one to
    midnight.
    """
    return min(abs(float(other_phase) - float(bp)) for bp in base_phases) if base_phases else 0.0


def _binance_profiles() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not _SETTLEMENTS.exists():
        return out
    for p in sorted(_SETTLEMENTS.glob("*.parquet")):
        try:
            df = pd.read_parquet(p)
        except (OSError, ValueError):
            continue
        if "timestamp" not in df.columns or "funding" not in df.columns:
            continue
        prof = _phase_profile(df["timestamp"])
        prof["abs_funding_bps"] = {
            "median": round(float(df["funding"].abs().median()) * 1e4, 4),
            "p90": round(float(df["funding"].abs().quantile(0.90)) * 1e4, 4),
            "p99": round(float(df["funding"].abs().quantile(0.99)) * 1e4, 4),
            "max": round(float(df["funding"].abs().max()) * 1e4, 4),
        }
        out[p.stem] = prof
    return out


def _bitmex_profile() -> dict[str, Any]:
    if not _BITMEX.exists():
        return {"usable": False, "why": "data/bitmex_funding.jsonl absent"}
    rows = []
    malformed = 0
    for line in _BITMEX.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(r, dict) and r.get("timestamp"):
            rows.append(r)
        else:
            malformed += 1
    if not rows:
        return {"usable": False, "why": "no parseable rows", "malformed": malformed}
    df = pd.DataFrame(rows)
    prof = _phase_profile(pd.to_datetime(df["timestamp"], utc=True, format="ISO8601"))
    prof["symbols"] = sorted(set(df.get("symbol", pd.Series(dtype=str)).dropna().tolist()))
    prof["malformed_rows"] = malformed
    return prof


def _roundtrip_bps(symbol: str) -> float | None:
    """Measured Binance pair round trip at $500, or None. NEVER a default (L1.41 refusal path)."""
    try:
        cm = json.loads(_COST_MODEL.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    leg = ((cm.get("symbols") or {}).get(symbol) or {}).get("pair") or {}
    v = (leg.get("500") or {}).get("pair_roundtrip_bps")
    return float(v) if isinstance(v, (int, float)) else None


def build_report() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    nov = hypothesis_novelty(_STATEMENT,
                             features=("funding", "cross-venue", "settlement-phase", "calendar",
                                       "two-leg"),
                             priors=list(_PRIORS))

    binance = _binance_profiles()
    bitmex = _bitmex_profile()

    usable = {k: v for k, v in binance.items() if v.get("usable")}
    by_interval: dict[str, int] = {}
    off_grid: list[str] = []
    for sym, prof in binance.items():
        by_interval[f"{prof.get('interval_h')}h"] = by_interval.get(f"{prof.get('interval_h')}h",
                                                                    0) + 1
        if not prof.get("usable"):
            off_grid.append(sym)

    # ---- TRIAL 1: intra-Binance interval heterogeneity (8h vs 4h) -------------------------
    # The deepest corpus the desk owns, and the one an "intervals differ" reading points at first.
    binance_phases = {round(p["dominant_phase_h"], 2) for p in usable.values()}
    # The DENSEST measured interval is the honest reference grid: it is the tightest constraint a
    # capture window has to thread, and taking it from the data means the report describes the
    # venue's calendar as it is rather than as it was when this line was written.
    dense_iv = min((float(p["interval_h"]) for p in usable.values() if p.get("interval_h")),
                   default=None)
    nested = binance_phases == {0.0}
    trial_intra = {
        "trial": "intra_venue_binance_8h_vs_4h",
        "n_symbols": len(usable),
        "intervals_seen": by_interval,
        "distinct_grid_phases": sorted(binance_phases),
        "verdict": "IMPOSSIBLE-NESTED" if nested else "OFFSET-CANDIDATE",
        "why": (
            "every usable symbol settles at phase 0 of a UTC-midnight-anchored grid, so the 4h "
            "grid (00/04/08/12/16/20) is a strict SUPERSET of the 8h grid (00/08/16). Every 8h "
            "stamp coincides with a 4h stamp; no window contains one and not the other. The "
            "mechanism is geometrically impossible within this venue regardless of rate levels."
            if nested else
            "at least one symbol settles off the UTC-midnight grid -- a capture window may exist"),
    }

    # ---- TRIAL 2: cross-venue Binance vs BitMEX ------------------------------------------
    trial_cross: dict[str, Any] = {"trial": "cross_venue_binance_vs_bitmex"}
    bm_phase = bitmex.get("dominant_phase_h")
    if not bitmex.get("usable"):
        trial_cross.update({"verdict": "NO-DATA", "why": bitmex.get("why", "unusable")})
    elif bm_phase in binance_phases:
        trial_cross.update({"verdict": "IMPOSSIBLE-NESTED",
                            "why": f"BitMEX settles at the same grid phase ({bm_phase}h) "
                                   f"as Binance -- no capture window"})
    else:
        # A genuine phase offset. Price it, and refuse to price the leg we have never executed.
        offset_h = _phase_offset(bm_phase, binance_phases)
        btc = binance.get("BTCUSDT", {})
        gross = (btc.get("abs_funding_bps") or {}).get("median")
        rt = _roundtrip_bps("BTCUSDT")
        breakeven = (round(gross - rt, 4) if gross is not None and rt is not None else None)
        trial_cross.update({
            "verdict": "GEOMETRICALLY-FEASIBLE",
            "binance_grid_phase_h": sorted(binance_phases),
            "bitmex_grid_phase_h": bm_phase,
            "bitmex_interval_h": bitmex.get("interval_h"),
            "bitmex_symbols": bitmex.get("symbols"),
            "bitmex_stamps_on_its_own_grid": bitmex.get("share_at_dominant_phase"),
            "phase_offset_h": offset_h,
            "capture_window_h": bitmex.get("interval_h"),
            "why": (f"BitMEX settles at {_grid_stamps(bm_phase, bitmex.get('interval_h'))} UTC "
                    f"against Binance's densest measured grid "
                    f"{_grid_stamps(min(binance_phases), dense_iv)} -- a genuine {offset_h:g}h "
                    f"phase offset, so a window straddling exactly one Binance stamp and no "
                    f"BitMEX stamp DOES exist"),
            "economics_btcusdt": {
                "gross_per_cycle_bps_median": gross,
                "binance_leg_roundtrip_bps_measured": rt,
                "bitmex_leg_roundtrip_bps": None,
                "breakeven_second_leg_roundtrip_bps": breakeven,
                "reading": (
                    f"the pair pays only if a BitMEX XBTUSD round trip costs less than "
                    f"{breakeven} bps. That number is NOT measured on this desk -- "
                    f"data/cost_model.json covers Binance spot+perp pairs only -- so the screen "
                    f"reports the threshold rather than a verdict computed from a fee schedule "
                    f"nobody here has executed against"
                    if breakeven is not None else
                    "breakeven not computable: missing measured gross or Binance leg cost"),
            },
            "unpriced_risks": [
                "THE LEGS ARE NOT THE SAME INSTRUMENT: Binance BTCUSDT is a USDT-margined LINEAR "
                "perp; BitMEX XBTUSD is an INVERSE perp. A long/short pair across them is not "
                "delta-flat -- the inverse leg is convex in price -- so 'structurally free' "
                "understates the position by whatever that convexity and the inter-venue basis "
                "move over the holding window.",
                "BREADTH IS ONE SYMBOL. The desk's BitMEX corpus holds XBTUSD and nothing else, "
                "so this is n=1 cross-sectionally; there is no cohort to Holm-correct against "
                "and no way to separate the mechanism from BTC's own regime.",
                "THE INCUMBENT DOMINATES ON THE STATED BENEFIT. The benefit claimed is 'pay no "
                "funding on the second leg'. A SPOT hedge pays no funding at ANY phase, "
                "unconditionally, and the desk already runs one -- so the calendar trick buys "
                "nothing the existing spot-hedged carry does not already have, while adding a "
                "second venue's round trip and its convexity.",
            ],
        })

    trials = [trial_intra, trial_cross]
    feasible = [t for t in trials if t.get("verdict") == "GEOMETRICALLY-FEASIBLE"]

    if nov.is_redundant:
        status, detail = "REDUNDANT", (
            f"novelty {nov.novelty_score:.2f}: too close to {nov.nearest_id} -- {nov.nearest_lesson}")
    elif not usable:
        status, detail = "NO-DATA", "no usable settlement series -- the premise cannot be tested"
    elif not feasible:
        status, detail = "REFUTED-STRUCTURAL", (
            "the premise fails before the economics are reached: every venue/interval pair with "
            "data on this desk settles on a NESTED grid, where no window collects one venue's "
            "payment and avoids the other's")
    else:
        status, detail = "SCREEN-CONDITIONAL", (
            "one genuinely offset pair exists (Binance 00/08/16 vs BitMEX 04/12/20), so the "
            "mechanism is geometrically real -- but it is n=1, the second leg's execution cost is "
            "unmeasured here, and the benefit it claims is already held unconditionally by the "
            "desk's existing SPOT hedge. Not clock-worthy without a measured BitMEX round trip")

    return {
        "generated": now.isoformat(),
        "row": "R0121",
        "stage": "A (zero promotion authority)",
        "hypothesis": _STATEMENT,
        "status": status,
        "detail": detail,
        "novelty": {"score": round(nov.novelty_score, 4), "nearest": nov.nearest_id,
                    "similarity": round(nov.nearest_similarity, 4),
                    "redundant": nov.is_redundant, "lesson": nov.nearest_lesson},
        "timestamp_alignment": (
            "(a) every series is compared in UTC and ordered by the VENUE's own published "
            "settlement stamp, which is the instant the payment legally occurs -- not by our "
            "receipt time, so no polling cadence enters the phase measurement. (b) intervals and "
            "grid phases are DERIVED from successive stamps, never read from venue documentation "
            "or a configured constant (L1.46). (c) phase is computed modulo each series' OWN "
            "measured interval against a UTC-midnight anchor, so a venue anchoring elsewhere "
            "shows up as a non-zero phase rather than as noise. (d) no look-ahead is possible: "
            "the quantity measured is a calendar property of the stamps themselves, not a "
            "predictive relationship between a signal and a forward return. (e) the funding "
            "magnitudes are the rates published AT each stamp and are joined to no other series."),
        "trials": trials,
        "trial_accounting": {
            "constructions_tried": len(trials),
            "note": ("both constructions are reported whatever they returned, including the one "
                     "that refuted the premise -- reporting only the survivor is the "
                     "garden-of-forking-paths this desk logs trials to prevent"),
        },
        "corpus": {
            "binance_symbols_profiled": len(binance),
            "binance_symbols_usable": len(usable),
            "binance_off_grid_excluded": off_grid,
            "binance_intervals": by_interval,
            "bitmex": {k: v for k, v in bitmex.items() if k != "symbols"} | {
                "symbols": bitmex.get("symbols")},
        },
        "next_action": (
            "NO forward clock. To reopen: measure a BitMEX XBTUSD round trip from real fills (or "
            "a venue-published schedule the desk verifies), then compare against the breakeven "
            "printed here. Until that number exists the mechanism cannot be priced, and it would "
            "still have to beat a spot hedge that pays zero funding at every phase."
            if status == "SCREEN-CONDITIONAL" else
            "NO forward clock; the premise is refuted on the desk's own stamps"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"funding-interval mismatch screen (R0121): {rep['status']}")
        print(f"  {rep['detail']}")
        for t in rep["trials"]:
            print(f"  [{t['trial']}] {t.get('verdict')}: {t.get('why', '')[:150]}")
        print(f"  novelty {rep['novelty']['score']:.2f} vs {rep['novelty']['nearest']}")
        print(f"  next: {rep['next_action']}")
    # A Stage-A screen REPORTS; it is not a gate and must not fail a build.
    return 0


if __name__ == "__main__":
    sys.exit(main())
