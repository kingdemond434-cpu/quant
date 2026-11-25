#!/usr/bin/env python3
"""ENTRY TIMING PROBE: does the judge fill where the forward clock and the live book can?

READ-ONLY. It writes exactly one file, `desks/mt5/reports/ENTRY_TIMING_PROBE.json`, and touches
no certificate, clock, ledger or registry.

THE CLAIM IT TESTS (INTRADAY_GAP_1125, DSR_CHARGE_PROBE 2026-11-25): the judge fills an entry at
the signal bar's own close while the forward clock fills on the next tick, so the backtest keeps
moves the live system cannot. The code trace in this probe's commit refutes that. The judge
(`external_gauntlet.daily_series`) and the forward clock (`shadow_forward.main`) both call
`mt5desk.engine.run_backtest`, and that function fills at the open of the bar after the signal's
stamp (`i = i0 + 1`, `entry = o[i]`). This probe measures what the trace says, cell by cell.

ARMS, per sampled certificate (20 M5 and 20 H1 forward clocks, n >= 10, deduplicated on
(symbol, n, cum_r) the way DSR_CHARGE_PROBE counted them):

  a        the judge's own path: `external_gauntlet.build_cell` -> `run_backtest`, swap off so it
           compares like for like with b
  a_full   the same with the judge's full cost model (swap included)
  gross    the same signals with zero cost: what the cost model takes per trade, in R
  b        an INDEPENDENT reference fill: next bar's open at the ASK for buys and the BID for
           sells, long exits on the bid and short exits on the ask, a gapped stop or trigger
           filled at the open, stop before target on every bar, and no target on a trigger's
           own fill bar. The spread is the judge's charged one, so b - a isolates fill mechanics
  b_bar    b, with each bar's own recorded spread in place of the charged constant
  c        the claimed look-ahead, as a counterfactual: entry at the signal bar's own CLOSE. If a
           were secretly c, then a would equal c. They differ, and the size of c - a is what the
           look-ahead would be worth if it existed
  shadow   the forward clock's own rebuild (`shadow_forward` call shape, certified side, frozen
           and fill-hour costs) on the forward window, beside the recorded shadow_state figure

Every arm is split at the clock's forward boundary into `backtest` (entries before it) and
`forward` (entries at or after it). Expectancy is mean R per trade. `t` is the per-trade t, and
`sharpe` is the daily-summed R, annualised over trade days at sqrt(252), as `daily_series` builds
it.

NO REALISED COST TABLE EXISTS YET. One pipe's L11 table (judge, shadow and allocator on one
realised per-symbol-per-hour cost) is planned after its step 1b. Until it lands, b_bar, which
prices on the bar's own spread, is the closest measured basis. The basis is named in the output.

Run it on the trading box from the repository root:

    python scripts/entry_timing_probe.py
    python scripts/entry_timing_probe.py --per-tf 20 --budget-s 3000
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import math
import os
import re
import sys
import time
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "ENTRY_TIMING_PROBE.json"
SHADOW_STATE = DESK / "reports" / "shadow" / "shadow_state.json"
PROBE_VERSION = "r2-cache-only/entry-timing-probe-1"
_TF = re.compile(r"@(M1|M5|M15|M30|H1|H4|D1)\b")

#: Signal features the reference fill does not model. A cell whose signals carry any of them
#: gets b/b_bar/c reported as UNMEASURED with the reason, never a number from a partial walk.
UNSUPPORTED = ("bank_frac", "runner_trail_k", "trail_tighten_k", "add_every_r")


def _paths() -> None:
    for p in (ROOT, DESK, DESK / "research", DESK / "scripts"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


# ------------------------------------------------------------------------------------------------
# The reference fill. Pure: bars, signals, costs in, (entry_time, R) out.
# ------------------------------------------------------------------------------------------------

def _unsupported(sig: Any) -> str | None:
    for f in UNSUPPORTED:
        if float(getattr(sig, f, 0.0) or 0.0) > 0:
            return f
    if getattr(sig, "reversal_level", None) is not None:
        return "reversal_level"
    if (getattr(sig, "liquidity_spread_max", None) is not None
            or getattr(sig, "liquidity_ticks_min", None) is not None):
        return "liquidity_exit"
    return None


def reference_fills(df: pd.DataFrame, sigs: list, costs: Any, *, entry: str = "next_open",
                    bar_spread_px: np.ndarray | None = None) -> dict[str, Any]:
    """Walk `sigs` over `df` with explicit bid/ask by side and conservative intrabar order.

    Bars are BID OHLC (MetaTrader's rates). The ask is bid + spread. `entry` is "next_open" (the
    bar after the signal stamp, as the gateway fills while that bar forms) or "signal_close" (the
    claimed look-ahead, as a counterfactual only). R is measured in the same unit the engine uses,
    |reference entry - stop|, where the reference entry is the bid price the engine would record,
    so an R here and an R from `run_backtest` are the same ruler.
    """
    if entry not in ("next_open", "signal_close"):
        raise ValueError(entry)
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    lo = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float) if "close" in df.columns else o
    n = len(df)
    idx = df.index
    idx_ns = np.asarray(pd.DatetimeIndex(idx).as_unit("ns").asi8, dtype="int64")
    sp_const = float(costs.spread_per_lot) / float(costs.contract_oz)
    comm = (float(costs.commission_per_lot) * 2.0 * float(costs.quote_per_account)
            / float(costs.contract_oz))

    def spread(j: int) -> float:
        if bar_spread_px is not None:
            v = float(bar_spread_px[j])
            if math.isfinite(v) and v > 0:
                return v
        return sp_const

    for s in sigs:
        why = _unsupported(s)
        if why:
            return {"status": "UNMEASURED", "why": f"signal feature {why} is not modelled", "trades": []}
    sig_ns = np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64")
    locs = np.searchsorted(idx_ns, sig_ns)
    trades: list[tuple[pd.Timestamp, float, str]] = []
    rejected = 0
    last_exit = -1
    for sig, i0 in zip(sigs, locs, strict=True):
        side = int(sig.side)
        if side not in (-1, 1):
            continue
        i = int(i0) + 1                       # the engine's fill bar, kept identical
        if i <= 0 or i >= n - 1 or i <= last_exit:
            continue
        trig = getattr(sig, "trigger", None)
        is_trigger = trig is not None
        if entry == "signal_close":
            if is_trigger or i0 >= n:
                continue                      # a close fill of a resting order is not defined
            fill_bar = int(i0)
            neutral = float(c[fill_bar])
            px = neutral + (spread(fill_bar) if side > 0 else 0.0)
            walk_from = fill_bar + 1
        elif not is_trigger:
            fill_bar = i
            neutral = float(o[i])
            px = neutral + (spread(i) if side > 0 else 0.0)
            walk_from = i
        else:
            tgt = float(trig)
            # Classified against the quote when the order is PLACED, the signal bar's close (ask
            # for a buy, bid for a sell): a buy above it is a buy STOP, below it a buy LIMIT. The
            # engine classifies against the next open instead, so a stop the market gapped over
            # becomes a "limit" filled at the trigger, a price that was never offered.
            pb = int(i0) if int(i0) < n else i - 1
            q0 = float(c[pb]) + (spread(pb) if side > 0 else 0.0)
            stop_order = (tgt >= q0) if side > 0 else (tgt <= q0)
            fill_bar, px = -1, float("nan")
            for j in range(i, min(i + int(getattr(sig, "wait_bars", 1) or 1), n)):
                add = spread(j) if side > 0 else 0.0
                qo, qh, ql = float(o[j]) + add, float(h[j]) + add, float(lo[j]) + add
                if stop_order:
                    if (side > 0 and qo >= tgt) or (side < 0 and qo <= tgt):
                        fill_bar, px = j, qo          # gapped through the trigger: the open
                    elif (side > 0 and qh >= tgt) or (side < 0 and ql <= tgt):
                        fill_bar, px = j, tgt
                else:
                    if (side > 0 and qo <= tgt) or (side < 0 and qo >= tgt):
                        fill_bar, px = j, qo          # opened through the limit: the open
                    elif (side > 0 and ql <= tgt) or (side < 0 and qh >= tgt):
                        fill_bar, px = j, tgt
                if fill_bar >= 0:
                    break
            if fill_bar < 0:
                continue
            neutral = px - (spread(fill_bar) if side > 0 else 0.0)
            walk_from = fill_bar
        stop, target = float(sig.stop), float(sig.target)
        if not (side * (neutral - stop) > 0 and side * (target - neutral) > 0):
            rejected += 1
            continue
        risk = abs(neutral - stop)
        ttl = int(sig.ttl_bars)
        # The engine walks `ttl` bars from its fill bar and closes at the next open; a close fill
        # walks the same `ttl` bars after the bar it filled on.
        first = walk_from
        last = min(n, first + ttl)
        exit_px: float | None = None
        exit_bar = -1
        reason = "ttl"
        for j in range(walk_from, last):
            # Long exits trade at the bid; short exits at the ask (bid + spread).
            add = spread(j) if side < 0 else 0.0
            qo, qh, ql = float(o[j]) + add, float(h[j]) + add, float(lo[j]) + add
            entry_bar = (j == fill_bar)
            if not entry_bar and ((side > 0 and qo <= stop) or (side < 0 and qo >= stop)):
                exit_px, exit_bar, reason = qo, j, "stop_gap"
                break
            if (side > 0 and ql <= stop) or (side < 0 and qh >= stop):
                exit_px, exit_bar, reason = stop, j, "stop"
                break
            # Conservative: a trigger's own fill bar never pays the target (path unknown).
            if entry_bar and is_trigger:
                continue
            if (side > 0 and qh >= target) or (side < 0 and ql <= target):
                exit_px, exit_bar, reason = target, j, "target"
                break
        if exit_px is None:
            exit_bar = min(first + ttl, n - 1)
            exit_px = float(o[exit_bar]) + (spread(exit_bar) if side < 0 else 0.0)
        last_exit = exit_bar
        r = side * (exit_px - px) / risk - comm / risk
        trades.append((pd.Timestamp(idx[fill_bar]), float(r), reason))
    return {"status": "MEASURED", "trades": trades, "geometry_rejections": rejected}


# ------------------------------------------------------------------------------------------------
# Summaries.
# ------------------------------------------------------------------------------------------------

def summarise(rows: list[tuple[pd.Timestamp, float]]) -> dict[str, Any]:
    """n, mean R per trade, per-trade t, and the daily-summed Sharpe the judge's series uses."""
    if not rows:
        return {"n": 0, "exp_r": None, "t": None, "sharpe": None}
    r = np.array([x[1] for x in rows], dtype=float)
    n = len(r)
    sd = float(r.std(ddof=1)) if n > 1 else 0.0
    t = float(r.mean() / (sd / math.sqrt(n))) if sd > 0 else None
    daily = pd.Series(r, index=[pd.Timestamp(x[0]).date() for x in rows]).groupby(level=0).sum()
    dsd = float(daily.std(ddof=1)) if len(daily) > 1 else 0.0
    sharpe = float(daily.mean() / dsd * math.sqrt(252)) if dsd > 0 else None
    return {"n": n, "exp_r": round(float(r.mean()), 4), "t": None if t is None else round(t, 2),
            "sharpe": None if sharpe is None else round(sharpe, 2)}


