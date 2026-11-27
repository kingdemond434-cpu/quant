#!/usr/bin/env python3
"""ASIA BRACKET REFILL: the gold Asia stop-pair clocks re-filled under the old and fixed engine.

READ-ONLY and CACHE-ONLY. It writes exactly one file, `desks/mt5/reports/ASIA_BRACKET_REFILL.json`,
and touches no certificate, clock, ledger, registry or terminal.

WHAT IT MEASURES. The XAUUSD.asia forward clocks (`session_range_breakout`, window `asia`) rest a
BUY STOP at the Asia range high and a SELL STOP at its low. Until `engine.FILL_RULES`
fill-2026-11-25-a the engine told a stop from a limit by comparing the trigger with the NEXT
bar's open, so a stop the market gapped over read as a "limit" and filled at the trigger -- a
price that was never offered -- and a short's stop and target triggered on the bid. Each clock's
exact spec is rebuilt the way `shadow_forward.main` rebuilds it (certified params, certified side,
frozen and fill-hour costs, the clock's own chart) and replayed twice on the same bars and the same
signals: once through the engine as it stood at `PRE_FIX_REV` (read from git, so nothing is
vendored) and once through the engine in this tree. Per clock, over the forward window
(`forward_start` + `broker_offset_h`, as the clock counts it): n, exp_r, t, cum_r under each
engine, the difference, and the GAP DAYS -- days on which the market opened through a resting
bracket trigger, the days the old rule over-paid.

THE BARS COME FROM THE CACHE AND NOWHERE ELSE (Autonomy 2026-11-25). `h1_source.fetch_h1` tries
the MT5 terminal first, and `from_mt5` calls `mt5.shutdown()` and attach/initialize on the live
FTMO / E8 / Fusion terminals, which a box measurement must never do. Before any desk module is
imported, `MetaTrader5` is replaced by a module that refuses every attribute; the script exits if
the real one is already loaded; `from_mt5` is replaced by a refusal on BOTH `research.h1_source`
and `h1_source`; the extra free-data sources are emptied; and `from_cache` is wrapped to count the
bars it served. The `bar_source` block reports all of it.

Run on the trading box from the repository root (it also runs once a day as the
`asia_bracket_refill` step of `desks/mt5/research/daily_cycle.py`):

    python scripts/asia_bracket_refill.py
    python scripts/asia_bracket_refill.py --budget-s 900
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import math
import os
import subprocess
import sys
import time
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "ASIA_BRACKET_REFILL.json"
SHADOW_STATE = DESK / "reports" / "shadow" / "shadow_state.json"
ENGINE_REL = "desks/mt5/mt5desk/engine.py"
#: The last commit whose engine carries the pre-fill-2026-11-25-a rules.
PRE_FIX_REV = "d7fce4adce"
CLOCK_PREFIX = "XAUUSD.asia"
REFILL_VERSION = "asia-bracket-refill-1"


def _paths() -> None:
    for p in (ROOT, DESK, DESK / "research", DESK / "scripts"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


# ------------------------------------------------------------------ cache-only, fail closed
class _NoTerminal(Exception):
    pass


class _MT5Forbidden(types.ModuleType):
    """Importable (so `import MetaTrader5` in a desk module still loads), but every real
    attribute -- initialize, shutdown, copy_rates_*, symbol_info ... -- raises."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        _TERMINAL_TOUCHES.append(f"MetaTrader5.{name}")
        raise _NoTerminal(f"asia_bracket_refill is cache-only: MetaTrader5.{name} refused")


_TERMINAL_TOUCHES: list[str] = []
CACHE_SOURCES: dict[str, int] = {}


def _install_cache_only() -> None:
    real = sys.modules.get("MetaTrader5")
    if real is not None and type(real).__name__ != "_MT5Forbidden":
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
        real_cache = getattr(mod, "from_cache", None)
        if getattr(real_cache, "_cache_only_counted", False):
            continue                                   # already wrapped in this process

        def _counted_cache(sym: str, start: Any, timeframe: str = "H1",
                           _real: Any = real_cache) -> Any:
            b = _real(sym, start, timeframe)
            CACHE_SOURCES[f"{sym}:{timeframe}"] = 0 if b is None else int(getattr(b, "n", 0) or 0)
            return b

        _counted_cache._cache_only_counted = True      # type: ignore[attr-defined]
        mod.from_mt5 = _refuse_mt5
        mod.from_cache = _counted_cache
        if isinstance(getattr(mod, "EXTRA_SOURCES", None), list):
            mod.EXTRA_SOURCES[:] = []                  # no network source either: cache only


