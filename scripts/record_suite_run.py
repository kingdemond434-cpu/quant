#!/usr/bin/env python3
"""INGEST A WHOLE-SUITE PYTEST RUN INTO THE SUITE RECORD (R0564, defect test-suite-passfail-*).

THE DEFECT THIS CLOSES, MEASURED 2026-08-20 01:03Z. `docs/research/test_suite_record.json` has
NEVER carried a `pass_fail` block, so `check_test_suite_pass_fail` has read UNMEASURED for its
whole life -- and the reason is not that nobody runs the suite. `scripts/run_ci.py` is the ONLY
producer of that block (it says so itself, and the defect text names it), and run_ci appears
NOWHERE in ops/crontab.manifest: it is a producer nothing invokes (III.16, built-never-wired).
Meanwhile the whole suite *does* run on this box -- at 00:18Z a 60-80 minute `pytest tests/ -q`
was live under /home/quant/run_suite_verdict.sh, appending its counts to a log file OUTSIDE the
repo and its exit code to a second one. The desk was spending an hour of box time producing
EXACTLY the observation the fence needs and then throwing the observation away.

So the missing piece was never a measurement. It was a PATH from a run that already happens to
the record that already knows how to hold it. That is this file, and it is deliberately tiny:

    .venv/bin/python scripts/record_suite_run.py --log /home/quant/suite_verdict_*.log
    .venv/bin/python -m pytest tests/ -q 2>&1 | tee /tmp/s.log; scripts/record_suite_run.py -

WHY A SEPARATE INGEST AND NOT "JUST RUN run_ci". Because the suite is 60-80 minutes and the box
has been measured refusing a second concurrent run for memory (R0407) -- so the run that is
ALREADY HAPPENING is the one whose verdict the desk should be banking, whoever launched it. A
recorder that only accepts runs it started itself would leave every hand-run and every
shell-script run unmeasured, which is the state this file exists to end.

THE REFUSAL PATH IS THE LOAD-BEARING PART (L1.41 condition 1), and it encodes a defect this desk
has now paid for three times (L0177, R0711). `docs/research/test_suite_record.json` is a PROTECTED
artifact: tests/conftest.py snapshots it before the first test and RESTORES it at teardown. So a
write landing while a suite is live IN THE SAME TREE is silently reverted -- the writer prints
success and persists nothing. This script therefore (a) refuses when it can see a live pytest in
the target tree, and (b) RE-READS its own write and fails loudly if the block is not there. A
same-run claim of a write is not the write.

IT RECORDS; IT DOES NOT GATE. A red suite exits 0 here, because a recorder that exits non-zero on
red gets wrapped in `|| true` at its call site and stops recording -- and then the desk is back to
UNMEASURED, which is strictly worse than a measured red (L1.28a). Grading is max_audit's job and
it already does it. Exit 2 is reserved for "I could not record", never for "the news is bad".

`--scan` IS WHAT MAKES IT SCHEDULABLE, and the schedulable version is the point. The suite is 60-80
minutes and the box has refused a second concurrent run for memory (R0407), so the collector must
be the CHEAP half: a few seconds, hourly, picking up whatever whole-suite run finished since the
last tick, whoever launched it. That is an L1.28c information-arrival cadence -- the fastest tick
that can carry new information, given the suite itself can only produce one every 80 minutes.

RE-INGESTING ONE LOG WOULD BE WORSE THAN NOT RUNNING, and the guard against it is not incidental.
`grade` calls a record STALE past 48h, so an hourly job that re-recorded the same ancient log
would stamp it `now` every hour and a suite last run in July would read as fresh forever -- a
fabricated freshness on the exact axis the fence exists to measure. `--scan` therefore records a
log only when it is NEWER than the run already on file, and says so when it declines.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
from libs.ops import suite_record  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402


def live_pytest_in(root: Path) -> list[int]:
    """PIDs of pytest processes whose cwd is `root`. Empty is a real answer; unreadable is not.

    Scanned through /proc rather than `pgrep`, because `pgrep -f pytest` self-matches any agent
    whose own command line mentions the word and, more to the point, cannot answer the question
    that actually decides this: not "is a suite running somewhere on the box" -- two trees run
    concurrently here all day -- but "is a suite running in THE TREE I AM ABOUT TO WRITE TO",
    which is the only one whose conftest can revert the write.
    """
    hits: list[int] = []
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return hits                      # no /proc: caller degrades to the post-write verify
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().decode("utf-8", "replace")
            if "pytest" not in cmdline:
                continue
            if (entry / "cwd").resolve() != root:
                continue
        except OSError:
            continue                     # vanished or not ours mid-scan; both are "not evidence"
        hits.append(int(entry.name))
    return hits


def newest_unrecorded(pattern: str, root: Path) -> tuple[Path | None, str]:
    """(newest suite log strictly newer than the recorded run, why-not). Never re-ingests.

    Newness is the LOG'S mtime against the recorded `at`, not against the wall clock: the question
    is "has a suite finished since the one on file", and answering it from the clock would re-stamp
    the same run every tick and publish a freshness the suite never had.
    """
    try:
        cands = sorted((p for p in Path(pattern).parent.glob(Path(pattern).name) if p.is_file()),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError as exc:
        return None, f"cannot scan {pattern} ({exc})"
    if not cands:
        return None, f"no suite log matches {pattern} -- nothing has been run, or it logs elsewhere"

    newest = cands[0]
    block = suite_record.read(root).get("pass_fail")
    if isinstance(block, dict):
        recorded = suite_record.hours_since(str(block.get("at", "")))
        log_age_h = (time.time() - newest.stat().st_mtime) / 3600.0
        if recorded is not None and log_age_h >= recorded:
            return None, (f"{newest.name} is {log_age_h:.1f}h old and the record already holds a "
                          f"run from {recorded:.1f}h ago -- already banked. Re-recording it would "
                          f"re-stamp an old run as fresh, which is the one lie this fence cannot "
                          f"afford (it grades staleness)")
    return newest, ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", default="-",
                    help="pytest output to read; '-' (default) reads stdin")
    ap.add_argument("--scan", default=None,
                    help="glob of suite logs; ingests the newest one that postdates the recorded "
                         "run, and exits 0 saying so when there is nothing new. The schedulable "
                         "form -- seconds, not the suite's 60-80 minutes")
    ap.add_argument("--source", default="record_suite_run",
                    help="who produced this run -- kept in the record so a reading can be traced")
    ap.add_argument("--root", default=str(_ROOT), help="tree whose record is written")
    ap.add_argument("--force", action="store_true",
                    help="write even with a live pytest in the tree. The write may be reverted "
                         "at that suite's teardown; the post-write verify still runs and still "
                         "fails, so this cannot make an unrecorded run look recorded")
    args = ap.parse_args()

    _law_guard()
    root = Path(args.root).resolve()

    source = args.source
    if args.scan:
        newest, why_not = newest_unrecorded(args.scan, root)
        if newest is None:
            # EXIT 0 WITH THE REASON PRINTED. "Nothing new to bank" is the normal state of an
            # hourly collector over an 80-minute suite; failing on it would make the job red most
            # of the day and it would be silenced (L1.43). The fence still reports UNMEASURED or
            # STALE if that is what the record actually says -- this line never speaks for it.
            print(f"nothing to record: {why_not}")
            return 0
        args.log, source = str(newest), f"{args.source}:{newest.name}"

    try:
        text = sys.stdin.read() if args.log == "-" else Path(args.log).read_text("utf-8", "replace")
    except OSError as exc:
        print(f"REFUSED: cannot read the run's output ({exc})", file=sys.stderr)
        return 2

    counts = suite_record.parse_summary(text)
    if counts is None:
        # NONE IS NOT ZERO (L1.55). A killed, hung or never-started run has no summary line, and
        # recording zeros for it would publish a perfect record for a suite that did not execute.
        # THE TWO CAUSES DEMAND OPPOSITE REPAIRS AND ARE REPORTED APART: re-run the suite, versus
        # fix the invocation that silenced its own output. Reported as one, an operator burns 80
        # minutes re-running a suite that already answered.
        if suite_record.completed_without_counts(text):
            print("REFUSED: that run FINISHED and printed no counts line -- pyproject's addopts "
                  "is already `-ra -q`, so an invocation adding its own `-q` reaches pytest as "
                  "`-qq`, which suppresses the terminal counts outright. Do NOT re-run the "
                  "suite; drop the redundant -q from whatever launched it (run_ci.py:108 and "
                  "/home/quant/run_suite_verdict.sh both carried it). The record stays "
                  "UNMEASURED, which is the honest state.", file=sys.stderr)
            return 2
        print("REFUSED: no parseable pytest summary line, and no sign the run reached its own "
              "end -- it was killed, hung, or has not finished. Recording zeros here would "
              "publish a clean record for a suite that never ran; UNMEASURED is the honest "
              "state and it stays.", file=sys.stderr)
        return 2

    live = live_pytest_in(root)
    if live and not args.force:
        print(f"REFUSED: pytest is live in {root} (pid(s) {live}). "
              f"{suite_record.RECORD_REL} is a PROTECTED artifact -- tests/conftest.py restores "
              f"it at that session's teardown, so this write would print success and persist "
              f"NOTHING (L0177/R0711, three recorded instances). Wait for that run to finish and "
              f"record ITS log instead, or pass --force and read the verify line.", file=sys.stderr)
        return 2

    block = suite_record.record_run(root, counts, source=source)

    # THE WRITE IS NOT THE CLAIM; THE RE-READ IS. Reverted-by-conftest, a read-only checkout and a
    # full disk all leave `record_run` returning a perfectly good dict over a file that does not
    # hold it. Nothing here is swallowed: every one of those exits 2 with the value it saw.
    landed = suite_record.read(root).get("pass_fail")
    if not isinstance(landed, dict) or landed.get("at") != block["at"]:
        print(f"FAILED: wrote the record but re-reading {suite_record.RECORD_REL} does not show "
              f"it (found {landed!r}). The suite's protected-artifact guard, a read-only tree or "
              f"a full disk -- the run stays UNMEASURED and the defect will fire.", file=sys.stderr)
        return 2

    status, detail = suite_record.grade(suite_record.read(root))
    print(f"recorded: {block['n_passed']} passed, {block['n_failed']} failed, "
          f"{block['n_skipped']} skipped, high-water {block['high_water_passed']}"
          + (f", red since {block['red_since']}" if block["red_since"] else ""))
    print(f"grade: {status} -- {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
