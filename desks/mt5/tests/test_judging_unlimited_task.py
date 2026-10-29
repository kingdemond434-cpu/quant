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


# THE RESIDENT BUILD BUDGET IS A MEASURED STEP (2026-10-29, v2 after the audit HOLD): kept only
# when its regime returns more verdicts per wall-hour than the level it left, else reverted.
from datetime import UTC, datetime, timedelta  # noqa: E402

T0 = datetime(2026, 11, 1, tzinfo=UTC)
H = timedelta(hours=1)


def _run(state, hours, *, applied=8640.0, ended=None, sweep_s=None, rows=None):
    return jt.step_build_budget(state, T0 + hours * H, applied, ended, sweep_s, rows)


def test_the_first_pass_measures_the_applied_budget_and_changes_nothing():
    st, b, why = _run(None, 0)
    assert b == 8640.0 and st["phase"] == "measure" and st["regime_start"] is None
    assert "measuring" in why


def test_the_regime_starts_only_at_the_first_sweep_end_after_the_change():
    st, _, _ = _run(None, 0)
    st, b, why = _run(st, 3, ended=T0 - H)                     # the sweep that was running
    assert st["regime_start"] is None and "waiting" in why
    st, b, _ = _run(st, 4, ended=T0 + 4 * H)
    assert st["regime_start"] == (T0 + 4 * H).isoformat() and b == 8640.0


def _measured(rows_per_h: float):
    st, _, _ = _run(None, 0)
    st, _, _ = _run(st, 1, ended=T0 + H)
    st, b, why = _run(st, 25, rows=int(24 * rows_per_h), sweep_s=10 * 3600.0)
    return st, b, why


def test_a_measured_level_steps_up_and_a_step_that_pays_is_kept():
    st, b, why = _measured(100)
    assert b == 8640.0 * jt.BUILD_STEP_FACTOR and st["phase"] == "trial"
    assert st["baseline_vph"] == 100.0 and st["prev_budget_s"] == 8640.0
    st, _, _ = _run(st, 26, ended=T0 + 26 * H)
    st, b2, why = _run(st, 50, rows=24 * 130, sweep_s=10 * 3600.0)
    assert "KEPT" in why and b2 == min(jt.RESIDENT_BUILD_CAP_S, b * jt.BUILD_STEP_FACTOR)


def test_a_step_that_does_not_pay_is_reverted_and_held():
    st, b, _ = _measured(100)
    st, _, _ = _run(st, 26, ended=T0 + 26 * H)
    st, back, why = _run(st, 50, rows=24 * 102, sweep_s=10 * 3600.0)   # +2% < the 5% bar
    assert "REVERTED" in why and back == 8640.0 and st["phase"] == "hold"
    assert jt.fresh_budget_s(0, b, (back, why))[0] == 8640.0          # it comes back down


def test_the_window_waits_for_two_sweeps_and_unmeasured_rows():
    st, _, _ = _run(None, 0)
    st, _, _ = _run(st, 1, ended=T0 + H)
    _, b, why = _run(st, 30, rows=5000, sweep_s=20 * 3600.0)          # 29 h < 2 x 20 h
    assert b == 8640.0 and "of 40.0 h" in why
    _, b, why = _run(st, 45, rows=None, sweep_s=20 * 3600.0)
    assert b == 8640.0 and "UNMEASURED" in why


def test_the_step_never_passes_the_cap_or_the_sealed_floor():
    st = {"budget_s": jt.RESIDENT_BUILD_CAP_S, "phase": "measure", "changed_at": T0.isoformat(),
          "regime_start": T0.isoformat(), "baseline_vph": None, "hold_left": 0}
    st, b, why = _run(st, 50, rows=3000)      # no sweep history: a 2 x 24 h window
    assert b == jt.RESIDENT_BUILD_CAP_S and "cap" in why and st["phase"] == "hold"
    assert jt.fresh_budget_s(0, 8640, (1e9, "x"))[0] == jt.RESIDENT_BUILD_CAP_S
    assert jt.fresh_budget_s(0, 8640, (100.0, "x"))[0] is None         # sealed default


def test_a_finite_task_limit_ignores_the_step():
    assert jt.fresh_budget_s(14400, 8640, (40000.0, "x"))[0] == 8640


def test_the_regime_cut_is_counted_in_the_same_ledger_pass(tmp_path):
    import json
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(json.dumps({"at": (T0 + h * H).isoformat(), "cell": f"c{h}"}) + "\n"
                           for h in range(10)), encoding="utf-8")
    got = jt._verdict_counts(T0 + 10 * H, led,
                             extra_cuts={"build_step": (T0 + 6 * H).isoformat()})
    assert got["counts"]["build_step"] == 4
