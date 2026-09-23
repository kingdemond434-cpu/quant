"""THE SUITE MAY NOT WRITE THE THINGS IT OBSERVES (GAP 113).

Measured 2026-08-13: a full `pytest` run rewrote three TRACKED files -- the law-number allocator
60 -> 43, a block out of `ops/principal_doctrine.txt`, and real trade forensics replaced with
`n_closes: 0` -- and reported a green suite while doing it. The regressions were caught by reading
a diff and reverted by hand. That is not a control; it is a habit, and the next time it happens
inside a busy commit nobody will read the diff.

WHAT THIS DOES. Snapshots `libs.ops.protected_artifacts.PROTECTED` before the first test; after
EVERY test, re-hashes them; the first test to change one is NAMED and the session fails at the
end with the reason that artifact is protected. THE BYTES ARE LEFT WHERE THEY ARE.

WHY PER-TEST AND NOT ONCE AT THE END. Once at the end tells you the suite wrote something and
leaves you bisecting 5,000 tests to find out which. Fourteen small files hashed per test is a few
milliseconds against a suite measured in minutes, and it converts an afternoon of bisection into
a line of output. It also stops the FIRST write from contaminating what every later test reads.

WHY IT DETECTS AND REFUSES RATHER THAN REVERTING (changed 2026-09-05). It used to put the bytes
back. It could not: this process cannot tell a write made by a TEST from a write made by anything
else touching the tree during a 60-80 minute run -- an editor, an agent, a concurrent organ, a git
operation. All it ever knew was that a hash moved between two teardowns, and it answered that with
somebody else's old bytes.

It cost real evidence twice. 2026-08-18: a concurrent max_audit's recommendation-ledger rows and
two hand-raised rows were attributed to a governance test and restored out of existence -- which
bought the per-test re-baseline below, narrowing the window without closing it. 2026-09-05: a
repair to docs/desk_lessons.jsonl landed inside that residual window and was reverted mid-session,
twice; the only symptom was a `git diff` that came back empty.

Refusing loses nothing. Detection is unchanged, the culprit is still named per test, the session
still fails -- and a failing suite is already a stop signal, so the "next run starts from a
corrupted baseline" worry is answered by the red run rather than by a silent repair. What
reverting actually bought was invisibility: a clean tree, with the only record of the write in a
summary block someone had to read. Leaving the change on disk puts it in `git status`, where it
is seen. Undoing it is then one deliberate `git checkout --`, made with the diff in view.

THERE IS NO HOST EXEMPTION, and that is deliberate. The owning-host guard (GAP 111) exists because
"may this box recompute state?" has a legitimate YES. "May a test run recompute state?" does not:
on the VPS, the one host that owns the artifacts, an overwrite lands on real evidence and is the
WORST case rather than the safe one.

IF A TEST LEGITIMATELY EXERCISES ONE OF THESE WRITERS, point it at `tmp_path`. Every existing test
that touches a ratchet already does; this fence exists for the ones that reach the real path
through three layers of default arguments, which is how all three of the measured cases happened.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parent.parent

# PATH BOOTSTRAP, and it must happen here. pytest imports conftest before collecting anything, so
# without this a `libs` import below resolves only when the project is pip-installed into the
# interpreter in use -- which is not how the gates invoke it.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.protected_artifacts import (  # noqa: E402  (must follow the bootstrap)
    PROTECTED,
    Snapshot,
    changed,
    snapshot,
)

#: rel-path -> (nodeid of the test that changed it, what was done about it -- always 'nothing').
#: First writer only: the
#: interesting fact is WHICH test introduced the write; every later test then sees the changed
#: file as its own baseline, so listing them all would name bystanders.
_VIOLATIONS: dict[str, tuple[str, str]] = {}
_SNAP: Snapshot | None = None


def pytest_configure(config: Any) -> None:
    global _SNAP
    _SNAP = snapshot(_ROOT)


def pytest_runtest_setup(item: Any) -> None:
    """Re-baseline before EVERY test, not once per session (measured 2026-08-18).

    The session-length snapshot had a false-positive mode that ERASED REAL EVIDENCE: this desk's
    organs legitimately append to the protected files while the suite runs (the suite takes
    60-80min; the ledger takes writes hourly), and a change made BETWEEN tests by a concurrent
    organ is indistinguishable from a test's write under a configure-time baseline. Measured: a
    concurrent max_audit's recommendation-ledger rows and two hand-raised rows were attributed to
    tests/governance/test_denominators.py::test_meta_fence_runs_and_reports_a_measured_denominator
    and 'restored' out of existence. Re-snapshotting per test absorbs between-test organ writes
    into the baseline and keeps the guard's real property: a change that appears DURING one test
    is that test's write, and is named. The residual window (an organ or an editor writing
    mid-test) is seconds rather than the session -- and since 2026-09-05 a false positive inside
    that window costs a spurious failure line instead of somebody's work."""
    global _SNAP
    _SNAP = snapshot(_ROOT)


