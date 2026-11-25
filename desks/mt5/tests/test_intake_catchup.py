"""The core intake catch-up merges ONLY a fresh compile; the compile has its own lane.

2026-11-25: the compile inside this leg was killed at its cap on every pass, so the compiler
artifact went stale for 52 days. A stale compile must never be republished as fresh intake.
"""
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from contextlib import contextmanager  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

import hourly_cycle  # noqa: E402

from research import job_lock  # noqa: E402


def _artifact(monkeypatch, tmp_path, age_s):
    """Point the catch-up at a tmp tree whose miner_candidates.json is `age_s` old (None=absent)."""
    (tmp_path / "data" / "hypotheses").mkdir(parents=True)
    if age_s is not None:
        stamp = (datetime.now(UTC) - timedelta(seconds=age_s)).isoformat(timespec="seconds")
        (tmp_path / "data" / "hypotheses" / "miner_candidates.json").write_text(
            '{\n "compiled_at": "%s",\n "hypotheses": []\n}' % stamp)
    monkeypatch.setattr(hourly_cycle, "BASE", tmp_path)


def _lane(monkeypatch, owned=True):
    @contextmanager
    def acquire(name, **kwargs):
        yield owned
    monkeypatch.setattr(job_lock, "exclusive_job", acquire)


def test_catchup_merges_a_fresh_compile(monkeypatch, tmp_path):
    _artifact(monkeypatch, tmp_path, 600)
    calls = []
    monkeypatch.setattr(hourly_cycle, "_producer",
                        lambda *args: calls.append(args[0]) or {"exit_code": 0})
    assert hourly_cycle.catch_up_intake()["status"] == "OK"
    assert calls == ["merge_hypotheses"]


def test_catchup_never_compiles_and_never_merges_a_stale_compile(monkeypatch, tmp_path):
    _artifact(monkeypatch, tmp_path, 3 * 3600)
    calls = []
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda *a: calls.append("compile"))
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: calls.append("merge"))
    out = hourly_cycle.catch_up_intake()
    assert out["status"] == "SKIPPED" and calls == []


def test_unmeasured_compile_is_never_merged(monkeypatch, tmp_path):
    _artifact(monkeypatch, tmp_path, None)
    calls = []
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: calls.append("merge"))
    assert hourly_cycle.catch_up_intake()["status"] == "SKIPPED" and calls == []


def test_merge_failure_is_not_reported_as_success(monkeypatch, tmp_path):
    _artifact(monkeypatch, tmp_path, 60)
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: {"exit_code": 1})
    assert hourly_cycle.catch_up_intake()["status"] == "FAILED"


def test_compiler_lane_compiles_with_its_own_budget_then_merges(monkeypatch):
    _lane(monkeypatch)
    calls = []
    monkeypatch.setattr(hourly_cycle, "compile_candidates",
                        lambda b=0: calls.append(("compile", b)) or {"exit_code": 0})
    monkeypatch.setattr(hourly_cycle, "_producer",
                        lambda *args: calls.append(("merge", 0)) or {"exit_code": 0})
    assert hourly_cycle.compiler_lane()["status"] == "OK"
    assert calls == [("compile", hourly_cycle.COMPILER_LANE_BUDGET_S), ("merge", 0)]
    assert hourly_cycle.COMPILER_LANE_BUDGET_S > 720   # the budget the leg was killed under


def test_failed_compilation_withholds_merge(monkeypatch):
    _lane(monkeypatch)
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda b=0: {"exit_code": 1})
    calls = []
    monkeypatch.setattr(hourly_cycle, "_producer", lambda *args: calls.append("merge"))
    assert hourly_cycle.compiler_lane()["status"] == "FAILED"
    assert calls == []


def test_busy_lane_never_runs_second_compiler(monkeypatch):
    _lane(monkeypatch, owned=False)
    calls = []
    monkeypatch.setattr(hourly_cycle, "compile_candidates", lambda b=0: calls.append("compile"))
    assert hourly_cycle.compiler_lane()["status"] == "SKIPPED"
    assert calls == []


def test_lane_legs_run_only_inside_their_lane_and_no_plan_runs_them(monkeypatch):
    for leg in ("compile_candidates", "record_tape", "tier_s", "replication_civilization"):
        assert leg in hourly_cycle.OWN_CLOCK_LEGS
        for plan in ("core", "heavy", "all", "dept:discovery"):
            assert not hourly_cycle.in_plan(leg, plan), (leg, plan)
    monkeypatch.setattr(hourly_cycle, "_LANE", "tape")
    assert hourly_cycle.in_plan("record_tape", "all")
    assert not hourly_cycle.in_plan("tier_s", "all")


def test_every_own_clock_leg_is_in_exactly_one_lane():
    lane_legs = [leg for legs in hourly_cycle.LANE_LEGS.values() for leg in legs]
    for leg in ("compile_candidates", "record_tape", "tier_s", "replication_civilization"):
        assert lane_legs.count(leg) == 1, leg
    assert set(hourly_cycle._lane_calls()) == set(hourly_cycle.LANE_LEGS)
