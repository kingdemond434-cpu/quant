"""max_audit.check_dig_depth must see VERIFICATION depth, not only CORPUS depth.

THE MEASURED FALSE POSITIVE (2026-08-12). frontier_br_20260812T0827.log scored 1/11 on the
original marker list and was flagged "breadth-theater, no reply/fork/citation mining evident".
What that dig actually did: reimplemented a repo's "MCPT validation" to show it permutes
order-invariant statistics (max-min across 500 permutations = 1.1e-15, so its p-value is a
floating-point rounding hash), censused 23 archive vintages to RETRACT its own predecessor's
inferred decay rate, ran the native-key control that exposed a structural zero in a supposedly
well-formed English search term, and recorded a falsifier rather than picking the exciting
hypothesis. Every one of those costs more than following a comment tree.

WHY THE MISS WAS NOT HARMLESS, which is why this is a test and not a tweak. A lexical fence
teaches seats to write the words it counts. A list that can only see reply/fork/citation pushes
every dig toward comment-tree breadth and grades re-derivation as theatre -- the fence causing
the failure it exists to detect. Goodhart, inside governance.

THE BAR IS NOT LOWERED. Still <2 hits fails; a genuinely wide-and-shallow log still trips it.
This widens what counts as depth, which is the same remedy check_timidity_language records for
its own vocabulary ("vocabulary lists widen on a FALSE POSITIVE").
"""
from __future__ import annotations

from pathlib import Path

from scripts import max_audit

_REAL_BR_LOG = (Path(__file__).resolve().parents[2]
                / "data/cro_ai_logs/frontier_br_20260812T0827.log")


def _markers() -> tuple[str, ...]:
    """The marker tuple as the function actually uses it, read from its own source.

    Deliberately NOT a copy pasted into the test: a duplicated list drifts, and then the test
    asserts about a vocabulary the fence no longer has.
    """
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(max_audit.check_dig_depth).lstrip())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and node.targets
                and getattr(node.targets[0], "id", "") == "markers"):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("check_dig_depth no longer assigns `markers` -- retarget this test")


def _score(text: str) -> int:
    t = text.lower()
    return sum(1 for m in _markers() if m in t)


def test_verification_depth_is_depth():
    """A dig that re-derives a claim instead of repeating it must clear the bar."""
    verification = ("I reimplemented the permutation test and the census of 23 vintages "
                    "retracts my predecessor's rate; falsifier recorded.")
    assert _score(verification) >= 2


def test_corpus_depth_still_counts():
    """The original class is untouched -- widening must not trade one blindness for another."""
    corpus = "Mined the reply chain in that thread, followed the fork, chased the citation."
    assert _score(corpus) >= 2


def test_a_genuinely_shallow_log_still_fails():
    """THE BAR IS UNCHANGED. If this ever passes, the widening became slack."""
    shallow = ("Searched 40 sites. Listed 200 repositories by name. Catalogued the results. "
               "Nothing further to report; the ground looks rich and I will return later.")
    assert _score(shallow) < 2


def test_the_real_br_log_is_no_longer_theatre():
    """REGRESSION FIXTURE, the actual artifact that produced the defect. Skipped rather than
    silently passing if the log has been reaped -- data/cro_ai_logs is on a 3x/day reaper, so an
    absent file here means "cannot look", never "fixed"."""
    if not _REAL_BR_LOG.exists():
        import pytest
        pytest.skip(f"{_REAL_BR_LOG.name} reaped -- cannot re-measure, which is not a pass")
    assert _score(_REAL_BR_LOG.read_text("utf-8", errors="ignore")) >= 2
