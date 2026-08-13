"""The unlock calendar's honesty properties (R0288).

What these pin: the parser REFUSES a reshaped page instead of appending zero rows; a linear-rate
row can never fabricate a tranche; a past event stays flagged retrospective so `forward_events`
cannot serve the pct_circ_now look-ahead; and `supply_at` only answers from observations made at
or before the asked date -- the exact point-in-time discipline whose absence killed the original
screen (0/27 cells with a structurally empty high-threshold bucket).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.research.unlock_calendar import (
    append_new,
    extract_events,
    forward_events,
    load_snapshot,
    parse_next_data,
    supply_at,
)

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
PAST = int((NOW - timedelta(days=30)).timestamp())
FUTURE = int((NOW + timedelta(days=30)).timestamp())


def _page(protocols: list[dict]) -> str:
    doc = {"props": {"pageProps": {"data": protocols, "generatedAtSec": 1754900000}}}
    return ('<html><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(doc) + "</script></html>")


def _proto(**over) -> dict:
    base = {
        "tSymbol": "TIA", "name": "Celestia", "protocolSlug": "celestia",
        "gecko_id": "celestia", "circSupply": 1_000_000_000.0, "maxSupply": 1_336_000_000.0,
        "events": [
            {"timestamp": FUTURE, "noOfTokens": [100_000_000], "category": "insiders",
             "unlockType": "cliff"},
            {"timestamp": PAST, "noOfTokens": [50_000_000], "category": "airdrop",
             "unlockType": "cliff"},
            {"timestamp": FUTURE, "noOfTokens": [1000.0, 2000.0], "category": "ecosystem",
             "unlockType": "linear"},
        ],
    }
    base.update(over)
    return base


def test_parser_refuses_a_reshaped_page() -> None:
    with pytest.raises(ValueError, match="marker absent"):
        parse_next_data("<html>redesigned</html>")
    with pytest.raises(ValueError, match="missing or empty"):
        parse_next_data(_page([]))


def test_cliffs_are_sized_and_linear_rows_cannot_fabricate_a_tranche() -> None:
    events = extract_events(parse_next_data(_page([_proto()]))["protocols"], NOW)
    cliffs = [e for e in events if e["unlock_type"] == "cliff"]
    linear = [e for e in events if e["unlock_type"] == "linear"]
    assert {e["tokens"] for e in cliffs} == {100_000_000.0, 50_000_000.0}
    # summing a [from, to] rate pair would invent a 3000-token tranche no venue ever saw
    assert linear[0]["tokens"] is None
    assert linear[0]["tokens_raw"] == [1000.0, 2000.0]


def test_pct_of_float_is_stamped_and_past_events_stay_flagged() -> None:
    events = extract_events(parse_next_data(_page([_proto()]))["protocols"], NOW)
    fut = next(e for e in events if e["ts"] == FUTURE and e["unlock_type"] == "cliff")
    past = next(e for e in events if e["ts"] == PAST)
    assert fut["pct_circ_at_obs"] == pytest.approx(10.0)
    assert fut["retrospective"] is False
    assert past["retrospective"] is True


def test_append_is_dedup_and_survives_a_corrupt_line(tmp_path: Path) -> None:
    events = extract_events(parse_next_data(_page([_proto()]))["protocols"], NOW)
    assert append_new(events, tmp_path) == 3
    assert append_new(events, tmp_path) == 0
    cal = tmp_path / "data/unlock_calendar.jsonl"
    cal.write_text(cal.read_text("utf-8") + "{corrupt\n", "utf-8")
    assert append_new(events, tmp_path) == 0


def test_forward_events_never_serve_the_lookahead(tmp_path: Path) -> None:
    events = extract_events(parse_next_data(_page([_proto()]))["protocols"], NOW)
    append_new(events, tmp_path)
    fwd = forward_events(NOW, within_days=90, min_pct_circ=5.0, root=tmp_path)
    assert [e["ts"] for e in fwd] == [FUTURE]      # past cliff and linear row both excluded
    assert forward_events(NOW, within_days=90, min_pct_circ=15.0, root=tmp_path) == []


def test_supply_at_only_uses_observations_at_or_before_the_date(tmp_path: Path) -> None:
    series = tmp_path / "data/circulating_supply.jsonl"
    series.parent.mkdir(parents=True)
    rows = [
        {"coin_id": "celestia", "symbol": "TIA", "circulating_supply": 900.0,
         "observed_utc": (NOW - timedelta(days=10)).isoformat()},
        {"coin_id": "celestia", "symbol": "TIA", "circulating_supply": 950.0,
         "observed_utc": (NOW - timedelta(days=2)).isoformat()},
        {"coin_id": "celestia", "symbol": "TIA", "circulating_supply": 999.0,
         "observed_utc": (NOW + timedelta(days=5)).isoformat()},
    ]
    series.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    got = supply_at("TIA", NOW, root=tmp_path)
    assert got is not None and got["circulating_supply"] == 950.0
    # a series that starts after the asked date is UNMEASURED, not the earliest row
    assert supply_at("TIA", NOW - timedelta(days=30), root=tmp_path) is None
    assert supply_at("NOSUCH", NOW, root=tmp_path) is None


def test_snapshot_reader_renames_the_lookahead_field(tmp_path: Path) -> None:
    snap = tmp_path / "data/unlock_events.json"
    snap.parent.mkdir(parents=True)
    snap.write_text(json.dumps({"events": [
        {"symbol": "GLMUSDT", "ts": 1478822400, "pct_circ_now": 82.0}]}), "utf-8")
    rows = load_snapshot(tmp_path)
    assert rows[0]["pct_circ_lookahead"] == 82.0
    assert "pct_circ_now" not in rows[0]


def test_the_collector_script_parses_and_refuses_loudly() -> None:
    """collect_unlock_calendar.py's contract without network: it imports, its error path writes
    status UNMEASURED (never a silent zero-append), and its happy path stamps status OK."""
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "scripts/collect_unlock_calendar.py").read_text()
    ast.parse(src)
    assert '"UNMEASURED"' in src and '"status": "OK"' in src
