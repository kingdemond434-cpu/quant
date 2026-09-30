"""`cell_modifiers`: the miners' variant keys are applied or refused by name, never passed."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5desk import cell_modifiers as cm
from mt5desk.engine import Signal


def _bars(n: int = 400) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.2 + 0.4 * (np.arange(n) > n // 2), n))
    return pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3,
                         "close": close}, index=idx)


def _sig(bars: pd.DataFrame, i: int, side: int = 1, trigger: float | None = None) -> Signal:
    c = float(bars["close"].iloc[i])
    return Signal(time=bars.index[i], side=side, stop=c - side * 1.0, target=c + side * 2.0,
                  ttl_bars=5, tag="t", trigger=trigger)


def fam(df, lookback: int = 5, side: int = 1):
    return []


def fam_kw(df, **kw):
    return []


def test_only_keys_the_family_would_reject_are_moved() -> None:
    kwargs, mods = cm.split(fam, {"lookback": 3, "regime": "high_vol", "side_mode": "revert"})
    assert kwargs == {"lookback": 3}
    assert mods == {"regime": "high_vol", "side_mode": "revert"}


def test_a_family_taking_kwargs_is_left_exactly_as_it_was_called() -> None:
    params = {"lookback": 3, "regime": "high_vol"}
    assert cm.split(fam_kw, params) == (params, {})


def test_a_family_that_names_the_key_keeps_it() -> None:
    def native(df, regime: str = "x"):
        return []
    assert cm.split(native, {"regime": "high_vol"}) == ({"regime": "high_vol"}, {})


def test_unapplicable_variants_are_refused_by_name() -> None:
    assert "risk" in cm.refusal({"regime": "risk_off"})
    assert "fill model" in cm.refusal({"execution_style": "limit"})
    assert "conditioning series" in cm.refusal({"conditioner": "carry"})
    assert "residualise" in cm.refusal({"residual": "usd", "residual_tag": "residual"})
    assert cm.refusal({"regime": "high_vol", "side_mode": "revert", "entry_timing": "delayed",
                       "execution_style": "market", "representation": "cross_asset"}) is None


def test_revert_mirrors_around_the_close_with_the_same_risk_geometry() -> None:
    b = _bars()
    s = _sig(b, 50)
    (f,) = cm.apply([s], b, {"side_mode": "revert"})
    c = float(b["close"].iloc[50])
    assert f.side == -1 and f.time == s.time
    assert abs((f.stop - c) - (c - s.stop)) < 1e-9 and abs((c - f.target) - (s.target - c)) < 1e-9


def test_revert_of_a_resting_trigger_fades_it_at_the_same_level() -> None:
    b = _bars()
    c = float(b["close"].iloc[60])
    s = _sig(b, 60, trigger=c + 0.5)
    (f,) = cm.apply([s], b, {"side_mode": "revert"})
    assert f.trigger == s.trigger and f.side == -1 and f.stop > f.trigger > f.target


def test_delayed_moves_one_bar_and_drops_the_last_bar() -> None:
    b = _bars()
    out = cm.apply([_sig(b, 10), _sig(b, len(b) - 1)], b, {"entry_timing": "delayed"})
    assert [s.time for s in out] == [b.index[11]]


def test_volatility_regime_uses_the_generic_family_definition() -> None:
    from mt5desk.family_generic import _CONTEXTS

    b = _bars()
    sigs = [_sig(b, i) for i in range(120, 400, 7)]
    hi = cm.apply(sigs, b, {"regime": "high_vol"})
    lo = cm.apply(sigs, b, {"regime": "low_vol"})
    mask = _CONTEXTS["high_vol"](b)
    assert hi and lo and all(bool(mask[s.time]) for s in hi)
    assert not ({s.time for s in hi} & {s.time for s in lo})


def test_quarter_end_is_month_end_in_a_quarters_last_month() -> None:
    idx = pd.date_range("2026-02-20", "2026-04-05", freq="D", tz="UTC")
    b = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    sigs = [Signal(time=t, side=1, stop=0.9, target=1.2, ttl_bars=1, tag="t") for t in idx]
    got = {s.time.strftime("%m-%d") for s in cm.apply(sigs, b, {"regime": "quarter_end"})}
    assert got == {f"03-{d}" for d in range(26, 32)}


def test_no_modifiers_is_the_identity() -> None:
    b = _bars()
    sigs = [_sig(b, 5)]
    assert cm.apply(sigs, b, {}) == sigs
    assert cm.apply(sigs, b, {"representation": "price_only", "cost_aware": True}) == sigs


def test_family_call_applies_the_same_modifiers_the_gauntlet_does():
    """The forward clock and the live executor call `family_call.signals`; a cell the gauntlet
    certified with a variant key must clock the same signals; a call without one is unchanged.
    """
    from dataclasses import dataclass

    from mt5desk import family_call as fc

    @dataclass(frozen=True)
    class _S:
        time: object
        side: int
        stop: float
        target: float
        trigger: object = None

    idx = pd.date_range("2026-01-01", periods=5, freq="h")
    bars = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=idx)

    def fam(b, lookback=3):
        return [_S(idx[1], 1, 0.5, 3.0)]

    plain = fc.signals(fam, bars, side=1, params={"lookback": 3})
    assert plain == [_S(idx[1], 1, 0.5, 3.0)]
    flipped = fc.signals(fam, bars, side=1, params={"lookback": 3, "side_mode": "revert"})
    assert flipped == cm.apply(plain, bars, {"side_mode": "revert"})
    assert flipped[0].side == -1
    with pytest.raises(ValueError, match="NOT_RUN_MODIFIER"):
        fc.signals(fam, bars, side=1, params={"regime": "risk_off"})