def split(rows: list[tuple[pd.Timestamp, float]], boundary: pd.Timestamp | None) -> dict[str, Any]:
    if boundary is None:
        return {"all": summarise(rows), "backtest": None, "forward": None}
    bt = [x for x in rows if pd.Timestamp(x[0]) < boundary]
    fw = [x for x in rows if pd.Timestamp(x[0]) >= boundary]
    return {"backtest": summarise(bt), "forward": summarise(fw)}


def _engine_rows(df: pd.DataFrame, sigs: list, costs: Any) -> list[tuple[pd.Timestamp, float]]:
    from mt5desk.engine import run_backtest
    return [(pd.Timestamp(t.entry_time), float(t.r_multiple))
            for t in run_backtest(df, sigs, costs).trades]


# ------------------------------------------------------------------------------------------------
# Sampling and rebuild (box only: these read the parquet bars and the canon).
# ------------------------------------------------------------------------------------------------

def timeframe_of_key(key: str) -> str:
    m = _TF.search(key)
    return m.group(1) if m else "H1"


def sample_clocks(state: dict, per_tf: int, tfs: tuple[str, ...] = ("M5", "H1"),
                  min_n: int = 10) -> dict[str, list[tuple[str, dict]]]:
    """The largest-n distinct forward clocks per chart, deduplicated on (symbol, n, cum_r)."""
    picked: dict[str, list[tuple[str, dict]]] = {tf: [] for tf in tfs}
    seen: set[tuple] = set()
    rows = sorted(((k, v) for k, v in state.items() if isinstance(v, dict)),
                  key=lambda kv: (-(int(kv[1].get("n") or 0)), kv[0]))
    for k, v in rows:
        tf = timeframe_of_key(k)
        if tf not in picked or int(v.get("n") or 0) < min_n or v.get("exp_r") is None:
            continue
        dk = (k.split(".")[0], int(v.get("n") or 0), round(float(v.get("cum_r") or 0.0), 6))
        if dk in seen:
            continue
        seen.add(dk)
        if len(picked[tf]) < per_tf:
            picked[tf].append((k, v))
    return picked


