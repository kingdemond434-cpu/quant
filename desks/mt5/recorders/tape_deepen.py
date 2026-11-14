"""Deepen the Fusion tick tape BACKWARDS from the terminal's own tick store (CopyTicks).

    py -3 -m recorders.tape_deepen --budget-s 300       # one bounded pass (the hourly leg)
    py -3 -m recorders.tape_deepen --budget-s 0         # run until every symbol is exhausted
    py -3 -m recorders.tape_deepen --dry-run            # the plan only; no terminal call

WHY. The tape-input families (cumulative delta, order-flow imbalance, thin-level sweeps) wait on
66 recorded days per symbol, and the forward writers (`mt5desk/tape.py`, `recorders/
tick_recorder.py`, `moat/moat_recorder.py`) only ever add the day that is happening now. But the
Fusion terminal already HOLDS weeks or months of its own broker's ticks behind the first day this
desk recorded, and `copy_ticks_range` serves them. Every day of that store we copy is a day the
bar arrives sooner, from the venue we actually trade, at the venue's own quotes. It is the lawful
replacement for the Dukascopy backfill, whose terms refuse automated download (#891, closed).

WHAT IT DOES, PER SYMBOL. It keeps a FLOOR -- the deepest broker day it has asked about -- and
walks one day below it per step: ask the terminal for that day's ticks, write them through
`mt5desk.tape.write_day` into `data/tape/ticks/<SYM>/<YYYY-MM-DD>.parquet` (the forward writer's
own file, merge and dedupe, so the two writers and `tape_days` see one tape), and lower the floor.
A day already on disk, or already shipped off the box by `scripts/archive_tape.py` (read from its
manifest), is stepped over and never re-fetched.

WHEN IT STOPS, AND WHY THAT STOP IS CHECKED TWICE. The terminal's store ends somewhere, and the
only evidence of the end is silence: EMPTY_RUN_DAYS consecutive empty calendar days (two weeks
clears every exchange holiday cluster). But MT5 serves history it is still synchronising from the
trade server as an empty answer, so silence on ONE pass is not proof. A run of empty days is
marked `pending_confirm` and the whole window is asked for again on the NEXT pass; only a second
empty answer marks the symbol exhausted. Ticks on the re-ask are written and the walk goes on.

WHAT IT NEVER DOES. It never deletes or rewrites a tick that is already recorded (`write_day` is a
union), never attaches to any terminal but the desk's Fusion one (`mt5_session.venue_refusal`, the
same pin the recorders use -- an FTMO quote filed under a Fusion symbol is worse than no quote),
never launches a terminal from Session 0 (`attach_or_initialize`), and never writes below the disk
floor: it PAUSES and says so. It imports nothing from the money path.

ORDER. Symbols nearest the 66-day bar go first (they unlock cells soonest), then the rest from the
shallowest. Each symbol gets DAYS_PER_TURN days per turn, round robin, until the budget is spent,
so no one deep symbol starves the universe.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_DESK = _HERE.parent
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import tape  # noqa: E402

TICKS = tape.TICKS
STATE = tape.TAPE / "deepen_state.json"
ARCHIVE_MANIFEST = tape.TAPE / "ARCHIVE_MANIFEST.jsonl"
REPORT = _DESK / "reports" / "TAPE_DEEPEN.json"
UNIVERSE = tape.DATA / "universe" / "universe.json"

#: The day count the tape-input families wait for (tape_days / the tick-moat bar).
SEED_BAR = 66
#: Consecutive empty calendar days that END a walk (after a second, confirming ask).
EMPTY_RUN_DAYS = 14
#: Days one symbol gets per round-robin turn.
DAYS_PER_TURN = 7
#: The deepest any walk goes, in calendar days below today. The terminal's own store is the real
#: limit; this only stops a walk on a symbol that answers forever.
MAX_DEPTH_DAYS = int(os.environ.get("TAPE_DEEPEN_MAX_DEPTH_DAYS", "3650"))
#: Below this much free disk the pass pauses. It never prunes.
DISK_FLOOR_GB = float(os.environ.get("TAPE_DEEPEN_DISK_FLOOR_GB", "15"))
#: Ticks per terminal call; a fuller answer is drained from its last stamp.
PULL_CAP = 2_000_000
DAY_MS = 86_400_000

STATUS_OK = "OK"
STATUS_BUDGET = "BUDGET_SPENT"
STATUS_DISK = "DISK_FLOOR"
STATUS_VENUE = "WRONG_VENUE"
STATUS_NO_TERMINAL = "NO_TERMINAL"
STATUS_DONE = "ALL_EXHAUSTED"


class TickHistory(Protocol):
    """The one call this organ makes: a broker-clock window of ticks, or None on failure."""

    def ticks(self, symbol: str, start_ms: int, end_ms: int) -> np.ndarray | None: ...


class Mt5History:
    """`copy_ticks_range` on the pinned Fusion terminal. Bounds are on the broker clock, which is
    how the terminal compares them with `time_msc` (see `mt5desk.tape.record_ticks`)."""

    def __init__(self, mt5: Any) -> None:
        self.mt5 = mt5
        self._selected: set[str] = set()

    def ticks(self, symbol: str, start_ms: int, end_ms: int) -> np.ndarray | None:
        mt5 = self.mt5
        if symbol not in self._selected:
            try:
                mt5.symbol_select(symbol, True)
            except Exception:
                pass
            self._selected.add(symbol)
        try:
            got = mt5.copy_ticks_range(symbol, datetime.fromtimestamp(start_ms / 1000, tz=UTC),
                                       datetime.fromtimestamp(end_ms / 1000, tz=UTC),
                                       mt5.COPY_TICKS_ALL)
        except Exception:
            return None
        return got


def _iso(d: date) -> str:
    return d.isoformat()


def _day(s: str) -> date:
    return date.fromisoformat(s)


def archived_days(manifest: Path = ARCHIVE_MANIFEST) -> dict[str, set[str]]:
    """{symbol: {ISO day}} shipped off the box by archive_tape: recorded, so never re-fetched."""
    out: dict[str, set[str]] = {}
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        sym, day = row.get("symbol"), str(row.get("day") or "")
        if len(day) == 8 and day.isdigit():
            day = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        if isinstance(sym, str) and len(day) == 10:
            out.setdefault(sym, set()).add(day)
    return out


def present_days(symbol: str, archived: dict[str, set[str]], root: Path = TICKS) -> set[str]:
    """Every broker day this desk holds for `symbol`, on the box or archived, in either name."""
    return {d for d, _ in tape.day_files(symbol, root)} | archived.get(symbol, set())


def _frame(arr: np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame(arr)
    df["ts"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
    return df.sort_values("time_msc", kind="stable")


def fetch_window(src: TickHistory, symbol: str, start_ms: int, end_ms: int
                 ) -> pd.DataFrame | None:
    """Every tick in [start_ms, end_ms), drained past PULL_CAP. None when the terminal failed."""
    parts: list[pd.DataFrame] = []
    cur = start_ms
    while True:
        arr = src.ticks(symbol, cur, end_ms)
        if arr is None:
            return None
        if len(arr) == 0:
            break
        df = _frame(arr)
        df = df[(df["time_msc"] >= start_ms) & (df["time_msc"] < end_ms)]
        parts.append(df)
        if len(arr) < PULL_CAP or df.empty:
            break
        top = int(df["time_msc"].max())
        if top <= cur:
            break
        cur = top                       # the overlap re-reads `top`; write_day dedupes it
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def write_days(symbol: str, df: pd.DataFrame, root: Path = TICKS) -> dict[str, int]:
    """Write a window's ticks into their broker-day files. {day: ticks written}."""
    out: dict[str, int] = {}
    if df.empty:
        return out
    for day, chunk in df.groupby(df["ts"].dt.date):
        tape.write_day(chunk, root / symbol / f"{day.isoformat()}.parquet")
        out[day.isoformat()] = int(len(chunk))
    return out


