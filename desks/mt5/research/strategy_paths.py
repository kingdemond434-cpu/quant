"""Per-sleeve return paths on ONE COMMON CLOCK. The file four built capabilities wait on.

WHAT ITS ABSENCE COSTS. `portfolio_monte_carlo.dependence_blindness` reads 2.93x on a constructed
clone book and ~1.0 on an independent one -- the discriminator provably works in both directions
-- and on the REAL book it is UNMEASURED, because `data/strategy_paths.json` does not exist.
Without it the desk cannot compute real `n_eff`, cannot denoise its covariance, cannot run a
dependence-aware Monte Carlo, and cannot answer whether 190 sleeves are 13 bets. Twelve sleeves
sharing one parameter hash stayed invisible until someone counted the hashes by hand.

I SAID THIS FILE COULD NOT BE BUILT. That was wrong and worth recording. The shadow ROW carries
only summaries -- n, cum_r, exp_r, max_dd_r -- so reading a row and concluding "the data was
never recorded" is a reasonable inference and a false one. `shadow_forward` writes a separate
per-sleeve LEDGER beside every row: `ledger_<sym>_<fam>_<win>.json`, one object per trade with
entry_time, exit_time, r_multiple and a phase flag. 173 of them are already on disk. The paths
were there the whole time, one directory over.

THE COMMON CLOCK IS THE WHOLE POINT, and `StrategyPath` says so in its own docstring: index i
must be the same calendar instant in every path, because the method draws index i once and
applies it everywhere. Two series that merely share a LENGTH are not aligned, and a caller who
passes those gets a confident simulation of a portfolio that never existed. So this builds one
daily grid spanning the union of every sleeve's forward window and places every sleeve on it --
including the days a sleeve did not exist yet, which are zeros with `active` false rather than
gaps.

FORWARD TRADES ONLY. Each ledger marks every trade `forward` or `historical` against the sleeve's
own pre-registration boundary. Including the historical leg would feed selection-era evidence into
a covariance estimate and make every sleeve look better correlated with its own backtest than
with the book -- the same contamination `forward_start` exists to prevent (RESEARCH 6d).

AND THE FILE BEING BUILT DOES NOT MAKE THE MEASUREMENT AVAILABLE YET. `portfolio_monte_carlo`
requires MIN_COMMON_MARKS = 60 common periods and the forward window currently spans 19 daily
marks, so it returns None -- correctly. That is the refusal working, not a fault: block-resampling
19 days with a 5-day mean block would produce a confident number about nothing.

A finer grid would not help and would be dishonest. These sleeves trade a few times a week; an
hourly clock adds zeros, not information, and would clear the 60-mark bar with padding. The
window reaches 60 daily marks on its own in about six weeks, and this rebuilds every hour until
it does. Until then `dependence_blindness` on the real book stays UNMEASURED, which is a verdict.

    python desks/mt5/research/strategy_paths.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
SHADOW = BASE / "reports" / "shadow"
ALLOCATION = BASE / "reports" / "pf_allocation.json"
OUT = BASE / "data" / "strategy_paths.json"
REPORT = BASE / "reports" / "STRATEGY_PATHS.json"

#: Forward trades a sleeve needs before its path is worth carrying. Below this the series is
#: almost all zeros and contributes noise to a covariance rather than information.
MIN_TRADES = 3


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _day(stamp: object) -> date | None:
    s = str(stamp or "").strip()
    if not s or s.lower() in ("none", "nat"):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:26], fmt).date()
        except ValueError:
            continue
    return None


def _ledgers() -> dict[str, list[dict[str, Any]]]:
    """sleeve id -> its FORWARD trades. A ledger with none is dropped, not zero-filled."""
    out: dict[str, list[dict[str, Any]]] = {}
    for f in sorted(SHADOW.glob("ledger_*.json")):
        rows = _read(f, [])
        if not isinstance(rows, list):
            continue
        fwd = [r for r in rows
               if isinstance(r, dict) and str(r.get("phase") or "") == "forward"
               and isinstance(r.get("r_multiple"), (int, float))]
        if len(fwd) >= MIN_TRADES:
            out[f.stem[len("ledger_"):]] = fwd
    return out


def build() -> dict[str, Any]:
    ledgers = _ledgers()
    if not ledgers:
        return {"paths": [], "measured": False,
                "why": f"no ledger under {SHADOW} carries >= {MIN_TRADES} forward trades"}

    # ONE GRID, spanning the union of every sleeve's forward window. A sleeve that did not exist
    # on a given day contributes a zero with active=False -- which is true, and is not the same
    # claim as "it was flat while holding".
    days: dict[str, dict[date, float]] = defaultdict(dict)
    held: dict[str, set[date]] = defaultdict(set)
    lo: date | None = None
    hi: date | None = None
    for sleeve, trades in ledgers.items():
        for t in trades:
            d_out = _day(t.get("exit_time")) or _day(t.get("entry_time"))
            d_in = _day(t.get("entry_time")) or d_out
            if d_out is None:
                continue
            # THE RETURN LANDS ON THE EXIT DAY. A trade's R is only known when it closes, and
            # dating it to entry would place a number on a day nothing could have observed it.
            days[sleeve][d_out] = days[sleeve].get(d_out, 0.0) + float(t["r_multiple"])
            if d_in is not None:
                cur = d_in
                while cur <= d_out:
                    held[sleeve].add(cur)
                    cur += timedelta(days=1)
            lo = d_out if lo is None else min(lo, d_out)
            hi = d_out if hi is None else max(hi, d_out)
            if d_in is not None:
                lo = min(lo, d_in)

    if lo is None or hi is None:
        return {"paths": [], "measured": False, "why": "no dated forward trade in any ledger"}

    grid: list[date] = []
    cur = lo
    while cur <= hi:
        grid.append(cur)
        cur += timedelta(days=1)

    book = (_read(ALLOCATION) or {}).get("book") or {}
    total_heat = sum(float(v) for v in book.values()) or 0.0

    paths: list[dict[str, Any]] = []
    for sleeve, by_day in sorted(days.items()):
        returns = [round(by_day.get(d, 0.0), 6) for d in grid]
        active = [d in held[sleeve] for d in grid]
        # WEIGHT FROM THE ALLOCATOR WHERE IT HAS AN OPINION. A sleeve the allocator does not fund
        # still belongs in the covariance -- it is part of the opportunity set -- so it carries a
        # zero weight rather than being dropped, and the caller can decide.
        w = 0.0
        for name, frac in book.items():
            if sleeve.lower().startswith(str(name).split("_")[0].lower()):
                w = float(frac) / total_heat if total_heat else 0.0
                break
        paths.append({"strategy_id": sleeve, "returns": returns, "active": active, "weight": w})

    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "measured": True,
        "clock": {"start": lo.isoformat(), "end": hi.isoformat(), "n_periods": len(grid),
                  "period": "1D",
                  "why": ("one grid for every path: StrategyPath draws index i once and applies "
                          "it to all, so equal LENGTH is not alignment")},
        "n_paths": len(paths),
        "min_trades": MIN_TRADES,
        "forward_only": True,
        "paths": paths,
    }


def main() -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    # A reader-sized summary beside the payload: the paths themselves are large and nobody reads
    # them by eye, but the shape decides whether the Monte Carlo below is worth believing.
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({k: v for k, v in doc.items() if k != "paths"}, indent=1),
                      encoding="utf-8")
    if not doc.get("measured"):
        print(f"strategy paths: UNMEASURED -- {doc.get('why')}")
        return 1
    c = doc["clock"]
    nz = sum(1 for p in doc["paths"] if any(p["returns"]))
    print(f"strategy paths: {doc['n_paths']} sleeve(s) on a common {c['period']} clock, "
          f"{c['n_periods']} period(s) {c['start']} -> {c['end']}")
    print(f"  {nz} carry a non-zero return; forward trades only, min {MIN_TRADES} per sleeve")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
