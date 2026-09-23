"""THE PATH FROM A RUN THAT ALREADY HAPPENS TO THE RECORD THAT HOLDS IT (R0564).

The pass/fail block had never been written once, and not because nobody runs the suite: the only
producer was `run_ci.py`, which appears in no schedule, while the whole-suite run that DOES happen
on this box appended its counts to a log outside the repo. These pin the ingest that closes that
gap -- and, more importantly, the two refusals, because a recorder that writes zeros for a killed
run or prints success over a reverted write is worse than the UNMEASURED state it replaces.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

R = importlib.import_module("scripts.record_suite_run")
from libs.ops import suite_record as S  # noqa: E402

_GREEN = "tests/x/test_a.py ....\n\n700 passed, 12 skipped in 4212.11s (1:10:12)\n"
_RED = "tests/x/test_a.py FF..\n\n13 failed, 691 passed, 12 skipped in 4380.02s (1:13:00)\n"


@pytest.fixture(autouse=True)
def _no_law_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard is a boundary check on the LAWS, not on this parser; it reaches the network of
    files under the real root and has nothing to say about a tmp_path record."""
    monkeypatch.setattr(R, "_law_guard", lambda *a, **k: None)


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str, *argv: str) -> int:
    log = tmp_path / "run.log"
    log.write_text(text, "utf-8")
    monkeypatch.setattr(sys, "argv", ["record_suite_run.py", "--log", str(log),
                                      "--root", str(tmp_path), *argv])
    monkeypatch.setattr(R, "live_pytest_in", lambda root: [])
    return R.main()


def test_a_finished_run_lands_in_the_record(monkeypatch: pytest.MonkeyPatch,
                                            tmp_path: Path) -> None:
    assert _run(monkeypatch, tmp_path, _GREEN) == 0

    blk = S.read(tmp_path)["pass_fail"]
    assert (blk["n_passed"], blk["n_failed"], blk["n_skipped"]) == (700, 0, 12)
    assert blk["source"] == "record_suite_run"
    assert S.grade(S.read(tmp_path))[0] == "OK"


def test_a_RED_run_is_recorded_and_still_EXITS_ZERO(monkeypatch: pytest.MonkeyPatch,
                                                    tmp_path: Path) -> None:
    """It records, it does not gate. A recorder that exits non-zero on bad news gets wrapped in
    `|| true` at its call site and stops recording -- and then the desk is back to UNMEASURED,
    which is strictly worse than a measured red. Exit 2 means 'I could not record'."""
    assert _run(monkeypatch, tmp_path, _RED) == 0

    assert S.read(tmp_path)["pass_fail"]["n_failed"] == 13
    assert S.grade(S.read(tmp_path))[0] == "RED"


def test_a_KILLED_run_is_REFUSED_and_never_recorded_as_zeros(monkeypatch: pytest.MonkeyPatch,
                                                             tmp_path: Path) -> None:
    """L1.55. A hung or killed run has no summary line, and zeros there would publish a perfect
    record for a suite that did not execute -- a fabrication that reads exactly like health."""
    assert _run(monkeypatch, tmp_path, "tests/x/test_a.py ..\nKilled\n") == 2

    assert "pass_fail" not in S.read(tmp_path), "a killed run must leave the record UNMEASURED"
    assert S.grade(S.read(tmp_path))[0] == "UNMEASURED"


def test_a_LIVE_SUITE_IN_THE_SAME_TREE_is_REFUSED(monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path) -> None:
    """L0177/R0711, three recorded instances. The record is a PROTECTED artifact: conftest
    restores it at the live session's teardown, so the write would print success and persist
    nothing. Refusing is the only outcome that does not manufacture a false green."""
    log = tmp_path / "run.log"
    log.write_text(_GREEN, "utf-8")
    monkeypatch.setattr(sys, "argv", ["record_suite_run.py", "--log", str(log),
                                      "--root", str(tmp_path)])
    monkeypatch.setattr(R, "live_pytest_in", lambda root: [4242])

    assert R.main() == 2
    assert "pass_fail" not in S.read(tmp_path)


def test_a_write_that_does_not_LAND_is_a_FAILURE_not_a_success(monkeypatch: pytest.MonkeyPatch,
                                                               tmp_path: Path) -> None:
    """A same-run claim of a write is not the write. Reverted-by-conftest, a read-only tree and a
    full disk all leave `record_run` returning a perfectly good dict over a file that never took
    it -- so the re-read is the claim, and it must fail loudly rather than print the block it
    just built."""
    log = tmp_path / "run.log"
    log.write_text(_GREEN, "utf-8")
    monkeypatch.setattr(sys, "argv", ["record_suite_run.py", "--log", str(log),
                                      "--root", str(tmp_path)])
    monkeypatch.setattr(R, "live_pytest_in", lambda root: [])

    real_record_run = S.record_run

    def _write_then_revert(root: Path, counts: dict[str, int], **kw: object) -> dict[str, object]:
        block = real_record_run(root, counts, **kw)          # type: ignore[arg-type]
        (root / S.RECORD_REL).write_text(json.dumps({"max_collected": 817}), "utf-8")
        return block

    monkeypatch.setattr(R.suite_record, "record_run", _write_then_revert)

    assert R.main() == 2, "the recorder claimed a write the file does not hold"


