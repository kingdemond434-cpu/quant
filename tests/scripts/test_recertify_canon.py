"""Regression coverage for graceful recertification cost-input failures."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "scripts" / "recertify_canon.py"
SPEC = importlib.util.spec_from_file_location("recertify_canon", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_missing_current_cost_is_unmeasured_not_an_audit_crash() -> None:
    assert module._cost_total({"costs": None}) is None
    assert module._cost_total({}) is None


def test_current_cost_is_reported_from_the_rebuilt_cell_only() -> None:
    class Costs:
        spread_per_lot = 12.3456
        commission_per_lot = 3.5

    assert module._cost_total({"costs": Costs()}) == 15.8456