def _boundary(st: dict) -> pd.Timestamp | None:
    fs = st.get("forward_start")
    if not fs:
        return None
    try:
        ts = pd.Timestamp(fs)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        return ts + timedelta(hours=float(st.get("broker_offset_h") or 0.0))
    except (TypeError, ValueError):
        return None


def _bar_spread_px(df: pd.DataFrame, meta: dict) -> np.ndarray | None:
    ts = float(meta.get("tick_size") or meta.get("point") or 0.0)
    if "spread" not in df.columns or ts <= 0:
        return None
    return df["spread"].to_numpy(dtype=float) * ts


def _no_swap(costs: Any) -> Any:
    return dataclasses.replace(costs, swap_per_lot_per_night=0.0, swap_per_lot_per_price=None)


def _zero(costs: Any) -> Any:
    return dataclasses.replace(_no_swap(costs), spread_per_lot=0.0, commission_per_lot=0.0)


def probe_cell(key: str, st: dict, row: tuple | None, meta: dict) -> dict[str, Any]:
    _paths()
    import external_gauntlet as eg
    out: dict[str, Any] = {"key": key, "timeframe": timeframe_of_key(key),
                           "recorded_forward": {"n": st.get("n"), "exp_r": st.get("exp_r"),
                                                "forward_t": st.get("forward_t"),
                                                "status": st.get("status")}}
    if row is None:
        out["status"] = "UNMEASURED"
        out["why"] = "no certified row in shadow_forward.certified_sleeves() maps to this key"
        return out
    sym, _win, params, fam, side = row[0], row[1], dict(row[2] or {}), row[3], row[4]
    out.update({"symbol": sym, "family": fam, "side": side})
    boundary = _boundary(st)
    out["forward_boundary"] = None if boundary is None else str(boundary)
    cell = eg.build_cell(sym, fam, params, meta)
    if not cell:
        out["status"] = "UNMEASURED"
        out["why"] = f"judge rebuild failed: {eg.LAST_BUILD_FAILURE}"
        return out
    df, sigs, costs = cell["df"], list(cell["sigs"]), cell["costs"]
    if str(side).upper() == "SHORT":
        out["judge_side_note"] = ("build_cell calls the family with side=1; the clock replays "
                                  "SHORT. Compare `shadow` for the certified direction.")
    arms: dict[str, Any] = {"cost_basis": cell.get("_cost_basis")}
    arms["a"] = split(_engine_rows(df, sigs, _no_swap(costs)), boundary)
    arms["a_full"] = split(_engine_rows(df, sigs, costs), boundary)
    arms["gross"] = split(_engine_rows(df, sigs, _zero(costs)), boundary)
    for name, kw in (("b", {}), ("b_bar", {"bar_spread_px": _bar_spread_px(df, meta.get(sym, {}))}),
                     ("c", {"entry": "signal_close"})):
        if name == "b_bar" and kw["bar_spread_px"] is None:
            arms[name] = {"status": "UNMEASURED", "why": "no per-bar spread column or tick size"}
            continue
        ref = reference_fills(df, sigs, _no_swap(costs), **kw)
        arms[name] = (split([(t, r) for t, r, _ in ref["trades"]], boundary)
                      if ref["status"] == "MEASURED" else ref)
    # The forward clock's own call shape and costs, on its own fetched bars.
    try:
        import shadow_forward as sf
        from mt5desk.family_inputs import resolve, runtime_call_params
        bars = sf.fetch_h1(sym, sf.timeframe_of(params))
        if bars is None:
            arms["shadow"] = {"status": "UNMEASURED", "why": "no bars from the forward source"}
        else:
            h1 = bars.df
            fn = sf._family_fn(fam)
            call = runtime_call_params(fam, params)
            extra, why = resolve(sym, fam, params, h1)
            if fn is None or extra is None:
                arms["shadow"] = {"status": "UNMEASURED", "why": why or "no constructor"}
            else:
                call.update(extra)
                ssigs = sf.family_signals(fn, h1, side=-1 if str(side).upper() == "SHORT" else 1,
                                          params=call)
                scosts = sf.per_symbol_costs(meta, sym)
                with contextlib.suppress(Exception):
                    import sleeve_registry as reg
                    ff = reg.frozen_cost_fields(key)
                    if ff:
                        known = {f.name for f in dataclasses.fields(scosts)}
                        scosts = dataclasses.replace(scosts, **{k: float(v) for k, v in ff.items()
                                                                if k in known})
                    scosts, _b, _p = sf.fill_hour_costs(scosts, meta, sym, ssigs,
                                                        sf.timeframe_of(params),
                                                        reg.frozen_cost_fields(key))
                rows_s = [x for x in _engine_rows(h1, ssigs, scosts)
                          if x[0] >= pd.Timestamp(sf.SHADOW_START)]
                arms["shadow"] = split(rows_s, boundary)
    except Exception as exc:                                  # a probe never crashes the pass
        arms["shadow"] = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:300]}
    out["arms"] = arms
    out["status"] = "MEASURED"
    return out


