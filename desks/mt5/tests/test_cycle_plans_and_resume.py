"""The hourly cycle's core/heavy plans, the daily cycle's step-by-step stamp, the reconciler's
running-unfrozen count and the healer's modern-key freeze -- the 2026-09-16 reliability batch."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "scripts"), str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402
import forward_reconcile  # noqa: E402
import heal_identity_broken_clocks as healer  # noqa: E402
import hourly_cycle as hc  # noqa: E402


def test_plans_partition_the_legs():
    assert hc.in_plan("health", "core") and not hc.in_plan("backtest", "core")
    assert hc.in_plan("backtest", "heavy") and not hc.in_plan("health", "heavy")
    assert hc.in_plan("health", "all") and hc.in_plan("backtest", "all")
    assert "promoter" in hc.CORE_LEGS and "forward_reconcile" in hc.CORE_LEGS
    assert "closed_loop" in hc.CORE_LEGS and "credit_assignment" in hc.CORE_LEGS
    for heavy in ("backtest", "deepen", "daily", "sweep", "search", "external_gauntlet",
                  "refresh_bars", "tape_features", "enrol_clocks", "publish_state"):
        assert heavy not in hc.CORE_LEGS


def test_costed_skips_a_leg_outside_the_plan_without_running_it(monkeypatch):
    monkeypatch.setattr(hc, "HOURLY_PLAN", "core")
    ran: list[str] = []
    out = hc._costed("backtest", lambda: ran.append("x") or {"status": "OK"})
    assert out["status"] == "SKIPPED_BY_PLAN" and out["plan"] == "core" and ran == []
    monkeypatch.setattr(hc, "HOURLY_PLAN", "heavy")
    out = hc._costed("health", lambda: ran.append("x") or {"status": "OK"})
    assert out["status"] == "SKIPPED_BY_PLAN" and ran == []


def test_daily_stamp_survives_a_kill_mid_chain(monkeypatch, tmp_path):
    stamp = tmp_path / "daily_cycle_state.json"
    monkeypatch.setattr(daily_cycle, "STAMP", stamp)
    monkeypatch.setattr(daily_cycle, "_load_stamp", lambda: {})

    def _killed():
        raise KeyboardInterrupt

    monkeypatch.setattr(daily_cycle, "STEPS", (("first", lambda: None), ("second", _killed),
                                               ("third", lambda: None)))
    with pytest.raises(KeyboardInterrupt):
        daily_cycle.main([])
    doc = json.loads(stamp.read_text(encoding="utf-8"))
    assert list(doc["steps"]) == ["first"] and doc["steps"]["first"]["ok"] is True
    assert doc["last_run"]


def test_running_unfrozen_excludes_same_pass_retirements():
    actions = [{"key": "A", "action": "IDENTITY_UNFROZEN"},
               {"key": "A", "action": "RETIRED_ORPHAN"},
               {"key": "B", "action": "IDENTITY_UNFROZEN"},
               {"key": "C", "action": "RETIRED_UNRECONSTRUCTIBLE"}]
    assert forward_reconcile._running_unfrozen(actions) == 1


def test_healer_freezes_modern_keys_from_the_engine_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(healer, "DESK", tmp_path)
    (tmp_path / "reports" / "shadow").mkdir(parents=True)
    key = "EURRUB.carry.continuous#input_symbol=EURRUB"
    shadow = {key: {"status": "ACTIVE", "forward_start": "2026-09-13"},
              "AFG.discovered.asia#band=x": {"status": "RETIRED_ORPHAN"}}
    (tmp_path / "reports" / "shadow" / "shadow_state.json").write_text(json.dumps(shadow),
                                                                        encoding="utf-8")
    calls: list[tuple] = []
    monkeypatch.setattr(healer.reg, "freeze",
                        lambda k, ident, forward_start=None, **kw: calls.append((k, ident)))
    ident = {"symbol": "EURRUB", "selector": "continuous", "family": "carry",
             "params": {"input_symbol": "EURRUB"}, "side": "LONG"}
    n = healer.freeze_unfrozen({"sleeves": {}}, apply=True, identities={key: ident})
    assert n == 1 and calls == [(key, ident)]
    # no engine identity for the key -> left alone, never guessed
    assert healer.freeze_unfrozen({"sleeves": {}}, apply=True, identities={}) == 0


def test_department_plans_partition_the_heavy_legs():
    heavy = [n for n in ("search", "compile_candidates", "deepen", "world_crawler",
                         "external_gauntlet", "state_vector", "refresh_bars", "issue_board",
                         "some_unknown_leg") if n not in hc.CORE_LEGS]
    assert hc.department_of("search") == hc.department_of("compile_candidates") == "discovery"
    assert hc.department_of("deepen") == "discovery"          # one pipeline, one department
    assert hc.department_of("world_crawler") == "intel"
    assert hc.department_of("external_gauntlet") == "validate"
    assert hc.department_of("refresh_bars") == "data"
    assert hc.department_of("some_unknown_leg") == "rest"
    for n in heavy:
        depts = [d for d in hc.DEPARTMENTS if hc.in_plan(n, f"dept:{d}")]
        if n in hc.OWN_CLOCK_LEGS:
            # A LEG WITH ITS OWN TASK IS IN NO DEPARTMENT PLAN, AND STILL HAS A DEPARTMENT.
            # `external_gauntlet` keeps `department_of() == "validate"` -- that is what the leg
            # IS, and every report that groups by department still places it correctly. What
            # changed 2026-09-24 is where it RUNS: `MT5-Gauntlet` is its clock, so the validate
            # resident must not start a second concurrent sweep of the same docket behind the
            # first. The partition invariant below is about legs the cycle schedules, and this
            # leg is no longer one of them.
            assert depts == [], f"{n} has its own clock and must be in no department plan"
            continue
        assert depts == [hc.department_of(n)]                   # exactly one department
    assert not hc.in_plan("health", "dept:meta")                # core legs never in a department
    assert hc.in_plan("auto_x", "dept:rest")
    for d in hc.LEG_DEPARTMENT.values():
        assert d in hc.DEPARTMENTS


def test_auto_legs_under_department_plans_run_only_in_rest(monkeypatch, tmp_path):
    ran: list[str] = []
    monkeypatch.setattr(hc, "_auto_leg", lambda e: ran.append(e["organ"]) or {"exit_code": 0})
    monkeypatch.setattr(hc, "_costed", lambda name, fn: fn())
    f = tmp_path / "auto_legs.json"
    f.write_text(json.dumps({"legs": [
        {"organ": "desks/mt5/research/a.py", "leg": "auto_a", "plan": "core"},
        {"organ": "desks/mt5/research/b.py", "leg": "auto_b", "plan": "heavy"}]}),
        encoding="utf-8")
    assert hc.run_auto_legs("dept:discovery", f)["n"] == 0
    assert hc.run_auto_legs("dept:rest", f)["n"] == 1 and ran == ["desks/mt5/research/b.py"]
