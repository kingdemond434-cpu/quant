"""An unlimited scheduler deadline must not resurrect an obsolete kill limit."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import judging_throughput as jt


def test_zero_task_limit_is_a_measurement(monkeypatch):
    monkeypatch.setattr(jt.sys, 'platform', 'win32')
    monkeypatch.setattr(jt.subprocess, 'run', lambda *a, **k:
                        subprocess.CompletedProcess(a, 0, '<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>'))
    assert jt.task_time_limit_s() == 0


@pytest.mark.parametrize('prior,expected', [(8640, 8640), (None, None),
                                          (100, None), (float('inf'), None),
                                          (float('nan'), None)])
def test_unlimited_task_keeps_a_finite_bounded_build_budget(prior, expected):
    budget, why = jt.fresh_budget_s(0, prior)
    assert budget == expected
    assert 'unlimited' in why


def test_unreadable_limit_remains_distinct():
    budget, why = jt.fresh_budget_s(None, 8640)
    assert budget is None
    assert 'unreadable' in why


def test_finite_limit_still_uses_existing_policy():
    assert jt.fresh_budget_s(14400)[0] == 8640


# THE RESIDENT BUDGET IS SIZED FROM ITS OWN SWEEP (2026-10-29): the PT0S branch froze it at
# 8,640 s, 60% of a limit that no longer exists, while the rest of each sweep ran for hours.
def _times(**phases):
    return {"phases": {k: list(v) for k, v in phases.items()}, "sweeps": []}


def test_an_unlimited_task_sizes_the_build_from_measured_sweep_overhead():
    times = _times(plan=[1500, 1496], plan_handoff=[160], build_shards=[9000, 12000, 11000],
                   collect_and_cut=[500], rule_shards=[100], merge_and_publish=[2000, 3000])
    overhead, _ = jt.resident_overhead_s(times)
    assert overhead == 1498 + 160 + 11000 + 500 + 100 + 2500
    budget, why = jt.fresh_budget_s(0, 8640, times)
    assert budget == jt.RESIDENT_BUILD_SHARE * overhead
    assert "unlimited" in why and "build_shards 11000s" in why


def test_the_resident_budget_is_capped_and_never_falls_below_what_is_applied():
    huge = _times(build_shards=[90000], merge_and_publish=[50000])
    assert jt.fresh_budget_s(0, 8640, huge)[0] == jt.RESIDENT_BUILD_CAP_S
    small = _times(build_shards=[1000], merge_and_publish=[500])
    assert jt.fresh_budget_s(0, 8640, small)[0] == 8640          # one way: up only
    # with nothing applied, 2 x 1,500 s = 3,000 s is above the sealed 2,700 s and is published
    assert jt.fresh_budget_s(0, None, small)[0] == 3000
    tiny = _times(build_shards=[600], merge_and_publish=[400])
    assert jt.fresh_budget_s(0, None, tiny)[0] is None           # 2,000 s: the sealed default


@pytest.mark.parametrize("times", [None, {}, {"phases": "x"}, _times(build_shards=[9000]),
                                   _times(merge_and_publish=[5000]),
                                   _times(build_shards=[float("nan"), -1, True],
                                          merge_and_publish=[5000])])
def test_unmeasured_overhead_keeps_the_retained_budget(times):
    budget, why = jt.fresh_budget_s(0, 8640, times)
    assert budget == 8640 and "UNMEASURED" in why


def test_a_finite_task_limit_ignores_the_sweep_history():
    times = _times(build_shards=[90000], merge_and_publish=[50000])
    assert jt.fresh_budget_s(14400, 8640, times)[0] == 8640
