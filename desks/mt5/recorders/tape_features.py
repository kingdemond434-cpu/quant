"""Make the tape earn: bronze ticks in, the artifacts the desk already reads out.

    py -3 -m recorders.tape_features                  # incremental: only what changed
    py -3 -m recorders.tape_features --symbols XAUUSD --days 5
    py -3 -m recorders.tape_features --rebuild        # ignore the watermark

A TAPE NOBODY READS IS A DISK BILL. `moat/moat_miner.py` states the desk's own law on this in its
first paragraph -- under-exploration of owned data is a BREACH, not a backlog, because unmined
proprietary data is edge already paid for and declined. The recorder is the expensive half and
the irreversible one; this is the half that turns it into something a decision can reach.

FOUR CONSUMERS, ALL OF WHICH ALREADY EXIST. Nothing here builds a parallel feature path:

  1. THE SILVER TAPE -- `data/tape/ticks/<SYM>/<DAY>.parquet` with `ts, bid, ask`. That exact
     path and those exact columns are what `research/orthogonal_sweep._tape_series` reads, which
     is what `mt5desk/family_inputs.resolve` hands to the `liquidity_regime` and
     `orderflow_imbalance` families, in BOTH the gauntlet and the forward engine. Those two
     families have been enrollable and starved: their producer (`moat/moat_silver.py`) converts
     from a bronze store that exists only on the trading box, and its own docstring records the
     day it died silently and left the tape looking dead while the recorder recorded perfectly.
     This is a second, independent producer of the same contract, written from the crash-safe
     store, and it carries the microstructure columns as EXTRAS so the existing two-column
     readers are unaffected.

  2. THE COST SURFACE -- `data/cost_surface_tick.json`, schema `cost-surface-1`, byte-compatible
     with what `research/cost_surface.py` writes, so `cost_surface.spread_pts(surface, sym, hour)`
     reads it VERBATIM with no code change. That module ends with an open question in writing:
     "whether it is EXECUTABLE at hour 01 needs symbol_info_tick from the trading box, which this
     box cannot reach ... a live-tick confirmation is owed and is recorded as such." The bar
     surface measures the broker's stamped spread on an H1 bar. This one measures what a market
     order would ACTUALLY have crossed, tick by tick, at seven latencies. It is the confirmation
     that module says it is owed, and where the two disagree the tick surface is the measurement
     and the bar surface is the proxy.

  3. THE EXECUTION TWIN AND THE FILL SURFACE -- `data/tape/slippage_surface.json`.
     `mt5desk/fill_surface.py` fits E[slip | state] on the desk's own FILLS and falls back to
     "half the spread, wide" until it has 30 of them; `research/execution_twin.py` names its
     consumers and says plainly that its recalibration "is consumed by nobody yet". A desk with
     few fills has almost no data to fit on -- but it has millions of ticks, and the tape gives
     the latency-slippage curve WITHOUT needing a single fill. That is a strictly better prior
     than "half the spread", it is available on day one, and it is per symbol and per hour.

  4. THE INTRABAR PATH -- `data/tape/intrabar/<SYM>/<DAY>.parquet`. Whether the high came before
     the low, per bar, measured. See the CONSUMERS note at the bottom of this file for exactly
     what has to change to use it and why this module does not make that change itself.

WHAT THIS MODULE WILL NOT DO. It will not write a number it did not measure. Every symbol-hour
cell below `MIN_TICKS_PER_CELL` is UNMEASURED and carries no value, so a consumer cannot read one
by accident -- which is the specific failure `cost_surface.py` calls out: rounding an unmeasured
cell to the pooled scalar is the defect that module exists to end, and inheriting it here would
undo the point of measuring.

MEMORY. On the trading box this runs beside the live terminal; on the VPS it would run beside the
miners on 8GB. Either way it declares its need through `research/job_lock.exclusive_job`, which
holds it to the worst of its own measured runs rather than to a hopeful constant.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_DESK = _HERE.parent
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import microstructure as ms  # noqa: E402

from recorders.tape_store import TapeStore  # noqa: E402

SCHEMA = "tape-features-1"
#: The COST SURFACE schema is deliberately the one `research/cost_surface.py` already emits. A
#: different schema here would mean a second reader, a second set of consumers and the producer/
#: consumer collapse this desk keeps paying for.
COST_SCHEMA = "cost-surface-1"

SILVER = _DESK / "data" / "tape" / "ticks"
INTRABAR = _DESK / "data" / "tape" / "intrabar"
COST_OUT = _DESK / "data" / "cost_surface_tick.json"
SLIPPAGE_OUT = _DESK / "data" / "tape" / "slippage_surface.json"
REPORT = _DESK / "reports" / "TAPE_FEATURES.json"
STATE = _DESK / "data" / "tape_features_state.json"
UNIVERSE = _DESK / "data" / "universe" / "universe.json"
#: `tick_integrity`'s verdict per symbol-day. READ BEFORE BUILDING, AND THIS IS THE WHOLE POINT
#: OF HAVING WRITTEN IT. A day the checker called FAIL has a hole in it that no gap row explains,
#: and a spread percentile or a quote-intensity number computed over that hole reads the absence
#: as a calm market. Building features from a failed day would take a known, named, measured data
#: defect and launder it into a feature the gauntlet cannot tell apart from a real one.
INTEGRITY = _DESK / "reports" / "TICK_INTEGRITY.json"

#: The memory this pass declares. Corrected upward by `job_lock.measured_need_mb` from its own
#: observed runs -- a declaration is a floor, never a claim.
NEED_MB = 900

#: Bars the intrabar path is measured on. H1 is the desk's main clock; M15 is the scalp lane's.
INTRABAR_FREQS = ("1h", "15min")

#: Days to look back when nothing has been built yet. Bounded so a first run on a long tape does
#: not try to build a year in one pass -- the watermark makes the next run continue.
DEFAULT_DAYS = 30


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _point_for(symbol: str, store: TapeStore, day: str, registry: dict[str, Any]) -> float:
    """The symbol's point, FROM THE TAPE'S OWN METADATA FIRST.

    The registry is today's value; the segment carries the value in force when the ticks were
    recorded. `mt5desk/tape.py` already documents why that distinction matters -- a field
    re-derived from tomorrow's registry silently re-prices yesterday's tape -- so the recorded
    one wins and the registry is only the fallback for a segment written without a spec.
    """
    recs = store.manifest(symbol, day)
    for r in reversed(recs):
        if r.point and r.point > 0:
            return float(r.point)
    meta = registry.get(symbol) or {}
    digits = meta.get("digits")
    if digits is not None:
        try:
            return float(10.0 ** -int(digits))
        except (TypeError, ValueError):
            pass
    ts = meta.get("tick_size")
    return float(ts) if ts else 0.0


def build_day(store: TapeStore, symbol: str, day: str, point: float) -> dict[str, Any]:
    """Everything one symbol-day donates: silver rows, hour cells, intrabar paths."""
    raw = store.read_day(symbol, day)
    out: dict[str, Any] = {"symbol": symbol, "day": day, "n_ticks": len(raw),
                           "point": point, "cells": [], "silver_rows": 0, "intrabar": {}}
    if raw.empty or point <= 0:
        out["status"] = "NO_TICKS" if raw.empty else "NO_POINT"
        return out
    df = ms.quote_frame(raw, point)
    if df.empty:
        out["status"] = "NO_TWO_SIDED_QUOTES"
        return out
    out["status"] = "BUILT"

    ts = pd.to_datetime(np.asarray(df["time_msc"], dtype=np.int64), unit="ms", utc=True)
    # -- 1. SILVER. `ts, bid, ask` is the contract `orthogonal_sweep._tape_series` reads; the
    # microstructure columns ride along as extras so that reader is unaffected and a richer
    # consumer does not have to re-derive them from the bronze.
    silver = pd.DataFrame({
        "ts": ts,
        "bid": np.asarray(df["bid"], dtype=np.float64),
        "ask": np.asarray(df["ask"], dtype=np.float64),
        "mid": np.asarray(df["mid"], dtype=np.float64),
        "spread_pts": np.asarray(df["spread_pts"], dtype=np.float64),
        "microprice": np.asarray(df["microprice"], dtype=np.float64),
    })
    ofi, ofi_basis = ms.order_flow_imbalance(df)
    silver["ofi_proxy"] = np.concatenate([[0.0], ofi]) if ofi.size else 0.0
    dst = SILVER / symbol / f"{day}.parquet"
    dst.parent.mkdir(parents=True, exist_ok=True)
    _atomic_parquet(silver, dst)
    out["silver_rows"] = len(silver)
    out["ofi_basis"] = ofi_basis

    # -- 2. HOUR CELLS. Broker-clock hour, matching the cost surface's own hour convention.
    hours = ts.hour
    for h in range(24):
        chunk = df.loc[np.asarray(hours == h)]
        if chunk.empty:
            continue
        cell = ms.hour_cell(chunk, symbol, h, point)
        out["cells"].append(cell)

    # -- 3. INTRABAR PATH.
    for freq in INTRABAR_FREQS:
        path = ms.path_excursions(ms.intrabar_path(df, freq), point)
        if path.empty:
            continue
        p = INTRABAR / symbol / freq.replace("min", "m") / f"{day}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        _atomic_parquet(path.reset_index(), p)
        out["intrabar"][freq] = {
            "bars": len(path),
            # THE NUMBER THAT RETIRES THE ASSUMPTION. A backtest that assumes the high came first
            # is right this often and wrong the rest of the time, and until now the desk had no
            # way to say which.
            "high_first_frac": round(float(path["high_first"].mean()), 4),
            "median_t_high_ms": int(path["t_high_ms"].median()),
            "median_t_low_ms": int(path["t_low_ms"].median()),
        }
    return out


def _failed_days() -> tuple[dict[str, str], str]:
    """Symbol-days `tick_integrity` called FAIL, and a note on whether it was consulted at all.

    A MISSING INTEGRITY REPORT DOES NOT BLOCK THE BUILD, and that is a deliberate asymmetry
    rather than an oversight. The checker runs hourly and the feature pass runs hourly; on the
    first hour of a new box the report does not exist yet, and refusing to build anything until
    it does would mean a fresh box produces no features at all until someone notices. What the
    absence DOES do is get stated in the report, so "built without an integrity check" is never
    indistinguishable from "built against a clean one" (L1.28a).
    """
    if not INTEGRITY.exists():
        return {}, ("tick_integrity has not run on this host yet; every day was built WITHOUT a "
                    "verdict. This is stated, not silently equivalent to a clean check.")
    doc = _load(INTEGRITY, {})
    if not doc:
        return {}, f"{INTEGRITY.name} is unreadable; built without a verdict"
    out: dict[str, str] = {}
    for row in (doc.get("days") or []):
        if row.get("verdict") == "FAIL":
            out[f"{row.get('symbol')}/{row.get('day')}"] = "; ".join(row.get("reasons") or [])
    return out, (f"{INTEGRITY.name} at {doc.get('generated_utc')}: verdict "
                 f"{doc.get('verdict')}, {len(out)} symbol-day(s) refused")


def _atomic_parquet(df: pd.DataFrame, dst: Path) -> None:
    """Write a derived parquet without ever leaving a torn file where a good one was.

    The SILVER layer is rebuildable from bronze, so a torn file here is recoverable in a way a
    torn segment is not -- but a consumer that reads a half-written parquet gets an exception in
    the middle of a gauntlet run, and the fix costs one rename.
    """
    tmp = dst.parent / f".tmp-{dst.name}"
    df.to_parquet(tmp, index=False, compression="zstd")
    tmp.replace(dst)


def cost_surface_from_cells(by_symbol: dict[str, list[ms.QuoteStats]],
                            registry: dict[str, Any]) -> dict[str, Any]:
    """A `cost-surface-1` document measured from ticks rather than from bar spread columns.

    Shape-identical to `research/cost_surface.py`'s output on purpose: `spread_pts(surface, sym,
    hour)` in that module reads this with no change, so the tick measurement can replace the bar
    proxy at every one of its ~25 call sites by pointing at a different file.

    The EXTENSION fields carry what the bar surface structurally cannot have: the effective
    spread at each latency, the slippage on top of the half-spread, the realised spread, the
    price impact, quote intensity and burstiness. They sit alongside p50/p75/p90 rather than
    replacing them, so an old reader sees exactly the schema it expects.
    """
    symbols: dict[str, Any] = {}
    for sym, cells in sorted(by_symbol.items()):
        hours: dict[str, Any] = {}
        pooled = (registry.get(sym) or {}).get("median_spread_pts")
        for c in sorted(cells, key=lambda x: x.hour):
            row: dict[str, Any] = {"n_bars": c.n_ticks, "n_nonzero": c.n_ticks,
                                   "zero_frac": c.zero_spread_frac}
            if c.status != "MEASURED" or c.quoted_spread_pts_p50 is None:
                # NO NUMBER IS EMITTED. A consumer cannot round an unmeasured cell to the pooled
                # scalar if there is nothing there to round.
                row["status"] = "UNMEASURED"
            else:
                row.update({
                    "status": "MEASURED",
                    "p50": c.quoted_spread_pts_p50,
                    "p75": c.quoted_spread_pts_p75,
                    "p90": c.quoted_spread_pts_p90,
                    "p99": c.quoted_spread_pts_p99,
                    "effective_spread_pts": c.effective_spread_pts,
                    "latency_slip_pts": c.latency_slip_pts,
                    # Buy-side realised spread; the two-sided average is algebraically the
                    # quoted spread and carries no information (see microstructure.py).
                    "realised_spread_pts_buy": c.realised_spread_pts,
                    "mid_move_pts": c.mid_move_pts,
                    "price_impact_pts": ms.price_impact_pts(c),
                    "quote_intensity_per_min": c.quote_intensity_per_min,
                    "burstiness": c.burstiness,
                    "stale_frac": c.stale_frac,
                    "ofi_mean": c.ofi_mean,
                    "ofi_basis": c.ofi_basis,
                    "crossed_frac": c.crossed_frac,
                })
            hours[str(c.hour)] = row
        measured = {h: r for h, r in hours.items() if r.get("status") == "MEASURED"}
        entry: dict[str, Any] = {
            "hours": hours,
            "n_hours_measured": len(measured),
            "pooled_median_spread_pts": (float(pooled) if pooled is not None else None),
            "tick_size": float((registry.get(sym) or {}).get("tick_size", 0.0) or 0.0),
            "contract_size": float((registry.get(sym) or {}).get("contract_size", 0.0) or 0.0),
            "basis": "tick_tape",
        }
        if measured:
            p50s = {int(h): float(r["p50"]) for h, r in measured.items()}
            cheap = min(p50s, key=lambda k: p50s[k])
            dear = max(p50s, key=lambda k: p50s[k])
            entry["cheapest_hour"] = cheap
            entry["dearest_hour"] = dear
            entry["dear_over_cheap"] = (round(p50s[dear] / p50s[cheap], 2) if p50s[cheap] else None)
            entry["administered"] = bool(len(set(p50s.values())) == 1)
            p90s = {int(h): float(r["p90"]) for h, r in measured.items() if r.get("p90")}
            ratios = [p90s[h] / p50s[h] for h in p90s if p50s[h] > 0]
            entry["stress_p90_over_p50"] = (round(float(np.median(ratios)), 2) if ratios else None)
            # THE COMPARISON THAT MATTERS: how wrong is the number every gate currently divides
            # by? Reported in BOTH directions -- undercharging manufactures survivors, and
            # overcharging kills real edges silently, which is the direction nothing else on this
            # desk instruments.
            if pooled:
                entry["tick_over_pooled_p50"] = round(float(np.median(list(p50s.values())))
                                                      / float(pooled), 3)
        symbols[sym] = entry
    return {
        "schema": COST_SCHEMA,
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "source": "mt5 tick tape (recorders/tick_recorder)",
        "min_obs": ms.MIN_TICKS_PER_CELL,
        "latency_grid_ms": list(ms.LATENCY_GRID_MS),
        "realised_horizons_ms": list(ms.REALISED_HORIZONS_MS),
        "n_symbols": len(symbols),
        "n_skipped": 0,
        "skipped": [],
        "symbols": symbols,
        "note": ("Byte-compatible with research/cost_surface.py's cost-surface-1 so "
                 "cost_surface.spread_pts() reads it unchanged. Where the two disagree the TICK "
                 "surface is the measurement of what an order actually crosses and the bar "
                 "surface is the broker's stamped spread on an H1 bar -- the live-tick "
                 "confirmation that module records as owed."),
    }


def slippage_surface(by_symbol: dict[str, list[ms.QuoteStats]]) -> dict[str, Any]:
    """E[slip beyond the half-spread | symbol, hour, latency], in points.

    `mt5desk/fill_surface.py` falls back to `0.5 * spread` with a wide sd until it has 30 joined
    fills, and a desk that has just started has nowhere near 30 in most symbols. This is the same
    quantity estimated from millions of quote revisions instead of tens of fills: strictly more
    data, available immediately, and per hour rather than pooled. It does not replace the fitted
    surface -- a real fill carries queue position and broker behaviour a quote stream cannot see
    -- it replaces the CONSTANT the fitted surface falls back to.
    """
    out: dict[str, Any] = {}
    for sym, cells in sorted(by_symbol.items()):
        hours = {}
        for c in cells:
            if c.status != "MEASURED" or not c.latency_slip_pts:
                continue
            hours[str(c.hour)] = {"n_ticks": c.n_ticks,
                                  "half_spread_pts": (round(c.quoted_spread_pts_p50 / 2.0, 3)
                                                      if c.quoted_spread_pts_p50 else None),
                                  "latency_slip_pts": c.latency_slip_pts,
                                  "p90_spread_pts": c.quoted_spread_pts_p90,
                                  "price_impact_pts": ms.price_impact_pts(c)}
        if hours:
            out[sym] = {"hours": hours}
    return {
        "schema": "slippage-surface-1",
        "built_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "units": "broker points; slip is IN ADDITION to the half-spread already charged",
        "latency_grid_ms": list(ms.LATENCY_GRID_MS),
        "consumers": {
            "desks/mt5/mt5desk/fill_surface.py": (
                "FillSurface.expected_slip falls back to `0.5 * spread_frac_prior` with sd = "
                "spread_frac when fewer than MIN_FILLS=30 fills have been joined. That constant "
                "is what this replaces: read the symbol-hour cell and use half_spread + "
                "latency_slip_pts[L] for the desk's actual decision-to-fill latency."),
            "desks/mt5/research/execution_twin.py": (
                "the twin's PredictedFill can be seeded from this instead of a modelled spread, "
                "so predicted-vs-actual measures the BROKER rather than measuring the desk's own "
                "assumption"),
        },
        "symbols": out,
    }


def run(store: TapeStore, symbols: list[str] | None = None, days_back: int = DEFAULT_DAYS,
        rebuild: bool = False) -> dict[str, Any]:
    """Build every symbol-day whose bronze is newer than its silver. Incremental by design."""
    registry = _load(UNIVERSE, {})
    state = {} if rebuild else _load(STATE, {})
    failed_days, integrity_note = _failed_days()
    syms = symbols if symbols is not None else store.symbols()
    cutoff = ""
    if days_back:
        cutoff = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=int(days_back))).date().isoformat()

    by_symbol: dict[str, list[ms.QuoteStats]] = {}
    built: list[dict[str, Any]] = []
    skipped: list[str] = []
    intrabar_tally: dict[str, dict[str, float]] = {}
    for sym in syms:
        cells: list[ms.QuoteStats] = []
        for day in store.days(sym):
            if cutoff and day < cutoff:
                continue
            key = f"{sym}/{day}"
            if key in failed_days:
                # REFUSED, NOT SKIPPED QUIETLY. The refusal is in the report with the checker's
                # own reason attached, so a symbol whose features stop appearing has a named
                # cause instead of looking like a symbol nobody trades.
                skipped.append(f"{key}: REFUSED, tick_integrity verdict FAIL "
                               f"({failed_days[key][:120]})")
                continue
            seal = store.seal(sym, day)
            # THE WATERMARK IS THE DAY'S OWN CONTENT, not a timestamp. A sealed day is keyed by
            # its manifest digest, so a day that GREW after being built is rebuilt and a day that
            # did not is skipped -- an mtime would rebuild everything after any touch.
            token = (seal.manifest_sha256 if seal else f"unsealed:{store.day_bytes(sym, day)}")
            if not rebuild and state.get(key) == token:
                continue
            point = _point_for(sym, store, day, registry)
            res = build_day(store, sym, day, point)
            if res["status"] != "BUILT":
                skipped.append(f"{key}: {res['status']}")
                continue
            cells.extend(res.pop("cells"))
            for freq, row in res["intrabar"].items():
                t = intrabar_tally.setdefault(freq, {"bars": 0.0, "high_first": 0.0})
                t["bars"] += row["bars"]
                t["high_first"] += row["bars"] * row["high_first_frac"]
            built.append(res)
            state[key] = token
        if cells:
            by_symbol[sym] = _merge_cells(cells)

    cost = cost_surface_from_cells(by_symbol, registry)
    slip = slippage_surface(by_symbol)
    for path, doc in ((COST_OUT, cost), (SLIPPAGE_OUT, slip)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", "utf-8")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=0, sort_keys=True) + "\n", "utf-8")

    measured_cells = sum(1 for cells in by_symbol.values() for c in cells if c.status == "MEASURED")
    total_cells = sum(len(c) for c in by_symbol.values())
    return {
        "schema": SCHEMA,
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "tape_root": str(store.root),
        "symbol_days_built": len(built),
        "silver_rows": sum(int(b["silver_rows"]) for b in built),
        "symbols": sorted(by_symbol),
        "cells_measured": measured_cells,
        "cells_total": total_cells,
        "cells_unmeasured": total_cells - measured_cells,
        "intrabar": {f: {"bars": int(t["bars"]),
                         "high_first_frac": (round(t["high_first"] / t["bars"], 4)
                                             if t["bars"] else None)}
                     for f, t in sorted(intrabar_tally.items())},
        "artifacts": {
            "silver": str(SILVER), "intrabar": str(INTRABAR),
            "cost_surface": str(COST_OUT), "slippage_surface": str(SLIPPAGE_OUT),
        },
        "integrity": integrity_note,
        "days_refused_on_integrity": len(failed_days),
        "skipped": skipped[:50],
        "n_skipped": len(skipped),
        # NAMED, NOT IMPLIED. A feature nobody reads is the failure mode this module exists to
        # avoid, so every artifact says who is supposed to read it and what happens if nobody does.
        "consumers": CONSUMERS,
    }


def _merge_cells(cells: list[ms.QuoteStats]) -> list[ms.QuoteStats]:
    """Pool a symbol's per-day hour cells into one cell per hour, weighted by tick count.

    A one-day cell is a sample of one session, and the cost surface's whole point is a stable
    symbol-hour profile. Percentiles cannot be averaged exactly without keeping the raw values,
    so what is pooled here is the tick-weighted mean of each day's statistic -- stated plainly,
    because a weighted mean of medians is an approximation and calling it a median would be a
    small lie that a later reader would inherit as a fact.
    """
    out: list[ms.QuoteStats] = []
    for hour in range(24):
        same = [c for c in cells if c.hour == hour and c.status == "MEASURED"]
        n_all = sum(c.n_ticks for c in cells if c.hour == hour)
        if not same:
            if n_all:
                out.append(ms.QuoteStats(symbol=cells[0].symbol, hour=hour, n_ticks=n_all))
            continue
        w = np.array([c.n_ticks for c in same], dtype=float)
        w = w / w.sum()

        def _wm(vals: list[float | None], weights: np.ndarray = w) -> float | None:
            arr = np.array([v if v is not None else np.nan for v in vals], dtype=float)
            ok = np.isfinite(arr)
            return (round(float(np.average(arr[ok], weights=weights[ok])), 3)
                    if ok.any() else None)

        merged = ms.QuoteStats(
            symbol=same[0].symbol, hour=hour, n_ticks=n_all, status="MEASURED",
            quoted_spread_pts_p50=_wm([c.quoted_spread_pts_p50 for c in same]),
            quoted_spread_pts_p75=_wm([c.quoted_spread_pts_p75 for c in same]),
            quoted_spread_pts_p90=_wm([c.quoted_spread_pts_p90 for c in same]),
            quoted_spread_pts_p99=_wm([c.quoted_spread_pts_p99 for c in same]),
            quote_intensity_per_min=_wm([c.quote_intensity_per_min for c in same]),
            burstiness=_wm([c.burstiness for c in same]),
            stale_frac=_wm([c.stale_frac for c in same]),
            ofi_mean=_wm([c.ofi_mean for c in same]),
            ofi_basis=same[0].ofi_basis,
            microprice_basis=same[0].microprice_basis,
            zero_spread_frac=_wm([c.zero_spread_frac for c in same]),
            crossed_frac=_wm([c.crossed_frac for c in same]),
        )
        for grid, attr in ((ms.LATENCY_GRID_MS, "effective_spread_pts"),
                           (ms.LATENCY_GRID_MS, "latency_slip_pts"),
                           (ms.REALISED_HORIZONS_MS, "realised_spread_pts"),
                           (ms.REALISED_HORIZONS_MS, "mid_move_pts")):
            target = getattr(merged, attr)
            for k in grid:
                v = _wm([getattr(c, attr).get(str(k)) for c in same])
                if v is not None:
                    target[str(k)] = v
        out.append(merged)
    return out


#: WHO READS WHAT, and what it costs if nobody does. Stated as data so the capability graph's
#: DEAD_PRODUCER check has something to point at and a person can audit the claim.
CONSUMERS: dict[str, str] = {
    "desks/mt5/research/orthogonal_sweep.py::_tape_series": (
        "reads data/tape/ticks/<SYM>/<DAY>.parquet (ts,bid,ask) -> family_inputs.resolve -> the "
        "liquidity_regime and orderflow_imbalance families in the gauntlet AND the forward "
        "engine. Already wired; this module is a second producer of that exact contract."),
    "desks/mt5/research/cost_surface.py::spread_pts": (
        "reads a cost-surface-1 document. data/cost_surface_tick.json is byte-compatible, so "
        "switching the ~25 consumers to the measured surface is a path change, not a rewrite. "
        "NOT DONE HERE: cost_surface.py is outside this seat's territory and the switch should "
        "be made once, deliberately, with the two surfaces compared first."),
    "desks/mt5/mt5desk/fill_surface.py::FillSurface.expected_slip": (
        "falls back to 0.5*spread with sd=spread below MIN_FILLS=30 joined fills. "
        "data/tape/slippage_surface.json is that constant, measured per symbol per hour per "
        "latency from the tape. NOT WIRED HERE: fill_surface is on the execution path's cost "
        "model and the change deserves its own before/after on the twin's calibration table."),
    "desks/mt5/mt5desk/engine.py::run_backtest": (
        "data/tape/intrabar/<SYM>/<FREQ>/<DAY>.parquet carries high_first, t_high_ms, t_low_ms, "
        "mae_pts and mfe_pts per bar. The engine currently has to assume an order for the "
        "extremes, which decides stop-vs-target on exactly the bars where both were touched. "
        "NOT CHANGED HERE ON PURPOSE: every live certificate was minted by this engine, so "
        "changing its fill semantics silently re-prices the whole canon. The measurement is now "
        "available; the change is a deliberate, separately-evidenced revaluation."),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Turn the MT5 tick tape into what the desk reads")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--symbols", type=str, default="")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--out", type=Path, default=REPORT)
    args = ap.parse_args(argv)

    from recorders.tick_recorder import DEFAULT_TAPE_ROOT
    store = TapeStore(args.root or Path(DEFAULT_TAPE_ROOT))
    if not store.ticks_dir.is_dir():
        print(f"tape_features: no tape at {store.root} -- nothing to build. This is UNMEASURED, "
              f"not a clean build: start recorders/tick_recorder.py first.")
        return 1

    syms = [s.strip() for s in args.symbols.split(",") if s.strip()] or None
    try:
        from research.job_lock import exclusive_job
    except ImportError:
        exclusive_job = None                                   # type: ignore[assignment]

    if exclusive_job is None:
        rep = run(store, syms, args.days, args.rebuild)
    else:
        with exclusive_job("tape_features", need_mb=NEED_MB) as admitted:
            if not admitted:
                print("tape_features: stood down (another instance, or the box cannot fit this "
                      "pass right now). The tape is unharmed and the next run resumes from the "
                      "watermark.")
                return 0
            rep = run(store, syms, args.days, args.rebuild)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", "utf-8")
    print(f"tape_features: {rep['symbol_days_built']} symbol-day(s) built, "
          f"{rep['silver_rows']:,} silver rows, {rep['cells_measured']}/{rep['cells_total']} "
          f"symbol-hour cells MEASURED")
    for freq, t in rep["intrabar"].items():
        print(f"  intrabar {freq}: {t['bars']:,} bars, high came first on "
              f"{t['high_first_frac']} of them")
    print(f"  -> {COST_OUT.name}, {SLIPPAGE_OUT.name}, {args.out.name}")
    # YIELD line, in the convention `research/hourly_discovery.run_organ` parses.
    print(f"YIELD symbol_days={rep['symbol_days_built']} cells={rep['cells_measured']} "
          f"silver_rows={rep['silver_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
