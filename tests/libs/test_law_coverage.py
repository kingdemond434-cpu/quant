"""EVERY LAW ENFORCED -- desk-wide, in every interaction, now and for laws added later.

THE HARD HALF IS "LATER". A one-time audit of twenty-five principles is a snapshot: the
twenty-sixth lands next week with no enforcement and nothing notices, because nothing was watching
for it. So enforcement coverage is a measured fraction with a high-water mark, and a new principle
defaults to UNENFORCED -- which drops the live percentage below the mark and fails the audit. That
default is the entire mechanism; without it "and upcoming always" is an intention rather than code.

TWO MODES, DELIBERATELY NOT INTERCHANGEABLE. Mechanical cover is a registered check that can go
red: it constrains what gets DONE. Interactional cover is presence in the preamble every organ
injects: it constrains what gets PROPOSED. A law with only the second is not fully enforced,
because a model that ignores the preamble produces a bad recommendation and nothing catches it.

AND THE MAP IS VERIFIED, NEVER TRUSTED. Naming a check that is not registered would report a law
as covered while nothing fires -- the failure four consecutive charters shipped with before
check_registry_complete existed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.max_audit as M

from libs.doctrine.constitution import OBJECTIVE_PREAMBLE, PRINCIPLES
from libs.doctrine.enforcement import ENFORCEMENT, PREAMBLE_MARKERS, coverage, unenforced


def _registered() -> set[str]:
    return {name for name, _ in M.CHECKS}


# ------------------------------------------------------------------ the live state


def test_no_principle_is_completely_unenforced() -> None:
    """A law nothing can detect a violation of is not a law. This is the floor: every principle
    must have at least one of the two modes."""
    dark = [r for r in coverage(_registered())["rows"] if r["mode"] == "NONE"]
    assert dark == [], [f"{r['id']} {r['name']}" for r in dark]


def test_no_law_claims_enforcement_by_an_unregistered_check() -> None:
    """A phantom entry is worse than an empty one: it reports the law as covered while nothing
    fires. An unregistered check is a law the desk BELIEVES it is enforcing."""
    assert coverage(_registered())["phantom"] == []


def test_the_map_covers_every_principle_including_ones_added_later() -> None:
    """A principle absent from the map is invisible to the whole mechanism -- it would not even
    be counted as a gap. Missing IS the failure mode, so it is checked directly."""
    missing = sorted({p.id for p in PRINCIPLES} - set(ENFORCEMENT))
    assert missing == [], f"principles with no enforcement entry: {missing}"


def test_every_principle_has_a_preamble_marker_declared() -> None:
    """Even an empty marker is a declaration -- it says 'this law is NOT carried into model
    interactions', which is a fact worth stating. A missing key is silence."""
    missing = sorted({p.id for p in PRINCIPLES} - set(PREAMBLE_MARKERS))
    assert missing == [], f"principles with no preamble marker declared: {missing}"


@pytest.mark.parametrize("pid", [p.id for p in PRINCIPLES])
def test_declared_preamble_markers_are_actually_present(pid: str) -> None:
    """Checked against the LIVE preamble rather than asserted, so an edit that drops a clause
    surfaces as lost interactional cover instead of passing silently. Parametrised so a failure
    names the law."""
    marker = PREAMBLE_MARKERS[pid]
    if not marker:
        pytest.skip(f"{pid} declares no interactional cover")
    assert marker in OBJECTIVE_PREAMBLE, (
        f"{pid} claims interactional cover via '{marker}' but the preamble no longer contains it")


def test_coverage_is_reported_in_both_modes_separately() -> None:
    """Collapsing them would let interactional-only cover count as done, and a model that ignores
    the preamble is not constrained by it at all."""
    c = coverage(_registered())
    assert c["mechanical_pct"] <= 100.0 and c["interactional_pct"] <= 100.0
    assert c["full_pct"] <= min(c["mechanical_pct"], c["interactional_pct"])
    assert "constrains what gets PROPOSED" in c["note"]


# ------------------------------------------------------------------ the gaps are honest


def test_the_remaining_gaps_state_what_would_close_them() -> None:
    """An empty entry must be an argued declaration, not an oversight. P1 needs EVIG wired into
    the funnel's ordering; P16 needs a second sleeve to exist at all."""
    src = Path("libs/doctrine/enforcement.py").read_text("utf-8")
    gaps = list(unenforced(_registered()))
    for r in gaps:
        assert f'"{r["id"]}": ()' in src, f"{r['id']} is a gap but has no empty-tuple declaration"
    # There are currently NO gaps -- P1 closed when EVIG was wired into the funnel's ordering and
    # P16 when the coexistence organ landed. The assertion is written to hold in both worlds: an
    # empty gap list is the goal, and any future gap must be a DECLARED empty tuple rather than an
    # oversight, because a plausible-looking check name would report the law as covered while
    # nothing fires.
    if gaps:
        assert "GENUINELY UNENFORCED" in src


def test_gaps_are_ranked_worst_first_and_then_by_aggression() -> None:
    """An unenforced principle at aggression 10 is a law the desk considers maximally binding and
    cannot detect a violation of. Ranking gaps together would let the loudest wait behind quiet
    ones."""
    gaps = unenforced(_registered())
    if len(gaps) > 1:
        modes = [g["mode"] for g in gaps]
        assert modes == sorted(modes, key=lambda m: m != "NONE")
        aggr = [g["aggression"] for g in gaps if g["mode"] == gaps[0]["mode"]]
        assert aggr == sorted(aggr, reverse=True)


# ------------------------------------------------------------------ the ratchet


