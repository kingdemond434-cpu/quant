"""The family lane acts only on a CURRENT closed bar, on the venue's own clock (ported from #111).

A frame whose "forming" row had already closed -- a stalled feed, or a quiet symbol whose venue
printed no bar -- would otherwise be read as the bar just finished and entered hours late.
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


def test_the_gateway_passes_the_broker_wall_clock_to_both_branches() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    body = src[src.index("def resolve_family_order("):]
    body = body[:body.index("\ndef ")]
    assert "_venue_now = _venue_clock(st)" in body
    assert "now=_venue_now, bar_minutes=_tf_min)" in body
    assert "not closed_bar_is_current(last_bar, now=_venue_now," in body
    clock = src[src.index("def _venue_clock("):]
    assert 'st.get("placement_tick_broker")' in clock[:clock.index("\ndef ")]
    # main stamps that clock naive, in the broker's wall time: the bars' own convention
    assert 'st["placement_tick_broker"] = tnow.tz_localize(None).isoformat()' in src


def test_the_venue_clock_reader_never_raises() -> None:
    pytest.importorskip("MetaTrader5")
    from mt5desk import gateway as gw
    assert gw._venue_clock({}) is None
    assert gw._venue_clock({"placement_tick_broker": "not a time"}) is None
    assert gw._venue_clock({"placement_tick_broker": "2026-11-11T03:00:00"}) ==         pd.Timestamp("2026-11-11T03:00:00")
