#!/usr/bin/env python3
"""ACTIVE POSITION MANAGER -- in-trade exit overlays over every certified sleeve's own entries.

WHAT IT ASKS. A sleeve's entry and its baseline exit (stop / target / TTL, as replayed by
`shadow_forward.py` into `reports/shadow/**/ledger_<sleeve>.json`) are fixed inputs. This organ
asks whether MANAGING the open trade -- the way a discretionary trader watches a position and
reacts -- would have bought R per trade over leaving it alone:

    time_stop        exit at the close of the k-th H1 bar the trade has been open
    breakeven        after a CLOSED bar shows +x R favourable, the stop moves to entry
    atr_trail        chandelier: stop = best close-extreme - k * ATR14 (prior bars), never loosened
    partial          close half at +x R the first bar it trades there, rest to the baseline exit
    regime_exit      leave at the first new broker day whose PRIOR closed day moved the pair's
                     currency-leg spread (libs.portfolio.leg_factors) >= k sigma against the side
    adverse_spread   leave at a bar close whose spread is >= k x the symbol's trailing median

It EXTENDS what exists, it does not duplicate it: `exit_study.py` (breakeven/TP2/fast-fail on
the armed gold windows only, one-shot) and the live `mt5desk/position_manager.py` ratchet
(BREAKEVEN_TRIGGER_R, chandelier K_TREND/K_STALLED) are the policies the desk already uses;
this is the per-sleeve, every-sleeve, trial-charged and gauntlet-judged replay of that family,
and the evidence the live ratchet's parameters never had per sleeve.

CONSERVATIVE BY CONSTRUCTION. An overlay can only act on H1 bars that lie WHOLLY inside the
baseline trade (open >= entry, close <= baseline exit); the bar that holds the baseline exit is
never used, so an overlay never claims an exit that the baseline's own intrabar fill may have
pre-empted. A trigger arms at a bar's CLOSE and can fill no earlier than the NEXT bar; a gap
through a stop fills at the bar's open. Overlays never extend a trade.

R ARITHMETIC. The ledger carries entry, exit and net R but not the stop, so the per-trade risk
is recovered as |exit - entry| / |R| where |R| >= 0.2 (the sleeve's median elsewhere); the
overlay's R is the baseline net R plus the side-signed price change of the exit, in R, minus
the COST DELTA: half the spread at the overlay's exit hour minus half at the baseline's, from
`research/cost_surfaces.cost_for(hour=...)` (the fill-hour cost surface), falling back to the
bar's own recorded spread, stamped per cell with its basis.

TRIALS. Every (sleeve x policy x param) cell is charged ONCE over its lifetime
(`data/position_overlay_charged.json` -> `data/null_pass_trials.jsonl`, family
`position_overlay`, which `libs.research.experiment_ledger` already sums). The grid is
fixed and small (10 cells per sleeve); a re-run charges nothing new.

THE BAR. Per (sleeve, policy) the parameter is chosen walk-forward on trades whose EXIT +
`EMBARGO_H` precedes the scored trade's ENTRY (purged, embargoed, expanding); the out-of-sample
per-trade lift d_i = R_overlay - R_baseline is judged with
`libs.validation.dsr.deflated_sharpe_ratio` at N = max(5, cells charged for the sleeve),
Var(SR) = 1/(T-1), DSR >= 0.95 (t ~ 2.84 at N = 5) -- the Tier S bar. A sleeve or policy short
of trades is UNMEASURED with its n, never a zero.

REPORT ONLY -> reports/POSITION_MANAGER.json. No money path reads it; the live wiring of
survivors is a laptop spec (patches/active_position_manager/README.md), principal-gated.

    python desks/mt5/research/position_overlay.py --once
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SHADOW_DIR = DESK / "reports" / "shadow"
UNIVERSE_DIR = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
OUT = DESK / "reports" / "POSITION_MANAGER.json"
CHARGED = DESK / "data" / "position_overlay_charged.json"
TRIALS = DESK / "data" / "null_pass_trials.jsonl"

SCHEMA = "position-manager-1"
FAMILY = "position_overlay"
UNMEASURED = "UNMEASURED"
EMBARGO_H = 24
MIN_TRAIN = 20          # prior trades before a walk-forward choice may score anything
MIN_OOS = 20            # scored trades before a (sleeve, policy) verdict is a number
TIER_S_MIN_N = 5
DSR_THRESHOLD = 0.95
MIN_R_FOR_RISK = 0.2
ATR_N = 14
SPREAD_MED_N = 240
REGIME_WIN = 60

#: The fixed grid. Adding a param here charges one more trial per sleeve.
GRID: dict[str, tuple[float, ...]] = {
    "time_stop": (3.0, 6.0),
    "breakeven": (0.5, 1.0),
    "atr_trail": (2.0, 3.0),
    "partial": (1.0,),
    "regime_exit": (1.5, 2.0),
    "adverse_spread": (3.0,),
}


def cell_id(sleeve: str, policy: str, param: float) -> str:
    spec = json.dumps({"family": FAMILY, "sleeve": sleeve, "policy": policy,
                       "param": param, "embargo_h": EMBARGO_H, "bars": "H1"}, sort_keys=True)
    return "po_" + hashlib.sha256(spec.encode()).hexdigest()[:16]


@dataclass
class Trade:
    sleeve: str
    symbol: str
    entry_time: datetime
    exit_time: datetime
    side: int
    entry: float
    exit: float
    r: float
    forward: bool
    risk: float = 0.0


@dataclass
class Bars:
    """H1 bars as plain arrays; `t` is each bar's OPEN, UTC epoch seconds."""
    t: np.ndarray
    o: np.ndarray
    h: np.ndarray
    lo: np.ndarray
    c: np.ndarray
    spread: np.ndarray            # points, NaN when absent
    point: float | None
    atr: np.ndarray = field(default_factory=lambda: np.zeros(0))
    spread_med: np.ndarray = field(default_factory=lambda: np.zeros(0))

    def __post_init__(self) -> None:
        n = len(self.c)
        prev = np.concatenate([[np.nan], self.c[:-1]]) if n else self.c
        tr = np.nanmax(np.vstack([self.h - self.lo, np.abs(self.h - prev),
                                  np.abs(self.lo - prev)]), axis=0) if n else self.c
        atr = np.full(n, np.nan)
        for i in range(ATR_N, n):
            atr[i] = float(np.mean(tr[i - ATR_N:i]))      # bars strictly before i
        self.atr = atr
        med = np.full(n, np.nan)
        sp = self.spread
        for i in range(30, n):
            w = sp[max(0, i - SPREAD_MED_N):i]
            w = w[np.isfinite(w)]
            if w.size >= 30:
                med[i] = float(np.median(w))
        self.spread_med = med


