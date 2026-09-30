"""experiment_ledger.charge_by_family: a file's trials are charged by what each row cost.

The audit of 2026-09-30 found `_proposer_counts` split a discovery file's `tests_run` evenly over
its DISTINCT families with a floor: a 3-row family paid what a 1-row family paid, and the floor's
remainder was charged to nobody. The TOTAL now follows the rows (`proportional_charge`) and never
sums below the file; each FAMILY's deflation charge (`charge_by_family`) is tightening-only:
max(proportional, even split, union), so no family is ever charged less than either old rule.
"""
from __future__ import annotations

import json

from libs.research import experiment_ledger as el


def _rows(*fams: str) -> list[dict]:
    return [{"family": f} for f in fams]


def test_split_follows_row_counts_and_sums_exactly():
    c = el.proportional_charge(10, _rows("a", "a", "a", "b"))
    assert c == {"a": 8, "b": 2} and sum(c.values()) == 10


def test_floor_remainder_is_charged_never_dropped():
    c = el.proportional_charge(7, _rows("a", "b", "c"))
    assert sum(c.values()) == 7            # the even floor split charged 6


def test_per_row_counts_are_charged_and_total_never_falls_below_the_file():
    c = el.proportional_charge(10, [{"family": "a", "tests_run": 6}, {"family": "b"},
                                 {"family": "b"}])
    assert c == {"a": 6, "b": 4}
    over = el.proportional_charge(5, [{"family": "a", "n_trials": 9}, {"family": "b", "trials": 3}])
    assert over == {"a": 9, "b": 3}         # rows declare more than the file: charge the rows


def test_declared_by_family_wins_and_the_unexplained_rest_is_still_charged():
    c = el.proportional_charge(20, _rows("a"), by_family={"a": 5, "b": 10})
    assert sum(c.values()) == 20 and c["b"] >= 10 and c["a"] >= 5


def test_no_family_charges_the_unknown_bucket():
    assert el.proportional_charge(4, []) == {"?": 4}
    assert el.proportional_charge(0, _rows("a")) == {}


def test_proposer_counts_charge_rows_and_keep_the_total(tmp_path, monkeypatch):
    d = tmp_path / "data" / "intelligence" / "seat"
    d.mkdir(parents=True)
    (d / "discoveries_1.json").write_text(json.dumps(
        {"tests_run": 7, "discoveries": _rows("a", "a", "b")}), "utf-8")
    (d / "discoveries_2.json").write_text(json.dumps(
        {"tests_run": 3, "discoveries": _rows("x", "y")}), "utf-8")
    monkeypatch.setattr(el, "DESK", tmp_path)
    total, by_fam = el._proposer_counts()
    assert total == 10                     # each trial counted once in the lifetime total
    # each family is charged its file's whole union (tightening-only)
    assert by_fam == {"a": 7, "b": 7, "x": 3, "y": 3}


def test_family_charge_is_tightening_only_in_a_mixed_file():
    """The audit's case: 101,000 screened, a 100-row family beside a 1-row family. The even
    split charged each 50,500; the proportional split charged the minority 1,000 -- a LOWER
    deflation charge. The family charge is max(new, old, union): never below either rule."""
    rows = _rows(*(["major"] * 100 + ["minor"]))
    new = el.proportional_charge(101_000, rows)
    assert new == {"major": 100_000, "minor": 1_000}
    old = el._even_split(101_000, rows)
    assert old == {"major": 50_500, "minor": 50_500}
    got = el.charge_by_family(101_000, rows)
    assert got == {"major": 101_000, "minor": 101_000}
    for f in got:
        assert got[f] >= new[f] and got[f] >= old[f]


def test_family_charge_never_below_declared_or_row_counts():
    over = el.charge_by_family(5, [{"family": "a", "n_trials": 9}, {"family": "b", "trials": 3}])
    assert over == {"a": 12, "b": 12}      # union = the 12 the rows declare, above the file's 5
    dec = el.charge_by_family(20, _rows("a"), by_family={"a": 5, "b": 10, "c": 0})
    assert dec == {"a": 20, "b": 20}       # a declared family with no row is still charged
    assert el.charge_by_family(4, []) == {"?": 4}
    assert el.charge_by_family(0, _rows("a")) == {}
