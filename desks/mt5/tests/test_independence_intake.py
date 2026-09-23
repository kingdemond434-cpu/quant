"""INDEPENDENCE AT INTAKE: the order, the mix and the grid, and that none of them reduces."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import independence_intake as ii  # noqa: E402
from research import judge_coverage as jc  # noqa: E402
from research import survivor_distiller as sd  # noqa: E402


def _row(fam: str, sym: str, hor: str, seen: str, cell: str) -> dict[str, Any]:
    return {"family": fam, "symbol": sym, "horizon": hor, "first_seen": seen, "_cell": cell}


def test_grid_cell_is_the_key_the_yield_fence_weighs() -> None:
    assert jc.grid_cell({"family": "Carry", "symbol": "EURUSD", "horizon": "Sub_4h"}) == \
        "carry|eurusd|sub_4h"
    assert jc.grid_cell({}) == "?|?|?"
    assert jc.grid_cell({"family": "carry", "sym": "xauusd",
                         "params": {"horizon": "h1"}}) == "carry|xauusd|h1"


def test_variants_are_charged_against_their_parent_and_nothing_is_dropped() -> None:
    rows = [_row("carry", "eurusd", "sub_4h", "2026-09-01", "a"),
            _row("carry", "eurusd", "sub_4h", "2026-09-02", "b"),
            _row("carry", "eurusd", "sub_4h", "2026-09-03", "c"),
            _row("carry", "xauusd", "sub_4h", "2026-09-04", "d")]
    split = jc.variant_split(rows, {"a", "b", "c", "d"})
    assert split["rows"] == 4
    assert split["unseen_mechanisms"] == 2 and split["variants"] == 2
    assert split["distinct_grid_cells"] == 2
    # the OLDEST row on a cell is its mechanism; the later ones are its variants
    assert [r["_variant"] for r in rows] == [0, 1, 1, 0]


def test_the_order_ranks_an_unseen_mechanism_above_a_variant_and_keeps_every_row() -> None:
    rows = [_row("carry", "eurusd", "sub_4h", "2026-09-01", "a"),
            _row("carry", "eurusd", "sub_4h", "2026-09-02", "b"),
            _row("carry", "xauusd", "sub_4h", "2026-09-03", "c")]
    ids = {"a", "b", "c"}
    jc.variant_split(rows, ids)
    after = jc.coverage_order(rows, {"carry": 3}, ids)
    before = jc.coverage_order(rows, {"carry": 3}, ids, demote_variants=False)
    assert len(after) == len(before) == 3          # nothing dropped, the queue is uncapped
    assert [r["_cell"] for r in after] == ["a", "c", "b"]
    assert [r["_cell"] for r in before] == ["a", "b", "c"]
    assert jc._unseen_in_prefix(after, 2) - jc._unseen_in_prefix(before, 2) == 1


def test_the_dedup_ladder_reports_each_rung_and_its_collapse() -> None:
    rows = [("carry", "eurusd", "sub_4h", "h1", "carry trade"),
            ("carry", "eurusd", "sub_4h", "h2", "carry trade"),
            ("carry", "eurusd", "sub_4h", "h3", "carry trade"),
            ("breakout", "xauusd", "sub_1d", "h4", "range break")]
    lad = ii.dedup_ladder(rows)
    assert lad["available"] and lad["raw_cells"] == 4
    assert lad["content_hashes"] == 4 and lad["grid_cells"] == 2 and lad["mechanisms"] == 2
    assert lad["collapse"]["raw_per_grid_cell"] == 2.0
    assert ii.dedup_ladder([])["available"] is False


def test_grid_occupancy_publishes_empty_cells_as_targets(monkeypatch: Any) -> None:
    monkeypatch.setattr(ii, "_axes", lambda: (["eurusd", "xauusd"], ["carry", "breakout"],
                                              ["sub_4h", "sub_1d", "unknown"], {}))
    rows = [("carry", "eurusd", "sub_4h", "h1", "m"), ("breakout", "xauusd", "sub_1d", "h2", "m")]
    grid = ii.grid_occupancy(rows)
    assert grid["available"] and grid["nominal_cells"] == 2 * 2 * 3
    assert grid["occupied_cells"] == 2
    assert grid["occupancy"] == pytest.approx(2 / 12, abs=1e-5)
    cells = {t["cell"] for t in grid["targets"]}
    assert "carry|xauusd|sub_4h" in cells          # reachable: both axes already productive
    assert not any(t["horizon"] == "unknown" for t in grid["targets"])


def test_the_mechanism_share_is_tuned_by_measured_gain_two_sided_and_bounded(
        tmp_path: Path) -> None:
    mix = tmp_path / "mix.json"
    assert ii.declared_mechanism_share(mix) == ii.DEFAULT_MECHANISM_SHARE
    up = ii.tune_mix({"mechanism": 0.9, "parameter": 0.1}, mix)
    assert up["declared_mechanism_share"] > ii.DEFAULT_MECHANISM_SHARE
    down = ii.tune_mix({"mechanism": 0.05, "parameter": 0.95}, mix)
    assert down["declared_mechanism_share"] < up["declared_mechanism_share"]
    for _ in range(20):                            # it can never leave its two-sided bounds
        down = ii.tune_mix({"mechanism": 0.0, "parameter": 1.0}, mix)
    assert ii.SHARE_BOUNDS[0] <= down["declared_mechanism_share"] <= ii.SHARE_BOUNDS[1]


def test_an_unmeasured_gain_leaves_the_declared_share_exactly_where_it_was(
        tmp_path: Path) -> None:
    mix = tmp_path / "mix.json"
    ii.tune_mix({"mechanism": 0.9, "parameter": 0.1}, mix)
    was = ii.declared_mechanism_share(mix)
    doc = ii.tune_mix({"available": False, "why": "UNMEASURED: nothing stamped"}, mix)
    assert doc["declared_mechanism_share"] == pytest.approx(was)


def test_orthogonality_gain_reads_the_operator_stamp_the_distiller_writes() -> None:
    rows = [("carry", "eurusd", "sub_4h", "h1", "carry (mutation: step_band_up)"),
            ("carry", "eurusd", "sub_4h", "h2", "carry (mutation: step_band_down)"),
            ("carry", "xauusd", "sub_1d", "h3", "carry (mutation: condition_on_state)")]
    gain = ii.orthogonality_gain(rows)
    assert gain["available"] and gain["mechanism"] == 1.0 and gain["parameter"] == 0.5
    assert ii.orthogonality_gain([])["available"] is False


def test_mechanism_class_names_the_moves_that_change_the_mechanism() -> None:
    assert ii.mechanism_class("condition_on_state") == "mechanism"
    assert ii.mechanism_class("cross_horizon") == "mechanism"
    assert ii.mechanism_class("step_band_up") == "parameter"
    assert ii.mechanism_class(None) == "parameter"


def _move(op: str, score: float, ident: str, fam: str = "carry",
          sym: str = "EURUSD") -> tuple[dict[str, Any], str]:
    return ({"operator": op, "score": score, "id": ident, "family": fam, "symbol": sym}, "why")


def test_the_mix_gives_the_declared_share_to_mechanism_moves_and_drops_nothing(
        tmp_path: Path, monkeypatch: Any) -> None:
    mix = tmp_path / "mix.json"
    mix.write_text(json.dumps({"declared_mechanism_share": 0.5}), encoding="utf-8")
    monkeypatch.setattr(ii, "MIX", mix)
    monkeypatch.setattr(ii, "OUT", tmp_path / "absent.json")
    pairs = [_move("step_band_up", 9.0 - i, f"p{i}") for i in range(10)]
    pairs += [_move("condition_on_state", 0.1, f"m{i}") for i in range(10)]
    out, rep = sd.mix_by_mechanism(pairs)
    assert len(out) == len(pairs)                  # every move survives; only the order changed
    assert {p[0]["id"] for p in out} == {p[0]["id"] for p in pairs}
    assert rep["available"] and rep["declared_share"] == 0.5
    head = out[:10]
    assert sum(1 for p in head if p[0]["operator"] == "condition_on_state") == 5


def test_empty_grid_cells_go_first_inside_the_mechanism_arm(
        tmp_path: Path, monkeypatch: Any) -> None:
    mix = tmp_path / "mix.json"
    mix.write_text(json.dumps({"declared_mechanism_share": 0.5}), encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"grid": {"targets": [{"family": "carry", "symbol": "xauusd"}]}}),
                      encoding="utf-8")
    monkeypatch.setattr(ii, "MIX", mix)
    monkeypatch.setattr(ii, "OUT", report)
    pairs = [_move("condition_on_state", 9.0, "high", sym="EURUSD"),
             _move("condition_on_state", 0.1, "empty", sym="XAUUSD"),
             _move("step_band_up", 5.0, "p0")]
    out, rep = sd.mix_by_mechanism(pairs)
    # inside the mechanism arm the empty-cell move outranks the higher-scoring occupied one;
    # the parameter move still takes its interleaved slot, because nothing is displaced
    mech_order = [p[0]["id"] for p in out if p[0]["operator"] == "condition_on_state"]
    assert mech_order == ["empty", "high"]
    assert len(out) == 3
    assert rep["empty_cell_targets_hit"] == 1


def test_an_unimportable_or_unmeasured_mix_returns_the_list_untouched(
        tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(ii, "MIX", tmp_path / "absent.json")
    monkeypatch.setattr(ii, "OUT", tmp_path / "absent2.json")
    out, rep = sd.mix_by_mechanism([])
    assert out == [] and rep["available"] is False


def test_the_headline_is_read_from_the_yield_fence_and_never_recomputed(
        tmp_path: Path, monkeypatch: Any) -> None:
    art = tmp_path / "PRODUCER_YIELD.json"
    art.write_text(json.dumps({"cells_owed": {
        "cells_to_judge_per_hour": 227.5, "orthogonal_cells_to_judge_per_hour": 23.4138,
        "orthogonality_weight": 0.1029, "breadth": {"total": 5.1459, "columns": 1132},
        "ratchet": {"orthogonal_cells_to_judge_per_hour_best": 23.4138}}}), encoding="utf-8")
    monkeypatch.setattr(ii, "YIELD", art)
    head = ii.headline()
    assert head["available"] and head["orthogonal_cells_to_judge_per_hour"] == 23.4138
    assert head["effective_rank"] == 5.1459 and head["columns"] == 1132
    monkeypatch.setattr(ii, "YIELD", tmp_path / "absent.json")
    assert ii.headline()["available"] is False


def test_the_leg_is_on_a_clock_and_in_a_layer() -> None:
    from research.hourly_cycle import LEG_DEPARTMENT

    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["independence_intake"] == "meta"
    assert LEG_DEPARTMENT["independence_intake"] == "meta"
