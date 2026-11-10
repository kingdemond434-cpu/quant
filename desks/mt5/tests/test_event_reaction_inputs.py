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


def test_the_event_index_reads_the_backfilled_history_beside_the_polled_calendar(
        tmp_path, monkeypatch):
    """2026-11-10: the polled calendar is twelve weeks long, so no event_reaction spec could
    reach 60 fire days and none was ever judged. The backfill lives in a sibling directory (the
    compiler mints a cell per row under data/intelligence) and the index must read both."""
    import gzip
    import json

    for extra in (str(DESK / "research"),):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    import orthogonal_sweep as osw

    polled = tmp_path / "data" / "intelligence" / "ff_calendar_vintage"
    polled.mkdir(parents=True)
    (polled / "discoveries_1.json").write_text(json.dumps([
        {"event_date": "2026-09-04T08:30:00-04:00", "title": "Non-Farm Employment Change"}]),
        encoding="utf-8")
    back = tmp_path / "data" / "calendar_backfill"
    back.mkdir(parents=True)
    rows = [{"event_date": "2015-03-06T13:30:00+00:00", "currency": "USD", "backfill": True},
            {"event_date": "2015-04-03T12:30:00+00:00", "currency": "USD", "backfill": True},
            # the same instant the polled calendar holds: one event, not two
            {"event_date": "2026-09-04T12:30:00+00:00", "currency": "USD", "backfill": True}]
    with gzip.open(back / "backfill_fred_usrel_payems.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write("\n".join(json.dumps(r) for r in rows) + "\n")
    (back / "notes.txt").write_text("not a calendar", encoding="utf-8")
    monkeypatch.setattr(osw, "BASE", tmp_path)
    monkeypatch.setattr(osw, "EVENT_BACKFILL_DIR", back)
    osw._event_index.cache_clear()               # one reading per process, by design
    idx = osw._event_index()
    assert [t.isoformat() for t in idx] == ["2015-03-06T13:30:00+00:00",
                                            "2015-04-03T12:30:00+00:00",
                                            "2026-09-04T12:30:00+00:00"]
    # A BACKFILLED RELEASE GOES ONLY WHERE ITS CURRENCY TRADES. The two 2015 instants are known
    # only from the backfill and are USD; the 2026 one is also in the polled calendar, so it
    # keeps its historical behaviour and reaches every instrument.
    assert len(osw.EVENT_BACKFILL_CURRENCY) == 2
    assert set(osw.EVENT_BACKFILL_CURRENCY.values()) == {frozenset({"USD"})}
    monkeypatch.setattr(fi, "_SYMBOL_CURRENCY", {
        "EURUSD": frozenset({"EUR", "USD"}), "AUDNZD": frozenset({"AUD", "NZD"}),
        "GER40": frozenset({"EUR"}), "MYSTERY": frozenset()})
    assert len(fi.events_for_symbol(idx, "EURUSD")) == 3
    for sym in ("AUDNZD", "GER40"):
        assert [e["at"] for e in fi.events_for_symbol(idx, sym)] == ["2026-09-04T12:30:00+00:00"]
    assert len(fi.events_for_symbol(idx, "MYSTERY")) == 3   # unknown is not a refusal
    # A WORKER HANDED THE INDEX BUILT ELSEWHERE STILL FILTERS (audit of a93a35352f2a). The table
    # is a module global `_event_index` fills; a spawned worker inherits neither it nor the
    # cache. An empty table is never taken at its word: the index is read here and the filter
    # holds, and the counters say so by name.
    osw._event_index.cache_clear()
    osw.EVENT_BACKFILL_CURRENCY.clear()
    monkeypatch.setattr(fi, "EVENT_PLACEMENT", dict.fromkeys(fi.EVENT_PLACEMENT, 0))
    assert [e["at"] for e in fi.events_for_symbol(idx, "AUDNZD")] == ["2026-09-04T12:30:00+00:00"]
    assert fi.EVENT_PLACEMENT == {"calls": 1, "table_empty_calls": 0, "table_self_loaded": 1,
                                  "backfill_instants_seen": 2, "instants_filtered": 2}
    assert len(fi.events_for_symbol(idx, "EURUSD")) == 3
    assert fi.EVENT_PLACEMENT["table_self_loaded"] == 1 and fi.EVENT_PLACEMENT["calls"] == 2
    assert fi.EVENT_PLACEMENT["backfill_instants_seen"] == 4
    assert fi.EVENT_PLACEMENT["instants_filtered"] == 2
    # no backfill directory: the polled calendar alone, exactly as before
    monkeypatch.setattr(osw, "EVENT_BACKFILL_DIR", tmp_path / "absent")
    osw._event_index.cache_clear()
    assert [t.isoformat() for t in osw._event_index()] == ["2026-09-04T12:30:00+00:00"]
    assert osw.EVENT_BACKFILL_CURRENCY == {} and len(fi.events_for_symbol(
        pd.DatetimeIndex(["2015-03-06 13:30"], tz="UTC"), "AUDNZD")) == 1
    assert fi.EVENT_PLACEMENT["table_empty_calls"] == 1      # named, never silent
    osw._event_index.cache_clear()               # leave no temp-dir reading behind
