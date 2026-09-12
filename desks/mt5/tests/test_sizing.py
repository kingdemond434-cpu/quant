"""mt5desk.sizing -- the 3%-base risk engine (principal order 2026-08-25).

Defect this guards (promotion rule 13): promoted_lot() sized EVERY promoted sleeve with
gold's hardcoded parameters (DIST_USD=19.1, CONTRACT_OZ=100, FX_EUR), so a promoted JPY
cross would have carried gold's risk per lot, not 3% of equity. risk_lot() must derive
risk purely from the trade's stop distance and the broker's own tick economics.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk.sizing import (  # noqa: E402
    BASE_RISK_FRAC,
    MAX_RISK_FRAC,
    authority_ramp,
    clamp_risk_frac,
    risk_lot,
)


def test_three_percent_of_equity_is_three_percent() -> None:
    # equity 10_000, stop 0.005 price units, tick_value 1.0 per tick of 0.0001
    # -> per-lot risk = 0.005 * (1.0/0.0001) = 50 -> target 300*0.25(ramp) = 75 -> 1.5 lots
    lot = risk_lot(equity=10_000, sl_dist_price=0.005, tick_value=1.0, tick_size=0.0001,
                   volume_min=0.01, volume_step=0.01, volume_max=100.0)
    assert lot == 1.5
    per_lot_risk = 0.005 * (1.0 / 0.0001)
    assert abs(lot * per_lot_risk - 10_000 * BASE_RISK_FRAC * 0.25) < per_lot_risk * 0.01


def test_rounds_down_never_oversizes() -> None:
    lot = risk_lot(equity=10_000, sl_dist_price=0.005, tick_value=1.0, tick_size=0.0001,
                   volume_min=0.01, volume_step=0.4, volume_max=100.0)
    assert lot == 1.2  # 1.5 raw floored to the 0.4 step, never up


def test_ramp_scales_risk_not_just_lots() -> None:
    kw = dict(equity=10_000, sl_dist_price=0.005, tick_value=1.0, tick_size=0.0001,
              volume_min=0.01, volume_step=0.01, volume_max=100.0)
    assert risk_lot(**kw, live_n=0) * 2 == risk_lot(**kw, live_n=50)
    assert risk_lot(**kw, live_n=50) * 2 == risk_lot(**kw, live_n=200)
    assert authority_ramp(0) == 0.25 and authority_ramp(199) == 0.5 and authority_ramp(200) == 1.0


def test_the_venue_minimum_overrides_the_risk_target() -> None:
    """REVERSED BY THE PRINCIPAL, 2026-09-12: "all sleeves must trade at least 0.01 lots
    overriding the risk per trade cuz thats broker minimum no matter what".

    This test was `test_unsizeable_returns_zero_not_minimum` and pinned the opposite rule: at a
    tiny equity, where even volume_min risks far more than 2x the 3% target, risk_lot refused.
    The arithmetic behind that refusal was never wrong -- `capacity.py` measured it on the same
    day, 40 of 40 live sleeves floor-bound with several over 1,000x policy -- and the principal's
    decision is that a trade the broker will accept beats no trade, with the overshoot published
    by `realised_q` rather than hidden.

    The name changed with the rule. A test called "returns zero" that asserts a non-zero lot is
    how a suite stops being readable.
    """
    lot = risk_lot(equity=100, sl_dist_price=5.0, tick_value=1.0, tick_size=0.01,
                   volume_min=0.01, volume_step=0.01, volume_max=100.0)
    assert lot == 0.01


def test_volume_min_tolerated_within_2x_target() -> None:
    # min lot risks between 1x and 2x target -> allowed at volume_min, not silently skipped
    lot = risk_lot(equity=10_000, sl_dist_price=0.005, tick_value=1.0, tick_size=0.0001,
                   volume_min=2.0, volume_step=1.0, volume_max=100.0)
    assert lot == 2.0  # target 75, min-lot risk 100 <= 150


def test_clamp_risk_frac_bounds_and_junk() -> None:
    assert clamp_risk_frac(None) == BASE_RISK_FRAC
    assert clamp_risk_frac("garbage") == BASE_RISK_FRAC
    assert clamp_risk_frac(0.001) == BASE_RISK_FRAC        # never below principal base
    assert clamp_risk_frac(0.5) == MAX_RISK_FRAC           # never above the ceiling
    assert clamp_risk_frac(0.05) == 0.05                   # justified dynamic-up passes


def test_degenerate_inputs_never_trade() -> None:
    for bad in ({"equity": 0}, {"sl_dist_price": 0}, {"tick_value": 0},
                {"tick_size": 0}, {"volume_step": 0}, {"volume_min": 0}):
        kw = dict(equity=10_000, sl_dist_price=0.005, tick_value=1.0, tick_size=0.0001,
                  volume_min=0.01, volume_step=0.01, volume_max=100.0)
        kw.update(bad)
        assert risk_lot(**kw) == 0.0
