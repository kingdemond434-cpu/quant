"""experiment_ledger.charge_by_family: a file's trials are charged by what each row cost.

The audit of 2026-09-30 found `_proposer_counts` split a discovery file's `tests_run` evenly over
its DISTINCT families with a floor: a 3-row family paid what a 1-row family paid, and the floor's
remainder was charged to nobody. The charge now follows the rows, and never sums below the file.
"""
from __future__ import annotations

import json

from libs.research import experiment_ledger as el


def _rows(*fams: str) -> list[dict]:
    return [{"family": f} for f in fams]


def test_split_follows_row_counts_and_sums_exactly():
    c = el.charge_by_family(10, _rows("a", "a", "a", "b"))
    assert c == {"a": 8, "b": 2} and sum(c.values()) == 10


def test_floor_remainder_is_charged_never_dropped():
    c = el.charge_by_family(7, _rows("a", "b", "c"))
    assert sum(c.values()) == 7            # the even floor split charged 6


def test_per_row_counts_are_charged_and_total_never_falls_below_the_file():
    c = el.charge_by_family(10, [{"family": "a", "tests_run": 6}, {"family": "b"},
                                 {"family": "b"}])
    assert c == {"a": 6, "b": 4}
    over = el.charge_by_family(5, [{"family": "a", "n_trials": 9}, {"family": "b", "trials": 3}])
    assert over == {"a": 9, "b": 3}         # rows declare more than the file: charge the rows


def test_declared_by_family_wins_and_the_unexplained_rest_is_still_charged():
    c = el.charge_by_family(20, _rows("a"), by_family={"a": 5, "b": 10})
    assert sum(c.values()) == 20 and c["b"] >= 10 and c["a"] >= 5


def test_no_family_charges_the_unknown_bucket():
    assert el.charge_by_family(4, []) == {"?": 4}
    assert el.charge_by_family(0, _rows("a")) == {}


def test_proposer_counts_charge_rows_and_keep_the_total(tmp_path, monkeypatch):
    d = tmp_path / "data" / "intelligence" / "seat"
    d.mkdir(parents=True)
    (d / "discoveries_1.json").write_text(json.dumps(
        {"tests_run": 7, "discoveries": _rows("a", "a", "b")}), "utf-8")
    (d / "discoveries_2.json").write_text(json.dumps(
        {"tests_run": 3, "discoveries": _rows("x", "y")}), "utf-8")
    monkeypatch.setattr(el, "DESK", tmp_path)
    total, by_fam = el._proposer_counts()
    assert total == 10 and sum(by_fam.values()) == total
    assert by_fam["a"] > by_fam["b"]
