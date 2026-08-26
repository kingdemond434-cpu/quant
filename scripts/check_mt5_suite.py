#!/usr/bin/env python3
"""THE MT5 DESK'S TESTS HAVE NEVER BEEN RUN BY ANYTHING. This is the organ that runs them.

MEASURED 2026-08-26, and it is the reason every other defect this cycle survived:

    grep -rl "desks/mt5/tests" over the repo, ops/gates.sh, ops/githooks and every systemd unit
    returns NOTHING. `testpaths = ["tests"]`, so `pytest` never collects them; `ops/gates.sh`
    runs `pytest --co -q tests/`; ruff and mypy both list `desks/mt5` in `exclude`.

So the desk holding the money path -- the shadow engine, the promoter, the risk sizer, the
gauntlet -- is outside ruff, outside mypy, outside collection and outside the suite. Thirty of its
tests were failing when this was written, including eleven in `test_risk_units` that were red
because live position sizing could not price a stop in account currency, and two look-ahead guards
that ERROR rather than run. Nothing had ever reported any of it. A gate that never ran is a claim
the desk cannot cash (L1.49).

WHY A RATCHET AND NOT A BLOCKING GATE. Turning thirty red tests into a hard gate blocks every push
desk-wide, which this desk has already paid for once (R0688). The floor is today's count; it may
only FALL. A new failure fails the gate immediately, and an improvement lowers the floor
automatically so it can never be given back. That converts thirty invisible failures into thirty
visible ones plus a hard stop on the thirty-first, without stopping the desk for a day.

COLLECTION ERRORS ARE COUNTED SEPARATELY AND FLOORED AT ZERO. A failing test is one test; a
collection error silently removes a whole FILE from the run, so a rising error count hides an
unknown number of failures behind it, and the desk has lost real fixes to exactly that.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

BASE = Path(__file__).resolve().parent.parent
SUITE = BASE / "desks" / "mt5" / "tests"
FLOOR = BASE / "data" / "mt5_suite_floor.json"
REPORT = BASE / "desks" / "mt5" / "reports" / "mt5_suite.json"

def run_suite(timeout: int) -> tuple[dict[str, int], list[str], str]:
    """Counts from pytest's MACHINE-READABLE report, never from its terminal text.

    The first version of this parsed the summary line and reported "no tests at all" over a run
    of 730. `addopts` in pyproject already carries `-q`, so passing another made it `-qq` and
    pytest suppressed the counts line entirely -- an absence that reads exactly like a suite that
    never ran, which is the precise failure class this organ exists to catch. junit-xml carries
    the counts as attributes and cannot be turned off by a verbosity flag.
    """
    names: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "junit.xml"
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(SUITE), "--tb=no", "-p", "no:cacheprovider",
             f"--timeout={timeout}", f"--junitxml={report}"],
            cwd=BASE, capture_output=True, text=True, timeout=timeout + 300, check=False)
        tail = "\n".join((proc.stdout or "").strip().splitlines()[-3:])
        if not report.exists():
            return {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "total": 0}, [], tail
        root = ElementTree.parse(report).getroot()
        suites = root.findall("testsuite") or ([root] if root.tag == "testsuite" else [])
        counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "total": 0}
        for node in suites:
            total = int(node.get("tests") or 0)
            failed = int(node.get("failures") or 0)
            errors = int(node.get("errors") or 0)
            skipped = int(node.get("skipped") or 0)
            counts["total"] += total
            counts["failed"] += failed
            counts["error"] += errors
            counts["skipped"] += skipped
            counts["passed"] += total - failed - errors - skipped
        for case in root.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                cls = (case.get("classname") or "").strip()
                names.append(f"{cls}::{case.get('name')}" if cls else str(case.get("name")))
    return counts, sorted(set(names)), tail


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=int, default=900, help="per-test timeout in seconds")
    ap.add_argument("--set-floor", action="store_true",
                    help="seed the floor from this run (first run only)")
    args = ap.parse_args()

    if not SUITE.is_dir():
        print(f"FAIL: {SUITE} is absent -- that is not a suite with nothing to run (L1.28a)")
        return 1

    counts, failing, tail = run_suite(args.timeout)
    if not counts["total"]:
        print(f"FAIL: the suite reported no tests at all. Last lines:\n{tail}")
        return 1

    floor = _read(FLOOR)
    known = set(floor.get("known_failing") or [])
    seeded = args.set_floor or "known_failing" not in floor
    now = datetime.now(UTC).isoformat(timespec="seconds")

    # NAMES, NOT A COUNT. The count moved 30 <-> 31 across two identical runs on this live tree,
    # so a `>` comparison would alarm on noise -- and worse, a count is blind to a SWAP: one test
    # fixed while another breaks reads as "no change" and the new red never surfaces. A name set
    # catches the swap, survives the flake as a named row a reader can judge, and says WHICH.
    new_red = sorted(set(failing) - known)
    now_green = sorted(known - set(failing))

    verdict, reasons = "OK", []
    if seeded:
        reasons.append(f"floor seeded with {len(failing)} known-failing test(s)")
        known = set(failing)
    else:
        if new_red:
            verdict = "FAIL"
            reasons.append(f"{len(new_red)} NEW failing test(s) on the money path: "
                           + "; ".join(new_red[:6]))
        if now_green:
            reasons.append(f"{len(now_green)} test(s) now pass and are struck from the floor "
                           f"-- a ratchet never gives ground back: " + "; ".join(now_green[:6]))
        # The floor only ever loses names. A new red is REPORTED, never absorbed: absorbing it
        # here would let the next run call the same breakage "known".
        known = known - set(now_green)

    if verdict == "OK":
        FLOOR.write_text(json.dumps({
            "known_failing": sorted(known), "measured_at": now,
            "passed_at_measure": counts["passed"], "total_at_measure": counts["total"],
            "command": "python scripts/check_mt5_suite.py",
            "why": ("desks/mt5 is excluded from ruff, mypy and testpaths, so NOTHING else runs "
                    "these. A name may only leave this list; a name arriving is a new red."),
        }, indent=1) + "\n", "utf-8")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "checked_at": now, "verdict": verdict, "counts": counts,
        "new_failing": new_red, "newly_passing": now_green,
        "known_failing": sorted(known), "reasons": reasons, "pytest_tail": tail,
    }, indent=1) + "\n", "utf-8")

    print(f"mt5 suite: {counts['passed']} passed, {counts['failed']} failed, "
          f"{counts['error']} error(s), {counts['skipped']} skipped "
          f"({len(known)} on the floor)")
    for line in reasons:
        print(f"  {line}")
    print(verdict)
    return 1 if verdict == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
