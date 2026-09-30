#!/usr/bin/env python3
"""REGIME-SPLIT RESEARCH: label every bar by regime, search each regime alone, kill with purged
walk-forward, donate only the survivors to the gauntlet.

    python desks/mt5/research/regime_split_miner.py [--symbol EURUSD ...] [--budget-s 1800]

WHAT IT REVERSE-ENGINEERS (principal, 2026-09-30). A solo operator's overnight research loop on
NAS100: M1 history -> an HMM labels every candle by regime -> the dataset is split by regime and
never optimised on blended data -> candidates proposed per regime -> backtested -> optimised ->
purged walk-forward kills the overfit -> only survivors enter the library. 28 strategy/regime
pairs tested, 26 killed, 2 survived with every fold passing. His stated reason: "most
strategies fail not because the logic is wrong but because they are optimised across mixed
market regimes where the edge disappears."

ON THIS DESK, EVERY STAGE IS AN EXISTING ORGAN EXCEPT THE SPLIT ITSELF:

    label      `libs.regime.control_room`: vol tercile x trend/range per instrument, per day,
               causal with no fitted parameters (the HMM of `libs.regime.bar_states` fits its
               emissions on a training window; a label that must be causal inside a family call
               on the whole history cannot use it without leaking, so the transparent reading is
               the one the gauntlet can re-execute exactly)
    generate   every registered PRICE-ONLY family at its own defaults, per regime -- the regime
               is the only thing searched, so the split adds 6 cells per family, not a grid
    backtest   `proposer_common.screen`: fill at the next open, non-overlapping, net of the
               instrument's round trip, artifact hours refused -- the same screen every proposer
               uses
    walk-fwd   the regime's trades cut into FOLDS contiguous time folds; trades within EMBARGO
               bars of a fold boundary are purged; a survivor needs every measured fold net
               positive and at least FOLDS-1 folds measured
    deflate    `proposer_common.deflate` over the WHOLE sweep, so each regime cell pays for every
               other one tried
    library    survivors donate as family `regime_split` (`mt5desk.families_orthogonal`) through
               `proposer_common.donate` -- the same door as every proposer, judged by the same
               ten gates. No parallel library.

Each row also carries the base family's BLENDED result on the same bars, so the report says for
every survivor whether the split found an edge the blended test hid.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families as fam  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402

from research import proposer_common as pc  # noqa: E402

SOURCE = "regime_split_miner"
REPORT = _DESK / "reports" / "regime_split_miner.json"
#: Price-only base families: each runs from bars alone, so the gauntlet can rebuild it exactly.
BASE_FAMILIES: tuple[str, ...] = (
    "trend_ma_cross", "mean_reversion_rsi", "mean_reversion_bollinger", "volatility_squeeze",
    "range_reversion", "pullback_entry", "overnight_drift", "vol_transition",
    "vol_mean_reversion", "overnight_gap_decay", "drawdown_conditional", "turn_of_month")
VOLS = ("low", "mid", "high")
TRENDS = ("trend", "range")
FOLDS = 5
EMBARGO = 24
MIN_FOLD_TRADES = 5
CORE = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY",
        "GBPJPY", "AUDJPY", "XAUUSD", "XAGUSD")


def _base_fn(name: str) -> Any:
    return getattr(fam, f"family_{name}", None) or fo.ORTHOGONAL_FAMILIES.get(name)


def purged_walk_forward(pnl: list[float], entry_pos: list[int], n_bars: int, cost: float,
                        folds: int = FOLDS, embargo: int = EMBARGO) -> dict[str, Any]:
    """Cut the bar range into `folds` contiguous folds; purge trades within `embargo` bars of a
    boundary; score each fold's mean net return. Passes when every measured fold is net positive
    and at least `folds - 1` folds are measured (>= MIN_FOLD_TRADES trades)."""
    edges = np.linspace(0, n_bars, folds + 1).astype(int)
    per: list[dict[str, Any]] = []
    pos = np.asarray(entry_pos, dtype=int)
    r = np.asarray(pnl, dtype=float) - cost
    for k in range(folds):
        lo, hi = edges[k], edges[k + 1]
        m = (pos >= lo + (embargo if k > 0 else 0)) & (pos < hi - (embargo if k < folds - 1 else 0))
        n = int(m.sum())
        per.append({"fold": k, "n": n,
                    "net_mean": round(float(r[m].mean()), 8) if n else None})
    measured = [f for f in per if f["n"] >= MIN_FOLD_TRADES]
    ok = len(measured) >= folds - 1 and all(f["net_mean"] > 0 for f in measured)
    return {"passed": bool(ok), "measured": len(measured), "folds": per}


def sweep_symbol(sym: str, meta: dict, deadline: float) -> tuple[list[dict], str | None]:
    d = pc.bars(sym)
    if d is None or len(d) < 24 * 400:
        return [], "under 400 days of H1 bars"
    cost = pc.cost_frac(sym, meta, d["close"])
    if cost is None:
        return [], "no contract terms to price the round trip"
    unfillable = pc.artifact_hours(d)
    rows: list[dict] = []
    for base in BASE_FAMILIES:
        if time.monotonic() > deadline:
            break
        if _base_fn(base) is None:
            continue
        blended = pc.screen(d, _base_fn(base)(d), cost, unfillable)
        for v in VOLS:
            for t in TRENDS:
                params = {"base_family": base, "vol": v, "trend": t}
                sig = fo.family_regime_split(d, **params)
                sc = pc.screen(d, sig, cost, unfillable, detail=True)
                if sc is None:
                    continue
                wf = purged_walk_forward(sc.pop("pnl"), sc.pop("entry_pos"), len(d), cost)
                rows.append({"cell": f"{sym}.regime_split.{base}.{v}_{t}", "symbol": sym,
                             "params": params, **sc, "walk_forward": wf,
                             "blended": ({k: blended[k] for k in ("n_independent",
                                                                   "net_per_trade", "t_gross")}
                                         if blended else None)})
    return rows, None


def run(symbols: list[str] | None = None, budget_s: float = 1800.0) -> dict[str, Any]:
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    todo = sorted(s for s in (symbols or CORE) if s in have)
    deadline = time.monotonic() + budget_s
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    for sym in todo:
        if time.monotonic() > deadline:
            skipped[sym] = "sweep budget exhausted"
            continue
        got, why = sweep_symbol(sym, meta, deadline)
        if why:
            skipped[sym] = why
        rows.extend(got)
    rows = pc.deflate(rows)
    for r in rows:
        # The walk-forward is a KILL, never a rescue: a row the deflated screen proposed is
        # withdrawn when any measured fold loses; nothing the screen refused is revived by it.
        r["proposed"] = bool(r.get("proposed") and r["walk_forward"]["passed"])
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], "regime_split", dict(r["params"]),
        mechanism=(f"{r['params']['base_family']} traded only when {r['symbol']} is in "
                   f"{r['params']['vol']}-vol {r['params']['trend']} (control-room label of the "
                   "last completed day): the edge a blended-regime test averages away"),
        title=f"{r['cell']}",
        evidence={**{k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                       "cost_frac", "t_gross", "t_deflated_sweep",
                                       "n_tests_sweep")},
                  "walk_forward_measured": r["walk_forward"]["measured"],
                  "blended": r["blended"]},
    ) for r in proposals]
    killed_by_wf = sum(1 for r in rows if r.get("clears_cost") and not r["walk_forward"]["passed"])
    report = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(todo),
              "tests_run": len(rows), "cells_proposed": len(proposals),
              "killed_by_walk_forward": killed_by_wf, "skipped": skipped,
              "design": {"base_families": list(BASE_FAMILIES), "regimes": [f"{v}_{t}" for v in
                                                                         VOLS for t in TRENDS],
                         "folds": FOLDS, "embargo_bars": EMBARGO,
                         "min_fold_trades": MIN_FOLD_TRADES},
              "proposals": proposals, "all": rows}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if cands:
        report["donated"] = str(pc.donate(SOURCE, cands, len(rows)))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=1800.0)
    a = ap.parse_args()
    rep = run(a.symbol, a.budget_s)
    print(json.dumps({k: rep[k] for k in ("symbols_swept", "tests_run", "cells_proposed",
                                          "killed_by_walk_forward", "skipped")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
