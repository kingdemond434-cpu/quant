#!/usr/bin/env python3
"""WHOLE PROCESSES, NOT PIECES: each cited practitioner's end-to-end loop, run by this desk.

    python desks/mt5/research/practitioner_processes.py [--out PATH]

The principal (2026-09-30): "reverse engineer fully ... yes whole processes". A practice copied
one stage at a time is not the practice. The winner's edge was a regime reading that CHANGED THE
WEIGHTS THE SAME DAY, not a regime model sitting in a research folder. So this organ writes each
practitioner's loop down as the ordered stages they described, binds every stage to the desk
organ that performs it and the artifact that organ writes, and checks the WHOLE chain every day:

    RUNNING        the stage's artifact exists, is fresh, and says it did its job
    NOT_ADMITTED   built and running, but its admission contract has not shown gain, so it
                   does not reach capital (a real state, never a failure to hide)
    STALE          the artifact exists and is older than the stage's clock allows
    UNMEASURED     the artifact is absent on this host (the box holds most of them)
    GAP            no organ performs this stage

A process is COMPLETE only when every stage is RUNNING. `bottleneck` is the first stage that is
not, because a loop is only as fast as its slowest stage and that is where the next build goes.
Where a stage hands a COUNT to the next (candidates -> judged -> certified -> live -> funded),
the counts are carried so the funnel reads end to end.

THE FOUR LOOPS, reverse-engineered to mechanisms on this desk's instruments:

  korean_winner      regime detection (vol + liquidity -> trend/range) -> factor-based selection
                     -> geometric (Kelly) allocation, the regime re-weighting the book live
  regime_first_seven a market-regime read first -> a small set of distinct strategies (a gap
                     strategy among them) -> each weighted by the regime -> live on a broker API
  scherman_funnel    thousands of models backtested -> hundreds put to work -> the few that
                     keep working sized up, one disclosed pattern (index/VIX divergence)
  mini_quant         gather data -> generate hypotheses (5 regions) -> backtest -> alpha pool
                     with a composite score -> execute with automated risk management
"""
from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "desks" / "mt5"
R = BASE / "reports"
D = BASE / "data"
OUT = R / "PRACTITIONER_PROCESSES.json"
DAY_H, WEEK_H, HOUR_H = 36.0, 8 * 24.0, 3.0


