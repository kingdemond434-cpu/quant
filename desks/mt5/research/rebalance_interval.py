#!/usr/bin/env python3
"""REBALANCE INTERVAL -- how often the live book should be pulled back to its target weights.

REPORT-ONLY. Nothing here changes a fraction, a lot or a gate; `pf_allocator` and the gateway
never read this file. It answers one question with the desk's own forward evidence:

    which rebalance policy has the highest NET E[log W] gain over never rebalancing?

THE GAIN. Holding fixed target weights in several imperfectly correlated sleeves and pulling
them back as they drift earns the "volatility pumping" (rebalancing / diversification) return:
a constant-mix book's log growth exceeds the weighted log growth of its parts by roughly half
the weighted variance minus the book's variance. A buy-and-hold book lets the weights drift
toward whatever won, and gives that premium back. Rebalancing more often harvests more of it
and pays the spread and slippage every time it does -- so the interval is a cost trade-off, and
this organ measures both sides rather than assuming either.

CANDIDATES: every pass (hourly), daily, every 2 days, weekly, and drift thresholds of 10% and
20% (rebalance when any sleeve's weight has drifted that far, relative, from its target).

EVIDENCE, AND WHAT MAKES A ROW UNMEASURED.
  * Forward returns only: each live sleeve's OWN per-key forward ledger
    (`reports/shadow/ledger_<key>.json`), filtered to trades at or after the clock's
    `forward_start`. A sleeve with no `forward_start` cannot prove its rows are forward, and is
    UNMEASURED -- no look-ahead, ever.
  * A ledger that more than one key resolves to (a `#param` sibling, a shadow key and a sleeve
    naming one file) is SHARED: its rows cannot be attributed to this sleeve, so UNMEASURED.
  * Cost per symbol = the clean markout slip (in R, `reports/markout.json` -> `slip.by_symbol`,
    the #391 clean column) PLUS half the median spread from the spread surface
    (`data/cost_surface.json`, converted to R through the same symbol's measured R-per-point).
    If EITHER is absent for a symbol, that symbol's result is UNMEASURED; it is never priced at
    zero and never at a pooled default.

THE CHARGE. A rebalance that moves |dw| of the book into or out of a sleeve resizes that
sleeve's next 1R exposure by that share; it is charged |dw| * RISK_UNIT * cost_R of wealth. This
is the conservative reading (a sleeve whose position is flat could resize for free).
"""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
SHADOW_DIR = DESK / "reports" / "shadow"
SHADOW_STATES = ("shadow_state.json", "scalp_shadow_state.json", "qquant_shadow_state.json",
                 "external_shadow_state.json")
SLEEVES = DESK / "data" / "sleeves.json"
MARKOUT = DESK / "reports" / "markout.json"
SPREAD_SURFACE = DESK / "data" / "cost_surface.json"
OUT = DESK / "reports" / "REBALANCE_INTERVAL.json"

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
#: Wealth at risk per 1R of a sleeve at its full target weight (the R -> return conversion).
RISK_UNIT = 0.01
#: Forward hours a book needs before an interval verdict is a verdict.
MIN_HOURS = 24 * 5
#: Candidates: (name, fixed period in hours or None, drift threshold or None).
CANDIDATES: tuple[tuple[str, int | None, float | None], ...] = (
    ("every_pass", 1, None), ("daily", 24, None), ("every_2_days", 48, None),
    ("weekly", 168, None), ("drift_10pct", None, 0.10), ("drift_20pct", None, 0.20),
)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def ledger_name(key: str) -> str:
    """Same resolution as forward_exploitation.ledger_path: the `#` suffix is a parameterisation."""
    return f"ledger_{str(key).split('#')[0].replace('.', '_')}.json"


# ------------------------------------------------------------------------------------- inputs
def live_book(sleeves_doc: Any) -> list[dict[str, Any]]:
    rows = sleeves_doc.get("sleeves") if isinstance(sleeves_doc, dict) else sleeves_doc
    out = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE" and r.get("name"):
            out.append(r)
    return out


def key_counts(sleeves_doc: Any, states: list[Any]) -> dict[str, int]:
    """How many distinct keys resolve to each ledger file -- >1 means SHARED."""
    keys: set[str] = set()
    rows = sleeves_doc.get("sleeves") if isinstance(sleeves_doc, dict) else sleeves_doc
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and r.get("name"):
            keys.add(str(r["name"]))
    for st in states:
        for k, v in (st.items() if isinstance(st, dict) else ()):
            if isinstance(v, dict):
                keys.add(str(k))
    counts: dict[str, int] = {}
    for k in keys:
        counts[ledger_name(k)] = counts.get(ledger_name(k), 0) + 1
    return counts


def forward_start(sleeve: dict[str, Any], states: list[Any]) -> datetime | None:
    t = _ts(sleeve.get("forward_start"))
    if t is not None:
        return t
    for st in states:
        row = st.get(str(sleeve["name"])) if isinstance(st, dict) else None
        if isinstance(row, dict) and _ts(row.get("forward_start")) is not None:
            return _ts(row.get("forward_start"))
    return None