@pytest.fixture(autouse=True)
def _denominator_registry_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE SUITE MAY NOT WRITE THE L1.57 GOVERNANCE REGISTRY EITHER (R0474).

    `fence_exit(scanned=...)` appends a row to data/denominator_contracts.jsonl through
    `denominator._root()` and exposes no redirect, so every suite run filed synthetic rows in the
    live registry: 94/670 rows (14%) on 2026-08-12, re-accumulated to 878/6105 (14%) by
    2026-08-18 under the names 't' and '__main__.py' -- the latter is `caller_name()` under
    `python -m pytest`. Same class as the suite writing the live L1.29 forecast store.

    NOT folded into PROTECTED above, deliberately: the registry is append-only and cron fences
    legitimately append to it WHILE the suite runs, so restore-on-change would destroy real rows
    and blame a test. Redirecting the default root is the correct boundary. A test that patches
    `_root` itself still wins inside its own scope, and a test that drives a real fence through
    a SUBPROCESS is a real fence run whose row is genuine evidence -- both stay untouched.
    """
    monkeypatch.setattr("libs.ops.denominator._root", lambda: tmp_path)


# LOST IN A MERGE AND RESTORED 2026-08-28. This fixture landed in 3358a73b and was gone at HEAD
# with NO commit touching this file after 84cbf97d -- the unification class: the merge kept the
# test that names the guarantee (tests/governance/test_conftest_isolation.py) and dropped the
# fixture it guards. Restored verbatim; the two isolation halves are siblings and travel together.

@pytest.fixture(autouse=True)
def _freshness_registry_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NOR THE L1.44 FRESHNESS REGISTRY (R0544, R0398 follow-up).

    `read_fresh` appends its contract row to `data/freshness_contracts.jsonl` under
    `fresh._root()`, which is cwd when QUANT_FRESH_ROOT is unset -- so a test that points a
    production reader at a tmp artifact still files that read in the PRODUCTION registry, under
    an absolute /tmp/pytest-of-quant/... path. Measured 2026-08-12: 1089 of 1097 rows. Re-measured
    2026-08-19 after the row sat open: 2053 of 2478 (82.8%), from exactly two callers --
    `run_cashcarry_executor._structurally_bleeding` (1322) and `._rt_bps` (731).

    THE VERDICTS WERE NEVER WRONG, THE DENOMINATOR WAS. `check_freshness.py` quarantines an
    off-root path as FOREIGN, so nothing was mis-graded; what it lost is the one number the L1.44
    fence is read for. n_contracts=8 real contracts inside 2478 rows is the L1.57 class pointed at
    a self-building registry: a count that grows with test volume and is 82.8% noise reads as
    coverage. Deleting the rows would be the wrong repair twice over -- it treats the symptom, and
    it blinds the FOREIGN guard to a real production leak, which is the thing it exists to catch.

    FIX AT THE WRITER, WHICH IS WHY THIS IS SUITE-WIDE AND NOT PER-DIRECTORY. The two owning
    suites (tests/ops/test_fresh*.py, tests/governance/test_freshness_fence.py) already pin the
    root; the leak is from every OTHER test that drives a production reader and has no reason to
    know a second path exists. Opt-in isolation only ever protects the tests that remembered to
    ask, and the next one will not -- the same argument the execution suite's bleed-cache fixture
    was written on, one level up.

    tmp_path, not a shared temp dir: it is the SAME per-test directory the test itself writes its
    fixture artifacts into, so a relative read resolves exactly where the test put the file and
    `_rel()` records it by its relative name rather than as an off-root absolute. A test that
    passes `root=` explicitly, or that delenv's this itself to exercise the cwd fallback, still
    wins inside its own scope.
    """
    monkeypatch.setenv("QUANT_FRESH_ROOT", str(tmp_path))


