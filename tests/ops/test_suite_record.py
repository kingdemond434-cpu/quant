"""The pass/fail half of the suite record (R0543).

THE PROPERTY EVERY TEST HERE SERVES: a test that imports fine and FAILS is still COLLECTED, so a
ratchet on collection cannot fall when the suite breaks. These pin the second ratchet -- the one
that can.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import suite_record as S

_NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)


# ================================================================================ parsing a run


def test_parse_reads_outcomes_by_NAME_not_by_position() -> None:
    """A positional parse reads `xfailed` as `failed` the first time one appears."""
    c = S.parse_summary("5 failed, 700 passed, 12 skipped, 3 xfailed in 91.20s")
    assert c == {"n_passed": 700, "n_failed": 5, "n_skipped": 12}


def test_an_ERROR_counts_as_RED_and_is_never_a_softer_failure() -> None:
    """A collection or fixture error is a test that NEVER RAN, reported beside a pass count."""
    assert S.parse_summary("2 errors, 700 passed in 10s")["n_failed"] == 2
    assert S.parse_summary("1 error, 700 passed in 10s")["n_failed"] == 1


def test_a_run_with_NO_SUMMARY_returns_None_and_never_zeros() -> None:
    """A killed or hung run has no summary line. Zeros there would publish a PERFECT record for a
    suite that did not execute -- the fabricated-measurement class (L1.55)."""
    assert S.parse_summary("") is None
    assert S.parse_summary("Killed\n") is None
    assert S.parse_summary("ERROR: file or directory not found: tests/") is None


# ================================================================================ the two ratchets


def test_n_passed_ratchets_UP_and_a_fall_is_a_defect(tmp_path: Path) -> None:
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 0}, source="t", now=_NOW)
    blk = S.record_run(tmp_path, {"n_passed": 640, "n_failed": 0}, source="t", now=_NOW)

    assert blk["high_water_passed"] == 700          # the bar does not follow the reading down
    assert blk["n_passed"] == 640
    status, detail = S.grade(S.read(tmp_path), now=_NOW)
    assert status == "FELL"
    assert "640" in detail and "700" in detail


def test_n_failed_has_a_floor_of_ZERO_with_no_high_water_and_no_tolerance(tmp_path: Path) -> None:
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 13}, source="t", now=_NOW)
    status, detail = S.grade(S.read(tmp_path), now=_NOW)
    assert status == "RED"
    assert "13" in detail


def test_RED_outranks_STALE_because_age_qualifies_a_failure_and_cannot_withdraw_it(
    tmp_path: Path,
) -> None:
    old = _NOW - timedelta(hours=500)
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 1}, source="t", now=old)
    # The RED FAMILY, not the exact word: R0564 split a 500h-old red into its own verdict, and the
    # property this test exists for is that AGE NEVER TURNS A FAILURE INTO A STALENESS REPORT.
    # Asserting the literal string would have made this test a lock on the vocabulary instead.
    status = S.grade(S.read(tmp_path), now=_NOW)[0]
    assert status.startswith("RED")
    assert status != "STALE"


def test_a_clean_fresh_run_is_OK(tmp_path: Path) -> None:
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 0}, source="t", now=_NOW)
    status, detail = S.grade(S.read(tmp_path), now=_NOW)
    assert status == "OK"
    assert "700 passed" in detail


# ============================================================== the refusals, kept apart from each
# ============================================================== other and from a clean verdict


def test_no_recorded_run_is_UNMEASURED_and_never_OK(tmp_path: Path) -> None:
    """L1.28a. This is the state the row was raised from; it must not render green."""
    assert S.grade({})[0] == "UNMEASURED"
    (tmp_path / "docs/research").mkdir(parents=True)
    (tmp_path / S.RECORD_REL).write_text(json.dumps({"max_collected": 804}), "utf-8")
    assert S.grade(S.read(tmp_path))[0] == "UNMEASURED"


def test_STALE_and_UNMEASURED_are_DIFFERENT_verdicts(tmp_path: Path) -> None:
    """'the writer was never wired' and 'the suite has not been run lately' have different first
    moves, and a desk that cannot tell them apart debugs the wrong organ."""
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 0}, source="t",
                 now=_NOW - timedelta(hours=200))
    status, detail = S.grade(S.read(tmp_path), now=_NOW)
    assert status == "STALE"
    assert "200h" in detail


def test_recording_LEAVES_max_collected_alone(tmp_path: Path) -> None:
    """Additive: the collection ratchet keeps its own meaning and its own number."""
    (tmp_path / "docs/research").mkdir(parents=True)
    (tmp_path / S.RECORD_REL).write_text(json.dumps({"max_collected": 804, "at": "x"}), "utf-8")
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 0}, source="t", now=_NOW)
    assert S.read(tmp_path)["max_collected"] == 804


# ===================================================== the two writers must not erase each other


def test_max_audits_collection_writer_PRESERVES_the_pass_fail_block(
    tmp_path: Path, monkeypatch
) -> None:
    """THE STATE-ERASER CLASS, caught before it shipped. max_audit wrote a fresh three-key dict
    into this file -- harmless while it held exactly three keys, a silent state-eraser the moment
    a second writer appeared. Same shape as the whole-dict write that made `--rollback` unfirable
    in data/model_upgrade.json: the erasure is silent, and the erased half is the half nobody is
    looking at."""
    import importlib
    import subprocess

    ma = importlib.import_module("scripts.max_audit")
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 0}, source="t", now=_NOW)

    # Drive max_audit's OWN writer, not a re-implementation of it: a test that asserts its own
    # inline copy preserved the block proves nothing about the code that does the erasing.
    fake = subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout="\n".join(f"tests/x/test_{i}.py::test_a" for i in range(900)), stderr="")
    monkeypatch.setattr(ma, "TEST_RECORD", tmp_path / S.RECORD_REL)
    monkeypatch.setattr(ma.subprocess, "run", lambda *a, **k: fake)

    ma.check_test_suite_collectable([])

    after = S.read(tmp_path)
    assert after["max_collected"] == 900, "the collection ratchet did not record the new high-water"
    assert after["pass_fail"]["n_passed"] == 700, "the collection writer erased the pass/fail half"


# ============================================ how LONG it has been red is a different claim (R0564)


def test_red_since_is_CARRIED_across_runs_that_stay_red(tmp_path: Path) -> None:
    """The clock measures the CURRENT redness, so a second red run does not restart it -- that is
    the whole difference between 'red' and 'red for eleven days'."""
    first = _NOW - timedelta(days=5)
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 3}, source="t", now=first)
    blk = S.record_run(tmp_path, {"n_passed": 699, "n_failed": 4}, source="t",
                       now=_NOW - timedelta(days=1))
    assert blk["red_since"] == first.isoformat()


def test_ONE_GREEN_RUN_clears_the_clock(tmp_path: Path) -> None:
    """A fixed suite that breaks again is a NEW redness, not a continuation of the old one."""
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 3}, source="t",
                 now=_NOW - timedelta(days=9))
    S.record_run(tmp_path, {"n_passed": 703, "n_failed": 0}, source="t",
                 now=_NOW - timedelta(days=8))
    blk = S.record_run(tmp_path, {"n_passed": 702, "n_failed": 1}, source="t", now=_NOW)

    assert blk["red_since"] == _NOW.isoformat()
    assert S.grade(S.read(tmp_path), now=_NOW)[0] == "RED", "a fresh red is work in flight"


def test_red_past_the_threshold_is_ENTRENCHED_and_a_distinct_verdict(tmp_path: Path) -> None:
    """R0564. Both statuses mean a test is failing; they differ in what the desk should DO, and
    that is the only thing a status is for. 8 days is the merge-union regression's own duration."""
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 4}, source="t",
                 now=_NOW - timedelta(days=8))
    status, detail = S.grade(S.read(tmp_path), now=_NOW)

    assert status == "RED-ENTRENCHED"
    assert "8.00d" in detail


