"""The named refusal ledger: a batch budget may truncate, it may not discard silently."""
from __future__ import annotations

import json
from pathlib import Path

from libs.research import set_aside as sa


def test_take_returns_the_same_slice_and_never_shrinks_the_budget(tmp_path: Path) -> None:
    rows = list(range(100))
    kept = sa.take(rows, 40, organ="o", stage="s", ordering="-x",
                   path=tmp_path / "L.json")
    assert kept == rows[:40]


def test_the_remainder_is_named_not_dropped(tmp_path: Path) -> None:
    p = tmp_path / "L.json"
    sa.take(list(range(900)), 40, organ="alpha_lineage_search", stage="untried_mutations",
            ordering="-len(untried), -n_nodes", pass_id="P1", path=p)
    doc = json.loads(p.read_text(encoding="utf-8"))
    row = doc["rows"][-1]
    assert (row["organ"], row["stage"], row["considered"], row["kept"], row["set_aside"]) == (
        "alpha_lineage_search", "untried_mutations", 900, 40, 860)
    assert row["ordering"] == "-len(untried), -n_nodes" and row["pass"] == "P1"
    assert doc["set_aside_total"] == 860
    assert doc["totals"]["alpha_lineage_search/untried_mutations"]["passes"] == 1


def test_totals_accumulate_across_passes_and_zero_passes_leave_no_row(tmp_path: Path) -> None:
    p = tmp_path / "L.json"
    sa.take(list(range(10)), 4, organ="o", stage="s", ordering="k", path=p)
    sa.take(list(range(10)), 4, organ="o", stage="s", ordering="k", path=p)
    sa.take(list(range(3)), 4, organ="o", stage="s", ordering="k", path=p)  # nothing set aside
    doc = json.loads(p.read_text(encoding="utf-8"))
    t = doc["totals"]["o/s"]
    assert (t["passes"], t["considered"], t["kept"], t["set_aside"]) == (3, 23, 11, 12)
    assert len(doc["rows"]) == 2, "a pass that set nothing aside is counted, not illustrated"


def test_an_unwritable_ledger_never_takes_down_the_organ(tmp_path: Path) -> None:
    bad = tmp_path / "file.json" / "nested" / "L.json"
    (tmp_path / "file.json").write_text("not a directory", encoding="utf-8")
    assert sa.take([1, 2, 3], 2, organ="o", stage="s", ordering="k", path=bad) == [1, 2]
    assert sa.note("o", "s", kept=1, considered=9, ordering="k", path=bad) is None


def test_read_of_an_absent_ledger_is_unmeasured_not_zero(tmp_path: Path) -> None:
    doc = sa.read(tmp_path / "absent.json")
    assert doc["at"] is None and doc["totals"] == {} and doc["rows"] == []
