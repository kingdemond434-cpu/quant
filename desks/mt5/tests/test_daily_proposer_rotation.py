"""The daily proposer loop rotates, so the tail of the roster is never starved (2026-11-03).

On the box every MT5-Daily pass hit its 10 h limit before the tail: learned_miners and five more
had never run, and the learned-models weekly contract froze on 10-07.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import daily_cycle as dc  # noqa: E402

NAMES = ("a", "b", "c", "d")


def test_absent_or_unreadable_cursor_starts_at_the_first(tmp_path: Path) -> None:
    cur = tmp_path / "cur.json"
    assert dc.rotated(NAMES, cur) == list(NAMES)
    cur.write_text("not json", "utf-8")
    assert dc.rotated(NAMES, cur) == list(NAMES)


def test_a_pass_killed_mid_loop_resumes_after_the_proposer_it_was_in(tmp_path: Path) -> None:
    cur = tmp_path / "cur.json"
    seen: list[str] = []
    for name in dc.rotated(NAMES, cur):          # pass 1: killed while "b" runs
        dc.advance_cursor(NAMES, name, cur)
        seen.append(name)
        if name == "b":
            break
    assert dc.rotated(NAMES, cur) == ["c", "d", "a", "b"]
    assert json.loads(cur.read_text("utf-8"))["after"] == "b"


def test_every_proposer_runs_within_a_rotation_even_when_each_pass_runs_only_two(
        tmp_path: Path) -> None:
    cur = tmp_path / "cur.json"
    ran: set[str] = set()
    for _ in range(2):
        for i, name in enumerate(dc.rotated(NAMES, cur)):
            if i == 2:
                break
            dc.advance_cursor(NAMES, name, cur)
            ran.add(name)
    assert ran == set(NAMES)


def test_the_real_roster_includes_learned_miners_and_the_loop_uses_the_cursor() -> None:
    src = (DESK / "research" / "daily_cycle.py").read_text("utf-8")
    assert "for name in rotated(proposers, PROPOSER_CURSOR):" in src
    assert '"learned_miners"' in src and '"book_forensics")' in src
