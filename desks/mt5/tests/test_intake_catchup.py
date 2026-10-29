"""A failed fresh compile must never republish an old docket as fresh intake."""
import sys
from contextlib import contextmanager
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import hourly_cycle  # noqa: E402
import pytest  # noqa: E402

from research import job_lock  # noqa: E402

#: A compile that exited 0 AND advanced compiled_at -- what `compile_candidates` now reports for
#: a real success (2026-10-29: exit 0 without an advance is FAILED, see
#: test_miner_compiler_freshness).
FRESH = {"exit_code": 0, "compiled_at_advanced": True}


@pytest.fixture(autouse=True)
def _attempt_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(hourly_cycle, "MINER_COMPILER_ATTEMPT", tmp_path / "attempt.json")


def _lane(monkeypatch, owned=True):
    @contextmanager
    def acquire(name, **kwargs):
        yield owned
    monkeypatch.setattr(job_lock, "exclusive_job", acquire)


def test_catchup_publishes_successful_compile_before_generation(monkeypatch):
    _lane(monkeypatch)
    calls = []
    monkeypatch.setattr(hourly_cycle, "compile_candidates",
                        lambda: calls.append("compile") or FRESH)
    monkeypatch.setattr(hourly_cycle, "_producer",
                        lambda *args: calls.append("merge") or {"exit_code": 0})
    assert hourly_cycle.catch_up_intake()["status"] == "OK"
    assert calls == ["compile", "merge"]


def test_failed_compilation_withholds_merge(monkeypatch):
    _lane(monkeypatch)
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda: {"exit_code": 1})
    calls = []
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: calls.append("merge"))
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"
    assert calls == []


def test_busy_lane_never_runs_second_compiler(monkeypatch):
    _lane(monkeypatch, owned=False)
    calls = []
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda: calls.append("compile"))
    assert hourly_cycle.catch_up_intake()["status"] == "SKIPPED"
    assert calls == []


def test_merge_failure_is_not_reported_as_success(monkeypatch):
    _lane(monkeypatch)
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda: FRESH)
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: {"exit_code": 1})
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"


def test_catchup_leaves_merger_lock_to_its_child(monkeypatch):
    locks = []

    @contextmanager
    def acquire(name, **kwargs):
        locks.append(name)
        yield True

    monkeypatch.setattr(job_lock, "exclusive_job", acquire)
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda: FRESH)
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: {"exit_code": 75})
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"
    assert locks == ["miner_candidate_compiler"]


def test_exit_zero_without_an_advance_withholds_merge(monkeypatch):
    _lane(monkeypatch)
    monkeypatch.setattr(hourly_cycle, "compile_candidates",
                        lambda: {"exit_code": 0, "compiled_at_advanced": False})
    calls = []
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: calls.append("merge"))
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"
    assert calls == []
