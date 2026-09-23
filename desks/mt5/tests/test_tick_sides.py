"""Which side the venue moved, and what a zero spread is actually evidence of.

THE DEFECT THIS FILE IS THE ANSWER TO (moat series organ, 2026-09-17): 41,604 of EURUSD's 42,460
tape rows for 2026-09-15 carried ask == bid, while XAUUSD carried none. Two explanations fit that
sentence and they demand opposite responses -- either the venue quoted a locked market, or a
writer repeated the other side of a one-sided update -- and the tape could not tell them apart,
because nothing stored or read the one field that knows: `flags`.

WHAT THE MEASUREMENT SAID, and these are the numbers the tests below pin. Across 204,322,244
rows in 2,767 day files on this box: `ask == prev_ask` on 100.00% of bid-only ticks and
`bid == prev_bid` on 100.00% of ask-only ticks, on EVERY instrument including the clean ones;
ZERO rows anywhere carry a missing side; 97.9% of EURUSD's locked rows are ticks whose flags say
BOTH sides moved; both independent writers report the same fraction for the same day; and the
terminal's own `symbol_info().spread`, recorded separately in `contract_terms`, reads 0 points
for EURUSD/GBPUSD/AUDUSD/USDJPY and 5-11 for XAUUSD at the same instants. The terminal already
carries the untouched side, and the lock is real.

So the tests here are shaped by that finding rather than by the hypothesis it replaced:

  * a carry keyed on the FLAGS is forbidden -- it would overwrite a published price with an
    inferred one, and `test_a_present_side_is_never_overwritten...` is the fence;
  * a carry keyed on ABSENCE is required -- the guard for the day the feed really is one-sided;
  * `sided` must survive the round trip through parquet, because a column downstream cannot read
    is the same as no column at all;
  * the repair must be a measured NO-OP on healthy rows and IDEMPOTENT, or it is a rewrite of
    history wearing the word "repair".
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import tape  # noqa: E402
from recorders import tick_integrity as ti  # noqa: E402
from recorders import tick_recorder as tr  # noqa: E402

BID, ASK, LAST = tape.TICK_FLAG_BID, tape.TICK_FLAG_ASK, tape.TICK_FLAG_LAST
#: Fusion sets two bits MetaTrader does not document (0x400 and 0x80) alongside the documented
#: ones. Measured on this box: EURUSD/XAUUSD/US500 carry flags 1026/1028/1030/1154/1158 while the
#: share CFDs carry 2/4/6. Every test that derives a side uses the REAL values, so a future reader
#: cannot "simplify" the mask away and pass.
FUSION = 1024 | 128


def _frame(rows: list[tuple[int, float, float, int]]) -> pd.DataFrame:
    """(time_msc, bid, ask, flags) -> the shape both writers hand to `merge_day`."""
    return pd.DataFrame({
        "time": [r[0] // 1000 for r in rows],
        "bid": [r[1] for r in rows], "ask": [r[2] for r in rows],
        "last": [0.0] * len(rows), "volume": [0] * len(rows),
        "time_msc": [r[0] for r in rows], "flags": [r[3] for r in rows],
        "volume_real": [0.0] * len(rows),
    })


# ------------------------------------------------------------------ sided, from flags --
def test_sided_reads_the_documented_bits_and_ignores_the_undocumented_ones() -> None:
    """The broker sets bits MetaTrader does not define. Guessing at one would put an invention in
    a column whose whole job is to record what the venue said."""
    flags = np.array([BID, ASK, BID | ASK, LAST, 0,
                      FUSION | BID, FUSION | ASK, FUSION | BID | ASK, FUSION], dtype=np.int64)
    assert list(tape.sided_from_flags(flags)) == [
        "bid", "ask", "both", "last", "none", "bid", "ask", "both", "none"]


def test_a_volume_only_tick_is_none_not_a_quote() -> None:
    """`none` is a measurement, not a defect: a tick that names no price side did not move one,
    and calling it `both` would credit the feed with a quote update it never sent."""
    assert list(tape.sided_from_flags(np.array([16, 32, 64], dtype=np.int64))) == [
        "none", "none", "none"]


# ------------------------------------------------------------------------ the carry --
def test_a_present_side_is_never_overwritten_even_when_the_flags_call_it_unchanged() -> None:
    """THE FENCE. MT5 already carries the untouched side (measured: 100.00% of 204M rows), so a
    carry keyed on the flags would replace a price the venue published with one this desk
    inferred. A tape that does that is no longer a record of what the broker said."""
    bid = np.array([1.15490, 1.15495, 1.15495])
    ask = np.array([1.15499, 1.15499, 1.15501])          # row 1 is a bid-only tick: ask carried
    out_bid, out_ask, filled_bid, filled_ask = tape.carry_sides(bid, ask)
    assert np.array_equal(out_bid, bid) and np.array_equal(out_ask, ask)
    assert not filled_bid.any() and not filled_ask.any()


def test_an_absent_side_is_filled_from_the_last_one_this_session_quoted() -> None:
    """The guard for the day the payload really is one-sided. Without it a zero ask makes the mid
    half the price of the instrument and the spread its full width."""
    bid = np.array([1.15490, 1.15495, 1.15496])
    ask = np.array([1.15499, 0.0, 1.15501])
    out_bid, out_ask, filled_bid, filled_ask = tape.carry_sides(bid, ask)
    assert out_ask[1] == 1.15499, "the absent ask was not carried from the last real quote"
    assert list(filled_ask) == [False, True, False]
    assert not filled_bid.any() and np.array_equal(out_bid, bid)


def test_the_carry_never_crosses_a_session_boundary_without_a_seed() -> None:
    """Yesterday's close is not a fact about today's open. A leading absent side stays absent and
    is COUNTED as unfilled, rather than inheriting a quote from a day that has ended."""
    _, out_ask, _, filled_ask = tape.carry_sides(np.array([1.1, 1.1]), np.array([0.0, 1.2]))
    assert out_ask[0] == 0.0 and not filled_ask[0]
    seeded = tape.carry_sides(np.array([1.1, 1.1]), np.array([0.0, 1.2]), seed_ask=1.19)
    assert seeded[1][0] == 1.19 and seeded[3][0], "an explicit same-session seed must carry in"


def test_a_locked_quote_the_venue_really_published_survives_the_repair_untouched() -> None:
    """EURUSD 2026-09-15 in miniature: both sides moved, to the same price. The repair must not
    'fix' it -- that IS the quote, and a desk that widens it invents a spread it never paid."""
    df = _frame([(1_000, 1.15496, 1.15496, FUSION | BID | ASK),
                 (2_000, 1.15497, 1.15497, FUSION | BID | ASK)])
    out = tape.repair_sides(df.copy())
    assert list(out["bid"]) == [1.15496, 1.15497]
    assert list(out["ask"]) == [1.15496, 1.15497]
    assert list(out["sided"]) == ["both", "both"]
    assert "bid_raw" not in out.columns and "ask_raw" not in out.columns


# ----------------------------------------------------------------------- the repair --
def test_repair_sides_adds_sided_and_is_a_no_op_on_a_healthy_frame() -> None:
    """The measured outcome on every row of this desk's tape. A repair whose effect on healthy
    data is zero is a repair that cannot corrupt it."""
    df = _frame([(1_000, 1.15490, 1.15499, FUSION | BID),
                 (2_000, 1.15495, 1.15499, FUSION | BID),
                 (3_000, 1.15495, 1.15501, FUSION | ASK)])
    out = tape.repair_sides(df.copy())
    assert list(out["sided"]) == ["bid", "bid", "ask"]
    assert list(out["bid"]) == list(df["bid"]) and list(out["ask"]) == list(df["ask"])
    assert "bid_raw" not in out.columns and "ask_raw" not in out.columns
    assert list(out["flags"]) == list(df["flags"]), "flags are recorded, never rewritten"


def test_the_raw_value_is_kept_only_where_the_repair_changed_one() -> None:
    """bid/ask ARE the best-known quote because every consumer on this desk reads those two
    names; the as-delivered value is preserved beside them, and ONLY on the rows that differ, so
    the columns' presence is itself the signal that a reconstruction happened."""
    df = _frame([(1_000, 1.15490, 1.15499, FUSION | BID | ASK),
                 (2_000, 1.15495, 0.0, FUSION | BID)])
    out = tape.repair_sides(df.copy())
    assert out["ask"].iloc[1] == 1.15499
    assert out["ask_raw"].iloc[1] == 0.0
    assert pd.isna(out["ask_raw"].iloc[0]), "an untouched row must carry no raw value"
    assert "bid_raw" not in out.columns, "the bid was never reconstructed; do not invent a column"