# ------------------------------------------------------------------ the two engines
def load_engine_at(rev: str = PRE_FIX_REV) -> tuple[Any | None, str]:
    """The engine module as it stood at `rev`, read from git and loaded under its own name.

    (module, "") or (None, why). The module's `__file__` is the real engine's, so its data paths
    (`carry_state.json`) resolve exactly as the live engine's do.
    """
    try:
        proc = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{ENGINE_REL}"],
                              capture_output=True, text=True, timeout=60, check=False,
                              encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"git show {rev}:{ENGINE_REL} failed: {type(exc).__name__}: {exc}"
    if proc.returncode != 0 or not proc.stdout.strip():
        return None, f"git show {rev}:{ENGINE_REL} exited {proc.returncode}: {proc.stderr[:200]}"
    name = f"_engine_at_{rev}"
    mod = types.ModuleType(name)
    mod.__file__ = str(ROOT / ENGINE_REL)
    sys.modules[name] = mod                            # dataclasses resolve through sys.modules
    try:
        exec(compile(proc.stdout, f"<{ENGINE_REL}@{rev}>", "exec"), mod.__dict__)
    except Exception as exc:
        sys.modules.pop(name, None)
        return None, f"engine at {rev} did not load: {type(exc).__name__}: {exc}"
    if "FILL_RULES" in mod.__dict__:
        return None, f"engine at {rev} already carries FILL_RULES; it is not the pre-fix engine"
    return mod, ""


# ------------------------------------------------------------------ measurement
def boundary_of(st: dict) -> datetime | None:
    """The clock's forward boundary on the bars' clock: forward_start + broker_offset_h."""
    import pandas as pd
    fs = st.get("forward_start")
    if not fs:
        return None
    try:
        ts = pd.Timestamp(fs)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        return (ts + timedelta(hours=float(st.get("broker_offset_h") or 0.0))).to_pydatetime()
    except (TypeError, ValueError):
        return None


def summarise(rs: list[float]) -> dict[str, Any]:
    if not rs:
        return {"n": 0, "exp_r": None, "t": None, "cum_r": 0.0}
    n = len(rs)
    mean = sum(rs) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in rs) / (n - 1)) if n > 1 else 0.0
    t = mean / (sd / math.sqrt(n)) if sd > 0 else None
    return {"n": n, "exp_r": round(mean, 4), "t": None if t is None else round(t, 3),
            "cum_r": round(sum(rs), 4)}


def gap_days(df: Any, sigs: list, boundary: datetime | None) -> list[str]:
    """Dates (of the fill bar) on which a resting STOP trigger was gapped through by the open.

    The same classification the fixed engine applies: a trigger at or beyond the signal bar's
    close in the trade's direction is a stop; the first bar of its wait window that reaches it
    is the fill bar; a gap day is one where that bar OPENED through the trigger.
    """
    import numpy as np
    import pandas as pd
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float) if "close" in df.columns else o
    idx = df.index
    idx_ns = np.asarray(pd.DatetimeIndex(idx).as_unit("ns").asi8, dtype="int64")
    n = len(df)
    days: set[str] = set()
    for s in sigs:
        trig = getattr(s, "trigger", None)
        if trig is None or s.side not in (-1, 1):
            continue
        t_ns = pd.Timestamp(s.time).value
        i0 = int(np.searchsorted(idx_ns, t_ns))
        i = i0 + 1
        if i <= 0 or i >= n - 1:
            continue
        ref_bar = i0 if idx_ns[i0] == t_ns else max(i0 - 1, 0)
        ref = float(c[ref_bar])
        trig = float(trig)
        stop_order = trig >= ref if s.side > 0 else trig <= ref
        if not stop_order:
            continue
        for j in range(i, min(i + int(getattr(s, "wait_bars", 1) or 1), n)):
            touched = h[j] >= trig if s.side > 0 else lo[j] <= trig
            if not touched:
                continue
            gapped = o[j] > trig if s.side > 0 else o[j] < trig
            if gapped and (boundary is None or idx[j] >= boundary):
                days.add(str(pd.Timestamp(idx[j]).date()))
            break
    return sorted(days)


