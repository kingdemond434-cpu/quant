"""The event ledger is the asset every learned thing in the macro layer is fitted on.

These pin the properties that make it learnable-from rather than merely large: it appends and
never rewrites, the same item twice is one row, a row from a future schema survives a round trip,
and -- the one that matters most -- a category with headlines but no MEASURED reactions has n=0
for every estimate. A ledger that counted headlines as evidence would let the desk believe it had
sample it does not have.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro.ledger import MIN_CATEGORY_N, EventLedger  # noqa: E402
from macro.schema import EventRecord, Status, content_id, now_iso, parse_ts  # noqa: E402


def _rec(eid: str, category: str = "inflation_release", *, measured: bool = False,
         total: float = 2.0) -> EventRecord:
    return EventRecord(
        event_id=eid, received_at=now_iso(), processed_at=now_iso(),
        source_id="src", title=f"title {eid}", category=category,
        priced=({"status": Status.MEASURED, "total_move_sigma": total,
                 "unpriced_fraction": 0.5} if measured
                else {"status": Status.UNMEASURED, "unpriced_fraction": None}),
        decay_half_life_s=45.0 if measured else None)


def test_the_ledger_appends_and_dedupes_by_content(tmp_path: Path) -> None:
    led = EventLedger(tmp_path / "l.jsonl")
    assert led.append(_rec("a")) is True
    assert led.append(_rec("b")) is True
    # The same id again is a re-poll of a feed, not a second event.
    assert led.append(_rec("a")) is False
    assert len(led.records()) == 2

    # Append-only: the first row's bytes are untouched by later writes.
    lines = (tmp_path / "l.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event_id"] == "a"


def test_two_sources_reporting_the_same_thing_stay_two_rows() -> None:
    """Collapsing them would destroy the evidence that a claim was independently corroborated,
    which is the only thing that makes credibility.combine's confirmation term meaningful."""
    a = content_id("REUTERS", "Refinery outage in Rotterdam", "http://x", "2026-09-05T10:00:00Z")
    b = content_id("BLOOMBERG", "Refinery outage in Rotterdam", "http://y",
                   "2026-09-05T10:00:00Z")
    assert a != b


def test_a_row_from_a_later_schema_survives_a_round_trip() -> None:
    raw = _rec("z").to_dict()
    raw["some_future_field"] = {"nested": 1}
    rec = EventRecord.from_dict(raw)
    assert rec.extra["some_future_field"] == {"nested": 1}
    assert json.loads(rec.to_json())["some_future_field"] == {"nested": 1}


def test_headlines_are_not_evidence_only_measured_reactions_are(tmp_path: Path) -> None:
    """The distinction between a big ledger and an informative one."""
    led = EventLedger(tmp_path / "l.jsonl")
    for i in range(MIN_CATEGORY_N * 3):
        led.append(_rec(f"h{i}", measured=False))
    stats = led.category_stats("inflation_release")
    assert stats.n_recorded == MIN_CATEGORY_N * 3
    assert stats.n_measured == 0
    assert stats.status == Status.UNMEASURED
    assert stats.total_move_sigma is None
    assert stats.has_sample is False


def test_the_category_floor_is_a_floor_not_a_suggestion(tmp_path: Path) -> None:
    led = EventLedger(tmp_path / "l.jsonl")
    for i in range(MIN_CATEGORY_N - 1):
        led.append(_rec(f"m{i}", measured=True))
    assert led.category_stats("inflation_release").status == Status.UNMEASURED
    led.append(_rec("m_last", measured=True))
    stats = led.category_stats("inflation_release")
    assert stats.status == Status.MEASURED
    assert stats.n_measured == MIN_CATEGORY_N
    assert stats.total_move_sigma == 2.0
    assert stats.decay_half_life_s == 45.0


def test_before_gives_the_point_in_time_view(tmp_path: Path) -> None:
    led = EventLedger(tmp_path / "l.jsonl")
    early = EventRecord(event_id="e", received_at="2026-01-01T00:00:00+00:00",
                        processed_at="2026-01-01T00:00:01+00:00", category="c")
    late = EventRecord(event_id="l", received_at="2026-06-01T00:00:00+00:00",
                       processed_at="2026-06-01T00:00:01+00:00", category="c")
    led.append(early)
    led.append(late)
    seen = led.before("2026-03-01T00:00:00+00:00")
    assert [r.event_id for r in seen] == ["e"]


def test_a_malformed_line_costs_one_row_not_the_file(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    led = EventLedger(path)
    led.append(_rec("good1"))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("{not json at all\n")
    led2 = EventLedger(path)
    led2.append(_rec("good2"))
    assert {r.event_id for r in EventLedger(path).read()} == {"good1", "good2"}


def test_rfc822_publication_clocks_are_parsed_not_dropped() -> None:
    """REGRESSION, found on live data. Every RSS feed the desk reads stamps `pubDate` in RFC-822,
    which `datetime.fromisoformat` refuses. An ISO-only parser dropped the publication clock on
    85 of 85 live rows, and without that clock `priced.estimate` cannot answer at all -- so the
    most important estimator in the package was silently disabled for every source the desk has.
    """
    got = parse_ts("Fri, 4 Sep 2026 15:00:00 GMT")
    assert got is not None and got.tzinfo is not None
    assert (got.year, got.month, got.day, got.hour) == (2026, 9, 4, 15)
    offset = parse_ts("Fri, 04 Sep 2026 11:10:00 +0200")
    assert offset is not None and offset.utcoffset() is not None
    # ISO still works, both with and without the Z spelling, and sub-second survives.
    assert parse_ts("2026-09-05T12:00:00Z") == parse_ts("2026-09-05T12:00:00+00:00")
    micro = parse_ts("2026-09-05T12:00:00.123456+00:00")
    assert micro is not None and micro.microsecond == 123456
    # And genuine rubbish still costs one clock, never the item.
    assert parse_ts("not a date") is None


def test_clocks_are_sub_second_and_timezone_aware() -> None:
    ts = parse_ts(now_iso())
    assert ts is not None and ts.tzinfo is not None
    # Microseconds present: the whole layer is a latency argument, and a second-resolution clock
    # cannot measure a source that is four hundred milliseconds ahead of another.
    assert "." in now_iso()


def test_summary_reports_what_has_authority_not_just_what_exists(tmp_path: Path) -> None:
    led = EventLedger(tmp_path / "l.jsonl")
    led.append(_rec("x", measured=True))
    s = led.summary()
    assert s["rows"] == 1
    assert s["rows_with_capital_authority"] == 0
    assert s["min_category_n"] == MIN_CATEGORY_N
    assert s["categories_with_sample"] == []
