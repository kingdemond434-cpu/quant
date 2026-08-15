"""THE EXPENSIVE ORPHANS ARE NOT MODULES.

`dormancy` answers the code question. The costly strandings are further down the chain, where the
desk has already paid for the discovery: a dataset turned into no feature, a hypothesis never
tested, a survivor never portfolio-tested. None of those is visible to an importer count -- the
code works, the artifacts exist, and the chain is broken at a join nobody watches.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research.orphan_scan import STAGES, StageCount, scan, summarise, to_gaps


def _counter(mapping: dict[str, int | None]):
    """Count by artifact path, so a test states a chain without writing artifacts."""
    return lambda p: mapping.get(Path(p).name)


def test_EVERY_STAGE_NAMES_AN_ACTION() -> None:
    """A row nobody can act on is a complaint. The Gap contract refuses one, so a stage without an
    action would blow up at publish time rather than here -- which is too late to be useful."""
    for s in STAGES:
        assert s.action.strip(), s.name
        assert s.why.strip(), s.name


def test_A_MISSING_ARTIFACT_IS_UNMEASURED_NOT_ZERO_CONVERSION() -> None:
    """'Nobody looked' and 'nothing was stranded' are opposite facts, and only one is good news."""
    counts = scan(counter=_counter({}))
    assert all(not c.measured for c in counts)
    assert all(c.conversion is None and c.stranded is None for c in counts)
    gaps = to_gaps(counts)
    assert all(g.current is None and g.gap_fraction == 1.0 for g in gaps)
    assert all("UNMEASURED" in g.detail for g in gaps)


def test_AN_UNWATCHED_JOIN_OUTRANKS_A_BADLY_CONVERTING_ONE() -> None:
    """The desk knows roughly how bad its measured conversion is. It does not know which joins
    nobody watches at all, and that is the more expensive ignorance."""
    watched = StageCount(STAGES[0], produced=100, consumed=5)     # 5% conversion, terrible
    unwatched = StageCount(STAGES[1], produced=100, consumed=None)
    a, b = to_gaps([watched, unwatched])
    assert a.gap_fraction == pytest.approx(0.95)
    assert b.gap_fraction == 1.0 > a.gap_fraction


def test_STRANDED_IS_THE_DIFFERENCE_AND_NEVER_NEGATIVE() -> None:
    """A downstream population can legitimately EXCEED the upstream one -- one feature spawns many
    hypotheses -- and a negative 'stranded' would read as a surplus of nothing."""
    assert StageCount(STAGES[0], 100, 40).stranded == 60
    assert StageCount(STAGES[0], 40, 100).stranded == 0


def test_FAN_OUT_IS_CAPPED_AT_FULL_CONVERSION_NOT_REPORTED_ABOVE_ONE() -> None:
    assert StageCount(STAGES[0], 10, 90).conversion == 1.0


def test_NOTHING_PRODUCED_IS_NOT_A_CONVERSION_FAILURE() -> None:
    """It is an UPSTREAM problem, and the stage above is where it shows up as a real gap. Scoring
    it as 0% here would double-count one defect and point the desk at the wrong join."""
    assert StageCount(STAGES[0], 0, 0).conversion == 1.0


def test_THE_BOTTLENECK_IS_THE_WORST_MEASURED_JOIN() -> None:
    """The bottleneck stage IS the work (L1.53). A report ordered by stage name would bury it."""
    counts = [StageCount(STAGES[0], 100, 90), StageCount(STAGES[1], 100, 10),
              StageCount(STAGES[2], 100, 50)]
    assert summarise(counts)["bottleneck"] == STAGES[1].name


def test_UNWATCHED_JOINS_ARE_NAMED_RATHER_THAN_COUNTED() -> None:
    """A count says how blind the desk is; the names say where. Only the second is actionable."""
    rep = summarise([StageCount(STAGES[0], 10, 5), StageCount(STAGES[1], None, None)])
    assert rep["unwatched"] == [STAGES[1].name]
    assert rep["measured"] == 1


def test_A_FULLY_CONVERTED_CHAIN_STILL_REPORTS_A_BOTTLENECK() -> None:
    """Never 'no bottleneck'. Something is always the least-converted join, and naming it is how
    the desk keeps finding the next gap instead of declaring itself finished."""
    counts = [StageCount(s, 10, 10) for s in STAGES]
    rep = summarise(counts)
    assert rep["bottleneck"] is not None
    assert rep["unwatched"] == []


def test_THE_GAPS_CARRY_THE_STAGE_EVIDENCE_AND_DEPENDENCY() -> None:
    """A triaging human needs to know why the join matters and which artifact feeds it, and the
    ranker does not read either -- so they must travel on the row rather than in a report."""
    g = to_gaps([StageCount(STAGES[0], 100, 20)])[0]
    assert g.evidence == STAGES[0].why
    assert g.dependency == STAGES[0].produced_artifact
    assert "conversion-chain" in g.tags


def test_THE_SCAN_IS_PURE_OVER_ITS_COUNTER() -> None:
    """Testable without artifacts, which is what lets the chain be asserted rather than mocked at
    the filesystem."""
    counts = scan(counter=_counter({"data_universe_map.json": 30, "feature_library.json": 4}))
    first = counts[0]
    assert first.produced == 30 and first.consumed == 4
    assert first.conversion == pytest.approx(4 / 30)


def _write_json(root: Path, relative: str, doc: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), "utf-8")


def _stage(counts: list[StageCount], name: str) -> StageCount:
    return next(count for count in counts if count.stage.name == name)


def test_STAGE_PATHS_ARE_THE_ARTIFACTS_THE_LIVE_PRODUCERS_WRITE() -> None:
    stages = {stage.name: stage for stage in STAGES}
    assert stages["data_to_feature"].consumed_artifact == "data/feature_library.json"
    assert stages["feature_to_hypothesis"].consumed_artifact == "data/hypothesis_queue.jsonl"
    assert stages["recommendation_to_change"].produced_artifact == \
        "docs/research/recommendation_ledger.json"
    assert stages["survivor_to_portfolio"].consumed_artifact == \
        "data/portfolio_admission.json"
    assert stages["failure_to_mining"].consumed_artifact == \
        "data/graveyard_resurrection_queue.json"
    assert stages["near_survivor_to_experiment"].consumed_artifact == \
        "data/hypothesis_queue.jsonl"
    paths = {
        path
        for stage in STAGES
        for path in (stage.produced_artifact, stage.consumed_artifact)
    }
    assert not paths & {
        "data/feature_registry.json",
        "data/hypothesis_ledger.json",
        "data/recommendation_ledger.json",
        "data/portfolio_candidates.json",
        "data/failure_mining.json",
        "data/near_survivor_runs.json",
    }


def test_DOWNSTREAM_POPULATION_CANNOT_HIDE_A_PLANTED_UNCONSUMED_SURVIVOR(
        tmp_path: Path) -> None:
    """Two unrelated rows used to make one survivor read as fully converted by row count alone."""
    identity = "family|trial-a"
    _write_json(tmp_path, "data/full_sweep.json", {
        "survivors": [{"key": ["family", "trial-a"]}],
    })
    _write_json(tmp_path, "data/portfolio_admission.json", {
        "rows": [{"survivor": "other-a"}, {"survivor": "other-b"}],
    })

    planted = _stage(scan(root=tmp_path), "survivor_to_portfolio")
    assert planted.produced == 1
    assert planted.consumed == 0
    assert planted.stranded_ids == (identity,)
    assert planted.conversion == 0.0
    assert identity in to_gaps([planted])[0].detail

    _write_json(tmp_path, "data/portfolio_admission.json", {
        "rows": [{"survivor": identity}],
    })
    cleared = _stage(scan(root=tmp_path), "survivor_to_portfolio")
    assert cleared.consumed == 1
    assert cleared.stranded_ids == ()
    assert cleared.conversion == 1.0


def test_CANONICAL_NESTED_JSON_JSONL_AND_MARKDOWN_SCHEMAS_MATCH_IDENTITIES(
        tmp_path: Path) -> None:
    _write_json(tmp_path, "data/data_universe_map.json", {
        "sources": {
            "market": [{"name": "source-a"}, {"name": "source-b"}],
            "source-c": {"class": "distant-domain", "grade": "catalogued"},
        },
    })
    _write_json(tmp_path, "data/feature_library.json", {
        "features": [{"id": "F1", "name": "feature-one", "source": "source-a"}],
    })
    queue = tmp_path / "data/hypothesis_queue.jsonl"
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text("\n".join([
        json.dumps({"name": "H1", "feature_id": "F1"}),
        json.dumps({"name": "H-near", "parent": "G_COST"}),
    ]) + "\n", "utf-8")
    _write_json(tmp_path, "data/full_sweep.json", {
        "survivors": [{"key": ["H1"]}],
    })
    _write_json(tmp_path, "data/portfolio_admission.json", {
        "rows": [{"survivor": "H1"}],
    })
    _write_json(tmp_path, "docs/research/recommendation_ledger.json", {
        "recommendations": [
            {"id": "R1", "status": "implemented"},
            {"id": "R2", "status": "scheduled"},
            {"id": "R3", "status": "done"},
            {"id": "R4", "status": "screened"},
        ],
    })
    graveyard = tmp_path / "docs/graveyard.md"
    graveyard.parent.mkdir(parents=True, exist_ok=True)
    graveyard.write_text(
        "| Name | Metric | Tags |\n|---|---|---|\n"
        "| Dead-A | x | `cost` |\n| Dead-B | y | `regime` |\n",
        "utf-8",
    )
    _write_json(tmp_path, "data/graveyard_resurrection_queue.json", {
        "entries": [{"name": "Dead-A"}],
    })
    _write_json(tmp_path, "data/research_review.json", {
        "near_survivor_bank": [{"killed_by": "G_COST", "next_experiments": ["slower"]}],
    })

    counts = scan(root=tmp_path)
    data_join = _stage(counts, "data_to_feature")
    assert data_join.produced == 3 and data_join.consumed == 1
    assert data_join.stranded_ids == ("source-b", "source-c")
    feature_join = _stage(counts, "feature_to_hypothesis")
    assert feature_join.produced == 1 and feature_join.consumed == 1
    hypothesis_join = _stage(counts, "hypothesis_to_test")
    assert hypothesis_join.produced == 2 and hypothesis_join.consumed == 1
    assert hypothesis_join.stranded_ids == ("H-near",)
    recommendation_join = _stage(counts, "recommendation_to_change")
    assert recommendation_join.produced == 4 and recommendation_join.consumed == 3
    assert recommendation_join.stranded_ids == ("R2",)
    assert _stage(counts, "survivor_to_portfolio").conversion == 1.0
    failure_join = _stage(counts, "failure_to_mining")
    assert failure_join.produced == 2 and failure_join.consumed == 1
    assert failure_join.stranded_ids == ("Dead-B",)
    assert _stage(counts, "near_survivor_to_experiment").conversion == 1.0


def test_PRESENT_BUT_WRONG_SCHEMA_IS_UNMEASURED_NOT_EMPTY(tmp_path: Path) -> None:
    _write_json(tmp_path, "data/full_sweep.json", {"survivors": {"not": "a list"}})
    _write_json(tmp_path, "data/portfolio_admission.json", {"rows": []})
    count = _stage(scan(root=tmp_path), "survivor_to_portfolio")
    assert not count.measured
    assert count.produced is None
    assert count.conversion is None


def test_CORRUPT_JSONL_REFUSES_PARTIAL_IDENTITY_EVIDENCE(tmp_path: Path) -> None:
    _write_json(tmp_path, "data/feature_library.json", {
        "features": [{"id": "F1", "name": "feature-one"}],
    })
    path = tmp_path / "data/hypothesis_queue.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"name":"valid","feature_id":"F1"}\n{broken\n', "utf-8")
    count = _stage(scan(root=tmp_path), "feature_to_hypothesis")
    assert not count.measured
    assert count.produced == 1
    assert count.consumed is None
