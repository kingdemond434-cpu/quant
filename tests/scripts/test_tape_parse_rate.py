"""R0529: the reader must COUNT what it discards, and the fence must fire on both ways a venue
goes dark -- silently dropped, and never read at all.

The bug these pin is on the record: 221,000 of 221,000 bybit entries dropped for mislabelled
fields, reported as a venue with no trades; then, once parsing was fixed, 440 files on disk and
ZERO budgeted because a venue-major path sort was sliced with `[-each:]`. Both failure modes are
INVISIBLE unless attempts are counted, which is the whole of L1.60.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.build_bars as B
import scripts.check_tape_parse_rate as C

T0 = 1_767_225_600_000


# ------------------------------------------------------------------ the counter itself

def test_a_fully_unparseable_venue_is_distinguishable_from_a_quiet_one():
    """THE DEFECT, EXACTLY. Both rows yield zero prints; only the counter separates them."""
    broken = {"t": T0, "k": "trades", "v": [{"nope": 1}, {"nope": 2}]}
    quiet = {"t": T0, "k": "trades", "v": []}

    a_broken, a_quiet = B.ParseAttrition(), B.ParseAttrition()
    assert B.trades_from(broken, a_broken) == []
    assert B.trades_from(quiet, a_quiet) == []

    assert a_broken.entries == 2 and a_broken.parsed == 0
    assert a_broken.parse_rate == 0.0, "a total parse loss must read as 0.0, not as absence"
    assert a_quiet.entries == 0
    assert a_quiet.parse_rate is None, "nothing attempted is UNMEASURED, never a clean zero"


def test_the_real_bybit_schema_parses_and_is_counted():
    """The shape the recorder actually wrote -- price/time/size, not p/T/v."""
    row = {"t": T0, "k": "trades",
           "v": [{"price": "100.5", "time": str(T0), "size": "0.3"},
                 {"price": "101.0", "time": str(T0 + 1), "size": "0.7"}]}
    a = B.ParseAttrition()
    assert len(B.trades_from(row, a)) == 2
    assert (a.entries, a.parsed, a.dropped) == (2, 2, 0)
    assert a.parse_rate == 1.0


def test_drop_reasons_are_separate_because_they_point_at_different_repairs():
    row = {"t": T0, "k": "trades",
           "v": ["not-a-dict", {"price": "x", "time": "y", "size": "1"},
                 {"price": "0", "time": str(T0), "size": "1"}]}
    a = B.ParseAttrition()
    assert B.trades_from(row, a) == []
    assert a.not_dict == 1, "a schema change"
    assert a.bad_number == 1, "a corrupt payload"
    assert a.no_ts_or_px == 1, "well-formed and still refused"
    assert a.dropped == 3 and a.entries == 3


def test_counting_is_opt_in_so_the_existing_consumers_are_unchanged():
    row = {"t": T0, "k": "trades", "v": [{"price": "100.5", "time": str(T0), "size": "0.3"}]}
    assert B.trades_from(row) == [(T0, 100.5, 0.3)]


# ------------------------------------------------------------------ the budget, one level down

def _tape(root: Path, venue: str, symbol: str, days: list[str]) -> None:
    for d in days:
        p = root / venue / symbol / f"{d}_00.jsonl.gz"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")


def test_no_venue_can_be_starved_by_the_alphabet(tmp_path):
    """THE SEVEN-DAY DEFECT. `sorted()` on `<venue>/<symbol>/<file>` is VENUE-MAJOR, so `[-each:]`
    took the alphabetically-last venue. bybit < fut < spot, so bybit never made the cut however
    recent its files were -- 440 on disk, 0 budgeted, and R0378's parse fix moved not one bar."""
    root = tmp_path / "moat"
    _tape(root, "bybit", "BTCUSDT", ["20260817", "20260818", "20260819"])   # the NEWEST tape
    _tape(root, "spot", "BTCUSDT", [f"202607{d:02d}" for d in range(1, 21)])  # old, but sorts last
    files = sorted(root.glob("*/*/*.jsonl.gz"))

    assert files[-3:] == sorted(root.glob("spot/*/*.jsonl.gz"))[-3:], \
        "fixture does not reproduce the venue-major sort the bug depended on"

    got = B.newest_across_venues(files, 6)
    venues = {p.parent.parent.name for p in got}
    assert venues == {"bybit", "spot"}, f"a venue was starved: {sorted(venues)}"
    assert len(got) == 6, "the total budget must not grow -- this reorders reads, it does not add"


