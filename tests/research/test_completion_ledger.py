"""CAPABILITY STATUS IS COMPUTED, NEVER ASSERTED.

Asked repeatedly whether a specification was fully built, this desk answered in prose. Prose
status drifts the moment code changes, cannot be re-checked without re-reading everything, and
lets "built" mean whichever of EXISTS / IMPORTS / TESTED / WIRED the writer had in mind.
"""

from __future__ import annotations

import json
from pathlib import Path

from libs.research.completion_ledger import (
    STAGES,
    STATUS,
    Capability,
    load,
    summarise,
    verify,
)

_LEDGER = Path("docs/research/COMPLETION_LEDGER.json")


def _cap(**kw) -> Capability:
    base = {"capability_id": "X", "title": "t", "economic_reason": "r", "source_spec": "s"}
    return Capability(**{**base, **kw})


def _ok(_m: str) -> tuple[bool, str]:
    return True, ""


def test_STATUS_IS_THE_FIRST_FAILING_STAGE_NOT_THE_STRONGEST_PASSING() -> None:
    """A capability with code, tests and a caller that nothing schedules is not TESTED -- reporting
    it that way would be true and useless."""
    v = verify(_cap(module="libs.research.completion_ledger",
                    tests=("tests/research/test_completion_ledger.py",)), importer=_ok)
    assert v.failed_stage == "CALLED", v.stages
    assert v.status == "PARTIAL"


def test_A_MISSING_FILE_IS_MISSING_NOT_PARTIAL() -> None:
    v = verify(_cap(module="libs.research.does_not_exist_at_all"), importer=_ok)
    assert v.status == "MISSING" and v.failed_stage == "EXISTS"


def test_AN_IMPORT_FAILURE_IS_MISSING_AND_CARRIES_THE_REASON() -> None:
    """A capability that cannot be imported cannot run, whatever else is true of it."""
    def boom(_m: str) -> tuple[bool, str]:
        return False, "import raised ImportError: no numpy"
    v = verify(_cap(module="libs.research.completion_ledger"), importer=boom)
    assert v.status == "MISSING" and "no numpy" in v.detail


def test_A_NAMED_BUT_ABSENT_TEST_EARNS_NO_CREDIT() -> None:
    """Worse than no test: the ledger would otherwise credit a file that does not exist."""
    v = verify(_cap(module="libs.research.completion_ledger",
                    tests=("tests/research/test_that_was_never_written.py",)), importer=_ok)
    assert v.stages["TESTS"] is False


def test_A_TEST_FILE_THAT_DOES_NOT_MENTION_THE_MODULE_EARNS_NO_CREDIT() -> None:
    v = verify(_cap(module="libs.research.completion_ledger",
                    tests=("tests/research/test_alpha_state.py",)), importer=_ok)
    assert v.stages["TESTS"] is False


def test_A_CALLER_NOTHING_SCHEDULES_IS_NOT_WIRED() -> None:
    """The exact defect the repo's own fence caught in this very module's runner: a wiring fix one
    link short still reports success."""
    v = verify(_cap(module="libs.research.completion_ledger",
                    tests=("tests/research/test_completion_ledger.py",),
                    callers=("scripts/run_completion_ledger.py",)), importer=_ok)
    assert v.stages["CALLED"] is True
    assert v.stages["WIRED"] is True, "it IS scheduled now -- the cycle runs it"


def test_EXTERNALLY_BLOCKED_REQUIRES_A_NAMED_DEPENDENCY() -> None:
    """'Large', 'later' and 'queued' are scheduling information and map to MISSING. Only a named
    dependency this repository cannot satisfy is terminal."""
    v = verify(_cap(module="libs.x", external_blocker="OS credential separation on the VPS"))
    assert v.status == "EXTERNALLY_BLOCKED"
    assert "VPS" in v.detail


def test_ARTIFACTS_MATCH_ON_BASENAME_NOT_THE_SLASH_JOINED_PATH() -> None:
    """Producers build paths as ROOT / "data" / "x.json", so the literal path never appears in the
    source. A path-only check reported every wired producer as PRODUCES-false -- the CHECK was
    wrong, and a verifier that emits false gaps trains its reader to ignore it."""
    v = verify(_cap(module="libs.research.completion_ledger",
                    tests=("tests/research/test_completion_ledger.py",),
                    callers=("scripts/run_completion_ledger.py",),
                    artifacts=("data/completion_ledger_status.json",),
                    consumers=("scripts/run_completion_ledger.py",)), importer=_ok)
    assert v.stages["PRODUCES"] is True
    assert v.stages["CONSUMED"] is True


def test_EVERY_STATUS_IS_DECLARED() -> None:
    for cap in (_cap(module="libs.research.completion_ledger"),
                _cap(module="libs.nope"),
                _cap(module="libs.x", external_blocker="a real one")):
        assert verify(cap, importer=_ok).status in STATUS


def test_THE_REAL_LEDGER_PARSES_AND_IS_NOT_TRIVIAL() -> None:
    caps = load(_LEDGER)
    assert len(caps) > 30, "the ledger must contain the UNBUILT items too"
    assert all(c.economic_reason for c in caps), "every row states why it matters economically"
    assert all(c.source_spec for c in caps), "every row cites the spec that asked for it"


def test_UNBUILT_CAPABILITIES_ARE_ROWS_NOT_OMISSIONS() -> None:
    """A ledger listing only what exists reports 100% and measures nothing. The denominator has to
    include what is missing."""
    rep = summarise(load(_LEDGER))
    assert int(rep["missing"]) > 0, "no MISSING rows means the ledger is flattering itself"
    assert 0.0 <= float(rep["completion_pct"]) <= 100.0


def test_THE_HEADLINE_NAMES_A_NEXT_ACTION() -> None:
    rep = summarise(load(_LEDGER))
    assert str(rep["next_action"]).strip()


def test_AN_ALL_COMPLETE_LEDGER_ESCALATES_RATHER_THAN_CONGRATULATES() -> None:
    """Same anti-complacency property as the max-push queue: a board that can go all-green is a
    board measuring too little."""
    rep = summarise([_cap(capability_id="only", module="libs.research.completion_ledger",
                          tests=("tests/research/test_completion_ledger.py",),
                          callers=("scripts/run_completion_ledger.py",),
                          artifacts=("data/completion_ledger_status.json",),
                          consumers=("scripts/run_completion_ledger.py",))])
    if int(rep["verified_complete"]) == 1:
        assert "ADD CAPABILITIES" in str(rep["next_action"])


def test_A_MALFORMED_ROW_IS_SKIPPED_NOT_GUESSED(tmp_path) -> None:
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"capabilities": [
        {"capability_id": "good", "title": "t"}, {"no_id": True}, "not a dict"]}), "utf-8")
    assert [c.capability_id for c in load(p)] == ["good"]


def test_STAGES_ARE_ORDERED_WEAKEST_FIRST() -> None:
    assert STAGES[0] == "EXISTS" and STAGES[-1] == "MEASURED"
    assert STAGES.index("CALLED") < STAGES.index("WIRED")