def forward_trades(rows: Any, start: datetime) -> list[tuple[datetime, float]]:
    """(when, R) at or after `start`. Both ledger schemas (entry_time/r_multiple, opened_at/r)."""
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        when = _ts(row.get("entry_time") or row.get("opened_at"))
        r = _num(row.get("r_multiple"))
        if r is None:
            r = _num(row.get("r"))
        if when is None or r is None or when < start:
            continue
        out.append((when, r))
    out.sort()
    return out


def symbol_cost(symbol: str, markout: Any, surface: Any) -> dict[str, Any]:
    """Round-trip-free (one-way) cost of resizing 1R on `symbol`, in R. UNMEASURED if either
    source is missing for it."""
    slip = (((markout or {}).get("slip") or {}).get("by_symbol") or {}).get(symbol) \
        if isinstance(markout, dict) else None
    clean = (slip or {}).get("clean") or {}
    slip_r = _num((clean.get("r") or {}).get("mean"))
    slip_pts = _num((clean.get("pts") or {}).get("mean"))
    srow = (((surface or {}).get("symbols") or {}).get(symbol)) if isinstance(surface, dict) \
        else None
    spread_pts = _num((srow or {}).get("pooled_median_spread_pts"))
    missing = []
    if slip_r is None:
        missing.append("no clean markout slip in R for this symbol (reports/markout.json "
                       "slip.by_symbol.<sym>.clean.r)")
    if spread_pts is None:
        missing.append("no measured spread on the spread surface (data/cost_surface.json)")
    if slip_r is not None and (slip_pts is None or slip_pts == 0.0):
        missing.append("markout carries no point slip, so the spread cannot be put in R")
    if missing:
        return {"status": UNMEASURED, "why": "; ".join(missing)}
    assert slip_r is not None and slip_pts is not None and spread_pts is not None
    r_per_pt = abs(slip_r / slip_pts)
    cost_r = abs(slip_r) + 0.5 * spread_pts * r_per_pt
    return {"status": MEASURED, "cost_r": round(cost_r, 6), "slip_r": round(slip_r, 6),
            "half_spread_r": round(0.5 * spread_pts * r_per_pt, 6),
            "spread_pts": spread_pts, "n_clean": (slip or {}).get("n_clean")}


