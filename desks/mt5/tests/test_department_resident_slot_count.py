"""The department slot count is DERIVED at every claim, floored at today's three, ONE WAY UP.

2026-11-11: about 22 residents shared three FIFO slots; heavy passes run 9,000-10,600 s, so
Mathlab waited 8.4 h for a turn while the box has measured idle cores. The same night box CPU
read 90-95% with the allocator at ~4.8 cores and money tasks killed at their time limits, so
extra slots need a WINDOWED idle reading that still leaves the terminal and money reserves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK / "research") not in sys.path:
    sys.path.insert(0, str(_DESK / "research"))

import department_resident as dr  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DEPT_CONCURRENT_PASSES", raising=False)
    monkeypatch.setattr(dr, "_IDLE_SAMPLES", dr.deque(maxlen=256))
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dr, "_RECLAIMS_LOGGED", set())


def _fill_window(monkeypatch: pytest.MonkeyPatch, readings: list[float]) -> float:
    it = iter(readings)
    monkeypatch.setattr(dr, "spare_cores", lambda: next(it))
    t0 = 1_000_000.0
    step = dr.IDLE_WINDOW_MIN_SPAN_S / (len(readings) - 1)
    for k in range(len(readings)):
        dr.sample_idle_cores(now=t0 + k * step)
    return t0 + (len(readings) - 1) * step


def test_unmeasured_gives_exactly_todays_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dr, "free_phys_mb", lambda: None)
    count, why = dr.derived_slot_count()
    assert count == 3 and "UNMEASURED" in why
    now = _fill_window(monkeypatch, [16.0] * 6)          # cores measured, memory not
    assert dr.derived_slot_count(now)[0] == 3
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 90_000.0)
    monkeypatch.setattr(dr, "_IDLE_SAMPLES", dr.deque(maxlen=256))
    monkeypatch.setattr(dr, "spare_cores", lambda: 16.0)
    dr.sample_idle_cores(now=5.0)                         # one sample is not a window
    count, why = dr.derived_slot_count(now=5.0)
    assert count == 3 and "UNMEASURED" in why


def test_plenty_of_room_rises_above_three_and_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 1_000_000.0)
    now = _fill_window(monkeypatch, [200.0] * 6)
    count, why = dr.derived_slot_count(now)
    assert count == dr.DEPT_SLOTS_MAX > 3 and "cap" in why
    monkeypatch.setattr(dr, "_IDLE_SAMPLES", dr.deque(maxlen=256))
    monkeypatch.setattr(dr, "free_phys_mb", lambda: dr.MIN_FREE_MB + 5 * dr.PASS_MB_ESTIMATE)
    reserve = dr.IDLE_RESERVE_CORES + dr.MONEY_RESERVE_CORES
    now = _fill_window(monkeypatch, [reserve + 4 * dr.PASS_CORES_ESTIMATE] * 6)
    assert dr.derived_slot_count(now)[0] == 4            # min(by_cores 4, by_memory 5)


def test_the_window_minimum_rules_not_one_quiet_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 1_000_000.0)
    now = _fill_window(monkeypatch, [200.0, 200.0, 1.0, 200.0, 200.0, 200.0])  # a crunch
    count, why = dr.derived_slot_count(now)
    assert count == 3 and "min 1.0" in why


def test_tight_memory_or_busy_cores_never_go_below_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 100.0)
    now = _fill_window(monkeypatch, [200.0] * 6)
    assert dr.derived_slot_count(now)[0] == 3
    monkeypatch.setattr(dr, "_IDLE_SAMPLES", dr.deque(maxlen=256))
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 1_000_000.0)
    now = _fill_window(monkeypatch, [0.5] * 6)            # 90-95% CPU: reserves not free
    assert dr.derived_slot_count(now)[0] == 3


def test_env_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dr, "free_phys_mb", lambda: 1_000_000.0)
    now = _fill_window(monkeypatch, [200.0] * 6)
    monkeypatch.setenv("DEPT_CONCURRENT_PASSES", "2")
    count, why = dr.derived_slot_count(now)
    assert count == 2 and "override" in why
    monkeypatch.setattr(dr, "free_phys_mb", lambda: None)
    monkeypatch.setenv("DEPT_CONCURRENT_PASSES", "11")
    assert dr.derived_slot_count()[0] == 11


def test_admission_at_index_four_uses_the_same_lock_and_reclaim_scheme(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dr, "derived_slot_count", lambda now=None: (5, "test: derived 5"))
    monkeypatch.setattr(dr, "sample_idle_cores", lambda now=None: None)
    held = [dr.wait_for_capacity(f"d{k}", poll_s=1) for k in range(5)]
    assert [h.record["slot"] for h in held] == [0, 1, 2, 3, 4]
    assert held[4].lock_path.name == "dept_capacity_4.lock"
    assert dr.claim_capacity_slot(5, dept="late") is None   # all five busy, in budget
    log = (dr.LOGS / "department_resident.log").read_text(encoding="utf-8")
    assert "to slot 4 of 5 department slots (test: derived 5)" in log
    record = json.loads(dr._holder_path(held[4].lock_path).read_text(encoding="utf-8"))
    record.update(admitted_epoch=record["admitted_epoch"] - dr.holder_budget_s() - 60,
                  pid=626262, pid_create_time=1.0)
    dr._holder_path(held[4].lock_path).write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(dr, "_pid_state", lambda _pid, _ct: "alive")
    monkeypatch.setattr(dr, "_holder_rss", lambda _pid: "512MB")
    kills: list[int] = []
    monkeypatch.setattr(dr, "_kill_tree", lambda pid: kills.append(pid) or {"killed": 1})
    reclaimed = dr.wait_for_capacity("mathlab", poll_s=1)
    assert reclaimed.record["slot"] == 4 and reclaimed.record["generation"] == 1
    assert reclaimed.lock_path.name == "dept_capacity_4.g1.lock" and kills == [626262]
    log = (dr.LOGS / "department_resident.log").read_text(encoding="utf-8")
    assert "RECLAIM department slot 4 generation 0" in log and "holder rss 512MB" in log
    for h in [reclaimed, *held]:
        h.close()
