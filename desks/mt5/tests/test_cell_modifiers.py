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


def test_unapplicable_variants_are_refused_by_name(monkeypatch) -> None:
    assert "no desk definition" in cm.refusal({"regime": "bull_market"})
    monkeypatch.setattr(cm, "_risk_series", lambda: None)
    assert "UNMEASURED" in cm.refusal({"regime": "risk_off"})
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
        fc.signals(fam, bars, side=1, params={"execution_style": "limit"})


# ------------------------------------------------------------------------- risk-on / risk-off
def _index(n: int = 400, up_until: int = 200) -> pd.Series:
    """An H1 index that rises for `up_until` bars and falls after, on the _bars() clock."""
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    steps = np.where(np.arange(n) < up_until, 0.001, -0.001)
    return pd.Series(100 * np.exp(np.cumsum(steps)), index=idx)


def test_risk_regimes_are_defined_when_a_risk_index_is_on_the_box(monkeypatch) -> None:
    monkeypatch.setattr(cm, "_risk_series", lambda: ("US500", _index()))
    assert cm.refusal({"regime": "risk_on"}) is None
    assert cm.refusal({"regime": "risk_off", "side_mode": "revert"}) is None


def test_risk_state_reads_only_closed_index_bars() -> None:
    """The state at bar t uses index bars closed by t: the turn at bar 200 shows from bar
    200 + RISK_LOOKBACK_BARS / 2 + 1 at the earliest, never before the index has turned."""
    bars, ix = _bars(), _index()
    st = cm.risk_state(bars, ix)
    lb = cm.RISK_LOOKBACK_BARS
    assert (st.iloc[: lb + 1] == 0).all(), "no state until a full lookback is known"
    assert (st.iloc[lb + 1: 200 + 1] == 1).all(), "rising index: risk-on, read one bar late"
    first_off = int(np.argmax(st.to_numpy() == -1))
    assert first_off > 200 + lb // 2, "the state cannot turn before the trailing return does"
    # Shifting the index forward a bar moves the state a bar later: nothing is read early.
    later = cm.risk_state(bars, ix.shift(1).dropna())
    assert int(np.argmax(later.to_numpy() == -1)) == first_off + 1


def test_the_two_risk_states_partition_every_bar_that_has_a_state() -> None:
    bars = _bars()
    st = cm.risk_state(bars, _index())
    on, off = (st == 1), (st == -1)
    assert not (on & off).any() and ((on | off) == (st != 0)).all()
    assert on.sum() > 0 and off.sum() > 0


def test_a_dead_index_feed_has_no_state_rather_than_an_old_one() -> None:
    bars = _bars(400)
    ix = _index(250)                                  # the index stops at bar 249
    st = cm.risk_state(bars, ix)
    cut = 250 + int(cm.RISK_STALE_H)
    assert (st.iloc[cut + 1:] == 0).all() and (st.iloc[200:249] != 0).all()


def test_apply_keeps_a_signal_only_in_its_own_risk_state(monkeypatch) -> None:
    monkeypatch.setattr(cm, "_risk_series", lambda: ("US500", _index()))
    bars = _bars()
    sigs = [_sig(bars, 150), _sig(bars, 390)]
    assert [s.time for s in cm.apply(sigs, bars, {"regime": "risk_on"})] == [bars.index[150]]
    assert [s.time for s in cm.apply(sigs, bars, {"regime": "risk_off"})] == [bars.index[390]]


def test_mixed_clocks_are_refused_never_guessed() -> None:
    """A naive bar index beside a tz-aware risk index (or the reverse) cannot say which wall it
    carries; converting would read the state hours early. Refused both ways, loudly."""
    bars = _bars()
    naive = bars.copy()
    naive.index = naive.index.tz_convert(None)
    with pytest.raises(ValueError, match="mixed clocks"):
        cm.risk_state(naive, _index())
    ix = _index()
    naive_ix = pd.Series(ix.to_numpy(), index=ix.index.tz_convert(None))
    with pytest.raises(ValueError, match="mixed clocks"):
        cm.risk_state(bars, naive_ix)


def test_one_clock_on_both_sides_reads_the_same_state() -> None:
    bars = _bars()
    naive = bars.copy()
    naive.index = naive.index.tz_convert(None)
    ix = _index()
    naive_ix = pd.Series(ix.to_numpy(), index=ix.index.tz_convert(None))
    a = cm.risk_state(bars, ix).to_numpy()
    b = cm.risk_state(naive, naive_ix).to_numpy()
    assert (a == b).all()


def test_the_risk_state_is_computed_once_per_index_frame(monkeypatch) -> None:
    import mt5desk.family_learned_propagation as flp

    frame = pd.DataFrame({"close": _index().to_numpy()}, index=_index().index)
    calls = {"n": 0}
    real = cm._risk_sign

    def counting(series):
        calls["n"] += 1
        return real(series)

    monkeypatch.setattr(cm, "_RISK_MEMO", {})
    monkeypatch.setattr(cm, "_risk_sign", counting)
    monkeypatch.setattr(cm, "_risk_symbols", lambda: ("US500",))
    current = {"df": frame}
    monkeypatch.setattr(flp, "load_peer", lambda sym: current["df"])
    bars = _bars()
    a = cm.risk_state(bars)
    b = cm.risk_state(bars)
    assert calls["n"] == 1, "same parquet (same cached frame): the sign is reused"
    assert a.equals(b)
    current["df"] = frame.copy()          # load_peer re-read the file: a new frame object
    cm.risk_state(bars)
    assert calls["n"] == 2, "a changed parquet recomputes"


def test_the_definitions_version_names_the_risk_regimes() -> None:
    assert set(cm.NEWLY_DEFINED[cm.DEFINITIONS_VERSION]) == set(cm.RISK_REGIMES)
