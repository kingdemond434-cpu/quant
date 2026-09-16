"""The gold windows on the prop account (2026-09-16): the pure decisions, without a venue."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk.decision_core import BRACKET_TTL_HOURS, CANCEL_HOUR, CLOSE_HOUR  # noqa: E402
from prop import e8_gold as g  # noqa: E402


def _bars(hours: int = 120) -> pd.DataFrame:
    """Hourly bars ending at 12:00 server on the last day, a 4300-4340 range that morning."""
    end = pd.Timestamp("2026-09-16 12:00", tz="UTC")
    idx = pd.date_range(end=end, periods=hours, freq="h")
    rng = np.random.default_rng(1)
    close = 4320.0 + np.cumsum(rng.normal(0, 3.0, hours))
    df = pd.DataFrame({"open": close, "high": close + 6.0, "low": close - 6.0, "close": close},
                      index=idx)
    day = df.index.date == end.date()
    df.loc[day, "high"] = np.minimum(df.loc[day, "high"], 4340.0)
    df.loc[day, "low"] = np.maximum(df.loc[day, "low"], 4300.0)
    return df


def test_a_window_is_planned_once_at_or_after_its_signal_hour_before_the_cancel_hour() -> None:
    df = _bars()
    # 07:30 server: the Asia window (signal hour 7, range 00-07) is due; london_am (13) is not.
    due = g.plan(df, 7.5, {"windows": {}})
    assert [d["window"] for d in due] == ["asia"]
    spec = due[0]["spec"]
    assert spec["buy_stop"]["price"] == due[0]["hi"] and spec["sell_stop"]["price"] == due[0]["lo"]
    assert spec["buy_stop"]["sl"] < spec["buy_stop"]["price"] < spec["buy_stop"]["tp"]
    assert spec["sell_stop"]["tp"] < spec["sell_stop"]["price"] < spec["sell_stop"]["sl"]
    # Already placed today: not again.
    assert g.plan(df, 7.5, {"windows": {"asia": {}}}) == []
    # Past the cancel hour: nothing is placed.
    assert g.plan(df, CANCEL_HOUR + 0.1, {"windows": {}}) == []
    # Before the signal hour: nothing.
    assert g.plan(df, 6.9, {"windows": {}}) == []


def test_a_resting_leg_must_sit_on_the_right_side_of_the_quote() -> None:
    assert g.leg_is_legal("buy_stop", 4341.0, 4338.0, 4338.5)[0]
    assert not g.leg_is_legal("buy_stop", 4338.5, 4338.0, 4338.5)[0]
    assert g.leg_is_legal("sell_stop", 4300.0, 4338.0, 4338.5)[0]
    assert not g.leg_is_legal("sell_stop", 4338.0, 4338.0, 4338.5)[0]


def _state(placed_hour: float = 7.1, position_id: int | None = None) -> dict:
    return {"date": "2026-09-16", "windows": {"asia": {
        "placed_hour": placed_hour, "position_id": position_id,
        "orders": {"buy_stop": {"id": 11, "price": 4340.0},
                   "sell_stop": {"id": 12, "price": 4300.0}}}}}


def test_one_fill_cancels_the_other_leg_and_the_position_is_recorded() -> None:
    acts = g.manage_actions(_state(), 8.0, open_ids={12}, filled={11: 900}, position_ids={900})
    assert [a["act"] for a in acts] == ["record_position", "oco_cancel"]
    assert acts[0]["position_id"] == 900 and acts[1]["order_id"] == 12


def test_an_unfilled_pair_is_cancelled_after_the_ttl_and_at_the_end_of_day() -> None:
    both = {11, 12}
    assert g.manage_actions(_state(7.1), 7.1 + BRACKET_TTL_HOURS - 0.1, both, {}, set()) == []
    acts = g.manage_actions(_state(7.1), 7.1 + BRACKET_TTL_HOURS, both, {}, set())
    assert sorted(a["order_id"] for a in acts) == [11, 12]
    assert {a["act"] for a in acts} == {"ttl_cancel"}
    acts = g.manage_actions(_state(CANCEL_HOUR - 1.0), CANCEL_HOUR, both, {}, set())
    assert {a["act"] for a in acts} == {"eod_cancel"}


def test_the_position_is_closed_at_the_close_hour_and_only_while_it_exists() -> None:
    acts = g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR, set(), {}, {900})
    assert [a["act"] for a in acts] == ["close"] and acts[0]["position_id"] == 900
    # Already gone at the venue (stop or target hit): nothing to close.
    assert g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR, set(), {}, set()) == []
    # Before the close hour a live position is left to its stop and target.
    assert g.manage_actions(_state(7.1, position_id=900), CLOSE_HOUR - 0.5, set(), {}, {900}) == []
