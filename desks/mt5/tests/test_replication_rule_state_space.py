"""The written replication rules for the five framework families of 2026-11-10 (`garch_shock`,
`kalman_trend`, `kalman_pair`, `copula_pair`, `ou_reversion`): without a rule in the spec book
every certificate they earn is held unreplicated and starts no forward clock.

FIDELITY: the lane's rebuild, written from the rule text, emits exactly the desk family's orders
(the test may import the implementation; the lane may not)."""
from __future__ import annotations

import inspect
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
from mt5desk import families_specialist  # noqa: E402
from mt5desk import family_state_space as fss  # noqa: E402

FAMILIES = ("garch_shock", "kalman_trend", "kalman_pair", "copula_pair", "ou_reversion")


def _ohlc(c: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    idx = pd.date_range("2023-01-02", periods=c.size, freq="h", tz="UTC")
    df = pd.DataFrame({"open": np.concatenate([[c[0]], c[:-1]]), "close": c}, index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + rng.uniform(0, 5e-4, c.size))
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - rng.uniform(0, 5e-4, c.size))
    return df


def _trending(n: int = 3000, seed: int = 3) -> pd.DataFrame:
    """Drift that changes sign in blocks, with volatility clusters and fat-tailed shocks."""
    rng = np.random.default_rng(seed)
    drift = np.repeat(rng.choice([-2e-4, 0.0, 2e-4], n // 150 + 1), 150)[:n]
    vol = 1e-3 * np.exp(0.5 * np.sin(np.arange(n) / 90.0))
    r = drift + rng.standard_t(4, n) * vol
    return _ohlc(1.1 * np.exp(np.cumsum(r)), rng)


def _reverting(n: int = 3000, seed: int = 5) -> pd.DataFrame:
    """An OU log price around a slowly wandering mean: half-lives of a few dozen bars."""
    rng = np.random.default_rng(seed)
    mean = np.cumsum(rng.normal(0, 1e-4, n))
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = x[t - 1] + 0.04 * (mean[t] - x[t - 1]) + rng.normal(0, 1e-3)
    return _ohlc(1.3 * np.exp(x), rng)


def _pair(n: int = 3000, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two legs sharing a random walk, their spread mean-reverting; the peer misses some bars."""
    rng = np.random.default_rng(seed)
    common = np.cumsum(rng.standard_t(5, n) * 8e-4)
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = 0.95 * spread[t - 1] + rng.normal(0, 6e-4)
    a = _ohlc(1.2 * np.exp(common + spread), rng)
    b = _ohlc(0.9 * np.exp(0.8 * common + np.cumsum(rng.normal(0, 1e-4, n))), rng)
    return a, b.drop(b.index[rng.choice(n, 40, replace=False)])


def _bars(df: pd.DataFrame) -> rc.Bars:
    return rc.bars_from_arrays(df.index.as_unit("ns").asi8, df["open"].to_numpy(),
                               df["high"].to_numpy(), df["low"].to_numpy(),
                               df["close"].to_numpy())


def _same(orig: list, ours: list) -> bool:
    """Order for order. Prices to 1e-7 on a ~1.0 instrument: a filter written twice agrees to
    rounding, not to the bit (the widest gap measured here is 1.1e-9, on a Kalman target)."""
    return len(orig) == len(ours) and all(
        pd.Timestamp(o.time).value == q.t_ns and int(o.side) == q.side
        and abs(float(o.stop) - q.stop) < 1e-7 and abs(float(o.target) - q.target) < 1e-7
        and int(o.ttl_bars) == q.ttl_bars for o, q in zip(orig, ours, strict=True))


def _ours(family: str, df: pd.DataFrame, params: dict) -> list:
    p, why = rc.resolve_spec(family, {**params, "timeframe": "H1"}, "continuous", None,
                             symbol="TESTFX")
    assert p is not None, why
    return rc.SPEC_BOOK[family].build(_bars(df), p)


def _wire_peer(monkeypatch: pytest.MonkeyPatch, peer: pd.DataFrame) -> None:
    """Both sides read the same peer: the family through its store reader, the lane through
    its own factor loader."""
    stamps = peer.index.as_unit("ns").asi8
    closes = peer["close"].to_numpy(dtype="float64")

    def asof_close(at: np.ndarray, symbol: str, *, max_stale_h: float = 12.0) -> np.ndarray:
        assert max_stale_h == 0.0
        if symbol != "PEERFX":
            return np.full(at.size, np.nan)
        j = np.clip(np.searchsorted(stamps, at), 0, stamps.size - 1)
        return np.where(stamps[j] == at, closes[j], np.nan)

    monkeypatch.setattr(families_specialist, "asof_close", asof_close)
    monkeypatch.setattr(rc, "FACTOR_BARS",
                        lambda s, tf: _bars(peer) if (s, tf) == ("PEERFX", "H1") else None)


def test_every_framework_family_has_a_written_rule_that_sets_its_own_side() -> None:
    assert set(FAMILIES) == set(fss.FAMILIES)
    for name in FAMILIES:
        spec = rc.SPEC_BOOK[name]
        assert spec.rule_sets_side and spec.session_in_params and len(spec.text) > 200
        # the rule names every parameter the family takes, and nothing the family lacks
        taken = set(inspect.signature(fss.FAMILIES[name]).parameters) - {"df"}
        assert set(spec.defaults) == taken, (name, set(spec.defaults) ^ taken)
        for key, value in spec.defaults.items():
            default = inspect.signature(fss.FAMILIES[name]).parameters[key].default
            if key == "pair_symbol":             # required by the family: no default to mirror
                assert default is inspect.Parameter.empty and value is None
            else:
                assert default == value, (name, key)


@pytest.mark.parametrize("params", [
    {}, {"side_mode": "fade"}, {"q_level": 0.5, "q_slope": 1e-2, "entry_t": 1.5},
    {"warmup": 200, "atr_n": 14, "stop_atr": 1.5, "rr": 3.0, "ttl_bars": 12},
])
def test_kalman_trend_matches_the_registered_family(params: dict) -> None:
    df = _trending()
    orig = fss.family_kalman_trend(df, **params)
    assert len(orig) > 5 and _same(orig, _ours("kalman_trend", df, params))
    assert {int(o.side) for o in orig} == {1, -1}


@pytest.mark.parametrize("params", [
    {"window": 200}, {"window": 200, "entry_z": 1.5, "hl_min": 2.0, "hl_max": 40.0},
    {"window": 300, "hold_mult": 3.0, "target_frac": 1.0, "max_ttl": 60, "stop_atr": 1.5},
])
def test_ou_reversion_matches_the_registered_family(params: dict) -> None:
    df = _reverting()
    orig = fss.family_ou_reversion(df, **params)
    assert len(orig) > 5 and _same(orig, _ours("ou_reversion", df, params))
    assert {int(o.side) for o in orig} == {1, -1}
    assert len({int(o.ttl_bars) for o in orig}) > 1          # the hold follows the half-life


@pytest.mark.parametrize("params", [
    {"min_target_atr": 0.0}, {"delta": 1e-3, "entry_z": 1.5, "target_frac": 0.5},
    {"warmup": 200, "atr_n": 14, "stop_atr": 1.5, "ttl_bars": 12, "min_target_atr": 0.2},
])
def test_kalman_pair_matches_the_registered_family(params: dict,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    df, peer = _pair()
    _wire_peer(monkeypatch, peer)
    params = {**params, "pair_symbol": "PEERFX"}
    orig = fss.family_kalman_pair(df, **params)
    assert len(orig) > 5 and _same(orig, _ours("kalman_pair", df, params))
    assert {int(o.side) for o in orig} == {1, -1}
    gone = set(df.index) - set(peer.index)
    assert gone and not gone & {pd.Timestamp(o.time) for o in orig}   # no carried peer close


@pytest.mark.parametrize("params", [
    {"window": 300}, {"window": 300, "kind": "gauss", "entry_m": 1.5, "cum_bars": 8},
    {"window": 250, "nu": 6.0, "min_rho": 0.1, "atr_n": 14, "rr": 2.0, "ttl_bars": 12},
])
def test_copula_pair_matches_the_registered_family(params: dict,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    df, peer = _pair()
    _wire_peer(monkeypatch, peer)
    params = {**params, "pair_symbol": "PEERFX"}
    orig = fss.family_copula_pair(df, **params)
    assert len(orig) > 5 and _same(orig, _ours("copula_pair", df, params))
    assert {int(o.side) for o in orig} == {1, -1}


@pytest.mark.parametrize("params", [
    {"entry_z": 2.0}, {"entry_z": 2.0, "side_mode": "follow", "vol_state": "calm"},
    {"window": 800, "refit": 200, "entry_z": 1.8, "vol_state": "stressed", "ttl_bars": 12},
])
def test_garch_shock_matches_the_registered_family(params: dict) -> None:
    df = _trending(n=2600)
    orig = fss.family_garch_shock(df, **params)
    assert len(orig) > 5 and _same(orig, _ours("garch_shock", df, params))
    assert {int(o.side) for o in orig} == {1, -1}


def test_both_sides_survive_the_certificates_single_side_and_its_selector() -> None:
    df = _trending()
    p, _ = rc.resolve_spec("kalman_trend", {}, "asia", "SHORT", symbol="TESTFX")
    orders, _fills = rc.rebuild("kalman_trend", _bars(df), p, 0.0)
    assert {o.side for o in orders} == {1, -1}
    assert _same(fss.family_kalman_trend(df), orders)


def test_they_stand_aside_where_the_families_do(monkeypatch: pytest.MonkeyPatch) -> None:
    df, peer = _pair()
    _wire_peer(monkeypatch, peer)
    cases = (("kalman_trend", {"side_mode": "drift"}), ("kalman_trend", {"q_slope": 0.0}),
             ("kalman_trend", {"warmup": 5000}), ("ou_reversion", {"hl_min": 50.0, "hl_max": 10.0}),
             ("ou_reversion", {"hold_mult": 0.5}), ("ou_reversion", {"window": 2000}),
             ("kalman_pair", {"pair_symbol": "PEERFX", "delta": 1.0}),
             ("kalman_pair", {"pair_symbol": "PEERFX", "warmup": 5000}),
             ("copula_pair", {"pair_symbol": "PEERFX", "nu": 2.0}),
             ("copula_pair", {"pair_symbol": "PEERFX", "kind": "clayton"}),
             ("garch_shock", {"side_mode": "drift"}), ("garch_shock", {"vol_state": "wild"}),
             ("garch_shock", {"window": 5000}))
    for family, params in cases:
        assert fss.FAMILIES[family](df, **params) == [], (family, params)
        assert _ours(family, df, params) == [], (family, params)
    # WHERE THE FAMILY RAISES (a build failure by name) the lane has no second leg to rebuild
    # from and emits nothing: no peer named, a peer with no bars, a peer store fallen behind.
    for family in ("kalman_pair", "copula_pair"):
        with pytest.raises(TypeError, match="pair_symbol"):
            fss.FAMILIES[family](df)
        with pytest.raises(ValueError, match="no pair_symbol"):
            fss.FAMILIES[family](df, pair_symbol="")
        with pytest.raises(ValueError, match="no H1 bars"):
            fss.FAMILIES[family](df, pair_symbol="PEERFX2")
        for params in ({}, {"pair_symbol": ""}, {"pair_symbol": "PEERFX2"}):
            assert _ours(family, df, params) == [], (family, params)
    _wire_peer(monkeypatch, peer[peer.index <= df.index[-8]])
    with pytest.raises(ValueError, match="bars before this cell's last bar"):
        fss.family_kalman_pair(df, pair_symbol="PEERFX")
    assert _ours("kalman_pair", df, {"pair_symbol": "PEERFX"}) == []
    # ...and six bars behind is still a live peer, on both sides
    _wire_peer(monkeypatch, peer[peer.index <= df.index[-7]])
    params = {"pair_symbol": "PEERFX", "min_target_atr": 0.0}
    orig = fss.family_kalman_pair(df, **params)
    assert orig and _same(orig, _ours("kalman_pair", df, params))


def test_a_value_exactly_at_the_threshold_signals() -> None:
    """THE TIE SIDE IS WRITTEN, NOT LEFT TO THE LAST BIT: every rule says ">=" and "<=", so a
    statistic exactly at the threshold signals, and one a hair inside it does not."""
    v = np.array([0.0, 2.0, 2.0, 0.0, np.nan, -2.0, -1.9999999999, 2.0000000001, np.nan, 2.0])
    up, down = rc._crossings(v, 2.0)
    assert up.tolist() == [1, 7, 9] and down.tolist() == [5]
    inside = np.nextafter(2.0, 0.0)
    up, down = rc._crossings(np.array([0.0, inside, -inside]), 2.0)
    assert up.size == 0 and down.size == 0


def test_the_blocks_are_cut_by_the_calendar_not_by_the_first_bar() -> None:
    """A frame that starts later cuts the same blocks, so a forward clock's shorter frame trades
    the rule the certificate was judged on -- and the lane's cut is the family's own."""
    df = _trending()
    stamps = df.index.as_unit("ns").asi8
    for back, every in ((500, 500), (1000, 250), (200, 500)):
        ours = rc._calendar_blocks(stamps, back, every)
        assert [k for k, _ in ours] == fss._refit_starts(df.index, back, every).tolist()
        assert ours and ours[-1][1] == len(df) and all(k >= back for k, _ in ours)
        late = rc._calendar_blocks(stamps[137:], back, every)
        assert {stamps[137 + k] for k, _ in late} <= {stamps[k] for k, _ in ours}
    full = _ours("kalman_trend", df, {"warmup": 200})
    tail = _ours("kalman_trend", df.iloc[700:], {"warmup": 200})
    cut = df.index.as_unit("ns").asi8[700 + 200 + 500]
    assert tail and {(o.t_ns, o.side) for o in tail if o.t_ns >= cut} == {
        (o.t_ns, o.side) for o in full if o.t_ns >= cut}
