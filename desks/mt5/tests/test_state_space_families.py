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


@pytest.mark.parametrize("name", ["garch_shock", "kalman_trend", "ou_reversion",
                                  "particle_regime", "gp_forecast"])
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


@pytest.mark.parametrize("name", ["garch_shock", "kalman_trend", "particle_regime",
                                  "gp_forecast"])
def test_bracket_is_anchored_on_the_signal_bars_own_close(name):
    close = 1.2 * np.exp(np.cumsum(_gjr(4000, seed=11)))
    d = _frame(close)
    kw = {"window": 1500, "refit": 500, "entry_z": 2.0} if name == "garch_shock" else {}
    rr = 1.75
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
                                  "kalman_pair", "copula_pair", "particle_regime",
                                  "gp_forecast"])
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


@pytest.mark.parametrize("name", ["kalman_pair", "copula_pair"])
def test_a_peer_store_that_fell_behind_is_a_named_failure(name, monkeypatch):
    a, b = _pair()
    _store(monkeypatch, b.iloc[:-3])                 # a few bars: different hours, tolerated
    assert fs.FAMILIES[name](a, pair_symbol="PEER")
    _store(monkeypatch, b.iloc[:-50])
    with pytest.raises(ValueError, match="bars before this cell"):
        fs.FAMILIES[name](a, pair_symbol="PEER")


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
    for name in ("particle_regime", "gp_forecast"):      # at their defaults, no loosened entry
        assert fs.FAMILIES[name](d), name


def _drift_regimes(n: int, seed: int, size: float = 0.35, run: int = 150) -> tuple[np.ndarray,
                                                                                   np.ndarray]:
    """Unit-noise returns whose drift flips sign every `run` bars: (returns, true drift)."""
    rng = np.random.default_rng(seed)
    m = size * np.where((np.arange(n) // run) % 2 == 0, 1.0, -1.0)
    return 1e-3 * (m + rng.standard_normal(n)), m


def test_particle_filter_recovers_the_drift_sign_and_the_volatility():
    n = 4000
    x, m = _drift_regimes(n, seed=31)
    rng = np.random.default_rng(32)
    vol = np.where((np.arange(n) // 700) % 2 == 0, 1.0, 3.0)      # a variance regime on top
    x = 1e-3 * (m + vol * rng.standard_normal(n))
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    p, sig = fs.particle_drift_path(pd.Series(x, index=idx), 250, 0.3, 96.0)
    ok = p.notna().to_numpy()
    assert ok.sum() > 3000
    pv, sv = p.to_numpy()[ok], sig.to_numpy()[ok]
    assert pv[m[ok] > 0].mean() > 0.65 and pv[m[ok] < 0].mean() < 0.35
    assert np.corrcoef(np.log(sv), np.log(vol[ok]))[0, 1] > 0.6


def test_particle_filter_is_the_same_filter_twice():
    """The seed is a constant keyed on the calendar, so a rerun is bit-for-bit the same path."""
    x, _m = _drift_regimes(2000, seed=33)
    idx = pd.date_range("2020-01-01", periods=2000, freq="h", tz="UTC")
    a, _ = fs.particle_drift_path(pd.Series(x, index=idx), 250, 0.2, 48.0)
    b, _ = fs.particle_drift_path(pd.Series(x, index=idx), 250, 0.2, 48.0)
    assert a.notna().sum() > 1000 and a.equals(b)


def test_particle_count_moves_the_signals_by_a_stated_share():
    """The filter is Monte Carlo: the particle count is not a cell axis, so its effect is a
    number. Measured 2026-11-10 on three GJR series at 128 vs 256 particles: signal counts within
    3-8% of each other, 58-71% of the 128-particle signals identical in bar and side."""
    d = _frame(1.2 * np.exp(np.cumsum(_gjr(8000, seed=21))))
    a = {(s.time, s.side) for s in fs.family_particle_regime(d, n_particles=128)}
    b = {(s.time, s.side) for s in fs.family_particle_regime(d, n_particles=256)}
    assert len(a) > 30 and len(b) > 30
    assert abs(len(a) - len(b)) / max(len(a), len(b)) < 0.15
    assert len(a & b) / len(a) >= 0.5


def test_gp_forecast_reads_the_series_its_length_scale_was_chosen_on():
    """Scaling every return by a constant changes neither the standardised series nor the
    forecast; the first cut divided raw returns by the end bar's sd only."""
    rng = np.random.default_rng(41)
    n = 2500
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    vol = np.where((np.arange(n) // 300) % 2 == 0, 1.0, 4.0)        # sd changes inside windows
    x = pd.Series(1e-3 * vol * rng.standard_normal(n), index=idx)
    t1, e1 = fs.gp_forecast_path(x, 240, 8, 0.2)
    t2, e2 = fs.gp_forecast_path(1000.0 * x, 240, 8, 0.2)
    ok = t1.notna().to_numpy()
    assert ok.sum() > 1500 and np.array_equal(ok, t2.notna().to_numpy())
    assert np.allclose(t1[ok], t2[ok], rtol=1e-9, atol=1e-12) and e1.equals(e2)
    z = x / x.rolling(240, min_periods=240).std()
    i = int(np.flatnonzero(ok)[-1])
    wts, psd, _ = fs._gp_weights(240, 8, 0.2, float(e1.iloc[i]))
    assert t1.iloc[i] == pytest.approx(float(z.iloc[i - 239:i + 1].to_numpy() @ wts) / psd)


def test_gp_forecast_tracks_a_smooth_drift_and_says_little_about_noise():
    n = 4000
    rng = np.random.default_rng(41)
    drift = 0.5 * np.sin(2 * np.pi * np.arange(n) / 200.0)
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    t, ell = fs.gp_forecast_path(pd.Series(1e-3 * (drift + rng.standard_normal(n)), index=idx),
                                 240, 8, 0.3)
    ok = t.notna().to_numpy()
    fut = np.array([drift[i + 1:i + 9].sum() if i + 9 <= n else np.nan for i in range(n)])
    use = ok & np.isfinite(fut)
    assert use.sum() > 2500
    assert np.corrcoef(t.to_numpy()[use], fut[use])[0, 1] > 0.6
    assert set(ell.dropna().unique()) <= set(fs.GP_LENGTHS)
    noise, _ = fs.gp_forecast_path(pd.Series(1e-3 * rng.standard_normal(n), index=idx),
                                   240, 8, 0.3)
    assert (noise.abs() >= 1.0).mean() < 0.5 * (t.abs() >= 1.0).mean()


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