def _start_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def order(symbols: Iterable[str], days_on_disk: dict[str, int]) -> list[str]:
    """Nearest the bar first (they unlock cells soonest), then the rest from the shallowest."""
    def key(s: str) -> tuple[int, int, str]:
        n = days_on_disk.get(s, 0)
        return (0, SEED_BAR - n, s) if n < SEED_BAR else (1, n, s)
    return sorted(symbols, key=key)


def _free_gb(root: Path) -> float | None:
    probe = root
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return shutil.disk_usage(str(probe)).free / 1e9
    except OSError:
        return None


def _load_state(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def deepen(src: TickHistory, symbols: list[str], *, budget_s: float, today: date,
           root: Path = TICKS, state_path: Path = STATE,
           manifest: Path = ARCHIVE_MANIFEST,
           free_gb: Callable[[Path], float | None] = _free_gb,
           clock: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """One bounded pass. Returns the report; writes the state after every symbol turn."""
    t0 = clock()
    deadline = t0 + budget_s if budget_s > 0 else float("inf")
    archived = archived_days(manifest)
    state = _load_state(state_path)
    syms = state.setdefault("symbols", {})
    deepest = today - timedelta(days=MAX_DEPTH_DAYS)

    held: dict[str, set[str]] = {s: present_days(s, archived, root) for s in symbols}
    start_count = {s: len(held[s]) for s in symbols}
    added: dict[str, int] = dict.fromkeys(symbols, 0)
    ticks_added = 0
    errors: dict[str, int] = {}
    status = STATUS_OK

    for s in symbols:
        st = syms.setdefault(s, {})
        floor = st.get("floor")
        earliest = min(held[s]) if held[s] else None
        if not floor:
            floor = earliest or _iso(today)
        elif earliest and earliest < floor:
            floor = earliest
        st["floor"] = floor
        st.setdefault("empty_run", 0)
        st.setdefault("exhausted", False)

    def live() -> list[str]:
        return [s for s in symbols if not syms[s]["exhausted"]]

    def step(s: str) -> bool:
        """One day (or one confirming re-ask) for `s`. False when this symbol is done for now."""
        nonlocal ticks_added
        st = syms[s]
        floor = _day(st["floor"])
        if st.get("pending_confirm"):
            lo = floor
            hi = floor + timedelta(days=int(st["empty_run"]))
            got = fetch_window(src, s, _start_ms(lo), _start_ms(hi))
            if got is None:
                errors[s] = errors.get(s, 0) + 1
                return False
            st["pending_confirm"] = False
            if got.empty:
                st["exhausted"] = True
                st["exhausted_at"] = datetime.now(UTC).isoformat(timespec="seconds")
                return False
            wrote = write_days(s, got, root)
            new = [d for d in wrote if d not in held[s]]
            held[s].update(wrote)
            added[s] += len(new)
            ticks_added += sum(wrote.values())
            st["empty_run"] = 0
            st["floor"] = min(st["floor"], min(wrote))
            return True
        nxt = floor - timedelta(days=1)
        if nxt < deepest:
            st["exhausted"] = True
            st["exhausted_at"] = datetime.now(UTC).isoformat(timespec="seconds")
            st["exhausted_why"] = "MAX_DEPTH"
            return False
        iso = _iso(nxt)
        if iso in held[s]:
            st["floor"] = iso
            st["empty_run"] = 0
            return True
        got = fetch_window(src, s, _start_ms(nxt), _start_ms(nxt) + DAY_MS)
        if got is None:
            errors[s] = errors.get(s, 0) + 1
            return False
        st["floor"] = iso
        if got.empty:
            st["empty_run"] = int(st["empty_run"]) + 1
            if st["empty_run"] >= EMPTY_RUN_DAYS:
                st["pending_confirm"] = True
                return False
            return True
        wrote = write_days(s, got, root)
        new = [d for d in wrote if d not in held[s]]
        held[s].update(wrote)
        added[s] += len(new)
        ticks_added += sum(wrote.values())
        st["empty_run"] = 0
        return True

    # A confirming re-ask is due from the PREVIOUS pass; a run that just ended waits for the next.
    due_confirm = {s for s in symbols if syms[s].get("pending_confirm")}
    queue = order(live(), start_count)
    stalled: set[str] = set()
    while queue and status == STATUS_OK:
        progressed = False
        for s in list(queue):
            if clock() >= deadline:
                status = STATUS_BUDGET
                break
            gb = free_gb(root)
            if gb is not None and gb < DISK_FLOOR_GB:
                status = STATUS_DISK
                break
            if s in stalled:
                continue
            if syms[s].get("pending_confirm") and s not in due_confirm:
                stalled.add(s)
                continue
            for _ in range(DAYS_PER_TURN):
                if clock() >= deadline:
                    break
                if not step(s):
                    stalled.add(s)
                    break
                progressed = True
                if syms[s].get("pending_confirm") and s not in due_confirm:
                    stalled.add(s)
                    break
            due_confirm.discard(s)
            _write_json(state_path, state)
        queue = [s for s in live() if s not in stalled]
        if not progressed and status == STATUS_OK:
            break
    if status == STATUS_OK and not live():
        status = STATUS_DONE

    state["last_pass"] = datetime.now(UTC).isoformat(timespec="seconds")
    _write_json(state_path, state)
    per: dict[str, dict[str, Any]] = {}
    for s in symbols:
        st = syms[s]
        per[s] = {"days_on_disk": len(held[s]), "earliest": min(held[s]) if held[s] else None,
                  "floor": st["floor"], "added": added[s], "empty_run": st["empty_run"],
                  "pending_confirm": bool(st.get("pending_confirm")),
                  "exhausted": bool(st["exhausted"])}
        if errors.get(s):
            per[s]["terminal_failures"] = errors[s]
    crossed = sorted(s for s in symbols if start_count[s] < SEED_BAR <= len(held[s]))
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": status,
        "source": "Fusion MT5 terminal copy_ticks_range (venue-pinned)",
        "budget_s": budget_s,
        "elapsed_s": round(clock() - t0, 1),
        "seed_bar_days": SEED_BAR,
        "symbols": len(symbols),
        "days_added": int(sum(added.values())),
        "ticks_added": int(ticks_added),
        "at_or_above_bar": sum(1 for s in symbols if len(held[s]) >= SEED_BAR),
        "crossed_bar_this_pass": crossed,
        "exhausted": sum(1 for s in symbols if syms[s]["exhausted"]),
        "pending_confirm": sum(1 for s in symbols if syms[s].get("pending_confirm")),
        "terminal_failures": int(sum(errors.values())),
        "per_symbol": per,
    }


def universe_symbols(path: Path = UNIVERSE) -> list[str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return sorted(raw) if isinstance(raw, dict) else []


def _today_broker() -> date:
    """The broker's calendar day (venue clock = UTC + the session lead)."""
    now = datetime.now(UTC)
    return (now + timedelta(hours=tape._venue_lead_h(now))).date()


def _publish(report: dict[str, Any], path: Path = REPORT) -> None:
    _write_json(path, report)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=300.0,
                    help="seconds for this pass; 0 runs until every symbol is exhausted")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, call no terminal")
    args = ap.parse_args(argv)

    symbols = universe_symbols()
    if args.dry_run:
        archived = archived_days()
        counts = {s: len(present_days(s, archived)) for s in symbols}
        plan = order(symbols, counts)
        print(f"{len(symbols)} symbols; {sum(1 for n in counts.values() if n >= SEED_BAR)} at "
              f"or above {SEED_BAR} days")
        for s in plan[:20]:
            print(f"  {s:<12} {counts[s]:>4} days")
        return 0

    import MetaTrader5 as mt5
    from mt5desk.config import terminal_path
    from research.mt5_session import attach_or_initialize, venue_refusal

    path = terminal_path()
    if not attach_or_initialize(mt5, path=path, timeout=5000):
        _publish({"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                  "status": STATUS_NO_TERMINAL, "days_added": 0})
        print("tape_deepen: no terminal attached (Session 0 never launches one)")
        return 1
    why = venue_refusal(mt5, path)
    if why:
        _publish({"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                  "status": STATUS_VENUE, "why": why, "days_added": 0})
        print(f"tape_deepen: refused, {why}")
        return 3
    report = deepen(Mt5History(mt5), symbols, budget_s=args.budget_s, today=_today_broker())
    _publish(report)
    print(f"tape_deepen {report['status']}: +{report['days_added']} symbol-days, "
          f"+{report['ticks_added']:,} ticks; {report['at_or_above_bar']}/{report['symbols']} "
          f"at >= {SEED_BAR} days; {report['exhausted']} exhausted; "
          f"crossed the bar: {', '.join(report['crossed_bar_this_pass']) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
