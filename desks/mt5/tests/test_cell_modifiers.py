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
    assert "risk" in cm.refusal({"regime": "risk_neutral"})
    assert "fill model" in cm.refusal({"execution_style": "iceberg"})
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


def test_selector_is_the_shared_session_axis_not_a_family_parameter() -> None:
    b = _bars(48)
    sigs = [_sig(b, i) for i in range(len(b))]
    kwargs, mods = cm.split(fam, {"lookback": 3, "selector": "ny"})
    assert kwargs == {"lookback": 3} and mods == {"selector": "ny"}
    assert cm.refusal(mods) is None
    got = cm.apply(sigs, b, mods)
    assert got and all(14 <= s.time.hour < 22 for s in got)
    assert "session window" in cm.refusal({"selector": "invented"})


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
    selected = fc.signals(fam, bars, side=1, params={"lookback": 3, "selector": "asia"})
    assert selected == plain
    with pytest.raises(ValueError, match="NOT_RUN_MODIFIER"):
        fc.signals(fam, bars, side=1, params={"regime": "risk_neutral"})


# ------------------------------------------------------------ states the desk already computes
def _state_file(tmp_path: Path, bars: pd.DataFrame) -> Path:
    """A free_states-shaped file: risk-off in the first half, risk-on in the second."""
    n = len(bars)
    frame = pd.DataFrame({"gold_risk_off_z": np.where(np.arange(n) < n // 2, 1.0, -1.0),
                          "gold_macro_stress": np.where(np.arange(n) % 2 == 0, 0.9, 0.1)},
                         index=bars.index)
    path = tmp_path / "free_states.parquet"
    frame.to_parquet(path)
    return path


def test_risk_regimes_use_the_published_risk_state(tmp_path, monkeypatch) -> None:
    b = _bars(40)
    monkeypatch.setattr(cm, "STATE_FILE", _state_file(tmp_path, b))
    sigs = [_sig(b, i) for i in range(len(b))]
    assert cm.refusal({"regime": "risk_off"}) is None
    assert cm.refusal({"regime": "risk_on"}) is None
    off = cm.apply(sigs, b, {"regime": "risk_off"})
    on = cm.apply(sigs, b, {"regime": "risk_on"})
    assert [s.time for s in off] == list(b.index[:20])
    assert [s.time for s in on] == list(b.index[20:])


def test_a_stale_or_absent_state_keeps_nothing_and_refuses_by_name(tmp_path, monkeypatch) -> None:
    b = _bars(40)
    monkeypatch.setattr(cm, "STATE_FILE", _state_file(tmp_path, b.iloc[:5]))
    later = [_sig(b, i) for i in range(30, 40)]          # days past the last state print
    assert cm.apply(later, b, {"regime": "risk_off"}) == []
    monkeypatch.setattr(cm, "STATE_FILE", tmp_path / "absent.parquet")
    assert "UNMEASURED" in cm.refusal({"regime": "risk_on"})
    assert "UNMEASURED" in cm.refusal({"conditioner": "macro"})


def test_macro_seasonality_and_microstructure_conditioners_apply(tmp_path, monkeypatch) -> None:
    from mt5desk.family_generic import _CONTEXTS

    b = _bars(200)
    monkeypatch.setattr(cm, "STATE_FILE", _state_file(tmp_path, b))
    sigs = [_sig(b, i) for i in range(len(b))]
    for cond in ("macro", "seasonality", "microstructure"):
        assert cm.refusal({"conditioner": cond}) is None, cond
    macro = cm.apply(sigs, b, {"conditioner": "macro"})
    assert [s.time for s in macro] == list(b.index[::2])
    low_liq = pd.Series(_CONTEXTS["low_liquidity"](b), index=b.index).fillna(False)
    micro = cm.apply(sigs, b, {"conditioner": "microstructure"})
    assert [s.time for s in micro] == [t for t in b.index if bool(low_liq[t])]


def test_limit_style_rests_a_passive_order_at_the_signal_close() -> None:
    b = _bars(30)
    resting = _sig(b, 3, trigger=123.0)
    out = cm.apply([_sig(b, 2), resting], b, {"execution_style": "limit"})
    assert cm.refusal({"execution_style": "limit"}) is None
    assert out[0].trigger == float(b["close"].iloc[2]) and out[0].wait_bars == 1
    assert out[0].order_type == "limit"            # DECLARED, never inferred from the next open
    assert len(out) == 1          # a family's own stop entry has no limit expression: dropped


def _gap_bars(opens: list[float], highs: list[float], lows: list[float],
              closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(opens), freq="h", tz="UTC")
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes}, index=idx)


