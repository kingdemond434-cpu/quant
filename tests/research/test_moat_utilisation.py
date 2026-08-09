"""Regression tests for the MOAT UTILISATION instrument.

WHAT THESE PIN AND WHY EACH ONE EXISTS. The module measures how much of the desk's only
un-replicable asset has ever been read, and every way it can be wrong is a way the desk has
already been wrong about something else:

  * A GAP MUST SURVIVE THE REPORT. Endpoint-only reporting is how a feed came to claim 2,356
    elapsed days while holding 38 observed ones. The tape rotates hourly, so its gaps are recorder
    deaths, and an instrument that smooths them would certify a dead recorder as a healthy one.
  * A RECORDED-BUT-NEVER-READ SYMBOL MUST BE NAMED. That is the entire economic claim of the
    module -- an asset you record and do not read is a cost centre wearing an asset's name -- and
    it is the row the ranked next-action list is built from.
  * NOT-READABLE-HERE MUST NEVER READ AS 0%. "0% utilised" is a measurement and it is damning;
    "cannot measure utilisation here" is the absence of one. Conflating them is the precise defect
    this desk keeps finding in its own instruments, so it is pinned by test rather than by
    intention -- including the third state, tape-present-but-no-consumption-record, which is also
    not a zero.
  * THE RANKED LIST MUST PICK THE LARGEST UNREAD SLICE, not the newest and not the fattest, or the
    deliverable degenerates into the newest-first scheduling `screen_moat` was written to remove.
  * THE MECHANISM CLASSES MUST COME FROM THE CENSUS. A taxonomy invented here would report
    coverage against a vocabulary no other organ shares.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from libs.research.mechanism_census import CLASS_BY_ID
from libs.research.moat_utilisation import (
    GRAIN_HOUR,
    MEASURED,
    NOT_READABLE_HERE,
    PARTIAL,
    build_report,
    consumed_depth_levels,
    continuity,
    depth_level_use,
    documented_reference,
    inventory,
    measure_hour_gaps,
    rank_next_actions,
    read_records,
    recorder_declarations,
    tape_testable_classes,
    utilisation,
)

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 5, 12, tzinfo=UTC)
VENUES = ("fut", "spot", "bybit")


# ------------------------------------------------------------------------------- fixtures ------

def _write_partitions(root: Path, venue: str, symbol: str, day: str, hours: list[int],
                      *, size: int = 100) -> None:
    d = root / "data/moat" / venue / symbol
    d.mkdir(parents=True, exist_ok=True)
    for h in hours:
        (d / f"{day}_{h:02d}.jsonl.gz").write_bytes(b"x" * size)


@pytest.fixture()
def tape(tmp_path: Path) -> Path:
    """A tape with a KNOWN shape.

    ``GAPPY``  -- 2026-08-01, hours 00-03 and 20-23. One 16-hour hole, deliberately interior so a
                  first/last reading would report a flawless 24-hour day.
    ``UNREAD`` -- 2026-08-02 and 2026-08-03, every hour, 48 partitions, touched by nothing.
    Only ``GAPPY``'s first four hours are recorded as consumed, so every other cell is unread by
    construction and the arithmetic below is checkable by hand.
    """
    _write_partitions(tmp_path, "fut", "GAPPY", "20260801", [*range(4), *range(20, 24)], size=100)
    for day in ("20260802", "20260803"):
        _write_partitions(tmp_path, "fut", "UNREAD", day, list(range(24)), size=50)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data/micro_feature_store.json").write_text(
        json.dumps({f"GAPPY/20260801_{h:02d}": {"spread_bps": 1.0} for h in range(4)}), "utf-8")
    return tmp_path


# ---------------------------------------------------------------- 1. a gap is reported ---------

def test_interior_gap_is_reported_not_smoothed(tape: Path) -> None:
    """The 16-hour hole survives as a hole, and the endpoint reading does not hide it."""
    parts = inventory(tape / "data/moat")
    rows = {c.symbol: c for c in continuity(parts, now=NOW)}
    g = rows["GAPPY"]

    # The endpoints alone would say "a full day": first 00:00, last 23:00, 24 hours elapsed.
    assert g.first_hour_utc.startswith("2026-08-01T00:00")
    assert g.last_hour_utc.startswith("2026-08-01T23:00")
    assert g.elapsed_hours == 24
    # ...and the measurement says otherwise, with the hole located rather than merely counted.
    assert g.recorded_hours == 8
    assert g.n_gaps == 1
    assert g.gap_hours == 16
    assert g.largest_gap_hours == 16
    assert g.largest_gap_from is not None and g.largest_gap_from.startswith("2026-08-01T04:00")
    assert g.largest_gap_to is not None and g.largest_gap_to.startswith("2026-08-01T19:00")
    assert g.coverage_pct is not None and g.coverage_pct < 34.0
    # THE IDENTITY THAT MAKES THE TWO NUMBERS UNABLE TO QUIETLY DISAGREE.
    assert g.gap_hours == g.elapsed_hours - g.recorded_hours

    # A contiguous stream is not accused of a gap it does not have.
    assert rows["UNREAD"].n_gaps == 0
    assert rows["UNREAD"].coverage_pct == 100.0


def test_a_day_level_reading_would_have_missed_it(tape: Path) -> None:
    """The reason the unit is an HOUR: the same outage is invisible at day granularity."""
    parts = [p for p in inventory(tape / "data/moat") if p.symbol == "GAPPY"]
    row = continuity(parts, now=NOW)[0]
    assert row.observed_days == 1
    assert row.day_gap_days in (None, 0)     # no day-level hole at all...
    assert row.largest_gap_hours == 16       # ...while sixteen unbuyable hours are missing


def test_stalled_recorder_is_visible_even_with_no_interior_gap(tape: Path) -> None:
    """A stream that died has NO internal gap and a perfect coverage_pct -- hours_since_last is
    the only thing that catches it, which is why it is reported alongside."""
    parts = [p for p in inventory(tape / "data/moat") if p.symbol == "UNREAD"]
    row = continuity(parts, now=NOW)[0]
    assert row.n_gaps == 0
    assert row.coverage_pct == 100.0
    assert row.hours_since_last is not None and row.hours_since_last >= 36


def test_measure_hour_gaps_refuses_a_single_observation() -> None:
    """One hour cannot carry a gap measurement, and None says so rather than 0."""
    assert measure_hour_gaps([datetime(2026, 8, 1, 0, tzinfo=UTC)]) is None
    assert measure_hour_gaps([]) is None


# -------------------------------------------------- 2. a recorded-but-never-read symbol --------

def test_recorded_but_never_read_symbol_is_identified(tape: Path) -> None:
    parts = inventory(tape / "data/moat")
    reads = read_records(tape)
    u = utilisation(parts, reads, moat_root=tape / "data/moat", venues=VENUES)

    assert u.status == MEASURED
    assert u.unread_symbols == ["fut/UNREAD"]
    # ...and the read one is NOT accused of being unread.
    assert not any("GAPPY" in s for s in u.unread_symbols)
    # The unread range carries the size of the loss, not just its name.
    top = u.unread_ranges[0]
    assert (top["venue"], top["symbol"]) == ("fut", "UNREAD")
    assert top["from_day"] == "20260802" and top["to_day"] == "20260803"
    assert top["symbol_hours"] == 48
    assert top["bytes"] == 48 * 50


def test_read_record_grain_is_not_promoted(tape: Path) -> None:
    """The one hour-grained record stays hour-grained, and the bracket brackets."""
    parts = inventory(tape / "data/moat")
    reads = read_records(tape)
    store = next(r for r in reads if r.artifact == "data/micro_feature_store.json")
    assert store.status == MEASURED and store.grain == GRAIN_HOUR and len(store.hours) == 4

    u = utilisation(parts, reads, moat_root=tape / "data/moat", venues=VENUES)
    assert u.symbol_hours_on_disk == 56
    assert u.symbol_hours_read == 4
    assert u.symbol_hours_read_pct == pytest.approx(100.0 * 4 / 56, abs=1e-3)
    # The upper bound credits every hour of the touched DAY -- 8 of GAPPY's hours, not 4.
    assert u.symbol_hours_read_pct_upper_bound == pytest.approx(100.0 * 8 / 56, abs=1e-3)
    assert u.symbol_hours_read_pct < u.symbol_hours_read_pct_upper_bound


# ------------------------------------- 3. NOT-READABLE-HERE is never 0%, and 0% is a finding ----

def test_absent_tape_is_not_zero_percent(tmp_path: Path) -> None:
    """No tape -> every figure is None and the missing paths are named. NEVER 0.0."""
    u = utilisation([], read_records(tmp_path), moat_root=tmp_path / "data/moat", venues=VENUES)
    assert u.status == NOT_READABLE_HERE
    for value in (u.symbol_hours_read_pct, u.symbol_days_read_pct, u.symbols_read_pct,
                  u.bytes_read_pct, u.bytes_read_pct_upper_bound,
                  u.symbol_hours_read_pct_upper_bound, u.symbol_hours_read, u.bytes_on_disk):
        assert value is None, "NOT-READABLE-HERE must not publish a number, least of all zero"
    assert u.missing_paths, "the exact missing paths must be named, not merely 'no data'"
    assert all(str(tmp_path / "data/moat") in p for p in u.missing_paths)


def test_zero_percent_is_reported_when_it_is_actually_measured(tmp_path: Path) -> None:
    """Tape present, consumption record present, nothing overlapping -> a real, damning 0.0."""
    _write_partitions(tmp_path, "fut", "NEVER", "20260801", [0, 1, 2])
    (tmp_path / "data/micro_feature_store.json").write_text(
        json.dumps({"SOMEONEELSE/20200101_00": {}}), "utf-8")
    parts = inventory(tmp_path / "data/moat")
    u = utilisation(parts, read_records(tmp_path), moat_root=tmp_path / "data/moat",
                    venues=VENUES)
    assert u.status == MEASURED
    assert u.symbol_hours_read_pct == 0.0
    assert u.bytes_read_pct == 0.0
    assert u.symbol_hours_on_disk == 3


def test_tape_without_any_consumption_record_is_partial_not_zero(tmp_path: Path) -> None:
    """The third state. 0% read and 'nobody records their reads' are the same evidence."""
    _write_partitions(tmp_path, "fut", "LONELY", "20260801", [0, 1])
    parts = inventory(tmp_path / "data/moat")
    u = utilisation(parts, read_records(tmp_path), moat_root=tmp_path / "data/moat",
                    venues=VENUES)
    assert u.status == PARTIAL
    assert u.symbol_hours_read_pct is None
    assert u.symbol_hours_on_disk == 2      # what IS measurable is still reported
    assert u.missing_paths


def test_full_report_in_a_checkout_never_publishes_a_fabricated_utilisation() -> None:
    """The end-to-end honesty rail on THIS repo, where the tape is genuinely absent."""
    rep = build_report(REPO, now=NOW)
    util = rep["utilisation"]
    assert rep["status"] == NOT_READABLE_HERE
    assert util["status"] == NOT_READABLE_HERE
    for key in ("symbol_hours_read_pct", "bytes_read_pct", "symbols_read_pct",
                "symbol_hours_read_pct_upper_bound", "bytes_read_pct_upper_bound"):
        assert util[key] is None, f"{key} must be None, not a number, when the tape is absent"
    assert util["missing_paths"] and rep["tape"]["missing_paths"]
    # The documented VPS numbers are carried, tagged, and NOT merged into a measured field.
    doc = util["documented_reference"]
    assert doc["status"] == "DOCUMENTED-NOT-MEASURED"
    assert doc["scored_fraction_of_tape_pct_upper_bound"] is not None
    assert doc["scored_fraction_of_tape_pct_upper_bound"] != util["symbol_hours_read_pct"]


def test_documented_citation_is_rechecked_against_its_source(tmp_path: Path) -> None:
    """A citation that cannot be re-checked is a rumour with a file name."""
    good = documented_reference(REPO)
    assert good["status"] == "DOCUMENTED-NOT-MEASURED"
    assert good["campaign"]["survivor_oos_sharpe"] == [0.103, 0.098]

    doc = tmp_path / "docs/research/VPS_STATE_20260805.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("the tape is fine and everything is different now", "utf-8")
    rotted = documented_reference(tmp_path)
    assert rotted["status"] == "DOCUMENTED-SOURCE-CHANGED"
    assert rotted["missing_tokens"]
    assert "scored_fraction_of_tape_pct_upper_bound" not in rotted


# ------------------------------------------------- 4. the ranked list picks the biggest slice ---

def test_ranked_next_actions_pick_the_largest_unread_slice(tape: Path) -> None:
    parts = inventory(tape / "data/moat")
    u = utilisation(parts, read_records(tape), moat_root=tape / "data/moat", venues=VENUES)
    actions = rank_next_actions(u, depth_level_use(recorder_declarations(REPO)), {})

    assert actions[0].rank == 1
    assert actions[0].slice_id.startswith("fut/UNREAD")
    assert actions[0].unread_symbol_hours == 48
    # Every subsequent row is smaller (or unquantified), so the ordering really is by size.
    sizes = [a.unread_symbol_hours or 0 for a in actions]
    assert sizes == sorted(sizes, reverse=True)


def test_ranked_list_prefers_hours_over_bytes(tmp_path: Path) -> None:
    """FAT is not BIG. A venue that writes heavier snapshots must not outrank more tape."""
    _write_partitions(tmp_path, "fut", "FAT", "20260801", [0, 1], size=10_000)
    _write_partitions(tmp_path, "fut", "LONG", "20260801", list(range(10)), size=10)
    (tmp_path / "data/micro_feature_store.json").write_text(json.dumps({"X/20200101_00": {}}),
                                                            "utf-8")
    parts = inventory(tmp_path / "data/moat")
    u = utilisation(parts, read_records(tmp_path), moat_root=tmp_path / "data/moat",
                    venues=VENUES)
    actions = rank_next_actions(u, [], {})
    assert actions[0].slice_id.startswith("fut/LONG")
    assert actions[0].unread_symbol_hours == 10


def test_unrecorded_wanted_symbol_becomes_a_start_recording_action(tape: Path) -> None:
    """The one action whose cost rises with delay is stated as such."""
    parts = inventory(tape / "data/moat")
    u = utilisation(parts, read_records(tape), moat_root=tape / "data/moat", venues=VENUES)
    actions = rank_next_actions(u, [], {"wanted_never_recorded": ["ATOM"]})
    row = next(a for a in actions if a.slice_id == "ATOM")
    assert "START RECORDING" in row.action
    assert "cannot be bought back" in row.why


# --------------------------------------------- 5. the taxonomy is the census's, not ours --------

def test_every_mechanism_class_comes_from_the_census_taxonomy(tape: Path) -> None:
    parts = inventory(tape / "data/moat")
    u = utilisation(parts, read_records(tape), moat_root=tape / "data/moat", venues=VENUES)
    actions = rank_next_actions(u, depth_level_use(recorder_declarations(REPO)),
                                {"wanted_never_recorded": ["ATOM"]})
    assert actions, "the ranked list must not be empty on a tape with unread slices"
    for a in actions:
        assert a.mechanism_class in CLASS_BY_ID, (
            f"{a.mechanism_class} is not a census class -- this module must invent no taxonomy")


def test_tape_testable_classes_are_derived_from_the_taxonomys_own_data_requirements() -> None:
    """The class list is DERIVED from what each class says it needs, not asserted here."""
    classes = tape_testable_classes()
    ids = {c["class_id"] for c in classes}
    assert "orderbook_microstructure_state" in ids
    assert "informed_order_flow" in ids, (
        "the recorders write aggressor-signed prints into the same partitions; the class whose "
        "declared dataset is trade-level signed flow is already on disk")
    for c in classes:
        assert c["class_id"] in CLASS_BY_ID
        assert c["satisfied_by"] in CLASS_BY_ID[c["class_id"]].data.datasets
        assert c["matched_tokens"], "a class must name WHY the tape satisfies it"


def test_hunting_yield_reports_the_moat_result_as_a_measured_negative() -> None:
    rep = build_report(REPO, now=NOW)
    y = rep["hunting_yield"]
    assert y["status"] == NOT_READABLE_HERE
    assert y["n_hypotheses"] is None, "an unreadable screen record is not zero hypotheses"
    assert "MEASURED NEGATIVE" in y["reading"]
    assert "0.103" in y["reading"] and "0.098" in y["reading"]
    assert y["taxonomy"].startswith("libs/research/mechanism_census")


# ------------------------------------------------------------------ coverage, both directions --

def test_coverage_holes_are_reported_in_both_directions() -> None:
    """A screened-but-unrecorded name is measurable in a checkout; both sides are source."""
    rep = build_report(REPO, now=NOW)
    holes = rep["coverage_of_recording"]["holes"]
    assert set(holes) >= {"wanted_never_declared", "wanted_never_recorded",
                          "declared_never_recorded", "recorded_never_wanted",
                          "recorded_never_read"}
    # data/perp_close_panel.json declares 30 screened names; the recorders declare 20 majors.
    assert holes["wanted_never_declared"], (
        "the desk screens names no recorder writes -- that hole widens every hour and never "
        "backfills, so it must not be silently empty")
    assert "ATOM" in holes["wanted_never_declared"]
    # BTCUSDT vs BTC must not manufacture a hole out of a quote-currency suffix.
    assert "BTC" not in holes["wanted_never_declared"]


def test_recorder_universe_is_read_from_source_not_by_import() -> None:
    """Importing run_recorder_bybit calls _universe() at module scope, which hits the network."""
    decls = {d.venue: d for d in recorder_declarations(REPO)}
    assert set(decls) == {"fut", "spot", "bybit"}
    for d in decls.values():
        assert d.status == MEASURED
        assert "BTCUSDT" in d.symbols and "ETHUSDT" in d.symbols
        assert d.depth_levels is not None and 0 < d.depth_levels <= 200


def test_unread_depth_levels_are_measurable_without_the_tape() -> None:
    """The one slice whose under-use is provable from source alone: recorded vs consumed levels."""
    consumed, who = consumed_depth_levels()
    assert consumed >= 20 and who
    rows = {d.venue: d for d in depth_level_use(recorder_declarations(REPO))}
    assert rows["bybit"].recorded_levels == 25
    assert rows["bybit"].unread_levels == rows["bybit"].recorded_levels - consumed
    assert rows["bybit"].unread_levels is not None and rows["bybit"].unread_levels > 0
    # The futures recorder's 20 levels are fully consumed -- so the instrument does not invent a
    # hole where there is none.
    assert rows["fut"].unread_levels == 0
