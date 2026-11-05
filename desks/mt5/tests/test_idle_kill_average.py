"""A wedged tree's background jitter can no longer reset the idle clock one interval at a time."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import run_sharded_gauntlet as rsg  # noqa: E402


def _run(per_minute: list[float]) -> rsg._TreeProgress:
    tr = rsg._TreeProgress(0.0, max_gap_s=180.0)
    cpu = 0.0
    for i, burn in enumerate(per_minute, start=1):
        cpu += burn
        tr.update({"cpu": {1: cpu}}, 60.0 * i)
    return tr


def test_a_jittering_wedged_tree_accrues_idleness() -> None:
    # 31752's measured pattern: ~0.65 cpu-s a minute on average, every third minute a 1.3 s burst
    tr = _run([0.3, 0.35, 1.3] * 20)                     # one hour at ~0.011 cores
    assert tr.idle_s(3600.0) >= 3000.0                   # the 40-minute idle kill would fire


def test_the_old_per_interval_rule_would_have_reset_on_every_burst() -> None:
    # documents the defect: each 1.3 s minute alone clears 0.02 cores x 60 s = 1.2 s
    assert rsg.NO_PROGRESS_CORES <= 1.3 / 60.0


def test_a_working_tree_resets_within_its_first_interval() -> None:
    tr = _run([0.3, 0.35, 0.3] * 10 + [30.0])            # 30 quiet minutes, then real work
    assert tr.idle_s(31 * 60.0) == 0.0


def test_a_real_burst_after_a_long_quiet_stretch_is_progress() -> None:
    # 39 jitter minutes, then 20 cpu-s in one minute: diluted over the stretch it is 0.0085 cores
    tr = _run([0.3, 0.35, 1.3] * 13 + [20.0])
    assert tr.idle_s(40 * 60.0) == 0.0


def test_a_late_io_burst_is_progress() -> None:
    tr = rsg._TreeProgress(0.0, max_gap_s=180.0)
    for i in range(1, 36):
        tr.update({"cpu": {1: 0.0}, "io": {1: 4096.0 * i}}, 60.0 * i)
    assert tr.idle_s(35 * 60.0) >= 30 * 60.0
    tr.update({"cpu": {1: 0.0}, "io": {1: 50e6}}, 36 * 60.0)      # 50 MB in one minute
    assert tr.idle_s(36 * 60.0) == 0.0


def test_the_burst_bar_sits_above_the_measured_jitter() -> None:
    assert rsg.BURST_CORES > 1.3 / 60.0


def test_steady_light_work_above_the_floor_is_never_idle() -> None:
    tr = _run([1.5] * 60)                                 # 0.025 cores, just over the floor
    assert tr.idle_s(3600.0) == 0.0


def test_a_gap_is_a_fresh_baseline_and_forgets_the_stretch() -> None:
    tr = rsg._TreeProgress(0.0, max_gap_s=180.0)
    tr.update({"cpu": {1: 0.1}}, 60.0)
    assert tr.update({"cpu": {1: 0.2}}, 1000.0) is None and tr.idle_s(1000.0) == 0.0
