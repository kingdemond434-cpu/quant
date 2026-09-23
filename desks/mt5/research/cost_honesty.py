"""WHAT THE FLAT-COST ASSUMPTION IS COSTING -- measured, before anything is fed.

`check_enforcement_execution` measured two modules MENTIONED on 2026-09-12: named in other files
only as text, never called. Both were built because the desk's cost model is wrong in a specific,
stated way, and both then sat unread:

  * `cost_surface` -- "spread is a symbol x HOUR state, not one scalar per symbol". universe.json
    carries exactly ONE `median_spread_pts` per symbol and every gate, certificate, stress
    scenario and forward clock charges that flat number at every hour of the day.
  * `carry_state` -- "`grep -i swap engine.py` returns ZERO hits: every backtest, every gate,
    every certificate and every forward clock on this desk charges overnight financing at zero."

An organ that is correct and unread has changed nothing (III.16), and these two are unread about
the two costs that decide whether a marginal edge is real.

WHY THIS MEASURES RATHER THAN FEEDS, and the restraint is the point. Wiring either number
straight into `engine.py` would change what every gate computes, which retroactively moves every
certificate the desk holds -- 67 of them, earned against a fixed trial wall. That is a decision
with a blast radius, and it is the CEO docket's to take on evidence, not a wiring change to make
in passing. So this calls both modules for real, on the live book, and publishes the SIZE of the
error: how much edge the flat assumption is manufacturing, per symbol, per hour, in R.

If the answer is small the desk learns its certificates are honest. If it is large, that is the
single highest-value finding available, because it means the gates have been passing cells whose
edge is an artefact of a cost number nobody measured -- and no amount of extra breadth fixes a
book sized on gross returns it can never capture.

    python desks/mt5/research/cost_honesty.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "COST_HONESTY.json"

#: Hours to sample for the spread comparison. The desk's live windows sit in the Asia, London and
#: New York sessions, so these span all three plus the thin hours between -- where a flat spread
#: is most wrong and where a breakout family is most likely to be filled.
HOURS = (0, 3, 7, 10, 13, 14, 16, 19, 21)


def _live_rows() -> list[dict[str, Any]]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    return [r for r in rows if isinstance(r, dict)
            and str(r.get("status", "")).upper() == "LIVE"]


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import carry_state
        import cost_surface
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"cost modules not importable ({exc}) -- UNMEASURED, never 'no error'"}

    try:
        surface = cost_surface.build()
    except Exception as exc:
        surface = {}
        surface_err = f"{type(exc).__name__}: {exc}"
    else:
        surface_err = None
    try:
        carry = carry_state.build()
    except Exception as exc:
        carry = {}
        carry_err = f"{type(exc).__name__}: {exc}"
    else:
        carry_err = None

    try:
        registry = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        registry = {}
    reg_syms = registry.get("symbols") if isinstance(registry, dict) else None
    reg_syms = reg_syms if isinstance(reg_syms, dict) else {}

    rows: list[dict[str, Any]] = []
    live = _live_rows()
    symbols = sorted({str(r.get("symbol") or "") for r in live if r.get("symbol")})

    for sym in symbols:
        flat = None
        entry = reg_syms.get(sym) if isinstance(reg_syms.get(sym), dict) else None
        if entry:
            v = entry.get("median_spread_pts")
            flat = float(v) if isinstance(v, (int, float)) else None

        measured: dict[str, float] = {}
        for h in HOURS:
            try:
                pts = cost_surface.spread_pts(surface, sym, h)
            except Exception:
                pts = None
            if pts is not None:
                measured[str(h)] = round(float(pts), 3)

        # THE ERROR IS THE WORST HOUR, NOT THE AVERAGE. A family that fills in one session is
        # charged that session's spread, and averaging over the day is precisely the flattening
        # this module exists to measure. The worst sampled hour is the honest bound on how far a
        # cell's assumed cost can sit below the one it will actually pay.
        worst = max(measured.values()) if measured else None
        ratio = (worst / flat) if (worst is not None and flat) else None

        swaps: dict[str, float | None] = {}
        for side in ("LONG", "SHORT"):
            try:
                swaps[side] = carry_state.swap_per_lot(carry, sym, side)
            except Exception:
                swaps[side] = None

        rows.append({
            "symbol": sym,
            "n_live_sleeves": sum(1 for r in live if r.get("symbol") == sym),
            "flat_spread_pts": flat,
            "measured_spread_by_hour_pts": measured,
            "worst_hour_spread_pts": worst,
            "worst_over_flat": None if ratio is None else round(ratio, 3),
            "swap_cost_per_lot_night": swaps,
            "charged_by_engine": {"spread": "the flat median, at every hour",
                                  "swap": "ZERO -- engine.py has no swap term at all"},
        })

    understated = [r for r in rows if (r.get("worst_over_flat") or 0) > 1.5]
    swap_bearing = [r for r in rows
                    if any(v for v in (r.get("swap_cost_per_lot_night") or {}).values())]
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": ("UNMEASURED" if not rows else
                   ("ATTENTION" if (understated or swap_bearing) else "OK")),
        "n_symbols": len(rows),
        "n_spread_understated": len(understated),
        "n_with_unpriced_swap": len(swap_bearing),
        "surface_error": surface_err,
        "carry_error": carry_err,
        "symbols": rows,
        "boundary": ("MEASURES ONLY. Nothing here feeds the engine: doing so would change what "
                     "every gate computes and retroactively move all 67 certificates, which is "
                     "the CEO docket's decision on evidence, not a wiring change made in "
                     "passing."),
        "why": ("a cell whose assumed cost is below the cost it will pay shows an edge it does "
                "not have, and no amount of extra breadth fixes a book sized on gross returns it "
                "can never capture."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report")
    a = ap.parse_args(argv)
    doc = build()
    print(f"cost honesty: {doc.get('status')}  {doc.get('n_symbols', 0)} symbol(s), "
          f"{doc.get('n_spread_understated', 0)} with spread understated >1.5x, "
          f"{doc.get('n_with_unpriced_swap', 0)} carrying unpriced swap")
    for r in (doc.get("symbols") or [])[:12]:
        wf = r.get("worst_over_flat")
        sw = r.get("swap_cost_per_lot_night") or {}
        print(f"  {r['symbol']:<12} flat={r.get('flat_spread_pts')!s:<8} "
              f"worst_hour={r.get('worst_hour_spread_pts')!s:<8} "
              f"x{wf if wf is not None else '-':<7} swap L/S={sw.get('LONG')}/{sw.get('SHORT')}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
