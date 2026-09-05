"""The coverage matrix: what the desk cannot fund, and why that is a search and not a shrug.

The load-bearing property is that NOTHING VANISHES. Every certificate either lands in a cell or
is counted as unplaceable; every unfilled point of heat becomes a request. A coverage report that
quietly drops what it cannot parse describes a smaller library than the one that exists, and
reads exactly like a desk that has certified nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.portfolio_gap import (  # noqa: E402
    band_of,
    build,
    parse_cell,
    sleeve_axes,
)


def test_hunt_cell_shape_parses() -> None:
    a = parse_cell("AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY")
    assert a == {"symbol": "AUDNZD", "side": "SHORT", "window": "afternoon",
                 "state": "NORMAL_DAY", "family": "dav_range_filter_adx"}


def test_external_dotted_shape_parses() -> None:
    """MEASURED: 62 of 63 certificates use this shape, and the token parser turned every one of
    them into an unspecified family with no window -- a matrix showing ONE certificate."""
    a = parse_cell("XAUUSD.session_range_breakout")
    assert a["symbol"] == "XAUUSD"
    assert a["family"] == "session_range_breakout"


def test_tokens_are_classified_not_positioned() -> None:
    """A hunt inventing a new token order must be parsed, not dropped."""
    a = parse_cell("EURJPY asia LONG mean_revert TREND_DAY")
    assert a["symbol"] == "EURJPY"
    assert a["window"] == "asia"
    assert a["side"] == "LONG"
    assert a["state"] == "TREND_DAY"
    assert a["family"] == "mean_revert"


def test_an_empty_cell_is_empty_not_a_fabricated_row() -> None:
    assert parse_cell("") == {}
    assert parse_cell("   ") == {}


def test_sleeve_axes_reads_the_allocator_naming() -> None:
    assert sleeve_axes("gold_asia")["window"] == "asia"
    a = sleeve_axes("USDJPY_london_am_TREND_DAY")
    assert a["symbol"] == "USDJPY" and a["window"] == "london_am"
    b = sleeve_axes("EURNOK_overnight_gap_decay_asia")
    assert b["symbol"] == "EURNOK" and b["family"] == "overnight_gap_decay"
    assert b["window"] == "asia"


def test_bands_cover_the_clock_and_nothing_falls_between_them() -> None:
    assert {band_of(h) for h in range(24)} == {"00-04", "04-08", "08-12",
                                              "12-16", "16-20", "20-24"}
    assert band_of(-1) == "??"


def _alloc(book: dict[str, float], target: float = 0.20, total: float | None = None) -> dict:
    return {"book": book, "marginal_delta_elog": {},
            "heat": {"target": target, "total": target if total is None else total}}


def test_an_unplaceable_certificate_is_counted_not_dropped() -> None:
    """A window the desk cannot put on a clock is unschedulable evidence, and it must show."""
    sv = [{"symbol": "EURUSD", "family": "mystery", "window": "some_future_session",
           "state": "", "side": ""}]
    doc = build(_alloc({"gold_asia": 0.2}), sv)
    assert doc["n_certificates"] == 1
    assert doc["certificates_unplaced_on_a_clock"] == 1
    assert any(r["kind"] == "unplaced_certificates" for r in doc["research_requests"])


def test_unplaceable_rows_do_not_pollute_the_dark_band_finding() -> None:
    sv = [{"symbol": "E", "family": "m", "window": "nope", "state": "", "side": ""}]
    doc = build(_alloc({"gold_asia": 0.2}), sv)
    assert "??" not in doc["dark_bands"]
    assert all(c["band"] != "??" for c in doc["empty_cells"])


def test_a_band_with_no_funded_sleeve_is_dark_even_when_certificates_exist() -> None:
    """Certified but unfunded is the finding. A cell full of certificates the book does not hold
    is not coverage -- it is a queue."""
    sv = [{"symbol": "AUDNZD", "family": "carry", "window": "asia", "state": "", "side": ""}]
    doc = build(_alloc({"gold_afternoon": 0.2}), sv)
    assert "04-08" in doc["dark_bands"], "the Asia band holds a certificate and no capital"


def test_the_heat_gap_becomes_a_request() -> None:
    doc = build(_alloc({"gold_asia": 0.11}, target=0.20, total=0.11), [])
    assert doc["heat_gap"] > 0.08
    assert doc["research_requests"][0]["kind"] == "heat_gap"


def test_a_fully_funded_book_asks_for_nothing_on_heat() -> None:
    doc = build(_alloc({"gold_asia": 0.20}, target=0.20, total=0.20), [])
    assert doc["heat_gap"] == 0.0
    assert all(r["kind"] != "heat_gap" for r in doc["research_requests"])


def test_the_mechanism_axis_is_discovered_never_enumerated() -> None:
    """A family that clears the gates tomorrow must appear tomorrow, with no edit to any file."""
    sv = [{"symbol": "X", "family": "a_family_invented_today", "window": "asia",
           "state": "", "side": ""}]
    doc = build(_alloc({"gold_asia": 0.2}), sv)
    assert "a_family_invented_today" in doc["families"]
