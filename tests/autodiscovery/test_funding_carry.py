"""The library's first true carry test, and the fence that keeps it honest.

`Family.CARRY` held exactly one generator since inception -- `drift_proxy`, which is
`momentum_positions(lookback=200)` on OHLC bars with no funding, swap or basis input anywhere.
The module header carried "the desk has run ZERO true carry tests" as a standing admission.

The data was never the obstacle: `MarketSeries.funding` has been populated by the adapter all
along, read by exactly one generator -- the FADE. What was missing was a RETURN PATH, and that is
what most of this file guards.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.autodiscovery.generators import (
    GENERATORS,
    carry_returns,
    net_returns,
    returns_for,
)
from libs.autodiscovery.models import Family, MarketSeries
from libs.research.mechanism_census import CONSTRUCTION_CLASS

_CARRY = next(s for s in GENERATORS if s.subtype == "funding_carry")


def _series(funding=None, n=300, drift=0.0):
    close = 100.0 * np.cumprod(np.full(n, 1.0 + drift))
    return MarketSeries(
        close=close, high=close * 1.001, low=close * 0.999,
        volume=np.ones(n), hour=np.zeros(n),
        funding=None if funding is None else np.asarray(funding, dtype="float64"),
    )


# ------------------------------------------------------------------ the mechanism is declared

def test_it_is_filed_as_carry_by_the_census_not_just_by_its_family():
    assert CONSTRUCTION_CLASS["funding_carry"] == "derivative_carry_basis"
    assert _CARRY.family is Family.CARRY


def test_drift_proxy_is_still_not_carry():
    """The new spec must not be read as rehabilitating the old mislabel."""
    assert CONSTRUCTION_CLASS["drift_proxy"] == "price_continuation"


def test_the_fade_and_the_carry_are_different_mechanisms_on_the_same_input():
    assert CONSTRUCTION_CLASS["funding_stress_reversal"] == "positioning_crowding_unwind"
    assert CONSTRUCTION_CLASS["funding_carry"] != CONSTRUCTION_CLASS["funding_stress_reversal"]


# ------------------------------------------------------------------------ the return path

def test_delta_neutral_specs_are_scored_by_carry_returns():
    assert _CARRY.delta_neutral is True
    assert returns_for(_CARRY) is carry_returns


def test_every_price_spec_keeps_its_historical_scoring():
    """The flag defaults False, so nothing else in the library may have moved."""
    for spec in GENERATORS:
        if spec.subtype == "funding_carry":
            continue
        assert spec.delta_neutral is False, spec.subtype
        assert returns_for(spec) is net_returns, spec.subtype


def test_carry_pnl_is_funding_and_ignores_the_spot_path():
    """THE WHOLE REASON A SECOND RETURN FUNCTION EXISTS.

    The legs cancel, so a carry's return must be identical whether spot doubled or halved. Scoring
    it with `net_returns` would report the spot move under a carry label -- `drift_proxy`'s error
    committed a second time, with better inputs.
    """
    f = np.full(300, 3e-4)
    pos = np.ones(300)
    up = carry_returns(_series(f, drift=+0.01), pos, cost=0.0)
    down = carry_returns(_series(f, drift=-0.01), pos, cost=0.0)
    assert np.allclose(up, down), "the carry's P&L moved with spot"
    assert np.allclose(up, 3e-4)

    # and the price path really would have reported the direction instead
    priced = net_returns(_series(f, drift=+0.01), pos, cost=0.0)
    assert abs(float(np.mean(priced)) - 0.01) < 1e-6


def test_no_position_earns_no_funding():
    f = np.full(300, 3e-4)
    assert not np.any(carry_returns(_series(f), np.zeros(300), cost=0.0))


def test_accrual_is_lagged_one_bar_like_net_returns():
    """Both paths must index the same way or their returns cannot be correlated bar-for-bar."""
    f = np.zeros(300)
    f[150] = 1e-3
    pos = np.zeros(300)
    pos[149] = 1.0                        # held INTO bar 150, so it earns bar 150's funding
    r = carry_returns(_series(f), pos, cost=0.0)
    assert len(r) == 299 == len(net_returns(_series(f), pos))
    assert r[149] == pytest.approx(1e-3)


def test_turnover_is_charged_on_both_legs():
    """A carry crosses TWO books to open and two to close; charging one would make the backtest
    cheaper than the live book it is meant to predict."""
    pos = np.zeros(300)
    pos[100:200] = 1.0
    r = carry_returns(_series(np.zeros(300)), pos, cost=0.001)
    assert float(r.sum()) == pytest.approx(-2 * 2 * 0.001)   # 2 turnovers x 2 legs


def test_absent_funding_degrades_to_flat_not_to_a_guess():
    assert not np.any(_CARRY.fn(_series(None), {}))
    assert not np.any(carry_returns(_series(None), np.ones(300)))


# ---------------------------------------------------------------------------- the generator

def test_it_holds_through_ordinary_positive_funding():
    f = np.full(300, 3e-4)                                  # 3 bps/day, ordinary major funding
    pos = _CARRY.fn(_series(f), {"window": 30, "enter_bps": 2.0, "exit_bps": 0.5})
    assert pos[-1] == 1.0
    assert pos[50:].mean() > 0.9, "the carry churned through a stable paying regime"


def test_it_stays_flat_when_funding_does_not_clear_the_bar():
    f = np.full(300, 0.5e-4)                                # 0.5 bps/day: real, but not enough
    assert not np.any(_CARRY.fn(_series(f), {"window": 30, "enter_bps": 2.0, "exit_bps": 0.5}))


def test_hysteresis_prevents_churn_around_the_entry_level():
    """A carry pays basis points a day and costs a pair round-trip to open. Entering and exiting
    on every wobble loses money on a mechanism that genuinely pays -- so the exit level sits
    BELOW the entry level and the position rides the noise."""
    rng = np.random.default_rng(7)
    f = 2.05e-4 + rng.normal(0, 0.3e-4, 300)                # jitters across enter_bps=2.0
    pos = _CARRY.fn(_series(f), {"window": 30, "enter_bps": 2.0, "exit_bps": 0.5})
    flips = int(np.abs(np.diff(pos[30:])).sum())
    assert flips <= 2, f"{flips} round-trips through one noisy regime"


def test_it_exits_when_funding_decays_away():
    f = np.concatenate([np.full(200, 4e-4), np.full(100, 0.0)])
    pos = _CARRY.fn(_series(f), {"window": 30, "enter_bps": 2.0, "exit_bps": 0.5})
    assert pos[199] == 1.0
    assert pos[-1] == 0.0, "held a carry that stopped paying"


def test_it_never_goes_short_the_basis():
    """Negative carry is a different trade with a different payer -- it needs the borrow cost of
    shorting spot, which nothing here measures."""
    f = np.full(300, -5e-4)
    pos = _CARRY.fn(_series(f), {"window": 30, "enter_bps": 2.0, "exit_bps": 0.5})
    assert pos.min() >= 0.0 and not np.any(pos)


def test_an_unpublished_stretch_drops_the_position_rather_than_assuming_it_held():
    f = np.full(300, 4e-4)
    f[200:] = np.nan
    pos = _CARRY.fn(_series(f), {"window": 30, "enter_bps": 2.0, "exit_bps": 0.5})
    assert pos[199] == 1.0
    assert pos[-1] == 0.0, "asserted a carry persisted through funding nobody published"


# --------------------------------------------------------------------------------- the fence

def test_nothing_scores_a_delta_neutral_spec_on_the_price_path():
    """THE FENCE. Scoring a carry with `net_returns` does not raise -- it quietly returns a
    plausible directional number under a carry label. Every module that scores generators must go
    through `returns_for`, so this asserts none of them reach for `net_returns` directly.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    scorers = [
        "libs/autodiscovery/orchestrator.py",
        "scripts/run_real_campaign.py",
        "scripts/run_rejection_rescore.py",
        "scripts/measure_cross_mechanism_corr.py",
    ]
    for rel in scorers:
        for i, line in enumerate(( root / rel).read_text("utf-8").splitlines(), 1):
            code = line.split("#")[0]
            assert "net_returns(" not in code, (
                f"{rel}:{i} scores generators with net_returns directly; use returns_for(spec)")
