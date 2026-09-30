"""The machine-learning laboratory reads the universe, not the head of the alphabet.

MEASURED 2026-09-24 on the trading box: `ML_LAYER.json` carried `series: 6` and
`per_series: ['3M_D1', '3M_H1', '3M_H4', '3M_M1', '3M_M15', '3M_M30']` -- six timeframes of ONE
single-name equity CFD, because the loader read `sorted(UNIVERSE.glob("*.parquet"))[:6]` and
`3M` sorts first. The lab had never seen gold, an FX pair, an index or a commodity in its life,
and its six "admissions" were six verdicts about 3M. A single-name equity is also the event
lane's, never the hypothesis lane's (two-lane order, 2026-09-06).

These tests pin the three properties that failure violated: the lane router is consulted, the
cursor rotates so every symbol is reached across passes, and a pass spends its budget on
distinct instruments rather than on one instrument's timeframes.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ml_layer as ml  # noqa: E402

#: Symbol-major, the way `_pairs()` returns them: seven timeframes of the alphabetically first
#: name, then the rest. This is exactly the shape that hid the defect.
PAIRS = [("3M", tf) for tf in ("D1", "H1", "H4", "M1", "M15", "M30", "M5")] + [
    (sym, tf) for sym in ("AUDUSD", "EURUSD", "GBPUSD", "US500", "XAGUSD", "XAUUSD")
    for tf in ("D1", "H1", "M15")]


def test_a_pass_reaches_distinct_symbols_not_one_symbols_timeframes() -> None:
    chosen, _ = ml._slice(PAIRS, 0, 6)
    assert len(chosen) == 6
    assert len({s for s, _ in chosen}) == 6, (
        f"a pass must spend its budget on six instruments, not on timeframes of one: {chosen}")


def test_the_cursor_walks_past_what_the_pass_consumed_and_covers_every_symbol() -> None:
    """Advancing by the KEPT count would step six places into a list where each symbol owns
    seven, so the same handful of names would be re-read for many passes."""
    symbols = {s for s, _ in PAIRS}
    seen: set[str] = set()
    cursor = 0
    for _ in range(len(symbols)):          # generous: coverage must arrive well inside this
        chosen, cursor = ml._slice(PAIRS, cursor, 3)
        seen |= {s for s, _ in chosen}
        if seen == symbols:
            break
    assert seen == symbols, f"the rotation never reached {sorted(symbols - seen)}"


def test_the_cursor_is_a_cycle_and_never_runs_off_the_end() -> None:
    cursor = 0
    for _ in range(40):
        chosen, cursor = ml._slice(PAIRS, cursor, 5)
        assert chosen, "a non-empty lane must always yield a slice"
        assert 0 <= cursor < len(PAIRS)


def test_the_router_is_consulted_and_never_empties_its_own_input() -> None:
    """A router that admits nothing would put the lab back where it started -- dark, with a
    tidy reason. It falls back to every series and SAYS so, which is a measurement."""
    kept, why = ml._hypothesis_lane(PAIRS)
    assert kept, "the lane may never be empty while the host holds parquets"
    assert isinstance(why, str) and why, "the routing decision is always recorded"
    if len(kept) < len(PAIRS):
        assert "may_hypothesise" in why, why
        assert not any(s == "3M" for s, _ in kept), (
            "a single-name equity CFD belongs to the event lane, not to this one")


def test_the_selection_record_names_the_whole_lane_not_only_the_slice() -> None:
    series, record = ml._closes(limit=2)
    assert record["pairs_on_host"] >= record["pairs_in_lane"] >= 1
    assert record["symbols_in_lane"] >= 1
    assert record["passes_to_cover_the_lane"] >= 1
    assert len(record["chosen"]) <= 2
    assert len({c.rsplit("_", 1)[0] for c in record["chosen"]}) == len(record["chosen"])
    assert set(series) <= set(record["chosen"])
    assert record["cursor_after"] != record["cursor_before"] or record["pairs_in_lane"] == 1