def _delta(cell: dict, x: str, y: str, window: str) -> float | None:
    try:
        a = cell["arms"][x][window]["exp_r"]
        b = cell["arms"][y][window]["exp_r"]
    except (KeyError, TypeError):
        return None
    return None if a is None or b is None else float(a) - float(b)


def verdict(cells: list[dict]) -> dict[str, Any]:
    """Per chart: mean b - a (fill mechanics), c - a (what a close fill would add), a - gross
    (cost per trade), and the backtest-to-forward drop under the judge's own engine."""
    res: dict[str, Any] = {}
    for tf in sorted({c.get("timeframe") for c in cells}):
        mine = [c for c in cells if c.get("timeframe") == tf and c.get("status") == "MEASURED"]
        def mean(vals: list) -> float | None:
            v = [x for x in vals if x is not None]
            return round(float(np.mean(v)), 4) if v else None
        res[str(tf)] = {
            "cells_measured": len(mine),
            "b_minus_a_backtest": mean([_delta(c, "b", "a", "backtest") for c in mine]),
            "c_minus_a_backtest": mean([_delta(c, "c", "a", "backtest") for c in mine]),
            "cost_r_backtest": mean([_delta(c, "gross", "a", "backtest") for c in mine]),
            "a_backtest_exp_r": mean([(c["arms"]["a"]["backtest"] or {}).get("exp_r")
                                      for c in mine]),
            "a_forward_exp_r": mean([(c["arms"]["a"]["forward"] or {}).get("exp_r")
                                     for c in mine]),
            "gross_forward_exp_r": mean([(c["arms"]["gross"]["forward"] or {}).get("exp_r")
                                         for c in mine]),
            "recorded_forward_exp_r": mean([c["recorded_forward"].get("exp_r") for c in mine]),
        }
    return res


