"""The hourly Execution Digital Twin: live intents become simulation test cases, every hour.

THE PRINCIPAL'S ORDER. "Every live intent becomes a simulation test case. Compare PredictedFill
vs ActualFill ... Collect broker-specific empirical distributions continuously. This is a Fusion
execution moat public frameworks cannot hand you." `libs.execution.digital_twin` is the pure
arithmetic; this organ is the clock, the ledgers and the dataset. Once an hour it reads the three
ledgers the gateway already writes, joins them into cases, appends the NEW or newly RESOLVED
cases to `data/execution_twin_cases.jsonl` -- the private Fusion quote/spread/fill/reject/
latency/slippage history the principal wants kept -- and writes `reports/EXECUTION_TWIN.json`:
the calibration tables, the per-symbol recalibration the simulator should apply, and the
verdicts, every one with its n.

THE WATERMARK IS THE LEDGERS' OWN LENGTH. The three ledgers are append-only, so the row counts
in `data/execution_twin_state.json` say whether anything new can exist; when nothing grew the
pass returns UNCHANGED and touches no file, so an hourly re-run never double counts. When
something grew, the join is rebuilt in full (a few thousand rows; cheap) rather than
incrementally, because a case can RESOLVE after it was first written -- a resting bracket's
deal arrives when the position closes, hours or days after the intent -- and only a full rebuild
sees that. A case is appended to the dataset when its key is new or its `resolution` changed, so
the file is append-only and its last row per key is the truth.

WHAT IT DOES NOT DO. It fabricates nothing: with no intent ledger on the box it returns
UNMEASURED with the reason and writes nothing (this research container has no ledgers; the
trading box does). It applies nothing: the recalibration it reports is consumed by nobody yet --
`engine.Costs` and `external_gauntlet.costs_for` still charge the registry's spread with a
hand-set `mult` -- and that wiring is the next handoff, named in the report under `consumers`.

    python3 research/execution_twin.py [--budget-s N] [--symbols XAUUSD,EURUSD]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import execution_registry  # noqa: E402

from libs.execution import digital_twin as dt  # noqa: E402

#: The gateway's three ledgers (declared on the gateway node of the capability graph).
INTENTS = BASE / "data" / "order_intents.jsonl"
OUTCOMES = BASE / "data" / "execution_algo_outcomes.jsonl"
LEDGER = BASE / "data" / "live_ledger.jsonl"
#: The registry the simulator prices from, for the spread it charges per symbol.
UNIVERSE = BASE / "data" / "universe" / "universe.json"
#: This organ's own: the watermark, the private dataset, the report.
STATE = BASE / "data" / "execution_twin_state.json"
CASES = BASE / "data" / "execution_twin_cases.jsonl"
REPORT = BASE / "reports" / "EXECUTION_TWIN.json"

YIELD_PREFIX = "YIELD "
#: The counters this organ yields, by name, for the hourly pass.
YIELD_KEYS = ("cases_joined", "symbols_calibrated", "symbols_unmeasured")

#: Where the recalibration should be applied, stated in the report so a reader of the report
#: knows the number is advisory until that wiring exists.
CONSUMERS: dict[str, str] = {
    "desks/mt5/mt5desk/engine.py": ("Costs.from_symbol(meta, mult=...): multiply `mult` by the "
                                    "symbol's slippage_multiplier"),
    "desks/mt5/scripts/external_gauntlet.py": ("costs_for(sym, meta, mult=...): same multiplier "
                                               "on the gauntlet's own call"),
    "status": "NOT WIRED -- the report is advisory until a consumer reads it",
}


def _rows(path: Path) -> list[dict[str, Any]]:
    """Every JSON row in an append-only ledger; a torn final line is skipped, never fatal."""
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _read_json(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _num(x: Any) -> float | None:
    """A positive finite number or None; registry fields are hand-maintained and can be absent."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v > 0 and v == v and v not in (float("inf"), float("-inf")) else None