def pytest_runtest_teardown(item: Any) -> None:
    """After every test: re-hash and name the culprit. NEVER put the bytes back.

    THIS FENCE USED TO RESTORE, AND THE RESTORE WAS THE DEFECT. It could not tell a write made by
    a TEST from a write made by anything else touching the tree while the suite ran -- an editor,
    an agent, a concurrent script, a git operation. All it knew was that a hash moved between two
    teardowns. So a legitimate edit made during a run was reverted to a snapshot taken before the
    edit existed, attributed to whichever test happened to be executing, and the work was gone.

    Measured 2026-09-05: a repair to `docs/desk_lessons.jsonl` -- eleven rows normalised out of a
    foreign key vocabulary that was making the WHOLE lesson corpus fail to load -- was silently
    reverted mid-session by exactly this path, twice, while a full-suite run was in the
    background. The evidence that it had happened was a `git diff` that came back empty.

    REMOVING THE RESTORE COSTS NO PROTECTION. The detection is unchanged, the culprit is still
    named per-test, and the session still fails. The old docstring justified restoring as "keeps
    the next run honest -- otherwise run two ratchets from an already-corrupted baseline", but a
    failing suite is already a stop signal, and running a ratchet off a red suite is a separate
    violation. What restoring actually bought was that the damage became invisible: the tree
    looked clean, so the only record of the write was a summary block someone had to read. Leaving
    the bytes where they are makes the write show up in `git status` and `git diff`, which is
    where a human will actually see it.

    IF YOU WANT THE OLD BYTES BACK, `git checkout -- <path>` is one command and it is a DECISION
    someone makes with the diff in front of them, rather than a thing that happens to them.
    """
    if _SNAP is None:
        return
    for rel in changed(_ROOT, _SNAP):
        _VIOLATIONS.setdefault(
            rel, (getattr(item, "nodeid", "?"),
                  "LEFT IN PLACE -- inspect with `git diff -- " + rel + "`"))


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:
    if not _VIOLATIONS:
        return
    w = terminalreporter
    w.write_sep("=", "PROTECTED ARTIFACTS WRITTEN BY THE SUITE (GAP 113)", red=True)
    for rel, (nodeid, did) in sorted(_VIOLATIONS.items()):
        w.write_line(f"  {rel}")
        w.write_line(f"    written by : {nodeid}")
        w.write_line(f"    protected  : {PROTECTED.get(rel, 'unstated')}")
        w.write_line(f"    action     : {did}")
    w.write_line("")
    w.write_line("  A test run is an OBSERVATION and must never be a write to the thing observed.")
    w.write_line("  THE FILES WERE LEFT EXACTLY AS FOUND. This fence detects and refuses; it does "
                 "not revert, because it cannot tell a test's write from a concurrent editor's "
                 "and reverting the latter destroys work that was never the suite's to touch.")
    w.write_line("  Read `git diff` on the paths above, then either point the offending call at "
                 "tmp_path or keep the change deliberately.")


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Fail the session on any protected write, including one that a green suite produced.

    Deliberately NOT folded into a test failure: the write is a property of the RUN, not of any
    one test, and attributing it to whichever test tripped it first would let a reordering make
    the failure look like it moved to a different subject.
    """
    if _VIOLATIONS and exitstatus == 0:
        session.exitstatus = 1