def test_repair_sides_is_idempotent() -> None:
    """Applied on every merge, so a day file goes through it hundreds of times. A second pass
    that moves a price is a file that drifts a little further from the tape every hour."""
    df = _frame([(1_000, 1.15490, 0.0, FUSION | BID),
                 (2_000, 1.15495, 1.15499, FUSION | BID | ASK)])
    once = tape.repair_sides(df.copy())
    twice = tape.repair_sides(once.copy())
    pd.testing.assert_frame_equal(once, twice)


def test_repair_sides_survives_a_frame_with_no_flags_and_an_empty_one() -> None:
    """The tape has been written by more than one generation of this code. A frame that predates
    `flags` must still come back usable, marked `none` -- unmeasured, never a guess."""
    df = _frame([(1_000, 1.1, 1.2, 0)]).drop(columns=["flags"])
    out = tape.repair_sides(df)
    assert list(out["sided"]) == ["none"]
    assert len(tape.repair_sides(_frame([]).iloc[0:0])) == 0


# ------------------------------------------------------------- through the day file --
def test_merge_day_heals_an_existing_file_without_rewriting_its_prices(tmp_path: Path) -> None:
    """The whole point of putting the repair in `merge_day`: a day already on disk gains `sided`
    on its next ordinary merge, and its recorded prices are byte-identical afterwards."""
    out = tmp_path / "EURUSD" / "2026-09-15.parquet"
    out.parent.mkdir(parents=True)
    old = _frame([(1_000, 1.15496, 1.15496, FUSION | BID | ASK),
                  (2_000, 1.15497, 1.15497, FUSION | BID)])
    old.to_parquet(out, index=False)                      # a file from before `sided` existed
    fresh = _frame([(3_000, 1.15498, 1.15499, FUSION | ASK)])
    assert tape.write_day(fresh, out) == 3

    t = pq.read_table(out)
    assert str(t.schema.field("sided").type) == "string"
    assert t.column("sided").to_pylist() == ["both", "bid", "ask"]
    assert t.column("bid").to_pylist() == [1.15496, 1.15497, 1.15498]
    assert t.column("ask").to_pylist() == [1.15496, 1.15497, 1.15499]
    assert "bid_raw" not in t.schema.names, "nothing was reconstructed; no raw column is owed"
    # merging the same chunk again changes nothing -- the repair must not manufacture a duplicate
    assert tape.write_day(fresh, out) == 3