def sim_costs(cases: list[dt.TwinCase], universe: dict[str, Any] | None = None
              ) -> dict[str, dt.SimCost]:
    """What the simulator assumes per symbol, on the twin's axis.

    `engine.run_backtest` fills at the bar open or the trigger with no slip and charges the
    registry's `median_spread_pts` (x `mult`) plus commission; so slip 0.0, p_fill 1.0, and the
    round-trip spread as a fraction of price is `median_spread_pts x point / price` with `point`
    the registry's `tick_size` or 10^-digits (MT5's definition of a point) and `price` the mean
    reference quote of the symbol's own cases. A symbol the registry does not know gets no
    spread_frac, and its correction is reported as slip to add rather than as a multiplier.
    """
    uni = universe if universe is not None else _read_json(UNIVERSE)
    out: dict[str, dt.SimCost] = {}
    by: dict[str, list[float]] = {}
    for c in cases:
        by.setdefault(c.symbol, []).append(c.price_ref)
    for sym, prices in by.items():
        meta = uni.get(sym) if isinstance(uni.get(sym), dict) else {}
        pts = _num(meta.get("median_spread_pts"))
        point = _num(meta.get("tick_size"))
        digits = _num(meta.get("digits"))
        if point is None and digits is not None:
            point = 10.0 ** (-int(digits))
        price = sum(prices) / len(prices) if prices else 0.0
        spread_frac = (pts * point / price if pts is not None and point is not None
                       and price > 0 else None)
        out[sym] = dt.SimCost(slip_frac=0.0, p_fill=1.0, spread_frac=spread_frac)
    return out


def _append_cases(cases: list[dt.TwinCase], path: Path) -> int:
    """Append cases whose key is new or whose resolution changed since the last stored row.
    Returns how many rows were appended -- the hour's donation to the private dataset."""
    last: dict[str, str] = {}
    for r in _rows(path):
        k = str(r.get("intent_id") or "")
        if k:
            last[k] = dt.case_from_row(r).resolution
    new = [c for c in cases if last.get(c.intent_id) != c.resolution]
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for c in new:
                f.write(json.dumps(c.to_row(), default=str) + "\n")
    return len(new)


def _gaps(cases: list[dt.TwinCase], n_outcomes: int) -> list[str]:
    """What the ledgers do not carry yet, measured on this hour's cases -- the handoff list."""
    gaps: list[str] = []
    if not cases:
        return gaps
    fuzzy = sum(1 for c in cases if c.join_key == "fuzzy")
    by_id = sum(1 for c in cases if c.join_key == "intent_id")
    if n_outcomes and by_id == 0:
        gaps.append(f"no intent carries intent_id: {fuzzy} of {len(cases)} cases joined on "
                    "(symbol, side, lots, time) -- gateway handoff: write intent_id on the "
                    "intent row and on record_outcome's row")
    if all(c.latency_ms is None for c in cases):
        gaps.append("no intent carries latency_ms: latency_summary is UNMEASURED -- gateway "
                    "handoff: time order_send and record it on the intent row")
    if all(c.spread_at_fill_frac is None for c in cases):
        gaps.append("nothing records the spread at fill: spread_expansion is UNMEASURED -- "
                    "gateway handoff: spread_at_fill on record_outcome's row / the deal row")
    if any(c.order_type == "market" and c.spread_frac is None for c in cases):
        gaps.append("market-path intents carry no spread_at_decision: their reject and slip "
                    "cells fall in the 'unknown' spread bucket -- gateway handoff: record the "
                    "tick's spread on the family/scalp intent rows as the bracket path does")
    unresolved = sum(1 for c in cases if c.filled is None)
    if unresolved:
        gaps.append(f"{unresolved} resting orders unresolved (no deal yet, younger than "
                    f"{dt.RESOLVE_AFTER_S / 3600:.0f}h): neither filled nor unfilled")
    return gaps


