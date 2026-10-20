#!/usr/bin/env python3
"""REBALANCE INTERVAL -- how often the live book should be pulled back to its target weights.

REPORT-ONLY. Nothing here changes a fraction, a lot or a gate; `pf_allocator`, `decision_core`
and the gateway never read this file. It answers one question with the desk's forward evidence:

    which rebalance policy (or none) has the highest NET E[log W] over buy-and-hold?

THE GAIN is the volatility-pumping premium a constant-mix book earns over a drifting one; the
COST is the spread and slippage paid to resize. Candidates: every pass (hourly), daily, every 2
days, weekly, and 10% / 20% relative drift thresholds -- and HOLD (never rebalance), which wins
whenever no candidate beats it with margin.

EVIDENCE, AND WHAT MAKES A ROW UNMEASURED.
  * Forward rows only: each live sleeve's own per-key ledger (`forward_exploitation.ledger_path`),
    rows whose ENTRY is at or after the clock's `forward_start`. No `forward_start` -> UNMEASURED.
  * Each trade's R is booked at its EXIT time (never the entry hour: that would credit the book
    with a result before it was known). A row with no exit time is dropped and counted.
  * A ledger more than one key resolves to is SHARED -> UNMEASURED.
  * Coverage: a sleeve with rows on fewer than MIN_DAY_COVERAGE of the window's days is silent
    for most of it -> UNMEASURED.
  * Cost per symbol = |clean markout slip R| (`reports/markout.json` slip.by_symbol, #391) plus
    half the spread surface's median spread in R. Either source older than MAX_COST_AGE_H (72h,
    as run_desk_integrity), or any input non-positive / non-finite -> UNMEASURED. Never zero.

THE CHOICE needs margin: the hourly book returns are block-bootstrapped and a non-hold interval
is chosen only when it beats the runner-up (hold included) in >= WIN_PROB of resamples;
otherwise "no clear winner" and the report says hold stands.

THE CHARGE (ASSUMPTION, stated in the artifact): a rebalance moving |dw| of the book is charged
|dw| * RISK_UNIT * cost_R of wealth, RISK_UNIT being the wealth at risk per 1R at full weight.
"""
from __future__ import annotations

import json
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.forward_exploitation import ledger_path as _fe_ledger_path  # noqa: E402

SHADOW_DIR = DESK / "reports" / "shadow"
SHADOW_STATES = ("shadow_state.json", "scalp_shadow_state.json", "qquant_shadow_state.json",
                 "external_shadow_state.json")
SLEEVES = DESK / "data" / "sleeves.json"
MARKOUT = DESK / "reports" / "markout.json"
SPREAD_SURFACE = DESK / "data" / "cost_surface.json"
OUT = DESK / "reports" / "REBALANCE_INTERVAL.json"

MEASURED, UNMEASURED, PARTIAL = "MEASURED", "UNMEASURED", "PARTIAL"
#: ASSUMPTION: wealth at risk per 1R of a sleeve at its full target weight.
RISK_UNIT = 0.01
MIN_HOURS = 24 * 5
#: A sleeve needs rows on at least this share of the window's days.
MIN_DAY_COVERAGE = 0.5
#: Cost inputs older than this are stale (run_desk_integrity's cost_surface horizon).
MAX_COST_AGE_H = 72.0
#: Bootstrap: a non-hold interval must beat the runner-up in this share of resamples.
WIN_PROB = 0.80
N_BOOT = 200
BLOCK_H = 24
CANDIDATES: tuple[tuple[str, int | None, float | None], ...] = (
    ("every_pass", 1, None), ("daily", 24, None), ("every_2_days", 48, None),
    ("weekly", 168, None), ("drift_10pct", None, 0.10), ("drift_20pct", None, 0.20),
)
HOLD = "hold"


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


def _pos(v: Any) -> float | None:
    f = _num(v)
    return f if f is not None and f > 0 else None


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def ledger_name(key: str) -> str:
    return _fe_ledger_path(key).name


# ------------------------------------------------------------------------------------- inputs
def live_book(sleeves_doc: Any) -> list[dict[str, Any]]:
    rows = sleeves_doc.get("sleeves") if isinstance(sleeves_doc, dict) else sleeves_doc
    return [r for r in (rows if isinstance(rows, list) else [])
            if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"
            and r.get("name")]


def key_counts(sleeves_doc: Any, states: list[Any]) -> dict[str, int]:
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