def _ts(v: Any) -> datetime | None:
    try:
        import pandas as pd
        t = pd.Timestamp(v)
    except (ValueError, TypeError):
        return None
    if t is pd.NaT:
        return None
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    out: datetime = t.to_pydatetime()
    return out


def certified_sleeves(path: Path = SLEEVES) -> dict[str, dict[str, Any]] | None:
    """Sleeve rows not RETIRED, by name; None when the registry is unreadable (then every
    ledger is read and the report says so)."""
    try:
        rows = json.loads(path.read_text("utf-8")).get("sleeves")
    except (OSError, ValueError, AttributeError):
        return None
    it = rows.values() if isinstance(rows, dict) else rows if isinstance(rows, list) else []
    return {str(r["name"]): r for r in it
            if isinstance(r, dict) and r.get("name") and r.get("status") != "RETIRED"}


def load_trades(shadow_dir: Path = SHADOW_DIR,
                registry: dict[str, dict[str, Any]] | None = None) -> dict[str, list[Trade]]:
    out: dict[str, list[Trade]] = {}
    for f in sorted(glob.glob(str(shadow_dir / "**" / "ledger_*.json"), recursive=True)):
        p = Path(f)
        sleeve = p.stem[len("ledger_"):]
        reg = (registry or {}).get(sleeve)
        if registry is not None and reg is None:
            continue
        symbol = str((reg or {}).get("symbol") or sleeve.split("_", 1)[0]).upper()
        try:
            rows = json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(rows, list):
            continue
        ts: list[Trade] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            e, x = _ts(row.get("entry_time")), _ts(row.get("exit_time"))
            try:
                r = float(row["r_multiple"])
                side = int(row.get("side") or 0)
                ep, xp = float(row["entry"]), float(row["exit"])
            except (KeyError, TypeError, ValueError):
                continue
            if e is None or x is None or side not in (1, -1) or not all(
                    math.isfinite(v) for v in (r, ep, xp)):
                continue
            ts.append(Trade(sleeve, symbol, e, x, side, ep, xp, r, row.get("phase") == "forward"))
        if ts:
            ts.sort(key=lambda t: t.entry_time)
            _fill_risk(ts)
            out[sleeve] = [t for t in ts if t.risk > 0]
    return out


