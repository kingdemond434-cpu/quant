#!/usr/bin/env python3
"""REGIME-DISAGREEMENT RESEARCH: our own regime systems vote, their disagreement gates every
price-only family, purged walk-forward kills, survivors go to the gauntlet.

    python desks/mt5/research/regime_disagreement_miner.py [--symbol EURUSD ...] [--budget-s 1800]

ROMAN-0806, re-scoped 2026-11-11 after the principal dropped the external "semantic regime"
API: "Disagreement between these regime systems becomes another feature family." The systems
are ours (`libs.regime.disagreement`: control-room, EWMA, GARCH, HMM, Kalman, time-series
momentum, BOCPD); the family is `regime_disagreement` (`mt5desk.families_orthogonal`).

THE SEARCH, stage for stage the regime-split pipeline, so the two charge the same way:

    states     six, one axis at a time: vol split / consensus, trend split / consensus,
               transition fresh / settled
    generate   every price-only base family of `regime_split_miner.BASE_FAMILIES`, at defaults
    screen     `proposer_common.screen`, net of the instrument's round trip
    walk-fwd   `regime_split_miner.purged_walk_forward` -- a KILL, never a rescue
    deflate    over the lifetime union of every (symbol, base, state) cell ever screened
    donate     `proposer_common.donate`, the one door; the ten gates judge

AND IT ANSWERS THE DIRECTIVE'S OWN QUESTION per symbol: does disagreement predict future
realised vol (beyond today's level) and the size of the next move? Those rank correlations are
in the report beside the cells, so a family that trades nothing still leaves a measurement.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_orthogonal as fo  # noqa: E402

from research import proposer_common as pc  # noqa: E402
from research import regime_split_miner as rsm  # noqa: E402

SOURCE = "regime_disagreement_miner"
FAMILY = "regime_disagreement"
REPORT = _DESK / "reports" / "regime_disagreement_miner.json"
CHARGED = _DESK / "data" / "regime_disagreement_charged.json"
TRIALS = _DESK / "data" / "REGIME_DISAGREEMENT_TRIALS.jsonl"
STATES: tuple[tuple[str, str], ...] = (
    ("vol", "split"), ("vol", "consensus"), ("trend", "split"), ("trend", "consensus"),
    ("transition", "fresh"), ("transition", "settled"))


def lane() -> list[str]:
    """Every hypothesis-lane symbol `universe_policy` admits for this family, least-judged
    first (the same rotation the regime split uses)."""
    from research.universe_policy import may_hypothesise
    have = sorted(p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet"))
    ok = [s for s in have if may_hypothesise(s, FAMILY)]
    try:
        from research.breadth_rotation import judged_counts, orthogonal_ring
        return list(orthogonal_ring(ok, FAMILY, counts=judged_counts()))
    except Exception:
        return ok


def _charged() -> dict[str, str]:
    try:
        got = json.loads(CHARGED.read_text("utf-8"))
        return {str(k): str(v) for k, v in got.items()} if isinstance(got, dict) else {}
    except (OSError, ValueError):
        return {}


def charge(rows: list[dict]) -> tuple[int, int]:
    """(cells newly charged this pass, the lifetime union's size). Writes both files."""
    union = _charged()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    new = [str(r["cell"]) for r in rows if str(r["cell"]) not in union]
    for c in new:
        union[c] = now
    CHARGED.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHARGED.with_suffix(".tmp")
    tmp.write_text(json.dumps(union, sort_keys=True), "utf-8")
    tmp.replace(CHARGED)
    if new:
        with TRIALS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": now, "family": FAMILY, "cells_screened": len(new),
                                 "source": SOURCE, "dry_run": False,
                                 "rule": "each (symbol, base, state) cell charged once over "
                                         "the lifetime union"}) + "\n")
    return len(new), len(union)


def sweep_symbol(sym: str, meta: dict, deadline: float) -> tuple[list[dict], dict | None,
                                                                   str | None]:
    d = pc.bars(sym)
    if d is None or len(d) < 24 * 400:
        return [], None, "under 400 days of H1 bars"
    cost = pc.cost_frac(sym, meta, d["close"])
    if cost is None:
        return [], None, "no contract terms to price the round trip"
    from libs.regime.control_room import daily_frame
    from libs.regime.disagreement import predictiveness, readings_for_bars
    try:
        lab = readings_for_bars(d)
        pred = predictiveness(lab, daily_frame(d))
    except Exception as exc:   # a reading that cannot be built is a skip, never a crash
        return [], None, f"regime readings failed: {type(exc).__name__}: {exc}"
    unfillable = pc.artifact_hours(d)
    rows: list[dict] = []
    for base in rsm.BASE_FAMILIES:
        if time.monotonic() > deadline:
            break
        fn = rsm._base_fn(base)
        if fn is None:
            continue
        blended = pc.screen(d, fn(d), cost, unfillable)
        for axis, state in STATES:
            params = {"base_family": base, axis: state}
            sc = pc.screen(d, fo.family_regime_disagreement(d, **params), cost, unfillable,
                           detail=True)
            if sc is None:
                continue
            wf = rsm.purged_walk_forward(sc.pop("pnl"), sc.pop("entry_pos"), len(d), cost)
            rows.append({"cell": f"{sym}.{FAMILY}.{base}.{axis}_{state}", "symbol": sym,
                         "params": params, **sc, "walk_forward": wf,
                         "blended": ({k: blended[k] for k in ("n_independent",
                                                               "net_per_trade", "t_gross")}
                                     if blended else None)})
    return rows, pred, None


