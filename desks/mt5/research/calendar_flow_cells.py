#!/usr/bin/env python3
"""CALENDAR FLOW CELLS -- every dated forced-flow kind, minted as gauntlet cells every hour.

WHY THIS EXISTS (principal 2026-10-13: "calendar and flow mechanics ... all mapped to MT5 symbols")

`research/forced_flow_calendar.py` dates eighteen kinds of compelled flow -- the WMR fix, month
and quarter end, the Tokyo fix and its gotobi days, the Japanese fiscal half-year ends, equity and
FX option expiries, the US coupon auctions and the refunding, Chinese closures, inventory, USDA --
and `family_forced_flow` trades the window around any of them. But the breadth sweep calls that
family at its DEFAULTS only (`event_kind="month_end"`, `clock="bars"`), so seventeen of the
eighteen kinds never reached the judge as a cell, and the one that did read its UTC windows on the
broker's bar clock -- the two-to-three-hour error the family's own docstring warns about.

WHAT IT DOES, and nothing more:

  1. For every kind, takes the instruments the calendar ITSELF names for that kind (already
     intersected with the broker registry and the hypothesis lane by `_keep`), so a Chinese
     closure is never tested on EURCHF and a gilt auction never on USDJPY.
  2. Builds the preregistered grid: kind x mode (pre_flow, post_flow_fade) x polarity (+1, -1),
     on the UTC clock, at the family's own window and exit defaults. The grid is fixed in this
     file BEFORE any return is seen; nothing here reads a P&L.
  3. Measures FIRING only -- how many distinct days the cell could trade -- the same lower bound
     `cross_sectional_breadth.firing` uses, and holds back a cell whose firing cannot reach the
     sealed gauntlet's 60-day floor. That is a buildability screen, not a performance screen: a
     refunding cell with 30 events in a decade is OBSERVATION-SCARCE, counted and named, never
     minted to be judged as a market "no" the market never gave.
  4. Donates every cell that clears, once per identity, through `proposer_common.donate` -- the
     one intake (PIT stamp, two-lane filter, preregistration, registry) that reaches the compiler,
     the docket and the canonical gauntlet. Trial counts are the judge's; this adds none of its
     own and charges none.

NEVER: a second family, a second gauntlet, a performance pre-screen, or a cap on what the miners
produce. Calendar rules, not feeds; no network.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

SOURCE = "calendar_flow"
FAMILY = "forced_flow"
OUT = BASE / "reports" / "CALENDAR_FLOW_CELLS.json"
STATE = BASE / "data" / "calendar_flow_cells_state.json"
UNIVERSE_DIR = BASE / "data" / "universe"
UNMEASURED = "UNMEASURED"

#: The sealed gauntlet's floor (a daily series under 60 days is dropped before any gate) plus the
#: same 10% margin `cross_sectional_breadth` carries for a trimmed last day and a refused entry.
FIRE_FLOOR = 60
SEED_FLOOR = 66

MODES = ("pre_flow", "post_flow_fade")
POLARITIES = (1, -1)
#: Charts the windows are meaningful on. Every forced-flow window is minutes to hours wide; a D1
#: or H4 bar cannot sit inside one, so those charts would test the fallback, not the mechanism.
CHARTS = ("M15", "H1")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def identity(symbol: str, params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({"s": symbol, "f": FAMILY, "p": params}, sort_keys=True,
                                     default=str).encode()).hexdigest()[:20]


def _calendar() -> Any:
    from research import forced_flow_calendar
    return forced_flow_calendar


def kind_instruments(lo: date, hi: date) -> dict[str, tuple[str, ...]]:
    """kind -> every instrument the calendar names for it over [lo, hi], in first-seen order."""
    cal = _calendar()
    out: dict[str, dict[str, None]] = {k: {} for k in cal.KINDS}
    for e in cal.events(lo, hi):
        for s in e.instruments:
            out.setdefault(e.kind, {})[s] = None
    return {k: tuple(v) for k, v in out.items()}


def grid(kind: str) -> list[dict[str, Any]]:
    """The preregistered call params for one kind. Fixed here; never tuned on returns."""
    return [{"event_kind": kind, "mode": m, "side": s, "clock": "utc"}
            for m in MODES for s in POLARITIES]


def _bars(symbol: str, chart: str) -> pd.DataFrame | None:
    path = UNIVERSE_DIR / f"{symbol}_{chart}.parquet"
    if not path.exists():
        return None
    try:
        from mt5desk.families import _h1
        return _h1(pd.read_parquet(path))
    except Exception:
        return None


def firing(sigs: list, d: pd.DataFrame) -> dict[str, int]:
    """Distinct signal days and the lower bound on trade days -- one shared definition."""
    from research.cross_sectional_breadth import firing as xs_firing
    return xs_firing(sigs, d)


def _cached_windows() -> None:
    """One calendar computation per (kind, span) in this process, not one per cell.

    `family_forced_flow` recomputes the whole rule calendar on every call when the artifact does
    not cover the bars' span. The windows are a pure function of (kind, lo, hi), so caching them
    here changes no signal and turns a per-cell cost into a per-kind one.
    """
    from mt5desk import family_forced_flow as fff
    if getattr(fff.calendar_windows, "cache_info", None) is None:
        fff.calendar_windows = lru_cache(maxsize=512)(fff.calendar_windows)


def _load_state() -> dict[str, Any]:
    doc = _read(STATE)
    return doc if isinstance(doc, dict) and isinstance(doc.get("cells"), dict) else {"cells": {}}


def _save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True), "utf-8")
    tmp.replace(STATE)


def _event_text(lo: date, hi: date) -> dict[str, tuple[str, str]]:
    """kind -> (forced actor, mechanism) from the calendar's own first row of that kind."""
    out: dict[str, tuple[str, str]] = {}
    for e in _calendar().events(lo, hi):
        out.setdefault(e.kind, (e.forced_actor, e.mechanism))
    return out