def rebuild(key: str, row: tuple, meta: dict) -> tuple[Any, list, Any, str]:
    """(bars, signals, costs, why) in `shadow_forward.main`'s own call shape for this clock."""
    import shadow_forward as sf
    from mt5desk.family_inputs import resolve, runtime_call_params
    sym, _win, params, fam, side = row[0], row[1], dict(row[2] or {}), row[3], row[4]
    tf = sf.timeframe_of(params)
    bars = sf.fetch_h1(sym, tf)
    if bars is None:
        return None, [], None, f"no {tf} bars for {sym} in the cache covering the window"
    h1 = bars.df
    fn = sf._family_fn(fam)
    if fn is None:
        return None, [], None, f"family {fam} has no constructor on this tree"
    call = runtime_call_params(fam, params)
    extra, why = resolve(sym, fam, params, h1)
    if extra is None:
        return None, [], None, f"runtime inputs unavailable: {why}"
    call.update(extra)
    sigs = sf.family_signals(fn, h1, side=-1 if str(side).upper() == "SHORT" else 1, params=call)
    costs = sf.per_symbol_costs(meta, sym)
    with contextlib.suppress(Exception):
        import sleeve_registry as reg
        ff = reg.frozen_cost_fields(key)
        if ff:
            known = {f.name for f in dataclasses.fields(costs)}
            costs = dataclasses.replace(costs, **{k: float(v) for k, v in ff.items()
                                                  if k in known})
        costs, _basis, _pts = sf.fill_hour_costs(costs, meta, sym, sigs, tf,
                                                 reg.frozen_cost_fields(key))
    return h1, list(sigs), costs, ""


def refill_clock(key: str, st: dict, row: tuple | None, meta: dict, old_engine: Any,
                 new_run: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"key": key,
                           "recorded": {"n": st.get("n"), "exp_r": st.get("exp_r"),
                                        "forward_t": st.get("forward_t"),
                                        "status": st.get("status"),
                                        "forward_start": st.get("forward_start")}}
    if row is None:
        out.update(status="UNMEASURED",
                   why="no certified row in shadow_forward.certified_sleeves() maps to this key")
        return out
    boundary = boundary_of(st)
    out["forward_boundary"] = None if boundary is None else boundary.isoformat()
    if boundary is None:
        out.update(status="UNMEASURED", why="the clock has no readable forward_start")
        return out
    h1, sigs, costs, why = rebuild(key, row, meta)
    if h1 is None:
        out.update(status="UNMEASURED", why=why)
        return out
    import pandas as pd
    b = pd.Timestamp(boundary)

    def fwd(res: Any) -> list[float]:
        return [float(t.r_multiple) for t in res.trades if pd.Timestamp(t.entry_time) >= b]

    new = summarise(fwd(new_run(h1, sigs, costs)))
    out["fixed"] = new
    if old_engine is None:
        out["old"] = {"status": "UNMEASURED", "why": "pre-fix engine unavailable (see engines)"}
    else:
        old = summarise(fwd(old_engine.run_backtest(h1, sigs, costs)))
        out["old"] = old
        if old["exp_r"] is not None and new["exp_r"] is not None:
            out["delta_exp_r"] = round(new["exp_r"] - old["exp_r"], 4)
        out["delta_cum_r"] = round(new["cum_r"] - old["cum_r"], 4)
    days = gap_days(h1, sigs, boundary)
    out["gap_days"] = len(days)
    out["gap_dates"] = days
    out["status"] = "MEASURED"
    return out


def _certified_rows() -> tuple[dict[str, tuple], str]:
    rows: dict[str, tuple] = {}
    try:
        import shadow_forward as sf
        for row in sf.certified_sleeves():
            k = sf.sleeve_key(row[0], row[1], dict(row[2] or {}), row[3], row[4])
            rows[k] = row
            rows.setdefault(getattr(sf, "ALIAS_MERGED", {}).get(k, k), row)
    except Exception as exc:
        return rows, f"certified_sleeves failed: {type(exc).__name__}: {exc}"
    return rows, ""