def test_a_one_sided_payload_on_disk_is_repaired_and_says_so(tmp_path: Path) -> None:
    """The case the repair exists for. A day whose ask was never published comes back with the
    carried quote in `ask`, the delivered 0.0 in `ask_raw`, and `sided` naming the bid."""
    out = tmp_path / "EURUSD" / "2026-09-15.parquet"
    out.parent.mkdir(parents=True)
    tape.write_day(_frame([(1_000, 1.15490, 1.15499, FUSION | BID | ASK),
                           (2_000, 1.15495, 0.0, FUSION | BID)]), out)
    t = pq.read_table(out)
    assert t.column("ask").to_pylist() == [1.15499, 1.15499]
    raw = t.column("ask_raw").to_pylist()
    # NaN, not null: the raw column is a float column like every other price here, and "no raw
    # value on this row" is the same absence pandas already carries for `recv_utc` on a row the
    # other writer produced. One absence convention per file beats two.
    assert np.isnan(raw[0]) and raw[1] == 0.0
    assert t.column("sided").to_pylist() == ["both", "bid"]


def test_sides_summary_separates_a_venue_lock_from_a_repeated_side() -> None:
    """The two readings of one zero spread, and the only field that tells them apart."""
    venue = tape.sides_summary(tape.repair_sides(
        _frame([(1_000, 1.1, 1.1, FUSION | BID | ASK), (2_000, 1.2, 1.2, FUSION | BID | ASK)])))
    assert venue["locked_frac"] == 1.0 and venue["sided_both"] == 2 and venue["sided_bid"] == 0
    repeated = tape.sides_summary(tape.repair_sides(
        _frame([(1_000, 1.1, 1.1, FUSION | BID), (2_000, 1.2, 1.2, FUSION | BID)])))
    assert repeated["locked_frac"] == 1.0 and repeated["sided_bid"] == 2


