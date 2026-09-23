"""The exit is the third key of a cell type (Tier-1 audit G11).

TRIAL_ALLOCATION.json reported `n_cell_types: 132` over (family x asset class) and nothing else.
`exit_sweep` solves 216 exit arms per sleeve and `exit_study` four; every one is a trial, and the
yield table -- the thing that decides where the next trial goes -- could not tell a trailing stop
from a fixed target. What is pinned: the exit CLASS is read off the params the queue already
carries, it is a third key everywhere the cell type is a key, the class axis still sums to what
it did, and the coarse vocabulary is deliberate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import trial_allocator as ta  # noqa: E402

Y = ta.CellYield


# --------------------------------------------------------------------------- the classifier
@pytest.mark.parametrize("params,expect", [
    ({"runner_trail_k": 1.5, "rr": 2.0}, "trail"),
    ({"breakeven_at_r": 1.0}, "trail"),
    ({"bank_frac": 0.5, "ttl_bars": 24}, "partial"),
    ({"tp2": 1.0}, "partial"),
    ({"rr": 2.0, "wait_bars": 12}, "target_rr"),
    ({"true_break_tp_atr": 2.0}, "target_rr"),
    ({"ttl_bars": 12}, "time_only"),
    ({"horizon": 8, "band": [0.9, 1.0]}, "time_only"),
    ({"feature": "spread", "side": 1}, "unnamed"),
    ({}, "unnamed"),
    (None, "unnamed"),
    ("not a dict", "unnamed"),
])
def test_the_exit_class_is_read_off_the_params_the_queue_already_carries(params, expect) -> None:
    assert ta.exit_rule_of(params) == expect


def test_a_trail_beats_a_target_when_a_cell_carries_both() -> None:
    """A cell with a trail AND a target is a trail cell: the trail is what closes it."""
    assert ta.exit_rule_of({"rr": 2.0, "ttl_bars": 24, "trail_atr": 1.0}) == "trail"
    assert ta.exit_rule_of({"rr": 2.0, "ttl_bars": 24}) == "target_rr"
    assert ta.exit_rule_of({"ttl_bars": 24}) == "time_only"


def test_the_vocabulary_is_coarse_on_purpose() -> None:
    """Keying on `rr=2.0` rather than `target_rr` would make almost every cell type a singleton:
    the shrinkage would never leave the pooled prior and the table would stop being evidence."""
    assert len(ta.EXIT_RULES) == 5 and ta.UNNAMED_EXIT in ta.EXIT_RULES
    assert ta.exit_rule_of({"rr": 2.0}) == ta.exit_rule_of({"rr": 3.5}) == "target_rr"


# --------------------------------------------------------------------------- the key
def test_the_cell_type_key_carries_the_exit() -> None:
    y = Y("overnight_gap_decay", "fx_exotic", 122, 18, exit_rule="trail")
    assert y.key == ("overnight_gap_decay", "fx_exotic", "trail")
    assert y.as_dict()["exit_rule"] == "trail"
    # A caller that has not been taught the axis builds the row it always did.
    assert Y("f", "c", 1, 0).key == ("f", "c", ta.UNNAMED_EXIT)


def test_two_exits_of_one_family_are_two_cell_types_with_their_own_yields(tmp_path) -> None:
    """The whole point: a family whose certificates all come from ONE exit must stop reading as
    a family that works."""
    rows = []
    for i in range(120):
        rows.append({"canonical_cell": f"EURUSD.overnight_gap_decay.p={i}",
                     "family": "overnight_gap_decay", "canonical_verdict": "REJECTED",
                     "params": {"ttl_bars": 8}})
    for i in range(40):
        rows.append({"canonical_cell": f"EURUSD.overnight_gap_decay.t={i}",
                     "family": "overnight_gap_decay",
                     "canonical_verdict": "PASSED" if i < 18 else "REJECTED",
                     "params": {"ttl_bars": 8, "runner_trail_k": 1.5}})
    q = tmp_path / "research_queue.json"
    q.write_text(json.dumps(rows), "utf-8")

    ys = ta.observed(q)
    by_exit = {y.exit_rule: y for y in ys}
    assert set(by_exit) == {"time_only", "trail"}, [y.key for y in ys]
    assert by_exit["time_only"].tried == 120 and by_exit["time_only"].certified == 0
    assert by_exit["trail"].tried == 40 and by_exit["trail"].certified == 18
    assert by_exit["trail"].lower > by_exit["time_only"].lower, (
        "the exit that certifies must outrank the exit that does not, inside one family")
    # Ordering puts the paying exit first, and both keys are distinct.
    assert ys[0].key == by_exit["trail"].key
    assert len({y.key for y in ys}) == 2


def test_the_asset_class_axis_still_sums_over_the_new_key(tmp_path) -> None:
    """`class_weights` is what every generator actually calls; adding a key must not change
    what it answers about a class."""
    ys = [Y("f", "equity", 100, 1, exit_rule="trail"),
          Y("f", "equity", 100, 1, exit_rule="time_only"),
          Y("g", "fx_exotic", 100, 9, exit_rule="target_rr")]
    cls = ta.class_weights(ys)
    assert set(cls) == {"equity", "fx_exotic"}
    assert abs(sum(cls.values()) - 1.0) < 1e-9
    assert cls["fx_exotic"] > cls["equity"] / 2, "the paying class still outranks per cell type"

    ex = ta.exit_weights(ys)
    assert set(ex) == {"trail", "time_only", "target_rr"}
    assert abs(sum(ex.values()) - 1.0) < 1e-9
    assert ex["target_rr"] > ex["trail"], "the exit that certified must hold the larger share"


def test_the_report_publishes_the_exit_axis(tmp_path, monkeypatch) -> None:
    rows = [{"canonical_cell": "EURUSD.carry.p=1", "family": "carry",
             "canonical_verdict": "PASSED", "params": {"rr": 2.0}},
            {"canonical_cell": "EURUSD.carry.p=2", "family": "carry",
             "canonical_verdict": "REJECTED", "params": {"ttl_bars": 4}}]
    q = tmp_path / "research_queue.json"
    q.write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(ta, "QUEUE", q)
    monkeypatch.setattr(ta, "REPORT", tmp_path / "TRIAL_ALLOCATION.json")
    rep = ta.run()
    assert rep["n_cell_types"] == 2
    assert set(rep["exit_rules_seen"]) == {"target_rr", "time_only"}
    assert abs(sum(rep["exit_weights"].values()) - 1.0) < 1e-9
    written = json.loads((tmp_path / "TRIAL_ALLOCATION.json").read_text("utf-8"))
    assert written["cell_type_yield"][0]["exit_rule"] in ("target_rr", "time_only")
    assert written["exit_weights"] == rep["exit_weights"]
