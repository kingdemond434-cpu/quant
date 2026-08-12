"""Local CI gate -- lint + tests + stress, in one command. Free (no cloud, no cost).

Runs ruff (lint) and the test suite, then the stress harness. Non-zero exit if anything fails, so
it can gate a commit or a deploy. This is the always-available substitute for hosted CI: correctness
of the survival-critical logic (hedge reconcile, risk controls, sizing, leverage) is checked
mechanically, not by hand.

NOTE (2026-07-18): the pytest step names specific files/dirs rather than the whole `tests/` tree
-- a full-tree collection currently fails on pre-existing duplicate test-module basenames across
directories (e.g. two unrelated `test_regime.py`, two unrelated `test_registry.py`; see GAP
register). `tests/execution/` (the risk-path/execution directory, incl. the live connector +
stage machine) was added to the gate 2026-07-18 since that code must never silently go untested;
other directories (risk/, portfolio/, features/, regime/, ...) are NOT yet gated here -- a real
open gap, tracked separately, not fixed by this comment.

    python scripts/run_ci.py
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root, so `libs`
# resolves only if the project happens to be pip-installed into the interpreter in use. The daily
# cycle invokes these by path. Without this the libs imports fail -- and in run_trade_forensics a
# broad `except Exception` caught exactly that and shipped {"error": "ModuleNotFoundError"} into
# the artifact, where an error string is indistinguishable from data to every reader downstream.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))


import contextlib
import fcntl
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from libs.ops.host_resources import mem_available_mb, pressure_note
from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_PY = venv_python(_ROOT)

# EVERY STEP IS WALL-CLOCK BOUNDED (2026-08-05). subprocess.run had no timeout, and on this gate
# that is not merely a slow run -- it is the gate silently switching itself off, permanently:
#
#   a step blocks (a network-bound test on a filtered-egress box does exactly this)
#     -> this process never exits, so it never releases the flock it holds
#     -> every later run_ci finds the lock taken and returns 0, "skipping", by design
#     -> .ci_last_run.json is never rewritten, so it stays frozen at its last value
#     -> max_audit only raises on `ok is False`, and a FROZEN marker is never false
#     -> the desk reports its safety gate GREEN, with nothing running behind it, indefinitely.
#
# That is the 2026-07-22 incident (81h of undetected red) through a different door, and the fix
# applied then -- surface a red marker -- cannot catch it, because this failure never produces a
# red marker. It produces a stale green one. Hence three independent repairs: bound the steps so
# a hang becomes a named FAIL here; keep writing the marker on that path so it goes red; and make
# max_audit treat a STALE marker as a defect in its own right (fail-closed -- unknown must never
# read as "no breach"). Any one alone leaves the hole open.
#
# Budgets are per-step and generous -- a ruin rail, not a performance target. They are sized off
# observed runtimes with a wide margin, so tripping one means "wedged", never "busy today".
#
# THE INNER BOUND MUST FIRE BEFORE THE OUTER ONE. daily_research_cycle.py runs this script under
# its own per-step timeout, and if that outer bound wins the race the process is killed from the
# outside: no [HUNG] line, no red marker written, nothing named -- which is the stale-green
# failure again, merely relocated. So the invariant is sum(_STEPS budgets) < the cycle's ci_gate
# budget, with the outer kept only as the backstop for what a Python-level timeout cannot catch
# (this interpreter itself wedging). tests/ops/test_ci_gate_timeouts.py asserts the ordering
# across both files, because it is exactly the kind of coupling that survives one edit and dies
# on the next -- the two numbers live in different files and nothing else relates them.
_STEPS = [
    ("lint (ruff)", [_PY, "-m", "ruff", "check", "scripts", "libs", "tests"], 300),
    # WHOLE TREE (2026-07-25): was 4 named files + tests/execution = ~147 of ~1099 tests, leaving
    # tests/risk (the ruin path) and tests/validation (the anti-false-positive path) ungated, and
    # every newly-shipped test ungated by default. GAP 31's stated blocker -- duplicate basenames
    # breaking collection -- EXPIRED once pyproject set --import-mode=importlib: the tree collects
    # and was run 100% GREEN this session (only optional-dep skips), so gating it is proven safe.
    # 7200s (2026-08-12): the full tree measured 60-80min under --cov in back-to-back runs
    # (cycle memory 2026-08-11), so the old 1800s budget tripped on every HONEST run -- the
    # marker read "HUNG >1800s" nightly and the gate was a wall no run could pass (L1.49).
    # 2h keeps the wide "wedged, never busy" margin over the 80min observation.
    ("tests (pytest)", [_PY, "-m", "pytest", "tests/", "-q"], 7200),
    # TYPES (2026-07-25): mypy --strict was configured in pyproject and run by NOBODY -- the
    # strictest tool in the repo was not in the gate, so nothing stopped a type regression
    # landing. Added the same day scripts/ entered its `files` list, because a type gate that
    # covers the money path but is never executed is not a gate.
    ("types (mypy)", [_PY, "-m", "mypy"], 600),
    ("stress harness", [_PY, "scripts/run_stress.py"], 600),
]
#: Worst-case wall clock if every step wedges. Read by the cycle-budget invariant test rather
#: than recomputed there, so the two cannot drift apart silently.
STEP_BUDGET_TOTAL_S = sum(b for _, _, b in _STEPS)  # 8700s


_LOCK = _ROOT / "data/.ci_run.lock"


def _acquire() -> IO[str] | None:
    """Take the CI lock, or return None if another run already holds it.

    Non-blocking on purpose: a second concurrent gate tests the same tree, so it adds no
    information while doubling peak RAM on a 3.8 GiB box with no swap -- where the OOM-killer's
    victim could be the dead-man rail. Declining beats queueing.
    """
    _LOCK.parent.mkdir(parents=True, exist_ok=True)
    fh = _LOCK.open("w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    fail_on_lock = "--fail-on-lock" in args
    _fh = _acquire()
    if _fh is None:
        # Another gate is mid-run on the same tree. For an ORGAN's routine gate, exit 0 and DO
        # NOT touch the marker: non-zero would fail its cycle for the non-error of someone else
        # already checking, and writing the marker here IS the last-writer-wins race.
        # For a DEPLOY decision that exit 0 is a lie -- pull_deploy read "skipped" as "green"
        # and would have shipped an unvetted commit (found 2026-07-31, R0145). --fail-on-lock
        # returns 3: "could not gate", which a deployer must treat as not-green and retry.
        if fail_on_lock:
            print("CI: another run holds the lock -- cannot gate this tree state (rc 3)")
            return 3
        print("CI: another run holds the lock -- skipping (marker left untouched)")
        return 0
    # RELEASE THE LOCK ON EVERY EXIT PATH. The handle was previously left open and reclaimed only
    # by process teardown -- invisible in production, but it meant this function could not be
    # called twice in one interpreter, which is why the gate's own failure paths had never been
    # executed by a test. A gate whose error handling has never run is a gate with an untested
    # ruin rail; closing the handle here is what made the [HUNG] path testable at all.
    try:
        return _run_steps()
    finally:
        _fh.close()


def _inflight_py() -> list[str]:
    """Untracked .py files under the gated roots -- a concurrent session's work in progress.

    This box runs several agent sessions against ONE working tree, so the steps above also judge
    whatever anyone happens to have half-written at that instant. Those failures belong to NO
    COMMIT, the session that observes them cannot fix them, and they clear on their own -- while a
    genuine failure in committed code sits inside the very same red verdict, indistinguishable.
    That is why `ci-gate-red` recurred 8x in 10.7d and why fixing the instance bought exactly one
    cycle. 2026-08-05, measured: all 5 lint errors and every pytest failure were another session's
    untracked files, while two REAL mypy errors in committed code sat buried underneath.
    """
    r = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "--",
                        "scripts", "libs", "tests"],
                       cwd=str(_ROOT), capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return []
    return sorted(p for p in r.stdout.split() if p.endswith(".py"))


def _scoped_to_tracked(label: str, cmd: list[str], inflight: list[str]) -> list[str] | None:
    """`cmd` re-expressed to skip the in-flight files, or None if this step cannot be scoped.

    None is the FAIL-SAFE answer: an unscopable step is attributed to committed code, so this
    attribution can only ever retract an alarm it has positively PROVEN belongs to scratch files.
    It can never hide a real one -- the only direction that matters on a safety gate.
    """
    if not inflight:
        return None
    if label.startswith("lint"):
        return [*cmd, "--extend-exclude", ",".join(inflight)]
    if label.startswith("tests"):
        return [*cmd, *(f"--ignore={p}" for p in inflight)]
    if label.startswith("types"):
        return [*cmd, "--exclude", "(" + "|".join(re.escape(p) for p in inflight) + ")"]
    return None


def _attribute(failed: list[str]) -> tuple[list[str], list[str]]:
    """Split `failed` into (committed-code failures, in-flight files seen).

    Paid for only when something already failed AND scratch files exist, so the normal green run
    costs nothing. A HUNG step is never re-run: its label carries a suffix so it will not match
    `_STEPS`, and re-running a step that just ate its whole budget to prove whose fault it is
    would double the wedge it is reporting.
    """
    inflight = _inflight_py() if failed else []
    if not inflight:
        return list(failed), []
    failed_tracked = []
    for label, cmd, budget in _STEPS:
        if label not in failed:
            continue
        scoped = _scoped_to_tracked(label, cmd, inflight)
        if scoped is None:
            failed_tracked.append(label)
            continue
        try:
            rr = subprocess.run(scoped, cwd=str(_ROOT), capture_output=True, text=True,
                                check=False, timeout=budget)
        except subprocess.TimeoutExpired:
            failed_tracked.append(label)
            continue
        if rr.returncode != 0:
            failed_tracked.append(label)
    failed_tracked += [s for s in failed if s not in {lab for lab, _, _ in _STEPS}]
    return failed_tracked, inflight


def _mem_available_mb() -> int | None:
    """MemAvailable in MB, or None where /proc is absent or unreadable.

    Delegates to the shared reader so this gate and max_audit's collection probe cannot drift into
    two different opinions about how much memory the box had when they died. None and 0 stay
    different answers there: "we could not measure" must never render as "there was no memory".
    """
    return mem_available_mb()


def _run_steps() -> int:
    failed: list[str] = []
    for label, cmd, budget in _STEPS:
        try:
            r = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True, text=True,
                               check=False, timeout=budget)
        except subprocess.TimeoutExpired:
            # A HANG IS A FAILURE, NOT A SLOW PASS. Naming it distinctly from an ordinary red
            # matters: "wedged" and "broken" have different first moves, and the operator who
            # reads this line should not have to guess which one they are looking at.
            print(f"[HUNG] {label}: exceeded {budget}s budget -- killed and counted as FAILED")
            failed.append(f"{label} (HUNG >{budget}s)")
            continue
        if r.returncode < 0:
            # KILLED BY A SIGNAL IS NOT A VERDICT ON THE CODE -- it is the same distinction the
            # HUNG branch above already draws, for the resource this box actually runs out of.
            # A negative returncode means the kernel (or an operator) killed the child before it
            # could report anything, so `failed.append(label)` below would file "the tests are
            # broken" on the strength of a process that never finished a test. Several agent
            # sessions share this 3.8GB box with the live daemons and there is NO SWAP, so a
            # concurrent run is enough for the OOM killer to take whichever pytest it likes;
            # measured 2026-08-05, max_audit's own probe recorded rc=-9 while the full suite
            # collected cleanly seconds later (rc=0, peak RSS 326MB, 19s).
            #
            # NOTHING IS LOOSENED. The step still enters `failed`, so the gate still exits
            # non-zero and the marker still writes ok=false; and because the suffixed label does
            # not match `_STEPS`, `_attribute` puts it straight into `failed_tracked` (line 195),
            # keeping tracked_ok False so max_audit's ci-gate-red still fires. On a safety gate
            # "unknown" reads as NOT-PROVEN-GREEN, never as fine. What changes is only WHAT THE
            # ALARM SAYS: max_audit prints failed_tracked verbatim, so the operator now reads the
            # cause and the first move instead of hunting a test failure that does not exist.
            # The suffix also means the step is never re-run -- re-running a memory-killed step
            # under the same pressure would double the shortage it is reporting, exactly the
            # reason the HUNG branch refuses a re-run.
            sig = -r.returncode
            # tmpfs occupancy rides along with MemAvailable because on this box it is the usual
            # CULPRIT and is invisible to every other memory check the desk owns: `/tmp` is a
            # tmpfs, so a previous run's leftover scratch is resident RAM belonging to no process.
            # Without it the operator reads "MemAvailable 189MB", finds no process holding the
            # rest, and has nowhere to go next.
            note = pressure_note()
            print(f"[KILLED] {label}: died on signal {sig} ({note}) -- counted as FAILED, but "
                  "this is a verdict on the BOX, not on the code")
            failed.append(f"{label} (KILLED sig{sig}, {note} -- box ran out of "
                          "resources mid-step, NOT a code failure; re-run when quiet)")
            continue
        ok = r.returncode == 0
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: {tail[0][:120]}")
        if not ok:
            failed.append(label)
    failed_tracked, inflight = _attribute(failed)
    stale = [s for s in failed if s not in failed_tracked]
    if stale:
        print(f"CI: {stale} fail ONLY on uncommitted files -> {inflight}")
        print("CI: not attributable to a commit; the author sees it, the desk does not")
    print("CI:", "ALL GREEN" if not failed else f"FAILED -> {failed}")
    if failed_tracked:
        print(f"CI: committed-code failures -> {failed_tracked}")
    # Freshest-truth CI status marker (2026-07-23): a red desk-wide gate sat undetected 81h
    # because the brain cycle that runs run_ci was quota-dead; max_audit now surfaces this
    # marker so a red gate always enters the escalation path. Additive; never affects the gate.
    with contextlib.suppress(OSError):
        (_ROOT / "data/.ci_last_run.json").write_text(
            # `ok`/`failed` keep their exact old meaning (whole tree) so every pre-existing reader
            # is untouched; `tracked_ok`/`failed_tracked`/`inflight` are ADDITIVE. Nothing is
            # swallowed -- scratch-file breakage is recorded here and printed above; it is just no
            # longer allowed to claim the desk-wide gate is down.
            # `killed` is ADDITIVE and carries no authority: the steps in it are already inside
            # `failed`/`failed_tracked`, so no existing reader changes behaviour and the gate
            # cannot be read as greener than it is. It exists so a future check can ask "did this
            # step report a verdict, or was it killed before it could?" structurally, instead of
            # matching on the label text.
            json.dumps({"ok": not failed, "ts": datetime.now(tz=UTC).isoformat(),
                        "failed": failed, "tracked_ok": not failed_tracked,
                        "failed_tracked": failed_tracked, "inflight": inflight,
                        "killed": [s for s in failed if "(KILLED sig" in s]}), "utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
