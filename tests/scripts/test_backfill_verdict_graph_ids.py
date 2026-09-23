"""The one-off join between the gate ledger's cell names and the graph's node ids.

THE DEFECT (measured 2026-09-17 on this box). 3,361 distinct cells in
`gate_verdict_ledger.jsonl` are named `EURAUD.overnight_gap_decay.p=<sha of params>`; the
hypothesis graph names the same rules by `node_id`. Nothing joined them, so every trial the moat
registry recorded hung off an id no candidate has. New verdict rows carry `graph_id`; these are
the 3,361 already written, and this script is how they are read back.

Pinned here: a cell whose spec the graph holds resolves to the id the GRAPH wrote (not to a
formula repeated in the script), a cell whose parameters are recoverable from its own string
resolves without the graph, a cell that is neither is NAMED as unresolved rather than counted as
a zero (L1.28a), and `--dry-run` writes nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "scripts"), str(_ROOT / "desks" / "mt5")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import backfill_verdict_graph_ids as bf  # noqa: E402
from research.frontier_identity import cell_id  # noqa: E402

from libs.research import hypothesis_graph as hg  # noqa: E402

SPEC = {"sym": "EURAUD", "family": "overnight_gap_decay", "params": {"hold_bars": 4}}


def _write(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _graph(tmp_path: Path, specs: list[dict]) -> Path:
    rows = []
    for s in specs:
        node = hg.Node(symbol=str(s["sym"]), family=str(s["family"]), params=dict(s["params"]),
                       source="miner:test", parent="seed", seed_key="seed")
        rows.append(node.to_row())
    return _write(tmp_path / "hypothesis_graph.jsonl", rows)


def _ledger(tmp_path: Path, cells: list[str]) -> Path:
    return _write(tmp_path / "gate_verdict_ledger.jsonl",
                  [{"at": "2026-09-16T00:00:00+00:00", "cell": c, "passed": False,
                    "terminal_gate": "deflated_sharpe"} for c in cells])


def test_a_cell_the_graph_holds_resolves_to_the_id_the_graph_wrote(tmp_path: Path) -> None:
    graph = _graph(tmp_path, [SPEC])
    ledger = _ledger(tmp_path, [cell_id(SPEC)])
    doc = bf.build(graph, ledger)
    written = json.loads(graph.read_text("utf-8").splitlines()[0])
    assert doc["graph_ids"][cell_id(SPEC)] == written["id"] == hg.node_id_for_spec(SPEC)
    assert doc["by_method"] == {"graph_row": 1} and doc["n_resolved"] == 1
    assert doc["n_unresolved"] == 0 and doc["unresolved_named"] == []


def test_a_parseable_cell_resolves_with_no_graph_row_at_all(tmp_path: Path) -> None:
    """Two spellings whose whole parameter set IS recoverable from the cell string: an empty
    params digest, and the legacy `rr=/wb=` short form."""
    empty = cell_id({"sym": "XAUUSD", "family": "carry", "params": {}})
    legacy = cell_id({"sym": "GBPJPY", "family": "session_range_breakout",
                      "params": {"rr": 2.0, "wait_bars": 8}})
    doc = bf.build(_graph(tmp_path, []), _ledger(tmp_path, [empty, legacy]))
    assert doc["graph_ids"][empty] == hg.node_id("XAUUSD", "carry", {})
    assert doc["graph_ids"][legacy] == hg.node_id("GBPJPY", "session_range_breakout",
                                                  {"rr": 2.0, "wait_bars": 8})
    assert doc["by_method"] == {"empty_params": 1, "rr_wb": 1}


def test_an_unparseable_cell_is_named_not_counted_as_a_zero(tmp_path: Path) -> None:
    dead = "Honeywell.discovered.p=11835059c639ac64"
    doc = bf.build(_graph(tmp_path, [SPEC]), _ledger(tmp_path, [cell_id(SPEC), dead, "junk"]))
    assert doc["n_cells"] == 3 and doc["n_resolved"] == 1
    assert doc["n_unresolved"] == 2 and doc["by_method"]["UNRESOLVED"] == 2
    assert sorted(doc["unresolved_named"]) == sorted([dead, "junk"])
    assert "UNMEASURED" in doc["unresolved_note"]
    assert dead not in doc["graph_ids"], "never guessed: a digest cannot be inverted"


def test_the_chart_suffix_is_dropped_the_way_node_id_already_drops_it(tmp_path: Path) -> None:
    """KNOWN LIMIT, pinned so it is a decision rather than a surprise: a cell whose chart rides
    on the ROW shares a node id with the H1 cell of the same parameters."""
    m5 = cell_id({"sym": "XAUUSD", "family": "carry", "params": {}, "timeframe": "M5"})
    assert m5.startswith("XAUUSD@M5.")
    doc = bf.build(_graph(tmp_path, []), _ledger(tmp_path, [m5]))
    assert doc["graph_ids"][m5] == hg.node_id("XAUUSD", "carry", {})


def test_dry_run_writes_nothing_and_a_real_run_writes_the_map(tmp_path: Path, capsys) -> None:
    graph, ledger = _graph(tmp_path, [SPEC]), _ledger(tmp_path, [cell_id(SPEC)])
    out = tmp_path / "gate_verdict_graph_ids.json"
    assert bf.main(["--dry-run", "--graph", str(graph), "--ledger", str(ledger),
                    "--out", str(out)]) == 0
    assert "DRY RUN" in capsys.readouterr().out and not out.exists()
    assert bf.main(["--graph", str(graph), "--ledger", str(ledger), "--out", str(out)]) == 0
    doc = json.loads(out.read_text("utf-8"))
    assert doc["graph_ids"] == {cell_id(SPEC): hg.node_id_for_spec(SPEC)}
    assert doc["n_resolved"] == 1 and doc["graph_rows_read"] == 1


def test_missing_inputs_are_a_measurement_never_a_crash(tmp_path: Path) -> None:
    doc = bf.build(tmp_path / "no-graph.jsonl", tmp_path / "no-ledger.jsonl")
    assert doc["n_cells"] == 0 and doc["n_resolved"] == 0 and doc["graph_rows_read"] == 0
