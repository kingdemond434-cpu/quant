"""The written replication rule for `cross_asset_residual` (2026-11-06: the largest certified block
the spec book still had no rule for once carry was found to be held for decay, not a missing rule).

FIDELITY: the lane's rebuild, written from the rule text, emits exactly the desk family's orders
(the test may import the implementation; the lane may not)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402
from mt5desk.families_orthogonal import family_cross_asset_residual  # noqa: E402


def _ohlc(c: np.ndarray, idx: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    df = pd.DataFrame({"open": c * (1 + rng.normal(0, 2e-4, len(c))), "close": c}, index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + rng.uniform(0, 8e-4, len(c)))
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - rng.uniform(0, 8e-4, len(c)))
    return df


def _market(days: int = 60, seed: int = 11) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """A target driven by two factors plus its own mean-reverting residual; one factor misses a
    few bars, so the rule's bar intersection is exercised."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=24 * days, freq="h", tz="UTC")
    f1 = rng.normal(0, 1e-3, len(idx))
    f2 = rng.normal(0, 1e-3, len(idx))
    own = np.zeros(len(idx))
    for i in range(1, len(idx)):
        own[i] = 0.97 * own[i - 1] + rng.normal(0, 8e-4)
    y = 1.2 * np.exp(np.cumsum(0.6 * f1 - 0.4 * f2) + own)
    fac1 = _ohlc(1.1 * np.exp(np.cumsum(f1)), idx, rng)
    fac2 = _ohlc(95.0 * np.exp(np.cumsum(f2)), idx, rng)
    fac2 = fac2.drop(fac2.index[[300, 301, 777]])
    return _ohlc(y, idx, rng), [fac1, fac2]


def _bars(df: pd.DataFrame) -> rc.Bars:
    return rc.bars_from_arrays(df.index.as_unit("ns").asi8, df["open"].to_numpy(),
                               df["high"].to_numpy(), df["low"].to_numpy(),
                               df["close"].to_numpy())


def _same(orig: list, ours: list) -> bool:
    return len(orig) == len(ours) and all(
        pd.Timestamp(o.time).value == q.t_ns and int(o.side) == q.side
        and abs(float(o.stop) - q.stop) < 1e-9 and abs(float(o.target) - q.target) < 1e-9
        and int(o.ttl_bars) == q.ttl_bars for o, q in zip(orig, ours, strict=True))


@pytest.fixture
def market(monkeypatch: pytest.MonkeyPatch) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    target, factors = _market()
    store = {"FAC1": _bars(factors[0]), "FAC2": _bars(factors[1])}
    monkeypatch.setattr(rc, "FACTOR_BARS", lambda sym, tf: store.get(sym))
    return target, factors


@pytest.mark.parametrize("extra", [
    {},
    {"side_mode": "continue"},
    {"beta_win": 120, "lookback": 96, "entry_z": 1.5},
    {"active_hours": [2, 3, 9, 14, 15], "atr_n": 14, "stop_atr": 1.5, "rr": 2.0,
     "ttl_bars": 24},
])
def test_rule_matches_the_registered_family(market: tuple, extra: dict) -> None:
    target, factors = market
    params = {"lookback": 120, **extra}
    orig = family_cross_asset_residual(target, factors=factors, **params)
    p, why = rc.resolve_spec("cross_asset_residual",
                             {"factor_symbols": ["FAC1", "FAC2"], "timeframe": "H1", **params},
                             "continuous", None, symbol="TGT")
    assert p is not None, why
    ours = rc.SPEC_BOOK["cross_asset_residual"].build(_bars(target), p)
    assert len(orig) > 10 and _same(orig, ours)
    if not extra.get("active_hours"):
        assert {int(o.side) for o in orig} == {1, -1}


def test_both_sides_survive_the_certificates_single_side_and_its_selector(market: tuple
                                                                           ) -> None:
    target, factors = market
    params = {"factor_symbols": ["FAC1", "FAC2"], "lookback": 120}
    p, _ = rc.resolve_spec("cross_asset_residual", params, "asia", "LONG", symbol="TGT")
    orders, _fills = rc.rebuild("cross_asset_residual", _bars(target), p, 0.0)
    assert {o.side for o in orders} == {1, -1}
    assert _same(family_cross_asset_residual(target, factors=factors, lookback=120), orders)


def test_the_certificates_session_parameter_filters_like_the_gauntlet(market: tuple) -> None:
    target, factors = market
    params = {"factor_symbols": ["FAC1", "FAC2"], "lookback": 120, "session": "london"}
    p, _ = rc.resolve_spec("cross_asset_residual", params, "continuous", None, symbol="TGT")
    orders, _ = rc.rebuild("cross_asset_residual", _bars(target), p, 0.0)
    want = [o for o in family_cross_asset_residual(target, factors=factors, lookback=120)
            if 8 <= o.time.hour < 16]
    assert want and _same(want, orders)


def test_it_stands_aside_where_the_family_does(market: tuple) -> None:
    target, _factors = market
    for params in ({"factor_symbols": []}, {"factor_symbols": ["FAC1", "NOPE"]},
                   {"factor_symbols": ["FAC1", "FAC2"], "side_mode": "sideways"},
                   {"factor_symbols": ["FAC1", "FAC2"], "lookback": 600}):
        p, _ = rc.resolve_spec("cross_asset_residual", params, None, None, symbol="TGT")
        assert rc.SPEC_BOOK["cross_asset_residual"].build(_bars(target), p) == []
