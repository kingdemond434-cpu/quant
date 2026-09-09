"""The recombination engine's artifacts reach the compiler as RECOMBINANTS, not as their atoms.

MEASURED (Tier-1 audit G12, 2026-09-08): sixty REC-*.json files under data/intelligence/
recombinants, and `miner_candidate_compiler._rows` -- which reads a document's `discoveries` list
or, failing that, every list value -- read their `atoms` list. The per_source table gained four
keys that were survivor CELL NAMES, and the recombination itself was never compiled. This pins
the contract: one `discoveries` row per file, under the engine's own source, carrying the
instrument the atoms were cut from, with every pre-existing field kept.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpha_recombination as ar  # noqa: E402

from research import miner_candidate_compiler as compiler  # noqa: E402

UNIVERSE = {"EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "AUDNZD"}
LEGACY_KEYS = {"id", "atoms", "mechanism_class", "expected_orthogonality", "estimated_edge_bps",
               "source_strategies", "recombination_type", "falsifier", "metadata"}


def _survivors(base: Path) -> None:
    doc = {"survivors": {
        "external.XAUUSD.session_range_breakout.rr=2.0": {
            "sym": "XAUUSD",
            "shadow_spec": {"symbol": "XAUUSD", "family": "session_range_breakout",
                            "trigger": "session_breakout", "regime": "all",
                            "session": "london_am", "horizon": "intraday",
                            "participant": "none", "stop": "atr"}},
        "external.AUDNZD.overnight_gap_decay.gap=0.75": {
            "sym": "AUDNZD",
            "shadow_spec": {"symbol": "AUDNZD", "family": "overnight_gap_decay",
                            "trigger": "overnight_gap", "regime": "low_vol",
                            "session": "asia", "horizon": "hours",
                            "participant": "pension", "stop": "fixed"}},
    }}
    out = base / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc), "utf-8")


def test_every_artifact_carries_one_discovery_row_and_keeps_its_legacy_fields(tmp_path) -> None:
    _survivors(tmp_path)
    recs = ar.run_recombination_pipeline(tmp_path)
    assert recs, "two survivors with distinct atoms must recombine"
    files = sorted((tmp_path / "desks" / "mt5" / "data" / "intelligence"
                    / "recombinants").glob("REC-*.json"))
    # The engine's id hashes ATOM VALUES only, so two recombinants cut from different parents
    # with the same values share a file (pre-existing; not this contract's to change).
    assert len(files) == len({r.id for r in recs})
    for f in files:
        doc = json.loads(f.read_text("utf-8"))
        assert set(doc) >= LEGACY_KEYS, f"{f.name} dropped a pre-existing field"
        assert doc["source"] == ar.SOURCE == "alpha_recombination"
        rows = doc["discoveries"]
        assert isinstance(rows, list) and len(rows) == 1
        row = rows[0]
        assert row["source"] == "alpha_recombination" and row["kind"] == "hypothesis"
        assert row["recombinant_id"] == doc["id"]
        assert set(row["symbols"]) <= {"XAUUSD", "AUDNZD"} and row["symbols"], (
            "the instrument the atoms were cut from must ride on the row, or the compiler files "
            "it NEEDS_SYMBOL_EXTRACTION")
        assert row["testable_claim"] == doc["falsifier"]
        assert doc["mechanism_class"] in row["mechanism_tags"]
        assert "params" not in row, "a recombinant names atoms, not executable parameters"


def test_the_compiler_reads_the_recombinant_and_not_its_atoms(tmp_path) -> None:
    _survivors(tmp_path)
    ar.run_recombination_pipeline(tmp_path)
    f = next((tmp_path / "desks" / "mt5" / "data" / "intelligence"
              / "recombinants").glob("REC-*.json"))
    doc = json.loads(f.read_text("utf-8"))
    rows = compiler._rows(doc)
    assert len(rows) == 1 and rows[0]["source"] == "alpha_recombination"
    assert all("type" not in r or r.get("kind") == "hypothesis" for r in rows), (
        "an atom row (`type`/`value`/`source`=parent cell) leaked into the compiler's intake")
    # The attribution the compiler makes is the engine, never a parent survivor's cell name.
    assert str(rows[0].get("source")).split(":")[0] == "alpha_recombination"


def test_a_recombinant_is_a_deepening_hypothesis_never_an_atom_recipe(tmp_path) -> None:
    _survivors(tmp_path)
    recs = ar.run_recombination_pipeline(tmp_path)
    lib = ar.build_full_atom_library(tmp_path)
    row = ar.discovery_row(recs[0], lib)
    cands, disposition = compiler.compile_row("alpha_recombination", row, UNIVERSE)
    assert disposition != "EXACT_RECIPE"
    # Whatever the prose path decides, nothing here may be attributed to the atoms' parents.
    assert all(str(c.get("source")) == "miner:alpha_recombination" for c in cands)


def test_the_library_remembers_where_atoms_came_from(tmp_path) -> None:
    _survivors(tmp_path)
    lib = ar.build_full_atom_library(tmp_path)
    assert lib.strategy_symbols["external.XAUUSD.session_range_breakout.rr=2.0"] == "XAUUSD"
    assert lib.strategy_families["external.AUDNZD.overnight_gap_decay.gap=0.75"] == \
        "overnight_gap_decay"
    # A recombinant with no library still produces a well-formed row: symbols empty, never wrong.
    recs = ar.RecombinationEngine(lib).generate_orthogonal_recombinants()
    bare = ar.discovery_row(recs[0], None)
    assert bare["symbols"] == [] and bare["source"] == "alpha_recombination"
