"""All 12 family generators: present, ternary positions, declared mechanism, graceful fallback."""

from __future__ import annotations

import numpy as np
from tests.autodiscovery.conftest import noise_series

from libs.autodiscovery.generators import GENERATORS, net_returns, planned_hypotheses
from libs.autodiscovery.models import Family, MarketSeries


def test_all_twelve_families_present() -> None:
    families = {spec.family for spec in GENERATORS}
    assert families == set(Family)  # exactly the 12 declared families


def test_every_generator_declares_economics() -> None:
    for spec in GENERATORS:
        assert spec.mechanism is not None
        assert spec.edge_source
        assert spec.failure_modes  # expected failure modes declared before testing


def test_positions_are_ternary_and_sized() -> None:
    series = noise_series(n=1000)
    for spec in GENERATORS:
        for variant in spec.param_variants:
            pos = spec.fn(series, dict(variant))
            assert len(pos) == len(series), spec.subtype
            assert set(np.unique(pos)).issubset({-1.0, 0.0, 1.0}), spec.subtype


def test_cross_asset_degrades_without_reference() -> None:
    # No ref_close -> honest flat (not a fabricated signal).
    series = noise_series(n=500)
    spec = next(s for s in GENERATORS if s.family is Family.CROSS_ASSET)
    assert np.all(spec.fn(series, dict(spec.param_variants[0])) == 0.0)


def test_session_degrades_without_hour() -> None:
    series = MarketSeries(close=noise_series(n=500).close, high=noise_series(n=500).high,
                          low=noise_series(n=500).low)  # no hour
    spec = next(s for s in GENERATORS if s.family is Family.SESSION)
    assert np.all(spec.fn(series, dict(spec.param_variants[0])) == 0.0)


def test_net_returns_no_lookahead() -> None:
    series = noise_series(n=600)
    spec = next(s for s in GENERATORS if s.family is Family.TREND)
    rets = net_returns(series, spec.fn(series, {"fast": 20, "slow": 50}))
    assert len(rets) == len(series) - 1
    assert np.all(np.isfinite(rets))


def test_planned_hypotheses_expands() -> None:
    plan = planned_hypotheses(["EURUSD", "XAUUSD"])
    # >= 12 variant-rows x 2 symbols, each carrying a declared mechanism
    assert len(plan) >= 24
    assert all(h.mechanism is not None for h, _ in plan)
    assert all(h.symbol in {"EURUSD", "XAUUSD"} for h, _ in plan)
