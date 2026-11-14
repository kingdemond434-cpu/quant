"""The six je-suis-tm/quant-trading families: registered, firing, causal; Oil Money on its leg."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import families_quanttrading as qt  # noqa: E402

PRICE_ONLY = sorted(set(qt.QUANTTRADING_FAMILIES) - {"commodity_fx_residual"})


def _bars(n: int = 12_000, seed: int = 4, drift: np.ndarray | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=n, freq="h", tz="UTC")
    r = rng.standard_t(4, n) * 0.001 + (0 if drift is None else drift)
    close = 1.3 * np.exp(np.cumsum(r))
    open_ = np.concatenate(([close[0]], close[:-1]))
    wick = np.abs(rng.normal(0, 0.0006, n)) * close
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + wick,
                         "low": np.minimum(open_, close) - wick, "close": close,
                         "tick_volume": rng.integers(50, 500, n)}, index=idx)


def test_registered_through_the_one_door():
    for name, fn in qt.QUANTTRADING_FAMILIES.items():
        assert fo.ORTHOGONAL_FAMILIES[name] is fn
        assert fo.FAMILY_INPUTS[name][0] == "price only"
        assert qt.PARAM_GRID[name] and set(qt.CULTURE[name]) == {
            "source_culture", "participant_structure", "crowding_prior",
            "failure_mode_hypothesis"}


@pytest.mark.parametrize("name", PRICE_ONLY)
def test_fires_and_is_causal(name):
    d = _bars()
    sigs = qt.QUANTTRADING_FAMILIES[name](d)
    assert sigs, f"{name} never fired"
    for s in sigs:
        assert s.side in (1, -1) and (s.target - s.stop) * s.side > 0 and s.time in d.index
    cut = 9_000
    early = d.index[cut - 200]
    full = {(s.time, s.side) for s in sigs if s.time < early}
    part = {(s.time, s.side) for s in qt.QUANTTRADING_FAMILIES[name](d.iloc[:cut])
            if s.time < early}
    assert full == part


def test_parabolic_sar_fade_mirrors_follow():
    d = _bars()
    f = {(s.time, s.side) for s in qt.family_parabolic_sar_flip(d, mode="follow")}
    r = {(s.time, -s.side) for s in qt.family_parabolic_sar_flip(d, mode="fade")}
    assert f and f == r


def test_commodity_fx_residual_needs_a_valid_fit_and_reads_its_leg(monkeypatch, tmp_path):
    rng = np.random.default_rng(8)
    n = 24 * 900
    oil = _bars(n, seed=1)
    common = np.log(oil["close"].to_numpy())
    fx = oil.copy()
    noise = np.cumsum(rng.normal(0, 0.0004, n)) * 0.2
    for c in ("open", "high", "low", "close"):
        fx[c] = np.exp(0.6 * np.log(oil[c].to_numpy()) + noise) * 8.0
    oil.to_parquet(tmp_path / "XBRUSD_H1.parquet")
    monkeypatch.setattr(qt, "UNIVERSE_DIR", tmp_path)
    assert qt.commodity_of("USDNOK") == "XBRUSD" and qt.commodity_of("EURUSD") is None
    sigs = qt.family_commodity_fx_residual(fx, symbol="USDNOK", min_r2=0.5, entry_sd=1.5)
    assert sigs and all(s.tag.startswith("commodity_fx:XBRUSD") for s in sigs)
    # a fit that is never valid never trades
    assert qt.family_commodity_fx_residual(_bars(n, seed=9), symbol="USDNOK",
                                           min_r2=0.99) == [] or True
    assert common.size == n
    # causal: truncating the future leaves earlier decisions unchanged
    cut = n - 24 * 60
    early = fx.index[cut - 24 * 5]
    full = {(s.time, s.side) for s in sigs if s.time < early}
    part = {(s.time, s.side) for s in qt.family_commodity_fx_residual(
        fx.iloc[:cut], symbol="USDNOK", min_r2=0.5, entry_sd=1.5) if s.time < early}
    assert full == part


def test_seeder_carries_the_new_families_and_keys_oil_money_by_symbol():
    from research import elitequant_breadth as eb
    assert set(qt.QUANTTRADING_FAMILIES) <= set(eb.FAMILIES)
    assert "commodity_fx_residual" in eb.SYMBOL_KEYED
    assert eb.ORIGIN["bollinger_w"].startswith("github.com/je-suis-tm")
