"""The continuous Fusion tick recorder. Runs on the Windows box; never touches the money path.

    py -3 -m recorders.tick_recorder --once        # one cycle, print the report, exit
    py -3 -m recorders.tick_recorder               # resident loop, single instance

WHAT IT IS FOR. Every second of Fusion quotes that nobody writes down is gone at any price. No
vendor sells one retail CFD broker's past quote stream and none ever will, so the inventory of
unrecorded hours only grows while the code is being improved. That asymmetry -- an unbounded,
permanent loss on one side against a few gigabytes a year on the other -- is why this loop is
built to keep running through conditions that would stop a tidier one, and why every ambiguity
in it resolves toward re-reading rather than skipping.

THE FOUR THINGS THAT ACTUALLY BREAK A RECORDER ON THIS BOX, and what each one does here:

  THE TERMINAL RESTARTS. Windows Update, a broker terminal upgrade, someone RDP'ing in and
  closing it. `alive()` is asked EVERY cycle and reconnects itself; a cycle that finds the
  terminal down records SOURCE_UNAVAILABLE over the window it could not see and comes back. It
  does not exit, because a recorder that exits on the first disconnect records one morning.

  THE WEEKEND. FX quotes stop Friday night and resume Sunday night, and a naive recorder either
  alarms every weekend or learns to ignore silence and then ignores a real outage too. Here the
  two are never confused: an empty pull is recorded as PULL_EMPTY with its exact window, and
  whether that window SHOULD have carried quotes is decided later by `tick_integrity` against
  the symbol's own observed session -- not by a hardcoded market calendar this desk would then
  have to maintain per asset class.

  THE SYMBOL LIST CHANGES. The broker lists and delists instruments, and `mt5desk/universe.py`
  records what a hardcoded list cost this desk: the energy and index complexes were absent from
  every hunt ever run and nothing said so. The universe here is `symbols()` on every refresh. A
  new symbol gets a COLD_START boundary marker at the instant capture begins -- the honest
  statement that quotes before that instant were never ours -- and a delisted one gets a
  SYMBOL_REMOVED row and keeps its cursor, so a symbol that comes back resumes rather than
  restarting.

  THE DISK FILLS. The previous generation of recorders on this desk filled the VPS. This one
  stops capturing and records the pause as a gap EPISODE while it lasts. IT NEVER DELETES TAPE TO
  MAKE ROOM. Deleting an unbuyable asset to acquire a cheaper one is a trade at infinitely bad
  odds, and a recorder that can do it once will do it on the day the disk fills for an unrelated
  reason. What it does instead is compact: a day that has stopped receiving is folded from ~1,440
  per-cycle segments into one, measured at ~25x smaller, before it is sealed. That is not
  downsampling -- every tick survives byte-for-byte -- and it is why the disk floor is a rare
  event rather than a weekly one.

WHAT IT NEVER DOES. It cannot place, modify or cancel an order; it imports nothing from
`gateway`, `execution_policy`, `netting` or `decision_core`, and a test asserts that. It is a
separate process from the gateway on purpose: the gateway must never wait on a disk write, and
the cheapest way to guarantee that is for the writer to be somewhere the gateway cannot call.

THE SETTLE LAG IS LOAD-BEARING. Pulls stop `SETTLE_MS` short of now rather than reaching for the
current millisecond. `copy_ticks_range` over a window that closed a moment ago can legitimately
be a beat behind the feed, and a recorder that advances its cursor past a window the server had
not finished filling drops the tail of every cycle -- a small, permanent, invisible loss. The lag
plus the overlap re-pull make advancing safe.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_HERE = Path(__file__).resolve().parent
_DESK = _HERE.parent
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders.tape_store import (  # noqa: E402
    GAP_COLD_START,
    GAP_DISK_FLOOR,
    GAP_PULL_EMPTY,
    GAP_PULL_FAILED,
    GAP_RECORDER_DOWN,
    GAP_SOURCE_UNAVAILABLE,
    GAP_SYMBOL_ADDED,
    GAP_SYMBOL_REMOVED,
    GAP_TRUNCATED,
    GAP_WRITE_FAILED,
    GapRecord,
    TapeStore,
    broker_day,
    dedupe,
    split_by_day,
)
from recorders.tick_source import TickSource, TickSourceError  # noqa: E402

#: The tape's home. Deliberately NOT inside the git tree: a directory that grows by gigabytes a
#: year has no business in a repository, and `desks/mt5/data/tape` is already the SILVER (derived,
#: rebuildable) layer. An operator moves it with one environment variable.
DEFAULT_TAPE_ROOT = Path(os.environ.get("MT5_TAPE_ROOT", "") or (
    r"C:\mt5tape" if sys.platform == "win32" else str(_DESK / "data" / "tape_bronze")))

#: One cycle a minute. Not faster: `copy_ticks_range` is a round trip to the terminal per symbol
#: and 251 of them at a 10s beat is a busy loop against the process that holds live positions.
#: Not slower: a longer beat means a longer window to re-pull after every crash.
DEFAULT_CYCLE_S = 60

#: Re-ask the broker what it lists every 5 minutes. Cheap, and the alternative is a stale list.
DEFAULT_UNIVERSE_REFRESH_S = 300

#: How far back a symbol with no cursor starts. Short on purpose: the point is to stop losing NEW
#: seconds, and a broker's own tick history is thin and not ours in any case.
DEFAULT_COLD_START_DAYS = 3

#: Never ask for more than this span in one call. A symbol whose cursor is a month behind after
#: a long outage catches up over successive cycles instead of trying to materialise a month.
MAX_WINDOW_MS = 6 * 3600 * 1000

#: Re-pull this much before the cursor every time. Overlap costs duplicate ticks, which are
#: removed on read; the alternative costs holes, which are permanent.
OVERLAP_MS = 5_000

#: Stop pulls this far short of now. See the module docstring -- this is the difference between
#: dropping the tail of every cycle and not.
SETTLE_MS = 2_000

#: A wall-clock hole longer than this between cycles is an OUTAGE and is recorded as one for
#: every enrolled symbol. Three cycles: long enough that an ordinary slow cycle is not an alarm.
MAX_CYCLE_GAP_MULT = 3

#: Below this much free space, capture PAUSES and says so. It never deletes tape.
DEFAULT_DISK_FLOOR_BYTES = 10 * 1024**3

#: Per-cycle wall budget. When it is spent the cycle stops where it is and the NEXT cycle
#: resumes from the same rotation offset, so a slow symbol can never starve the tail of the
#: alphabet -- the failure mode of every "first N symbols" slice.
DEFAULT_CYCLE_BUDGET_S = 45.0

#: Ticks above which a single pull is trimmed and the remainder deferred to the next cycle.
MAX_TICKS_PER_PULL = 2_000_000

#: Backfillable gap reasons: windows the broker's own tick history may still be able to fill.
#: PULL_EMPTY is NOT here -- the broker answered and had nothing, so there is nothing to recover
#: -- and neither are the boundary markers, which are facts rather than holes.
BACKFILLABLE = (GAP_RECORDER_DOWN, GAP_SOURCE_UNAVAILABLE, GAP_PULL_FAILED, GAP_DISK_FLOOR,
                GAP_WRITE_FAILED, GAP_TRUNCATED)

#: How many open backfillable windows are TRACKED per symbol for later resolution. The ledger
#: keeps every one of them forever; this is only the working set the recorder tries to close.
#: A symbol with more than this many unresolved outages has a bigger problem than bookkeeping,
#: and the overflow stays OPEN in the ledger -- which is the safe direction to fail.
MAX_TRACKED_GAPS = 50

#: A quiet interval is written to the gap ledger once it exceeds this, and again in full when it
#: ends. The first write is insurance: a crash inside a 60-hour weekend must still leave evidence
#: that the desk queried those hours and the broker had nothing. Fifteen minutes is long enough
#: that ordinary inter-tick silence on a thin equity CFD does not produce a row every cycle.
QUIET_RECORD_MS = 15 * 60 * 1000

#: How often a PAUSE (terminal down, disk floor) re-states itself in the gap ledger while it
#: lasts. Same insurance logic as QUIET_RECORD_MS and the same reason it is not every cycle: see
#: `_note_pause`, where the arithmetic of the per-cycle version is written out.
PAUSE_RECORD_MS = 15 * 60 * 1000

#: Symbol-days compacted per cycle, and the wall-clock allowance they share. BOTH ARE MEASURED
#: BOUNDS, NOT ROUND NUMBERS. Compacting one real-rate symbol-day costs 8.2s (EURUSD, 82,744
#: ticks) to 10.7s (XAUUSD, 553,742) in this container -- it reads 1,440 segments, merges,
#: dedupes and re-encodes. Four of those is 43 seconds, which is the ENTIRE default cycle budget
#: spent on housekeeping, on a 60-second beat, at exactly the moment 251 symbols all become
#: eligible together six hours after the day rolls.
#:
#: The wall allowance is the real control and the count is the cheap guard behind it. At ~10s
#: apiece the allowance admits one or two per cycle, so a full universe's daily backlog clears in
#: ~2.5 hours out of the 1,440 cycles a day offers, and no cycle carries more than ~15s of it.
#: Nothing is lost by going slowly: an uncompacted day is a COMPLETE day that costs more disk
#: than it needs to, and disk is the cheap side of every trade in this package.
MAX_COMPACTIONS_PER_CYCLE = 4
DEFAULT_COMPACT_BUDGET_S = 15.0

STATE_CURSORS = "cursors"
STATE_RECORDER = "recorder"
HEARTBEAT = "heartbeat"

#: THE ONE ARTIFACT THIS RECORDER WRITES INSIDE THE REPO. The tape itself lives outside the git
#: tree -- a directory that grows by gigabytes a year does not belong in a repository -- which
#: would leave the recorder invisible to every brain that cannot open a shell on this box. One
#: small committed status file is what makes "is the tape growing?" answerable from the VPS, the
#: dashboard and the capability graph, and it is what `tick_integrity` reads to tell "no tape
#: because the recorder never started" from "no tape because it is down right now". Those are
#: different alarms and they must not render the same way (WS-005).
STATUS = _DESK / "reports" / "TAPE_RECORDER.json"


@dataclass
class RecorderConfig:
    tape_root: Path = field(default_factory=lambda: Path(DEFAULT_TAPE_ROOT))
    cycle_s: int = DEFAULT_CYCLE_S
    universe_refresh_s: int = DEFAULT_UNIVERSE_REFRESH_S
    cold_start_days: int = DEFAULT_COLD_START_DAYS
    disk_floor_bytes: int = DEFAULT_DISK_FLOOR_BYTES
    cycle_budget_s: float = DEFAULT_CYCLE_BUDGET_S
    #: Wall-clock allowance for compaction, spent AFTER capture and separately from it. Separate
    #: on purpose: sharing the capture budget would starve compaction on a busy box, and a
    #: recorder that never compacts fills the disk it was compacting to protect.
    compact_budget_s: float = DEFAULT_COMPACT_BUDGET_S
    max_window_ms: int = MAX_WINDOW_MS
    overlap_ms: int = OVERLAP_MS
    settle_ms: int = SETTLE_MS
    clock_probe_symbol: str = ""
    #: Seal a day once this many hours of the next day have elapsed. Not zero: a broker can
    #: deliver the last ticks of a session slightly late, and sealing a day that is still
    #: receiving would make a normal delivery look like a post-seal write.
    seal_after_hours: int = 6


@dataclass
class SymbolResult:
    symbol: str
    ticks: int = 0
    segments: int = 0
    bytes: int = 0
    gaps: list[str] = field(default_factory=list)
    truncated: bool = False
    error: str = ""
    cursor_ms: int = 0


@dataclass
class CycleReport:
    cycle_id: str
    at: str
    window_ms: tuple[int, int]
    symbols_seen: int
    symbols_pulled: int
    ticks: int = 0
    segments: int = 0
    bytes: int = 0
    gaps_recorded: int = 0
    gaps_resolved: int = 0
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    sealed: list[str] = field(default_factory=list)
    truncations: int = 0
    clock_behind: int = 0
    compacted: int = 0
    bytes_reclaimed: int = 0
    paused: str = ""
    errors: dict[str, str] = field(default_factory=dict)
    budget_exhausted: bool = False
    elapsed_s: float = 0.0

    def render(self) -> str:
        head = (f"cycle {self.cycle_id} {self.at}  {self.ticks:,} ticks  "
                f"{self.segments} segments  {self.bytes/1e6:.2f} MB  "
                f"{self.symbols_pulled}/{self.symbols_seen} symbols  {self.elapsed_s:.1f}s")
        if self.paused:
            head += f"  PAUSED: {self.paused}"
        bits = []
        if self.gaps_recorded:
            bits.append(f"{self.gaps_recorded} gap row(s)")
        if self.gaps_resolved:
            bits.append(f"{self.gaps_resolved} resolved")
        if self.added:
            bits.append(f"+{len(self.added)} symbol(s): {', '.join(self.added[:6])}")
        if self.removed:
            bits.append(f"-{len(self.removed)} symbol(s): {', '.join(self.removed[:6])}")
        if self.sealed:
            bits.append(f"sealed {len(self.sealed)}")
        if self.compacted:
            bits.append(f"compacted {self.compacted} day(s), "
                        f"{self.bytes_reclaimed/1e6:.1f} MB reclaimed")
        if self.truncations:
            bits.append(f"{self.truncations} truncated pull(s), deferred")
        if self.clock_behind:
            bits.append(f"{self.clock_behind} symbol(s) IDLE: the query mark is ahead of the "
                        f"wall clock -- the system clock stepped backward")
        if self.budget_exhausted:
            bits.append("budget spent; next cycle resumes where this stopped")
        if self.errors:
            bits.append(f"{len(self.errors)} source error(s): "
                        f"{', '.join(sorted(self.errors)[:4])}")
        return head + ("\n  " + "; ".join(bits) if bits else "")


class TickRecorder:
    """The loop. Constructed with a `TickSource`, so it is fully testable off Windows."""

    def __init__(self, source: TickSource, config: RecorderConfig | None = None,
                 store: TapeStore | None = None) -> None:
        self.source = source
        self.config = config or RecorderConfig()
        self.store = store or TapeStore(self.config.tape_root)
        self._swept = False
        self._cycle = 0

    # ----------------------------------------------------------------- state --
    def _cursors(self) -> dict[str, dict[str, Any]]:
        raw = self.store.read_state(STATE_CURSORS, {}) or {}
        return {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}

    def _recorder_state(self) -> dict[str, Any]:
        return dict(self.store.read_state(STATE_RECORDER, {}) or {})

    # ----------------------------------------------------------------- cycle --
    def run_once(self, now_ms: int | None = None) -> CycleReport:
        """One capture cycle. Everything in this method is safe to interrupt at any point."""
        t_start = time.monotonic()
        now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
        end_ms = now_ms - self.config.settle_ms
        self._cycle += 1
        cycle_id = f"{now_ms}-{self._cycle}"
        rep = CycleReport(cycle_id=cycle_id,
                          at=datetime.fromtimestamp(now_ms / 1000.0,
                                                    tz=UTC).isoformat(timespec="seconds"),
                          window_ms=(0, end_ms), symbols_seen=0, symbols_pulled=0)

        if not self._swept:
            self.store.sweep_temp()
            self._swept = True

        cursors = self._cursors()
        state = self._recorder_state()
        active = [s for s, c in cursors.items() if c.get("active", True)]

        # -- THE OUTAGE CHECK COMES FIRST, BEFORE ANY PULL. A recorder that backfills and then
        # decides whether it was down has already made the hole invisible to itself.
        last_end = int(state.get("last_cycle_end_ms") or 0)
        down_window: tuple[int, int] | None = None
        max_gap_ms = self.config.cycle_s * 1000 * MAX_CYCLE_GAP_MULT
        if last_end and (now_ms - last_end) > max_gap_ms:
            down_window = (last_end, min(end_ms, now_ms))
            for sym in active:
                g = GapRecord(
                    symbol=sym, from_ms=down_window[0], to_ms=down_window[1],
                    reason=GAP_RECORDER_DOWN, cycle_id=cycle_id,
                    detail=(f"no cycle completed for {(now_ms - last_end)/1000.0:.0f}s "
                            f"(budget {max_gap_ms/1000.0:.0f}s) -- the recorder, the terminal "
                            f"or the box was not running"))
                self.store.record_gap(g)
                self._track_gap(cursors.get(sym), g)
                rep.gaps_recorded += 1

        # -- IS THERE A BROKER AT ALL THIS CYCLE?
        try:
            alive = bool(self.source.alive())
        except Exception as exc:                  # a source that raises is a source that is down
            alive = False
            rep.errors["_alive"] = f"{type(exc).__name__}: {exc}"
        if not alive:
            rep.paused = "source not connected"
            rep.gaps_recorded += self._note_pause(
                state, cursors, active, GAP_SOURCE_UNAVAILABLE, last_end, end_ms, cycle_id,
                "terminal not connected on this cycle")
            rep.symbols_seen = len(active)
            self._finish(rep, state, end_ms, t_start, cursors)
            return rep

        # -- DISK FLOOR. Pause, say so, keep saying so. Never delete tape.
        free = self.store.free_bytes()
        if free is not None and free < self.config.disk_floor_bytes:
            rep.paused = (f"free space {free/1e9:.1f}GB below the "
                          f"{self.config.disk_floor_bytes/1e9:.1f}GB floor")
            rep.gaps_recorded += self._note_pause(
                state, cursors, active, GAP_DISK_FLOOR, last_end, end_ms, cycle_id, rep.paused)
            rep.symbols_seen = len(active)
            self._finish(rep, state, end_ms, t_start, cursors)
            return rep

        # -- A PAUSE THAT HAS ENDED IS WRITTEN IN FULL, exactly like a quiet run.
        rep.gaps_recorded += self._close_pause(state, cursors, end_ms, cycle_id)

        # -- THE UNIVERSE IS WHATEVER THE TERMINAL SAYS IT IS, RIGHT NOW.
        last_uni = float(state.get("universe_at_ms") or 0)
        if (now_ms - last_uni) / 1000.0 >= self.config.universe_refresh_s or not cursors:
            try:
                listed = list(self.source.symbols())
                self._sync_universe(listed, cursors, now_ms, cycle_id, rep)
                state["universe_at_ms"] = now_ms
                state["universe_n"] = len(listed)
            except TickSourceError as exc:
                # A universe refresh that fails is NOT an empty universe. Keep the last known
                # list and record the failure -- shrinking the universe on a failed call is how
                # a whole asset class disappears from a desk without a decision.
                rep.errors["_symbols"] = str(exc)

        active = [s for s, c in cursors.items() if c.get("active", True)]
        rep.symbols_seen = len(active)

        # -- ROTATION OFFSET: whoever was next last time goes first now.
        offset = int(state.get("rotation_offset") or 0) % max(1, len(active))
        order = active[offset:] + active[:offset]
        budget = self.config.cycle_budget_s
        processed = 0

        for sym in order:
            if time.monotonic() - t_start > budget:
                rep.budget_exhausted = True
                break
            processed += 1
            res = self._pull_symbol(sym, cursors, end_ms, cycle_id)
            rep.ticks += res.ticks
            rep.segments += res.segments
            rep.bytes += res.bytes
            rep.gaps_recorded += len(res.gaps)
            if res.truncated:
                rep.truncations += 1
            if res.idle_clock_behind:
                rep.clock_behind += 1
            if res.error:
                rep.errors[sym] = res.error
            if res.ticks or res.segments:
                rep.symbols_pulled += 1
            rep.gaps_resolved += res.resolved
        # WHOEVER WAS NEXT GOES FIRST NEXT TIME. Advancing by what was actually processed --
        # never by the whole list -- is what stops a slow symbol starving the tail of the
        # alphabet, which is the standing defect of every "first N symbols" slice.
        state["rotation_offset"] = (offset + processed) % max(1, len(active))

        # -- COMPACT AND SEAL what has stopped moving.
        rep.sealed = self._seal_due(cursors, now_ms, rep)

        # -- THE CLOCK. Two integers, unbuyable after the fact.
        probe_sym = self.config.clock_probe_symbol or (active[0] if active else "")
        if probe_sym:
            try:
                probe = self.source.clock_probe(probe_sym)
            except Exception:
                probe = None
            if probe:
                self.store.record_clock(probe[0], probe[1], probe_sym)

        self._finish(rep, state, end_ms, t_start, cursors)
        return rep

    # ------------------------------------------------------------- internals --
    def _sync_universe(self, listed: list[str], cursors: dict[str, dict[str, Any]],
                       now_ms: int, cycle_id: str, rep: CycleReport) -> None:
        listed_set = set(listed)
        known = set(cursors)
        cold_ms = self.config.cold_start_days * 86_400_000

        for sym in sorted(listed_set - known):
            start = now_ms - cold_ms
            cursors[sym] = {"cursor_ms": start, "enrolled_ms": start, "active": True,
                            "last_tick_ms": 0, "quiet_from_ms": 0}
            # A ZERO-LENGTH BOUNDARY MARKER, not a gap with a made-up length. The honest claim is
            # "capture begins HERE"; inventing a start for the un-owned history before it would
            # put a number on something this desk never had and make the coverage arithmetic a
            # fiction. `tick_integrity` reads this row as the left edge of the desk's claim.
            self.store.record_gap(GapRecord(
                symbol=sym, from_ms=start, to_ms=start, reason=GAP_COLD_START, cycle_id=cycle_id,
                detail=("capture begins here; quotes before this instant were never recorded by "
                        "this desk and cannot be bought")))
            rep.gaps_recorded += 1
            rep.added.append(sym)
            select = getattr(self.source, "select", None)
            if callable(select):
                select(sym)
            if len(known) and sym not in known:
                self.store.record_gap(GapRecord(
                    symbol=sym, from_ms=start, to_ms=start, reason=GAP_SYMBOL_ADDED,
                    cycle_id=cycle_id, detail="newly listed by the broker"))
                rep.gaps_recorded += 1

        for sym in sorted(known - listed_set):
            row = cursors[sym]
            if not row.get("active", True):
                continue
            row["active"] = False
            row["delisted_ms"] = now_ms
            # THE CURSOR IS KEPT. A symbol the broker hides for a session and relists must
            # RESUME, not restart -- restarting would re-pull from a cold start and silently
            # abandon the window between.
            self.store.record_gap(GapRecord(
                symbol=sym, from_ms=int(row.get("cursor_ms") or now_ms), to_ms=now_ms,
                reason=GAP_SYMBOL_REMOVED, cycle_id=cycle_id,
                detail="no longer listed by the broker; cursor kept so a relist resumes"))
            rep.gaps_recorded += 1
            rep.removed.append(sym)

        for sym in sorted(listed_set & known):
            if not cursors[sym].get("active", True):
                cursors[sym]["active"] = True
                cursors[sym]["relisted_ms"] = now_ms

    def _pull_symbol(self, sym: str, cursors: dict[str, dict[str, Any]], end_ms: int,
                     cycle_id: str) -> _PullResult:
        res = _PullResult(symbol=sym)
        row = cursors.setdefault(sym, {"cursor_ms": end_ms, "enrolled_ms": end_ms,
                                       "active": True, "last_tick_ms": 0, "quiet_from_ms": 0})
        cursor = int(row.get("cursor_ms") or end_ms)
        start = max(int(row.get("enrolled_ms") or 0), cursor - self.config.overlap_ms)
        window_end = min(end_ms, start + self.config.max_window_ms)
        res.cursor_ms = cursor
        if window_end <= start:
            # NOTHING TO ASK FOR: the query mark is already at or past the settled edge of the
            # wall clock. Normally that means the previous cycle finished the window, which is
            # harmless. It ALSO happens when the system clock steps BACKWARD -- w32time resyncs
            # on this box -- and then every symbol silently does nothing, for as long as the step
            # was, while the heartbeat goes on saying RECORDING. That is the pairing the integrity
            # report calls the loudest finding available: the process believes it is working and
            # the output disagrees. It is not a GAP (no window is missing; the mark is ahead of
            # the clock, not behind it), so it is counted and surfaced rather than filed.
            res.idle_clock_behind = cursor > end_ms
            return res

        spec = None
        try:
            spec = self.source.symbol_spec(sym)
        except Exception:
            spec = None

        try:
            ticks = self.source.ticks(sym, start, window_end)
        except TickSourceError as exc:
            # THE CURSOR DOES NOT MOVE. The window is re-pulled next cycle; the failure is on
            # the record either way, so a run of failures is visible as a run.
            g = GapRecord(symbol=sym, from_ms=cursor, to_ms=window_end,
                          reason=GAP_PULL_FAILED, cycle_id=cycle_id, detail=str(exc)[:200])
            self.store.record_gap(g)
            self._track_gap(row, g)
            res.gaps.append(GAP_PULL_FAILED)
            res.error = str(exc)[:200]
            return res
        except Exception as exc:
            # An UNTYPED failure is tracked exactly like a typed one. The window this desk could
            # not read is the same window either way, and a gap that is only tracked when the
            # error had the right class is a gap that stays open on the surprises.
            g = GapRecord(symbol=sym, from_ms=cursor, to_ms=window_end, reason=GAP_PULL_FAILED,
                          cycle_id=cycle_id, detail=f"{type(exc).__name__}: {exc}"[:200])
            self.store.record_gap(g)
            self._track_gap(row, g)
            res.gaps.append(GAP_PULL_FAILED)
            res.error = f"{type(exc).__name__}: {exc}"[:200]
            return res

        ticks = dedupe(np.asarray(ticks))
        if ticks.size == 0:
            self._note_quiet(sym, row, cursor, window_end, cycle_id, res)
            # THE CURSOR IS THE HIGH-WATER MARK OF WHAT HAS BEEN QUERIED, not of what came back.
            # See `_pull_symbol`'s closing comment for why conflating the two deadlocks the loop.
            row["cursor_ms"] = window_end
            return res

        # A TRUNCATED PULL DEFERS ITS TAIL; IT DOES NOT DROP IT, AND IT USED TO.
        #
        # The cap's own comment said "the remainder deferred to the next cycle" and nothing
        # deferred it: the array was trimmed, the trimmed ticks were written, and then the cursor
        # advanced to `window_end` -- past every tick the trim had just discarded. Nothing was
        # re-queried, no gap row was written, and GAP_TRUNCATED sat in the ledger's vocabulary
        # unused. That is a permanent, silent loss that reads as a successful capture, which is
        # the single failure class this whole package exists to end, sitting inside the package.
        #
        # The deferral is now real: the query mark is rewound to just past the last tick KEPT, so
        # the tail is re-pulled next cycle, and a TRUNCATED row records the deferred window so a
        # crash before that cycle still leaves evidence. The row is backfillable and closes itself
        # when the tail actually lands.
        defer_from = 0
        if ticks.size > MAX_TICKS_PER_PULL:
            order = np.argsort(np.asarray(ticks["time_msc"]), kind="mergesort")
            ticks = ticks[order][:MAX_TICKS_PER_PULL]
            defer_from = int(np.asarray(ticks["time_msc"], dtype=np.int64).max()) + 1
            res.truncated = True

        # A QUIET RUN HAS ENDED. Record it as one interval so a reader sees one weekend rather
        # than 2,880 rows. Overlapping with the row written when the run passed QUIET_RECORD_MS
        # is harmless -- the integrity checker unions gap intervals, so a minute counts once.
        quiet_from = int(row.get("quiet_from_ms") or 0)
        first_ms = int(np.asarray(ticks["time_msc"]).min())
        if quiet_from and first_ms > quiet_from + QUIET_RECORD_MS:
            self.store.record_gap(GapRecord(
                symbol=sym, from_ms=quiet_from, to_ms=first_ms, reason=GAP_PULL_EMPTY,
                cycle_id=cycle_id,
                detail=("queried in full; the broker returned no ticks across this interval. "
                        "Whether it SHOULD have is decided by tick_integrity against this "
                        "symbol's own observed session, never by a hardcoded market calendar")))
            res.gaps.append(GAP_PULL_EMPTY)
        row["quiet_recorded"] = False

        if spec is not None and spec.point > 0:
            point, digits = spec.point, spec.digits
        else:
            # NO SPEC IS NOT A REASON TO GUESS A UNIT. The segment is written float64, which is
            # bigger and exactly right, and the encoding says so on the manifest row.
            point, digits = 0.0, 0

        last_written = 0
        try:
            for day, chunk in split_by_day(ticks):
                rec = self.store.write_segment(sym, day, chunk, point, digits, cycle_id)
                res.segments += 1
                res.bytes += rec.bytes
                res.ticks += rec.rows
                last_written = max(last_written, rec.last_ms)
        except (OSError, ValueError) as exc:
            # THE CURSOR DOES NOT MOVE ON A FAILED WRITE. Whatever landed is content-addressed
            # and will be recognised as already-present when the window is re-pulled.
            g = GapRecord(symbol=sym, from_ms=cursor, to_ms=window_end,
                          reason=GAP_WRITE_FAILED, cycle_id=cycle_id,
                          detail=f"{type(exc).__name__}: {exc}"[:200])
            self.store.record_gap(g)
            self._track_gap(row, g)
            res.gaps.append(GAP_WRITE_FAILED)
            res.error = f"{type(exc).__name__}: {exc}"[:200]
            return res

        tms = np.asarray(ticks["time_msc"], dtype=np.int64)
        res.resolved = self._close_tracked_gaps(sym, row, tms, cycle_id)

        # The window this cycle can honestly claim to have finished with. Normally the whole
        # window; after a truncation, only up to the last tick kept.
        done_to = window_end
        if defer_from and defer_from < window_end:
            done_to = defer_from
            g = GapRecord(symbol=sym, from_ms=defer_from, to_ms=window_end,
                          reason=GAP_TRUNCATED, cycle_id=cycle_id,
                          detail=(f"pull hit the {MAX_TICKS_PER_PULL:,}-tick cap; the tail of "
                                  f"this window is DEFERRED, not dropped -- the query mark stays "
                                  f"at {defer_from} and the next cycle re-reads from there"))
            self.store.record_gap(g)
            self._track_gap(row, g)
            res.gaps.append(GAP_TRUNCATED)
        # STEP 6 OF THE WRITE ORDER: the cursor moves only now, and only after a durable write.
        #
        # IT MOVES TO `window_end`, NOT TO THE LAST TICK, AND THAT DISTINCTION IS A BUG THIS CODE
        # ALREADY HAD. `cursor = last_tick + 1` reads as the careful choice -- never skip past
        # anything unseen -- and it deadlocks the loop every Friday night. The last pull before
        # the weekend returns a handful of Friday ticks near the START of a six-hour window; the
        # cursor advances to that tick; the next cycle re-queries almost the same window, gets
        # the same handful, and advances by milliseconds. Measured on the fake at 40k ticks/day:
        # the recorder froze at Friday's close and re-pulled the same window for all 160
        # remaining cycles, recording four days and then nothing, forever, while every heartbeat
        # said RECORDING.
        #
        # The correct invariant separates the two marks: `cursor_ms` is the high-water mark of
        # what has been QUERIED, `last_tick_ms` of what has been RECEIVED, and the interval
        # between them is a quiet interval the ledger records. Advancing the query mark past a
        # fully-queried window is safe for the same reason advancing past an empty one is: the
        # window closed SETTLE_MS ago and every pull re-reads OVERLAP_MS behind itself.
        row["cursor_ms"] = max(cursor, done_to)
        row["last_tick_ms"] = int(tms.max())
        row["quiet_from_ms"] = int(tms.max()) + 1
        row["last_write_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
        res.cursor_ms = row["cursor_ms"]
        return res

    def _note_pause(self, state: dict[str, Any], cursors: dict[str, dict[str, Any]],
                    active: list[str], reason: str, last_end: int, end_ms: int, cycle_id: str,
                    detail: str) -> int:
        """A cycle the recorder could not capture on. Recorded ONCE PER EPISODE, not per cycle.

        THE ARITHMETIC THAT FORCED THIS, and it is the disk-floor case that makes it urgent. The
        obvious implementation writes one gap row per enrolled symbol per cycle. At 251 symbols
        and a 60-second beat that is 15,060 rows an hour, roughly 3.7 MB an hour, ~90 MB a day --
        appended to the very disk whose exhaustion triggered the pause. The guard that exists to
        stop the recorder filling the disk would have filled it about three times faster than
        capturing would have, and it would have done so while reporting that it was protecting the
        box. A protective mechanism whose cost exceeds the thing it protects against is not a
        conservative choice.

        So a pause is an EPISODE, recorded the way `_note_quiet` records a quiet run: once when it
        starts, again every PAUSE_RECORD_MS as insurance against a crash mid-episode, and once in
        full when it ends. The integrity checker unions gap intervals, so the overlapping rows
        cover the same minutes once and the coverage arithmetic is unchanged. What changes is 96
        rows a day per symbol instead of 1,440, and a ledger in which a real outage is still
        legible.
        """
        ep = dict(state.get("pause_episode") or {})
        started = ep.get("reason") == reason and int(ep.get("from_ms") or 0) > 0
        if not started:
            # A NEW EPISODE CLOSES THE OLD ONE FIRST. A terminal that drops and then a disk that
            # fills are two different facts about two different windows, and letting the second
            # extend the first would file the outage under the wrong cause.
            n = self._close_pause(state, cursors, end_ms, cycle_id)
            ep = {"reason": reason, "from_ms": max(last_end, end_ms - self.config.cycle_s * 1000),
                  "symbols": list(active), "recorded_to_ms": 0, "cycle_id": cycle_id}
        else:
            n = 0
        from_ms = int(ep["from_ms"])
        ep["to_ms"] = end_ms
        ep["symbols"] = sorted({*(ep.get("symbols") or []), *active})
        due = (not ep.get("recorded_to_ms")
               or (end_ms - int(ep["recorded_to_ms"])) >= PAUSE_RECORD_MS)
        if due:
            for sym in (ep["symbols"] or active):
                self.store.record_gap(GapRecord(
                    symbol=sym, from_ms=from_ms, to_ms=end_ms, reason=reason, cycle_id=cycle_id,
                    detail=detail))
                n += 1
            ep["recorded_to_ms"] = end_ms
        state["pause_episode"] = ep
        return n

    def _close_pause(self, state: dict[str, Any], cursors: dict[str, dict[str, Any]],
                     end_ms: int, cycle_id: str) -> int:
        """Write the full window of a pause that has ended, and track it for backfill.

        The final row is what makes the episode's TOTAL extent a fact rather than a series of
        fifteen-minute fragments, and tracking it is what lets a later cycle mark it RESOLVED once
        the broker's own tick history fills it in. Without the tracking, SOURCE_UNAVAILABLE and
        DISK_FLOOR would sit in `BACKFILLABLE` and never actually be backfilled -- open forever in
        a ledger whose reader would learn that open outages are normal.
        """
        ep = dict(state.get("pause_episode") or {})
        reason = str(ep.get("reason") or "")
        from_ms, to_ms = int(ep.get("from_ms") or 0), int(ep.get("to_ms") or 0)
        state["pause_episode"] = {}
        if not reason or to_ms <= from_ms:
            return 0
        n = 0
        for sym in (ep.get("symbols") or []):
            g = GapRecord(symbol=sym, from_ms=from_ms, to_ms=to_ms, reason=reason,
                          cycle_id=str(ep.get("cycle_id") or cycle_id),
                          detail=(f"capture paused for {(to_ms - from_ms)/1000.0:.0f}s and has "
                                  f"resumed; this row is the episode in full"))
            self.store.record_gap(g)
            self._track_gap(cursors.get(sym), g)
            n += 1
        return n

    def _track_gap(self, row: dict[str, Any] | None, gap: GapRecord) -> None:
        """Remember a backfillable window so a LATER cycle can close it.

        THE OUTAGE IS USUALLY NOT CLOSED BY THE CYCLE THAT FINDS IT, and the first version of
        this loop assumed it was. After a six-hour outage the cursor is six hours behind, so the
        very next pull covers a window nowhere near the hole; by the time the backfill reaches it,
        several cycles later, the `down_window` local is long gone and the row can never be
        resolved. An outage that is permanently open is not a safe default -- it teaches whoever
        reads the integrity report that open outages are normal, which is precisely how a real
        one stops being visible.

        Tracked in the recorder's own state, which is written every cycle anyway, so closing a
        gap costs no extra I/O.
        """
        if gap.reason not in BACKFILLABLE or row is None:
            return
        open_gaps = list(row.get("open_gaps") or [])
        entry = {"from_ms": gap.from_ms, "to_ms": gap.to_ms, "reason": gap.reason,
                 "cycle_id": gap.cycle_id}
        # CONTIGUOUS WINDOWS OF THE SAME REASON ARE ONE WINDOW. Successive cycles of one outage
        # produce windows that abut exactly, and appending each of them would push a six-hour
        # outage's 360 fragments through a 50-entry ring buffer -- evicting the START of the very
        # outage being tracked, and writing a megabyte of cursor state every cycle for 251
        # symbols. Extending the tail keeps the episode whole and the state file small.
        for prev in reversed(open_gaps):
            if (prev.get("reason") == gap.reason
                    and int(prev.get("to_ms") or 0) >= gap.from_ms
                    and int(prev.get("from_ms") or 0) <= gap.from_ms):
                prev["to_ms"] = max(int(prev.get("to_ms") or 0), gap.to_ms)
                row["open_gaps"] = open_gaps[-MAX_TRACKED_GAPS:]
                return
        if entry not in open_gaps:
            open_gaps.append(entry)
        row["open_gaps"] = open_gaps[-MAX_TRACKED_GAPS:]

    def _close_tracked_gaps(self, sym: str, row: dict[str, Any], tms: np.ndarray,
                            cycle_id: str) -> int:
        """Resolve every tracked window this pull actually put ticks into.

        ONLY TICKS INSIDE THE WINDOW MAY CLOSE IT. Counting the whole pull would resolve an
        outage with data that is not in it, and a gap marked filled by data it does not contain
        is worse than an open gap because it stops anyone looking.
        """
        open_gaps = list(row.get("open_gaps") or [])
        if not open_gaps or tms.size == 0:
            return 0
        still_open: list[dict[str, Any]] = []
        closed = 0
        for entry in open_gaps:
            lo, hi = int(entry.get("from_ms", 0)), int(entry.get("to_ms", 0))
            n = int(np.count_nonzero((tms >= lo) & (tms < hi)))
            if n <= 0:
                still_open.append(entry)
                continue
            self.store.resolve_gap(
                GapRecord(symbol=sym, from_ms=lo, to_ms=hi,
                          reason=str(entry.get("reason") or GAP_RECORDER_DOWN),
                          cycle_id=str(entry.get("cycle_id") or "")),
                n, detail=(f"backfilled from the broker's own tick history on cycle {cycle_id}"))
            closed += 1
        row["open_gaps"] = still_open
        return closed

    def _note_quiet(self, sym: str, row: dict[str, Any], cursor: int, window_end: int,
                    cycle_id: str, res: _PullResult) -> None:
        """A window that was queried in full and had nothing in it.

        The interval is recorded ONCE when it grows past QUIET_RECORD_MS -- insurance, so a crash
        inside a long weekend still leaves evidence that the desk asked -- and again in full when
        quotes resume. Writing a row every cycle instead would put 2,880 rows in the ledger for
        one ordinary weekend and bury the outage rows that matter.
        """
        if not row.get("quiet_from_ms"):
            row["quiet_from_ms"] = cursor
        quiet_from = int(row["quiet_from_ms"])
        if not row.get("quiet_recorded") and (window_end - quiet_from) >= QUIET_RECORD_MS:
            row["quiet_recorded"] = True
            self.store.record_gap(GapRecord(
                symbol=sym, from_ms=quiet_from, to_ms=window_end, reason=GAP_PULL_EMPTY,
                cycle_id=cycle_id,
                detail=("queried in full; no ticks. The interval continues until quotes resume "
                        "and is then recorded in full -- this row exists so a crash mid-quiet "
                        "still leaves evidence that the desk asked")))
            res.gaps.append(GAP_PULL_EMPTY)

    def _seal_due(self, cursors: dict[str, dict[str, Any]], now_ms: int,
                  rep: CycleReport) -> list[str]:
        """Compact and seal every day that has stopped receiving. Both conditions are necessary.

        The wall clock says enough of the next day has passed that a late delivery is unlikely.
        THE CURSOR says this recorder has actually finished with the day -- and that one is the
        one that is easy to forget. A symbol catching up after a long outage is still writing
        into last Tuesday while the wall clock says Tuesday is ancient history, and sealing it
        would stamp "complete" on a day the recorder was mid-way through filling. The seal is a
        claim about completeness; a claim made while still writing is a false one.

        COMPACTION HAPPENS HERE, IMMEDIATELY BEFORE THE SEAL, because this is the one moment the
        recorder knows a day is finished. It folds ~1,440 per-cycle segments into one and takes a
        symbol-day from ~5 MB to ~0.2 MB (measured; see `tape_store`'s retention section). Sealing
        after compacting rather than before means the seal describes what the day actually holds.

        THE WATERMARK IS NOT AN OPTIMISATION, it is what stops this method growing without bound.
        Without it, every cycle stat-ed and JSON-parsed the seal of every day the tape has ever
        held: 251 symbols x 365 days is 91,000 file reads a minute after one year, on a box also
        running the terminal. Days are listed in ascending order and every eligibility test here
        is monotone in the day, so the first ineligible day ends the symbol -- and the watermark
        only ever advances across a contiguous prefix of finished days.
        """
        today = broker_day(now_ms)
        cutoff_day = broker_day(now_ms - self.config.seal_after_hours * 3600 * 1000)
        sealed: list[str] = []
        budget = MAX_COMPACTIONS_PER_CYCLE
        t_compact = time.monotonic()
        for sym in sorted(cursors):
            row = cursors.get(sym) or {}
            cursor_day = broker_day(int(row.get("cursor_ms") or 0)) if row.get("cursor_ms") else ""
            mark = str(row.get("sealed_through") or "")
            for day in self.store.days(sym):
                if mark and day <= mark:
                    continue
                if day >= today or day >= cutoff_day or (cursor_day and day >= cursor_day):
                    break                          # ascending: nothing after this is eligible
                if self.store.seal(sym, day) is None:
                    if budget <= 0 or (time.monotonic() - t_compact
                                       > self.config.compact_budget_s):
                        # Out of compaction budget: leave the day UNSEALED so the next cycle
                        # compacts it. Sealing it now would leave a finished day PERMANENTLY
                        # uncompacted, because nothing revisits a sealed day -- ~25x its
                        # necessary size, forever, for the sake of finishing this cycle sooner.
                        return sealed
                    res = self.store.compact_day(sym, day)
                    budget -= 1
                    if res["status"] == "COMPACTED":
                        rep.compacted += 1
                        rep.bytes_reclaimed += max(0, res["bytes_before"] - res["bytes_after"])
                    self.store.seal_day(sym, day)
                    sealed.append(f"{sym}/{day}")
                mark = day
                row["sealed_through"] = day
                if len(sealed) >= 200:
                    return sealed
        return sealed

    def _finish(self, rep: CycleReport, state: dict[str, Any], end_ms: int, t_start: float,
                cursors: dict[str, dict[str, Any]]) -> None:
        rep.elapsed_s = round(time.monotonic() - t_start, 3)
        rep.window_ms = (int(state.get("last_cycle_end_ms") or 0), end_ms)
        state["last_cycle_end_ms"] = end_ms
        state["cycles"] = int(state.get("cycles") or 0) + 1
        state["last_report"] = asdict(rep)
        self.store.write_state(STATE_CURSORS, cursors)
        self.store.write_state(STATE_RECORDER, state)
        self.store.write_state(HEARTBEAT, {
            "at": rep.at, "cycle_id": rep.cycle_id, "pid": os.getpid(),
            "ticks_this_cycle": rep.ticks, "bytes_this_cycle": rep.bytes,
            "symbols_seen": rep.symbols_seen, "symbols_pulled": rep.symbols_pulled,
            "paused": rep.paused, "elapsed_s": rep.elapsed_s,
            "free_bytes": self.store.free_bytes(),
            # A PAUSED RECORDER STILL BEATS. Silence and "paused on purpose" must never render
            # the same way to whatever is watching (WS-005).
            "state": "PAUSED" if rep.paused else "RECORDING",
        })
        self._write_status(rep, cursors)

    def _write_status(self, rep: CycleReport, cursors: dict[str, dict[str, Any]]) -> None:
        """The in-repo status file. Best effort: a status write that fails must never cost a
        capture, so this swallows its own errors -- the tape is the asset, the report is not."""
        try:
            active = [c for c in cursors.values() if c.get("active", True)]
            behind = [int(c.get("cursor_ms") or 0) for c in active if c.get("cursor_ms")]
            now_ms = int(time.time() * 1000)
            doc = {
                "schema": "tape-recorder-1",
                "at": rep.at,
                "state": "PAUSED" if rep.paused else "RECORDING",
                "paused_reason": rep.paused,
                "tape_root": str(self.config.tape_root),
                "cycle_id": rep.cycle_id,
                "cycle_elapsed_s": rep.elapsed_s,
                "symbols_enrolled": len(active),
                "symbols_pulled_this_cycle": rep.symbols_pulled,
                "ticks_this_cycle": rep.ticks,
                "bytes_this_cycle": rep.bytes,
                "segments_this_cycle": rep.segments,
                "gaps_recorded_this_cycle": rep.gaps_recorded,
                "gaps_resolved_this_cycle": rep.gaps_resolved,
                "truncated_pulls": rep.truncations,
                # Nonzero means the system clock stepped BACKWARD and capture is stalled until it
                # catches up. Surfaced beside the heartbeat on purpose: the heartbeat alone would
                # go on reporting RECORDING throughout.
                "symbols_idle_clock_behind": rep.clock_behind,
                "days_compacted_this_cycle": rep.compacted,
                "bytes_reclaimed_this_cycle": rep.bytes_reclaimed,
                "budget_exhausted": rep.budget_exhausted,
                # HOW FAR BEHIND THE FEED THE SLOWEST SYMBOL IS. The single number that says
                # whether the recorder is keeping up: a heartbeat proves the process is alive,
                # this proves it is not falling permanently behind while alive.
                "max_lag_s": (round((now_ms - min(behind)) / 1000.0, 1) if behind else None),
                "median_lag_s": (round((now_ms - float(np.median(behind))) / 1000.0, 1)
                                 if behind else None),
                "free_bytes": self.store.free_bytes(),
                "errors": dict(sorted(rep.errors.items())[:20]),
                "added": rep.added[:20],
                "removed": rep.removed[:20],
            }
            STATUS.parent.mkdir(parents=True, exist_ok=True)
            tmp = STATUS.parent / f".tmp-{STATUS.name}"
            tmp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            tmp.replace(STATUS)
        except (OSError, ValueError, TypeError):
            pass

    def run_forever(self, max_cycles: int | None = None,
                    sleep: Any = time.sleep) -> int:
        """The resident loop. Returns only on max_cycles or KeyboardInterrupt.

        NOTHING IN HERE MAY RAISE PAST THIS FRAME. A recorder that dies on an unexpected
        exception converts a one-cycle problem into an unbounded, permanent loss of tape, and
        the exceptions that matter are by definition the ones nobody predicted.
        """
        n = 0
        while max_cycles is None or n < max_cycles:
            n += 1
            try:
                rep = self.run_once()
                print(rep.render(), flush=True)
            except KeyboardInterrupt:
                print("stopped by operator", flush=True)
                return 0
            except Exception as exc:                # deliberate: see the docstring
                print(f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} CYCLE FAILED "
                      f"{type(exc).__name__}: {exc} -- continuing; the cursor did not move, so "
                      f"the window is re-pulled next cycle", flush=True)
            try:
                sleep(self.config.cycle_s)
            except KeyboardInterrupt:
                return 0
        return 0


@dataclass
class _PullResult(SymbolResult):
    #: Tracked gap windows this pull actually put ticks into and therefore closed.
    resolved: int = 0
    #: The query mark is AHEAD of the settled wall clock -- the system clock stepped backward.
    #: Not a gap; a stall, and one that would otherwise be invisible behind a healthy heartbeat.
    idle_clock_behind: bool = False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Continuous MT5/Fusion tick recorder")
    ap.add_argument("--once", action="store_true", help="one cycle, print the report, exit")
    ap.add_argument("--cycles", type=int, default=None, help="run exactly N cycles")
    ap.add_argument("--root", type=Path, default=None, help="tape root (default MT5_TAPE_ROOT)")
    ap.add_argument("--cycle-s", type=int, default=DEFAULT_CYCLE_S)
    ap.add_argument("--cold-start-days", type=int, default=DEFAULT_COLD_START_DAYS)
    ap.add_argument("--disk-floor-gb", type=float, default=DEFAULT_DISK_FLOOR_BYTES / 1024**3)
    ap.add_argument("--json", action="store_true", help="print the cycle report as JSON")
    args = ap.parse_args(argv)

    cfg = RecorderConfig(
        tape_root=args.root or Path(DEFAULT_TAPE_ROOT),
        cycle_s=args.cycle_s, cold_start_days=args.cold_start_days,
        disk_floor_bytes=int(args.disk_floor_gb * 1024**3),
    )
    from mt5desk.config import terminal_path

    from recorders.tick_source import Mt5TickSource

    src = Mt5TickSource(terminal_path())
    if not src.initialize():
        print("mt5 init failed -- the recorder cannot start without a terminal. This is a "
              "REPORTED failure, not a silent one: nothing was recorded and nothing pretends "
              "otherwise.")
        return 1
    rec = TickRecorder(src, cfg)
    if args.once or args.cycles:
        n = 1 if args.once else int(args.cycles or 1)
        out = [rec.run_once() for _ in range(n)]
        if args.json:
            print(json.dumps([asdict(r) for r in out], indent=1, default=str))
        else:
            for r in out:
                print(r.render())
        return 0
    print(f"recording to {cfg.tape_root} every {cfg.cycle_s}s -- Ctrl-C to stop", flush=True)
    return rec.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
