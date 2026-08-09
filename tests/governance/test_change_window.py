"""L1.38 sterile cockpit -- money-path freeze inside launch/first-fills/rail windows only."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.check_change_window import build_report, touches_money_path

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def _launch(root: Path, days_ago: float, fills: int = 50) -> None:
    (root / "data/moat/execution_tape").mkdir(parents=True, exist_ok=True)
    (root / "data/moat/execution_tape/cashcarry_trades.jsonl").write_text(
        "\n".join('{"x":1}' for _ in range(fills)), "utf-8")
    # R0333: the executor publishes its book state here, not to the phantom cashcarry_state.json.
    (root / "data/cashcarry_positions.json").write_text(
        '{"last_risk_action": "normal", "positions": {}}', "utf-8")
    at = (NOW - timedelta(days=days_ago)).isoformat()
    (root / "data/capital_events.jsonl").write_text(
        json.dumps({"at": at, "kind": "DEPOSIT"}) + "\n", "utf-8")


def test_pre_launch_is_open_even_with_money_path_change(tmp_path):
    rep = build_report(tmp_path, NOW, paths=["libs/execution/binance_live.py"])
    assert rep["status"] == "OPEN"
    assert rep["verdict"] == "ALLOW"          # nothing live can be harmed pre-launch


def test_launch_week_blocks_money_path_improvement(tmp_path):
    _launch(tmp_path, days_ago=2)
    rep = build_report(tmp_path, NOW, paths=["libs/risk/sizing.py"])
    assert rep["status"] == "STERILE"
    assert rep["verdict"] == "BLOCK"
    assert any("GATE0_LAUNCH" in w for w in rep["windows_active"])


def test_research_change_is_allowed_during_the_freeze(tmp_path):
    _launch(tmp_path, days_ago=2)
    rep = build_report(tmp_path, NOW, paths=["scripts/run_deep_sweep.py", "ops/kimi.txt"])
    assert rep["status"] == "STERILE"         # window is live...
    assert rep["verdict"] == "ALLOW"          # ...but a non-money-path change is never blocked


def test_first_fills_window_blocks(tmp_path):
    _launch(tmp_path, days_ago=10, fills=5)   # past launch week, but < 20 fills
    rep = build_report(tmp_path, NOW, paths=["libs/execution/binance_live.py"])
    assert rep["verdict"] == "BLOCK"
    assert any("FIRST_FILLS" in w for w in rep["windows_active"])


def test_rail_breach_window_blocks(tmp_path):
    _launch(tmp_path, days_ago=30, fills=100)
    (tmp_path / "data/cashcarry_positions.json").write_text(
        '{"last_risk_action": "flatten", "positions": {}}', "utf-8")
    rep = build_report(tmp_path, NOW, paths=["scripts/run_cashcarry_executor.py"])
    assert rep["verdict"] == "BLOCK"
    assert any("RAIL_BREACH" in w for w in rep["windows_active"])


def test_settled_book_opens_the_window(tmp_path):
    _launch(tmp_path, days_ago=30, fills=100)  # past launch, plenty of fills, no rail
    rep = build_report(tmp_path, NOW, paths=["libs/execution/binance_live.py"])
    assert rep["status"] == "OPEN"
    assert rep["verdict"] == "ALLOW"


def test_freeze_is_improvements_not_repairs_in_the_law_text():
    src = Path("scripts/check_change_window.py").read_text("utf-8")
    assert "freezes IMPROVEMENTS, never REPAIRS" in src
    doc = Path("ops/principal_doctrine.txt").read_text("utf-8")
    assert "IMPROVEMENTS, NEVER REPAIRS" in doc


def test_money_path_matcher():
    assert touches_money_path(["libs/risk/gate.py"]) == ["libs/risk/gate.py"]
    assert touches_money_path(["docs/research/x.md"]) == []
