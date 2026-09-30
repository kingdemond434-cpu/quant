"""The novel-mechanism lane must end at the docket, not in a file nobody reads.

WHAT THIS PINS, AND WHY IT IS WORTH A FILE OF ITS OWN (measured on the trading box 2026-09-24).

A mechanism with no registered family function reaches the judge by exactly one route: the
compiler refuses it as NEEDS_EXACT_RULE_EXTRACTION, `deepening_worker` spends a model call
recovering the rule, and the recovery is re-run through `compile_row`. That is the only way the
Chinese/Japanese/Korean/Russian forests, the championship records, the world crawler and the
arXiv feed can contribute a mechanism the desk did not already know -- everything else the desk
mines is a REGISTERED family being re-parameterised.

The worker wrote `deepened_candidates.json` every pass. `merge_hypotheses.SOURCES` -- the tuple
that builds the docket the judge reads -- did not list it. `libs/ops/capability_graph.py`
asserted the edge anyway ("deepened_candidates -> external_gauntlet via compiler merge", with a
comment calling it "a real path"), which is how it stayed invisible: the graph said the lane was
connected and the graph was not the thing doing the connecting.

Cost of the gap, measured: 83 mechanisms recovered in the worker's lifetime, 30 in the preceding
24 hours, each bought with the scarcest budget the desk owns -- one account, 1,000 model requests
a day, exhausted by 01:42 UTC -- and not one had ever reached the docket, so not one had ever
been judged.

The two assertions below are deliberately CROSS-MODULE. A test that only checked the literal
string in SOURCES would pass while the worker wrote somewhere else entirely; these read the
worker's own constants, so a rename on either side fails here rather than silently reopening the
hole.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

merge_hypotheses = pytest.importorskip("merge_hypotheses")
deepening_worker = pytest.importorskip("deepening_worker")


def _entry():
    name = deepening_worker.OUT.name
    return name, dict(merge_hypotheses.SOURCES).get(name, "__ABSENT__")


def test_the_worker_output_is_a_docket_source() -> None:
    """The file the worker actually writes must be one the merge actually reads."""
    name, key = _entry()
    assert key != "__ABSENT__", (
        f"{name} is written by deepening_worker but is not in merge_hypotheses.SOURCES, so every "
        "mechanism the model seat recovers dies before the docket. This is the ONLY door a "
        "mechanism with no registered family has.")


def test_the_docket_reads_the_key_the_worker_writes() -> None:
    """A right filename under the wrong key reads as MALFORMED_OR_EMPTY -- silently zero.

    `merge_hypotheses` does `doc.get(key)` and, when that is not a list, records the source as
    MALFORMED_OR_EMPTY and moves on. So a mismatched key fails exactly like an empty file and the
    per-source count reads 0 rather than raising.
    """
    _, key = _entry()
    assert key == "candidates", (
        f"merge_hypotheses reads doc[{key!r}] but deepening_worker writes its rows under "
        "'candidates'; the merge would record MALFORMED_OR_EMPTY and admit nothing.")


def test_a_recovered_row_survives_the_merge_s_own_admission_rules(tmp_path) -> None:
    """The contract, not just the wiring: a recovered row must carry what the merge requires.

    The merge drops any row with no tradeable symbol and any row with no family. Recovered rows
    come out of `compile_row` -- the same function that produces miner_candidates' hypotheses --
    so they are contract-identical by construction, and this asserts that rather than assuming it.
    """
    row = {"symbol": "EURUSD", "family": "carry", "params": {"rr": 1.0},
           "source": "miner:deep_forest", "genome_id": "g1", "mechanism_status": "recovered"}
    doc = {"built_at": "2026-09-24T00:00:00+00:00", "candidates": [row],
           "dispositions": {}, "recovered_this_run": 1}
    p = tmp_path / deepening_worker.OUT.name
    p.write_text(json.dumps(doc), encoding="utf-8")

    _, key = _entry()
    loaded = json.loads(p.read_text("utf-8"))
    rows = loaded if isinstance(loaded, list) else loaded.get(key)
    assert isinstance(rows, list) and rows, "the merge would record MALFORMED_OR_EMPTY"
    got = rows[0]
    assert got.get("symbol"), "no symbol: the merge skips the row before any other check"
    assert got.get("family"), "no family: the merge counts it unrouted and drops it"


def test_the_capability_graph_claim_now_has_something_behind_it() -> None:
    """The graph asserted this edge for longer than the merge implemented it.

    Keeping the assertion honest is the point: an edge the graph names and nothing implements is
    a claim the desk cannot cash (L1.49), and it is worse than a missing edge because it stops
    anyone looking.
    """
    name, _ = _entry()
    graph = (ROOT / "libs" / "ops" / "capability_graph.py").read_text("utf-8", errors="ignore")
    if name not in graph:
        pytest.skip("the capability graph no longer names this artifact")
    assert name in dict(merge_hypotheses.SOURCES), (
        "the capability graph still claims deepened_candidates reaches the gauntlet via the "
        "merge; if that entry is removed from SOURCES the claim must be removed too.")