def _fill_risk(ts: list[Trade]) -> None:
    known = [abs(t.exit - t.entry) / abs(t.r) for t in ts if abs(t.r) >= MIN_R_FOR_RISK]
    med = statistics.median(known) if known else 0.0
    for t in ts:
        t.risk = abs(t.exit - t.entry) / abs(t.r) if abs(t.r) >= MIN_R_FOR_RISK else med


def load_bars(symbol: str, universe_dir: Path = UNIVERSE_DIR) -> Bars | None:
    p = universe_dir / f"{symbol}_H1.parquet"
    try:
        import pandas as pd
        d = pd.read_parquet(p)
    except Exception:
        return None
    point: float | None = None
    try:
        reg = json.loads((universe_dir / "universe.json").read_text("utf-8")).get(symbol) or {}
        point = float(reg.get("tick_size") or 0) or None
    except (OSError, ValueError, TypeError, AttributeError):
        point = None
    idx = d.index if isinstance(d.index, pd.DatetimeIndex) else pd.DatetimeIndex(d["time"])
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    sp = (d["spread"].to_numpy(dtype=float) if "spread" in d.columns
          else np.full(len(d), np.nan))
    return Bars(t=np.asarray(idx.as_unit("s").asi8, dtype=np.int64), o=d["open"].to_numpy(dtype=float),
                h=d["high"].to_numpy(dtype=float), lo=d["low"].to_numpy(dtype=float),
                c=d["close"].to_numpy(dtype=float), spread=sp, point=point)


# ---------------------------------------------------------------- the policies (pure)

#: (exit price, exit bar index or None for "baseline", fraction closed at it).
Exit = tuple[float, int, float]


def _window(b: Bars, tr: Trade) -> range:
    e, x = int(tr.entry_time.timestamp()), int(tr.exit_time.timestamp())
    i0 = int(np.searchsorted(b.t, e, side="left"))
    i1 = int(np.searchsorted(b.t, x - 3600, side="right"))   # bars whose close <= exit
    return range(i0, max(i0, i1))


def _fav(tr: Trade, price: float) -> float:
    return tr.side * (price - tr.entry) / tr.risk


def pol_time_stop(b: Bars, tr: Trade, k: float, _ctx: Any = None) -> Exit | None:
    w = _window(b, tr)
    j = w.start + int(k) - 1
    return (float(b.c[j]), j, 1.0) if j in w else None


def pol_breakeven(b: Bars, tr: Trade, x: float, _ctx: Any = None) -> Exit | None:
    armed = False
    for i in _window(b, tr):
        if armed:
            if tr.side * (b.o[i] - tr.entry) <= 0:
                return float(b.o[i]), i, 1.0
            if (b.lo[i] <= tr.entry) if tr.side > 0 else (b.h[i] >= tr.entry):
                return tr.entry, i, 1.0
        best = b.h[i] if tr.side > 0 else b.lo[i]
        if _fav(tr, float(best)) >= x and _fav(tr, float(b.c[i])) > 0:
            armed = True
    return None


def pol_atr_trail(b: Bars, tr: Trade, k: float, _ctx: Any = None) -> Exit | None:
    stop: float | None = None
    ext: float | None = None
    for i in _window(b, tr):
        if stop is not None:
            if tr.side > 0 and b.lo[i] <= stop:
                return float(min(b.o[i], stop)), i, 1.0
            if tr.side < 0 and b.h[i] >= stop:
                return float(max(b.o[i], stop)), i, 1.0
        a = b.atr[i] if i < len(b.atr) else np.nan
        if not np.isfinite(a):
            continue
        ext = float(b.c[i]) if ext is None else (max(ext, float(b.c[i])) if tr.side > 0
                                                  else min(ext, float(b.c[i])))
        if _fav(tr, ext) <= 0:
            continue
        cand = ext - tr.side * k * float(a)
        stop = cand if stop is None else (max(stop, cand) if tr.side > 0 else min(stop, cand))
    return None


def pol_partial(b: Bars, tr: Trade, x: float, _ctx: Any = None) -> Exit | None:
    lvl = tr.entry + tr.side * x * tr.risk
    for i in _window(b, tr):
        if (b.h[i] >= lvl) if tr.side > 0 else (b.lo[i] <= lvl):
            px = float(max(b.o[i], lvl)) if tr.side > 0 else float(min(b.o[i], lvl))
            return px, i, 0.5
    return None