def _certified_rows() -> tuple[dict[str, tuple], str]:
    """Every certified clock's (symbol, window, params, family, side), keyed as shadow keys it."""
    rows: dict[str, tuple] = {}
    try:
        import shadow_forward as sf
        for row in sf.certified_sleeves():
            k = sf.sleeve_key(row[0], row[1], dict(row[2] or {}), row[3], row[4])
            rows[k] = row
            rows.setdefault(sf.ALIAS_MERGED.get(k, k), row)
    except Exception as exc:
        return rows, f"certified_sleeves failed: {type(exc).__name__}: {exc}"
    return rows, ""



# ------------------------------------------------------------------ cache-only, fail closed
# A bridge session must NEVER touch a live terminal (Autonomy 2026-11-25: from_mt5 calls
# mt5.shutdown() then attach/initialize on the FTMO / E8 / Fusion terminals). Before anything
# imports the desk, `MetaTrader5` is replaced by a module that raises on ANY use, and
# h1_source.from_mt5 is replaced by a refusal, so every bar comes from the CACHE source.
class _NoTerminal(Exception):
    pass


class _MT5Forbidden(types.ModuleType):
    """Importable (so `import MetaTrader5` in a desk module still loads), but every real
    attribute -- initialize, shutdown, copy_rates_*, symbol_info ... -- raises."""

    def __getattr__(self, name: str) -> Any:
        _TERMINAL_TOUCHES.append(f"MetaTrader5.{name}")
        raise _NoTerminal(f"entry_timing_probe is cache-only: MetaTrader5.{name} refused")