def _load(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _age_h(p: Path) -> float:
    return (time.time() - p.stat().st_mtime) / 3600.0


def _n(doc: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(k)
    return doc


Check = Callable[[Any], tuple[str, dict[str, Any]]]


def _ran(_: Any) -> tuple[str, dict[str, Any]]:
    return "RUNNING", {}


def stage(name: str, practice: str, organ: str, artifact: Path | None, max_age_h: float,
          check: Check = _ran) -> dict[str, Any]:
    row: dict[str, Any] = {"stage": name, "practice": practice, "organ": organ,
                           "artifact": _rel(artifact) if artifact else None}
    if artifact is None:
        return {**row, "status": "GAP", "why": "no organ performs this stage"}
    if not artifact.exists():
        return {**row, "status": "UNMEASURED", "why": "artifact absent on this host"}
    age = _age_h(artifact)
    row["age_h"] = round(age, 1)
    doc = _load(artifact) if artifact.suffix == ".json" else None
    status, extra = check(doc)
    if age > max_age_h and status == "RUNNING":
        status = "STALE"
        extra["why"] = f"{age:.0f}h old, clock allows {max_age_h:.0f}h"
    return {**row, "status": status, **extra}


def _contract(doc: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(doc, dict):
        return "UNMEASURED", {"why": "contract unreadable"}
    info = {"verdict": doc.get("verdict"), "universe": _n(doc, "design", "universe"),
            "headline_annual": _n(doc, "headline", "annual")}
    return ("RUNNING" if doc.get("admits") else "NOT_ADMITTED"), info


def _control_room(doc: Any) -> tuple[str, dict[str, Any]]:
    a = _n(doc, "assets") or {}
    return ("RUNNING" if a else "UNMEASURED"), {"instruments": len(a),
                                                 "share_trending": _n(doc, "share_trending")}


def _screen(key: str) -> Check:
    def f(doc: Any) -> tuple[str, dict[str, Any]]:
        s = _n(doc, "screens", key) or {}
        v = s.get("verdict")
        if v in (None, "UNMEASURED", "INSUFFICIENT"):
            return "UNMEASURED", {"verdict": v, "why": s.get("why")}
        return "RUNNING", {"verdict": v, "pooled": s.get("pooled")}
    return f


def _count(label: str, *keys: str) -> Check:
    def f(doc: Any) -> tuple[str, dict[str, Any]]:
        v = _n(doc, *keys)
        if isinstance(v, (list, dict)):
            v = len(v)
        return ("RUNNING" if v is not None else "UNMEASURED"), {label: v}
    return f


def _sleeves(doc: Any) -> tuple[str, dict[str, Any]]:
    rows = _n(doc, "sleeves") or []
    live = [r for r in rows if isinstance(r, dict) and r.get("status") == "LIVE"]
    fams = sorted({str(r.get("family")) for r in live})
    return ("RUNNING" if live else "UNMEASURED"), {"live": len(live),
                                                    "live_families": len(fams)}


def _alloc(doc: Any) -> tuple[str, dict[str, Any]]:
    book = {k: v for k, v in (_n(doc, "book") or {}).items()
            if isinstance(v, (int, float)) and v > 1e-6}
    return ("RUNNING" if isinstance(doc, dict) else "UNMEASURED"), {
        "funded": len(book), "total_heat": _n(doc, "heat", "total"),
        "armed": _n(doc, "armed"), "macro_kernel": _n(doc, "macro_regime", "kernel", "status")}


def _bridge(doc: Any) -> tuple[str, dict[str, Any]]:
    return ("RUNNING" if isinstance(doc, dict) else "UNMEASURED"), {
        "stages": {k: (v or {}).get("n") for k, v in (_n(doc, "stages") or {}).items()},
        "missed_growth": len(_n(doc, "missed_growth") or []),
        "missed_growth_per_year": _n(doc, "missed_growth_per_year")}


def _cross_sectional(_: Any) -> tuple[str, dict[str, Any]]:
    try:
        import sys
        sys.path.insert(0, str(BASE / "research"))
        from universe_policy import CROSS_SECTIONAL_FAMILIES
        return "RUNNING", {"families": sorted(CROSS_SECTIONAL_FAMILIES)}
    except Exception as exc:
        return "UNMEASURED", {"why": f"{type(exc).__name__}: {exc}"}


def processes() -> dict[str, list[dict[str, Any]]]:
    contract = R / "REGIME_ALLOCATION_CONTRACT.json"
    cr = R / "CONTROL_ROOM.json"
    mech = R / "CONTROL_ROOM_MECHANISMS.json"
    alloc = R / "pf_allocation.json"
    sleeves = D / "sleeves.json"
    bridge = R / "BENCH_BRIDGE.json"
    return {
        "korean_winner": [
            stage("regime_detection", "volatility + liquidity diagnose trend vs range",
                  "libs/regime/control_room.py; desks/mt5/research/control_room.py", cr, DAY_H,
                  _control_room),
            stage("factor_selection", "select by the gap between fundamentals and price",
                  "cross-sectional class books (universe_policy.CROSS_SECTIONAL_FAMILIES, "
                  "breadth lane) + macro kernel (libs/portfolio/macro_state.py)",
                  BASE / "research" / "universe_policy.py", 1e9, _cross_sectional),
            stage("geometric_allocation", "Kelly-based sizing, max CAGR, bankruptcy-controlled",
                  "desks/mt5/research/pf_allocator.py (robust E[log W] under heat_policy "
                  "survival envelope)", alloc, HOUR_H, _alloc),
            stage("regime_drives_weights", "the regime re-weights strategies in production",
                  "regime_allocation_contract.py -> pf_allocator control-room kernel "
                  "(desktop patch control_room_regime_kernel)", contract, WEEK_H, _contract),
        ],
        "regime_first_seven": [
            stage("market_regime_first", "uptrend or downtrend, read before anything else",
                  "libs/regime/control_room.py per instrument; pf_allocator.regime_state (gold "
                  "HMM) for the book", cr, DAY_H, _control_room),
            stage("small_distinct_strategy_set", "seven strategies, each a different mechanism",
                  "promoter.py -> data/sleeves.json LIVE rows", sleeves, DAY_H, _sleeves),
            stage("gap_strategy_regime_rule", "the gap strategy, gated by regime",
                  "control_room_mechanisms.py regime_first_gap (gate refused: fade pays in "
                  "every regime)", mech, DAY_H, _screen("regime_first_gap")),
            stage("regime_weighted_book", "weights follow the regime",
                  "regime_allocation_contract.py", contract, WEEK_H, _contract),
            stage("live_execution", "live on a broker API", "mt5desk/gateway.py",
                  D / "gateway_state.json", HOUR_H),
        ],
        "scherman_funnel": [
            stage("thousands_backtested", "backtest thousands of models",
                  "external_gauntlet.py sweep -> BACKTEST_COVERAGE.json",
                  R / "BACKTEST_COVERAGE.json", DAY_H, _count("cells_run", "cells_run")),
            stage("certified_bench", "the ones that survive",
                  "universal ten-gate -> UNIVERSAL_SURVIVORS.json",
                  R / "UNIVERSAL_SURVIVORS.json", DAY_H, _count("certified", "n")),
            stage("hundreds_put_to_work", "hundreds deployed",
                  "forward_enrolment.py -> promoter.py -> LIVE", sleeves, DAY_H, _sleeves),
            stage("sized_by_evidence", "the ones that keep working get the capital",
                  "bench_bridge.py (dE[log W] per candidate, missed growth)", bridge, DAY_H,
                  _bridge),
            stage("disclosed_pattern", "S&P 500 / VIX divergence",
                  "control_room_mechanisms.py index_vol_divergence", mech, DAY_H,
                  _screen("index_vol_divergence")),
        ],
        "mini_quant": [
            stage("gather", "multi-region data", "daily_cycle refresh_bars + world miners",
                  D / "universe" / "universe.json", DAY_H),
            stage("generate", "alpha hypotheses across regions",
                  "miner_candidate_compiler.py -> miner_candidates.json",
                  D / "hypotheses" / "miner_candidates.json", DAY_H,
                  _count("executable_candidates", "executable_candidates")),
            stage("backtest", "comprehensive metrics", "external_gauntlet.py",
                  R / "BACKTEST_COVERAGE.json", DAY_H, _count("cells_run", "cells_run")),
            stage("alpha_pool_scored", "SQLite pool with composite scoring",
                  "UNIVERSAL_SURVIVORS + FORWARD_ENROLMENT, scored by dE[log W] in "
                  "BENCH_BRIDGE.json", bridge, DAY_H, _bridge),
            stage("execute_with_risk", "automated execution and risk management",
                  "pf_allocator heat envelope -> gateway", alloc, HOUR_H, _alloc),
        ],
    }


def run() -> dict[str, Any]:
    procs = processes()
    out: dict[str, Any] = {}
    for name, stages in procs.items():
        bad = [s for s in stages if s["status"] != "RUNNING"]
        out[name] = {"complete": not bad, "running": len(stages) - len(bad),
                     "stages_total": len(stages),
                     "bottleneck": bad[0]["stage"] if bad else None,
                     "stages": stages}
    return {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "processes": out,
            "complete": sorted(k for k, v in out.items() if v["complete"]),
            "rule": ("a process is COMPLETE only when every stage's artifact is fresh and its "
                     "admission (where it moves capital) has shown gain; the bottleneck is the "
                     "first stage that is not, and it is where the next build goes")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = run()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: {"complete": v["complete"], "running": f"{v['running']}/"
                          f"{v['stages_total']}", "bottleneck": v["bottleneck"]}
                      for k, v in doc["processes"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