def pol_adverse_spread(b: Bars, tr: Trade, k: float, _ctx: Any = None) -> Exit | None:
    for i in _window(b, tr):
        m = b.spread_med[i] if i < len(b.spread_med) else np.nan
        if np.isfinite(m) and m > 0 and np.isfinite(b.spread[i]) and b.spread[i] >= k * m:
            return float(b.c[i]), i, 1.0
    return None


def regime_z(frame: Any, symbol: str) -> dict[str, float] | None:
    """date -> z of the pair's currency-leg spread return that day vs the REGIME_WIN days
    before it (point-in-time: each z uses only rows strictly before its own date)."""
    if frame is None:
        return None
    try:
        from libs.risk.fx_factors import split_pair
    except ImportError:
        return None
    pair = split_pair(symbol)
    if not pair or pair[0] not in frame.columns or pair[1] not in frame.columns:
        return None
    leg = (frame[pair[0]] - frame[pair[1]]).to_numpy(dtype=float)
    dates = [str(d) for d in frame.index]
    out: dict[str, float] = {}
    for i in range(REGIME_WIN, len(leg)):
        w = leg[i - REGIME_WIN:i]
        w = w[np.isfinite(w)]
        sd = float(np.std(w)) if w.size >= 20 else 0.0
        if sd > 0 and np.isfinite(leg[i]):
            out[dates[i]] = float((leg[i] - np.mean(w)) / sd)
    return out


def pol_regime_exit(b: Bars, tr: Trade, k: float, ctx: Any = None) -> Exit | None:
    z: dict[str, float] | None = ctx
    if not z:
        return None
    d0 = tr.entry_time.date()
    for i in _window(b, tr):
        day = datetime.fromtimestamp(int(b.t[i]), tz=UTC).date()
        if day <= d0:
            continue
        prev = (day - timedelta(days=1)).isoformat()
        zz = z.get(prev)
        if zz is not None and tr.side * zz <= -k:
            return float(b.o[i]), i, 1.0
        d0 = day
    return None


POLICIES: dict[str, Callable[..., Exit | None]] = {
    "time_stop": pol_time_stop, "breakeven": pol_breakeven, "atr_trail": pol_atr_trail,
    "partial": pol_partial, "regime_exit": pol_regime_exit,
    "adverse_spread": pol_adverse_spread,
}


# ---------------------------------------------------------------- costs and lift

class CostModel:
    """Half-spread at an exit hour, in price, from the fill-hour cost surface; the bar's own
    spread when the surface has nothing for the instrument."""

    def __init__(self, surface: dict[str, Any] | None) -> None:
        self.surface = surface
        self.basis: set[str] = set()

    def half_spread(self, symbol: str, b: Bars, i: int | None, when: datetime) -> float:
        if b.point is None:
            self.basis.add(UNMEASURED)
            return 0.0
        pts: float | None = None
        if self.surface:
            try:
                from research.cost_surfaces import cost_for
                t = cost_for(symbol, hour=when.hour, surface=self.surface)["terms"]["spread_points"]
                if t.get("status") in ("MEASURED", "PRIOR") and t.get("value") is not None:
                    pts = float(t["value"])
                    self.basis.add("cost_surface:" + str(t.get("level")))
            except Exception:
                pts = None
        if pts is None and i is not None and 0 <= i < len(b.spread) and np.isfinite(b.spread[i]):
            pts = float(b.spread[i])
            self.basis.add("bar_spread")
        if pts is None:
            self.basis.add(UNMEASURED)
            return 0.0
        return 0.5 * pts * b.point


def overlay_r(tr: Trade, ex: Exit | None, b: Bars, costs: CostModel) -> float:
    """Net R of the managed trade (== baseline R when the overlay never fires)."""
    if ex is None:
        return tr.r
    px, i, frac = ex
    when = datetime.fromtimestamp(int(b.t[i]) + 3600, tz=UTC)
    ib = int(np.searchsorted(b.t, int(tr.exit_time.timestamp()), side="right")) - 1
    dcost = (costs.half_spread(tr.symbol, b, i, when)
             - costs.half_spread(tr.symbol, b, ib if ib >= 0 else None, tr.exit_time)) / tr.risk
    move = tr.side * (px - tr.exit) / tr.risk
    return tr.r + frac * (move - dcost)


# ---------------------------------------------------------------- the judge

