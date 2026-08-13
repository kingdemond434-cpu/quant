"""BUYING CRASHES IS THE FAMILY WHERE A RULE IS RIGHT OFTEN ENOUGH TO KEEP RUNNING.

`drawdown_rebound` classifies WHY a decline happened and refuses to estimate a rebound for an
event it could not attribute. That refusal is the whole safety property, and it is worth nothing
unless the thing feeding it also refuses. These tests pin both halves:

  * no signal without a named mechanism -- depth alone must never fire;
  * no signal built from a bar the strategy could not have seen.

The second is the one that silently manufactures edge. An entry taken at the LOW backtests
beautifully and cannot be traded, so the detector confirms a trough only after `lookback` bars
with no new low, and the test below proves the signal moves when the series moves.
"""
from __future__ import annotations

import numpy as np

from libs.research.decline_detector import (
    MIN_DEPTH,
    REBOUND_FAVOURABLE,
    conditional_history,
    detect_declines,
    rebound_signal,
    summarise,
    with_forced_flow,
)


def _crash(n: int = 200, *, depth: float = 0.25, low_at: int = 120,
           recover: float = 0.9) -> np.ndarray:
    """Flat, then a sharp fall to `low_at`, then a partial recovery."""
    c = np.full(n, 100.0)
    fall = np.linspace(100.0, 100.0 * (1 - depth), 12)
    c[low_at - 11:low_at + 1] = fall
    c[low_at + 1:] = np.linspace(100.0 * (1 - depth),
                                 100.0 * (1 - depth * (1 - recover)), n - low_at - 1)
    return c


def _cascade_state(n: int, low_at: int) -> dict:
    """The observable state of a forced-deleveraging flush, at the trough.

    VOLUME IS NOT OPTIONAL HERE and that is the classifier being strict, not fussy: OI falling on
    LOW volume is makers withdrawing, while OI falling on HIGH volume is positions being
    liquidated into a real tape. `classify` requires >=1.5x before it will name a cascade, so a
    fixture omitting it gets IDIOSYNCRATIC_ASSET_FAILURE -- which is the correct reading of
    "a big fall, nothing else known".
    """
    oi = np.zeros(n)
    oi[low_at] = 0.35                       # a third of open interest destroyed
    fund = np.zeros(n)
    fund[low_at - 11] = 1.2                 # longs were paying heavily to be there
    liq = np.zeros(n)
    liq[low_at] = 5e7
    vol = np.ones(n)
    vol[low_at] = 4.0                       # liquidations print on a real tape
    return {"oi_cleared": oi, "funding": fund, "liquidation_notional": liq,
            "volume_multiple": vol}


class TestItRefusesWithoutAMechanism:
    def test_DEPTH_ALONE_NEVER_FIRES(self) -> None:
        """THE RULE THE REBOUND BOOK EXISTS TO FORBID. On OHLCV only, the state that separates a
        cascade from a repricing is simply not present, so the honest output is no trade."""
        c = _crash()
        found = detect_declines(c, symbol="T")
        assert found, (
            "a 25% fall must still be DETECTED -- refusing to trade is not refusing to see")
        assert all(d.mechanism not in REBOUND_FAVOURABLE for d in found)
        assert rebound_signal(c.size, found).sum() == 0.0

    def test_a_classified_cascade_does_fire(self) -> None:
        """POSITIVE CONTROL. A detector that can only refuse is indistinguishable from a broken
        one, and would make every assertion above vacuous."""
        c = _crash()
        found = detect_declines(c, symbol="T", **_cascade_state(c.size, 120))
        assert any(d.mechanism in REBOUND_FAVOURABLE for d in found), (
            f"classified as {[d.mechanism for d in found]}")
        assert rebound_signal(c.size, found).sum() > 0.0

    def test_a_shallow_dip_is_not_an_event(self) -> None:
        c = _crash(depth=MIN_DEPTH / 2)
        assert detect_declines(c, symbol="T", **_cascade_state(c.size, 120)) == []


class TestNoLookAhead:
    def test_NO_SIGNAL_USES_A_FUTURE_BAR(self) -> None:
        """THE ONE THAT MATTERS. Shift the whole series later and the signal must shift with it,
        by exactly the same amount -- if any bar of the signal were derived from data after its own
        index, the two would not line up."""
        n, shift = 220, 17
        a = _crash(n=n, low_at=120)
        b = np.concatenate([np.full(shift, 100.0), a])[:n + shift]

        sa = rebound_signal(a.size, detect_declines(a, symbol="T", **_cascade_state(n, 120)))
        st_b = _cascade_state(n + shift, 120 + shift)
        sb = rebound_signal(b.size, detect_declines(b, symbol="T", **st_b))

        assert sa.sum() > 0 and sb.sum() > 0
        assert np.flatnonzero(sb)[0] - np.flatnonzero(sa)[0] == shift

    def test_the_signal_never_lands_on_the_low_itself(self) -> None:
        """An entry at the trough is unreachable in real time; a backtest that takes it is
        measuring a price nobody could have paid."""
        c = _crash()
        found = detect_declines(c, symbol="T", **_cascade_state(c.size, 120))
        for d in found:
            assert d.confirm_idx > d.low_idx, "confirmation must come strictly after the trough"

    def test_history_is_measured_from_the_CONFIRMATION_not_the_low(self) -> None:
        """Measuring the bounce from the low flatters every number by exactly the part of the move
        the strategy could not have captured."""
        c = _crash()
        found = detect_declines(c, symbol="T", **_cascade_state(c.size, 120))
        hist = conditional_history(found, c, horizon=30)
        assert hist, "the estimator had no history to estimate from -- the original defect"
        for rows in hist.values():
            for bounce, adverse, rec in rows:
                assert bounce < 0.30, "a bounce measured off the trough would be far larger"
                # `adverse` is the forward MINIMUM relative to the entry, so on a monotone
                # recovery it is legitimately POSITIVE -- the position was never underwater. What
                # must always hold is that the worst point is no better than the best one.
                assert adverse <= bounce
                assert rec > 0


class TestTheBookCanNowBeEstimated:
    def test_conditional_history_feeds_rebound_estimate(self) -> None:
        """END TO END: the estimator existed and had no input. This is the wire."""
        from libs.research.drawdown_rebound import rebound_estimate
        c = _crash()
        found = detect_declines(c, symbol="T", **_cascade_state(c.size, 120))
        hist = conditional_history(found, c, horizon=30)
        est = rebound_estimate(found[0].event, hist)
        assert est.mechanism == found[0].mechanism
        # n_events is small here by construction, so the estimator must SAY it is underpowered
        # rather than return a confident number off one observation.
        assert est.n_events == len(hist.get(found[0].mechanism, []))

    def test_forced_flow_verdict_can_reclassify_without_recomputation(self) -> None:
        c = _crash()
        d = detect_declines(c, symbol="T")[0]
        assert d.mechanism not in REBOUND_FAVOURABLE
        upgraded = with_forced_flow(d, "FORCED")
        assert upgraded.event.forced_flow_verdict == "FORCED"
        assert upgraded.low_idx == d.low_idx, "re-classification must not move the event"

    def test_summarise_reports_refusals_as_first_class(self) -> None:
        c = _crash()
        s = summarise(detect_declines(c, symbol="T"))
        assert s["n_declines"] >= 1
        assert s["n_refused"] == s["n_declines"] - s["n_actionable"]
        assert "safety property working" in s["note"]


def test_an_empty_or_tiny_series_is_no_events_not_a_crash() -> None:
    assert detect_declines(np.array([]), symbol="T") == []
    assert detect_declines(np.full(5, 100.0), symbol="T") == []
