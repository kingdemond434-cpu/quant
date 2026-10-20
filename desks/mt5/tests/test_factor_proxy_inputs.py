"""Forward factor baskets: own bars on exact stamps, as-of alignment, declared proxies, named gaps.

Pinned on synthetic bars (2026-10-20, after 24 USDX+UST10Y clocks read n = 0 for weeks):
  * factors with full bars rebuild IDENTICALLY to the certification path (raw frames, same
    signals);
  * a factor trading other hours / printing sparsely no longer empties the frame;
  * a missing or stale factor yields a labelled proxy (only when the spec allows it) or
    NEEDS_PROXY_FACTOR -- never a silent zero;
  * the as-of join never reads a factor bar stamped after the bar it prices.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import factor_inputs as fi  # noqa: E402
from mt5desk import family_inputs  # noqa: E402
from mt5desk.families_orthogonal import family_cross_asset_residual  # noqa: E402

PARAMS = {"factor_symbols": ["USDX", "UST10Y"], "lookback": 120, "beta_win": 120,
          "entry_z": 2.0, "ttl_bars": 12, "side_mode": "revert", "timeframe": "M5"}


def _weekday_index(days: int = 30, start: str = "2026-08-03") -> pd.DatetimeIndex:
    idx = pd.date_range(start, periods=days * 288, freq="5min", tz="UTC")
    return idx[idx.weekday < 5]


def _bars(close: np.ndarray, idx: pd.DatetimeIndex) -> pd.DataFrame:
    c = pd.Series(close, index=idx)
    o = c.shift(1).fillna(c.iloc[0])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0002,
                         "low": np.minimum(o, c) * 0.9998, "close": c,
                         "tick_volume": 10, "spread": 2, "real_volume": 0}, index=idx)


def _world(seed: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    idx = _weekday_index()
    n = len(idx)
    usd = np.cumsum(rng.normal(0, 4e-4, n))
    rates = np.cumsum(rng.normal(0, 3e-4, n))
    own = np.cumsum(rng.normal(0, 3e-4, n))
    # a mean-reverting dislocation so the residual crosses its band
    dis = np.zeros(n)
    for i in range(1, n):
        dis[i] = 0.97 * dis[i - 1] + rng.normal(0, 6e-4)
    return {"XAUUSD": _bars(2000 * np.exp(-0.8 * usd + 0.5 * rates + own * 0.1 + dis), idx),
            "USDX": _bars(100 * np.exp(usd), idx),
            "UST10Y": _bars(110 * np.exp(rates), idx),
            "UST05Y": _bars(105 * np.exp(rates * 0.8), idx)}


def _store(monkeypatch, frames: dict[str, pd.DataFrame | None]) -> None:
    from research import orthogonal_sweep
    monkeypatch.setattr(orthogonal_sweep, "_bars", lambda sym, _tf="H1": frames.get(sym))
    family_inputs._RUNTIME_BAR_CACHE.clear()


def _signals(primary: pd.DataFrame, factors: list[pd.DataFrame]) -> list:
    call = family_inputs.strip_identity_keys("cross_asset_residual", PARAMS)
    return family_cross_asset_residual(primary, factors=factors, **call)


def test_present_factors_rebuild_identically_to_the_certificate_path(monkeypatch) -> None:
    w = _world()
    _store(monkeypatch, w)
    extra, why, prov = family_inputs.resolve_with_provenance(
        "XAUUSD", "cross_asset_residual", PARAMS, w["XAUUSD"])
    assert why == "ok" and extra is not None
    assert prov["alignment"] == "EXACT" and prov["proxy_fed"] is False
    assert [f["source"] for f in prov["factors"]] == ["OWN", "OWN"]
    # `build_cell` hands the family the store's raw frames: the same frames, the same signals.
    cert = _signals(w["XAUUSD"], [w["USDX"], w["UST10Y"]])
    fwd = _signals(w["XAUUSD"], extra["factors"])
    assert cert, "the synthetic world must fire for the comparison to mean anything"
    assert [(s.time, s.side, s.stop, s.target) for s in fwd] == \
        [(s.time, s.side, s.stop, s.target) for s in cert]


def test_misaligned_sparse_session_no_longer_empties_the_frame(monkeypatch) -> None:
    w = _world()
    rng = np.random.default_rng(3)
    bond = w["UST10Y"]
    in_session = (bond.index.hour >= 12) & (bond.index.hour < 21)
    sparse = bond[in_session & (rng.random(len(bond)) < 0.3)]          # close-only tape
    frames = dict(w, UST10Y=sparse)
    _store(monkeypatch, frames)
    # The certification-path join (raw frames, inner) starves: the family emits nothing.
    assert _signals(w["XAUUSD"], [w["USDX"], sparse]) == []
    extra, why, prov = family_inputs.resolve_with_provenance(
        "XAUUSD", "cross_asset_residual", PARAMS, w["XAUUSD"])
    assert why == "ok", why
    assert prov["alignment"] == "ASOF"
    assert prov["exact_rows"] < prov["floor_rows"] <= prov["asof_rows"]
    assert _signals(w["XAUUSD"], extra["factors"]), "the aligned basket must reach the family"


def test_missing_factor_without_permission_is_named_never_silent(monkeypatch) -> None:
    w = _world()
    _store(monkeypatch, dict(w, UST10Y=None))
    extra, why, prov = family_inputs.resolve_with_provenance(
        "XAUUSD", "cross_asset_residual", PARAMS, w["XAUUSD"])
    assert extra is None
    assert why.startswith(fi.NEEDS_PROXY_FACTOR) and "UST10Y" in why
    assert "factor_proxy" in why and "UST05Y" in why, "the available proxy is named"
    assert prov["needs"] == ["UST10Y"]


def test_missing_factor_with_permission_is_a_labelled_proxy(monkeypatch) -> None:
    w = _world()
    _store(monkeypatch, dict(w, UST10Y=None))
    extra, why, prov = family_inputs.resolve_with_provenance(
        "XAUUSD", "cross_asset_residual", dict(PARAMS, factor_proxy=True), w["XAUUSD"])
    assert why == "ok" and extra is not None
    assert prov["proxy_fed"] is True
    leg = prov["factors"][1]
    assert leg == {"factor": "UST10Y", "source": "PROXY", "proxy": "UST05Y",
                   "own_bars": "no bars on this chart from any source"}
    assert extra["factors"][1] is not None
    # the permission key never reaches the family
    assert "factor_proxy" not in family_inputs.strip_identity_keys(
        "cross_asset_residual", dict(PARAMS, factor_proxy=True))


def test_no_fresh_rates_neighbour_is_needs_proxy_factor(monkeypatch) -> None:
    w = _world()
    stale = w["UST05Y"][w["UST05Y"].index < w["UST05Y"].index[len(w["UST05Y"]) // 2]]
    _store(monkeypatch, dict(w, UST10Y=None, UST05Y=stale))
    extra, why, _prov = family_inputs.resolve_with_provenance(
        "XAUUSD", "cross_asset_residual", dict(PARAMS, factor_proxy="allow"), w["XAUUSD"])
    assert extra is None and why.startswith(fi.NEEDS_PROXY_FACTOR)
    assert "UST05Y" in why and "trading hours behind" in why


def test_stale_own_factor_is_not_used_silently(monkeypatch) -> None:
    w = _world()
    usdx = w["USDX"][w["USDX"].index < w["USDX"].index[-2000]]
    _store(monkeypatch, dict(w, USDX=usdx))
    extra, why, prov = family_inputs.resolve_with_provenance(
        "XAUUSD", "cross_asset_residual", PARAMS, w["XAUUSD"])
    assert extra is None and why.startswith(fi.NEEDS_PROXY_FACTOR) and "USDX" in why
    assert prov["factors"][0]["source"] == "MISSING"


def test_synthetic_usdx_proxy_is_the_ice_basket(monkeypatch) -> None:
    from research.synthetic_usdx import CONSTANT, WEIGHTS
    w = _world()
    idx = w["XAUUSD"].index
    rng = np.random.default_rng(11)
    legs = {s: _bars(1.1 * np.exp(np.cumsum(rng.normal(0, 2e-4, len(idx)))), idx)
            for s in WEIGHTS}
    _store(monkeypatch, dict(w, USDX=None, **legs))
    extra, why, prov = family_inputs.resolve_with_provenance(
        "XAUUSD", "cross_asset_residual", dict(PARAMS, factor_proxy=True), w["XAUUSD"])
    assert why == "ok" and prov["factors"][0]["proxy"] == fi.SYNTH_USDX
    got = extra["factors"][0]["close"]
    want = np.exp(np.log(CONSTANT) + sum(wt * np.log(legs[s]["close"].to_numpy())
                                         for s, wt in WEIGHTS.items()))
    np.testing.assert_allclose(got.to_numpy(), want, rtol=1e-12)


def test_asof_join_never_reads_a_later_factor_bar() -> None:
    idx = _weekday_index(days=3)
    rng = np.random.default_rng(5)
    keep = rng.random(len(idx)) < 0.25
    factor = _bars(100 + np.cumsum(rng.normal(0, 0.1, len(idx))), idx)[keep]
    tol = pd.Timedelta(minutes=60)
    aligned = fi.asof_align(factor, idx, tol)
    for t, v in aligned["close"].dropna().items():
        prior = factor.loc[:t, "close"]
        assert v == prior.iloc[-1] and t - prior.index[-1] <= tol
    # rewriting every factor bar AFTER a cut changes nothing at or before it
    cut = idx[len(idx) // 2]
    future = factor.copy()
    future.loc[future.index > cut, "close"] += 1000.0
    again = fi.asof_align(future, idx, tol)
    pd.testing.assert_series_equal(aligned["close"][aligned.index <= cut],
                                   again["close"][again.index <= cut])


def test_a_coarser_factor_chart_is_refused_not_aligned(monkeypatch) -> None:
    w = _world()
    hourly = w["UST10Y"].resample("1h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    hourly = hourly[hourly.index.hour >= 12]
    _store(monkeypatch, dict(w, UST10Y=hourly))
    extra, why, _prov = family_inputs.resolve_with_provenance(
        "XAUUSD", "cross_asset_residual", PARAMS, w["XAUUSD"])
    assert extra is None and why.startswith(fi.FACTOR_FRAME_STARVED)
    assert "closes after" in why


def test_clock_fence_counts_the_named_cause() -> None:
    import importlib
    from datetime import UTC, datetime
    sys.path.insert(0, str(_ROOT / "scripts"))
    law = importlib.import_module("check_certificate_clock_law")
    cert = {"name": "c", "symbol": "XAUUSD", "family": "cross_asset_residual",
            "selector": "asia", "side": "LONG", "certified_at": "2026-09-25T00:00:00+00:00"}
    row = {"status": "NEEDS_PROXY_FACTOR", "n": 0, "last_error": "NEEDS_PROXY_FACTOR: UST10Y",
           "forward_start": "2026-09-26T00:00:00+00:00"}
    e = law.judge(cert, "k", row, [], 72.0, "t", datetime(2026, 10, 20, tzinfo=UTC))
    assert e["verdict"] == "BLOCKED" and e["blocked_cause"] == "NEEDS_PROXY_FACTOR"


@pytest.mark.parametrize("expr", [["ts_backfill", ["std", "spread", 12], 3]])
def test_replay_diagnosis_names_a_degenerate_formula(expr) -> None:
    from mt5desk.replay_diagnosis import zero_signal_cause
    idx = pd.date_range("2026-07-01", periods=1500, freq="h", tz="UTC")
    bars = _bars(1.3 + np.cumsum(np.random.default_rng(1).normal(0, 1e-3, len(idx))), idx)
    bars["spread"] = 7                                   # a feed whose spread never moves
    why = zero_signal_cause("formula", bars, {"expr": expr, "norm": 240, "entry_z": 1.5},
                            n_signals=0)
    assert why.startswith("FORMULA_DEGENERATE_SIGNAL"), why


def test_replay_diagnosis_names_a_starved_residual_join() -> None:
    from mt5desk.replay_diagnosis import zero_signal_cause
    w = _world()
    sparse = w["UST10Y"].iloc[::50]
    why = zero_signal_cause("cross_asset_residual", w["XAUUSD"],
                            dict(PARAMS, factors=[w["USDX"], sparse]), n_signals=0)
    assert why.startswith("RESIDUAL_FRAME_BELOW_FLOOR"), why