def _dsr(d: Sequence[float], n_trials: int) -> dict[str, Any]:
    a = np.asarray(d, dtype=float)
    if a.size < MIN_OOS or float(np.std(a, ddof=1)) == 0.0:
        return {"status": UNMEASURED, "n": int(a.size),
                "why": f"{a.size} scored trades < {MIN_OOS}" if a.size < MIN_OOS
                else "zero variance: the overlay never changed an exit"}
    from libs.validation.dsr import deflated_sharpe_ratio
    n = max(TIER_S_MIN_N, n_trials)
    res = deflated_sharpe_ratio(a, n_trials=n, variance_of_sharpes=1.0 / (a.size - 1),
                                threshold=DSR_THRESHOLD)
    return {"status": "MEASURED", "n": int(a.size), "n_trials": n,
            "sr": round(float(res.sr_observed), 4), "sr0": round(float(res.sr0_threshold), 4),
            "dsr": round(float(res.dsr), 4), "passed": bool(res.passed),
            "rule": "PSR(d) vs E[max SR], N=max(5, cells charged for the sleeve), "
                    "Var(SR)=1/(T-1), DSR>=0.95"}


def walk_forward(trades: Sequence[Trade], lifts: dict[float, list[float]]) -> tuple[
        list[float], list[float | None], list[bool]]:
    """Purged expanding walk-forward param choice: for trade j, the param with the best mean
    lift over trades whose exit + EMBARGO_H < trade j's entry. Returns (oos d, chosen, fwd)."""
    d: list[float] = []
    chosen: list[float | None] = []
    fwd: list[bool] = []
    exits = [t.exit_time for t in trades]
    for j, tj in enumerate(trades):
        cut = tj.entry_time - timedelta(hours=EMBARGO_H)
        train = [i for i in range(j) if exits[i] < cut]
        if len(train) < MIN_TRAIN:
            continue
        best = max(lifts, key=lambda p: (float(np.mean([lifts[p][i] for i in train])), -p))
        d.append(lifts[best][j])
        chosen.append(best)
        fwd.append(tj.forward)
    return d, chosen, fwd


def judge_sleeve(sleeve: str, trades: list[Trade], bars: Bars | None, costs: CostModel,
                 regime: dict[str, float] | None) -> dict[str, Any]:
    n_cells = sum(len(v) for v in GRID.values())
    base = [t.r for t in trades]
    row: dict[str, Any] = {"symbol": trades[0].symbol if trades else None, "n_trades": len(trades),
                           "n_forward": sum(t.forward for t in trades), "cells_charged": n_cells,
                           "baseline_r_per_trade": round(float(np.mean(base)), 4) if base else None,
                           "policies": {}}
    if bars is None:
        row["status"] = UNMEASURED
        row["why"] = f"no H1 bars for {row['symbol']} under data/universe"
        return row
    for pol, params in GRID.items():
        if pol == "regime_exit" and not regime:
            row["policies"][pol] = {"status": UNMEASURED,
                                    "why": "no point-in-time leg-factor state for this symbol"}
            continue
        costs.basis = set()
        lifts: dict[float, list[float]] = {}
        cells: dict[str, Any] = {}
        for p in params:
            fired = 0
            ls: list[float] = []
            for t in trades:
                ex = POLICIES[pol](bars, t, p, regime)
                fired += ex is not None
                ls.append(overlay_r(t, ex, bars, costs) - t.r)
            lifts[p] = ls
            cells[str(p)] = {"cell_id": cell_id(sleeve, pol, p), "fired": fired,
                             "lift_r_per_trade_in_sample": round(float(np.mean(ls)), 4)
                             if ls else None}
        d, chosen, fwd = walk_forward(trades, lifts)
        verdict = _dsr(d, n_cells)
        fwd_d = [x for x, f in zip(d, fwd, strict=True) if f]
        row["policies"][pol] = {
            "cells": cells, "cost_basis": sorted(costs.basis) or ["no exit changed"],
            "oos_lift_r_per_trade": round(float(np.mean(d)), 4) if d else UNMEASURED,
            "oos_forward_lift_r_per_trade": round(float(np.mean(fwd_d)), 4) if fwd_d
            else UNMEASURED,
            "n_oos_forward": len(fwd_d),
            "params_chosen": {str(p): chosen.count(p) for p in params},
            "verdict": verdict,
            "survivor": bool(verdict.get("passed")) and bool(d) and float(np.mean(d)) > 0,
        }
    return row


