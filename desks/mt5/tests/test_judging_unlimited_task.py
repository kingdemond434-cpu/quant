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


# THE RESIDENT BUILD BUDGET IS A MEASURED STEP (2026-10-29, v2.1 after two audit HOLDs): kept only
# when its regime returns more verdicts per wall-hour of WHOLE sweeps than the level it left.
from datetime import UTC, datetime, timedelta  # noqa: E402

T0 = datetime(2026, 11, 1, tzinfo=UTC)
H = timedelta(hours=1)


class Box:
    """A resident that publishes `rows` changed verdicts at the end of every `hours`-long sweep,
    driven through the controller exactly as `run` drives it, one pass per hour."""

    def __init__(self) -> None:
        self.t, self.ledger, self.last_end, self.state, self.budget = T0, [], None, None, None
        self.whys: list[str] = []

    def rows_between(self, cuts):
        if not cuts:
            return None
        lo, hi = (datetime.fromisoformat(cuts[k]) for k in ("build_step_lo", "build_step_hi"))
        return sum(1 for at in self.ledger if lo <= at) - sum(1 for at in self.ledger if hi <= at)

    def pass_(self, applied=8640.0):
        st = jt.observe_sweep_end(self.state, self.last_end)
        rows = self.rows_between(jt.regime_cuts(st))
        self.state, self.budget, why = jt.step_build_budget(st, self.t, applied, rows)
        self.whys.append(why)

    def sweeps(self, n, hours, rows):
        for _ in range(n):
            for _h in range(hours):
                self.t += H
                self.pass_()
            stamp = self.t - timedelta(seconds=30)        # rows land before the sweep's end stamp
            self.ledger.extend([stamp] * rows)
            self.last_end = self.t
            self.pass_()                                  # the hourly pass that sees this end


def test_the_first_pass_measures_the_applied_budget_and_changes_nothing():
    st, b, why = jt.step_build_budget(None, T0, 8640.0, None)
    assert b == 8640.0 and st["phase"] == "measure" and "measuring" in why


def test_the_sweep_running_at_a_change_is_not_counted():
    st, _, _ = jt.step_build_budget(None, T0, 8640.0, None)
    st = jt.observe_sweep_end(st, T0 - H)                    # ended before the change
    assert st["regime_start"] is None
    st = jt.observe_sweep_end(st, T0 + 3 * H)
    assert st["regime_start"] == (T0 + 3 * H).isoformat() and st["sweep_ends"] == []
    assert jt.regime_cuts(st) is None
    st = jt.observe_sweep_end(st, T0 + 3 * H)                # the same end seen again
    assert st["sweep_ends"] == []


def test_a_longer_sweep_that_truly_pays_is_kept_not_lost_to_publish_phase():
    """The audit's probe: 30 h / 6,000-row sweeps (200 vph), then a 1.5x trial of 33 h /
    7,000-row sweeps (212 vph, +6%). A fixed 60 h window read 116.7 and reverted it."""
    box = Box()
    box.pass_()                                     # bootstrap at 8,640
    box.sweeps(1, 30, 6000)                         # the straddling sweep starts the regime
    box.sweeps(2, 30, 6000)                         # two whole sweeps: measured, step up
    assert box.budget == 8640.0 * jt.BUILD_STEP_FACTOR, box.whys[-1]
    assert box.state["baseline_vph"] == 200.0
    box.sweeps(1, 33, 7000)                         # straddles the step: starts the trial
    box.sweeps(2, 33, 7000)
    assert "KEPT" in box.whys[-1], box.whys[-1]


def test_a_longer_sweep_that_does_not_pay_is_reverted():
    box = Box()
    box.pass_()
    box.sweeps(3, 30, 6000)
    stepped = box.budget
    box.sweeps(3, 45, 9000)                         # 200 vph again: no gain
    assert "REVERTED" in box.whys[-1] and box.budget == 8640.0 < stepped
    assert box.state["phase"] == "hold"
    assert jt.fresh_budget_s(0, stepped, (box.budget, "x"))[0] == 8640.0


def test_a_regime_waits_for_two_whole_sweeps_and_a_day():
    box = Box()
    box.pass_()
    box.sweeps(2, 10, 5000)                         # start + one whole sweep
    assert box.budget == 8640.0 and "1 of 2 whole sweeps" in box.whys[-1]
    box.sweeps(1, 10, 5000)                         # two whole sweeps, but only 20 h
    assert box.budget == 8640.0 and "2 of 2" in box.whys[-1]
    box.sweeps(1, 10, 5000)
    assert box.budget > 8640.0


def test_unmeasured_rows_never_step():
    st = {"budget_s": 8640.0, "phase": "measure", "changed_at": T0.isoformat(),
          "regime_start": T0.isoformat(),
          "sweep_ends": [(T0 + 20 * H).isoformat(), (T0 + 40 * H).isoformat()]}
    _, b, why = jt.step_build_budget(st, T0 + 41 * H, 8640.0, None)
    assert b == 8640.0 and "UNMEASURED" in why


def test_the_step_never_passes_the_cap_or_the_sealed_floor():
    st = {"budget_s": jt.RESIDENT_BUILD_CAP_S, "phase": "measure", "changed_at": T0.isoformat(),
          "regime_start": T0.isoformat(),
          "sweep_ends": [(T0 + 20 * H).isoformat(), (T0 + 40 * H).isoformat()]}
    st, b, why = jt.step_build_budget(st, T0 + 41 * H, 8640.0, 4000)
    assert b == jt.RESIDENT_BUILD_CAP_S and "cap" in why and st["phase"] == "hold"
    assert st["regime_start"] is None                      # the next window starts at a sweep end
    assert jt.fresh_budget_s(0, 8640, (1e9, "x"))[0] == jt.RESIDENT_BUILD_CAP_S
    assert jt.fresh_budget_s(0, 8640, (100.0, "x"))[0] is None


def test_a_finite_task_limit_ignores_the_step():
    assert jt.fresh_budget_s(14400, 8640, (40000.0, "x"))[0] == 8640


def test_the_regime_bounds_are_counted_in_the_same_ledger_pass(tmp_path):
    import json
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join(json.dumps({"at": (T0 + h * H).isoformat(), "cell": f"c{h}"}) + "\n"
                           for h in range(10)), encoding="utf-8")
    st = {"budget_s": 8640.0, "regime_start": (T0 + 2 * H).isoformat(),
          "sweep_ends": [(T0 + 6 * H).isoformat()]}
    got = jt._verdict_counts(T0 + 10 * H, led, extra_cuts=jt.regime_cuts(st))["counts"]
    assert got["build_step_lo"] - got["build_step_hi"] == 4     # hours 3,4,5,6: (start, end]
