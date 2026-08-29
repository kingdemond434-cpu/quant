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
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECORD = ROOT / "docs/research/COVERAGE_RATCHET.json"

#: The files that can PLACE ORDERS or MOVE FUNDS. Kept explicit rather than globbed: a new venue
#: adapter must be added here deliberately, because the alternative is a money-path file that
#: silently escapes the floor by not matching a pattern.
#:
#: POINTED AT THE LIVE UNIVERSE 2026-08-29 (gap-fixer). Until this edit all five entries were
#: `libs/execution/binance_*` -- the RETIRED crypto adapters, which LAWS §1 forbids ever running
#: again. So the number every session read at the top of its context, "money path 89.44%", was
#: measured entirely over code that can never execute, while `desks/mt5/mt5desk/gateway.py`
#: (1510 lines, FOUR `mt5.order_send` call sites, `close_positions`, `manage_open_positions`)
#: and `libs/execution/broker.py` (`place_order`/`cancel_order`) were in no floor at all.
#: The explicit-not-globbed reasoning above was right and still is; what nobody did was update
#: the list when the principal changed the universe on 2026-08-18. A guard aimed at retired
#: ground reads healthy forever -- the WS-005 class, on the money path.
MONEY_PATH = (
    "libs/execution/broker.py",
    "libs/execution/staging.py",
)

#: LIVE money path that CANNOT BE EXECUTED ON THIS HOST, path -> the structural reason.
#:
#: These are reported as UNMEASURABLE by name every run and are NEVER folded into the
#: percentage (L1.28a: unmeasured is a real answer, and it must not render as either a pass or
#: a zero). They are also not a breach: a fence that is red from day one with no action that
#: could ever clear it gets ignored and then deleted (L1.43), and an unclosable red is how a
#: real one stops being read. The verdict is "unmeasurable HERE", which names the host where it
#: could be measured -- that is a build request, not a failure.
MONEY_PATH_UNMEASURABLE_HERE = {
    "desks/mt5/mt5desk/gateway.py": (
        "imports MetaTrader5 at module scope and that package is Windows-only, so no line of it "
        "executes on this Linux box. The desk's own tests know: desks/mt5/tests/test_risk_units.py "
        "does `_SRC = (_DESK / 'mt5desk' / 'gateway.py').read_text()` and AST-extracts the pure "
        "helpers, commenting 'gateway.py imports MetaTrader5'. That is a sound adaptation and the "
        "tests are real, but it means STATEMENT coverage of the live order path is 0% here and "
        "structurally so. Measurable only on the Windows terminal host."
    ),
}

