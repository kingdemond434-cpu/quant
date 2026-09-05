"""The allocator has a clock: the research supervisor launches pf_allocator on its own cadences.

Pinned: the most overdue mode wins (heavy > normal > fast); a heavier pass resets the lighter
clocks; nothing launches while an allocator is running or while a HOLD marker stands; a failed
launch leaves the clock untouched so the next tick retries.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_supervisor as rs  # noqa: E402

CAD = {"fast": 300, "normal": 900, "heavy": 3600}


def test_the_most_overdue_mode_wins_heaviest_first() -> None:
    assert rs._allocator_mode({}, 10_000.0, CAD) == "heavy"
    st = {"pf_allocator_heavy": {"last_spawn": 9_000.0},
          "pf_allocator_normal": {"last_spawn": 9_000.0},
          "pf_allocator_fast": {"last_spawn": 9_000.0}}
    assert rs._allocator_mode(st, 9_100.0, CAD) is None
    assert rs._allocator_mode(st, 9_400.0, CAD) == "fast"
    assert rs._allocator_mode(st, 9_950.0, CAD) == "normal"
    assert rs._allocator_mode(st, 12_700.0, CAD) == "heavy"


def test_a_tick_launches_the_due_mode_and_resets_the_lighter_clocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rs, "BASE", tmp_path)
    monkeypatch.setattr(rs, "is_running", lambda match: False)
    calls: list[tuple[str, list[str]]] = []

    def spawn(name: str, args: list[str]) -> int:
        calls.append((name, args))
        return 4242

    state: dict = {}
    assert rs.tick_periodic(state, 100_000.0, spawn) == ["pf_allocator:heavy"]
    assert calls[0][1][-3:] == ["research/pf_allocator.py", "--mode", "heavy"]
    for mode in ("heavy", "normal", "fast"):
        assert state[f"pf_allocator_{mode}"]["last_spawn"] == 100_000.0
    # nothing is due four minutes later; the fast clock is due after five
    assert rs.tick_periodic(state, 100_240.0, spawn) == []
    assert rs.tick_periodic(state, 100_301.0, spawn) == ["pf_allocator:fast"]
    assert state["pf_allocator_heavy"]["last_spawn"] == 100_000.0


def test_running_or_held_allocators_are_left_alone(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rs, "BASE", tmp_path)
    monkeypatch.setattr(rs, "is_running", lambda match: match == "pf_allocator.py")
    assert rs.tick_periodic({}, 100_000.0, lambda n, a: 1) == []
    monkeypatch.setattr(rs, "is_running", lambda match: False)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "HOLD_pf_allocator").write_text("", "utf-8")
    assert rs.tick_periodic({}, 100_000.0, lambda n, a: 1) == []


def test_a_failed_launch_keeps_the_clock_so_the_next_tick_retries(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rs, "BASE", tmp_path)
    monkeypatch.setattr(rs, "is_running", lambda match: False)
    state: dict = {}
    assert rs.tick_periodic(state, 100_000.0, lambda n, a: None) == []
    assert state == {}
