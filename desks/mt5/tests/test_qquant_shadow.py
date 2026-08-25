from __future__ import annotations

import inspect
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "research", DESK.parent.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import daily_cycle  # noqa: E402
from qquant_shadow import _max_drawdown  # noqa: E402


def test_daily_cycle_wires_qquant_shadow_before_promotion() -> None:
    names = [name for name, _ in daily_cycle.STEPS]
    assert names.index("shadow") < names.index("qquant_shadow") < names.index("promoter")


def test_forward_drawdown_is_path_aware() -> None:
    assert _max_drawdown([1.0, -0.5, -1.0, 2.0]) == -1.5


def test_qquant_shadow_has_no_order_authority() -> None:
    source = (DESK / "research" / "qquant_shadow.py").read_text(encoding="utf-8")
    assert '"order_authority": False' in source
    assert "promotion_authority" in source
    assert "FULL_TRADES = 50" in source and "MIN_DAYS = 14" in source


def test_qquant_shadow_exposes_zero_trade_observation_evidence() -> None:
    source = inspect.getsource(__import__("qquant_shadow").main)
    assert '"forward_bars_evaluated"' in source
    assert '"forward_decision_bars"' in source
    assert '"forward_eligible_signals"' in source
    assert '"last_evaluated_bar"' in source
    assert '"source_gate_policy_valid"' in source
    assert "return 1" in source
    assert "prefer_promotion_authority=True" in source