def forward_trades(rows: Any, start: datetime) -> tuple[list[tuple[datetime, float]], int]:
    """((exit_time, R) for trades ENTERED at or after `start`, n dropped for no exit time)."""
    out, no_exit = [], 0
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        entry = _ts(row.get("entry_time") or row.get("opened_at"))
        r = _num(row.get("r_multiple"))
        if r is None:
            r = _num(row.get("r"))
        if entry is None or r is None or entry < start:
            continue
        ex = _ts(row.get("exit_time") or row.get("closed_at") or row.get("close_time"))
        if ex is None or ex < entry:
            no_exit += 1
            continue
        out.append((ex, r))
    out.sort()
    return out, no_exit


def _age_h(stamp: Any, now: datetime) -> float | None:
    t = _ts(stamp)
    return None if t is None else (now - t).total_seconds() / 3600.0


def cost_freshness(markout: Any, surface: Any, now: datetime) -> dict[str, Any]:
    ages = {"markout_at_age_h": _age_h((markout or {}).get("at") if isinstance(markout, dict)
                                       else None, now),
            "cost_surface_built_at_age_h": _age_h((surface or {}).get("built_at")
                                                  if isinstance(surface, dict) else None, now)}
    bad = [f"{k[:-6]} {'absent' if v is None else f'{v:.0f}h old'} (> {MAX_COST_AGE_H:.0f}h)"
           for k, v in ages.items() if v is None or v > MAX_COST_AGE_H]
    return {"status": UNMEASURED if bad else MEASURED, "max_age_h": MAX_COST_AGE_H, **ages,
            "why": "; ".join(bad)}


def symbol_cost(symbol: str, markout: Any, surface: Any) -> dict[str, Any]:
    """One-way cost of resizing 1R on `symbol`, in R. UNMEASURED unless every input is a
    finite positive measurement."""
    slip = (((markout or {}).get("slip") or {}).get("by_symbol") or {}).get(symbol) \
        if isinstance(markout, dict) else None
    clean = (slip or {}).get("clean") or {}
    slip_r = _num((clean.get("r") or {}).get("mean"))
    slip_pts = _num((clean.get("pts") or {}).get("mean"))
    srow = ((surface or {}).get("symbols") or {}).get(symbol) if isinstance(surface, dict) \
        else None
    spread_pts = _pos((srow or {}).get("pooled_median_spread_pts"))
    missing = []
    if slip_r is None or slip_r == 0.0:
        missing.append("no finite non-zero clean markout slip in R")
    if slip_pts is None or slip_pts == 0.0:
        missing.append("no finite non-zero clean markout slip in points")
    if spread_pts is None:
        missing.append("no finite positive median spread on the spread surface")
    r_per_pt = (abs(slip_r / slip_pts) if not missing and slip_r and slip_pts else None)
    if not missing and _pos(r_per_pt) is None:
        missing.append("R-per-point ratio is not finite and positive")
    if missing:
        return {"status": UNMEASURED, "why": "; ".join(missing)}
    assert slip_r is not None and spread_pts is not None and r_per_pt is not None
    half = 0.5 * spread_pts * r_per_pt
    cost_r = abs(slip_r) + half
    if _pos(cost_r) is None:
        return {"status": UNMEASURED, "why": "cost is not finite and positive"}
    return {"status": MEASURED, "cost_r": round(cost_r, 6), "slip_r": round(slip_r, 6),
            "half_spread_r": round(half, 6), "spread_pts": spread_pts,
            "n_clean": (slip or {}).get("n_clean")}


# ------------------------------------------------------------------------------------- engine
def hourly_returns(trades: dict[str, list[tuple[datetime, float]]],
                   start: datetime, end: datetime) -> list[dict[str, float]]:
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
    names = list(target)
    hold = dict(target)
    logw = paid = 0.0
    n_reb = 0
    for i, row in enumerate(grid):
        w = sum(hold.values())
        for k in names:
            hold[k] *= max(1e-12, 1.0 + row.get(k, 0.0))
        w_new = sum(hold.values())
        logw += math.log(w_new / w)
        due = (period is not None and (i + 1) % period == 0) or (
            drift is not None and any(abs(hold[k] / w_new - target[k]) / target[k] > drift
                                      for k in names if target[k] > 0))
        if due:
            cost = min(0.5, sum(abs(hold[k] / w_new - target[k]) * RISK_UNIT * cost_r[k]
                                for k in names))
            paid += cost
            logw += math.log(1.0 - cost)
            hold = {k: target[k] * w_new * (1.0 - cost) for k in names}
            n_reb += 1
    return {"log_w": logw, "cost_paid": paid, "n_rebalances": n_reb}