def test_a_new_unenforced_principle_drops_coverage_and_is_caught() -> None:
    """THE MECHANISM THAT MAKES 'AND UPCOMING ALWAYS' REAL. A principle added with no enforcement
    must lower the measured percentage -- if it did not, the twenty-sixth law would land silently
    and the audit would keep reporting full coverage."""
    from libs.doctrine.constitution import Principle
    extra = (*PRINCIPLES, Principle(id="P99", name="new law", statement="x", formula="y",
                                    directive="z", aggression=10, posture="ENABLER"))
    import libs.doctrine.enforcement as E
    before = coverage(_registered())["full_pct"]
    orig = E.PRINCIPLES
    try:
        E.PRINCIPLES = extra
        after = E.coverage(_registered())["full_pct"]
    finally:
        E.PRINCIPLES = orig
    assert after < before, "an unenforced new principle must lower coverage"


def test_the_audit_check_is_registered_and_currently_clean() -> None:
    assert any(n == "law-coverage" for n, _ in M.CHECKS)
    assert any(n == "governing-layer" for n, _ in M.CHECKS)
    d: list = []
    M.check_law_coverage(d)
    assert d == [], [msg for _, msg in d]


def test_a_coverage_regression_is_detected(monkeypatch, tmp_path) -> None:
    """Coverage ratchets like aggression: it may rise freely, and a fall is either a law that lost
    its check or a new law nobody enforced -- both defects. The check must be able to go red."""
    mark = tmp_path / "LAW_COVERAGE.json"
    mark.write_text('{"high_water": {"mechanical_pct": 100.0, "interactional_pct": 100.0,'
                    ' "full_pct": 100.0}}', "utf-8")
    monkeypatch.setattr(M, "LAW_COVERAGE_MARK", mark)
    d: list = []
    M.check_law_coverage(d)
    assert "law-coverage-regressed" in {k for k, _ in d}


def test_the_high_water_mark_lives_in_git_not_in_data() -> None:
    """data/ is gitignored, so a mark stored there would vanish on every fresh checkout and the
    ratchet would silently re-baseline to whatever coverage happened to be that day."""
    assert M.LAW_COVERAGE_MARK.parts[-3:][0] == "docs"
    assert M.LAW_COVERAGE_MARK.exists()


# ------------------------------------------------------------------ the layer must RUN


def test_an_inert_governing_layer_is_a_defect(monkeypatch, tmp_path) -> None:
    """A layer nothing calls governs nothing -- and its unit tests stay green the entire time it
    is inert, which is why the check reads the ARTIFACT rather than the imports."""
    monkeypatch.setattr(M, "ALLOCATOR_ARTIFACT", tmp_path / "absent.json")
    d: list = []
    M.check_governing_layer_live(d)
    assert "governing-layer-inert" in {k for k, _ in d}


def test_a_partial_artifact_names_the_law_it_leaves_unenforced(monkeypatch, tmp_path) -> None:
    """Each field exists only if its code path actually ran, so a missing field is a specific law
    going unenforced -- and the defect says which one."""
    art = tmp_path / "alloc.json"
    art.write_text('{"allocation": {"funded": []}, "why_no_ranking": "made entirely of guesses"}',
                   "utf-8")
    monkeypatch.setattr(M, "ALLOCATOR_ARTIFACT", art)
    d: list = []
    M.check_governing_layer_live(d)
    msg = dict(d)["governing-layer-partial"]
    assert "P13" in msg and "P18" in msg and "P4" in msg


# ------------------------------------------------------------------ the mark writes only on change


def test_an_unchanged_ratchet_is_not_rewritten(monkeypatch, tmp_path) -> None:
    """A tracked file that changes on EVERY audit run has no information in its diff, and a repo
    where running the auditor always dirties the tree trains whoever commits to `git add -A`
    without reading -- so the one run whose diff carries a real regression goes through with the
    noise. A ratchet's timestamp must mean 'this is when the mark moved', not 'this is when
    somebody looked': the same distinction that made min_snapshots an unsound gate."""
    mark = tmp_path / "LAW_COVERAGE.json"
    monkeypatch.setattr(M, "LAW_COVERAGE_MARK", mark)
    M.check_law_coverage([])
    first = mark.read_text("utf-8")
    M.check_law_coverage([])
    M.check_law_coverage([])
    assert mark.read_text("utf-8") == first, "the mark was rewritten with nothing changed"


def test_the_mark_STILL_writes_when_the_high_water_actually_rises(monkeypatch, tmp_path) -> None:
    """The other half, and the one that matters more: suppressing a no-op write must never
    suppress a real one. A ratchet that stopped recording progress would be a far worse defect
    than the churn it replaced."""
    mark = tmp_path / "LAW_COVERAGE.json"
    mark.write_text('{"high_water": {"mechanical_pct": 1.0, "interactional_pct": 1.0,'
                    ' "full_pct": 1.0}, "live": {}}', "utf-8")
    monkeypatch.setattr(M, "LAW_COVERAGE_MARK", mark)
    M.check_law_coverage([])
    after = json.loads(mark.read_text("utf-8"))
    assert after["high_water"]["mechanical_pct"] > 1.0, "a real rise must be persisted"
    assert after["live"], "the live snapshot must be written alongside it"


def test_a_first_run_with_no_mark_writes_one(monkeypatch, tmp_path) -> None:
    """Absence must not be mistaken for 'unchanged' -- that is WS-005 in the very code that
    records law coverage."""
    mark = tmp_path / "sub" / "LAW_COVERAGE.json"
    monkeypatch.setattr(M, "LAW_COVERAGE_MARK", mark)
    M.check_law_coverage([])
    assert mark.exists()
