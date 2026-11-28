"""The family lane refuses a STALLED feed and nothing else (ported from #111; #926 audit MF).

A frame is current while its FORMING row is the bar in progress on the venue's broker wall clock.
After a weekend or a daily session break the venue prints a new forming bar at the open, so the
first decision after the gap is taken exactly as the certified replay takes it; only a feed that
stopped printing leaves the forming row behind the clock. A refusal leaves its reason and a
count in the pass state.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402


def _frame(*stamps: str) -> pd.DataFrame:
    return pd.DataFrame({"close": [1.0] * len(stamps)}, index=pd.DatetimeIndex(stamps))


def test_the_first_decision_after_a_weekend_is_admitted() -> None:
    f = _frame("2026-11-06T22:00", "2026-11-06T23:00", "2026-11-09T00:00")   # Fri .. Mon open
    now = pd.Timestamp("2026-11-09T00:05")
    assert dc.frame_is_current(f.index[-1], now=now, bar_minutes=60)
    assert dc.family_bar_due(f.iloc[:-1], 23) == pd.Timestamp("2026-11-06T23:00")


def test_the_first_decision_after_a_session_break_is_admitted() -> None:
    f = _frame("2026-11-10T22:00", "2026-11-11T01:00")                       # break 23:00-01:00
    assert dc.frame_is_current(f.index[-1], now=pd.Timestamp("2026-11-11T01:05"), bar_minutes=60)


def test_a_stalled_feed_is_refused() -> None:
    f = _frame("2026-11-11T09:00", "2026-11-11T10:00")                       # last print 10:00
    assert not dc.frame_is_current(f.index[-1], now=pd.Timestamp("2026-11-11T13:20"),
                                   bar_minutes=60)
    m5 = _frame("2026-11-11T10:00", "2026-11-11T10:05")
    assert dc.frame_is_current(m5.index[-1], now=pd.Timestamp("2026-11-11T10:09"), bar_minutes=5)
    assert not dc.frame_is_current(m5.index[-1], now=pd.Timestamp("2026-11-11T10:10"),
                                   bar_minutes=5)
    # an aware clock against naive bars compares on one clock; skew before the open is current
    assert dc.frame_is_current(f.index[-1], now=pd.Timestamp("2026-11-11T10:30", tz="UTC"))
    assert dc.frame_is_current(f.index[-1], now=pd.Timestamp("2026-11-11T09:58"))


def test_the_gateway_judges_the_forming_row_and_records_the_refusal() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    body = src[src.index("def resolve_family_order("):]
    body = body[:body.index("\ndef ")]
    assert "_venue_now = _venue_clock(st)" in body
    assert "frame.index[-1], now=_venue_now, bar_minutes=_tf_min)" in body
    assert '_stale["count"] = int(_stale.get("count") or 0) + 1' in body
    assert '"stage": "stale_frame"' in body
    assert body.index("frame_is_current(") < body.index("family_bar_due(closed")
    clock = src[src.index("def _venue_clock("):]
    assert 'st.get("placement_tick_broker")' in clock[:clock.index("\ndef ")]
    assert 'st["placement_tick_broker"] = tnow.tz_localize(None).isoformat()' in src


def test_the_venue_clock_reader_never_raises() -> None:
    pytest.importorskip("MetaTrader5")
    from mt5desk import gateway as gw
    assert gw._venue_clock({}) is None
    assert gw._venue_clock({"placement_tick_broker": "not a time"}) is None
    assert gw._venue_clock({"placement_tick_broker": "2026-11-11T03:00:00"}) == \
        pd.Timestamp("2026-11-11T03:00:00")