def _nets(grid: list[dict[str, float]], target: dict[str, float],
          cost_r: dict[str, float]) -> dict[str, float]:
    base = simulate(grid, target, cost_r, None, None)["log_w"]
    out = {HOLD: 0.0}
    for name, period, drift in CANDIDATES:
        out[name] = simulate(grid, target, cost_r, period, drift)["log_w"] - base
    return out


def _resample(grid: list[dict[str, float]], rng: random.Random) -> list[dict[str, float]]:
    n = len(grid)
    out: list[dict[str, float]] = []
    while len(out) < n:
        s = rng.randrange(n)
        out.extend(grid[(s + j) % n] for j in range(min(BLOCK_H, n - len(out))))
    return out


def evaluate(trades: dict[str, list[tuple[datetime, float]]], target: dict[str, float],
             cost_r: dict[str, float], start: datetime, end: datetime,
             seed: int = 7) -> dict[str, Any]:
    tot = sum(target.values())
    target = {k: v / tot for k, v in target.items()}
    grid = hourly_returns(trades, start, end)
    days = len(grid) / 24.0
    base = simulate(grid, target, cost_r, None, None)
    rows = []
    for name, period, drift in CANDIDATES:
        res = simulate(grid, target, cost_r, period, drift)
        gross = simulate(grid, target, {k: 0.0 for k in cost_r}, period, drift)
        rows.append({
            "interval": name, "period_h": period, "drift_threshold": drift,
            "n_rebalances": res["n_rebalances"],
            "gross_gain_elogw_per_day": (gross["log_w"] - base["log_w"]) / days,
            "cost_elogw_per_day": (gross["log_w"] - res["log_w"]) / days,
            "net_gain_elogw_per_day": (res["log_w"] - base["log_w"]) / days})
    point = {HOLD: 0.0, **{r["interval"]: r["net_gain_elogw_per_day"] for r in rows}}
    ranked = sorted(point, key=lambda k: -point[k])
    best, runner = ranked[0], ranked[1]
    rng = random.Random(seed)
    wins = 0
    for _ in range(N_BOOT):
        nets = _nets(_resample(grid, rng), target, cost_r)
        wins += nets[best] > nets[runner]
    p_win = wins / N_BOOT
    if best == HOLD:
        chosen, why = HOLD, ("no candidate beats buy-and-hold net of cost; hold stands "
                             f"(best candidate {runner} {point[runner]:+.3e}/day)")
    elif p_win >= WIN_PROB:
        chosen, why = best, (f"{best} beats {runner} in {p_win:.0%} of {N_BOOT} block "
                             f"resamples (net {point[best]:+.3e}/day over hold)")
    else:
        chosen, why = None, (f"no clear winner: {best} beats {runner} in only {p_win:.0%} of "
                             f"resamples (< {WIN_PROB:.0%}); hold stands")
    return {"hours": len(grid), "days": round(days, 3),
            "hold_elogw_per_day": base["log_w"] / days, "candidates": rows,
            "point_best": best, "runner_up": runner, "p_beats_runner_up": p_win,
            "chosen": chosen, "verdict": chosen or "no_clear_winner",
            "chosen_net_gain_elogw_per_day": point[chosen] if chosen else None,
            "beats_hold": bool(chosen and chosen != HOLD), "why": why}


