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
                        lambda **_: calls.append("compile") or {"exit_code": 0})
    monkeypatch.setattr(hourly_cycle, "_producer",
                        lambda *args: calls.append("merge") or {"exit_code": 0})
    assert hourly_cycle.catch_up_intake()["status"] == "OK"
    assert calls == ["compile", "merge"]


def test_failed_compilation_withholds_merge(monkeypatch):
    _lane(monkeypatch)
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda **_: {"exit_code": 1})
    calls = []
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: calls.append("merge"))
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"
    assert calls == []


def test_busy_lane_never_runs_second_compiler(monkeypatch):
    _lane(monkeypatch, owned=False)
    calls = []
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda **_: calls.append("compile"))
    assert hourly_cycle.catch_up_intake()["status"] == "SKIPPED"
    assert calls == []


def test_merge_failure_is_not_reported_as_success(monkeypatch):
    _lane(monkeypatch)
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda **_: {"exit_code": 0})
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: {"exit_code": 1})
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"


def test_catchup_leaves_merger_lock_to_its_child(monkeypatch):
    locks = []

    @contextmanager
    def acquire(name, **kwargs):
        locks.append(name)
        yield True

    monkeypatch.setattr(job_lock, "exclusive_job", acquire)
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda **_: {"exit_code": 0})
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: {"exit_code": 75})
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"
    assert locks == ["miner_candidate_compiler"]


def test_hourly_compile_leg_takes_the_purge_lock_and_defers_when_held(monkeypatch):
    """Audit COT_AXIS_DEEPENING_31eb89f3d: the hourly compile leg takes the SAME writer lock the
    lane purge takes, and a held lock is DEFERRED -- loud, never a silent skip, never a run."""
    seen = []

    @contextmanager
    def held(name, **kwargs):
        seen.append((name, kwargs))
        yield False

    monkeypatch.setattr(job_lock, "exclusive_job", held)
    ran = []
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: ran.append(args))
    out = hourly_cycle.compile_candidates()
    assert out["status"] == "DEFERRED" and out["exit_code"] is None and out["why"]
    assert ran == []
    assert seen == [("miner_candidate_compiler", {"account": False})]


def test_hourly_compile_leg_runs_under_the_lock_when_free(monkeypatch):
    held_during = []
    state = {"held": False}

    @contextmanager
    def free(name, **kwargs):
        state["held"] = True
        yield True
        state["held"] = False

    monkeypatch.setattr(job_lock, "exclusive_job", free)
    monkeypatch.setattr(hourly_cycle, "_producer",
                        lambda *args: held_during.append(state["held"]) or {"exit_code": 0})
    assert hourly_cycle.compile_candidates()["exit_code"] == 0
    assert held_during == [True]


def test_hourly_compile_leg_defers_against_the_real_lock(monkeypatch, tmp_path):
    """No mock of the lock itself: a lock file owned by a live process defers the leg."""
    import json
    import os
    monkeypatch.setattr(job_lock, "LOCK_ROOT", tmp_path)
    (tmp_path / "miner_candidate_compiler.json").write_text(json.dumps(
        {"token": "x", "pid": os.getpid(), "host": __import__("socket").gethostname()}))
    ran = []
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: ran.append(args))
    assert hourly_cycle.compile_candidates()["status"] == "DEFERRED"
    assert ran == []
    # A caller that already holds the lock (catch_up_intake) runs straight through it.
    monkeypatch.setattr(hourly_cycle, "_producer",
                        lambda *args: ran.append(args) or {"exit_code": 0})
    assert hourly_cycle.compile_candidates(lock_held=True)["exit_code"] == 0
    assert len(ran) == 1