def test_the_threshold_is_a_boundary_not_a_mood(tmp_path: Path, tmp_path_factory) -> None:
    """Just inside three days is a fix in flight; just outside it is a gate the desk is carrying.

    Two trees, because `red_since` is CARRIED: a second write into the same record cannot move the
    clock, so testing both sides in one tree would be testing the carry, not the boundary.
    """
    S.record_run(tmp_path, {"n_passed": 700, "n_failed": 1}, source="t",
                 now=_NOW - timedelta(days=3))
    inside, detail = S.grade(S.read(tmp_path), now=_NOW)
    assert inside == "RED", "exactly at the threshold is not PAST it"
    assert "3.00d" in detail

    other = tmp_path_factory.mktemp("outside")
    S.record_run(other, {"n_passed": 700, "n_failed": 1}, source="t",
                 now=_NOW - timedelta(days=3, hours=1))
    assert S.grade(S.read(other), now=_NOW)[0] == "RED-ENTRENCHED"


def test_a_record_predating_red_since_is_RED_with_the_duration_UNMEASURED(tmp_path: Path) -> None:
    """L1.28a: the block knows the suite is red and NOT for how long. Back-dating it to `at` would
    be a measurement nobody took, and it would report an entrenched red the desk never observed."""
    (tmp_path / "docs/research").mkdir(parents=True)
    (tmp_path / S.RECORD_REL).write_text(json.dumps({"pass_fail": {
        "n_passed": 700, "n_failed": 9, "high_water_passed": 700,
        "at": (_NOW - timedelta(days=30)).isoformat(), "source": "old"}}), "utf-8")

    status, detail = S.grade(S.read(tmp_path), now=_NOW)
    assert status == "RED", "an unrecorded duration must never grade as entrenched"
    assert "UNMEASURED" in detail


def test_every_status_grade_can_return_has_a_defect_key_in_max_audit() -> None:
    """The consumer is a DICT LOOKUP, so a status added here without its key there is a KeyError
    in the audit -- loud, but only found by running it. This pins the two files together."""
    import importlib
    import inspect

    ma = importlib.import_module("scripts.max_audit")
    src = inspect.getsource(ma.check_test_suite_pass_fail)
    for status in ("RED", "RED-ENTRENCHED", "FELL", "UNMEASURED", "STALE"):
        assert f'"{status}"' in src, f"grade() can return {status} and max_audit cannot name it"
