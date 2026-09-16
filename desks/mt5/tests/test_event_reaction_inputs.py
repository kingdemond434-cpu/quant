"""The event_reaction family is handed event MAPPINGS, never a bare index (2026-09-16: every
live event_reaction cell produced zero signals because the sweep's DatetimeIndex was skipped)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import family_event_reaction as fer  # noqa: E402
from mt5desk import family_inputs as fi  # noqa: E402


def test_a_datetime_index_becomes_mappings_the_family_reads():
    idx = pd.DatetimeIndex(["2026-09-10 12:30", "2026-09-11 14:00"], tz="UTC")
    rows = fi.events_for_symbol(idx, "XAUUSD")
    assert rows == [{"symbol": "XAUUSD", "at": "2026-09-10T12:30:00+00:00"},
                    {"symbol": "XAUUSD", "at": "2026-09-11T14:00:00+00:00"}]
    times = fer._event_times(rows, "XAUUSD", clock="bars")
    assert [t.isoformat() for t in times] == ["2026-09-10T12:30:00+00:00",
                                              "2026-09-11T14:00:00+00:00"]
    # the bare index yields nothing -- the defect this fix removes
    assert fer._event_times(idx, "XAUUSD", clock="bars") == []


def test_mappings_pass_through_and_odd_shapes_never_raise():
    rows = [{"symbol": "EURUSD", "at": "2026-09-10T12:30:00+00:00"}]
    assert fi.events_for_symbol(rows, "EURUSD") == rows
    assert fi.events_for_symbol(None, "EURUSD") == []
    assert fi.events_for_symbol(42, "EURUSD") == []
    assert fi.events_for_symbol(["not a date", "2026-09-10"], "EURUSD") == [
        {"symbol": "EURUSD", "at": "2026-09-10T00:00:00+00:00"}]
