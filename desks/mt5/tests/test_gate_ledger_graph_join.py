"""One cell, one id: a gate verdict must name the graph node of the hypothesis it judged.

THE DEFECT (measured 2026-09-17). `gate_verdict_ledger.jsonl` names a judged cell
`EURAUD.overnight_gap_decay.p=<sha of params>` (`frontier_identity.cell_id`) while
`hypothesis_graph.jsonl` names the same rule `f668ed18...` (`hypothesis_graph.node_id`), and
nothing joined the two -- so `libs/moat/registry.sync_from_desk` recorded 3,361 trials against
cell strings that exist in no graph, and no trial could be attributed to the candidate it tested.
The verdict writer holds the SPEC, which is the only place both names can be computed from one
object, so the join is written there.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import hypothesis_graph as hg  # noqa: E402
from scripts import external_gauntlet as eg  # noqa: E402

SPEC = {"sym": "EURAUD", "family": "overnight_gap_decay", "params": {"hold_bars": 4}}


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(eg, "GATE_LEDGER", tmp_path / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(eg, "GATE_INDEX", tmp_path / "gate_verdict_index.json")
    return tmp_path / "gate_verdict_ledger.jsonl"


def _rows(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]


def _verdict(**kw: object) -> dict:
    v = {"cell": eg.cell_id(SPEC), "sym": SPEC["sym"], "family": SPEC["family"],
         "days": 120, "passed": False, "terminal_gate": "deflated_sharpe"}
    v.update(kw)
    return v


def test_a_new_verdict_row_carries_the_graphs_own_id_for_the_same_spec(ledger: Path,
                                                                      tmp_path: Path) -> None:
    out = eg._append_gate_ledger([_verdict()], [SPEC])
    assert out["appended"] == 1
    row = _rows(ledger)[0]
    assert row["cell"] == eg.cell_id(SPEC) != row["graph_id"], "two names, and both are kept"
    assert row["terminal_gate"] == "deflated_sharpe", "unchanged, as before"

    # THE JOIN IS PROVEN AGAINST THE GRAPH WRITER, not against a formula repeated here: the
    # candidate compiled from this spec and the verdict judged on it must land on ONE id.
    graph = hg.Graph(tmp_path / "graph.jsonl")
    hg.record_candidates([{"symbol": SPEC["sym"], "family": SPEC["family"],
                           "params": SPEC["params"], "source": "miner:test",
                           "source_title": "t", "source_url": "u"}],
                         source="miner_candidate_compiler", graph=graph)
    born = graph.rows()[0]
    assert row["graph_id"] == born["id"] == hg.node_id_for_spec(SPEC)


def test_a_verdict_carrying_its_own_params_needs_no_spec_list(ledger: Path) -> None:
    eg._append_gate_ledger([_verdict(params=SPEC["params"])], None)
    assert _rows(ledger)[0]["graph_id"] == hg.node_id_for_spec(SPEC)


def test_a_cell_whose_spec_is_not_in_hand_is_named_empty_never_guessed(ledger: Path) -> None:
    """UNMEASURED is a verdict (L1.28a): "" says the writer knew about `graph_id` and could not
    resolve this cell, which a reader can tell apart from a row written before the field."""
    eg._append_gate_ledger([_verdict()], [])
    row = _rows(ledger)[0]
    assert row["graph_id"] == "" and "graph_id" in row


def test_the_append_on_change_rule_is_untouched(ledger: Path) -> None:
    assert eg._append_gate_ledger([_verdict()], [SPEC])["appended"] == 1
    assert eg._append_gate_ledger([_verdict()], [SPEC])["appended"] == 0, "same verdict, no row"
    assert eg._append_gate_ledger([_verdict(passed=True, terminal_gate="PASSED")],
                                  [SPEC])["appended"] == 1
    assert len(_rows(ledger)) == 2


def test_a_malformed_spec_cannot_poison_the_map(ledger: Path) -> None:
    """A spec too broken to name must cost that ONE cell its join, never the whole sweep."""
    eg._append_gate_ledger([_verdict()], [{"family": "no_symbol_here"}, SPEC, "not a dict"])
    assert _rows(ledger)[0]["graph_id"] == hg.node_id_for_spec(SPEC)
