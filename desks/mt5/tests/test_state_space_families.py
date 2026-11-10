"""The quant-framework families (GARCH, Kalman trend/pair, copula pair, OU) are causal and honest."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import family_state_space as fs  # noqa: E402


def _frame(close: np.ndarray, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=close.size, freq="h", tz="UTC")
    wig = np.abs(rng.normal(0, 1e-4, close.size)) * close
    o = np.concatenate(([close[0]], close[:-1]))
    return pd.DataFrame({"open": o, "high": np.maximum(o, close) + wig,
                         "low": np.minimum(o, close) - wig, "close": close}, index=idx)


def _gjr(n: int, seed: int = 1, om: float = 2e-7, a: float = 0.05, g: float = 0.08,
         b: float = 0.88) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = om / (1 - a - b - g / 2)
    r = np.empty(n)
    for t in range(n):
        r[t] = math.sqrt(v) * rng.standard_normal()
        v = om + (a + g * (r[t] < 0)) * r[t] ** 2 + b * v
    return r


def _ou(n: int, hl: float, seed: int = 2) -> np.ndarray:
    rng = np.random.default_rng(seed)
    b = 0.5 ** (1 / hl)
    x = np.empty(n)
    x[0] = 0.0
    for t in range(1, n):
        x[t] = b * x[t - 1] + 0.002 * rng.standard_normal()
    return x


def test_gjr_garch_fit_recovers_persistence_and_leverage():
    om, a, g, b = fs.fit_gjr_garch(_gjr(6000))
    assert 0.85 < a + b + g / 2 < 0.999
    assert g > 0.02


def test_garch_beats_ewma_on_a_garch_series():
    r = pd.Series(_gjr(6000, seed=3))
    q = fs.qlike_vs_ewma(r, window=2000, refit=500)
    assert q is not None and q["garch_better"]


def test_ou_half_life_is_estimated_and_the_hold_covers_it():
    x = _ou(4000, hl=12.0)
    d = _frame(np.exp(np.log(1.1) + x))
    hl, _mu, _s = fs.ou_path(pd.Series(np.log(d["close"].to_numpy()), index=d.index), 500)
    assert 8 < float(hl.dropna().median()) < 18
    sigs = fs.family_ou_reversion(d, window=500, entry_z=1.5, hold_mult=2.0)
    assert sigs
    assert all(s.ttl_bars >= 8 for s in sigs)


@pytest.mark.parametrize("name", ["garch_shock", "kalman_trend", "ou_reversion"])
def test_single_leg_families_do_not_see_the_future(name):
    rng = np.random.default_rng(7)
    close = 1.2 * np.exp(np.cumsum(_gjr(4000, seed=5)) + 0.3 * _ou(4000, 20.0)
                         + 0.0005 * rng.standard_normal(4000))
    d = _frame(close)
    fn = fs.FAMILIES[name]
    kw = {"window": 1500, "refit": 500, "entry_z": 2.0} if name == "garch_shock" else {}
    full = fn(d, **kw)
    cut = d.index[3200]
    part = fn(d.loc[:cut], **kw)
    early = [(s.time, s.side, round(s.stop, 10), round(s.target, 10))
             for s in full if s.time < d.index[3199]]
    trunc = [(s.time, s.side, round(s.stop, 10), round(s.target, 10))
             for s in part if s.time < d.index[3199]]
    assert early and early == trunc


@pytest.mark.parametrize("name", ["garch_shock", "kalman_trend"])
def test_bracket_is_anchored_on_the_signal_bars_own_close(name):
    close = 1.2 * np.exp(np.cumsum(_gjr(4000, seed=11)))
    d = _frame(close)
    kw = {"window": 1500, "refit": 500, "entry_z": 2.0} if name == "garch_shock" else {}
    rr = 1.5
    sigs = fs.FAMILIES[name](d, rr=rr, **kw)
    assert sigs
    for s in sigs:
        px = (s.target + rr * s.stop) / (1 + rr)
        assert px == pytest.approx(float(d["close"].loc[s.time]), rel=1e-12)


def _pair(n: int = 3000) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(13)
    common = np.cumsum(0.001 * rng.standard_normal(n))
    spread = _ou(n, hl=10.0, seed=14)
    a = _frame(1.3 * np.exp(common + spread), seed=15)
    b = _frame(1.1 * np.exp(0.8 * common), seed=16)
    return a, b


@pytest.mark.parametrize("name", ["kalman_pair", "copula_pair"])
def test_pair_families_fade_the_dislocation(name):
    a, b = _pair()
    sigs = fs.FAMILIES[name](a, peer=b)
    assert len(sigs) > 10
    assert {s.side for s in sigs} == {-1, 1}


@pytest.mark.parametrize("name", ["kalman_pair", "copula_pair"])
def test_a_named_peer_with_no_bars_is_a_named_failure(name, monkeypatch):
    from mt5desk import families_cross_sectional as xs
    monkeypatch.setattr(xs, "_load_series", lambda symbol: None)
    a, _b = _pair()
    with pytest.raises(ValueError, match="no H1 bars"):
        fs.FAMILIES[name](a, peer_symbol="NOSUCH")
    assert fs.FAMILIES[name](a) == []            # no peer named: nothing to trade, no error


@pytest.mark.parametrize("name", ["kalman_pair", "copula_pair"])
def test_peer_read_from_the_store_matches_the_handed_frame(name, monkeypatch):
    from mt5desk import families_cross_sectional as xs
    a, b = _pair()
    stamps = b.index.asi8
    monkeypatch.setattr(xs, "_load_series",
                        lambda symbol: (stamps, b["close"].to_numpy(dtype=float)))
    via_frame = fs.FAMILIES[name](a, peer=b)
    via_store = fs.FAMILIES[name](a, peer_symbol="PEER")
    assert [(s.time, s.side) for s in via_frame] == [(s.time, s.side) for s in via_store]


def test_registered_where_the_judge_and_the_forward_clock_look():
    from mt5desk import families_orthogonal as fo
    from mt5desk import family_inputs as fi
    for name in fs.FAMILIES:
        assert fo.ORTHOGONAL_FAMILIES[name] is fs.FAMILIES[name]
        assert name in fo.FAMILY_INPUTS
    assert fs.PEER_FAMILIES <= fi._PEER_FAMILIES