# ------------------------------------------------------------------------------------- engine
def hourly_returns(trades: dict[str, list[tuple[datetime, float]]],
                   start: datetime, end: datetime) -> list[dict[str, float]]:
    """One dict per hour from `start` to `end`: sleeve -> simple return of that sleeve's capital."""
    t0 = start.replace(minute=0, second=0, microsecond=0)
    n = max(1, int((end - t0).total_seconds() // 3600) + 1)
    grid: list[dict[str, float]] = [{} for _ in range(n)]
    for name, rows in trades.items():
        for when, r in rows:
            i = int((when - t0).total_seconds() // 3600)
            if 0 <= i < n:
                grid[i][name] = grid[i].get(name, 0.0) + r * RISK_UNIT
    return grid


def simulate(grid: list[dict[str, float]], target: dict[str, float], cost_r: dict[str, float],
             period: int | None, drift: float | None) -> dict[str, Any]:
    """Log wealth of a book that starts at `target` and rebalances by the policy. period=None and
    drift=None is buy-and-hold."""
    names = list(target)
    hold = dict(target)                       # wealth share held in each sleeve (sums to wealth)
    logw = 0.0
    paid = 0.0
    n_reb = 0
    for i, row in enumerate(grid):
        w = sum(hold.values())
        for k in names:
            hold[k] *= max(1e-12, 1.0 + row.get(k, 0.0))
        w_new = sum(hold.values())
        logw += math.log(w_new / w)
        due = False
        if period is not None and (i + 1) % period == 0:
            due = True
        elif drift is not None:
            due = any(abs(hold[k] / w_new - target[k]) / target[k] > drift for k in names
                      if target[k] > 0)
        if due:
            turnover = {k: abs(hold[k] / w_new - target[k]) for k in names}
            cost = sum(turnover[k] * RISK_UNIT * cost_r[k] for k in names)
            cost = min(cost, 0.5)
            paid += cost
            w_after = w_new * (1.0 - cost)
            logw += math.log(1.0 - cost)
            hold = {k: target[k] * w_after for k in names}
            n_reb += 1
    return {"log_w": logw, "cost_paid": paid, "n_rebalances": n_reb}


def evaluate(trades: dict[str, list[tuple[datetime, float]]], target: dict[str, float],
             cost_r: dict[str, float], start: datetime, end: datetime) -> dict[str, Any]:
    tot = sum(target.values())
    target = {k: v / tot for k, v in target.items()}
    grid = hourly_returns(trades, start, end)
    days = len(grid) / 24.0
    base = simulate(grid, target, cost_r, None, None)
    rows = []
    for name, period, drift in CANDIDATES:
        res = simulate(grid, target, cost_r, period, drift)
        gross = simulate(grid, target, dict.fromkeys(cost_r, 0.0), period, drift)
        rows.append({
            "interval": name, "period_h": period, "drift_threshold": drift,
            "n_rebalances": res["n_rebalances"],
            "gross_gain_elogw_per_day": (gross["log_w"] - base["log_w"]) / days,
            "cost_elogw_per_day": (gross["log_w"] - res["log_w"]) / days,
            "net_gain_elogw_per_day": (res["log_w"] - base["log_w"]) / days})
    best = max(rows, key=lambda r: r["net_gain_elogw_per_day"])
    return {"hours": len(grid), "days": round(days, 3),
            "hold_elogw_per_day": base["log_w"] / days, "candidates": rows,
            "chosen": best["interval"],
            "chosen_net_gain_elogw_per_day": best["net_gain_elogw_per_day"],
            "beats_hold": best["net_gain_elogw_per_day"] > 0.0}


# ------------------------------------------------------------------------------------- build
def build(now: datetime | None = None, shadow_dir: Path = SHADOW_DIR, sleeves_path: Path = SLEEVES,
          markout_path: Path = MARKOUT, surface_path: Path = SPREAD_SURFACE) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    sleeves_doc = _read(sleeves_path)
    states = [_read(shadow_dir / n) for n in SHADOW_STATES]
    markout = _read(markout_path)
    surface = _read(surface_path)
    counts = key_counts(sleeves_doc, states)
    book = live_book(sleeves_doc)

    per_sleeve: list[dict[str, Any]] = []
    per_symbol: dict[str, dict[str, Any]] = {}
    trades: dict[str, list[tuple[datetime, float]]] = {}
    target: dict[str, float] = {}
    costs: dict[str, float] = {}
    starts: list[datetime] = []
    for s in book:
        name, sym = str(s["name"]), str(s.get("symbol") or "").upper()
        row: dict[str, Any] = {"sleeve": name, "symbol": sym,
                               "risk_frac": _num(s.get("risk_frac"))}
        per_sleeve.append(row)
        if sym not in per_symbol:
            per_symbol[sym] = symbol_cost(sym, markout, surface)
        cost = per_symbol[sym]
        lname = ledger_name(name)
        fs = forward_start(s, states)
        why = None
        if counts.get(lname, 0) > 1:
            why = f"{lname} is SHARED by {counts[lname]} keys; its rows are not this sleeve's"
        elif fs is None:
            why = "no forward_start: the rows cannot be proven forward (no look-ahead)"
        elif not (shadow_dir / lname).exists():
            why = f"{lname} is absent on this host"
        elif cost["status"] != MEASURED:
            why = f"{sym} cost UNMEASURED: {cost['why']}"
        if why is not None:
            row.update(status=UNMEASURED, why=why)
            continue
        assert fs is not None
        tr = forward_trades(_read(shadow_dir / lname), fs)
        w = row["risk_frac"]
        if not w or w <= 0:
            row.update(status=UNMEASURED, why="no positive allocator fraction to hold as target")
            continue
        row.update(status=MEASURED, forward_start=fs.isoformat(), n_forward=len(tr))
        trades[name], target[name], costs[name] = tr, float(w), float(cost["cost_r"])
        starts.append(fs)

    doc: dict[str, Any] = {
        "source": "rebalance_interval", "generated_at": now.isoformat(timespec="seconds"),
        "report_only": True,
        "sizing_effect": "none -- no allocator, gateway or promoter reads this file",
        "risk_unit": RISK_UNIT, "candidates": [c[0] for c in CANDIDATES],
        "n_live_sleeves": len(book), "n_measured_sleeves": len(trades),
        "sleeves": per_sleeve, "symbols": per_symbol,
        "cost_sources": {"markout": str(markout_path.relative_to(ROOT))
                         if markout_path.is_relative_to(ROOT) else str(markout_path),
                         "spread_surface": str(surface_path.relative_to(ROOT))
                         if surface_path.is_relative_to(ROOT) else str(surface_path)},
    }
    if len(trades) < 2:
        doc.update(status=UNMEASURED, chosen=None,
                   why=(f"{len(trades)} of {len(book)} live sleeve(s) measured; volatility "
                        f"pumping needs at least two sleeves with forward rows and a measured "
                        f"cost"))
        return doc
    # Common forward window: every sleeve must be forward over the whole simulated span.
    start = max(starts)
    trades = {k: [t for t in v if t[0] >= start] for k, v in trades.items()}
    if (now - start) < timedelta(hours=MIN_HOURS):
        doc.update(status=UNMEASURED, chosen=None, common_forward_start=start.isoformat(),
                   why=f"the common forward window is under {MIN_HOURS // 24} days")
        return doc
    res = evaluate(trades, target, costs, start, now)
    doc.update(status=MEASURED, common_forward_start=start.isoformat(), **res,
               why=(f"{res['chosen']} has the highest net E[log W] gain over buy-and-hold "
                    f"({res['chosen_net_gain_elogw_per_day']:+.3e}/day across "
                    f"{len(trades)} sleeves)"))
    return doc


def main(argv: list[str] | None = None) -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    tmp.replace(OUT)
    print(f"rebalance_interval: {doc['status']} chosen={doc.get('chosen')} "
          f"({doc['n_measured_sleeves']}/{doc['n_live_sleeves']} sleeves) -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
