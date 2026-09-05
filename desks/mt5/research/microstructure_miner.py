"""Mine the broker's own spread and activity columns for edge, every day, on every instrument.

THE MOAT, CONCRETELY. The audit put the desk's data moat at 5.8/10 and named what would raise
it: broker-specific microstructure nobody else holds in this form. This desk already has it in
every H1 parquet -- Fusion's `spread` and `tick_volume` on every bar for 251 instruments over
years -- and until now read the spread only to charge it. This is the first consumer that reads
those columns to find something.

TWO OUTPUTS.

1. THE SURFACES: per instrument, spread and activity by (weekday, hour) -- the venue's own map
   of when it is cheap and deep. Written to `reports/MICROSTRUCTURE_SURFACES.json` and consumed
   by `cost_surface` (which had only the symbol x hour marginal) and by the liquidity state.

2. THE PROPOSALS: `family_spread_state` cells -- spike reversion and calm continuation -- swept
   over the family's thresholds per instrument, screened with the shared proposer screen
   (artifact guard, non-overlapping, net of cost, self-deflated) and donated into the miner
   contract for the ten gates. Same door as every proposer.

WHY IT IS ORTHOGONAL. A spread state is a fact about the BOOK, not about price. A breakout
family and this family can fire on the same bar for opposite reasons, and the second one knows
something the first cannot: whether the move happened in a deep market or a hollow one.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.family_spread_state import MODES, family_spread_state  # noqa: E402

from research import proposer_common as pc  # noqa: E402

SOURCE = "microstructure"
REPORT = _DESK / "reports" / "microstructure_miner.json"
SURFACES = _DESK / "reports" / "MICROSTRUCTURE_SURFACES.json"
SPIKE = (0.90, 0.95, 0.98)
CALM = (0.10, 0.20)
MOVES = (0.5, 1.0)
HOLDS = (4, 8, 12)


def surface(d: pd.DataFrame) -> dict:
    """Median spread and activity by (weekday, hour), plus the cheapest and deepest windows."""
    if "spread" not in d.columns:
        return {}
    g = d.groupby([d.index.dayofweek, d.index.hour])
    sp = g["spread"].median()
    out = {"spread_by_dow_hour": {f"{int(k[0])}:{int(k[1])}": float(v) for k, v in sp.items()},
           "spread_median": float(d["spread"].median()),
           "spread_p95": float(d["spread"].quantile(0.95))}
    if "tick_volume" in d.columns:
        act = g["tick_volume"].median()
        out["activity_by_dow_hour"] = {f"{int(k[0])}:{int(k[1])}": float(v) for k, v in act.items()}
        ratio = (sp / sp.median()) / (act / act.median()).replace(0, np.nan)
        best = ratio.dropna().nsmallest(5)
        out["cheapest_deepest_windows"] = [f"dow{int(k[0])}:h{int(k[1])}" for k in best.index]
        worst = ratio.dropna().nlargest(5)
        out["dearest_thinnest_windows"] = [f"dow{int(k[0])}:h{int(k[1])}" for k in worst.index]
    return out


def run(symbols: list[str] | None = None, budget_s: float = 1500.0) -> dict:
    meta = pc.universe_meta()
    have = sorted(p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet"))
    if symbols:
        want = {s.upper() for s in symbols}
        have = [s for s in have if s.upper() in want]
    rows: list[dict] = []
    surfaces: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    started = time.monotonic()
    for sym in have:
        if time.monotonic() - started > budget_s:
            skipped[sym] = "budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < 24 * 250 or "spread" not in d.columns:
            skipped[sym] = "no spread column or under 250 days"
            continue
        surfaces[sym] = surface(d)
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms"
            continue
        unfillable = pc.artifact_hours(d)
        for mode in MODES:
            grid = ([{"spike_pct": s} for s in SPIKE] if mode == "spike_reversion"
                    else [{"calm_pct": c} for c in CALM])
            for extra in grid:
                for mv in MOVES:
                    for hold in HOLDS:
                        params = {"mode": mode, "min_move_atr": mv, "hold_bars": hold, **extra}
                        sig = family_spread_state(d, **params)
                        sc = pc.screen(d, sig, cost, unfillable)
                        if sc is None:
                            continue
                        rows.append({"cell": f"{sym}.spread_state.{mode}", "symbol": sym,
                                     "params": params, **sc})
    rows = pc.deflate(rows)
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "spread_state", dict(r["params"]),
        mechanism=("the broker's own spread state: " +
                   ("a spread spike on a moving bar is liquidity, not information; fade it"
                    if r["params"]["mode"] == "spike_reversion" else
                    "a tight, active book carries the move made in it")),
        title=f"{r['cell']} {r['params']}",
        evidence={k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                    "cost_frac", "t_gross", "t_deflated_sweep",
                                    "n_tests_sweep")},
    ) for r in proposals]
    SURFACES.parent.mkdir(parents=True, exist_ok=True)
    SURFACES.write_text(json.dumps({"generated_at": datetime.now(tz=UTC).isoformat(),
                                    "symbols": surfaces}, indent=1), "utf-8")
    report = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(surfaces),
              "tests_run": len(rows), "cells_proposed": len(proposals), "skipped": skipped,
              "proposals": proposals, "all": rows}
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if cands:
        report["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=1500.0)
    a = ap.parse_args()
    rep = run(symbols=a.symbol, budget_s=a.budget_s)
    print(f"MICROSTRUCTURE MINER  {rep['symbols_swept']} surfaces, {rep['tests_run']} tests, "
          f"{rep['cells_proposed']} proposed")
    for r in rep["proposals"][:15]:
        print(f"  {r['cell']:32s} {r['params']!s:58s} n={r['n_independent']:4d} "
              f"net={r['net_per_trade']:+.6f} t={r['t_gross']:+.2f} "
              f"t_defl={r['t_deflated_sweep']:+.2f}")
    print(f"surfaces: {SURFACES}   report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
