"""Too-good results are fast-tracked to forward test, never auto-rejected (zuck 2026-11-11).

The gauntlet's plausibility forensics list each flagged cell that cleared every leak test in
data/plausibility/FAST_TRACK.json. Forward shadow must replay those rows first, so a pass that is
cut never strands them, while keeping symbol groups whole and dropping nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import shadow_forward as sf  # noqa: E402

P1 = {"lookback": 20}
P2 = {"lookback": 40}
ROWS = [
    ("AUDUSD", "asia", P1, "carry", "LONG"),
    ("AUDUSD", "asia", P2, "carry", "LONG"),
    ("EURUSD", "london", P1, "jump", "SHORT"),
    ("XAUUSD", "asia", P2, "formula", "LONG"),
    ("XAUUSD", "asia", P1, "formula", "LONG"),
]


def _write(tmp_path: Path, cells: list) -> Path:
    p = tmp_path / "FAST_TRACK.json"
    p.write_text(json.dumps({"cells": cells}), encoding="utf-8")
    return p


def test_a_fast_tracked_row_moves_its_whole_symbol_group_to_the_front(tmp_path) -> None:
    cells = sf.fast_track_cells(_write(tmp_path, [
        {"sym": "XAUUSD", "family": "formula", "params": {"lookback": 20},
         "verdict": "MONSTER_CANDIDATE"}]))
    out, n = sf._fast_track_first(list(ROWS), cells)
    assert n == 1
    assert [r[0] for r in out] == ["XAUUSD", "XAUUSD", "AUDUSD", "AUDUSD", "EURUSD"]
    assert out[:2] == ROWS[3:]          # the group stays whole and in its order
    assert sorted(map(repr, out)) == sorted(map(repr, ROWS))   # nothing dropped or added


def test_params_match_regardless_of_key_order(tmp_path) -> None:
    rows = [("EURUSD", "x", {"a": 1, "b": 2}, "jump", "LONG"), ROWS[0]]
    cells = sf.fast_track_cells(_write(tmp_path, [
        {"sym": "EURUSD", "family": "jump", "params": {"b": 2, "a": 1}}]))
    out, n = sf._fast_track_first(list(reversed(rows)), cells)
    assert n == 1 and out[0][0] == "EURUSD"


def test_a_different_family_or_params_is_not_fast_tracked(tmp_path) -> None:
    cells = sf.fast_track_cells(_write(tmp_path, [
        {"sym": "AUDUSD", "family": "jump", "params": P1},
        {"sym": "EURUSD", "family": "jump", "params": {"lookback": 99}}]))
    out, n = sf._fast_track_first(list(ROWS), cells)
    assert n == 0 and out == ROWS


def test_an_absent_or_unreadable_list_reorders_nothing(tmp_path) -> None:
    assert sf.fast_track_cells(tmp_path / "missing.json") == set()
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert sf.fast_track_cells(bad) == set()
    assert sf._fast_track_first(list(ROWS), set()) == (ROWS, 0)


def test_malformed_cells_are_skipped_not_fatal(tmp_path) -> None:
    cells = sf.fast_track_cells(_write(tmp_path, [
        "junk", {"sym": "EURUSD"}, {"family": "jump"},
        {"sym": "EURUSD", "family": "jump", "params": P1}]))
    assert cells == {("EURUSD", "jump", sf._params_id(P1))}


def test_the_reader_points_at_the_file_the_gauntlet_writes() -> None:
    assert sf.FAST_TRACK == DESK / "data" / "plausibility" / "FAST_TRACK.json"


def test_the_forward_pass_applies_the_fast_track_after_the_staleness_order() -> None:
    src = (DESK / "research" / "shadow_forward.py").read_text("utf-8")
    body = src[src.index("def main("):]
    i_stale = body.index("_stalest_symbols_first(enrolled, state)")
    i_fast = body.index("_fast_track_first(enrolled, fast_track_cells())")
    i_ckpt = body.index("checkpoint_enrolments(enrolled, state, state_path)")
    assert i_stale < i_fast < i_ckpt
