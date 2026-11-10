"""The cross_asset_residual rule in the replication spec book, checked AGAINST the original
family, its session filter and the miners' modifiers -- which only this test may import."""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402

N = 2600


def _frames() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(5)
    t = pd.date_range("2023-01-01", periods=N, freq="h", tz="UTC")
    f1 = np.exp(np.cumsum(rng.normal(0, 1e-3, N)))
    f2 = np.exp(np.cumsum(rng.normal(0, 1e-3, N)))
    noise = np.zeros(N)
    for i in range(1, N):
        noise[i] = 0.97 * noise[i - 1] + rng.normal(0, 6e-4)
    y = np.exp(0.6 * np.log(f1) - 0.3 * np.log(f2) + noise)

    def frame(c: np.ndarray) -> pd.DataFrame:
        o = np.r_[c[0], c[:-1]]
        h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 3e-4, N)))
        lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 3e-4, N)))
        return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=t)

    out = {"TGT": frame(y), "FA": frame(f1), "FB": frame(f2)}
    out["FB"] = out["FB"].drop(out["FB"].index[[500, 501, 1700]])   # the join is exercised
    return out


@pytest.fixture()
def world(tmp_path: Path, monkeypatch):
    dfs = _frames()
    for k, d in dfs.items():
        d.rename_axis("time").to_parquet(tmp_path / f"{k}_H1.parquet")
    real = rc.load_bars
    monkeypatch.setattr(rc, "load_bars",
                        lambda s, tf="H1", universe=None: real(s, tf, universe=tmp_path))
    return dfs, rc.load_bars("TGT", "H1")


CASES = [{}, {"regime": "high_vol"}, {"regime": "low_vol", "entry_timing": "delayed"},
         {"session": "asia"}, {"session": "asia", "entry_timing": "delayed",
                               "execution_style": "market"},
         {"side_mode": "continue", "entry_z": 1.5}]


@pytest.mark.parametrize("case", CASES, ids=lambda c: ",".join(f"{k}={v}" for k, v in c.items())
                         or "plain")
def test_the_rule_signals_where_the_family_and_its_modifiers_do(world, case) -> None:
    from mt5desk import cell_modifiers
    from mt5desk.families_orthogonal import family_cross_asset_residual
    from mt5desk.family_call import session_filter
    dfs, bars = world
    params = {"lookback": 240, "beta_win": 240, "entry_z": 2.0, "ttl_bars": 8,
              "side_mode": "revert", **case}
    call = {k: v for k, v in params.items()
            if k in ("lookback", "beta_win", "entry_z", "ttl_bars", "side_mode")}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sig = family_cross_asset_residual(dfs["TGT"], factors=[dfs["FA"], dfs["FB"]], **call)
    sig = session_filter(sig, params.get("session"))
    mods = {k: params[k] for k in ("regime", "entry_timing", "execution_style") if k in params}
    sig = cell_modifiers.apply(sig, dfs["TGT"], mods) if mods else sig
    p, why = rc.resolve_spec("cross_asset_residual", {**params, "factor_symbols": ["FA", "FB"]},
                             "asia", None)
    assert why == "ok" and p is not None
    orders = rc._build_cross_asset_residual(bars, p)
    assert sig, "the planted residual must fire"
    assert [(int(s.time.value), s.side) for s in sig] == [(o.t_ns, o.side) for o in orders]
    # Stop and target too: the family measures them from the signal bar's own close (LIVE,
    # 2026-11-06), and the default reference reproduces it.
    assert [s.ttl_bars for s in sig] == [o.ttl_bars for o in orders]
    np.testing.assert_allclose([(s.stop, s.target) for s in sig],
                               [(o.stop, o.target) for o in orders], rtol=1e-12, atol=0)


def test_signal_close_is_the_default_reference_and_any_other_stands_aside(world) -> None:
    _dfs, bars = world
    base = {"lookback": 240, "entry_z": 2.0, "ttl_bars": 8, "side_mode": "revert",
            "factor_symbols": ["FA", "FB"]}
    p, _ = rc.resolve_spec("cross_asset_residual", {**base, "reference": "prev_row"},
                           "asia", None)
    q, _ = rc.resolve_spec("cross_asset_residual", base, "asia", None)
    assert p is not None and q is not None and q["reference"] == "signal_close"
    prev, close = rc._build_cross_asset_residual(bars, p), rc._build_cross_asset_residual(bars, q)
    assert prev and [(o.t_ns, o.side) for o in prev] == [(o.t_ns, o.side) for o in close]
    pos = np.searchsorted(bars.t, [o.t_ns for o in close])
    for o, j in zip(close, pos, strict=True):
        mid = o.stop + (o.target - o.stop) * (1.0 / 2.5)       # stop 2 ATR, target 3 ATR away
        assert mid == pytest.approx(float(bars.c[j]), rel=1e-12)
    assert any(a.stop != b.stop for a, b in zip(prev, close, strict=True))
    r, _ = rc.resolve_spec("cross_asset_residual", {**base, "reference": "open"}, "asia", None)
    assert r is not None and rc._build_cross_asset_residual(bars, r) == []


def test_a_missing_factor_or_an_undefined_modifier_stands_aside(world) -> None:
    _dfs, bars = world
    base = {"lookback": 240, "entry_z": 2.0, "ttl_bars": 8, "side_mode": "revert"}
    p, _ = rc.resolve_spec("cross_asset_residual", {**base, "factor_symbols": ["FA", "NOPE"]},
                           "asia", None)
    assert p is not None and rc._build_cross_asset_residual(bars, p) == []
    for extra in ({"regime": "risk_on"}, {"entry_timing": "late"},
                  {"execution_style": "limit"}):
        p, _ = rc.resolve_spec("cross_asset_residual",
                               {**base, "factor_symbols": ["FA", "FB"], **extra}, "asia", None)
        assert p is not None and rc._build_cross_asset_residual(bars, p) == [], extra


@pytest.mark.parametrize("family", ["formula", "cross_asset_residual"])
def test_the_session_is_the_cells_parameter_never_the_stamped_selector(family) -> None:
    """The sweep stamps "asia" on every certificate whose params name no window; such a cell was
    judged on every hour, so the rebuild must not cut it to 0-8."""
    p, _ = rc.resolve_spec(family, {}, "asia", None)
    assert p is not None and p["_session"] is None
    p, _ = rc.resolve_spec(family, {"session": "london"}, "asia", None)
    assert p is not None and p["_session"] == rc.SESSIONS["london"]