# ------------------------------------------------------------------- the audit path --
def test_audit_sides_reads_both_writers_naming_conventions(tmp_path: Path) -> None:
    """`YYYY-MM-DD.parquet` is this module's writer and `YYYYMMDD.parquet` is moat_silver's, in
    ONE directory. A reader that knows only one of them measures half the tape -- which is the
    exact shape of evidence that produces a confident wrong answer."""
    d = tmp_path / "EURUSD"
    d.mkdir(parents=True)
    rows = [(1_000, 1.15496, 1.15496, FUSION | BID | ASK),
            (2_000, 1.15497, 1.15499, FUSION | BID)]
    _frame(rows).to_parquet(d / "2026-09-15.parquet", index=False)
    _frame(rows).to_parquet(d / "20260915.parquet", index=False)
    assert [day for day, _ in tape.day_files("EURUSD", tmp_path)] == ["2026-09-15", "2026-09-15"]

    rep = tape.audit_sides(["EURUSD"], days=3, root=tmp_path)
    assert rep["instrument_days"] == 2 and rep["unreadable"] == 0
    assert {r["writer"] for r in rep["rows"]} == {"hourly", "silver"}
    for r in rep["rows"]:
        assert r["zero_spread_frac_before"] == r["zero_spread_frac_after"] == 0.5
        assert r["filled_bid"] == 0 and r["filled_ask"] == 0
    assert rep["sides_filled"] == 0, "the audit must not alter what it measures"


def test_the_audit_never_writes(tmp_path: Path) -> None:
    """`--dry-run` is the mode a session uses to decide whether the repair is a good idea. A
    measurement that silently applies the thing it is measuring cannot answer that."""
    d = tmp_path / "EURUSD"
    d.mkdir(parents=True)
    path = d / "2026-09-15.parquet"
    _frame([(1_000, 1.15490, 1.15499, FUSION | BID | ASK),
            (2_000, 1.15495, 0.0, FUSION | BID)]).to_parquet(path, index=False)
    before = path.read_bytes()
    rep = tape.audit_sides(["EURUSD"], days=1, root=tmp_path)
    assert rep["sides_filled"] == 1, "the audit must still REPORT what a repair would fill"
    assert path.read_bytes() == before, "the audit wrote to the tape"


# ------------------------------------------------------------------- the recorder --
def test_the_recorder_fills_only_an_absent_side_and_counts_it(tmp_path: Path) -> None:
    """The capture-time half of the same rule, on the numpy structured array the store writes."""
    from recorders.tick_source import TICK_DTYPE
    chunk = np.zeros(3, dtype=TICK_DTYPE)
    chunk["time_msc"] = [1_000, 2_000, 3_000]
    chunk["bid"] = [1.15490, 1.15495, 1.15496]
    chunk["ask"] = [1.15499, 0.0, 1.15499]                # row 1's ask was never published
    chunk["flags"] = [FUSION | BID | ASK, FUSION | BID, FUSION | BID]
    row: dict = {}
    out, filled = tr._carry_quote(chunk, row, "2026-09-15")
    assert filled == 1
    assert list(out["ask"]) == [1.15499, 1.15499, 1.15499]
    assert list(chunk["ask"]) == [1.15499, 0.0, 1.15499], "the pulled array was mutated in place"
    assert row["last_quote"] == {"day": "2026-09-15", "bid": 1.15496, "ask": 1.15499}