def _frozen_rows() -> dict[str, tuple]:
    """The registry's FROZEN identity for each clock, the spec the clock was frozen on.

    The fallback when the canon on this tree attests no certificate (certified_sleeves() then
    returns nothing): the forward clock's own frozen params, family and side are still its spec.
    """
    try:
        doc = json.loads((DESK / "data" / "sleeve_registry.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, tuple] = {}
    for key, row in (doc.get("sleeves") or {}).items():
        ident = row.get("identity") if isinstance(row, dict) else None
        if not (isinstance(ident, dict) and isinstance(ident.get("params"), dict)):
            continue
        key = str(key)
        win = key.split("#", 1)[0].split("@", 1)[0].rsplit(".", 1)[-1]
        out[key] = (str(ident.get("symbol") or key.split(".", 1)[0]), win,
                    dict(ident["params"]), str(ident.get("family") or "session_range_breakout"),
                    str(ident.get("direction") or "LONG"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--rev", default=PRE_FIX_REV)
    args = ap.parse_args(argv)
    _paths()
    _install_cache_only()
    t0 = time.monotonic()
    try:
        state = json.loads(SHADOW_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        state, state_why = {}, f"UNMEASURED: shadow state unreadable ({type(exc).__name__})"
    else:
        state_why = ""
    keys = sorted(k for k, v in state.items()
                  if isinstance(v, dict) and str(k).startswith(CLOCK_PREFIX))
    clocks: list[dict] = []
    engines: dict[str, Any] = {"pre_fix_rev": args.rev}
    if keys:
        meta = json.loads((DESK / "data" / "universe" / "universe.json")
                          .read_text(encoding="utf-8"))
        from mt5desk import engine as live_engine
        engines["fixed"] = getattr(live_engine, "FILL_RULES", None)
        old_engine, why_old = load_engine_at(args.rev)
        engines["old"] = None if old_engine is None else f"engine@{args.rev}"
        engines["old_why"] = why_old or None
        rows, why_rows = _certified_rows()
        frozen = _frozen_rows()
        engines["rows_note"] = why_rows or None
        for key in keys:
            if time.monotonic() - t0 > args.budget_s:
                clocks.append({"key": key, "status": "UNMEASURED",
                               "why": "refill budget exhausted before this clock"})
                continue
            row, row_src = rows.get(key), "certified_sleeves"
            if row is None and key in frozen:
                row, row_src = frozen[key], "sleeve_registry frozen identity"
            try:
                rec = refill_clock(key, state[key], row, meta, old_engine,
                                   live_engine.run_backtest)
                rec["spec_source"] = row_src if row is not None else None
                clocks.append(rec)
            except Exception as exc:
                clocks.append({"key": key, "status": "UNMEASURED",
                               "why": f"{type(exc).__name__}: {exc}"[:300]})
    measured = [c for c in clocks if c.get("status") == "MEASURED"]
    doc = {
        "refill": REFILL_VERSION,
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "elapsed_s": round(time.monotonic() - t0, 1),
        "status": ("UNMEASURED" if not measured else "MEASURED"),
        "why": (state_why or (None if keys else f"no {CLOCK_PREFIX}* clock in shadow_state")
                if not measured else None),
        "engines": engines,
        "summary": {"clocks": len(clocks), "measured": len(measured),
                    "mean_delta_exp_r": (round(sum(c["delta_exp_r"] for c in measured
                                                   if "delta_exp_r" in c)
                                               / max(1, sum(1 for c in measured
                                                            if "delta_exp_r" in c)), 4)
                                         if any("delta_exp_r" in c for c in measured)
                                         else None),
                    "gap_days_max": max((c.get("gap_days", 0) for c in measured), default=0)},
        "bar_source": {
            "mode": "CACHE_ONLY (MetaTrader5 refused; h1_source.from_mt5 refused; "
                    "EXTRA_SOURCES emptied)",
            "mt5_attempts_refused": len(_TERMINAL_TOUCHES),
            "cache_series": dict(CACHE_SOURCES),
            "cache_series_empty": sorted(k for k, v in CACHE_SOURCES.items() if not v),
            "note": ("bars come from the box's parquet cache only; a clock whose cache is "
                     "missing or does not cover the window reads UNMEASURED"),
        },
        "clocks": clocks,
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
