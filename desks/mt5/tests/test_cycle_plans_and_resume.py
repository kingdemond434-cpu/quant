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