_TERMINAL_TOUCHES: list[str] = []
CACHE_SOURCES: dict[str, int] = {}


def _install_cache_only() -> None:
    real = sys.modules.get("MetaTrader5")
    if real is not None and not isinstance(real, _MT5Forbidden):
        raise SystemExit("refusing to run: MetaTrader5 already imported in this process")
    sys.modules["MetaTrader5"] = _MT5Forbidden("MetaTrader5")
    import importlib

    # shadow_forward imports `research.h1_source`; other code may import `h1_source` bare. They
    # are two module objects, so BOTH are patched, and at least one must be.
    mods = []
    for name in ("research.h1_source", "h1_source"):
        with contextlib.suppress(ImportError):
            mods.append(importlib.import_module(name))
    if not mods:
        raise SystemExit("refusing to run: h1_source not importable, cannot force CACHE")

    def _refuse_mt5(sym: str, start: Any, timeframe: str = "H1") -> None:
        _TERMINAL_TOUCHES.append(f"{sym}:{timeframe}")
        return None

    for mod in mods:
        real_cache = mod.from_cache

        def _counted_cache(sym: str, start: Any, timeframe: str = "H1",
                           _real: Any = real_cache) -> Any:
            b = _real(sym, start, timeframe)
            CACHE_SOURCES[f"{sym}:{timeframe}"] = 0 if b is None else int(getattr(b, "n", 0) or 0)
            return b

        mod.from_mt5 = _refuse_mt5
        mod.from_cache = _counted_cache

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--per-tf", type=int, default=20)
    ap.add_argument("--budget-s", type=float, default=3000.0)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    _paths()
    _install_cache_only()
    t0 = time.monotonic()
    state = json.loads(SHADOW_STATE.read_text(encoding="utf-8"))
    meta = json.loads((DESK / "data" / "universe" / "universe.json").read_text(encoding="utf-8"))
    picked = sample_clocks(state, args.per_tf)
    rows_by_key: dict[str, tuple] = {}
    why_rows = ""
    if any(picked.values()):
        rows_by_key, why_rows = _certified_rows()
    cells: list[dict] = []
    for tf, rows in picked.items():
        for key, st in rows:
            if time.monotonic() - t0 > args.budget_s:
                cells.append({"key": key, "timeframe": tf, "status": "UNMEASURED",
                              "why": "probe budget exhausted before this cell"})
                continue
            try:
                cells.append(probe_cell(key, st, rows_by_key.get(key), meta))
            except Exception as exc:
                cells.append({"key": key, "timeframe": tf, "status": "UNMEASURED",
                              "why": f"{type(exc).__name__}: {exc}"[:300]})
    doc = {
        "probe": PROBE_VERSION,
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "elapsed_s": round(time.monotonic() - t0, 1),
        "rows_note": why_rows or None,
        "cost_basis_note": ("no realised cost table exists yet (One pipe L11 is planned); arms "
                            "a/b/c price on the judge's charged spread, b_bar on each bar's "
                            "own recorded spread"),
        "summary": verdict(cells),
        "bar_source": {
            "mode": "CACHE_ONLY (MetaTrader5 refused; h1_source.from_mt5 refused)",
            "mt5_attempts_refused": len(_TERMINAL_TOUCHES),
            "cache_series": CACHE_SOURCES,
            "cache_series_empty": sorted(k for k, v in CACHE_SOURCES.items() if not v),
            "note": ("bars come from the box's parquet cache only; a cell whose cache is "
                     "missing or short reads UNMEASURED or covers fewer forward days"),
        },
        "cells": cells,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, args.out)
    print(json.dumps(doc["summary"], indent=1))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
