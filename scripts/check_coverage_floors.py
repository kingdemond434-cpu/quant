#!/usr/bin/env python3
"""COVERAGE FLOORS, RATCHETED -- and the money path carries its own.

WHY THIS EXISTS. `pytest-cov` has been a declared dev dependency and `[tool.coverage.run]` has
carried `branch = true` for as long as either has existed, and NOTHING EVER RAN THEM. CI invoked
bare `pytest`. The only `.coverage` file on disk was from a single hand-run six days earlier. So
the desk had coverage tooling installed, configured, and unmeasured -- the same built-but-never-
runs class as an order book recorded for weeks and never screened.

Measured for the first time on 2026-08-04: 88.1% repo-wide. That number is not the finding.

THE SHAPE IS THE FINDING, AND IT INVERTS THE RISK. The least-covered substantial code in the
repository is the code that can place orders and move funds:

    binance_live.py          29.9%   <- the LIVE order path, worst in the repo
    binance_spot_testnet.py  22.1%
    binance_spot_live.py     40.9%
    binance_testnet.py       40.5%
    ------------------------------
    money path combined      41.6%   against 88.1% everywhere else

That is backwards from where the care should be. A bug in a research script costs a wasted cycle;
a bug on the order path walks a short through zero into a +916,772 long, which is not hypothetical
-- it is in `_market_max_qty`'s docstring, and a defect in that exact function was found on
2026-08-04 sitting in the seventy percent nobody tests.

TWO FLOORS, NOT ONE. A single repo-wide number lets money-path coverage fall while a wave of
research tests keeps the aggregate up -- the average hides precisely the thing worth watching. So
the money path is measured separately and ratcheted separately.

RATCHET, NEVER A TARGET. Floors only rise. `--update` raises them to what was just measured;
nothing lowers them but a human editing the record with a reason, which is the same discipline
docs/research/LAW_COVERAGE.json applies to constitutional enforcement.

Reads a coverage JSON report. Writes the ratchet record. Exits 1 if a floor is breached.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECORD = ROOT / "docs/research/COVERAGE_RATCHET.json"

#: The files that can PLACE ORDERS or MOVE FUNDS. Kept explicit rather than globbed: a new venue
#: adapter must be added here deliberately, because the alternative is a money-path file that
#: silently escapes the floor by not matching a pattern.
MONEY_PATH = (
    "libs/execution/binance_live.py",
    "libs/execution/binance_testnet.py",
    "libs/execution/binance_spot_live.py",
    "libs/execution/binance_spot_testnet.py",
    "libs/execution/staging.py",
)

#: Slack below the measured high-water mark, in percentage points. Coverage moves a little with
#: test ordering and optional-dependency skips, and a floor that fires on noise gets deleted --
#: which is worse than a floor set one point low.
SLACK = 1.0


def measure(report: dict) -> dict[str, float]:
    """(repo %, money-path %) from a coverage.py JSON report."""
    files = report.get("files", {})
    stmts = covered = 0
    for rel in MONEY_PATH:
        s = files.get(rel, {}).get("summary")
        if not s:
            continue
        stmts += int(s["num_statements"])
        covered += int(s["covered_lines"])
    return {
        "repo_pct": round(float(report["totals"]["percent_covered"]), 2),
        "money_path_pct": round(100.0 * covered / stmts, 2) if stmts else 0.0,
        "money_path_statements": stmts,
    }


def load_record() -> dict:
    try:
        return dict(json.loads(RECORD.read_text("utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default="coverage.json", help="coverage.py JSON report")
    ap.add_argument("--update", action="store_true",
                    help="RAISE the floors to what was just measured (never lowers)")
    a = ap.parse_args()

    p = Path(a.report)
    if not p.is_absolute():
        p = ROOT / p
    try:
        report = json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"coverage-floors: cannot read {a.report} ({type(e).__name__}). Run pytest with "
              "--cov=libs --cov-branch --cov-report=json:coverage.json first.")
        return 1

    now = measure(report)
    rec = load_record()
    floors = dict(rec.get("high_water", {}))
    repo_floor = float(floors.get("repo_pct", 0.0))
    money_floor = float(floors.get("money_path_pct", 0.0))

    print(f"coverage-floors: repo {now['repo_pct']}% (floor {repo_floor}%) | "
          f"money path {now['money_path_pct']}% over {now['money_path_statements']} stmts "
          f"(floor {money_floor}%)")

    breaches = []
    if now["repo_pct"] < repo_floor - SLACK:
        breaches.append(f"repo coverage {now['repo_pct']}% fell below its {repo_floor}% mark")
    if now["money_path_pct"] < money_floor - SLACK:
        breaches.append(
            f"MONEY PATH coverage {now['money_path_pct']}% fell below its {money_floor}% mark -- "
            "this is the code that places orders, and it is the one number a repo-wide average "
            "would have hidden")

    if a.update:
        floors["repo_pct"] = max(repo_floor, now["repo_pct"])
        floors["money_path_pct"] = max(money_floor, now["money_path_pct"])
        RECORD.write_text(json.dumps({
            "_": ("HIGH-WATER MARKS for test coverage. Raised by --update, NEVER lowered by code. "
                  "The money path is tracked separately because a repo-wide average lets order-"
                  "path coverage fall while research tests keep the aggregate up -- the average "
                  "hides exactly the number worth watching."),
            "updated": datetime.now(tz=UTC).isoformat(),
            "high_water": floors,
            "measured": now,
            "money_path_files": list(MONEY_PATH),
            "slack_pp": SLACK,
            "next_ceiling": (
                "money-path coverage at parity with the repo. It sits at 41.6% against 88.1% "
                "everywhere else, which is backwards: a bug in a research script costs a cycle, "
                "a bug on the order path walks a short through zero. Parity is not the end "
                "either -- the ceiling after it is coverage of the FAILURE branches specifically, "
                "since every incident this desk has had came from an error path, not a happy one."),
        }, indent=1), "utf-8")
        print(f"  floors updated -> repo {floors['repo_pct']}% | "
              f"money path {floors['money_path_pct']}%")
        return 0

    if breaches:
        for b in breaches:
            print(f"  BREACH: {b}")
        print("  Floors ratchet. Restore the coverage, or edit the record by hand with a reason.")
        return 1
    print("  both floors held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