def seed(*, budget_s: float = 900.0, dry_run: bool = False, kinds: list[str] | None = None,
         today: date | None = None) -> dict[str, Any]:
    """Measure firing over the preregistered grid and donate every cell that clears the floor."""
    started = time.monotonic()
    anchor = today or datetime.now(tz=UTC).date()
    stamp = anchor.isoformat()
    lo, hi = anchor - timedelta(days=400), anchor + timedelta(days=60)
    try:
        targets = kind_instruments(lo, hi)
        text = _event_text(lo, hi)
        from mt5desk.family_forced_flow import family_forced_flow
    except Exception as exc:
        return {"status": UNMEASURED, "why": f"calendar unreadable: {type(exc).__name__}: {exc}"}
    _cached_windows()
    from mt5desk.family_call import signals as call_signals

    state = _load_state()
    cells: dict[str, Any] = state["cells"]
    by_kind: dict[str, Counter] = {}
    cands: list[dict[str, Any]] = []
    no_bars: set[str] = set()
    errors: Counter = Counter()
    stopped = "grid exhausted"
    bars_cache: dict[tuple[str, str], pd.DataFrame | None] = {}
    for kind, symbols in sorted(targets.items()):
        if kinds and kind not in kinds:
            continue
        row = by_kind.setdefault(kind, Counter())
        row["instruments"] = len(symbols)
        if not symbols:
            row["no_instrument_in_lane"] = 1
            continue
        for sym in symbols:
            if time.monotonic() - started > budget_s:
                stopped = f"time budget {budget_s:g}s reached; resumes next pass"
                break
            for chart in CHARTS:
                key = (sym, chart)
                for call in grid(kind):
                    params = dict(call) if chart == "H1" else {**call, "timeframe": chart}
                    ident = identity(sym, params)
                    prior = cells.get(ident) or {}
                    row["grid"] += 1
                    if prior.get("day") != stamp:
                        if key not in bars_cache:
                            bars_cache[key] = _bars(sym, chart)
                        d = bars_cache[key]
                        if d is None:
                            no_bars.add(f"{sym}_{chart}")
                            row["no_bars"] += 1
                            continue
                        side = int(call["side"])
                        kw = {k: v for k, v in call.items() if k != "side"}
                        try:
                            sigs = call_signals(family_forced_flow, d, side=side,
                                                params={**kw, "symbol": sym})
                            got = firing(sigs, d)
                        except Exception as exc:
                            errors[f"{kind}: {type(exc).__name__}"] += 1
                            continue
                        prior = {**prior, **got, "day": stamp, "symbol": sym, "kind": kind,
                                 "params": params}
                        cells[ident] = prior
                        row["measured_this_pass"] += 1
                    ok = int(prior.get("trade_days_lb") or 0) >= SEED_FLOOR
                    row["clears_floor" if ok else "observation_scarce"] += 1
                    if ok and not prior.get("donated_at"):
                        cands.append({"ident": ident, "symbol": sym, "kind": kind,
                                      "params": params,
                                      "firing": {k: prior.get(k) for k in
                                                 ("signal_days", "trade_days_lb")}})
                bars_cache.pop(key, None)
            else:
                continue
            break
        else:
            continue
        break

    donated = 0
    donation: dict[str, Any] = {"status": "DRY_RUN" if dry_run else "NOTHING_NEW"}
    if cands and not dry_run:
        from research import proposer_common as pc
        rows = []
        for c in cands:
            actor, mech = text.get(c["kind"], ("", ""))
            p = c["params"]
            rows.append(pc.candidate(
                SOURCE, c["symbol"], FAMILY, {**p, "symbol": c["symbol"]},
                f"{c['kind']}: {actor}. {mech}",
                f"{c['symbol']} forced_flow {c['kind']} {p['mode']} "
                f"{'+' if p['side'] > 0 else '-'}{' ' + p['timeframe'] if 'timeframe' in p else ''}",
                {"firing": c["firing"], "seed_floor": SEED_FLOOR, "gauntlet_floor": FIRE_FLOOR,
                 "calendar_kind": c["kind"], "clock": "utc",
                 "preregistered_grid": "kind x mode x polarity, fixed in calendar_flow_cells.py"}))
        path = pc.donate(SOURCE, rows, len(rows))
        counts = pc.donation_counts()
        donated = int(counts.get("donated") or 0)
        donation = {"status": "DONATED" if path else "REFUSED_AT_DOOR",
                    "path": str(path) if path else None,
                    "refused_wrong_lane": counts.get("refused_wrong_lane"),
                    "refused_unstamped": counts.get("refused_unstamped")}
        if path:
            at = _now()
            for c in cands:
                cells[c["ident"]]["donated_at"] = at
                by_kind[c["kind"]]["donated_this_pass"] += 1
    if not dry_run:
        _save_state(state)
    seeded = Counter(str(v.get("kind")) for v in cells.values() if v.get("donated_at"))
    for kind, cnt in by_kind.items():
        cnt["donated_total"] = seeded.get(kind, 0)
    return {
        "status": "OK", "dry_run": bool(dry_run), "stopped_because": stopped,
        "elapsed_s": round(time.monotonic() - started, 2),
        "seed_floor_trade_days": SEED_FLOOR, "gauntlet_floor_days": FIRE_FLOOR,
        "cells_by_kind": {k: dict(v) for k, v in sorted(by_kind.items())},
        "candidates_this_pass": len(cands), "donated_this_pass": donated,
        "donation": donation, "charts_without_bars": sorted(no_bars)[:200],
        "errors": dict(errors),
    }


