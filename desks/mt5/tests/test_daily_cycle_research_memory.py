"""The typed research memory is a named daily STEP, not a swallowed afterthought (Tier-1 A4).

Measured 2026-09-08: `libs.research.memory.build_from_artifacts()` was called at the tail of
`_state_research_feedback` inside a bare try/except, and its output directory
`desks/mt5/data/memory` had never been created on this tree. A step whose failure is one log line
inside another step's body is indistinguishable from a step that never ran. Pinned: it is its own
STEP, it runs after the feedback engines whose artifacts it ingests, the old swallowing call is
gone, and a total failure of its inputs raises like any other step.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402

from libs.research import memory  # noqa: E402


def test_research_memory_is_a_named_step_after_the_feedback_engines() -> None:
    names = [n for n, _ in daily_cycle.STEPS]
    assert "research_memory" in names
    assert names.index("research_memory") > names.index("state_research_feedback")
    assert names.index("research_memory") < names.index("module_rent")
    assert dict(daily_cycle.STEPS)["research_memory"] is daily_cycle._research_memory


def test_the_feedback_step_no_longer_swallows_the_memory_build() -> None:
    src = inspect.getsource(daily_cycle._state_research_feedback)
    assert "build_from_artifacts" not in src
    assert "research memory" not in src


def test_the_step_calls_the_builder_and_logs_its_tally(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    seen: list[str] = []
    monkeypatch.setattr(daily_cycle, "dlog", lambda msg: seen.append(msg))
    monkeypatch.setattr(memory, "build_from_artifacts",
                        lambda: {"added": {"failure": 3}, "seen": {"failure": 3},
                                 "inputs": {"graph": "ok", "canon": "FAILED: boom"}})
    daily_cycle._research_memory()
    assert seen and "added={'failure': 3}" in seen[0] and "FAILED: boom" in seen[0]


def test_a_total_input_failure_raises_instead_of_reading_as_a_quiet_day(monkeypatch,
                                                                        tmp_path) -> None:
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    monkeypatch.setattr(daily_cycle, "dlog", lambda msg: None)
    monkeypatch.setattr(memory, "build_from_artifacts",
                        lambda: {"added": {}, "seen": {},
                                 "inputs": {"graph": "FAILED: a", "canon": "FAILED: b"}})
    with pytest.raises(RuntimeError, match="every memory input failed"):
        daily_cycle._research_memory()
    monkeypatch.setattr(memory, "build_from_artifacts", lambda: None)
    with pytest.raises(RuntimeError, match="not a report"):
        daily_cycle._research_memory()


def test_a_failing_memory_step_is_recorded_by_the_chain_like_any_other(monkeypatch,
                                                                       tmp_path) -> None:
    """The point of promotion: the runner's own failure accounting sees it."""
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    monkeypatch.setattr(memory, "build_from_artifacts", lambda: None)
    calls: list[str] = []
    monkeypatch.setattr(daily_cycle, "STEPS",
                        (("first", lambda: calls.append("first")),
                         ("research_memory", daily_cycle._research_memory),
                         ("last", lambda: calls.append("last"))))
    rc = daily_cycle.main([])
    assert calls == ["first", "last"], "a failing step must not stop the ones after it"
    log = (tmp_path / "daily_cycle.log").read_text("utf-8")
    assert "research_memory" in log and "not a report" in log
    assert rc != 0 or "FAILED" in log