def test_live_pytest_in_asks_about_THIS_TREE_not_the_box(tmp_path: Path) -> None:
    """Two trees run suites concurrently here all day, and only the one whose conftest owns this
    file can revert the write. A box-wide answer would refuse every legitimate ingest."""
    assert R.live_pytest_in(tmp_path) == [], "no suite has ever run in a fresh tmp_path"


# ============================================ the collector: what makes it SCHEDULABLE (R0564)


def test_scan_ingests_the_newest_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "old.log").write_text(_RED, "utf-8")
    (logs / "new.log").write_text(_GREEN, "utf-8")
    import os
    os.utime(logs / "old.log", (1, 1))

    monkeypatch.setattr(sys, "argv", ["record_suite_run.py", "--scan", str(logs / "*.log"),
                                      "--root", str(tmp_path)])
    monkeypatch.setattr(R, "live_pytest_in", lambda root: [])

    assert R.main() == 0
    blk = S.read(tmp_path)["pass_fail"]
    assert blk["n_passed"] == 700, "the collector took the older log"
    assert "new.log" in blk["source"], "the record must name WHICH run it banked"


def test_scan_REFUSES_TO_REBANK_the_same_run(monkeypatch: pytest.MonkeyPatch,
                                             tmp_path: Path) -> None:
    """THE GUARD THAT MAKES AN HOURLY JOB SAFE. `grade` calls a record STALE past 48h, so a
    collector that re-stamped one log every tick would make a suite last run in July read as fresh
    forever -- fabricating freshness on the exact axis the fence exists to measure."""
    logs = tmp_path / "logs"
    logs.mkdir()
    log = logs / "run.log"
    log.write_text(_GREEN, "utf-8")

    monkeypatch.setattr(sys, "argv", ["record_suite_run.py", "--scan", str(logs / "*.log"),
                                      "--root", str(tmp_path)])
    monkeypatch.setattr(R, "live_pytest_in", lambda root: [])
    assert R.main() == 0
    first = S.read(tmp_path)["pass_fail"]["at"]

    assert R.main() == 0, "nothing-new is the NORMAL state of an hourly collector, not a failure"
    assert S.read(tmp_path)["pass_fail"]["at"] == first, "the collector re-stamped an old run"


def test_scan_with_NO_LOGS_says_so_and_never_writes(monkeypatch: pytest.MonkeyPatch,
                                                    tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "argv", ["record_suite_run.py", "--scan", str(tmp_path / "n/*.log"),
                                      "--root", str(tmp_path)])
    monkeypatch.setattr(R, "live_pytest_in", lambda root: [])

    assert R.main() == 0
    assert "pass_fail" not in S.read(tmp_path), "an empty scan must leave the record UNMEASURED"


# ================================ the -qq trap: the run finished and printed no number (R0564)


_QQ = ("tests/x/test_a.py FF..\n"
       "=========================== short test summary info ============================\n"
       "FAILED tests/x/test_a.py::test_one\n"
       "FAILED tests/x/test_a.py::test_two\n")


def test_a_FINISHED_run_with_no_counts_is_diagnosed_as_the_qq_trap(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """THE DEFECT THAT COST THIS RECORD ITS WHOLE LIFE. pyproject's addopts is `-ra -q`, so an
    invocation adding its own `-q` reaches pytest as `-qq` and the terminal counts line is
    suppressed -- run_ci.py:108 did exactly that, so its parse returned None on every run it ever
    made. Diagnosed as 'killed or hung' it sends an operator to re-run an 80-minute suite that
    already answered; the two causes demand OPPOSITE repairs and must stay apart (L1.55)."""
    assert _run(monkeypatch, tmp_path, _QQ) == 2

    err = capsys.readouterr().err
    assert "-qq" in err and "Do NOT re-run" in err
    assert "pass_fail" not in S.read(tmp_path), "an unparseable run must stay UNMEASURED"


def test_a_KILLED_run_is_NOT_diagnosed_as_the_qq_trap(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    """The other side of the same distinction: no end-of-run marker means the run really did die,
    and THAT one is repaired by running the suite again."""
    assert _run(monkeypatch, tmp_path, "tests/x/test_a.py ..\nKilled\n") == 2

    err = capsys.readouterr().err
    assert "-qq" not in err
    assert "killed, hung" in err


def test_completed_without_counts_reads_the_END_of_a_run_not_its_verbosity() -> None:
    """A progress line alone is not proof of completion -- a suite killed at 40% has one too."""
    assert S.completed_without_counts(_QQ) is True
    assert S.completed_without_counts("tests/x ....  [100%]\n") is True
    assert S.completed_without_counts("tests/x ....  [ 40%]\n") is False
    assert S.completed_without_counts("") is False


def test_the_gate_that_feeds_the_record_no_longer_silences_it() -> None:
    """The one-token fix, pinned where it cannot silently come back. The COLLECT step keeps its
    `-q` on purpose: at -qq `--co` prints "path: N" per module, which is what the collection
    ratchet counts."""
    import importlib

    ci = importlib.import_module("scripts.run_ci")
    steps = {label: cmd for label, cmd, _ in ci._STEPS}
    suite = next(c for lbl, c in steps.items() if lbl.startswith("tests (pytest)"))

    assert suite.count("-q") == 0, "addopts already carries -q; a second one reaches pytest as -qq"
    collect = next(c for lbl, c in steps.items() if lbl.startswith("collect"))
    assert "-q" in collect, "the collect step's terse per-module output IS the -qq form"
