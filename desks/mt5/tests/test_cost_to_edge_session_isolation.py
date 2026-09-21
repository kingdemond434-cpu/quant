from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE = Path(__file__).resolve().parents[1] / "research" / "cost_to_edge.py"
sys.path.insert(0, str(MODULE.parent))
SPEC = importlib.util.spec_from_file_location("cost_to_edge_under_test", MODULE)
assert SPEC is not None and SPEC.loader is not None
cost_to_edge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cost_to_edge)


class DetachedTerminal:
    def terminal_info(self):
        return None

    def initialize(self):  # pragma: no cover - calling this is the regression
        raise AssertionError("research telemetry must not launch an MT5 terminal")


def test_detached_research_session_never_autostarts_terminal() -> None:
    result = cost_to_edge.symbol_cost_r("XAUUSD", mt5=DetachedTerminal())

    assert result["measured"] is False
    assert result["why"] == "no terminal attached in research session; autostart prohibited"
