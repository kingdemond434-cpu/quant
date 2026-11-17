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
  * Cost per sleeve = max(|clean markout slip R|, SLIP_FLOOR_PTS in R) (`reports/markout.json`
    slip.by_symbol, #391) plus half the spread surface's median spread, both put in R through
    tick_size / the sleeve's own stop distance (median |exit - entry| / |R| of forward rows).
  * Scalp ledgers (`opened_at`/`closed_at`) are shifted by the clock's stamped
    `broker_offset_h`, else by `h1_source.broker_utc_offset_hours` (0.0 today: the desk treats
    them as UTC). SCALP SLEEVES ARE ALWAYS UNMEASURED: their rows carry no entry/exit prices,
    so no stop -- and no R-per-point -- can be inferred. A book holding any scalp sleeve can
    therefore only ever read PARTIAL.
  * Either cost source older than MAX_COST_AGE_H (72h,
    as run_desk_integrity), or any input non-positive / non-finite -> UNMEASURED. Never zero.

THE CHOICE needs margin: the hourly book returns are block-bootstrapped and a non-hold interval
is chosen only when it beats HOLD in >= WIN_PROB of resamples (mean over SEEDS, block >= the
longest candidate period); otherwise "no clear winner" and the report says hold stands.

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
#: A sleeve needs rows on at least this share of the window's days.
MIN_DAY_COVERAGE = 0.5
#: Cost inputs older than this are stale (run_desk_integrity's cost_surface horizon).
MAX_COST_AGE_H = 72.0
#: Bootstrap: a non-hold interval must beat HOLD in this share of resamples.
WIN_PROB = 0.80
N_BOOT = 200
#: Block length: at least a week and at least the longest fixed candidate period.
BLOCK_H = 168
#: Below three blocks the circular block bootstrap is a rotation of the whole series and its
#: p measures phase, not sampling noise (audit v3: 5-7 day noise windows gave p = 1.00).
MIN_HOURS = 3 * BLOCK_H
#: Rows a sleeve needs before its inferred stop (median |exit-entry|/|R|) is used.
MIN_STOP_ROWS = 5
#: Seeds the bootstrap is run under; the verdict uses the MEAN p and the spread is reported.
SEEDS = (7, 11, 13, 17, 19)
#: Clock skew tolerated on a cost stamp before a future stamp is refused.
MAX_SKEW_S = 60.0
#: Slip noise floor, in points: a measured slip below half a point is indistinguishable from
#: rounding, so the charge never falls under it.
SLIP_FLOOR_PTS = 0.5
#: |R| below this is too small to infer a stop distance from |exit - entry| / |R|.
MIN_R_FOR_STOP = 0.1
#: The most recent share of the window must also be covered (trailing silence counts).
RECENT_SHARE = 0.25
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


def broker_offset(name: str, states: list[Any]) -> float | None:
    """The broker-minus-UTC hours stamped for this clock (scalp_shadow / shadow_forward)."""
    for st in states:
        if not isinstance(st, dict):
            continue
        for row in (st.get(name), (st.get("sleeves") or {}).get(name)
                    if isinstance(st.get("sleeves"), dict) else None):
            if isinstance(row, dict) and _num(row.get("broker_offset_h")) is not None:
                return _num(row.get("broker_offset_h"))
    return None


def _desk_offset() -> float:
    """The desk's own broker-vs-UTC offset (h1_source; 0.0 when it cannot be measured)."""
    try:
        from research.h1_source import broker_utc_offset_hours
        try:
            import MetaTrader5 as mt5_mod
        except Exception:
            mt5_mod = None
        v = _num(broker_utc_offset_hours(mt5_mod))
        return v if v is not None else 0.0
    except Exception:
        return 0.0


def forward_trades(rows: Any, start: datetime, offset_h: float | None = 0.0
                   ) -> tuple[list[tuple[datetime, float]], int, list[float], bool]:
    """(exit-time-booked (when_utc, R) for trades ENTERED at or after `start`, n dropped for no
    exit time, per-trade stop distances in price, needs_offset). The scalp schema
    (`opened_at`/`closed_at`) is stamped on the BROKER clock (scalp_shadow.py:203-209) and is
    shifted to UTC by `offset_h`; with no offset known it is refused (needs_offset True)."""
    out, no_exit, stops = [], 0, []
    lst = rows if isinstance(rows, list) else []
    scalp = any(isinstance(r, dict) and r.get("opened_at") and not r.get("entry_time")
                for r in lst)
    if scalp and offset_h is None:
        offset_h = _desk_offset()
    shift = timedelta(hours=(offset_h or 0.0) if scalp else 0.0)
    for row in lst:
        if not isinstance(row, dict):
            continue
        entry = _ts(row.get("entry_time") or row.get("opened_at"))
        entry = entry - shift if entry is not None else None
        r = _num(row.get("r_multiple"))
        if r is None:
            r = _num(row.get("r"))
        if entry is None or r is None or entry < start:
            continue
        ex = _ts(row.get("exit_time") or row.get("closed_at") or row.get("close_time"))
        ex = ex - shift if ex is not None else None
        if ex is None or ex < entry:
            no_exit += 1
            continue
        out.append((ex, r))
        px_in, px_out = _num(row.get("entry")), _num(row.get("exit"))
        if px_in is not None and px_out is not None and abs(r) >= MIN_R_FOR_STOP:
            st = abs(px_out - px_in) / abs(r)
            if st > 0 and math.isfinite(st):
                stops.append(st)
    out.sort()
    return out, no_exit, stops, False


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
    bad += [f"{k[:-6]} is {-v:.2f}h in the FUTURE (> {MAX_SKEW_S:.0f}s skew)"
            for k, v in ages.items() if v is not None and v < -MAX_SKEW_S / 3600.0]
    return {"status": UNMEASURED if bad else MEASURED, "max_age_h": MAX_COST_AGE_H, **ages,
            "why": "; ".join(bad)}


def symbol_cost(symbol: str, markout: Any, surface: Any,
                stop_price: float | None) -> dict[str, Any]:
    """One-way cost of resizing 1R, in R. R-per-point = tick_size / stop distance (the sleeve's
    own stop, inferred from its forward rows), never a ratio of slip means. Slip is floored at
    SLIP_FLOOR_PTS. UNMEASURED unless every input is a finite positive measurement, and the
    positivity is checked on the exact value the engine is given."""
    slip = (((markout or {}).get("slip") or {}).get("by_symbol") or {}).get(symbol) \
        if isinstance(markout, dict) else None
    clean = (slip or {}).get("clean") or {}
    slip_r = _num((clean.get("r") or {}).get("mean"))
    srow = ((surface or {}).get("symbols") or {}).get(symbol) if isinstance(surface, dict) \
        else None
    spread_pts = _pos((srow or {}).get("pooled_median_spread_pts"))
    tick = _pos((srow or {}).get("tick_size"))
    stop = _pos(stop_price)
    missing = []
    if slip_r is None:
        missing.append("no finite clean markout slip in R")
    if spread_pts is None:
        missing.append("no finite positive median spread on the spread surface")
    if tick is None:
        missing.append("no finite positive tick_size on the spread surface")
    if stop is None:
        missing.append(f"no inferred stop: fewer than {MIN_STOP_ROWS} forward rows carry "
                       f"entry/exit prices with |R| >= {MIN_R_FOR_STOP} (scalp ledgers never do)")
    if missing:
        return {"status": UNMEASURED, "why": "; ".join(missing)}
    assert slip_r is not None and spread_pts is not None and tick is not None and stop
    r_per_pt = tick / stop
    floor_r = SLIP_FLOOR_PTS * r_per_pt
    slip_used = max(abs(slip_r), floor_r)
    half = 0.5 * spread_pts * r_per_pt
    cost_r = slip_used + half
    if _pos(cost_r) is None or _pos(r_per_pt) is None:
        return {"status": UNMEASURED, "why": "cost or R-per-point is not finite and positive"}
    return {"status": MEASURED, "cost_r": cost_r, "cost_r_display": round(cost_r, 6),
            "slip_r": slip_r, "slip_r_charged": slip_used, "slip_floor_r": floor_r,
            "half_spread_r": half, "spread_pts": spread_pts, "r_per_pt": r_per_pt,
            "stop_price": stop, "n_clean": (slip or {}).get("n_clean")}


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
    if len(grid) < MIN_HOURS:
        return {"status": UNMEASURED, "hours": len(grid), "chosen": None, "verdict": None,
                "p_beats_hold": None, "candidates": [],
                "why": f"{len(grid)}h window < {MIN_HOURS}h (3 x {BLOCK_H}h blocks): the "
                       "block bootstrap would measure phase, not noise"}
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
    point = {HOLD: 0.0, **{r["interval"]: r["net_gain_elogw_per_day"] for r in rows}}
    best = max(point, key=lambda k: point[k])
    p_seeds: list[float] = []
    if best != HOLD:
        for sd in (seed, *[x for x in SEEDS if x != seed]):
            rng = random.Random(sd)  # noqa: S311 - resampling, not crypto
            wins = sum(_nets(_resample(grid, rng), target, cost_r)[best] > 0.0
                       for _ in range(N_BOOT))
            p_seeds.append(wins / N_BOOT)
    p_win = sum(p_seeds) / len(p_seeds) if p_seeds else None
    if best == HOLD:
        chosen, why = HOLD, "no candidate beats buy-and-hold net of cost; hold stands"
    elif p_win is not None and p_win >= WIN_PROB:
        chosen, why = best, (f"{best} beats hold in {p_win:.0%} of block resamples (mean over "
                             f"{len(p_seeds)} seeds; net {point[best]:+.3e}/day)")
    else:
        chosen, why = None, (f"no clear winner: {best} beats hold in only {p_win:.0%} of "
                             f"resamples (< {WIN_PROB:.0%}); hold stands")
    return {"hours": len(grid), "days": round(days, 3),
            "hold_elogw_per_day": base["log_w"] / days, "candidates": rows,
            "point_best": best, "p_beats_hold": p_win, "p_beats_hold_by_seed": p_seeds,
            "p_spread": (max(p_seeds) - min(p_seeds)) if p_seeds else None,
            "chosen": chosen, "verdict": chosen or "no_clear_winner",
            "chosen_net_gain_elogw_per_day": point[chosen] if chosen else None,
            "beats_hold": bool(chosen and chosen != HOLD), "why": why, "status": MEASURED}


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
        lname, fs = ledger_name(name), forward_start(s, states)
        tr: list[tuple[datetime, float]] = []
        stops: list[float] = []
        no_exit, needs_off = 0, False
        if fs is not None and (shadow_dir / lname).exists():
            tr, no_exit, stops, needs_off = forward_trades(
                _read(shadow_dir / lname), fs, broker_offset(name, states))
        stop = sorted(stops)[len(stops) // 2] if len(stops) >= MIN_STOP_ROWS else None
        cost = (symbol_cost(sym, markout, surface, stop) if fresh["status"] == MEASURED
                else {"status": UNMEASURED, "why": f"stale cost: {fresh['why']}"})
        per_symbol.setdefault(sym, {})[name] = cost
        why = None
        if counts.get(lname, 0) > 1:
            why = f"{lname} is SHARED by {counts[lname]} keys; its rows are not this sleeve's"
        elif fs is None:
            why = "no forward_start: the rows cannot be proven forward (no look-ahead)"
        elif not (shadow_dir / lname).exists():
            why = f"{lname} is absent on this host"
        elif needs_off:
            why = "scalp-schema ledger (broker clock) with no broker_offset_h stamped"
        elif cost["status"] != MEASURED:
            why = f"{sym} cost UNMEASURED: {cost['why']}"
        elif _pos(row["risk_frac"]) is None:
            why = "no finite positive allocator fraction to hold as target"
        if why is not None:
            row.update(status=UNMEASURED, why=why)
            continue
        assert fs is not None
        row.update(forward_start=fs.isoformat(), n_forward=len(tr), n_no_exit_time=no_exit)
        trades[name], target[name], costs[name] = tr, float(row["risk_frac"]), float(cost["cost_r"])
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
                  "block_h": BLOCK_H, "seeds": list(SEEDS), "comparator": "hold",
                  "slip_floor_pts": SLIP_FLOOR_PTS, "max_skew_s": MAX_SKEW_S,
                  "recent_share": RECENT_SHARE,
                  "r_per_point": "tick_size / INFERRED stop: median |exit-entry|/|R| over >= "
                                 f"{MIN_STOP_ROWS} forward rows (R is net of cost and partial "
                                 "exits, so the stop is approximate)",
                  "slip_floor_bias": "the 0.5pt floor only ever RAISES cost, so it biases the "
                                     "verdict toward hold (conservative; report-only)",
                  "scalp_sleeves": "always UNMEASURED (ledgers carry no prices); a book with "
                                   "any scalp sleeve reads PARTIAL at best",
                  "min_window": "3 x block_h; shorter windows are UNMEASURED"},
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
            tr = [t for t in trades[row["sleeve"]] if start <= t[0] <= now]
            hit = {(t[0] - start).days for t in tr}
            cov = len(hit) / days
            recent_days = max(1, math.ceil(days * RECENT_SHARE))
            rcov = len({d for d in hit if d >= days - recent_days}) / recent_days
            row["day_coverage"], row["recent_day_coverage"] = round(cov, 4), round(rcov, 4)
            if cov < MIN_DAY_COVERAGE or rcov < MIN_DAY_COVERAGE:
                row.update(status=UNMEASURED,
                           why=f"ledger silent: rows on {cov:.0%} of {days} days and "
                               f"{rcov:.0%} of the last {recent_days} (each must be >= "
                               f"{MIN_DAY_COVERAGE:.0%})")
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
    # The SAME window the coverage check used: no leading zero-fill.
    start = max(starts)
    if (now - start) < timedelta(hours=MIN_HOURS):
        doc.update(status=UNMEASURED, chosen=None, verdict=None,
                   why=f"the common forward window is under {MIN_HOURS}h (3 bootstrap blocks)")
        return doc
    res = evaluate(trades, target, costs, start, now)
    if res.pop("status") != MEASURED:
        doc.update(status=UNMEASURED, **res)
        return doc
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
