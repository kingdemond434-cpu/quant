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

#: L1.50. Past this many days with no floor RAISED, the ratchet is reported as STALLED.
#:
#: Not an evidence gate, so L1.48 does not apply: this measures ELAPSED NEGLECT, not accumulated
#: proof, and there is no observation whose arrival would make a stalled ratchet acceptable. 14 days
#: is two full weekly cycles -- long enough that one busy week reads as normal, short enough that a
#: quarter cannot pass unremarked.
STALL_DAYS = 14.0


def days_since(iso: str | None) -> float | None:
    """Days since an ISO timestamp, or None if absent/unparseable.

    None means NOT MEASURED and must never be rendered as 0.0 (L1.28a). A record written before
    L1.50 has no `last_raised`, and a missing timestamp that read as "raised today" would give the
    oldest, most-stalled records the healthiest possible reading -- the exact inversion GAP #83
    found in `register_health`, where a register never driven once scored perfect.
    """
    if not iso:
        return None
    try:
        then = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:  # naive compares wrong against every aware stamp
        return None
    return max(0.0, (datetime.now(tz=UTC) - then).total_seconds() / 86400.0)


def stall_report(rec: dict) -> str:
    """L1.50: a floor that has not risen is a ratchet that has stopped.

    REPORTS, NEVER FAILS. A check that exits non-zero on a quiet day gets deleted, and a deleted
    check enforces nothing -- the same reasoning behind SLACK. Regression is CI's business;
    stagnation is the auditor's. A desk that cannot tell "you regressed" from "you stopped
    improving" ends up told neither.
    """
    age = days_since(rec.get("last_raised"))
    if age is None:
        return (
            "  L1.50 STALL: this record has never recorded a raise. That is not a clean "
            "reading -- it is an absent one, and the two must not look alike."
        )
    if age >= STALL_DAYS:
        return (
            f"  L1.50 STALL: no floor has RISEN in {age:.0f} days. The floors are holding, "
            "which is the minimum, not the target. 100% is the target; the gap below is the "
            "distance to it."
        )
    return f"  L1.50: last raise {age:.1f}d ago -- ratchet moving."


def gap_to_target(now: dict[str, float]) -> str:
    """Distance to 100%, printed every run. A floor is a MINIMUM; the target is the ceiling, and
    reporting only the floor lets a permanently-green desk read as a finished one."""
    return (
        f"  to 100%: repo needs +{100.0 - now['repo_pct']:.2f}pp, "
        f"money path +{100.0 - now['money_path_pct']:.2f}pp "
        f"(~{round((100.0 - now['money_path_pct']) / 100.0 * now['money_path_statements'])} "
        "uncovered statements on the code that can move funds)"
    )


def measure(report: dict) -> dict[str, float]:
    """(repo %, money-path %) from a coverage.py JSON report."""
    raw_files = report.get("files", {})
    files = (
        {str(path).replace("\\", "/"): details for path, details in raw_files.items()}
        if isinstance(raw_files, dict)
        else {}
    )
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
    ap.add_argument(
        "--update",
        action="store_true",
        help="RAISE the floors to what was just measured (never lowers)",
    )
    a = ap.parse_args()

    p = Path(a.report)
    if not p.is_absolute():
        p = ROOT / p
    try:
        report = json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"coverage-floors: cannot read {a.report} ({type(e).__name__}). Run pytest with "
            "--cov=libs --cov-branch --cov-report=json:coverage.json first."
        )
        return 1

    now = measure(report)
    rec = load_record()
    floors = dict(rec.get("high_water", {}))
    repo_floor = float(floors.get("repo_pct", 0.0))
    money_floor = float(floors.get("money_path_pct", 0.0))

    print(
        f"coverage-floors: repo {now['repo_pct']}% (floor {repo_floor}%) | "
        f"money path {now['money_path_pct']}% over {now['money_path_statements']} stmts "
        f"(floor {money_floor}%)"
    )
    print(gap_to_target(now))
    print(stall_report(rec))

    breaches = []
    if now["repo_pct"] < repo_floor - SLACK:
        breaches.append(f"repo coverage {now['repo_pct']}% fell below its {repo_floor}% mark")
    if now["money_path_pct"] < money_floor - SLACK:
        breaches.append(
            f"MONEY PATH coverage {now['money_path_pct']}% fell below its {money_floor}% mark -- "
            "this is the code that places orders, and it is the one number a repo-wide average "
            "would have hidden"
        )

    if a.update:
        floors["repo_pct"] = max(repo_floor, now["repo_pct"])
        floors["money_path_pct"] = max(money_floor, now["money_path_pct"])
        # L1.50: `last_raised` moves ONLY when a floor actually rose. Stamping it on every
        # --update would make running the updater look identical to improving coverage, which is
        # GAP #85's error exactly -- an `n` that counts READINGS OF THE WORLD rather than events
        # in it, so diligence in running the audit becomes the mechanism by which it goes wrong.
        rose = (floors["repo_pct"] > repo_floor) or (floors["money_path_pct"] > money_floor)
        last_raised = datetime.now(tz=UTC).isoformat() if rose else rec.get("last_raised")
        RECORD.write_text(
            json.dumps(
                {
                    "_": (
                        "HIGH-WATER MARKS for test coverage. Raised by --update, NEVER lowered by code. "
                        "The money path is tracked separately because a repo-wide average lets order-"
                        "path coverage fall while research tests keep the aggregate up -- the average "
                        "hides exactly the number worth watching."
                    ),
                    "updated": datetime.now(tz=UTC).isoformat(),
                    "last_raised": last_raised,
                    "high_water": floors,
                    "measured": now,
                    "money_path_files": list(MONEY_PATH),
                    "slack_pp": SLACK,
                    "next_ceiling": (
                        "STILL money-path parity, and the gap is still the point. 41.6% -> 70.45% "
                        "(2026-08-06) against 92.46% repo-wide: the direction is right and the inversion "
                        "is not fixed. ~221 uncovered statements remain on the code that can place orders "
                        "and move funds, and the three defects found writing those tests -- a flatten leg "
                        "that could sell through zero, and GAP #49 wired into only one leg of a two-leg "
                        "trade -- were all in the untested part, which is the whole argument. Parity is "
                        "not the end either: the ceiling after it is the FAILURE branches specifically, "
                        "since every incident this desk has had came from an error path, not a happy one. "
                        "Per L1.50 the floor is the minimum and 100% is the target; the residue above is "
                        "named so it cannot be mistaken for work already done."
                    ),
                },
                indent=1,
            ),
            "utf-8",
        )
        print(
            f"  floors updated -> repo {floors['repo_pct']}% | "
            f"money path {floors['money_path_pct']}%"
            + ("  (RAISED)" if rose else "  (no raise -- last_raised unchanged)")
        )
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
