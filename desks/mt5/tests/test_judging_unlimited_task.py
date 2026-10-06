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
