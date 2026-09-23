"""Propose regime-transition cells into the gauntlet, so the family runs without being asked.

`family_regime_transition` exists and is registered, but a registered family only runs when a
candidate names it. Nothing did. This sweeps the book's symbols across the family's own
hypothesis space -- hazard threshold, minimum regime age, both side modes -- scores each cell on
its forward returns net of cost, deflates by everything tried, and donates the survivors as
EXACT_RECIPE. Same proposer contract as `factor_residual_engine` and `plumbing_miner`; same door.

WHY THE SEARCH IS SMALL AND SLOW. Each cell walk-forward refits a regime engine on the daily
series -- around 40s per symbol with the default windows -- so this is budgeted, scoped to book
symbols, and run daily rather than hourly. Cadence is multiplicity: re-running a fixed search
every hour against the same deflation is how a survivor gets manufactured.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.family_regime_transition import DEFAULT_REFIT, DEFAULT_WINDOW, family_regime_transition  # noqa: E402
from research import proposer_common as pc                                                          # noqa: E402

SOURCE = "transition_alpha"
REPORT = _DESK / "reports" / "transition_alpha.json"
ENTRY_P = (0.15, 0.25, 0.35)
MIN_AGE = (3, 10)
HORIZON_DAYS = (1,)
SIDES = ("exhaustion", "expansion")


def _book_symbols() -> list[str]:
    try:
        from research.state_vector_build import book_symbols
        return book_symbols()
    except Exception:                                            # noqa: BLE001
        return []


def run(symbols: list[str] | None = None, budget_s: float = 2400.0,
        window: int = DEFAULT_WINDOW, refit_days: int = DEFAULT_REFIT) -> dict:
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    todo = [s for s in (symbols or _book_symbols()) if s in have]
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    started = time.monotonic()
    for sym in sorted(set(todo)):
        if time.monotonic() - started > budget_s:
            skipped[sym] = "sweep budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < 24 * (window + refit_days):
            skipped[sym] = f"under {window + refit_days} days of H1 bars"
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms to price the round trip"
            continue
        unfillable = pc.artifact_hours(d)
        for h in HORIZON_DAYS:
            for thr in ENTRY_P:
                for age in MIN_AGE:
                    for side_mode in SIDES:
                        params = {"window": int(window), "refit_days": int(refit_days),
                                  "horizon_days": int(h), "entry_p_leave": float(thr),
                                  "min_age": int(age), "side_mode": side_mode}
                        sig = family_regime_transition(d, **params)
                        sc = pc.screen(d, sig, cost, unfillable)
                        if sc is None:
                            continue
                        rows.append({"cell": f"{sym}.regime_transition.{side_mode}",
                                     "symbol": sym, "params": params, **sc})
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "regime_transition", dict(r["params"]),
        mechanism=(f"P(regime ends within {r['params']['horizon_days']}d) >= "
                   f"{r['params']['entry_p_leave']} after age >= {r['params']['min_age']}d: "
                   + ("fade the move the regime made" if r["params"]["side_mode"] == "exhaustion"
                      else "follow the impulse that ends it")),
        title=f"{r['cell']} p>={r['params']['entry_p_leave']} age>={r['params']['min_age']}",
        evidence={k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                    "cost_frac", "t_gross", "t_deflated_sweep",
                                    "n_tests_sweep")},
    ) for r in proposals]
    report = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(todo),
              "tests_run": len(rows), "cells_proposed": len(proposals), "skipped": skipped,
              "proposals": proposals, "all": rows}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if cands:
        report["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=2400.0)
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--refit-days", type=int, default=DEFAULT_REFIT)
    a = ap.parse_args()
    rep = run(symbols=a.symbol, budget_s=a.budget_s, window=a.window, refit_days=a.refit_days)
    print(f"TRANSITION ALPHA  {rep['symbols_swept']} symbols, {rep['tests_run']} tests, "
          f"{rep['cells_proposed']} proposed")
    for r in rep["proposals"]:
        print(f"  {r['cell']:36s} p>={r['params']['entry_p_leave']} "
              f"age>={r['params']['min_age']:2d} n={r['n_independent']:4d} "
              f"net={r['net_per_trade']:+.6f} t={r['t_gross']:+.2f} "
              f"t_defl={r['t_deflated_sweep']:+.2f}")
    for k, v in rep["skipped"].items():
        print(f"  skipped {k}: {v}")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
