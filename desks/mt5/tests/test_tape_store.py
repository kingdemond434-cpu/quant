"""The tape's storage invariant, tested by breaking it on purpose.

THE CLAIM UNDER TEST is the one at the top of `recorders/tape_store.py`: a partial write can
never corrupt a completed day. That is not provable by reading the code -- the previous two
collectors on this desk both LOOK correct and both rewrite a day in place -- so every crash point
in the documented write order is simulated here and the day is read back afterwards.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders import tape_store as ts  # noqa: E402
from recorders.tick_source import TICK_DTYPE, FakeTickSource  # noqa: E402

T0 = 1_780_000_000_000
DAY = ts.broker_day(T0)


def _ticks(n: int = 500, start: int = T0, point: float = 1e-5) -> np.ndarray:
    out = np.empty(n, dtype=TICK_DTYPE)
    out["time_msc"] = start + np.arange(n, dtype=np.int64) * 37
    out["time"] = out["time_msc"] // 1000
    bid_pts = 100_000 + np.arange(n, dtype=np.int64) % 40
    out["bid"] = np.round(bid_pts * point, 5)
    out["ask"] = np.round((bid_pts + 12) * point, 5)
    out["last"] = 0.0
    out["volume"] = 0
    out["flags"] = 6
    out["volume_real"] = 0.0
    return out


@pytest.fixture
def store(tmp_path: Path) -> ts.TapeStore:
    return ts.TapeStore(tmp_path / "tape")


# ------------------------------------------------------------------- encoding --
def test_integer_point_encoding_round_trips_every_price_exactly() -> None:
    """A lossy tape is worse than a smaller one. The encoder verifies this itself; so does this."""
    t = _ticks(1000)
    payload, rec = ts.encode_segment(t, "EURUSD", DAY, 1e-5, 5)
    assert rec.encoding == "int_points"
    back = ts.decode_segment(payload)
    assert np.array_equal(back["time_msc"].to_numpy(), t["time_msc"])
    assert np.allclose(back["bid"].to_numpy(), t["bid"], rtol=0, atol=1e-9)
    assert np.allclose(back["ask"].to_numpy(), t["ask"], rtol=0, atol=1e-9)


def test_a_price_that_cannot_round_trip_falls_back_to_float_and_says_so() -> None:
    """The unit is not always what the broker claims. Silently rounding the desk's only
    unrecoverable asset is the one trade this module may not make."""
    t = _ticks(50)
    t["bid"] = t["bid"] + 3.7e-7          # finer than `point`, unrepresentable in integer points
    payload, rec = ts.encode_segment(t, "ODD", DAY, 1e-5, 5)
    assert rec.encoding == "f64", "an unrepresentable price must not be quietly rounded"
    back = ts.decode_segment(payload)
    assert np.allclose(back["bid"].to_numpy(), t["bid"], rtol=0, atol=0)


def test_a_segment_with_no_point_is_written_as_float_rather_than_guessing_a_unit() -> None:
    _, rec = ts.encode_segment(_ticks(20), "NOSPEC", DAY, 0.0, 0)
    assert rec.encoding == "f64"


def test_refusing_to_encode_an_empty_segment() -> None:
    """An empty capture is a GAP ROW, not a zero-row file that reads as a successful write."""
    with pytest.raises(ValueError, match="GAP row"):
        ts.encode_segment(np.empty(0, dtype=TICK_DTYPE), "EURUSD", DAY, 1e-5, 5)


def test_a_segment_carries_its_own_manifest_row_so_it_is_never_an_orphan_mystery() -> None:
    payload, rec = ts.encode_segment(_ticks(30), "XAUUSD", DAY, 0.01, 2, cycle_id="c9")
    assert rec.sha256 == hashlib.sha256(payload).hexdigest()
    assert rec.filename.startswith(rec.sha256[:16])


# ------------------------------------------------------------------ the write --
def test_writing_the_same_ticks_twice_is_idempotent(store: ts.TapeStore) -> None:
    """Content addressing: identical bytes are the same segment, not a second copy."""
    t = _ticks(200)
    a = store.write_segment("EURUSD", DAY, t, 1e-5, 5)
    b = store.write_segment("EURUSD", DAY, t, 1e-5, 5)
    assert a.sha256 == b.sha256
    assert len(store.manifest("EURUSD", DAY)) == 1
    assert len(list(store.day_dir("EURUSD", DAY).glob("*.parquet"))) == 1


def test_read_day_dedupes_across_overlapping_segments(store: ts.TapeStore) -> None:
    """The overlap re-pull is deliberate. Its cost is duplicates, and they are removed on READ --
    never by rewriting a sealed segment, which is the one operation that can lose data."""
    t = _ticks(300)
    store.write_segment("EURUSD", DAY, t[:200], 1e-5, 5)
    store.write_segment("EURUSD", DAY, t[150:], 1e-5, 5)     # 50 ticks overlap
    df = store.read_day("EURUSD", DAY)
    assert len(df) == 300
    assert df["time_msc"].is_monotonic_increasing
    assert df["time_msc"].nunique() == 300


# ------------------------------------------------------- crash-point survival --
def test_a_crash_before_the_rename_leaves_a_temp_file_and_loses_nothing(
        store: ts.TapeStore) -> None:
    """Crash point 1: bytes written to .tmp-*, process dies. Nothing was recorded and the
    completed part of the day is untouched."""
    store.write_segment("EURUSD", DAY, _ticks(100), 1e-5, 5)
    before = store.read_day("EURUSD", DAY)
    torn = store.day_dir("EURUSD", DAY) / f"{ts._TMP_PREFIX}deadbeef"
    torn.write_bytes(b"PAR1 half a parquet file and then the power went out")

    after = store.read_day("EURUSD", DAY)
    assert len(after) == len(before), "a torn temp file must not affect a completed day"
    assert store.sweep_temp() == 1
    assert not torn.exists()
    assert len(store.read_day("EURUSD", DAY)) == len(before)


def test_a_crash_between_the_rename_and_the_manifest_is_recovered_from_the_segment_itself(
        store: ts.TapeStore) -> None:
    """Crash point 2: the segment landed, the manifest line did not. NO DATA IS LOST -- the row
    is read back out of the parquet's own key-value metadata and re-registered."""
    rec = store.write_segment("EURUSD", DAY, _ticks(250), 1e-5, 5)
    # Simulate the manifest append never happening.
    store.manifest_path("EURUSD", DAY).unlink()
    assert store.manifest("EURUSD", DAY) == []
    assert len(store.read_day("EURUSD", DAY)) == 0, "the fixture must really orphan the segment"

    out = store.reconcile("EURUSD", DAY)
    assert out["orphans_recovered"] == [rec.filename]
    assert out["missing"] == [] and out["corrupt"] == []
    assert len(store.read_day("EURUSD", DAY)) == 250, "the orphan must be readable again"
    assert store.manifest("EURUSD", DAY)[0].recovered is True, "a recovery is recorded as one"


