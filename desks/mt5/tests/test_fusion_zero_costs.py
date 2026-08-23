from __future__ import annotations

from mt5desk.engine import Costs
from research.validate_fusion import fusion_costs


def test_fusion_zero_published_commission_is_the_default() -> None:
    costs = Costs.from_symbol({
        "median_spread_pts": 16.0,
        "tick_size": 0.01,
        "contract_size": 100.0,
    }, mult=2.0)
    assert costs.commission_per_lot == 2.25
    assert costs.per_oz_roundtrip() == 32.0 + 4.5


def test_stress_widens_spread_but_does_not_invent_commission() -> None:
    meta = {"median_spread_pts": 16.0, "tick_size": 0.01, "contract_size": 100.0}
    baseline = Costs.from_symbol(meta, mult=2.0)
    stress = Costs.from_symbol(meta, mult=6.0)
    assert stress.spread_per_lot == 3.0 * baseline.spread_per_lot
    assert stress.commission_per_lot == baseline.commission_per_lot == 2.25


def test_live_fusion_profile_keeps_spread_units_and_round_trip() -> None:
    costs = fusion_costs("XAUUSD", {"XAUUSD": {
        "live_spread_pts": 16.0,
        "live_tick_size": 0.01,
        "live_contract": 100.0,
    }})
    assert costs.spread_per_lot == 32.0
    assert costs.per_oz_roundtrip() == 36.5
