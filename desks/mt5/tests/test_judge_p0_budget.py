"""Judge P0 (2026-11-25): the build budget is bounded by E10 (a sweep ends inside 6 h).

judge_build_step.json reached 43,200 s (the old 12 h cap) while the trials measured LOWER
verdicts/hour than 8,640 s had; the 11-24 sweep then ran 17.5 h and was lost without a publish.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import judging_throughput as jt

T0 = datetime(2026, 11, 1, tzinfo=UTC)
H = timedelta(hours=1)


@pytest.fixture(autouse=True)
def _times(monkeypatch, tmp_path):
    f = tmp_path / "judge_phase_times.json"
    monkeypatch.setattr(jt, "PHASE_TIMES", f)
    jt._APPLY_DEADLINE[:] = []
    return f


def _write(f: Path, phases: dict) -> None:
    f.write_text(json.dumps({"phases": phases}), "utf-8")


def test_the_cap_plus_the_measured_overhead_never_exceeds_the_e10_window(_times) -> None:
    """THE PREVENTION FENCE: whatever this box measured, cap + overhead <= 6 h unless the cap is
    already at the sealed floor (and then it says so)."""
    assert jt.RESIDENT_BUILD_CAP_S <= jt.E10_SWEEP_WINDOW_S == 6 * 3600.0
    for per in (None, 1.0, 600.0, 2000.0, 4000.0, 9000.0):
        if per is None:
            _times.unlink(missing_ok=True)
        else:
            _write(_times, {p: [per] * 3 for p in jt.NON_BUILD_PHASES})
        cap, basis = jt.build_cap_s()
        assert cap >= jt.SEALED_FRESH_BUDGET_SEC
        assert basis["floored"] or cap + basis["overhead_s"] <= jt.E10_SWEEP_WINDOW_S + 1e-6
        assert cap <= jt.RESIDENT_BUILD_CAP_S


def test_unmeasured_phases_take_the_declared_seeds(_times) -> None:
    cap, basis = jt.build_cap_s()
    assert basis["overhead_s"] == sum(jt.E10_SEED_PHASE_S.values())
    assert cap == jt.E10_SWEEP_WINDOW_S - sum(jt.E10_SEED_PHASE_S.values())


def test_one_pathological_merge_does_not_set_the_bound_for_good(_times) -> None:
    _write(_times, {"plan": [600.0] * 5, "plan_handoff": [300.0] * 5,
                    "collect_and_cut": [900.0] * 5, "rule_shards": [90.0] * 5,
                    "merge_and_publish": [4000.0, 4200.0, 51198.0, 4100.0, 3900.0]})
    cap, basis = jt.build_cap_s()
    assert basis["phases"]["merge_and_publish"]["s"] == 4000.0       # the median
    assert cap == jt.E10_SWEEP_WINDOW_S - (600 + 300 + 900 + 90 + 4000)


def test_an_over_cap_budget_is_clamped_on_the_next_read_and_the_env_follows(_times) -> None:
    cap = jt.build_cap_s()[0]
    st = {"budget_s": 43200.0, "phase": "hold", "hold_left": 2, "changed_at": T0.isoformat(),
          "regime_start": T0.isoformat(), "sweep_ends": [(T0 + 20 * H).isoformat()]}
    st, b, why = jt.step_build_budget(st, T0 + 21 * H, 43200.0, 5000)
    assert b == cap and st["budget_s"] == cap and "CLAMPED" in why
    assert st["regime_start"] is None and st["phase"] == "hold"
    assert jt.fresh_budget_s(0, 43200.0)[0] == cap                   # retain path clamps too
    assert jt.fresh_budget_s(0, 43200.0, (43200.0, "x"))[0] == cap


def test_a_floored_clamp_still_overwrites_the_stale_machine_value() -> None:
    base = {"workers": 15, "shards": 15, "memory_budget_mb": 1, "headroom_cap_mb": 1,
            "per_worker_mb": 1, "fresh_budget_s": None, "fresh_budget_e10_floor": True}
    assert jt.env_for(base)["GAUNTLET_FRESH_BUDGET_SEC"] == str(int(jt.SEALED_FRESH_BUDGET_SEC))


def test_a_trial_must_beat_the_best_rate_any_smaller_budget_measured(_times) -> None:
    """The box's own history, 11-18..11-21: holds at 19,440 s collapsed to 321 and 247 v/h, the
    29,160 s trial measured 468 v/h -- above that baseline, far below 8,640 s's 3,255 -- and was
    KEPT, stepping to 43,200 s. It is now REVERTED."""
    _write(_times, {p: [100.0] for p in jt.NON_BUILD_PHASES})          # cap above 29,160 s
    hist = [{"budget_s": 8640.0, "verdicts_per_hour": 3255.0},
            {"budget_s": 12960.0, "verdicts_per_hour": 1202.0},
            {"budget_s": 19440.0, "verdicts_per_hour": 321.0},
            {"budget_s": 19440.0, "verdicts_per_hour": 247.0}]
    st = {"budget_s": 29160.0, "prev_budget_s": 19440.0, "phase": "trial",
          "baseline_vph": 247.0, "changed_at": T0.isoformat(), "regime_start": T0.isoformat(),
          "sweep_ends": [(T0 + 12 * H).isoformat(), (T0 + 26.4 * H).isoformat()],
          "history": hist}
    st, b, why = jt.step_build_budget(st, T0 + 27 * H, 29160.0, int(468 * 26.4))
    assert "REVERTED" in why and b == 19440.0 and st["phase"] == "hold"
    # and a trial that genuinely beats every smaller budget is still KEPT (two-sided)
    st = {"budget_s": 12960.0, "prev_budget_s": 8640.0, "phase": "trial",
          "baseline_vph": 3000.0, "changed_at": T0.isoformat(), "regime_start": T0.isoformat(),
          "sweep_ends": [(T0 + 12 * H).isoformat(), (T0 + 25 * H).isoformat()],
          "history": [{"budget_s": 8640.0, "verdicts_per_hour": 3255.0}]}
    st, b, why = jt.step_build_budget(st, T0 + 26 * H, 12960.0, 4000 * 25)
    assert "KEPT" in why and b > 12960.0
