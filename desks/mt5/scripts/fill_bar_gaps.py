#!/usr/bin/env python3
"""THE GAP THAT NO CLOCK COULD CLOSE -- fill a missing (symbol, timeframe), or name why not.

WHAT WAS BROKEN, MEASURED 2026-09-24 ON THE TRADING BOX. 248 instruments hold bars across seven
charts and 233 hold all seven. The other fifteen carried a hole -- twelve with no M1 and no M5,
three with no H4 -- and NOTHING ON ANY CLOCK COULD EVER FILL ONE. The hourly leg `refresh_bars`
runs `scripts/refresh_tail.py`, which globs the parquets that ALREADY EXIST and returns
`no-cache` for a file that does not, so it extends coverage it already has and can never create
a chart. `expand_universe.py` can create one and is on no clock at all. A gap therefore stayed a
gap for as long as nobody ran a script by hand, which is the definition of unwired (III.16).

THIS ORGAN IS THAT MISSING HALF, and it is deliberately small: it fills HOLES and never touches
a chart that exists. `refresh_tail` keeps its job of extending the tail; this one creates the
file `refresh_tail` needs in order to have a job.

EVERY CELL LEAVES A NAMED VERDICT, WHICH IS THE POINT AS MUCH AS THE FETCH. A hole has several
causes and they are not interchangeable:

    FILLED                the broker served the chart and it is now on disk
    BELOW_FLOOR           the broker served N bars and the gates want M; recorded WITH BOTH
                          numbers, because "the broker keeps less M1 than H1" is a real fact
                          about venues and must not read the same as a failed download
    BROKER_SERVES_NOTHING the symbol is offered and this chart comes back empty
    NOT_OFFERED           `symbol_info` is None: the venue does not quote this symbol at all.
                          This is a DELISTING and the registry row is stale, not a coverage gap
    NO_SUCH_TIMEFRAME     the terminal has no constant for this chart
    UNMEASURED            the terminal could not be reached; NEVER a zero and never a skip

A verdict is a MEASUREMENT with a timestamp, so `scripts/check_bar_coverage_ratchet.py` can
tell a cell the broker will never serve from a cell nobody has asked about -- and only the
second is a defect.

NOTHING IS EVER DELETED AND NOTHING SHRINKS. It writes parquets and one verdict file, both
under `desks/mt5/data/`, and removes nothing under any circumstance.

    python desks/mt5/scripts/fill_bar_gaps.py                 # bounded pass (the clocked shape)
    python desks/mt5/scripts/fill_bar_gaps.py --all           # every gap, one shot
    python desks/mt5/scripts/fill_bar_gaps.py --dry-run       # measure and print, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = DESK / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
VERDICTS = DESK / "data" / "bar_coverage_verdicts.json"
REPORT = DESK / "reports" / "BAR_GAP_FILL.json"

#: Cells attempted in one bounded pass. An M1 chart is four chunked round trips to the venue and
#: this organ shares the hour with everything else on the organ battery; twenty-seven gap cells
#: close in a handful of passes. `--all` is there for the one-shot.
MAX_CELLS = 6
BUDGET_S = 600.0
#: A cell whose verdict is settled -- the venue does not quote it, or the chart does not exist --
#: is re-asked no more often than this. A delisting does not un-delist hourly, and re-asking is
#: not free. A BELOW_FLOOR cell is re-asked every pass: a venue's history GROWS.
SETTLED_RETRY_S = 7 * 24 * 3600

FILLED, BELOW_FLOOR, NOTHING, NOT_OFFERED, NO_TF, UNMEASURED = (
    "FILLED", "BELOW_FLOOR", "BROKER_SERVES_NOTHING", "NOT_OFFERED", "NO_SUCH_TIMEFRAME",
    "UNMEASURED")
#: Verdicts that do not change on their own. Everything else is re-asked on every pass -- a
#: venue's history GROWS, so a BELOW_FLOOR cell is asked again and may fill later.
SETTLED = frozenset({NOT_OFFERED, NO_TF})


def _now() -> datetime:
    return datetime.now(UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8-sig", errors="replace"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def timeframes() -> tuple[str, ...]:
    """The canonical ladder, from the registry that owns it. NEVER a literal here.

    Four spellings of this ladder exist in the tree with different depths; a fifth written here
    would be a fifth thing to drift. `mt5desk.universe_registry` is the one the whole-broker
    fetcher imports, so it is the one this measures against.
    """
    from mt5desk.universe_registry import TIMEFRAMES
    return tuple(TIMEFRAMES)


def coverage(root: Path | None = None) -> dict[str, set[str]]:
    """Symbol -> the charts on disk for it. The denominator is what the venue has given us."""
    base = root or UNIVERSE
    have: dict[str, set[str]] = defaultdict(set)
    ladder = "|".join(timeframes())
    pattern = re.compile(rf"^(.*)_({ladder})$")
    for path in base.glob("*.parquet"):
        got = pattern.match(path.stem)
        if got:
            have[got.group(1)].add(got.group(2))
    return dict(have)


def gaps(root: Path | None = None) -> list[tuple[str, str]]:
    """Every (symbol, chart) cell the desk does not hold, for a symbol it holds SOMETHING for.

    A symbol with no chart at all is NOT a gap row here: it is either a delisting or a symbol
    never collected, and both are the registry's business rather than a tail to fill. It is
    reported separately so it cannot be silently dropped.
    """
    ladder = timeframes()
    have = coverage(root)
    out = [(sym, tf) for sym in sorted(have) for tf in ladder if tf not in have[sym]]
    return out


def undeclared(root: Path | None = None) -> list[str]:
    """Registry rows holding no chart at all -- named, never silently dropped."""
    reg = _read_json((root or UNIVERSE) / "universe.json")
    if not isinstance(reg, dict):
        return []
    return sorted(set(reg) - set(coverage(root)))


def _terminal() -> tuple[Any, str]:
    try:
        import MetaTrader5 as mt5
    except Exception as exc:                             # pragma: no cover - box-only import
        return None, f"MetaTrader5 is not importable on this host: {type(exc).__name__}: {exc}"
    if not mt5.initialize():
        return None, f"MetaTrader5.initialize() failed: {mt5.last_error()}"
    return mt5, ""


def _prior(now: datetime) -> dict[str, dict[str, Any]]:
    doc = _read_json(VERDICTS)
    rows = doc.get("cells") if isinstance(doc, dict) else None
    return {str(k): v for k, v in rows.items() if isinstance(v, dict)} if isinstance(
        rows, dict) else {}


def _settled(row: dict[str, Any], now: datetime) -> bool:
    """Has this cell a verdict that does not change on its own, asked recently enough?"""
    if str(row.get("verdict")) not in SETTLED:
        return False
    try:
        when = datetime.fromisoformat(str(row.get("at")).replace("Z", "+00:00"))
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return (now - when) < timedelta(seconds=SETTLED_RETRY_S)


def fill(*, max_cells: int = MAX_CELLS, budget_s: float = BUDGET_S, write: bool = True,
         every: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """One bounded pass. Never raises: an unreachable terminal is a verdict, not a crash."""
    started = time.monotonic()
    stamp = now or _now()
    ladder = timeframes()
    cells = gaps()
    orphans = undeclared()
    prior = _prior(stamp)
    mt5, why_no_terminal = _terminal()
    out: dict[str, Any] = {
        "at": stamp.isoformat(timespec="seconds"),
        "host": os.environ.get("COMPUTERNAME") or "unknown",
        "ladder": list(ladder),
        "n_symbols": len(coverage()),
        "n_gap_cells": len(cells),
        "registry_rows_with_no_chart": orphans,
        "attempted": 0, "filled": 0, "results": [],
        "law": ("a gap is FILLED or it carries a NAMED verdict with the numbers behind it; "
                "nothing is deleted and no chart already on disk is touched"),
    }
    if mt5 is None:
        out["status"] = UNMEASURED
        out["why"] = why_no_terminal
        # EVERY CELL STAYS UNMEASURED RATHER THAN BECOMING A ZERO. A host with no terminal has
        # not learned that the broker serves nothing; it has learned nothing at all.
        if write:
            _atomic(REPORT, out)
        return out

    try:
        import pandas as pd
        from research.expand_universe import (  # type: ignore[import-not-found]
            _pull_bars,
            min_bars,
        )
        verdicts = dict(prior)
        start = datetime(2015, 1, 1, tzinfo=UTC)
        for sym, tf in cells:
            key = f"{sym}_{tf}"
            if not every and (out["attempted"] >= max_cells
                              or time.monotonic() - started > budget_s):
                out["results"].append({"cell": key, "verdict": "DEFERRED",
                                       "why": "pass budget reached; the next pass takes it "
                                              "first (a queue, not a drop)"})
                continue
            if _settled(verdicts.get(key) or {}, stamp):
                out["results"].append({"cell": key, "verdict": "NOT_DUE",
                                       "why": f"settled verdict "
                                              f"{verdicts[key].get('verdict')} asked within "
                                              f"{SETTLED_RETRY_S // 3600}h"})
                continue
            out["attempted"] += 1
            row = _one(mt5, pd, _pull_bars, min_bars, sym, tf, start, stamp, write=write)
            verdicts[key] = row
            out["results"].append({"cell": key, **row})
            if row["verdict"] == FILLED:
                out["filled"] += 1
        # A REGISTRY ROW HOLDING NO CHART AT ALL IS ALSO A CELL THAT NEEDS AN ANSWER, and
        # listing the names without asking the venue about them was the old shape of leaving
        # them silently. Asked at the SYMBOL level, because "no chart at all" is a fact about
        # the symbol; a row the venue does quote gets a per-chart answer next pass, once its
        # first chart lands and it becomes a gap row like any other.
        out["symbols"] = []
        for sym in orphans:
            key = f"{sym}_*"
            if _settled(verdicts.get(key) or {}, stamp):
                out["symbols"].append({"symbol": sym, "verdict": "NOT_DUE",
                                       "why": str((verdicts.get(key) or {}).get("why") or "")})
                continue
            info = mt5.symbol_info(sym)
            row = ({"verdict": NOT_OFFERED, "at": stamp.isoformat(timespec="seconds"), "bars": 0,
                    "why": (f"the venue does not quote {sym} at all (symbol_info is None), so it "
                            f"holds no chart on any timeframe and never will. This is a DELISTED "
                            f"registry row, not a coverage gap: there is nothing to fetch, and "
                            f"the right repair is the registry's delisting stamp, not a "
                            f"download. It must not sit in a coverage denominator as a hole.")}
                   if info is None else
                   {"verdict": "QUOTED_NO_CHART", "at": stamp.isoformat(timespec="seconds"),
                    "bars": 0,
                    "why": (f"the venue quotes {sym} and the desk holds no chart for it on any "
                            f"timeframe: a real collection gap, and the next pass takes its "
                            f"charts one at a time")})
            verdicts[key] = row
            out["symbols"].append({"symbol": sym, **row})
        out["status"] = "present"
        counts: dict[str, int] = defaultdict(int)
        for row in verdicts.values():
            counts[str(row.get("verdict"))] += 1
        out["verdict_counts"] = dict(counts)
        if write:
            _atomic(VERDICTS, {
                "at": stamp.isoformat(timespec="seconds"),
                "host": out["host"],
                "rule": ("one row per (symbol, chart) cell the desk does not hold, with what the "
                         "VENUE said when asked and when it was asked. A cell the broker will "
                         "not serve is a measured fact; a cell nobody asked about is a defect. "
                         "The ratchet fence reads this to tell them apart."),
                "cells": verdicts})
            _atomic(REPORT, out)
    finally:
        with_shutdown = getattr(mt5, "shutdown", None)
        if callable(with_shutdown):
            with_shutdown()
    out["elapsed_s"] = round(time.monotonic() - started, 2)
    return out


def _one(mt5: Any, pd: Any, pull: Any, floor_for: Any, sym: str, tf: str,
         start: datetime, stamp: datetime, *, write: bool) -> dict[str, Any]:
    """One cell, one verdict, with the numbers that produced it."""
    at = stamp.isoformat(timespec="seconds")
    info = mt5.symbol_info(sym)
    if info is None:
        return {"verdict": NOT_OFFERED, "at": at, "bars": 0,
                "why": (f"the venue does not quote {sym} at all (symbol_info is None): this is "
                        f"a DELISTED registry row, not a coverage gap, and no chart for it will "
                        f"ever exist")}
    code = getattr(mt5, f"TIMEFRAME_{tf}", None)
    if code is None:
        return {"verdict": NO_TF, "at": at, "bars": 0,
                "why": f"this terminal has no TIMEFRAME_{tf} constant"}
    mt5.symbol_select(sym, True)
    want = _want(tf)
    rates = pull(mt5, sym, code, want, start, stamp)
    n = 0 if rates is None else len(rates)
    gates_floor = int(floor_for(tf))
    peer, peer_n = peer_floor(tf)
    floor, basis = _admission(gates_floor, peer, peer_n)
    if n == 0:
        return {"verdict": NOTHING, "at": at, "bars": 0, "floor": floor,
                "why": (f"{sym} is quoted and its {tf} chart came back empty "
                        f"(last_error {mt5.last_error()})")}
    if n < floor:
        return {"verdict": BELOW_FLOOR, "at": at, "bars": int(n), "floor": floor,
                "gates_floor": gates_floor, "peer_floor": peer, "peer_n": peer_n, "wanted": want,
                "why": (f"the venue served {n} {tf} bars against an admission floor of {floor} "
                        f"({basis}). This is a measured venue limit on this symbol, not a failed "
                        f"fetch: its peers on the same chart hold more")}
    if not write:
        return {"verdict": "WOULD_FILL", "at": at, "bars": int(n), "floor": floor}
    frame = pd.DataFrame(rates)
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    frame = frame.set_index("time").sort_index()
    try:
        frame.to_parquet(UNIVERSE / f"{sym}_{tf}.parquet")
    except Exception as exc:                             # pragma: no cover - disk-level failure
        return {"verdict": UNMEASURED, "at": at, "bars": int(n), "floor": floor,
                "why": f"the venue served {n} bars and the write failed: "
                       f"{type(exc).__name__}: {exc}"}
    return {"verdict": FILLED, "at": at, "bars": int(n), "floor": floor,
            "gates_floor": gates_floor, "peer_floor": peer, "peer_n": peer_n,
            "span_start": str(frame.index[0]), "span_end": str(frame.index[-1]),
            "why": f"the venue served {n} {tf} bars against an admission floor of "
                   f"{floor} ({basis})"}


def _admission(gates_floor: int, peer: int | None, peer_n: int) -> tuple[int, str]:
    """THE FLOOR A NEW CHART MUST CLEAR, AND WHY IT IS NOT ALWAYS THE GATES' FLOOR.

    MEASURED ON THE TRADING BOX 2026-09-24, and this is the whole argument. `min_bars("M1")` is
    180,000 -- the same market time as the H1 floor, which is the right idea. The venue serves
    about 100,000 M1 bars for EVERY symbol: the 236 M1 charts already on this disk hold 100,779
    to 102,920 bars, so NOT ONE of them meets that floor either. They are there because a
    different collector wrote them under a different floor.

    Refusing to write a 100,000-bar M1 chart while 236 charts of exactly that depth sit beside
    it is not rigour, it is an inconsistency that leaves twelve instruments dark for a rule the
    rest of the universe never passed. So the admission floor is the LOWER of the gates' floor
    and what the symbol's PEERS on the same chart actually hold -- and both numbers travel on
    the verdict, so nothing is hidden and the gates' floor is never restated as met.

    THIS LOWERS NO STATISTICAL BAR. `desks/mt5/policy/gate_spec.yaml` is untouched; a chart too
    short for a test is still refused BY THAT TEST at judgement time. This is the COLLECTION
    admission floor, and the only thing it changes is that the desk now holds data it was
    throwing away. With no peers to compare against, the gates' floor stands unchanged.
    """
    if peer is None or peer_n < 8:
        return gates_floor, (f"the gates' floor for this chart; too few peers ({peer_n}) to "
                             f"measure what the venue actually serves")
    if peer >= gates_floor:
        return gates_floor, "the gates' floor for this chart, which its peers also clear"
    # PEER_FRAC of the peer MEDIAN, borrowed from `scripts/check_bar_history_floor.py` so this
    # desk has ONE idea of "really short" and not two. A quarter of the median is the shape of
    # AUDNZD's twenty days beside its peers' eight years; it is not the shape of 100,000 bars
    # beside a thinnest peer of 100,779, and a floor set at that thinnest peer would refuse a
    # chart for being 0.8% behind -- a floor that fires on noise gets deleted, which is worse
    # than no floor at all.
    from check_bar_history_floor import (  # type: ignore[import-not-found]
        PEER_FRAC,
    )
    cut = int(peer * PEER_FRAC)
    return cut, (f"PEER PARITY: the gates want {gates_floor} and not one of the {peer_n} charts "
                 f"the desk already holds on this timeframe reaches it (median {peer}); a new "
                 f"chart is admitted at {PEER_FRAC:.0%} of that median, the same cut "
                 f"check_bar_history_floor uses to call a chart genuinely stumped")


#: Per-pass cache: reading 248 parquet footers once is cheap, 27 times is not.
_PEER_CACHE: dict[str, tuple[int | None, int]] = {}


def peer_floor(tf: str) -> tuple[int | None, int]:
    """(median bar count across the charts the desk already holds at `tf`, how many there are).

    Read from the parquet FOOTER -- `num_rows` costs a seek, not a load of a 100,000-row frame.
    """
    if tf in _PEER_CACHE:
        return _PEER_CACHE[tf]
    counts: list[int] = []
    try:
        import pyarrow.parquet as pq
        for path in UNIVERSE.glob(f"*_{tf}.parquet"):
            try:
                meta = pq.ParquetFile(path).metadata  # type: ignore[no-untyped-call]
                counts.append(int(meta.num_rows))
            except Exception:                            # pragma: no cover - one unreadable file
                continue
    except Exception:                                    # pragma: no cover - optional dependency
        _PEER_CACHE[tf] = (None, 0)
        return _PEER_CACHE[tf]
    if not counts:
        _PEER_CACHE[tf] = (None, 0)
        return _PEER_CACHE[tf]
    counts.sort()
    _PEER_CACHE[tf] = (counts[len(counts) // 2], len(counts))
    return _PEER_CACHE[tf]


def _want(tf: str) -> int:
    from research.expand_universe import _want_bars
    return int(_want_bars(tf))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=str(__doc__ or "").split("\n")[0])
    ap.add_argument("--max-cells", type=int, default=MAX_CELLS)
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--all", action="store_true", help="every gap cell, ignoring the pass cap")
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    a = ap.parse_args(argv)
    got = fill(max_cells=a.max_cells, budget_s=a.budget_s, write=not a.dry_run, every=a.all)
    print(f"fill_bar_gaps {got['at']} on {got['host']}: {got.get('status')} "
          f"-- {got['n_gap_cells']} gap cell(s) over {got['n_symbols']} symbol(s)")
    if got.get("why"):
        print(f"  {got['why']}")
    for row in got["results"][:40]:
        print(f"  {row['cell']:<20} {row['verdict']:<22} {str(row.get('why') or '')[:90]}")
    for row in got.get("symbols") or []:
        print(f"  {row['symbol']:<20} {row['verdict']:<22} {str(row.get('why') or '')[:90]}")
    print(f"  filled {got['filled']} of {got['attempted']} attempted; "
          f"verdicts {got.get('verdict_counts')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