#: RETIRED universe (LAWS §1, principal 2026-08-18/2026-08-25). Kept, never deleted: its
#: high-water mark is a real ratchet the desk earned and deleting the population would be the
#: denominator trick. Measured and reported SEPARATELY so a healthy retired number can never
#: stand in for the live one again -- which is exactly what it had been doing.
MONEY_PATH_RETIRED = (
    "libs/execution/binance_live.py",
    "libs/execution/binance_testnet.py",
    "libs/execution/binance_spot_live.py",
    "libs/execution/binance_spot_testnet.py",
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


def stall_report(rec: dict[str, Any]) -> str:
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


def gap_to_target(now: dict[str, Any]) -> str:
    """Distance to 100%, printed every run. A floor is a MINIMUM; the target is the ceiling, and
    reporting only the floor lets a permanently-green desk read as a finished one."""
    # NEVER CLAIM COMPLETENESS OVER A PARTIAL POPULATION (gap-fixer 2026-08-29). At 100% of the
    # measurable files this printed "~0 uncovered statements on the code that can move funds"
    # while `desks/mt5/mt5desk/gateway.py` -- 1510 lines and four `mt5.order_send` call sites --
    # sat in MONEY_PATH_UNMEASURABLE_HERE, executed by nothing. A gap-to-target that silently
    # omits the biggest order-placing file in the repo is the same false green this whole
    # module was just repointed to stop telling.
    unmeasurable = sorted(MONEY_PATH_UNMEASURABLE_HERE)
    tail = (
        f" -- and {len(unmeasurable)} live money-path file(s) are NOT in that count at all "
        f"({', '.join(unmeasurable)}): unmeasurable on this host, so the true remaining gap is "
        "strictly larger than the number above and is UNKNOWN, not zero"
        if unmeasurable
        else ""
    )
    return (
        f"  to 100%: repo needs +{100.0 - now['repo_pct']:.2f}pp, "
        f"money path +{100.0 - now['money_path_pct']:.2f}pp "
        f"(~{round((100.0 - now['money_path_pct']) / 100.0 * now['money_path_statements'])} "
        f"uncovered statements on the measurable part of the code that can move funds){tail}"
    )


def measure(report: dict[str, Any]) -> dict[str, Any]:
    """(repo %, money-path %) from a coverage.py JSON report."""
    raw_files = report.get("files", {})
    files = (
        {str(path).replace("\\", "/"): details for path, details in raw_files.items()}
        if isinstance(raw_files, dict)
        else {}
    )
    stmts = covered = 0
    attempted = 0
    missing: list[str] = []
    for rel in MONEY_PATH:
        # EVERY DISCARD IS COUNTED (L2.4/L1.60). `attempted` is incremented BEFORE the guard, and
        # an absent module is NAMED rather than skipped. The bug this closes: a money-path file
        # that stops appearing in the report -- renamed, its test file deleted, or the run dying
        # before it imports -- used to leave the numerator AND the denominator, so money_path_pct
        # ROSE while a fifth of the order path went dark, and the L1.50 ratchet then locked that
        # inflated floor in permanently. The denominator has to say how many it lost.
        attempted += 1
        s = files.get(rel, {}).get("summary")
        if not s:
            missing.append(rel)
            continue
        stmts += int(s["num_statements"])
        covered += int(s["covered_lines"])
    # The RETIRED population, measured on its own so its (earned, real) number can never be
    # printed as though it described the live order path.
    r_stmts = r_covered = 0
    r_missing: list[str] = []
    for rel in MONEY_PATH_RETIRED:
        s = files.get(rel, {}).get("summary")
        if not s:
            r_missing.append(rel)
            continue
        r_stmts += int(s["num_statements"])
        r_covered += int(s["covered_lines"])

    return {
        "repo_pct": round(float(report["totals"]["percent_covered"]), 2),
        "money_path_pct": round(100.0 * covered / stmts, 2) if stmts else 0.0,
        "money_path_statements": stmts,
        "money_path_attempted": attempted,
        "money_path_measured": attempted - len(missing),
        "money_path_missing": missing,
        "money_path_unmeasurable_here": sorted(MONEY_PATH_UNMEASURABLE_HERE),
        "money_path_retired_pct": (
            round(100.0 * r_covered / r_stmts, 2) if r_stmts else None
        ),
        "money_path_retired_statements": r_stmts,
        "money_path_retired_missing": r_missing,
    }


def load_record() -> dict[str, Any]:
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
    # SAID EVERY RUN, NEVER FOLDED INTO THE PERCENTAGE. A live money-path file the host cannot
    # execute is UNMEASURED, and unmeasured must not render as a pass or as a zero (L1.28a).
    for rel in now["money_path_unmeasurable_here"]:
        print(f"  UNMEASURABLE HERE: {rel} -- {MONEY_PATH_UNMEASURABLE_HERE[rel]}")
    if now["money_path_retired_pct"] is not None:
        print(
            f"  retired (LAWS §1, cannot execute): {now['money_path_retired_pct']}% over "
            f"{now['money_path_retired_statements']} stmts -- reported apart from the live "
            "figure on purpose; until 2026-08-29 this WAS the figure"
        )
    print(gap_to_target(now))
    print(stall_report(rec))

    # A FLOOR IS ONLY COMPARABLE AGAINST THE POPULATION THAT EARNED IT (gap-fixer 2026-08-29).
    # This is the general form of the bug found today: MONEY_PATH was changed by the principal's
    # universe order on 2026-08-18 in every sense except the list, and nothing anywhere compared
    # the list the floor was earned over against the list being measured. Silently comparing a
    # NEW population to an OLD floor is meaningless in both directions -- it invents a breach if
    # the new set is younger, and it certifies a pass if the new set is easier. Neither is a
    # measurement. So: detect the change, refuse to treat the inherited floor as binding, and
    # make the migration an explicit act with the old population recorded beside its number.
    recorded_pop = list(rec.get("money_path_files", []))
    population_changed = bool(recorded_pop) and recorded_pop != list(MONEY_PATH)
    if population_changed:
        gone = [f for f in recorded_pop if f not in MONEY_PATH]
        added = [f for f in MONEY_PATH if f not in recorded_pop]
        print(
            f"  POPULATION CHANGED: the {money_floor}% floor was earned over "
            f"{len(recorded_pop)} file(s), this run measured {len(MONEY_PATH)}. "
            f"Left: {', '.join(gone) or 'none'}. Joined: {', '.join(added) or 'none'}. "
            "The inherited floor is NOT binding on a different population and is not being "
            "compared; --update migrates it, preserving the old number with the files that "
            "earned it. Nothing is lowered -- the old floor keeps its own key."
        )

    breaches = []
    if now["money_path_missing"]:
        # A SHRINKING DENOMINATOR IS NOT AN IMPROVEMENT (L1.60). Absent modules leave both sides
        # of the ratio, so the percentage RISES as the money path goes dark. Refuse the reading
        # outright rather than compare a subset against a floor earned by the whole set.
        breaches.append(
            f"MONEY PATH UNMEASURED: {len(now['money_path_missing'])} of "
            f"{now['money_path_attempted']} module(s) absent from the coverage report "
            f"({', '.join(now['money_path_missing'])}). The {now['money_path_pct']}% above is "
            "over the SURVIVORS only -- an absent module leaves numerator and denominator "
            "together, so this number rises as the order path goes dark. Run pytest over the "
            "whole tree, or fix the path in MONEY_PATH if a module moved."
        )
    if now["repo_pct"] < repo_floor - SLACK:
        breaches.append(f"repo coverage {now['repo_pct']}% fell below its {repo_floor}% mark")
    if not population_changed and now["money_path_pct"] < money_floor - SLACK:
        breaches.append(
            f"MONEY PATH coverage {now['money_path_pct']}% fell below its {money_floor}% mark -- "
            "this is the code that places orders, and it is the one number a repo-wide average "
            "would have hidden"
        )

    if a.update and now["money_path_missing"]:
        # The ratchet is permanent, so a floor raised from a partial measurement is a permanent
        # error. Refuse to write rather than lock in a number earned by a smaller money path.
        print("  REFUSING --update: the money-path measurement is missing "
              f"{len(now['money_path_missing'])} module(s); a floor raised from a shrinking "
              "denominator can never be lowered again (L1.50/L1.60)")
        return 1

    if a.update:
        floors["repo_pct"] = max(repo_floor, now["repo_pct"])
        if population_changed:
            # PRESERVE, THEN ESTABLISH. The old number is archived beside the exact files that
            # earned it -- deleting it would be the denominator trick -- and the new population
            # is floored on its FIRST measurement (L2.0), which is what a first measurement is
            # for. `max()` across populations is the one thing that must not happen: it would
            # pin an unrelated set to a bar it never ran against.
            floors["superseded_money_path"] = {
                "pct": money_floor,
                "files": recorded_pop,
                "retired_on": datetime.now(tz=UTC).isoformat(),
                "why": (
                    "LAWS §1 (principal 2026-08-18/25) retired this universe; these files cannot "
                    "execute again, so their coverage cannot describe the live order path."
                ),
            }
            floors["money_path_pct"] = now["money_path_pct"]
        else:
            floors["money_path_pct"] = max(money_floor, now["money_path_pct"])
        # L1.50: `last_raised` moves ONLY when a floor actually rose. Stamping it on every
        # --update would make running the updater look identical to improving coverage, which is
        # GAP #85's error exactly -- an `n` that counts READINGS OF THE WORLD rather than events
        # in it, so diligence in running the audit becomes the mechanism by which it goes wrong.
        # A MIGRATION IS NOT A RAISE. Stamping `last_raised` because a new population happened
        # to measure higher than the old one would restart the L1.50 stall clock on an
        # accounting change -- the ratchet would read as "moving" while nothing improved.
        rose = (floors["repo_pct"] > repo_floor) or (
            not population_changed and floors["money_path_pct"] > money_floor
        )
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
