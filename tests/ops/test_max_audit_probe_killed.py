"""A COLLECTION PROBE THE KERNEL KILLED IS NOT A BROKEN TEST SUITE (R0407b).

`check_test_suite_collectable` reduced every non-zero exit to "pytest cannot COLLECT the suite" and
told the reader to install a missing dependency. Measured twice on 2026-08-05: the probe recorded
rc=-9 with an EMPTY list of reasons -- because a SIGKILLed child prints no ERROR lines to find --
while a full collection seconds later returned rc=0 in 19s at 326MB peak. The desk spent that
cycle hunting a dependency that does not exist and a failing test that was never there.

WHAT THESE TESTS PIN, and none of it loosens the gate:
  * a killed probe STILL raises a defect (unknown is NOT-PROVEN-GREEN on a safety gate),
  * under a DIFFERENT name, carrying the memory evidence, saying the box is at fault,
  * it is never re-run (re-running a memory-killed probe doubles the shortage it reports),
  * a genuine collection error is untouched and still says so,
  * and the collected-module ratchet's silence during a killed cycle is STATED, because a partial
    count from a truncated run would fire a false `test-suite-shrank`.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from scripts import max_audit


def _record_at(monkeypatch, tmp_path, payload: dict) -> None:
    """Point the high-water record at scratch, with ROOT moved to match.

    Both are patched together because the shrink message renders the record path RELATIVE to ROOT;
    moving one without the other is not a smaller change, it is a broken one.
    """
    rec = tmp_path / "docs/research/test_suite_record.json"
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(json.dumps(payload), "utf-8")
    monkeypatch.setattr(max_audit, "TEST_RECORD", rec)
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)


class _Result:
    def __init__(self, rc: int, out: str = "", err: str = "") -> None:
        self.returncode, self.stdout, self.stderr = rc, out, err


@pytest.fixture
def runs(monkeypatch):
    """Record every subprocess the check launches, so a hidden re-run cannot pass unnoticed."""
    calls: list[list[str]] = []

    def fake(cmd, **kwargs):
        calls.append(list(cmd))
        return fake.result

    fake.result = _Result(0)
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(max_audit.subprocess, "run", fake)
    return fake, calls


class TestKilledProbeIsNotACollectionError:
    def test_signal_death_raises_its_own_defect(self, runs):
        fake, _ = runs
        fake.result = _Result(-9)
        defects: list[tuple[str, str]] = []
        max_audit.check_test_suite_collectable(defects)
        names = [d[0] for d in defects]
        assert names == ["test-suite-probe-killed"], (
            f"a SIGKILLed probe must not be filed as a broken suite: {names}")

    def test_the_defect_carries_the_signal_and_the_memory_evidence(self, runs):
        fake, _ = runs
        fake.result = _Result(-9)
        defects: list[tuple[str, str]] = []
        max_audit.check_test_suite_collectable(defects)
        msg = defects[0][1]
        assert "signal 9" in msg, f"the signal must be named: {msg!r}"
        assert "MemAvailable" in msg, (
            "the claim must be CHECKABLE at the moment of death -- this box cannot read "
            f"journalctl -k, so rc=-9 is all it will ever see: {msg!r}")

    def test_it_does_not_advise_installing_a_dependency(self, runs):
        """The old text sent the reader after a dependency that does not exist."""
        fake, _ = runs
        fake.result = _Result(-9)
        defects: list[tuple[str, str]] = []
        max_audit.check_test_suite_collectable(defects)
        msg = defects[0][1].lower()
        assert "importorskip" not in msg and "missing dependency" not in msg, (
            f"false first move preserved: {msg!r}")

    def test_it_says_the_ratchet_could_not_be_evaluated(self, runs):
        """Silence is what made the shrink invisible; the gap must be stated out loud."""
        fake, _ = runs
        fake.result = _Result(-9)
        defects: list[tuple[str, str]] = []
        max_audit.check_test_suite_collectable(defects)
        assert "ratchet" in defects[0][1].lower()

    def test_the_killed_probe_is_never_re_run(self, runs):
        """Re-running a memory-killed probe under the same pressure doubles the shortage."""
        fake, calls = runs
        fake.result = _Result(-9)
        max_audit.check_test_suite_collectable([])
        assert len(calls) == 1, f"probe re-run after a signal death: {calls}"

    def test_a_killed_probe_still_counts_as_a_defect(self, runs):
        """Nothing is loosened: an unmeasured suite is not a green one."""
        fake, _ = runs
        fake.result = _Result(-9)
        defects: list[tuple[str, str]] = []
        max_audit.check_test_suite_collectable(defects)
        assert defects, "a killed probe must still raise -- unknown is NOT-PROVEN-GREEN"


class TestGenuineFailuresAreUntouched:
    def test_real_collection_error_still_says_uncollectable(self, runs):
        fake, _ = runs
        fake.result = _Result(2, "ERROR tests/x.py - ModuleNotFoundError: No module named 'zzz'")
        defects: list[tuple[str, str]] = []
        max_audit.check_test_suite_collectable(defects)
        assert [d[0] for d in defects] == ["test-suite-uncollectable"]
        assert "ModuleNotFound" in defects[0][1]

    def test_clean_collection_raises_nothing(self, runs, monkeypatch, tmp_path):
        fake, _ = runs
        fake.result = _Result(0, "tests/a/test_x.py: 3\ntests/b/test_y.py: 4\n")
        _record_at(monkeypatch, tmp_path, {"max_collected": 2})
        defects: list[tuple[str, str]] = []
        max_audit.check_test_suite_collectable(defects)
        assert defects == []

    def test_shrink_still_fires_on_a_completed_probe(self, runs, monkeypatch, tmp_path):
        """The ratchet is the important half and must survive this change intact."""
        fake, _ = runs
        fake.result = _Result(0, "tests/a/test_x.py: 3\n")
        _record_at(monkeypatch, tmp_path, {"max_collected": 99})
        defects: list[tuple[str, str]] = []
        max_audit.check_test_suite_collectable(defects)
        assert [d[0] for d in defects] == ["test-suite-shrank"]
