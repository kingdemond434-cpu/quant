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


def _pair(n: int = 4000) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(13)
    common = np.cumsum(0.001 * rng.standard_normal(n))
    spread = _ou(n, hl=10.0, seed=14)
    a = _frame(1.3 * np.exp(common + spread), seed=15)
    b = _frame(1.1 * np.exp(0.8 * common), seed=16)
    return a, b


def _store(monkeypatch, b: pd.DataFrame) -> None:
    from mt5desk import families_cross_sectional as xs
    stamps = b.index.as_unit("us").asi8 * 1000      # the store's unit (ns) from a us-unit frame
    monkeypatch.setattr(xs, "_load_series",
                        lambda symbol: (stamps, b["close"].to_numpy(dtype=float)))


@pytest.mark.parametrize("name", ["kalman_pair", "copula_pair"])
def test_pair_families_fade_the_dislocation(name, monkeypatch):
    a, b = _pair()
    _store(monkeypatch, b)
    sigs = fs.FAMILIES[name](a, pair_symbol="PEER")
    assert len(sigs) > 10
    assert {s.side for s in sigs} == {-1, 1}


@pytest.mark.parametrize("name", ["kalman_pair", "copula_pair"])
def test_a_named_pair_with_no_bars_is_a_named_failure(name, monkeypatch):
    from mt5desk import families_cross_sectional as xs
    monkeypatch.setattr(xs, "_load_series", lambda symbol: None)
    a, _b = _pair()
    with pytest.raises(ValueError, match="no H1 bars"):
        fs.FAMILIES[name](a, pair_symbol="NOSUCH")
    with pytest.raises(TypeError):               # no pair named: a failed build, never a zero
        fs.FAMILIES[name](a)
    with pytest.raises(ValueError, match="no pair_symbol"):
        fs.FAMILIES[name](a, pair_symbol="")


@pytest.mark.parametrize("name", ["kalman_pair", "copula_pair"])
def test_pair_families_refuse_a_chart_the_store_cannot_match(name, monkeypatch):
    a, b = _pair()
    _store(monkeypatch, b)
    four_hour = a.iloc[::4]
    with pytest.raises(ValueError, match="H1 only"):
        fs.FAMILIES[name](four_hour, pair_symbol="PEER")


@pytest.mark.parametrize("name", ["garch_shock", "kalman_trend", "ou_reversion",
                                  "kalman_pair", "copula_pair"])
def test_a_frame_that_starts_later_trades_the_same_rule(name, monkeypatch):
    """The forward clock's frame is shorter than the gauntlet's; the certificate must not move."""
    a, b = _pair(6000)
    _store(monkeypatch, b)
    kw = {"pair_symbol": "PEER"} if name in fs.PEER_FAMILIES else {}
    if name == "garch_shock":
        kw.update(entry_z=2.0)
    fn = fs.FAMILIES[name]
    late = a.index[4500]
    full = [(s.time, s.side, round(s.stop, 9), round(s.target, 9))
            for s in fn(a, **kw) if s.time >= late]
    for shift in (1, 137):
        cut = [(s.time, s.side, round(s.stop, 9), round(s.target, 9))
               for s in fn(a.iloc[shift:], **kw) if s.time >= late]
        assert full and cut == full, (name, shift)


def test_garch_refit_blocks_are_cut_by_the_calendar():
    idx = pd.date_range("2020-01-01", periods=3000, freq="h", tz="UTC")
    full = idx[fs._refit_starts(idx, 1000, 250)]
    shifted = idx[7:][fs._refit_starts(idx[7:], 1000, 250)]
    assert len(full) >= 7 and set(shifted) <= set(full) and set(full[1:]) <= set(shifted)


def test_the_sealed_gauntlet_can_build_every_family():
    """No family takes a DATA argument build_cell would leave None, nor an identity key."""
    import inspect

    from mt5desk import families_orthogonal as fo
    from mt5desk.family_inputs import IDENTITY_KEYS
    from research.gauntlet_buildability import BUILDABLE, DATA_INPUT_ARGS, family_verdict
    for name, fn in fs.FAMILIES.items():
        args = set(inspect.signature(fn).parameters)
        assert not args & DATA_INPUT_ARGS, name
        assert not args & IDENTITY_KEYS, name
        assert "side" not in args, name
        assert family_verdict(name)[0] == BUILDABLE, name
    for name in fs.PEER_FAMILIES:
        assert fo.timeframe_refusal(name, "M5") and fo.timeframe_refusal(name, "H1") is None


def test_default_cells_need_no_more_than_sixty_h1_days():
    """The judge's observations gate needs signals inside 60 development days of H1."""
    close = 1.2 * np.exp(np.cumsum(_gjr(60 * 24, seed=21)))
    d = _frame(close)
    for name in ("garch_shock", "kalman_trend", "ou_reversion"):
        kw = {"entry_z": 1.5} if name != "kalman_trend" else {"entry_t": 1.5}
        assert fs.FAMILIES[name](d, **kw), name


def test_every_family_is_classed_and_swept():
    from research import alpha_genome, axis_registry, breadth_sweep
    for name in fs.FAMILIES:
        assert name in alpha_genome.MECHANISM_CLASS
        assert axis_registry.classify_family(name)[0] != axis_registry.UNKNOWN
        assert breadth_sweep.READY[name]["grid"]
    targets = breadth_sweep._targets("kalman_pair", breadth_sweep.READY["kalman_pair"],
                                     ["EURUSD", "GBPUSD"])
    assert targets == [("EURUSD", {"pair_symbol": "GBPUSD"})]


def test_registered_where_the_judge_and_the_forward_clock_look():
    from mt5desk import families_orthogonal as fo
    from mt5desk import family_inputs as fi
    for name in fs.FAMILIES:
        assert fo.ORTHOGONAL_FAMILIES[name] is fs.FAMILIES[name]
        assert name in fo.FAMILY_INPUTS
    # The forward clock strips identity keys and loads frames only for its own peer families;
    # these carry `pair_symbol` by value, so they must NOT be in that set.
    assert not fs.PEER_FAMILIES & fi._PEER_FAMILIES
