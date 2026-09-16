"""The bandit's shares are OBEYED (research_budget), the board's epoch is MEASURED
(meta_controller._epoch) and no running clock stays unfrozen (heal_identity_broken_clocks)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "scripts"), str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import heal_identity_broken_clocks as healer  # noqa: E402
import meta_controller  # noqa: E402
import research_budget as rb  # noqa: E402

ARMS = ["new_mechanism", "mutate_survivor", "combine_survivors", "conditional_state_edge",
        "execution_improvement", "exit_improvement", "cross_asset_signal",
        "alt_data_hypothesis", "failure_derived", "model_architecture", "external_screen"]


def _point(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(rb, "BANDIT", tmp_path / "RESEARCH_BANDIT.json")
    monkeypatch.setattr(rb, "OUT", tmp_path / "RESEARCH_BUDGET.json")


def test_budget_is_base_when_bandit_unreadable(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert s == 240 and rec["applied"] is False
    rb.record(rec)
    ok, why = rb.authority()
    assert ok is False and "base budget" in why


def test_budget_scales_by_share_and_clips(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    shares = {a: 1 / 11 for a in ARMS}
    shares["mutate_survivor"] = 0.30
    shares["new_mechanism"] = 0.02
    rb.BANDIT.write_text(json.dumps({"shares": shares}), encoding="utf-8")
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert rec["applied"] is True and 1.4 < rec["factor"] < 1.6 and s == round(240 * rec["factor"])
    # a share of zero floors at 0.5x, never starves the leg
    shares = {a: 0.0 for a in ARMS}
    shares["model_architecture"] = 1.0
    rb.BANDIT.write_text(json.dumps({"shares": shares}), encoding="utf-8")
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert rec["factor"] == rb.FLOOR and s == 120
    # a runaway share caps at 2x
    shares = {a: 0.0 for a in ARMS}
    shares["mutate_survivor"] = 1.0
    rb.BANDIT.write_text(json.dumps({"shares": shares}), encoding="utf-8")
    s, rec = rb.budget_s("alpha_evolution", 240)
    assert rec["factor"] == rb.CEIL and s == 480
    rb.record(rec)
    ok, why = rb.authority()
    assert ok is True and "alpha_evolution=480s" in why


def test_epoch_reads_ledger_since_previous_board(monkeypatch, tmp_path):
    monkeypatch.setattr(meta_controller, "OUT", tmp_path / "META_CONTROLLER.json")
    monkeypatch.setattr(meta_controller, "DESK", tmp_path)
    (tmp_path / "data").mkdir()
    ledger = tmp_path / "data" / "compute_ledger.jsonl"
    meta_controller.OUT.write_text(json.dumps({"at": "2026-09-16T10:00:00+00:00"}),
                                   encoding="utf-8")
    rows = [{"run": "deepen", "at": "2026-09-16T09:30:00+00:00"},      # before the board: ignored
            {"run": "deepen", "at": "2026-09-16T10:30:00+00:00"},
            {"run": "forward_reconcile", "at": "2026-09-16T10:40:00+00:00"}]
    ledger.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    e = meta_controller._epoch(["deepen_existing", "gather_forward"])
    assert e["complete"] is True and e["missing"] == []
    e = meta_controller._epoch(["deepen_existing", "gather_forward", "run_falsifier"])
    assert e["complete"] is False and e["missing"] == ["run_falsifier"]
    assert meta_controller._epoch([])["complete"] is None


def test_legacy_identity_is_parsed_from_the_key():
    i = healer.legacy_identity("XAUUSD.london_am", {})
    assert i == {"symbol": "XAUUSD", "selector": "london_am", "family": "session_range_breakout",
                 "side": "LONG", "params": {}}
    i = healer.legacy_identity("CADJPY.asia.FAILED_BREAK", {"side": "short"})
    assert i["state"] == "FAILED_BREAK" and i["side"] == "SHORT"
    assert healer.legacy_identity("session_range_breakout#abc", {}) is None
    assert healer.legacy_identity("EURUSD.M15.k=1", {}) is None


def test_freeze_unfrozen_freezes_only_running_unfrozen_legacy_clocks(monkeypatch, tmp_path):
    monkeypatch.setattr(healer, "DESK", tmp_path)
    (tmp_path / "reports" / "shadow").mkdir(parents=True)
    shadow = {"XAUUSD.london_am": {"status": "ACTIVE", "forward_start": "2026-08-01"},
              "GBPJPY.asia": {"status": "RETIRED"},
              "EURUSD.asia": {"status": "ACTIVE"},
              "family#modern": {"status": "ACTIVE"}}
    (tmp_path / "reports" / "shadow" / "shadow_state.json").write_text(json.dumps(shadow),
                                                                        encoding="utf-8")
    registry = {"sleeves": {"EURUSD.asia": {"identity": {"symbol": "EURUSD"}}}}
    calls: list[tuple] = []
    monkeypatch.setattr(
        healer.reg, "freeze",
        lambda key, ident, forward_start=None, **kw: calls.append((key, ident, forward_start)))
    assert healer.freeze_unfrozen(registry, apply=False) == 1 and calls == []
    assert healer.freeze_unfrozen(registry, apply=True) == 1
    assert calls == [("XAUUSD.london_am",
                      {"symbol": "XAUUSD", "selector": "london_am",
                       "family": "session_range_breakout", "side": "LONG", "params": {}},
                      "2026-08-01")]
