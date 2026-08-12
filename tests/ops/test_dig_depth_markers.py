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


def test_archive_verification_depth_is_depth():
    """THE SECOND MODALITY, found the same way as the first (2026-08-12).

    The list above was community mining plus code replication. A dig into a BULK ARCHIVE or an
    API does its depth in a third vocabulary entirely, so it could not clear this bar however far
    it went -- a gate that rejects ~100% of a category carries zero information about it.

    MEASURED: dataaxis_20260812T1530 scored 1. It verified a published sha256 sidecar, ran
    archive-vs-live to 0 mismatches over 31 bars x 7 fields, and found the S3 lister truncates at
    1000 keys and never errors -- a 3.7-year silent understatement, now a desk lesson.
    """
    archive = ("Paginated the lister and the span moved 2022-11 -> 2026-08; the published sha256 "
               "sidecar matched byte-for-byte and archive-vs-live returned 0 mismatches.")
    assert _score(archive) >= 2


def test_the_observed_intention_word_was_refused_admission():
    """THE SELECTION RULE FOR NEW MARKERS, pinned as the decision it actually was.

    `backfill` was tested for the archive family and REFUSED: its only occurrence across all nine
    substantial digs on disk is "still needs a pi backfill" -- work NOT done -- and admitting it
    would have flipped frontier_jp_20260812T0747 from firing to passing on that one word. This
    pins the exclusion so a later widening cannot quietly re-admit it.
    """
    assert "backfill" not in _markers()


def test_the_fence_cannot_tell_a_performed_act_from_a_promised_one():
    """A CHARACTERISATION TEST: this pins a KNOWN BLIND SPOT, not a property the fence has.

    Written because the honest version of the rule above ("markers name acts, never intentions")
    turned out to be UNENFORCEABLE and this test failed on its first run, which is how it was
    found. `_score` is a bag-of-words match, so a log that PROMISES two verification acts scores
    exactly what a log that PERFORMED them scores. Excluding `backfill` narrowed the observed
    exposure; it did not close the hole, and no vocabulary edit can -- the fence has no syntax.

    So the residual is written down here rather than believed solved. The fence's own docstring
    already concedes lexical markers are fakeable by construction and that real depth quality is
    judged downstream by red-team/maximization; this is the concrete demonstration of that
    concession, and it is why the marker score must never become the ONLY depth authority.

    IF THIS EVER FAILS, something gained the ability to distinguish the two -- revisit the rule
    above, because it would then be enforceable and should be enforced.
    """
    promised = ("Rich ground here. I plan to paginate the archive and checksum it on a later "
                "pass once time allows.")
    assert _score(promised) >= 2          # scores as depth despite performing nothing


def test_the_real_dataaxis_log_is_no_longer_theatre():
    """REGRESSION FIXTURE for the archive modality. Skipped, never silently passed, if reaped."""
    log = _REAL_BR_LOG.parent / "dataaxis_20260812T1530.log"
    if not log.exists():
        import pytest
        pytest.skip(f"{log.name} reaped -- cannot re-measure, which is not a pass")
    assert _score(log.read_text("utf-8", errors="ignore")) >= 2


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


# --- A STUB MUST NOT BLIND THE FAMILY BEHIND IT (2026-08-12) ------------------------------------
#
# check_dig_depth took `logs[0]` and then skipped it when it was under 1500 bytes, so ONE tiny
# "DEFERRED -- brain mutex held by cro_ai" notice exempted every frontier dig from depth judgement.
# Measured live: frontier_kr_20260812T1500.log was 171 bytes and the newest of its glob, while four
# substantial digs from that morning went unread. The fence reported no defect over a set it never
# opened -- a pass on an empty scan (L1.57), not a threshold that was too loose.


def _judge(tmp_path, monkeypatch, files: dict[str, str]) -> dict[str, str]:
    """Run check_dig_depth over a synthetic log dir. `files` maps name -> contents, oldest first."""
    import os
    import time

    logs = tmp_path / "logs"
    logs.mkdir(parents=True)
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data/depth_mandate_baseline").write_text("0", "utf-8")
    now = time.time()
    for i, (name, body) in enumerate(files.items()):
        p = logs / name
        p.write_text(body, "utf-8")
        os.utime(p, (now - (len(files) - i) * 60, now - (len(files) - i) * 60))
    monkeypatch.setattr(max_audit, "LOGS", logs)
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    monkeypatch.setattr(max_audit, "NOW", now)
    defects: list[tuple[str, str]] = []
    max_audit.check_dig_depth(defects)
    return dict(defects)


_SHALLOW = "we looked at many sources and listed them. " * 60      # >1500b, 0 depth markers
_DEEP = "we reimplemented the permutation census and filed a falsifier. " * 40


def test_a_stub_newest_log_does_not_exempt_the_substantial_dig_behind_it(tmp_path, monkeypatch):
    """THE REGRESSION. The stub is newest; the shallow dig behind it must still be judged."""
    ids = _judge(tmp_path, monkeypatch, {
        "frontier_br_1.log": _SHALLOW,
        "frontier_kr_2.log": "frontier-kr DEFERRED -- brain mutex held by cro_ai pid=1097905\n",
    })
    assert "dig-shallow-frontier_br_1" in ids, (
        "a 171-byte mutex-deferral notice must not blind the fence to the substantial dig "
        "behind it -- that is a passing verdict over a set the fence never opened")


def test_a_deep_dig_behind_a_stub_still_passes(tmp_path, monkeypatch):
    """The widened selection must not manufacture defects either -- depth still clears."""
    assert _judge(tmp_path, monkeypatch, {
        "frontier_br_1.log": _DEEP,
        "frontier_kr_2.log": "frontier-kr DEFERRED -- brain mutex held\n",
    }) == {}


def test_stubs_alone_are_still_not_judged_for_depth(tmp_path, monkeypatch):
    """check_organs owns quota-deaths. A family with NO substantial dig raises nothing here."""
    assert _judge(tmp_path, monkeypatch, {
        "frontier_br_1.log": "DEFERRED\n",
        "frontier_kr_2.log": "DEFERRED\n",
    }) == {}
