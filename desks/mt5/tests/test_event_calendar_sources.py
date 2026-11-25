"""event_reaction reads every committed calendar, and a stale store is NAMED.

MEASURED on 013f0b3f76: `ff_calendar_vintage/` held 199 events spanning 2026-08-23..09-12. The
writer (seed_miners.mine_ff_calendar_vintage) is wired on two clocks, but the store a tree holds
ends where the shipping branch (intel-ship/send, tip 2026-11-03) last landed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research import fire_inputs, orthogonal_sweep as osw  # noqa: E402
from side_channels import seed_miners as sm  # noqa: E402


def _desk(tmp_path: Path, monkeypatch) -> Path:
    desk = tmp_path / "desks" / "mt5"
    (desk / "data" / "calendars").mkdir(parents=True)
    (desk / "data" / "observables").mkdir(parents=True)
    (desk / "data" / "intelligence" / "ff_calendar_vintage").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(osw, "BASE", desk)
    osw._event_index.cache_clear()
    return desk


def test_fomc_boc_and_fed_calendars_are_read_in_utc(tmp_path, monkeypatch) -> None:
    desk = _desk(tmp_path, monkeypatch)
    (tmp_path / "data" / "event_calendar.json").write_text(json.dumps(
        {"events": [{"utc": "2026-01-28T19:00:00Z", "name": "FOMC decision"}]}))
    (desk / "data" / "calendars" / "boc_policy_rate.json").write_text(json.dumps(
        {"tz": "America/Toronto", "dates": {"2026-01-28": "09:45", "2026-07-15": "09:45"}}))
    (desk / "data" / "observables" / "fomc_calendar.json").write_text(json.dumps({"raw": [
        {"type": "FOMC", "title": "FOMC Minutes", "time": "2:00 p.m.", "month": "2026-12",
         "days": "30"},
        {"type": "Speeches", "title": "x", "time": "8:30 a.m.", "month": "2026-09", "days": "3"},
        {"type": "FOMC", "title": "no clock", "time": "", "month": "2026-09", "days": "3"},
        {"type": "Testimony", "title": "range", "time": "10:00 a.m.", "month": "2026-07",
         "days": "14-15"},
        {}]}))
    idx = osw._event_index()
    got = {str(t) for t in idx}
    assert "2026-01-28 19:00:00+00:00" in got            # FOMC statement, as stamped
    assert "2026-01-28 14:45:00+00:00" in got            # BoC 09:45 EST = 14:45Z
    assert "2026-07-15 13:45:00+00:00" in got            # BoC 09:45 EDT = 13:45Z
    assert "2026-12-30 19:00:00+00:00" in got            # Fed minutes 2pm EST
    assert len(idx) == 5                                  # speech, no-clock, range, {} skipped


def test_instants_shared_with_the_vintage_store_are_not_counted_twice(tmp_path,
                                                                      monkeypatch) -> None:
    desk = _desk(tmp_path, monkeypatch)
    (desk / "data" / "intelligence" / "ff_calendar_vintage" / "discoveries_20260901_0000.json"
     ).write_text(json.dumps([{"event_date": "2026-01-28T14:00:00-05:00"}]))
    (tmp_path / "data" / "event_calendar.json").write_text(json.dumps(
        {"events": [{"utc": "2026-01-28T19:00:00Z"}]}))
    assert len(osw._event_index()) == 1


def test_stale_store_is_named_and_extra_calendars_counted(tmp_path, monkeypatch) -> None:
    desk = _desk(tmp_path, monkeypatch)
    v = desk / "data" / "intelligence" / "ff_calendar_vintage"
    (v / "discoveries_20260101_0000.json").write_text(json.dumps(
        [{"event_date": "2026-01-02T08:30:00-05:00"}]))
    st = osw.calendar_status()
    assert st["reason"] == "stale_calendar" and st["vintage_newest_file"] == "2026-01-01"
    assert st["vintage_age_days"] > osw.CALENDAR_STALE_DAYS and st["events_total"] == 1
    assert set(st["extra_calendars"]) == {"fomc_decisions", "boc_policy_rate", "fed_calendar"}
    today = pd.Timestamp.now(tz="UTC").strftime("%Y%m%d")
    (v / f"discoveries_{today}_0000.json").write_text(json.dumps([{"event_date": "2026-01-03"}]))
    osw._event_index.cache_clear()
    assert osw.calendar_status()["reason"] == "ok"


def test_no_calendar_at_all_is_named(tmp_path, monkeypatch) -> None:
    _desk(tmp_path, monkeypatch)
    assert osw.calendar_status()["reason"] == "no_calendar"
    assert fire_inputs.probe("EURUSD", "event_reaction")["status"] == "UNMEASURED"


def test_the_miner_captures_next_week_and_survives_its_failure(monkeypatch) -> None:
    ev = [{"country": "USD", "title": "CPI", "date": "2026-11-12T08:30:00-05:00",
           "impact": "High", "forecast": "0.3%", "previous": "0.2%"}]
    calls = []

    def ok(url, as_json=False, timeout=20):
        calls.append(url)
        return ev
    monkeypatch.setattr(sm, "fetch", ok)
    rows = sm.mine_ff_calendar_vintage()
    assert [r["feed"] for r in rows] == ["thisweek", "nextweek"] and len(calls) == 2
    assert rows[0]["kind"] == "calendar_vintage" and rows[0]["event_date"] == ev[0]["date"]

    def next_fails(url, as_json=False, timeout=20):
        if "nextweek" in url:
            raise OSError("429")
        return ev
    monkeypatch.setattr(sm, "fetch", next_fails)
    assert [r["feed"] for r in sm.mine_ff_calendar_vintage()] == ["thisweek"]

    def this_fails(url, as_json=False, timeout=20):
        raise OSError("down")
    monkeypatch.setattr(sm, "fetch", this_fails)
    try:
        sm.mine_ff_calendar_vintage()
    except OSError:
        pass
    else:
        raise AssertionError("a primary-feed failure must still raise (fetch_error row)")