def test_the_recorder_carries_within_a_day_and_resets_across_one() -> None:
    """The seed is the session boundary. A chunk continuing today inherits today's last quote; a
    chunk opening tomorrow does not, and its leading absence stays an absence."""
    from recorders.tick_source import TICK_DTYPE
    chunk = np.zeros(1, dtype=TICK_DTYPE)
    chunk["time_msc"] = [4_000]
    chunk["bid"], chunk["ask"] = [1.15500], [0.0]
    chunk["flags"] = [FUSION | BID]

    same = {"last_quote": {"day": "2026-09-15", "bid": 1.15496, "ask": 1.15499}}
    out, filled = tr._carry_quote(chunk, same, "2026-09-15")
    assert filled == 1 and out["ask"][0] == 1.15499

    across = {"last_quote": {"day": "2026-09-14", "bid": 1.15496, "ask": 1.15499}}
    out2, filled2 = tr._carry_quote(chunk, across, "2026-09-15")
    assert filled2 == 0 and out2["ask"][0] == 0.0, "yesterday's close leaked into today's open"


def test_a_cycle_reports_the_sides_it_filled(tmp_path: Path) -> None:
    """UNWIRED IS A DEFECT. The count reaches the cycle report and the in-repo status file, so a
    feed that starts publishing one-sided payloads says so on the cycle it happens."""
    from recorders.tape_store import TapeStore
    from recorders.tick_source import FakeTickSource
    src = FakeTickSource(["EURUSD"], ticks_per_day=2_000)
    rec = tr.TickRecorder(src, tr.RecorderConfig(tape_root=tmp_path / "tape", cycle_s=3600,
                                                 cold_start_days=1, disk_floor_bytes=0))
    rep = rec.run_once(now_ms=1_780_000_000_000)
    assert rep.sides_filled == 0, "the fake publishes both sides; nothing should be filled"
    assert "sides_filled" in rep.__dict__
    store = TapeStore(tmp_path / "tape")
    day = next(iter(store.days("EURUSD")), None)
    assert day, "the rig recorded nothing, so this test proves nothing"
    df = store.read_day("EURUSD", day)
    assert (np.asarray(df["ask"]) > np.asarray(df["bid"])).all()


# ------------------------------------------------------------------ the ONE_SIDED line --
def test_one_sided_is_named_with_its_fraction_and_its_cause() -> None:
    """The finding must carry the number AND what the flags say caused it, because the two causes
    of a zero spread demand opposite responses."""
    v = ti.DayVerdict(symbol="EURUSD", day="2026-09-15", verdict=ti.OK, locked_rate=0.9798,
                      asset_class="forex", one_sided=True,
                      sided_counts={"both": 41_226, "bid": 975, "ask": 258})
    _, reasons = ti._verdict(v)
    line = next(r for r in reasons if r.startswith("ONE_SIDED"))
    assert "97.98%" in line and "20%" in line and "forex" in line
    assert "VENUE-QUOTED" in line, "flags said BOTH on most ticks; that is a real locked quote"

    v.sided_counts = {"both": 100, "bid": 41_226, "ask": 258}
    _, reasons = ti._verdict(v)
    assert "ONE-SIDED PAYLOAD" in next(r for r in reasons if r.startswith("ONE_SIDED"))


def test_one_sided_reports_and_does_not_move_the_verdict() -> None:
    """Deliberate, and the reason is in this checker's own history: half this desk's FX days
    cross the line every day because the account quotes raw FX, and a `degraded` list capped at
    200 full of them would bury the findings that mean something. Recorded, not corrected."""
    clean = ti.DayVerdict(symbol="EURUSD", day="2026-09-15", verdict=ti.OK, coverage_frac=1.0,
                          one_sided=True, asset_class="forex", locked_rate=0.98,
                          sided_counts={"both": 10})
    worst, reasons = ti._verdict(clean)
    assert worst == ti.OK
    assert any(r.startswith("ONE_SIDED") for r in reasons), "the finding must still be named"


def test_a_metal_is_never_called_one_sided_and_an_unknown_symbol_is_never_called_fx() -> None:
    """Routing is by the broker's own registry, never by a symbol list and never by a name. A
    string the registry does not carry is UNCLASSIFIED, which is a verdict, not a permission."""
    assert tape.is_fx("EURUSD") is True
    assert tape.is_fx("XAUUSD") is False
    assert tape.is_fx("NOTAREALSYMBOL") is False
    assert tape.asset_class_of("NOTAREALSYMBOL") == ""