# ---------------------------------------------------------------- trials, run

def charge(ids: Sequence[str], *, charged: Path = CHARGED,
           trials: Path = TRIALS) -> tuple[int, int]:
    """(newly charged, lifetime union). Each cell id is charged exactly once, ever."""
    try:
        union = json.loads(charged.read_text("utf-8"))
        union = union if isinstance(union, dict) else {}
    except (OSError, ValueError):
        union = {}
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    new = sorted({i for i in ids if i not in union})
    for tid in new:
        union[tid] = now
    if new:
        charged.parent.mkdir(parents=True, exist_ok=True)
        tmp = charged.with_suffix(".tmp")
        tmp.write_text(json.dumps(union, sort_keys=True), "utf-8")
        tmp.replace(charged)
        with trials.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": now, "source": FAMILY, "tests_run": len(new),
                                 "by_family": {FAMILY: len(new)}, "trial_ids": new,
                                 "rule": "each (sleeve x policy x param) exit-overlay cell "
                                         "charged once over its lifetime; nothing donated"})
                     + "\n")
    return len(new), len(union)


def _factor_frame() -> Any:
    try:
        from libs.portfolio.leg_factors import daily_factor_returns
        return daily_factor_returns()
    except Exception:
        return None


def _surface() -> dict[str, Any] | None:
    try:
        from research.cost_surfaces import load
        s = load()
        return s if s else None
    except Exception:
        return None


def run(shadow_dir: Path = SHADOW_DIR, out: Path | None = OUT, *,
        universe_dir: Path = UNIVERSE_DIR, sleeves: Path = SLEEVES, frame: Any = None,
        surface: dict[str, Any] | None = None, charged: Path = CHARGED,
        trials: Path = TRIALS, load_frame: bool = True) -> dict[str, Any]:
    registry = certified_sleeves(sleeves)
    by_sleeve = load_trades(shadow_dir, registry)
    if frame is None and load_frame and by_sleeve:
        frame = _factor_frame()
    costs = CostModel(surface if surface is not None else _surface())
    bars_cache: dict[str, Bars | None] = {}
    rows: dict[str, Any] = {}
    ids: list[str] = []
    for sleeve, trades in sorted(by_sleeve.items()):
        sym = trades[0].symbol
        if sym not in bars_cache:
            bars_cache[sym] = load_bars(sym, universe_dir)
        rows[sleeve] = judge_sleeve(sleeve, trades, bars_cache[sym], costs,
                                    regime_z(frame, sym))
        ids += [cell_id(sleeve, p, v) for p, vs in GRID.items() for v in vs]
    new, union = charge(ids, charged=charged, trials=trials)
    survivors = [{"sleeve": s, "policy": p, "oos_lift_r_per_trade": v["oos_lift_r_per_trade"],
                  "dsr": v["verdict"].get("dsr"), "n": v["verdict"].get("n"),
                  "params_chosen": v["params_chosen"]}
                 for s, r in rows.items() for p, v in (r.get("policies") or {}).items()
                 if v.get("survivor")]
    doc: dict[str, Any] = {
        "schema": SCHEMA, "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "status": "MEASURED" if rows else UNMEASURED,
        "why": None if rows else "no certified sleeve ledger (reports/shadow/**/ledger_*.json) "
                                 "is present on this checkout",
        "n_trades": sum(len(t) for t in by_sleeve.values()),
        "registry": "data/sleeves.json (non-RETIRED rows)" if registry is not None
        else "UNREADABLE: every ledger read",
        "grid": {k: list(v) for k, v in GRID.items()},
        "bar": {"N": f"max({TIER_S_MIN_N}, cells charged per sleeve)", "var_sr": "1/(T-1)",
                "dsr": DSR_THRESHOLD, "embargo_h": EMBARGO_H, "min_train": MIN_TRAIN,
                "min_oos": MIN_OOS},
        "trials": {"newly_charged": new, "lifetime_cells": union,
                   "ledger": "desks/mt5/data/null_pass_trials.jsonl (family position_overlay)"},
        "survivors": survivors, "sleeves": rows,
        "money_path": "none -- report only; live wiring is principal-gated "
                      "(patches/active_position_manager/README.md)",
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(out)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true")
    ap.parse_args(argv)
    doc = run()
    print(json.dumps({"status": doc["status"], "sleeves": len(doc["sleeves"]),
                      "survivors": len(doc["survivors"]), "trials": doc["trials"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
