"""experiment_ledger.lifetime: each cell identity is charged ONCE, at the max of its charges.

The audit of 2026-09-30 found a donated cell charged at MINT (its discovery file's `tests_run`)
and again when JUDGED (the hypothesis graph), and a re-donated cell charged once per file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.research import experiment_ledger as el
from libs.research import hypothesis_graph as hg


def _cell(sym: str, fam: str = "fx_fixing_reversal", **p: Any) -> dict[str, Any]:
    return {"symbol": sym, "family": fam, "params": {"fix_hour": 3, **p}}


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: list[dict[str, Any]],
           judged: list[dict[str, Any]], born: list[dict[str, Any]] = ()) -> None:
    seat = tmp_path / "data" / "intelligence" / "seat"
    seat.mkdir(parents=True)
    for k, doc in enumerate(files):
        (seat / f"discoveries_{k}.json").write_text(json.dumps(doc), "utf-8")
    cur = {hg.node_id(c["symbol"], c["family"], c["params"]):
           {"family": c["family"], "fate": "FAILED"} for c in judged}
    cur.update({hg.node_id(c["symbol"], c["family"], c["params"]):
                {"family": c["family"], "fate": "BORN"} for c in born})

    class _G:
        def current(self) -> dict[str, dict[str, Any]]:
            return cur

    monkeypatch.setattr(el, "DESK", tmp_path)
    monkeypatch.setattr(hg, "Graph", _G)
    monkeypatch.setattr(el, "_prereg_counts", lambda: 0)


def test_a_minted_then_judged_cell_is_charged_once(tmp_path, monkeypatch):
    a, b, c = _cell("USDCNH"), _cell("USDINR"), _cell("USDJPY")
    _setup(tmp_path, monkeypatch, [{"tests_run": 3, "discoveries": [a, b, c]}], judged=[a, b])
    doc = el.lifetime(write=False)
    assert doc["judged_cells"] == 2 and doc["screened_cells"] == 3
    assert doc["duplicate_charges_removed"] == 2 and doc["identities_charged_twice"] == 2
    assert doc["lifetime_trials"] == 3                       # three identities, three trials
    assert doc["by_family"]["fx_fixing_reversal"] == 3


def test_a_re_donated_cell_takes_the_max_never_the_sum(tmp_path, monkeypatch):
    a = _cell("USDCNH")
    files = [{"tests_run": 1, "discoveries": [a]},
             {"tests_run": 5, "discoveries": [{**a, "n_trials": 5}]}]
    _setup(tmp_path, monkeypatch, files, judged=[a])
    doc = el.lifetime(write=False)
    assert doc["duplicate_charges_removed"] == 2             # 1 + 5 + 1 judged -> max 5
    assert doc["lifetime_trials"] == 5


def test_screened_but_unidentified_trials_stay_charged_in_full(tmp_path, monkeypatch):
    """A file's culled count has no identity to collide with: only the rows it names can."""
    a = _cell("USDCNH")
    _setup(tmp_path, monkeypatch,
           [{"tests_run": 1000, "discoveries": [a, {"family": "carry"}]}], judged=[a])
    doc = el.lifetime(write=False)
    assert doc["duplicate_charges_removed"] == 1
    assert doc["lifetime_trials"] == 1000                    # 1000 screened, a judged once more


def test_a_row_is_charged_only_out_of_what_its_file_paid(tmp_path, monkeypatch):
    """A file that paid 0 trials charged nothing at mint, so judging its row is the only charge."""
    a = _cell("USDCNH")
    _setup(tmp_path, monkeypatch, [{"tests_run": 0, "discoveries": [a]}], judged=[a])
    doc = el.lifetime(write=False)
    assert doc["duplicate_charges_removed"] == 0 and doc["lifetime_trials"] == 1


def test_born_is_not_judged_and_distinct_identities_never_collide(tmp_path, monkeypatch):
    a, a2 = _cell("USDCNH"), _cell("USDCNH", fix_align="start")
    _setup(tmp_path, monkeypatch, [{"tests_run": 2, "discoveries": [a, a2]}],
           judged=[a2 | {"params": {"fix_hour": 4}}], born=[a])
    doc = el.lifetime(write=False)
    assert doc["duplicate_charges_removed"] == 0
    assert doc["lifetime_trials"] == 3


def test_no_identity_is_ever_charged_below_its_largest_charge(tmp_path, monkeypatch):
    rows = [_cell(s) for s in ("USDCNH", "USDINR", "USDKRW")]
    files = [{"tests_run": 3, "discoveries": rows}, {"tests_run": 3, "discoveries": rows}]
    _setup(tmp_path, monkeypatch, files, judged=rows)
    doc = el.lifetime(write=False)
    # three identities, each charged 1 at two mints and 1 at judgement: once each
    assert doc["lifetime_trials"] == 3
    assert doc["lifetime_trials"] >= max(doc["judged_cells"], doc["screened_cells"] // 2)