def _entry(b: pd.DataFrame, sigs: list) -> float:
    from mt5desk.engine import Costs, run_backtest

    res = run_backtest(b, sigs, Costs())
    assert res.n == 1, res.n
    return float(res.trades[0].entry)


def test_a_limit_buy_after_a_gap_down_fills_no_worse_than_market() -> None:
    # Signal close 100, next bar gaps DOWN to open 99. Market buys at 99. A real limit at 100
    # fills at min(open, limit) = 99 -- the inferred trigger used to fill it as a STOP at 100.
    b = _gap_bars([100, 100, 99, 99, 99, 99], [100.2, 100.2, 99.5, 99.5, 99.5, 99.5],
                  [99.8, 99.8, 98.5, 98.5, 98.5, 98.5], [100, 100, 99, 99, 99, 99])
    sig = Signal(time=b.index[1], side=1, stop=97.0, target=110.0, ttl_bars=3, tag="t")
    limited = cm.apply([sig], b, {"execution_style": "limit"})
    assert _entry(b, limited) <= _entry(b, [sig])
    assert _entry(b, limited) == 99.0


def test_a_limit_sell_after_a_gap_up_fills_no_worse_than_market() -> None:
    b = _gap_bars([100, 100, 101, 101, 101, 101], [100.2, 100.2, 101.5, 101.5, 101.5, 101.5],
                  [99.8, 99.8, 100.5, 100.5, 100.5, 100.5], [100, 100, 101, 101, 101, 101])
    sig = Signal(time=b.index[1], side=-1, stop=103.0, target=90.0, ttl_bars=3, tag="t")
    limited = cm.apply([sig], b, {"execution_style": "limit"})
    assert _entry(b, limited) >= _entry(b, [sig])
    assert _entry(b, limited) == 101.0


def test_an_untouched_limit_never_fills() -> None:
    # Next bar opens ABOVE the buy limit and its low never comes back to it.
    b = _gap_bars([100, 100, 101, 102, 103, 104], [100.2, 100.2, 101.5, 102.5, 103.5, 104.5],
                  [99.8, 99.8, 100.5, 101.5, 102.5, 103.5], [100, 100, 101, 102, 103, 104])
    sig = Signal(time=b.index[1], side=1, stop=97.0, target=110.0, ttl_bars=3, tag="t")
    from mt5desk.engine import Costs, run_backtest

    assert run_backtest(b, cm.apply([sig], b, {"execution_style": "limit"}), Costs()).n == 0


def test_the_engine_fills_the_limit_only_on_a_touch() -> None:
    from mt5desk.engine import Costs, run_backtest

    idx = pd.date_range("2026-01-01", periods=6, freq="h", tz="UTC")
    close = np.array([100.0, 100.0, 101.0, 102.0, 103.0, 104.0])
    b = pd.DataFrame({"open": close, "high": close + 0.2, "low": close - 0.2, "close": close},
                     index=idx)
    sig = Signal(time=idx[1], side=1, stop=99.0, target=105.0, ttl_bars=3, tag="t")
    limited = cm.apply([sig], b, {"execution_style": "limit"})
    # The next bar opens at 101 and never trades back to 100: no touch, no trade.
    assert run_backtest(b, limited, Costs()).n == 0
    assert run_backtest(b, [sig], Costs()).n == 1


def test_residual_frame_is_inert_until_the_sealed_patch_lands() -> None:
    assert "residualise" in cm.refusal({"residual": "gold", "residual_tag": "residual"})
    b = _bars(400)
    f = _bars(400).assign(close=lambda d: d["close"] * 1.01)
    r = cm.residual_frame(b, f, win=50)
    assert r is not None and (r["high"] >= r["low"]).all()
    sig = _sig(r, 300)
    back = cm.residual_signals_to_real([sig], b, r)[0]
    k = float(r["close"].iloc[300] / b["close"].iloc[300])
    assert back.stop == pytest.approx(sig.stop / k) and back.time == sig.time
