"""Mint session_range_breakout legs on instruments UNCORRELATED to each other and to the live book.

THE PRODUCER THE BASKET JUDGE WAS WAITING FOR. `research/srb_basket_judge.py` (recovered box patch
13) reads `reports/SRB_UNCORRELATED_SWEEP.json` and nothing else. On the box that file was written
once, by hand, on 2026-09-24, and no organ on any clock ever wrote it again -- so the basket judge
was an hourly leg reading a photograph, and on every other host it read UNMEASURED for ever. This
organ is that sweep, on a clock.

WHAT IT DOES, in the order the basket judge needs it:

  1. THE HYPOTHESIS LANE ONLY. Instruments come from MetaTrader's own registry through
     `universe_policy.lane`; share CFDs and anything UNCLASSIFIED are not hunted here (the
     two-lane order), and a symbol with no H1 parquet is reported, not guessed.
  2. CORRELATION BLOCKS. Each instrument's daily close-to-close log return is clustered by average
     linkage on 1 - |rho|, cut at |rho| = BLOCK_RHO. An instrument with fewer than MIN_DAYS daily
     returns is NOT clustered: its cells carry `block: null`, which the basket judge excludes from
     every one-per-block rule rather than promoting to a block of its own (an unmeasured
     independence is not a measured one).
  3. UNCORRELATED TO THE LIVE BOOK. Every instrument's max |rho| against the instruments the LIVE
     sleeves trade (data/sleeves.json, read only) is measured and published. Instruments at or
     above LIVE_RHO_MAX are listed in `correlated_to_live` with their rho and are not minted: this
     sweep's whole question is what the book does NOT already hold. It is a scope, not a verdict --
     nothing is retired, capped or sized by it, and the main gauntlet still judges those
     instruments through its own docket.
  4. ONE LEG PER (INSTRUMENT, SESSION). The four session windows are the family's own
     (`miner_candidate_compiler._SESSION_PARAMS`, pinned equal by test). Each leg's daily R series
     is the sealed gauntlet's own `build_cell` / `daily_series` / `costs_for`, read from its
     content-addressed cache when that is warm, so `sharpe_is` here is the number the basket judge
     re-derives and reports as `sharpe_reproduction_max_err`.

WHAT IT DOES NOT DO: it judges nothing. No cell is handed to `run_gauntlet`, no gate ledger or
certificate is written and no trial is charged here -- the basket judge charges every basket it
judges (data/srb_basket_trials.jsonl), and single legs reach the judge through the docket like any
other cell. The in-sample Sharpe it publishes is a description the basket judge's sign-flip null
exists to discount, never evidence.

CADENCE: the legs move with one new daily bar, so a pass younger than `--max-age-h` (default 20)
is kept and the leg exits at once. Legs a pass could not reach inside its budget are CARRIED from
the previous artifact (marked `carried: true`) so a short hour never shrinks the basket's
universe, and `coverage` says exactly how many were built, carried and left unreached.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[3]
MT5 = BASE / "desks" / "mt5"
REPORTS = MT5 / "reports"
OUT = REPORTS / "SRB_UNCORRELATED_SWEEP.json"
SLEEVES = MT5 / "data" / "sleeves.json"

for _p in (str(BASE), str(MT5), str(MT5 / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FAMILY = "session_range_breakout"

#: The family's four session windows, in the family's own parameters. Pinned equal to
#: `miner_candidate_compiler._SESSION_PARAMS` by test, so the sweep and the compiler can never
#: disagree about what "london_am" means. Not imported: that module is heavy and this one runs as
#: a subprocess leg.
SESSIONS: dict[str, dict[str, int]] = {
    "asia": {"range_start": 7},
    "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13},
    "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14},
    "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17},
}

#: Two instruments whose daily returns correlate at or above this |rho| share a block.
BLOCK_RHO = 0.5
#: An instrument is "held by the live book" at or above this |rho| to any LIVE sleeve instrument.
LIVE_RHO_MAX = 0.5
#: Daily returns an instrument needs before its correlation is a measurement.
MIN_DAYS = 250
#: Overlapping days a PAIR needs before its rho counts; below it the pair reads 0 (unrelated),
#: which can only split blocks, never merge them.
MIN_OVERLAP = 120
#: A leg with fewer daily observations than this is not a leg the basket judge can use.
MIN_LEG_DAYS = 60


# --------------------------------------------------------------------------- the universe


def hypothesis_symbols(meta: dict[str, Any]) -> tuple[list[str], dict[str, int]]:
    """The hypothesis-lane symbols of the registry, and a count of what was set aside by lane."""
    from research import universe_policy as up

    keep: list[str] = []
    aside: dict[str, int] = {}
    for sym in sorted(meta):
        if not isinstance(meta.get(sym), dict):
            continue
        ln = up.lane(sym)
        if ln == up.HYPOTHESIS:
            keep.append(sym)
        else:
            aside[ln] = aside.get(ln, 0) + 1
    return keep, aside


def daily_returns(frame: pd.DataFrame | None) -> pd.Series | None:
    """Daily close-to-close log returns of an H1 frame, indexed by UTC date."""
    if frame is None or "close" not in getattr(frame, "columns", ()) or len(frame) == 0:
        return None
    close = frame["close"].astype(float)
    close = close[close > 0]
    if close.empty:
        return None
    idx = pd.DatetimeIndex(close.index)
    daily = close.groupby(idx.normalize()).last()
    out = np.log(daily).diff().dropna()
    out.index = pd.DatetimeIndex(out.index).tz_localize(None) if out.index.tz is not None \
        else out.index
    return out


def correlation_blocks(returns: dict[str, pd.Series]) -> tuple[dict[str, int | None], list[str]]:
    """Average-linkage blocks on 1 - |rho|, cut at BLOCK_RHO.

    Returns (block per symbol, symbols dropped for short history). Block numbers are assigned in
    the order of each block's alphabetically first member, so they are stable across passes that
    see the same clustering.
    """
    long_enough = sorted(s for s, r in returns.items() if r is not None and len(r) >= MIN_DAYS)
    dropped = sorted(s for s in returns if s not in set(long_enough))
    blocks: dict[str, int | None] = dict.fromkeys(dropped)
    if not long_enough:
        return blocks, dropped
    if len(long_enough) == 1:
        blocks[long_enough[0]] = 0
        return blocks, dropped
    panel = pd.DataFrame({s: returns[s] for s in long_enough})
    rho = np.array(panel.corr(min_periods=MIN_OVERLAP).abs().fillna(0.0).to_numpy(float))
    np.fill_diagonal(rho, 1.0)
    dist = np.clip(1.0 - rho, 0.0, 1.0)
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    labels = fcluster(linkage(squareform(dist, checks=False), method="average"),
                      t=1.0 - BLOCK_RHO, criterion="distance")
    first: dict[int, str] = {}
    for sym, lab in zip(long_enough, labels, strict=True):
        first.setdefault(int(lab), sym)
    order = {lab: i for i, lab in enumerate(sorted(first, key=lambda k: first[k]))}
    for sym, lab in zip(long_enough, labels, strict=True):
        blocks[sym] = order[int(lab)]
    return blocks, dropped


def live_sleeve_symbols(path: Path = SLEEVES) -> list[str]:
    """The instruments the LIVE sleeves trade. Read only; an unreadable file is an empty book."""
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    rows = raw.get("sleeves") if isinstance(raw, dict) else raw
    out = {str(r.get("symbol")) for r in rows or []
           if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"
           and r.get("symbol")}
    return sorted(out)


def live_rho(returns: dict[str, pd.Series], live: Iterable[str]) -> dict[str, float | None]:
    """Each symbol's max |rho| to any live-sleeve instrument; None when nothing overlaps enough.

    A symbol that IS a live-sleeve instrument reads 1.0: the book already holds it.
    """
    live = [s for s in live if returns.get(s) is not None]
    out: dict[str, float | None] = {}
    for sym, r in returns.items():
        if r is None:
            out[sym] = None
            continue
        if sym in live:
            out[sym] = 1.0
            continue
        best: float | None = None
        for ls in live:
            both = pd.concat([r, returns[ls]], axis=1, join="inner").dropna()
            if len(both) < MIN_OVERLAP:
                continue
            c = float(both.iloc[:, 0].corr(both.iloc[:, 1]))
            if math.isfinite(c):
                best = abs(c) if best is None else max(best, abs(c))
        out[sym] = None if best is None else round(best, 4)
    return out


# --------------------------------------------------------------------------- the legs


def leg_key(arm: str, sym: str, params: dict[str, Any]) -> str:
    """The same key `srb_basket_judge._leg_key` builds from a row."""
    return f"{arm}|{sym}|{json.dumps(params, sort_keys=True, separators=(',', ':'))}"


def _gauntlet() -> Any:
    """The SEALED judge's module, imported as a library and never modified."""
    import external_gauntlet  # type: ignore[import-not-found]
    return external_gauntlet


