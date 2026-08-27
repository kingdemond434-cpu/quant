"""The runner that was missing: shadow -> promoter -> markout, once per UTC day.

Nine validated candidates sat in shadow_forward.SLEEVES with nothing to execute them. The
supervisor runs one-shot DONE-marker research jobs and hourly_cycle does health/mine/report;
neither ever called the three processes that move an edge toward capital. This pins the runner AND
its wiring, because a runner nothing calls is the same defect one level up.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402


@pytest.fixture
def cyc(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    calls: list[str] = []

    def step(name, boom=False):
        def fn():
            calls.append(name)
            if boom:
                raise RuntimeError(f"{name} exploded")
        return fn

    return type("C", (), {"calls": calls, "step": staticmethod(step),
                          "stamp": tmp_path / "daily_cycle_state.json"})


def _steps(cyc, *names, boom=()):
    return tuple((n, cyc.step(n, boom=n in boom)) for n in names)


def test_the_three_steps_run_in_order(cyc, monkeypatch):
    """Order is load-bearing: the promoter reads the state shadow has just written, so running it
    first decides today on yesterday's evidence."""
    monkeypatch.setattr(daily_cycle, "STEPS", _steps(cyc, "shadow", "promoter", "markout"))
    assert daily_cycle.main([]) == 0
    assert cyc.calls == ["shadow", "promoter", "markout"]


def test_the_real_step_order_is_shadow_then_promoter_then_markout():
    """Pins the module's own STEPS. The cycle has since grown legitimate stages (curve
    compendium, reconciler, execution, portfolio, decay, dashboard export) -- the LAW here was
    never "exactly three steps", it is the ORDER: evidence accrues (shadow) before anyone
    promotes on it, and markouts are measured after the promoter acts, never instead of it."""
    names = [n for n, _ in daily_cycle.STEPS]
    for required in ("shadow", "promoter", "markout"):
        assert required in names, f"the {required} step vanished from the daily cycle"
    assert names.index("shadow") < names.index("promoter") < names.index("markout")


def test_it_runs_once_per_utc_day(cyc, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STEPS", _steps(cyc, "shadow", "promoter", "markout"))
    daily_cycle.main([])
    daily_cycle.main([])
    daily_cycle.main([])
    assert cyc.calls == ["shadow", "promoter", "markout"], "the cycle ran more than once today"


def test_force_reruns_the_day(cyc, monkeypatch):
    """The explicit way back in after fixing a failed step."""
    monkeypatch.setattr(daily_cycle, "STEPS", _steps(cyc, "shadow"))
    daily_cycle.main([])
    daily_cycle.main(["--force"])
    assert cyc.calls == ["shadow", "shadow"]


def test_a_failing_step_does_not_abort_the_rest(cyc, monkeypatch):
    """THE POINT. Shadow needs a live MT5 terminal and fails on a research box; markout reads
    files and does not. Aborting on the first failure would let a closed laptop silently suppress
    the execution measurement -- an unmeasured failure being the thing this desk least wants."""
    monkeypatch.setattr(daily_cycle, "STEPS",
                        _steps(cyc, "shadow", "promoter", "markout", boom=("shadow",)))
    rc = daily_cycle.main([])
    assert cyc.calls == ["shadow", "promoter", "markout"]
    assert rc == 1, "a failed step must be visible in the exit code"


def test_a_failure_is_recorded_not_swallowed(cyc, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STEPS",
                        _steps(cyc, "shadow", "promoter", boom=("shadow",)))
    daily_cycle.main([])
    steps = json.loads(cyc.stamp.read_text(encoding="utf-8"))["steps"]
    assert steps["shadow"]["ok"] is False
    assert "RuntimeError" in steps["shadow"]["error"]
    assert steps["promoter"]["ok"] is True


def test_a_failed_day_is_still_stamped(cyc, monkeypatch):
    """Stamping only on success would retry a broken step every hour, and a step that fails at
    09:00 because the terminal is shut fails identically at 10:00. One honest failure, not a log
    full of them; --force is the deliberate retry."""
    monkeypatch.setattr(daily_cycle, "STEPS", _steps(cyc, "shadow", boom=("shadow",)))
    daily_cycle.main([])
    n_after_first = len(cyc.calls)
    daily_cycle.main([])
    assert len(cyc.calls) == n_after_first


def test_the_hourly_loop_actually_calls_it():
    """A runner nothing calls is the same defect one level up -- which is exactly how shadow,
    promoter and markout came to be scheduled nowhere at all."""
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert "daily_cycle" in src, (
        "hourly_cycle does not invoke daily_cycle -- the three processes that move an edge toward "
        "capital are unscheduled again")
