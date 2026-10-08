"""E8 evaluates the certified broker day, retaining the physical bar prices and ordering."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))

from mt5desk.families_orthogonal import family_overnight_gap_decay  # noqa: E402
from mt5desk.family_call import certified_session_filter  # noqa: E402
from prop.e8_executor import _frame, _last_closed  # noqa: E402


class History:
    def __init__(self, index: pd.DatetimeIndex, prices: list[float]):
        self.data = pd.DataFrame({
            "t": index.as_unit("ms").asi8, "o": prices, "c": prices,
            "h": [p + 0.01 for p in prices], "l": [p - 0.01 for p in prices],
            "v": [100] * len(prices),
        })

    def get_price_history(self, *args, **kwargs):
        return self.data.copy()


@pytest.mark.parametrize(("physical", "broker"), [
    ("2026-02-02T22:00Z", "2026-02-03T00:00Z"),
    ("2026-07-06T21:00Z", "2026-07-07T00:00Z"),
])
def test_history_uses_each_bars_server_offset(physical, broker):
    # One fetch can contain summer and winter; applying today's offset to both is incorrect.
    idx = pd.DatetimeIndex(["2026-02-02T22:00Z", "2026-07-06T21:00Z"])
    frame = _frame(History(idx, [1.0, 1.1]), 1)
    assert pd.Timestamp(broker) in frame.index
    assert frame.loc[pd.Timestamp(broker), "open"] == (1.0 if "02-" in physical else 1.1)
    assert frame.attrs["strategy_clock"] == "broker_wall_time/E8_server_day"
    assert len(_last_closed(frame)) == 1


def test_rollover_gap_reaches_the_certified_asia_session():
    idx = pd.date_range("2026-10-06T00:00Z", periods=51, freq="h")
    boundary = pd.Timestamp("2026-10-07T21:00Z")
    prices = [1.0 if t < boundary else 1.08 for t in idx]
    history = History(idx, prices)
    raw = history.data.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})
    raw.index = idx
    assert family_overnight_gap_decay(raw) == []
    frame = _frame(history, 1)
    sigs = certified_session_filter(family_overnight_gap_decay(frame),
                                    {"params": {"params": {"session": "asia"}}})
    assert len(sigs) == 1
    assert sigs[0].time == pd.Timestamp("2026-10-08T00:00Z")
    assert sigs[0].side == -1
    assert frame["open"].tolist() == prices