def run(symbols: list[str] | None = None, budget_s: float = 1800.0) -> dict[str, Any]:
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    todo = [s for s in symbols if s in have] if symbols else lane()
    deadline = time.monotonic() + budget_s
    rows: list[dict] = []
    skipped: dict[str, str] = {}
    predictive: dict[str, Any] = {}
    for sym in todo:
        if time.monotonic() > deadline:
            skipped[sym] = "sweep budget exhausted"
            continue
        got, pred, why = sweep_symbol(sym, meta, deadline)
        if why:
            skipped[sym] = why
        if pred:
            predictive[sym] = pred
        rows.extend(got)
    rows = pc.deflate(rows)
    new_cells, union_n = charge(rows)
    from research.multiplicity import deflate_t
    for r in rows:
        n = max(int(r.get("n_tests_sweep") or 0), union_n)
        r["n_tests_sweep"] = n
        r["t_deflated_sweep"] = round(deflate_t(float(r["t_gross"]), n), 3)
        r["proposed"] = bool(r.get("clears_cost") and r["t_deflated_sweep"] > pc.PROPOSE_T
                             and int(r.get("n_independent", 0)) >= pc.MIN_TRADES
                             and r["walk_forward"]["passed"])
    proposals = pc.best_per_cell(rows)
    cands = [pc.candidate(
        SOURCE, r["symbol"], FAMILY, dict(r["params"]),
        mechanism=(f"{r['params']['base_family']} traded only when {r['symbol']}'s regime "
                   f"systems read {_state(r['params'])} (last completed day): the edge lives "
                   "where our models agree or contradict each other, not in the blend"),
        title=f"{r['cell']}",
        evidence={**{k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                       "cost_frac", "t_gross", "t_deflated_sweep",
                                       "n_tests_sweep")},
                  "walk_forward_measured": r["walk_forward"]["measured"],
                  "blended": r["blended"]},
    ) for r in proposals]
    killed = sum(1 for r in rows if r.get("clears_cost") and not r["walk_forward"]["passed"])
    report = {"generated_at": datetime.now(tz=UTC).isoformat(), "symbols_swept": len(todo),
              "lane": "every hypothesis-lane symbol (may_hypothesise), least-judged first",
              "tests_run": len(rows), "cells_newly_charged": new_cells,
              "lifetime_union_cells": union_n, "cells_proposed": len(proposals),
              "killed_by_walk_forward": killed, "skipped": skipped,
              "predictiveness": predictive,
              "predictiveness_summary": _summary(predictive),
              "design": {"base_families": list(rsm.BASE_FAMILIES),
                         "states": [f"{a}_{s}" for a, s in STATES],
                         "systems": {"vol": ["markov", "ewma", "garch", "hmm"],
                                     "trend": ["markov", "kalman", "tsmom", "hmm"],
                                     "transition": ["bocpd"]},
                         "llm_vote": "report-only (libs.regime.disagreement.with_llm); never a "
                                     "gate input"},
              "proposals": proposals, "all": rows}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if cands:
        report["donated"] = str(pc.donate(SOURCE, cands, new_cells))
    return report


def _state(params: dict) -> str:
    for a in ("vol", "trend", "transition"):
        if params.get(a):
            return f"{a} {params[a]}"
    return "any"


def _summary(pred: dict[str, Any]) -> dict[str, Any]:
    """Median rank correlation per axis across symbols: the desk-level answer."""
    out: dict[str, Any] = {}
    for ax in ("mi_vol", "mi_trend", "transition_bocpd"):
        for k in ("rho_fwd_vol", "rho_fwd_vol_beyond_level", "rho_fwd_abs_move"):
            xs = sorted(float(v[ax][k]) for v in pred.values()
                        if isinstance(v.get(ax), dict) and k in v[ax])
            out[f"{ax}.{k}"] = ({"symbols": len(xs), "median": round(xs[len(xs) // 2], 4)}
                                if xs else {"status": "UNMEASURED"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=1800.0)
    a = ap.parse_args()
    rep = run(a.symbol, a.budget_s)
    print(json.dumps({k: rep[k] for k in ("symbols_swept", "tests_run", "cells_proposed",
                                          "killed_by_walk_forward", "skipped",
                                          "predictiveness_summary")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