def run(symbols: list[str] | set[str] | None = None, budget_s: float | None = None
        ) -> dict[str, Any]:
    """One hourly pass. Returns the organ's report with the yield counters in it."""
    t0 = time.monotonic()
    now = datetime.now(tz=UTC)
    if not INTENTS.exists():
        return {"status": dt.UNMEASURED,
                "why": (f"no intent ledger at {INTENTS}: the gateway has not placed an order "
                        "on this box, so there is no live execution to twin"),
                "cases_joined": 0, "symbols_calibrated": 0, "symbols_unmeasured": 0,
                "donated_rows": 0}
    intents = _rows(INTENTS)
    outcomes = _rows(OUTCOMES) if OUTCOMES.exists() else []
    deals = _rows(LEDGER) if LEDGER.exists() else None
    counts = {"intents": len(intents), "outcomes": len(outcomes),
              "deals": len(deals) if deals is not None else 0}
    state = _read_json(STATE)
    prev = state.get("ledger_rows") if isinstance(state.get("ledger_rows"), dict) else None
    if prev == counts and not symbols:
        last = state.get("last") if isinstance(state.get("last"), dict) else {}
        return {"status": "UNCHANGED", "why": "no ledger grew since the last pass",
                "ledger_rows": counts, "cases_joined": int(last.get("cases_joined") or 0),
                "symbols_calibrated": int(last.get("symbols_calibrated") or 0),
                "symbols_unmeasured": int(last.get("symbols_unmeasured") or 0),
                "donated_rows": 0}
    want = {str(s) for s in symbols} if symbols else None
    if want:
        intents = [r for r in intents if str(r.get("symbol")) in want]
        outcomes = [r for r in outcomes if str(r.get("symbol")) in want]
    cases = dt.join_cases(intents, outcomes, deals, asof=now)
    if not cases:
        return {"status": dt.UNMEASURED,
                "why": f"{len(intents)} intent rows, none usable as a case (no side/lot/price)",
                "ledger_rows": counts, "cases_joined": 0, "symbols_calibrated": 0,
                "symbols_unmeasured": 0, "donated_rows": 0}

    donated = _append_cases(cases, CASES)
    costs = sim_costs(cases)
    recal = dt.recalibration(cases, costs)
    try:
        board = execution_registry.scoreboard(rows=outcomes)
    except Exception as exc:
        board = {"status": dt.UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    verdicts = recal["counts"]
    calibrated = sum(v for k, v in verdicts.items() if k != dt.UNMEASURED)
    unmeasured = int(verdicts.get(dt.UNMEASURED, 0))
    join_keys: dict[str, int] = {}
    provenance: dict[str, int] = {}
    for c in cases:
        join_keys[c.join_key] = join_keys.get(c.join_key, 0) + 1
        provenance[c.account_kind] = provenance.get(c.account_kind, 0) + 1
    report: dict[str, Any] = {
        "generated_utc": now.isoformat(), "status": dt.MEASURED,
        "ledger_rows": counts, "symbols_filter": sorted(want) if want else None,
        "cases": {"n": len(cases), "joined_outcome": sum(1 for c in cases if c.joined_outcome),
                  "joined_deal": sum(1 for c in cases if c.joined_deal),
                  "rejected": sum(1 for c in cases if c.rejected),
                  "filled": sum(1 for c in cases if c.filled),
                  "unresolved": sum(1 for c in cases if c.filled is None),
                  "by_join_key": join_keys, "by_account_kind": provenance,
                  "dataset": str(CASES), "appended_this_pass": donated},
        "fill_calibration": dt.fill_calibration(cases),
        "slippage_calibration": dt.slippage_calibration(cases),
        "reject_model": dt.reject_model(cases),
        "latency": dt.latency_summary(cases),
        "spread_expansion": dt.spread_expansion(cases),
        "impact_proxy": dt.impact_proxy(cases),
        "recalibration": recal,
        "execution_choice_value": dt.execution_choice_value(cases),
        "algo_scoreboard": board,
        "sim_costs": {s: {"slip_frac": c.slip_frac, "p_fill": c.p_fill,
                          "spread_frac": c.spread_frac} for s, c in sorted(costs.items())},
        "consumers": CONSUMERS,
        "gaps": _gaps(cases, len(outcomes)),
        "budget_s": budget_s, "seconds": round(time.monotonic() - t0, 3),
        # the yield counters, in the report so the hourly pass can count them by name
        "cases_joined": len(cases), "symbols_calibrated": calibrated,
        "symbols_unmeasured": unmeasured, "donated_rows": donated,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    if not want:
        # a filtered run is a probe, not the hour's pass: it must not move the watermark
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({
            "last_run_utc": now.isoformat(), "ledger_rows": counts,
            "last": {"cases_joined": len(cases), "symbols_calibrated": calibrated,
                     "symbols_unmeasured": unmeasured, "donated_rows": donated},
            "runs": int(state.get("runs") or 0) + 1,
            "donated_total": int(state.get("donated_total") or 0) + donated,
        }, indent=1), "utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=None)
    ap.add_argument("--symbols", default="", help="comma-separated; a probe, moves no watermark")
    a = ap.parse_args()
    syms = [s.strip() for s in a.symbols.split(",") if s.strip()] or None
    d = run(symbols=syms, budget_s=a.budget_s)
    status = d.get("status")
    if status in (dt.UNMEASURED, "UNCHANGED"):
        print(f"EXECUTION TWIN  {status}: {d.get('why')}", flush=True)
    else:
        v = d["recalibration"]["counts"]
        print(f"EXECUTION TWIN  cases={d['cases_joined']} "
              f"(outcome-joined {d['cases']['joined_outcome']}, deal-joined "
              f"{d['cases']['joined_deal']}, rejected {d['cases']['rejected']}) verdicts="
              f"{json.dumps(v)} appended={d['donated_rows']} gaps={len(d['gaps'])} -> {REPORT}",
              flush=True)
    print(YIELD_PREFIX + json.dumps({k: int(d.get(k) or 0) for k in YIELD_KEYS}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