def test_a_corrupted_segment_is_detected_and_excluded_rather_than_silently_read(
        store: ts.TapeStore) -> None:
    rec = store.write_segment("EURUSD", DAY, _ticks(120), 1e-5, 5)
    store.write_segment("EURUSD", DAY, _ticks(120, start=T0 + 10_000_000), 1e-5, 5)
    p = store.day_dir("EURUSD", DAY) / rec.filename
    raw = bytearray(p.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    p.write_bytes(bytes(raw))

    out = store.reconcile("EURUSD", DAY)
    assert rec.filename in out["corrupt"]
    verified = store.read_day("EURUSD", DAY, verify=True)
    assert len(verified) == 120, "only the intact segment may be read back"


def test_a_deleted_segment_is_reported_missing_and_never_papered_over(
        store: ts.TapeStore) -> None:
    rec = store.write_segment("EURUSD", DAY, _ticks(80), 1e-5, 5)
    (store.day_dir("EURUSD", DAY) / rec.filename).unlink()
    out = store.reconcile("EURUSD", DAY)
    assert out["missing"] == [rec.filename]
    seal = store.seal_day("EURUSD", DAY)
    assert any("missing" in n for n in seal.notes)


# ---------------------------------------------------------------- the sealing --
def test_sealing_records_what_the_day_holds_and_post_seal_growth_is_detectable(
        store: ts.TapeStore) -> None:
    store.write_segment("EURUSD", DAY, _ticks(100), 1e-5, 5)
    seal = store.seal_day("EURUSD", DAY)
    assert seal.segments == 1 and seal.rows == 100
    assert seal.manifest_sha256 and seal.bytes > 0

    store.write_segment("EURUSD", DAY, _ticks(40, start=T0 + 9_000_000), 1e-5, 5)
    rows_now = sum(r.rows for r in store.manifest("EURUSD", DAY))
    assert rows_now - store.seal("EURUSD", DAY).rows == 40, (
        "a day that grows after being sealed must be measurable as such -- the seal's "
        "completeness claim was false when it was made")


# -------------------------------------------------------------- the gap ledger --
def test_a_gap_is_recorded_with_a_named_reason_and_an_unnamed_one_is_refused(
        store: ts.TapeStore) -> None:
    store.record_gap(ts.GapRecord("EURUSD", T0, T0 + 60_000, ts.GAP_RECORDER_DOWN, "box rebooted"))
    rows = store.gaps("EURUSD", DAY)
    assert len(rows) == 1 and rows[0].reason == ts.GAP_RECORDER_DOWN
    assert rows[0].seconds == 60.0
    with pytest.raises(ValueError, match="unnamed reason"):
        store.record_gap(ts.GapRecord("EURUSD", T0, T0 + 1, "SOMETHING_ELSE"))


def test_resolving_a_gap_appends_rather_than_editing(store: ts.TapeStore) -> None:
    """The ledger is append-only for the same reason the tape is: an edit can lose a fact."""
    g = ts.GapRecord("EURUSD", T0, T0 + 60_000, ts.GAP_PULL_FAILED, "terminal down")
    store.record_gap(g)
    store.resolve_gap(g, recovered_ticks=1234)
    rows = store.gaps("EURUSD", DAY)
    assert len(rows) == 2, "the original row must still be there"
    assert {r.reason for r in rows} == {ts.GAP_PULL_FAILED, ts.GAP_RESOLVED}
    assert store.open_gaps("EURUSD", DAY) == []
    assert next(r for r in rows if r.reason == ts.GAP_RESOLVED).recovered_ticks == 1234


def test_a_gap_straddling_midnight_is_filed_under_both_days(store: ts.TapeStore) -> None:
    """A per-day integrity check must not be able to miss the half that fell outside its window."""
    midnight = int(np.datetime64(f"{DAY}T23:30", "ms").astype("int64"))
    store.record_gap(ts.GapRecord("EURUSD", midnight, midnight + 2 * 3600_000,
                                  ts.GAP_RECORDER_DOWN))
    next_day = ts.broker_day(midnight + 2 * 3600_000)
    assert next_day != DAY
    assert len(store.gaps("EURUSD", DAY)) == 1
    assert len(store.gaps("EURUSD", next_day)) == 1


# ----------------------------------------------------------------- housekeeping --
@pytest.mark.parametrize("symbol", ["AT&T", "BRK.B", "EUR/USD", "3M", "US500.cash"])
def test_broker_symbols_that_are_not_valid_directory_names_still_get_recorded(
        store: ts.TapeStore, symbol: str) -> None:
    """A symbol that cannot become a directory is a symbol that silently never gets recorded.
    The universe holds AT&T and 3M today, so this is not hypothetical."""
    store.write_segment(symbol, DAY, _ticks(20), 0.01, 2)
    df = store.read_day(symbol, DAY)
    assert len(df) == 20
    assert df["symbol"].iloc[0] == symbol, "the true symbol travels INSIDE the segment metadata"


def test_split_by_day_puts_a_straddling_pull_in_two_segments() -> None:
    edge = int(np.datetime64(f"{DAY}T23:59:59.900", "ms").astype("int64"))
    t = _ticks(20, start=edge)                      # 20 ticks * 37ms crosses midnight
    days = dict(ts.split_by_day(t))
    assert len(days) == 2, "a pull that straddles midnight must not land in one day's file"
    assert sum(v.size for v in days.values()) == 20


def test_dedupe_removes_exact_repeats_and_keeps_order() -> None:
    t = _ticks(10)
    doubled = np.concatenate([t, t])
    out = ts.dedupe(doubled)
    assert out.size == 10
    assert np.array_equal(out["time_msc"], t["time_msc"])


def test_state_is_replaced_atomically_and_survives_a_reread(store: ts.TapeStore) -> None:
    store.write_state("cursors", {"EURUSD": {"cursor_ms": T0}})
    assert store.read_state("cursors")["EURUSD"]["cursor_ms"] == T0
    assert store.read_state("nothing_here", {"d": 1}) == {"d": 1}


def test_the_clock_skew_is_recorded_because_it_is_unbuyable_afterwards(
        store: ts.TapeStore) -> None:
    """Without this, a tape recorded across a server DST change cannot be aligned to a
    UTC-stamped macro calendar, and every event study built on it is quietly out by an hour."""
    store.record_clock(T0, T0 + 7_200_000, "EURUSD")
    rows = [json.loads(x) for x in
            (store.clock_dir / f"{DAY}.jsonl").read_text("utf-8").splitlines()]
    assert rows[0]["skew_ms"] == 7_200_000


def test_measured_bytes_per_tick_is_within_the_range_the_module_claims(
        store: ts.TapeStore) -> None:
    """The retention policy is defended with a MEASURED number, so the number is a test.

    The docstring claims 3.05-3.35 B/tick on a realistic tape at this broker's observed rates.
    A synthetic tape compresses a little better than a real one, so the bound here is generous
    on the low side and hard on the high side -- what must never happen is the encoding
    regressing toward the 6.9 B/tick the desk's current gzip-jsonl bronze costs.
    """
    src = FakeTickSource(["EURUSD"], ticks_per_day=120_000)
    t = src.generate("EURUSD", T0, T0 + 6 * 3600_000)
    assert t.size > 5_000
    rec = store.write_segment("EURUSD", DAY, t, 1e-5, 5)
    per_tick = rec.bytes / rec.rows
    assert per_tick < 5.0, (f"{per_tick:.2f} B/tick -- the encoding has regressed toward the "
                            f"gzip-jsonl bronze it exists to replace")


def test_a_symbol_whose_point_changes_mid_tape_decodes_both_halves_correctly(
        store: ts.TapeStore) -> None:
    """A BROKER RE-QUOTE IS A REAL EVENT AND IT SILENTLY RE-PRICES A TAPE THAT LOOKS IT UP LATER.

    When an instrument's `digits` changes, every segment written before the change carries the
    OLD unit and every segment after carries the new one. A store that resolved `point` from
    today's registry at read time would decode half the tape at the wrong scale -- the exact
    failure `mt5desk/tape.py` warns about in writing. Each segment carries its own point, so
    both halves come back right and no registry lookup is involved.
    """
    old = _ticks(100, point=1e-5)
    new_pts = np.arange(100, dtype=np.int64) % 40 + 100
    new = _ticks(100, start=T0 + 5_000_000)
    new["bid"] = np.round(new_pts * 1e-3, 3)
    new["ask"] = np.round((new_pts + 12) * 1e-3, 3)

    a = store.write_segment("REQUOTED", DAY, old, 1e-5, 5)
    b = store.write_segment("REQUOTED", DAY, new, 1e-3, 3)
    assert a.point == 1e-5 and b.point == 1e-3, "each segment records the unit in force"

    df = store.read_day("REQUOTED", DAY)
    assert len(df) == 200
    assert np.allclose(df["bid"].to_numpy()[:100], old["bid"], atol=1e-9)
    assert np.allclose(df["bid"].to_numpy()[100:], new["bid"], atol=1e-9)
