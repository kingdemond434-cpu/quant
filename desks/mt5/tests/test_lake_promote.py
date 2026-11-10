"""lake_promote: the point-in-time share is measured on what the producer wrote, and only on that.

THE DEFECT THESE PIN (N12). The organ offered silver the bronze wrapper without opening the
payload, so no row could resolve an event time and `silver_share` read 0.0 on every pass -- the
binding term of the scorecard's `pit_compliance_pct`. The first test fails on that code.

THE OTHER HALF. Opening the payload must not turn a catalogue's "Yesterday" into a point in time,
nor the desk's own arrival stamp into the producer's event. Those rows stay refused, by name.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lake_promote as lp  # noqa: E402
from libs.data.lake import to_bronze  # noqa: E402

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def _corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict]) -> None:
    seat = tmp_path / "intelligence" / "seat"
    seat.mkdir(parents=True)
    (seat / "discoveries_1.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    monkeypatch.setattr(lp, "INTEL_ROOTS", (tmp_path / "intelligence",))


def test_a_row_carrying_its_own_event_time_reaches_silver(tmp_path, monkeypatch):
    _corpus(tmp_path, monkeypatch, [
        {"title": "a", "published_at": "2026-09-10T14:18:49Z"},
        {"title": "b", "event_date": "2026-09-01"},
        {"title": "c"},
    ])
    doc = lp.run()
    assert doc["status"] == "MEASURED"
    assert (doc["n_bronze"], doc["n_silver"], doc["n_refused"]) == (3, 2, 1)
    assert doc["silver_share"] == pytest.approx(0.6667)
    assert doc["resolved_by_key"] == {"published_at": 1, "event_date": 1}
    assert doc["normalisation"] == lp.NORMALISATION


def test_a_relative_date_is_refused_by_name_never_promoted(tmp_path, monkeypatch):
    _corpus(tmp_path, monkeypatch, [
        {"title": "ea", "date": "Yesterday"},
        {"title": "eb", "date": "1 hour ago"},
        {"title": "ec", "date": "2026-09-03"},
    ])
    doc = lp.run()
    assert doc["n_silver"] == 1
    relative = [why for why in doc["refusal_reasons"] if "`date` is relative" in why]
    assert relative and doc["refusal_reasons"][relative[0]] == 2


def test_the_desks_own_arrival_stamp_is_not_an_event_time(tmp_path, monkeypatch):
    _corpus(tmp_path, monkeypatch, [
        {"title": "x", "retrieved_at": "2026-09-10T14:18:49Z", "first_seen_at": "2026-09-10",
         "observed_at": "2026-09-10T00:00:00Z", "found_at": "2026-09-10T00:00:00Z"},
    ])
    doc = lp.run()
    assert (doc["n_silver"], doc["silver_share"]) == (0, 0.0)
    assert any("no resolvable event_time" in why for why in doc["refusal_reasons"])


def test_producer_aliases_are_counted_apart_from_the_canonical_keys(tmp_path, monkeypatch):
    _corpus(tmp_path, monkeypatch, [
        {"title": "video", "published": "2026-08-28T12:12:52Z"},
        {"title": "post", "created": "2026-08-28T13:53:34Z"},
        {"title": "paper", "published_at": "2026-08-01T00:00:00Z"},
        {"title": "bare"},
    ])
    doc = lp.run()
    assert doc["silver_share"] == 0.75
    assert doc["silver_share_canonical_keys"] == 0.25
    assert doc["resolved_by_key"] == {"published": 1, "created": 1, "published_at": 1}
    assert set(doc["event_keys"]["producer_aliases"]) == {"published", "created"}


def test_an_event_time_in_the_future_stamps_nothing():
    late = (NOW + timedelta(days=3)).isoformat()
    assert lp.absolute_instant(late, NOW) is None
    assert lp.absolute_instant((NOW + timedelta(hours=2)).isoformat(), NOW) is not None
    with pytest.raises(lp.UnresolvableEventTime):
        lp.normalise_arrived(to_bronze({"title": "t", "published_at": late}, "seat", now=NOW),
                             now=NOW)


@pytest.mark.parametrize("value", ["Yesterday", "1 hour ago", "Sep 3", "", "   ", None, 20260903,
                                   "2026-13-40", "03/09/2026"])
def test_only_an_absolute_iso_instant_is_an_event_time(value):
    assert lp.absolute_instant(value, NOW) is None


def test_a_bare_date_is_its_first_instant_utc_and_a_naive_stamp_is_utc():
    assert lp.absolute_instant("2026-09-03", NOW) == "2026-09-03T00:00:00+00:00"
    assert lp.absolute_instant("2026-09-03T10:00:00", NOW) == "2026-09-03T10:00:00+00:00"
    assert lp.absolute_instant("2026-09-03T10:00:00+02:00", NOW) == "2026-09-03T08:00:00+00:00"


def test_a_later_key_answers_when_an_earlier_one_is_relative():
    row = to_bronze({"date": "Yesterday", "published_at": "2026-09-10T14:18:49Z"}, "seat", now=NOW)
    out = lp.normalise_arrived(row, now=NOW)
    assert (out["event_time"], out["event_time_key"]) == ("2026-09-10T14:18:49+00:00",
                                                          "published_at")


def test_the_arrival_time_is_never_the_event_time(tmp_path, monkeypatch):
    """The stamp the wrapper carries (ingested now) cannot leak into `event_time`."""
    row = to_bronze({"title": "nothing dated"}, "seat", now=NOW)
    out = lp.normalise_arrived(row, now=NOW)
    assert "event_time" not in out and out["fields"] == {"title": "nothing dated"}


def test_an_empty_corpus_is_unmeasured_not_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "INTEL_ROOTS", (tmp_path / "absent",))
    doc = lp.run()
    assert doc["status"] == "UNMEASURED" and "silver_share" not in doc
