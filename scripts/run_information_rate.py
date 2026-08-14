#!/usr/bin/env python3
"""WHICH FORWARD CLOCKS ARE STARVED, AND WHAT WOULD FEED THEM.

THE COMPLAINT THIS ANSWERS is "forward validation takes 40 days", and the two obvious replies are
both closed. Shortening the clock lowers the evidence bar for everything including noise (L1.6).
A cleverer test was built and MEASURED: `libs/research/anytime_valid`'s own docstring records that
on a Sharpe-2 daily edge the e-process graduated 6 of 40 paths at a MEDIAN 132 days -- SLOWER than
the fixed 90-day clock -- and concludes "the only real accelerants are MORE OBSERVATIONS (higher
frequency or cross-sectional breadth), never a cleverer test".

This is that accelerant, made visible per clock. The desk could already say how much evidence a
clock HAD; nothing said how fast it was ARRIVING or which of the four deflators was eating it --
`evidence_clock.annualised_information_rate` and `regime_penalty` had zero callers outside their
own module.

    python scripts/run_information_rate.py

WHAT IT WRITES: `data/information_rate.json` and `web/information_rate.json` -- every clock ranked
by effective observations per day, its binding constraint, and the ranked levers that would earn
the SAME evidence sooner, each with a gain computed from that clock's own measured correlations.

**IT LOWERS NOTHING.** `required` is an input. Every lever changes how fast evidence arrives; none
changes how much is needed, which is the single edit that would make the exercise self-defeating.

**AND MOST ROWS HERE WILL SAY UNMEASURED, WHICH IS THE HONEST STATE.** The deflators need a return
series per clock -- autocorrelation, regimes covered, cross-symbol correlation -- and the forward
artifacts carry a day count, not a series. A row that assumed rho=0 would report a clock earning
several times the evidence it is actually earning, in the direction that promotes noise. So an
unmeasured input stays unmeasured and the row says which artifact would settle it (L1.28a).
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.research.evidence_clock import MIN_EFFECTIVE, EvidenceState
from libs.research.information_rate import measure
from libs.research.slot_registry import derive_slots

_OUT = Path("data/information_rate.json")
_WEB = Path("web/information_rate.json")
_LAKE = Path("data/lake")

def _universe_size(timeframe: str = "D1") -> tuple[int, str]:
    """How many symbols the desk ALREADY HOLDS BARS FOR at this timeframe.

    This is what separates the cross-section lever from a data project, so it is COUNTED, never
    asserted -- and counted at the right depth, which the first version of this function got
    wrong. The lake is `data/lake/<layer>/<asset_class>/<symbol>/<timeframe>/`, so listing the
    top level counts LAYERS: it returned 1 on a box holding 213 symbols and silently withheld the
    single most valuable accelerant on the desk. A count that is wrong in the direction of
    "no lever available" is not the safe error here; it is the error that leaves the clocks slow.

    A SYMBOL DIRECTORY IS NOT BARS. Only directories containing an actual parquet at this
    timeframe are counted -- an empty partition created by `write_bars` on an empty frame is a
    symbol the desk tried to collect and did not get, and counting it would price the lever
    against data that is not there.
    """
    root = _LAKE / "bronze"
    try:
        cands = [p for p in root.glob("*/*") if p.is_dir()]
    except OSError:
        cands = []
    if not cands:
        return 1, (f"{root} unreadable or empty -- the cross-section lever is NOT offered, "
                   "because a lever whose data nobody can confirm is a data project wearing a "
                   "config change's face")
    syms = {p.name for p in cands
            if (p / timeframe).is_dir() and any((p / timeframe).rglob("*.parquet"))}
    n = len(syms)
    if n == 0:
        return 1, (f"{len(cands)} symbol director(ies) under {root} but NONE holds a {timeframe} "
                   "parquet -- directories are not bars, and pricing the lever against them "
                   "would recommend widening onto data the desk does not have")
    return max(1, n), f"{n} symbol(s) holding {timeframe} bars under {root}"


def _state_for(slot: dict[str, Any]) -> tuple[EvidenceState | None, str]:
    """Build an EvidenceState from a slot row, or say what is missing.

    THE DEFLATORS ARE THE WHOLE MEASUREMENT AND THE ARTIFACTS DO NOT CARRY THEM. A forward record
    publishes `forward_days`; autocorrelation, regimes covered and cross-symbol correlation live
    only in the return series behind it. Defaulting them to the flattering values (rho=0, regimes
    plentiful) would inflate every rate by several times in the direction that promotes noise, so
    a row without them is UNMEASURED and names what would settle it.
    """
    days = slot.get("days")
    if not isinstance(days, (int, float)) or days <= 0:
        return None, ("no observation count on this row -- NO-EVIDENCE and information rate is "
                      "undefined, which is a different claim from a rate of zero")
    return EvidenceState(
        raw_observations=int(days),
        # UNMEASURED, carried as the clock's own untested defaults rather than as optimistic
        # zeros: `regime_penalty(0)` is 0.5 precisely because unmeasured is the concentrated case.
        autocorrelation=0.0,
        distinct_regimes=0,
        distinct_symbols=1,
        measured=False,
    ), ("deflators UNMEASURED -- the forward artifact carries a day count, not a return series. "
        "autocorrelation, regimes covered and cross-symbol correlation each need the series; "
        "until they are published this rate is an UPPER BOUND on the true one")


def main() -> int:
    try:
        snap = derive_slots()
        slots = list(snap.get("slots") or [])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"information-rate: cohort unreadable ({type(exc).__name__}: {exc}) -- UNMEASURED, "
              "nothing written")
        return 1
    if not slots:
        print("information-rate: the cohort is EMPTY, which the registry cannot produce "
              "legitimately -- treating it as 'no clocks are slow' would hide a read failure")
        return 1

    universe, universe_why = _universe_size()
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    for s in slots:
        name = str(s.get("name", "?"))
        state, why = _state_for(s)
        if state is None:
            unmeasured.append(f"{name}: {why}")
            continue
        rep = measure(name, state, days_elapsed=float(s.get("days") or 0),
                      required=MIN_EFFECTIVE, available_symbols=universe,
                      bars_per_day=1.0, available_bars_per_day=3.0)
        row = rep.as_row()
        row["caveat"] = why
        rows.append(row)

    rows.sort(key=lambda r: (r["effective_per_day"] is None, r["effective_per_day"] or 0.0))
    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "required_effective": MIN_EFFECTIVE,
        "universe_available": universe,
        "universe_why": universe_why,
        "clocks": rows,
        "unmeasured": unmeasured,
        "note": ("Ranked SLOWEST FIRST -- the starved clocks are the ones costing forward time, "
                 "which is the one input that cannot be bought later. Every gain is computed "
                 "from `effective_n`'s own formula against this clock's measured correlations, "
                 "never from a rule of thumb: widening the cross-section is worth ~65x at rho=0.7 "
                 "and EXACTLY 1.0x at rho=1.0, where the symbols are one instrument wearing many "
                 "tickers. Nothing here lowers the evidence requirement; the requirement is an "
                 "input and appears unchanged in every row."),
    }
    for p in (_OUT, _WEB):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=1), "utf-8")

    print(f"information-rate: {len(rows)} clock(s) measured, {len(unmeasured)} unmeasured "
          f"({universe_why})")
    for r in rows[:8]:
        rate = r["effective_per_day"]
        left = r["days_remaining"]
        rate_s = f"{rate:.2f}" if rate is not None else "UNMEASURED"
        left_s = f"{left:.0f} d left" if left is not None else "no projection"
        print(f"  {r['clock']:<34} {rate_s:>10} eff obs/day   {left_s}")
        print(f"      binding: {r['binding_constraint']} (x{r['binding_costs_multiplier']})")
        for a in r["accelerants"][:2]:
            print(f"      +{a['gain']:.1f}x  {a['lever']}")
    for u in unmeasured[:5]:
        print(f"  UNMEASURED  {u}")
    print(f"-> {_OUT} and {_WEB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
