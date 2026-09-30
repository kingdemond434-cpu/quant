"""ONE FIELD, FOUR PRODUCERS, AND THE STAMP WAS LYING ABOUT WHICH ONE YOU WERE HOLDING.

`universe_registry`'s own header has named this collapse since it was written -- `fetch_universe`
takes an H1 median, `expand_universe` and `download_all_symbols` take a `symbol_info.spread`
snapshot, all three into `median_spread_pts` -- and naming it did not stop the next writer.

MEASURED 2026-09-24 on the trading box. All 245 stamped rows read `download_all_symbols` with an
identical `at` of 2026-09-21T22:25:20Z: one `symbol_info.spread` snapshot of the whole registry,
taken at SERVER HOUR 01, eighty-five minutes after the rollover and the widest window of the day
(hour 01 runs a median 1.67x, p90 5.29x and max 30x each symbol's own 24h median). Meanwhile
`MT5-Universe` fired HOURLY and re-wrote the same field from an H1 bar median WITHOUT touching
`_provenance` -- so the file claimed a snapshot while holding a bar median, and a reader had no
way to tell. A stale stamp is worse than a missing one: it is a false claim about a measurement.

These pin the ranking that ends it, and the ranking is by what the number MEANS:

    realized_fills       > fusion_zero_m1_tape > h1_spread_median > download_all_symbols
    (an execution)         (~100k ticked bars)   (a PRE-2021        (one instant, and on this
                                                  FIXED-SPREAD era   account that instant was
                                                  on this broker)    the rollover)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ur = pytest.importorskip("mt5desk.universe_registry")

TAPE, H1, SNAP, FILLS = ("fusion_zero_m1_tape", "h1_spread_median",
                         "download_all_symbols", "realized_fills")


def _row(value, source=None):
    row = {"median_spread_pts": value}
    if source is not None:
        row["_provenance"] = {"median_spread_pts": {"source": source, "at": "2026-09-21T22:25:20"}}
    return row


def test_the_hourly_collector_may_not_overwrite_the_tape():
    """This is the whole point: the hourly clobber that would revert every correction."""
    ok, why = ur.may_write_median_spread(_row(2.0, TAPE), H1)
    assert ok is False
    assert TAPE in why and "leave the stamp lying" in why


def test_the_hourly_collector_may_not_overwrite_the_desks_own_fills():
    assert ur.may_write_median_spread(_row(5.0, FILLS), H1)[0] is False
    assert ur.may_write_median_spread(_row(5.0, FILLS), TAPE)[0] is False


def test_the_tape_may_overwrite_the_rollover_snapshot_and_the_h1_median():
    assert ur.may_write_median_spread(_row(6.0, SNAP), TAPE)[0] is True
    assert ur.may_write_median_spread(_row(160.0, H1), TAPE)[0] is True


def test_a_producer_may_always_rewrite_its_own_field():
    """Otherwise a re-measurement could never land and the ranking would freeze the registry."""
    for src in (FILLS, TAPE, H1, SNAP):
        assert ur.may_write_median_spread(_row(3.0, src), src)[0] is True


def test_an_absent_or_unstamped_value_is_writable_by_anyone():
    """Something beats nothing. 138 rows on the build box carry no stamp at all."""
    assert ur.may_write_median_spread({}, SNAP)[0] is True
    assert ur.may_write_median_spread(_row(None), SNAP)[0] is True
    ok, why = ur.may_write_median_spread(_row(12.0), H1)
    assert ok is True and "no median_spread_pts" not in why


def test_an_unnamed_writer_ranks_below_every_named_one():
    """A producer nobody ranked cannot claim to beat one that is ranked. Absence is not rank."""
    assert ur.may_write_median_spread(_row(2.0, TAPE), "some_new_script")[0] is False
    assert ur.may_write_median_spread(_row(2.0, SNAP), "some_new_script")[0] is False
    # ... but it may still fill a field nobody owns
    assert ur.may_write_median_spread(_row(2.0, "an_unrecognised_stamp"), "some_new_script")[0]


def test_the_ranking_is_ordered_best_first_and_has_no_duplicates():
    ranked = ur.MEDIAN_SPREAD_PRODUCERS
    assert ranked[0] == FILLS, "an execution beats every inference"
    assert ranked.index(TAPE) < ranked.index(H1) < ranked.index(SNAP)
    assert len(set(ranked)) == len(ranked)


def test_the_collectors_declare_a_source_the_ranking_knows():
    """A collector whose stamp is not in the ranking silently becomes unrankable."""
    eu = pytest.importorskip("expand_universe")
    fu = pytest.importorskip("fetch_universe")
    for mod in (eu, fu):
        assert mod.MEDIAN_SPREAD_SOURCE in ur.MEDIAN_SPREAD_PRODUCERS