def gauntlet_leg(sym: str, params: dict[str, Any],
                 meta: dict[str, Any]) -> tuple[pd.Series, pd.Series] | None:
    """One leg's daily R at 1x and at the sealed 3x cost scenario, built by the sealed gauntlet's
    own functions and served from its own cache when warm. None when it cannot be built."""
    G = _gauntlet()
    frame = G._bars_for(sym, "H1")
    if frame is None:
        return None
    last_day = frame.index[-1].normalize()
    got = G.cache_load(G._cache_key(sym, FAMILY, params, str(last_day.date()), "H1"))
    if got is not None:
        return got[0], got[1]
    cell = G.build_cell(sym, FAMILY, params, meta)
    if cell is None:
        return None
    costs3 = G.costs_for(sym, meta, mult=G.COST_SCENARIO)
    ds1 = G._series_trim_partial(G.daily_series(cell["df"], cell["sigs"], cell["costs"]),
                                 last_day)
    ds3 = G._series_trim_partial(G.daily_series(cell["df"], cell["sigs"], costs3), last_day)
    return ds1, ds3


def _sharpe(arr: np.ndarray) -> float:
    from libs.validation.dsr import sharpe_ratio
    return float(sharpe_ratio(arr))


def interleave_by_block(symbols: list[str], blocks: dict[str, int | None]) -> list[str]:
    """Round-robin across blocks, so a budget that runs out still covers the most blocks."""
    by: dict[Any, list[str]] = {}
    for s in symbols:
        by.setdefault(blocks.get(s), []).append(s)
    keys = sorted(by, key=lambda k: (k is None, -1 if k is None else k))
    out: list[str] = []
    while any(by[k] for k in keys):
        for k in keys:
            if by[k]:
                out.append(by[k].pop(0))
    return out


