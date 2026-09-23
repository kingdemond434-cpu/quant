"""Cost-basis fallback tests for the MT5 zero-capital forward engine."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))


def test_frozen_costs_requires_the_complete_admission_basis(monkeypatch) -> None:
    import sleeve_registry

    from research import shadow_forward

    monkeypatch.setattr(sleeve_registry, "frozen_cost_fields", lambda _key: {
        "spread_per_lot": 912.0,
        "commission_per_lot": 3.5,
        "contract_oz": 100_000.0,
        "quote_per_account": 18.56843,
    })
    cost = shadow_forward.frozen_costs("EURZAR.overnight_gap_decay.asia")
    assert cost is not None
    assert cost.spread_per_lot == 912.0
    assert cost.quote_per_account == 18.56843

    monkeypatch.setattr(sleeve_registry, "frozen_cost_fields", lambda _key: {
        "spread_per_lot": 912.0,
    })
    assert shadow_forward.frozen_costs("EURZAR.overnight_gap_decay.asia") is None