def run(*, budget_s: float = 900.0, dry_run: bool = False, kinds: list[str] | None = None,
        out: Path | None = None) -> dict[str, Any]:
    doc = {"generated_at": _now(), "producer": "desks/mt5/research/calendar_flow_cells.py",
           "family": FAMILY, "source": SOURCE,
           "rule": ("every dated forced-flow kind on the instruments the calendar names for it, "
                    "kind x mode x polarity on the UTC clock; held back only when its firing "
                    "cannot reach the gauntlet's 60-day floor (observation-scarce, named), "
                    "never on returns"),
           "seeding": seed(budget_s=budget_s, dry_run=dry_run, kinds=kinds)}
    path = out or OUT
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(path)
    except OSError as exc:
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--dry-run", action="store_true", help="measure and report, donate nothing")
    ap.add_argument("--kinds", nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = run(budget_s=args.budget_s, dry_run=args.dry_run, kinds=args.kinds, out=args.out)
    s = doc["seeding"]
    print(f"calendar_flow_cells: {s.get('status')} candidates={s.get('candidates_this_pass')} "
          f"donated={s.get('donated_this_pass')} stopped={s.get('stopped_because')!r} "
          f"elapsed={s.get('elapsed_s')}s -> {args.out or OUT}")
    for kind, c in (s.get("cells_by_kind") or {}).items():
        print(f"  {kind:22} instruments={c.get('instruments', 0):3} grid={c.get('grid', 0):5} "
              f"clears={c.get('clears_floor', 0):5} scarce={c.get('observation_scarce', 0):5} "
              f"no_bars={c.get('no_bars', 0):5}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
