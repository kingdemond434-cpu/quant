"""The recorder against the conditions that actually stop one on the Windows box.

Every test here corresponds to a named failure mode in `recorders/tick_recorder.py`'s docstring.
The point is not that the loop works on a good day -- it is that the loop keeps recording, and
keeps RECORDING WHAT IT MISSED, on the bad ones.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders import tape_store as ts  # noqa: E402
from recorders.tick_recorder import RecorderConfig, TickRecorder  # noqa: E402
from recorders.tick_source import FakeTickSource, TickSourceError  # noqa: E402

T0 = 1_780_000_000_000
HOUR = 3_600_000


def _rig(tmp_path: Path, symbols: list[str] | None = None, cold_start_days: int = 1
         ) -> tuple[FakeTickSource, TickRecorder, ts.TapeStore]:
    src = FakeTickSource(symbols or ["EURUSD", "XAUUSD"], ticks_per_day=40_000)
    config = RecorderConfig(tape_root=tmp_path / "tape", cycle_s=3600,
                            cold_start_days=cold_start_days, disk_floor_bytes=0,
                            seal_after_hours=1)
    rec = TickRecorder(src, config)
    return src, rec, ts.TapeStore(config.tape_root)


def _reasons(store: ts.TapeStore, sym: str) -> set[str]:
    out: set[str] = set()
    for day in store.days(sym) or [ts.broker_day(T0)]:
        out |= {g.reason for g in store.gaps(sym, day)}
    for d in (store.gaps_dir / sym).glob("*.jsonl") if (store.gaps_dir / sym).is_dir() else []:
        out |= {g.reason for g in store.gaps(sym, d.stem)}
    return out


# ------------------------------------------------------------------ cold start --
def test_a_new_symbol_gets_a_cold_start_boundary_marker_not_an_invented_gap(
        tmp_path: Path) -> None:
    """The honest claim is 'capture begins HERE'. Inventing a length for the un-owned history
    before it would put a number on something this desk never had."""
    _, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    assert ts.GAP_COLD_START in _reasons(store, "EURUSD")
    cold = [g for d in store.days("EURUSD") for g in store.gaps("EURUSD", d)
            if g.reason == ts.GAP_COLD_START]
    assert cold and all(g.seconds == 0.0 for g in cold), (
        "a cold-start marker must be zero-length: it is a boundary, not a hole")


def test_the_universe_is_the_terminal_s_list_and_a_new_listing_is_enrolled(
        tmp_path: Path) -> None:
    src, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    src.add_symbol("GBPJPY")
    rep = rec.run_once(now_ms=T0 + HOUR)
    assert "GBPJPY" in rep.added
    assert ts.GAP_SYMBOL_ADDED in _reasons(store, "GBPJPY")


def test_a_delisted_symbol_keeps_its_cursor_so_a_relist_resumes_rather_than_restarts(
        tmp_path: Path) -> None:
    src, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    cursor = store.read_state("cursors")["XAUUSD"]["cursor_ms"]
    src.remove_symbol("XAUUSD")
    rep = rec.run_once(now_ms=T0 + HOUR)
    assert "XAUUSD" in rep.removed
    row = store.read_state("cursors")["XAUUSD"]
    assert row["active"] is False
    assert row["cursor_ms"] == cursor, "restarting from cold would abandon the window between"
    assert ts.GAP_SYMBOL_REMOVED in _reasons(store, "XAUUSD")

    src.add_symbol("XAUUSD")
    rec.run_once(now_ms=T0 + 2 * HOUR)
    assert store.read_state("cursors")["XAUUSD"]["active"] is True


def test_a_failed_universe_refresh_does_not_shrink_the_universe(tmp_path: Path) -> None:
    """Shrinking on a failed call is how a whole asset class disappears without a decision."""
    src, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    src.is_alive = True

    def _boom() -> list[str]:
        raise TickSourceError("symbols_get failed")

    src.symbols = _boom                                     # type: ignore[method-assign]
    rep = rec.run_once(now_ms=T0 + HOUR)
    assert "_symbols" in rep.errors
    assert set(store.read_state("cursors")) == {"EURUSD", "XAUUSD"}
    assert rep.removed == []


# ------------------------------------------------------------- terminal is down --
def test_a_disconnected_terminal_is_recorded_as_a_gap_and_the_loop_survives(
        tmp_path: Path) -> None:
    src, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    src.is_alive = False
    rep = rec.run_once(now_ms=T0 + HOUR)
    assert rep.paused == "source not connected"
    assert ts.GAP_SOURCE_UNAVAILABLE in _reasons(store, "EURUSD")

    src.is_alive = True
    rep = rec.run_once(now_ms=T0 + 2 * HOUR)
    assert rep.paused == "" and rep.ticks > 0, "the recorder must come back by itself"


def test_a_pull_that_fails_records_the_window_and_does_not_move_the_cursor(
        tmp_path: Path) -> None:
    src, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    before = store.read_state("cursors")["EURUSD"]["cursor_ms"]
    src.fail_symbols = {"EURUSD"}
    rep = rec.run_once(now_ms=T0 + HOUR)
    assert "EURUSD" in rep.errors
    assert ts.GAP_PULL_FAILED in _reasons(store, "EURUSD")
    assert store.read_state("cursors")["EURUSD"]["cursor_ms"] == before, (
        "a failed pull must leave the window to be re-read, never skipped")


def test_an_outage_is_recorded_before_any_backfill_and_resolved_when_the_backfill_reaches_it(
        tmp_path: Path) -> None:
    """A recorder that backfills and THEN decides whether it was down has already made the hole
    invisible to itself -- so the row is written first, on the cycle that notices.

    THE RESOLUTION COMES LATER, AND THAT IS THE WHOLE DIFFICULTY. After a six-hour outage the
    cursor is hours behind the hole, so the very next pull covers a window nowhere near it; the
    backfill only arrives several cycles on. The first version of this loop resolved outages
    from a local variable that existed for exactly one cycle, which meant an outage during any
    catch-up backlog could never be closed -- and an outage row that is permanently open teaches
    whoever reads the integrity report that open outages are normal, which is exactly how a real
    one stops being visible.
    """
    _, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    # Six hours later: far beyond cycle_s * MAX_CYCLE_GAP_MULT.
    rec.run_once(now_ms=T0 + 6 * HOUR)
    assert ts.GAP_RECORDER_DOWN in _reasons(store, "EURUSD")
    tracked = store.read_state("cursors")["EURUSD"]["open_gaps"]
    assert tracked and tracked[0]["reason"] == ts.GAP_RECORDER_DOWN, (
        "the window must be tracked across cycles, not held in a local that dies with the cycle")

    resolved_on = None
    for i in range(2, 14):
        rep = rec.run_once(now_ms=T0 + (6 + i) * HOUR)
        if rep.gaps_resolved:
            resolved_on = i
            break
    assert resolved_on is not None, (
        "the backfill caught up and never closed the outage row it had already recorded")
    rows = [g for d in store.days("EURUSD") for g in store.gaps("EURUSD", d)]
    resolved = [g for g in rows if g.reason == ts.GAP_RESOLVED]
    assert resolved and resolved[0].recovered_ticks > 0
    assert not store.read_state("cursors")["EURUSD"]["open_gaps"]


def test_an_outage_over_a_period_with_no_quotes_stays_open(tmp_path: Path) -> None:
    """Only ticks that land INSIDE the window may close it. A gap marked filled by data that is
    not in it is worse than an open gap, because it stops anyone looking."""
    src, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    src.silent_symbols = {"EURUSD"}
    rec.run_once(now_ms=T0 + 6 * HOUR)
    opens = [g for d in store.days("EURUSD") for g in store.open_gaps("EURUSD", d)]
    assert any(g.reason == ts.GAP_RECORDER_DOWN for g in opens)


# ------------------------------------------------------------------ the weekend --
def test_a_quiet_period_does_not_deadlock_the_cursor(tmp_path: Path) -> None:
    """REGRESSION. The first version advanced the cursor to the LAST TICK rather than to the end
    of the window it had queried. The last pull before the weekend returns a handful of Friday
    ticks near the start of a six-hour window, the cursor advances to that tick, and the next
    cycle re-queries almost the same window forever. Measured: the recorder froze at Friday's
    close, recorded four days and then nothing, while every heartbeat still said RECORDING.
    """
    _, rec, store = _rig(tmp_path, cold_start_days=30)
    for i in range(200):
        rec.run_once(now_ms=T0 + i * HOUR)
    days = store.days("EURUSD")
    assert len(days) > 25, (
        f"the recorder only reached {len(days)} days -- the cursor is not advancing past quiet "
        f"windows, which is the weekend deadlock this test exists for")
    assert days[-1] > days[0]


def test_a_quiet_run_is_recorded_once_at_its_start_and_once_in_full_when_it_ends(
        tmp_path: Path) -> None:
    """Not once per cycle: one ordinary weekend would otherwise put 2,880 rows in the ledger and
    bury the outage rows that matter."""
    _, rec, store = _rig(tmp_path, cold_start_days=10)
    for i in range(80):
        rec.run_once(now_ms=T0 + i * HOUR)
    empties = [g for d in store.days("EURUSD") for g in store.gaps("EURUSD", d)
               if g.reason == ts.GAP_PULL_EMPTY]
    assert empties, "the weekend must be recorded as a queried-and-empty interval"
    assert len(empties) < 40, (f"{len(empties)} PULL_EMPTY rows over ~10 days is per-cycle "
                               f"spam, not per-interval recording")


# ------------------------------------------------------------------- disk floor --
def test_the_disk_floor_pauses_capture_and_never_deletes_tape(tmp_path: Path) -> None:
    _, rec, store = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    before = store.day_bytes("EURUSD", store.days("EURUSD")[-1])
    assert before > 0
    rec.config.disk_floor_bytes = 1 << 62                   # nothing can satisfy this
    rep = rec.run_once(now_ms=T0 + HOUR)
    assert "below the" in rep.paused
    assert ts.GAP_DISK_FLOOR in _reasons(store, "EURUSD")
    assert store.day_bytes("EURUSD", store.days("EURUSD")[-1]) >= before, (
        "deleting an unbuyable asset to acquire a cheaper one is a trade at infinitely bad odds")


def test_a_paused_recorder_still_beats(tmp_path: Path) -> None:
    """Silence and 'paused on purpose' must never render the same way to whatever is watching."""
    _, rec, store = _rig(tmp_path)
    rec.config.disk_floor_bytes = 1 << 62
    rec.run_once(now_ms=T0)
    hb = store.read_state("heartbeat")
    assert hb["state"] == "PAUSED" and hb["paused"]


# --------------------------------------------------------------- the loop itself --
def test_the_rotation_advances_by_what_was_processed_so_no_symbol_starves(
        tmp_path: Path) -> None:
    """The failure mode of every 'first N symbols' slice: the tail of the alphabet never runs."""
    _, rec, store = _rig(tmp_path, ["AAA", "BBB", "CCC", "DDD"])
    rec.config.cycle_budget_s = -1.0                       # every cycle stops immediately
    rec.run_once(now_ms=T0)
    rec.run_once(now_ms=T0 + HOUR)
    assert store.read_state("recorder")["rotation_offset"] == 0, (
        "a cycle that processed nothing must not advance the rotation past anybody")

    rec.config.cycle_budget_s = 1e6
    rec.run_once(now_ms=T0 + 2 * HOUR)
    assert set(store.read_state("cursors")) == {"AAA", "BBB", "CCC", "DDD"}


def test_run_forever_survives_a_source_that_raises_anything(tmp_path: Path) -> None:
    """A recorder that dies on an unexpected exception converts a one-cycle problem into an
    unbounded, permanent loss of tape."""
    src, rec, _ = _rig(tmp_path)

    def _explode() -> bool:
        raise RuntimeError("something nobody predicted")

    src.alive = _explode                                    # type: ignore[method-assign]
    calls: list[float] = []
    assert rec.run_forever(max_cycles=3, sleep=calls.append) == 0
    assert len(calls) == 3, "the loop must keep going, not exit on the first surprise"


def test_the_recorder_writes_an_in_repo_status_file_so_the_tape_is_visible_off_box(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import recorders.tick_recorder as tr
    status = tmp_path / "TAPE_RECORDER.json"
    monkeypatch.setattr(tr, "STATUS", status)
    _, rec, _ = _rig(tmp_path)
    rec.run_once(now_ms=T0)
    import json
    doc = json.loads(status.read_text("utf-8"))
    assert doc["state"] == "RECORDING"
    assert doc["symbols_enrolled"] == 2
    assert doc["max_lag_s"] is not None, "how far behind the feed we are is the number that says "\
                                         "whether the recorder is keeping up"


# ------------------------------------------------------------ the money-path fence --
_MONEY_PATH = {"gateway", "execution_policy", "netting", "decision_core", "scalp_exec",
               "position_manager", "sizing"}


@pytest.mark.parametrize("module", sorted(p.name for p in (_DESK / "recorders").glob("*.py")))
def test_no_recorder_can_reach_the_money_path(module: str) -> None:
    """A recorder that can stall an order is a recorder that loses money.

    The guarantee is structural, not procedural: nothing in `recorders/` may import the modules
    that place, modify or cancel an order. Checked by AST rather than by grep so a comment
    mentioning the gateway is not a violation and `from mt5desk import gateway` is.
    """
    src = (_DESK / "recorders" / module).read_text("utf-8")
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imported.add(base)
            imported |= {f"{base}.{a.name}" for a in node.names}
    leaves = {part for name in imported for part in name.split(".")}
    assert not (leaves & _MONEY_PATH), (
        f"{module} imports the money path ({sorted(leaves & _MONEY_PATH)}). The recorder runs in "
        f"its own process precisely so the gateway can never wait on a disk write.")


def test_metatrader5_is_never_imported_at_module_scope_anywhere_in_the_package() -> None:
    """One Windows-only import at module scope makes the whole package untestable off the box --
    which is how every previous collector on this desk ended up with no tests at all."""
    for path in sorted((_DESK / "recorders").glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        for node in tree.body:                              # MODULE SCOPE ONLY
            names: set[str] = set()
            if isinstance(node, ast.Import):
                names = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module or ""}
            assert "MetaTrader5" not in names, f"{path.name} imports MetaTrader5 at module scope"