# --------------------------------------------------------------------------- the sweep


def _previous(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def fresh_enough(prev: dict[str, Any], max_age_h: float, now: datetime) -> bool:
    try:
        at = datetime.fromisoformat(str(prev.get("generated_at")))
    except ValueError:
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return bool(prev.get("measured")) and (now - at).total_seconds() < max_age_h * 3600.0


def build(*, budget_s: float = 480.0, meta: dict[str, Any] | None = None,
          symbols: list[str] | None = None,
          bars_for: Callable[[str], pd.DataFrame | None] | None = None,
          leg_for: Callable[[str, dict[str, Any], dict[str, Any]],
                            tuple[pd.Series, pd.Series] | None] | None = None,
          live: list[str] | None = None, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """One sweep. Every input is injectable so the test runs it without a terminal or parquets."""
    t0 = time.monotonic()
    deadline = t0 + budget_s
    now = datetime.now(UTC)
    aside: dict[str, int] = {}
    if meta is None:
        try:
            meta = json.loads((MT5 / "data" / "universe" / "universe.json").read_text("utf-8"))
        except (OSError, ValueError) as exc:
            return {"measured": False, "generated_at": now.isoformat(),
                    "why": f"UNMEASURED: universe.json unreadable ({type(exc).__name__})"}
    if symbols is None:
        symbols, aside = hypothesis_symbols(meta)
    if bars_for is None:
        G = _gauntlet()

        def bars_for(sym: str) -> pd.DataFrame | None:
            return G._bars_for(sym, "H1")
    leg_for = leg_for or gauntlet_leg
    live = live_sleeve_symbols() if live is None else live

    returns: dict[str, pd.Series] = {}
    no_bars: list[str] = []
    for sym in sorted(set(symbols) | set(live)):
        r = daily_returns(bars_for(sym))
        if r is None:
            if sym in symbols:
                no_bars.append(sym)
            continue
        returns[sym] = r
    if not any(s in returns for s in symbols):
        return {"measured": False, "generated_at": now.isoformat(),
                "why": f"UNMEASURED: none of {len(symbols)} hypothesis-lane symbols has H1 bars "
                       f"on this host", "no_bars": len(no_bars)}

    cand = {s: returns[s] for s in symbols if s in returns}
    blocks, dropped = correlation_blocks(cand)
    rho_live = live_rho({**cand, **{s: returns[s] for s in live if s in returns}}, live)
    correlated = sorted(
        ({"symbol": s, "live_sleeve_max_abs_rho": rho_live[s]} for s in cand
         if rho_live.get(s) is not None and float(rho_live[s] or 0.0) >= LIVE_RHO_MAX),
        key=lambda d: (-float(d["live_sleeve_max_abs_rho"] or 0.0), d["symbol"]))
    held = {d["symbol"] for d in correlated}
    minted = interleave_by_block([s for s in sorted(cand) if s not in held], blocks)

    prev_rows = {leg_key(r["arm"], r["symbol"], r["params"]): r
                 for r in (previous or {}).get("cells") or []
                 if isinstance(r, dict) and {"arm", "symbol", "params"} <= set(r)}
    cells: list[dict[str, Any]] = []
    built = carried = unbuildable = unreached = 0
    for sym in minted:
        for sess, params in SESSIONS.items():
            arm = f"session_{sess}"
            key = leg_key(arm, sym, dict(params))
            if time.monotonic() > deadline:
                old = prev_rows.get(key)
                if old is not None:
                    cells.append({**old, "block": blocks.get(sym),
                                  "live_sleeve_max_abs_rho": rho_live.get(sym), "carried": True})
                    carried += 1
                else:
                    unreached += 1
                continue
            try:
                got = leg_for(sym, dict(params), meta)
            except Exception as exc:                     # one bad leg never ends the sweep
                print(f"  {sym} {sess}: {type(exc).__name__}: {exc}", flush=True)
                got = None
            if got is None or len(got[0]) < MIN_LEG_DAYS:
                unbuildable += 1
                continue
            ds1, ds3 = got
            a1 = ds1.to_numpy(float)
            cells.append({
                "arm": arm, "symbol": sym, "params": dict(params),
                "block": blocks.get(sym), "days": len(a1),
                "first_day": str(pd.Timestamp(ds1.index[0]).date()),
                "last_day": str(pd.Timestamp(ds1.index[-1]).date()),
                "sharpe_is": round(_sharpe(a1), 8),
                "sharpe_is_3x": round(_sharpe(ds3.to_numpy(float)), 8),
                "mean_daily_R_1x": round(float(a1.mean()), 6),
                "live_sleeve_max_abs_rho": rho_live.get(sym),
            })
            built += 1

    n_blocks = len({b for b in blocks.values() if b is not None})
    return {
        "measured": True,
        "generated_at": now.isoformat(),
        "family": FAMILY,
        "what_this_is": (
            "session_range_breakout legs, one per (hypothesis-lane instrument, session window), "
            "on instruments clustered into correlation blocks and NOT held by the live book. "
            "Minted and measured, never judged: srb_basket_judge sums them into baskets and "
            "charges each basket it hands to the sealed gauntlet."),
        "universe": {"hypothesis_lane": len(symbols), "set_aside_by_lane": aside,
                     "with_bars": len(cand), "no_bars": len(no_bars)},
        "blocks": {"rule": f"average linkage on 1-|rho| of daily log returns, cut at |rho| "
                           f"{BLOCK_RHO}; pairs with < {MIN_OVERLAP} common days read 0",
                   "n_blocks": n_blocks, "min_days": MIN_DAYS,
                   "dropped_short_history": dropped},
        "live_book": {"sleeve_instruments": live, "rho_max": LIVE_RHO_MAX,
                      "measure": "max |rho| of daily log returns to any LIVE sleeve instrument",
                      "n_held": len(held)},
        "correlated_to_live": correlated,
        "sessions": SESSIONS,
        "cells": cells,
        "coverage": {"instruments_minted": len(minted), "cells": len(cells), "built": built,
                     "carried": carried, "unbuildable": unbuildable, "unreached": unreached,
                     "budget_s": budget_s},
        "seconds": round(time.monotonic() - t0, 1),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=480.0)
    ap.add_argument("--max-age-h", type=float, default=20.0,
                    help="keep a measured pass younger than this and exit at once")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    prev = _previous(a.out)
    if fresh_enough(prev, a.max_age_h, datetime.now(UTC)):
        print(f"srb uncorrelated sweep: {a.out.name} is younger than {a.max_age_h}h -- kept")
        return 0
    doc = build(budget_s=a.budget_s, previous=prev)
    if not doc.get("measured") and prev.get("measured"):
        # An unmeasured pass never overwrites a measured one: the judge keeps reading real legs.
        print(f"srb uncorrelated sweep: {doc.get('why')} -- previous sweep kept")
        return 0
    try:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = a.out.with_name(a.out.name + ".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(a.out)
    except OSError as exc:
        print(f"srb uncorrelated sweep: could not write {a.out}: {exc}")
        return 1
    if doc.get("measured"):
        c = doc["coverage"]
        print(f"srb uncorrelated sweep: {c['cells']} leg(s) on {c['instruments_minted']} "
              f"instrument(s) in {doc['blocks']['n_blocks']} block(s); "
              f"{doc['live_book']['n_held']} held by the live book; built {c['built']}, "
              f"carried {c['carried']}, unreached {c['unreached']}")
    else:
        print(f"srb uncorrelated sweep: {doc.get('why')}")
    print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