def test_the_budget_takes_the_newest_within_a_venue(tmp_path):
    root = tmp_path / "moat"
    _tape(root, "spot", "BTCUSDT", ["20260101", "20260601", "20260819"])
    got = B.newest_across_venues(sorted(root.glob("*/*/*.jsonl.gz")), 1)
    assert [p.name for p in got] == ["20260819_00.jsonl.gz"]


def test_a_symbol_on_one_venue_is_unaffected(tmp_path):
    root = tmp_path / "moat"
    _tape(root, "fut", "BTCUSDT", ["20260101", "20260102", "20260103"])
    got = B.newest_across_venues(sorted(root.glob("*/*/*.jsonl.gz")), 2)
    assert [p.name for p in got] == ["20260102_00.jsonl.gz", "20260103_00.jsonl.gz"]


# ------------------------------------------------------------------ the fence

def _write(tmp_path: Path, doc: object) -> Path:
    p = tmp_path / "build_bars.json"
    p.write_text(json.dumps(doc), "utf-8")
    return p


def test_the_fence_refuses_an_artifact_that_never_counted(tmp_path):
    rep = C.build_report(_write(tmp_path, {"venues": {"spot": 5}}), moat=tmp_path / "none")
    assert rep["status"] == "UNMEASURED", "an uncounted discard is the defect, not its absence"
    assert C.fence_exit(rep["status"], C.PASSING, scanned=rep["n_venues"], of="v") != 0


def test_the_fence_refuses_a_missing_artifact(tmp_path):
    rep = C.build_report(tmp_path / "absent.json", moat=tmp_path / "none")
    assert rep["status"] == "NO-ARTIFACT"


def test_the_fence_fires_on_a_collapsed_parse_rate(tmp_path):
    doc = {"parse": {"bybit": {"entries": 221_000, "parsed": 0},
                     "spot": {"entries": 5_000, "parsed": 5_000}}}
    rep = C.build_report(_write(tmp_path, doc), moat=tmp_path / "none")
    assert rep["status"] == "COLLAPSED"
    assert rep["venues"]["bybit"]["verdict"] == "COLLAPSED"
    assert rep["venues"]["spot"]["verdict"] == "OK"
    assert any("bybit" in b for b in rep["breaches"])


def test_the_fence_fires_when_a_venue_on_disk_was_never_read(tmp_path):
    """The R0378-inert case: parsing is perfect for everything the builder actually opened."""
    moat = tmp_path / "moat"
    _tape(moat, "bybit", "BTCUSDT", ["20260819"])
    _tape(moat, "spot", "BTCUSDT", ["20260819"])
    doc = {"parse": {"spot": {"entries": 5_000, "parsed": 5_000}}}
    rep = C.build_report(_write(tmp_path, doc), moat=moat)
    assert rep["status"] == "VENUE-UNREAD"
    assert rep["venues"]["bybit"]["verdict"] == "UNREAD"
    assert rep["venues"]["bybit"]["parse_rate"] is None, "never read is unmeasured, not 0%"


def test_a_thin_sample_is_unjudged_rather_than_passed(tmp_path):
    doc = {"parse": {"spot": {"entries": 3, "parsed": 0}}}
    rep = C.build_report(_write(tmp_path, doc), moat=tmp_path / "none")
    assert rep["venues"]["spot"]["verdict"] == "UNJUDGED"
    assert rep["status"] == "OK", "too few attempts to decide is not a breach"


def test_a_healthy_run_passes_and_is_not_vacuous(tmp_path):
    moat = tmp_path / "moat"
    _tape(moat, "spot", "BTCUSDT", ["20260819"])
    doc = {"parse": {"spot": {"entries": 5_000, "parsed": 5_000}}}
    rep = C.build_report(_write(tmp_path, doc), moat=moat)
    assert rep["status"] == "OK"
    assert C.fence_exit(rep["status"], C.PASSING, scanned=rep["n_venues"], of="v") == 0


@pytest.mark.parametrize("scanned", [0, None])
def test_the_fence_cannot_pass_over_nothing(scanned):
    """L1.57: a passing status over an empty denominator is refused at the exit site."""
    if scanned == 0:
        assert C.fence_exit("OK", C.PASSING, scanned=0, of="v") != 0
