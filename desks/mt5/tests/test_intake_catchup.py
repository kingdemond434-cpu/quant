"""A failed fresh compile must never republish an old docket as fresh intake."""
import sys
from contextlib import contextmanager
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import hourly_cycle  # noqa: E402

from research import job_lock  # noqa: E402


def _lane(monkeypatch, owned=True):
    @contextmanager
    def acquire(name, **kwargs):
        yield owned
    monkeypatch.setattr(job_lock, "exclusive_job", acquire)


def test_catchup_publishes_successful_compile_before_generation(monkeypatch):
    _lane(monkeypatch)
    calls = []
    monkeypatch.setattr(hourly_cycle, "compile_candidates",
                        lambda: calls.append("compile") or {"exit_code": 0})
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
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda: {"exit_code": 0})
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: {"exit_code": 1})
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"