# ------------------------------------------------------------------------------------- build
def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def build(now: datetime | None = None, shadow_dir: Path = SHADOW_DIR, sleeves_path: Path = SLEEVES,
          markout_path: Path = MARKOUT, surface_path: Path = SPREAD_SURFACE) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    sleeves_doc = _read(sleeves_path)
    states = [_read(shadow_dir / n) for n in SHADOW_STATES]
    markout, surface = _read(markout_path), _read(surface_path)
    counts = key_counts(sleeves_doc, states)
    book = live_book(sleeves_doc)
    fresh = cost_freshness(markout, surface, now)

    per_sleeve: list[dict[str, Any]] = []
    per_symbol: dict[str, dict[str, Any]] = {}
    trades: dict[str, list[tuple[datetime, float]]] = {}
    target: dict[str, float] = {}
    costs: dict[str, float] = {}
    starts: list[datetime] = []
    for s in book:
        name, sym = str(s["name"]), str(s.get("symbol") or "").upper()
        row: dict[str, Any] = {"sleeve": name, "symbol": sym, "risk_frac": _num(s.get("risk_frac"))}
        per_sleeve.append(row)
        if sym not in per_symbol:
            per_symbol[sym] = (symbol_cost(sym, markout, surface) if fresh["status"] == MEASURED
                               else {"status": UNMEASURED, "why": f"stale cost: {fresh['why']}"})
        cost = per_symbol[sym]
        lname, fs = ledger_name(name), forward_start(s, states)
        why = None
        if counts.get(lname, 0) > 1:
            why = f"{lname} is SHARED by {counts[lname]} keys; its rows are not this sleeve's"
        elif fs is None:
            why = "no forward_start: the rows cannot be proven forward (no look-ahead)"
        elif not (shadow_dir / lname).exists():
            why = f"{lname} is absent on this host"
        elif cost["status"] != MEASURED:
            why = f"{sym} cost UNMEASURED: {cost['why']}"
        elif _pos(row["risk_frac"]) is None:
            why = "no finite positive allocator fraction to hold as target"
        if why is not None:
            row.update(status=UNMEASURED, why=why)
            continue
        assert fs is not None
        tr, no_exit = forward_trades(_read(shadow_dir / lname), fs)
        row.update(forward_start=fs.isoformat(), n_forward=len(tr), n_no_exit_time=no_exit)
        trades[name], target[name], costs[name] = tr, float(row["risk_frac"]), cost["cost_r"]
        starts.append(fs)

    doc: dict[str, Any] = {
        "source": "rebalance_interval", "generated_at": now.isoformat(timespec="seconds"),
        "report_only": True,
        "sizing_effect": "none -- no allocator, decision_core, gateway or promoter reads this",
        "assumptions": {"risk_unit": RISK_UNIT,
                        "risk_unit_is": "ASSUMPTION: wealth at risk per 1R at full target weight; "
                                        "a rebalance moving |dw| pays |dw|*risk_unit*cost_R",
                        "booking": "each trade's R at its exit time"},
        "rules": {"min_day_coverage": MIN_DAY_COVERAGE, "max_cost_age_h": MAX_COST_AGE_H,
                  "min_hours": MIN_HOURS, "win_prob": WIN_PROB, "n_boot": N_BOOT,
                  "block_h": BLOCK_H},
        "candidates_considered": [HOLD] + [c[0] for c in CANDIDATES],
        "cost_freshness": fresh, "n_live_sleeves": len(book),
        "sleeves": per_sleeve, "symbols": per_symbol,
        "cost_sources": {"markout": _rel(markout_path), "spread_surface": _rel(surface_path)},
    }
    if starts:
        start = max(starts)
        days = max(1, math.ceil((now - start).total_seconds() / 86400))
        for row in per_sleeve:
            if row["sleeve"] not in trades:
                continue
            tr = [t for t in trades[row["sleeve"]] if t[0] >= start]
            cov = len({(t[0] - start).days for t in tr}) / days
            row["day_coverage"] = round(cov, 4)
            if cov < MIN_DAY_COVERAGE:
                row.update(status=UNMEASURED,
                           why=f"ledger silent: rows on {cov:.0%} of {days} days "
                               f"(< {MIN_DAY_COVERAGE:.0%})")
                for d in (trades, target, costs):
                    d.pop(row["sleeve"])
            else:
                row["status"] = MEASURED
                trades[row["sleeve"]] = tr
        doc["common_forward_start"] = start.isoformat()
    n_meas = len(trades)
    doc["n_measured_sleeves"] = n_meas
    counts_txt = f"{n_meas} of {len(book)} live sleeve(s) measured"
    if n_meas < 2:
        doc.update(status=UNMEASURED, chosen=None, verdict=None,
                   why=f"{counts_txt}; volatility pumping needs at least two")
        return doc
    start = max(_ts(r["forward_start"]) or now for r in per_sleeve if r["sleeve"] in trades)
    if (now - start) < timedelta(hours=MIN_HOURS):
        doc.update(status=UNMEASURED, chosen=None, verdict=None,
                   why=f"the common forward window is under {MIN_HOURS // 24} days")
        return doc
    res = evaluate(trades, target, costs, start, now)
    status = MEASURED if n_meas == len(book) else PARTIAL
    why = res.pop("why")
    doc.update(status=status, **res,
               why=(why if status == MEASURED else f"PARTIAL ({counts_txt}): {why}"))
    return doc


def main(argv: list[str] | None = None) -> int:
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    tmp.replace(OUT)
    print(f"rebalance_interval: {doc['status']} verdict={doc.get('verdict')} "
          f"({doc['n_measured_sleeves']}/{doc['n_live_sleeves']} sleeves) -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
