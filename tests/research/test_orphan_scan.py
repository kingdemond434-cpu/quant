"""THE EXPENSIVE ORPHANS ARE NOT MODULES.

`dormancy` answers the code question. The costly strandings are further down the chain, where the
desk has already paid for the discovery: a dataset turned into no feature, a hypothesis never
tested, a survivor never portfolio-tested. None of those is visible to an importer count -- the
code works, the artifacts exist, and the chain is broken at a join nobody watches.
"""

from __future__ import annotations

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
    counts = scan(counter=_counter({"data_universe_map.json": 30, "feature_registry.json": 4}))
    first = counts[0]
    assert first.produced == 30 and first.consumed == 4
    assert first.conversion == pytest.approx(4 / 30)
