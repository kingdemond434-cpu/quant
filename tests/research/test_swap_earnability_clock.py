"""Discrete rollover belongs to a held position, not the bar carrying its entry stamp."""
import numpy as np
import pandas as pd
import pytest

from libs.research import earnability as e


def flows():
    index = pd.date_range("2026-01-01", periods=4, freq="D", tz="UTC")
    return pd.Series([1.0, -2.0, 3.0, 4.0], index=index)


def test_settlement_milliseconds_do_not_change_booking_phase():
    original = flows()
    delayed = original.copy()
    delayed.index += pd.to_timedelta([1, 12, 37, 4], unit="ms")
    for phase in e.PHASES:
        pd.testing.assert_series_equal(e.bin_flows(original, phase=phase),
                                       e.bin_flows(delayed, phase=phase))
    booked = e.bin_flows(original, phase=e.BOOKED)
    earnable = e.bin_flows(original, phase=e.EARNABLE)
    assert booked.loc[original.index[0]] == 1
    assert earnable.loc[original.index[0]] == -2


@pytest.mark.parametrize("phase", e.PHASES)
def test_panel_honors_each_symbol_clock_and_empty_inputs(phase):
    f = flows()
    result = e.bin_panel({"USDJPY": f, "CHFSGD": f * 2}, phase=phase)
    np.testing.assert_allclose(result.CHFSGD, result.USDJPY * 2)
    pd.testing.assert_frame_equal(result, e.bin_panel(pd.DataFrame({"USDJPY": f,
                                                                  "CHFSGD": f * 2}), phase=phase))
    assert e.bin_panel({}, phase=phase).empty
    assert e.bin_panel({"empty": f[:0]}, phase=phase).empty
    assert e.bin_flows(f[:0], phase=phase).empty


def test_earnable_flow_is_strictly_after_entry_through_exit():
    f = flows()
    result = e.attributable(f, f.index[0], f.index[2])
    assert (result.n_flows, result.n_earnable, result.n_unearnable) == (4, 2, 2)
    assert result.booked == 6 and result.earnable == 1 and result.unearnable == 5
    assert result.unearnable_share == pytest.approx(5 / 6)
    delayed = e.attributable(f, f.index[0], f.index[2], decision_ts=f.index[1], latency_s=1)
    assert delayed.n_earnable == 1 and delayed.earnable == 3
    empty = e.attributable(f[:0], f.index[0], f.index[2])
    assert empty.n_flows == 0 and empty.unearnable_share == 0


def test_invalid_clocks_and_negative_latency_refused():
    f = flows()
    with pytest.raises(ValueError, match="positive"):
        e.normalise_stamps(f.index, 0)
    with pytest.raises(TypeError, match="DatetimeIndex"):
        e.normalise_stamps([1, 2])
    with pytest.raises(ValueError, match="tz-aware"):
        e.normalise_stamps(f.index.tz_localize(None))
    with pytest.raises(ValueError, match="phase"):
        e.bin_flows(f, phase="invented")
    with pytest.raises(TypeError):
        e.bin_flows(pd.Series([1, 2]), phase=e.BOOKED)
    with pytest.raises(TypeError):
        e.attributable(pd.Series([1, 2]), f.index[0], f.index[2])
    with pytest.raises(ValueError, match="non-negative"):
        e.attributable(f, f.index[0], f.index[2], latency_s=-1)


def test_payout_convention_sign_flip_is_not_claimed_robust():
    panel = pd.DataFrame({"r": [0.001, 0.002, 0.003, 0.004]})
    result = e.phase_sensitivity(lambda p: p.r.to_numpy(),
                                 {e.BOOKED: panel, e.EARNABLE: -panel})
    assert result.convention_dependent and result.sign_flip and result.n == 4
    assert result.d_mean_bps == pytest.approx(50)
    stable = e.phase_sensitivity(lambda p: p.r.to_numpy(),
                                 {e.BOOKED: panel, e.EARNABLE: panel.copy()})
    assert not stable.convention_dependent and not stable.sign_flip
    with pytest.raises(ValueError, match="missing"):
        e.phase_sensitivity(lambda p: p.r.to_numpy(), {e.BOOKED: panel})
    empty = e.phase_sensitivity(lambda _: np.array([np.nan]),
                                {e.BOOKED: panel, e.EARNABLE: panel})
    assert np.isnan(empty.d_sharpe) and empty.n == 0
    assert np.isnan(e._sharpe(np.ones(4)))
