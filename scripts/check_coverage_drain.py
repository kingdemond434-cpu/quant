#!/usr/bin/env python3
"""THE COVERAGE-DRAIN FENCE -- the uncrawled backlog may fall, and may not rise.

    "close the gap between the information the desk could lawfully have and the information it
     actually holds, and keep it closed 24/7"                        -- the principal, 2026-09-23

WHAT THIS ASSERTS, AND THE ONE THING IT DELIBERATELY DOES NOT. `research/coverage_drain.py`
publishes four numbers every hour: how many registered sources have never been fetched, how long
the oldest has waited, how many are past the organ's own 24-hour lease, and how many the desk has
cumulatively drained. Three of them are ratcheted here:

  * `backlog_overdue`     may FALL, never RISE.   <- the failing metric
  * `oldest_wait_h`       may FALL, never RISE.
  * `drained_total`       may RISE, never FALL.

`uncrawled_total` is ALSO ratcheted, but it fails only when it rises in a pass that seeded no new
ground. That exception is the whole design and it is not a loophole. The drain's FIRST duty is to
register lawful ground the registry had never heard of -- every root forty-odd country packs
declare, every ground in `deep_forest_sources.json`, every row in the source registry. Doing that
RAISES the uncrawled count, because the count was low from ignorance rather than from coverage. A
fence that punished the rise would teach the next session to stop seeding, and the desk would
then report a beautiful backlog of zero while knowing less every week. So the metric that FAILS
is the one seeding cannot touch: a root registered this hour is not overdue; a root that has sat
for a day is, whatever put it there.

WHY A RATCHET AND NOT A THRESHOLD. A threshold has to be chosen, and whoever chooses it is
guessing at what "enough coverage" means for a universe nobody has enumerated. A ratchet needs no
number: it starts at whatever was FIRST MEASURED ON THIS TREE and refuses to let that go
backwards. The desk has broken itself once by inventing a floor it had not measured (CLAUDE.md,
the 8 GB/96 GB memory note), so a quantity with no previous reading ENTERS at its measurement and
is never invented at zero.

UNMEASURED IS A VERDICT (L1.28a). On a clean checkout there is no registry and no report; this
fence says UNMEASURED and exits 0, because "this machine has no desk state" is not "a law was
broken". On the box, where the state is real, `--require-state` promotes an absent report to a
failure -- an organ that was scheduled and produced nothing is exactly the defect L1.49 names.

THIS FENCE CAPS NOTHING. It subtracts no crawl, no worker and no second from any forest. It reads
a report and compares two numbers (GROWTH_GOVERNANCE Rule 1: a mechanism that only ever says
"this got worse" costs no growth and is not a brake).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "COVERAGE_DRAIN.json"
LEDGER = DESK / "data" / "coverage_drain_ledger.json"
AUDIT = DESK / "reports" / "coverage_drain_fence.json"

#: The three ratcheted quantities and the direction each is allowed to move.
CEILINGS: tuple[str, ...] = ("backlog_overdue", "oldest_wait_h")
FLOORS: tuple[str, ...] = ("drained_total",)
#: Float noise only. A ratchet is not a band: a real move of any size is the verdict.
EPS = 1e-6
#: How old a report may be before the fence stops treating it as this hour's measurement. The
#: organ is an hourly leg, so three hours is two missed passes -- a schedule problem, not a
#: coverage problem, and it is named as such rather than counted as a backlog rise.
STALE_H = 3.0

RULE = ("the overdue uncrawled backlog and the oldest wait ratchet DOWN, the cumulative drained "
        "count ratchets UP, and the headline uncrawled count may rise only in a pass that "
        "registered new lawful ground; every refusal is a permanent registered fact")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str),
                   encoding="utf-8")
    os.replace(tmp, path)


def _age_h(stamp: Any, now: datetime | None = None) -> float | None:
    text = str(stamp or "").strip()
    if not text:
        return None
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return ((now or datetime.now(tz=UTC)) - at).total_seconds() / 3600.0


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def judge(*, report: Path | None = None, ledger: Path | None = None,
          require_state: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """PASS / FAIL / UNMEASURED, with every comparison printed.

    PATHS ARE RESOLVED AT CALL TIME rather than bound as defaults, so a test can point the fence
    at a scratch tree. A fence that can only be run against the live ledger is a fence that gets
    tested against the live ledger, or not at all.
    """
    rpt_path = report or REPORT
    led_path = ledger or LEDGER
    doc = _read(rpt_path)
    out: dict[str, Any] = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                           "report": str(rpt_path), "ledger": str(led_path), "rule": RULE,
                           "checks": [], "reasons": [], "verdict": "UNMEASURED"}
    if not isinstance(doc, Mapping):
        out["why"] = (f"{rpt_path} is absent or unreadable: the coverage drain has not run on "
                      "this host. UNMEASURED is a real answer and it is not a pass.")
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        if require_state:
            out["reasons"].append(out["why"])
        return out

    age = _age_h(doc.get("at"), now)
    out["report_age_h"] = None if age is None else round(age, 2)
    if doc.get("status") == "UNMEASURED":
        out["why"] = str((doc.get("verdict") or {}).get("what")
                         or "the organ could not read the registry on this host")
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        if require_state:
            out["reasons"].append(f"the drain ran and measured nothing: {out['why']}")
        return out

    measured = doc.get("measured")
    if not isinstance(measured, Mapping):
        out["why"] = "the report carries no `measured` block; nothing to ratchet"
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        if require_state:
            out["reasons"].append(out["why"])
        return out

    prev = _read(led_path)
    prev_ceil = dict((prev or {}).get("ceilings") or {}) if isinstance(prev, Mapping) else {}
    prev_floor = dict((prev or {}).get("floors") or {}) if isinstance(prev, Mapping) else {}
    seeded = int(doc.get("seeded_this_pass") or 0)

    for key in CEILINGS:
        cur, old = _num(measured.get(key)), _num(prev_ceil.get(key))
        row = {"metric": key, "direction": "may fall, never rise", "current": cur,
               "ceiling": old}
        if cur is None:
            row["state"] = "UNMEASURED"
            row["why"] = f"{key} was not measured this pass"
        elif old is None:
            row["state"] = "FIRST"
            row["why"] = (f"no previous reading on this tree; the ceiling enters at {cur}, which "
                          "is what was measured and never an invented zero")
        elif cur > old + EPS:
            row["state"] = "OVER"
            row["why"] = (f"{key} rose from its ceiling {old} to {cur}: the desk is falling "
                          "further behind the ground it already owns")
            out["reasons"].append(row["why"])
        else:
            row["state"] = "OK"
            row["why"] = f"{key} {cur} <= ceiling {old}"
        out["checks"].append(row)

    for key in FLOORS:
        cur, old = _num(measured.get(key)), _num(prev_floor.get(key))
        row = {"metric": key, "direction": "may rise, never fall", "current": cur, "floor": old}
        if cur is None:
            row["state"] = "UNMEASURED"
            row["why"] = f"{key} was not measured this pass"
        elif old is None:
            row["state"] = "FIRST"
            row["why"] = f"no previous reading on this tree; the floor enters at {cur}"
        elif cur < old - EPS:
            row["state"] = "UNDER"
            row["why"] = (f"{key} fell from its floor {old} to {cur}: a cumulative count cannot "
                          "fall, so the ledger was reset or the organ lost its history")
            out["reasons"].append(row["why"])
        else:
            row["state"] = "OK"
            row["why"] = f"{key} {cur} >= floor {old}"
        out["checks"].append(row)

    cur, old = _num(measured.get("uncrawled_total")), _num(prev_ceil.get("uncrawled_total"))
    row = {"metric": "uncrawled_total", "current": cur, "ceiling": old, "seeded": seeded,
           "direction": "may rise ONLY in a pass that registered new lawful ground"}
    if cur is None or old is None:
        row["state"] = "FIRST" if cur is not None else "UNMEASURED"
        row["why"] = ("no previous reading on this tree" if cur is not None
                      else "the uncrawled count was not measured this pass")
    elif cur > old + EPS and seeded <= 0:
        row["state"] = "OVER"
        row["why"] = (f"the uncrawled count rose from {old} to {cur} in a pass that registered "
                      "NO new ground: the backlog grew without the desk learning anything")
        out["reasons"].append(row["why"])
    elif cur > old + EPS:
        row["state"] = "SEEDED"
        row["why"] = (f"the uncrawled count rose from {old} to {cur} because this pass registered "
                      f"{seeded} newly known lawful ground(s); that is the organ working, and "
                      "the overdue ratchet above is what holds it to account")
    else:
        row["state"] = "OK"
        row["why"] = f"uncrawled_total {cur} <= ceiling {old}"
    out["checks"].append(row)

    if age is not None and age > STALE_H:
        note = (f"the report is {age:.1f}h old (> {STALE_H:.0f}h): the drain leg is not running "
                "on its clock. This is a SCHEDULE defect, named here and not counted as a "
                "backlog rise -- a stale number is not a worse number.")
        out["checks"].append({"metric": "freshness", "state": "STALE", "why": note,
                              "age_h": round(age, 2)})
        if require_state:
            out["reasons"].append(note)

    out["verdict"] = "FAIL" if out["reasons"] else "PASS"
    out["backlog"] = dict(doc.get("backlog") or {})
    out["largest_gap"] = dict(doc.get("verdict") or {})
    out["why"] = (f"{len(out['reasons'])} ratchet breach(es)" if out["reasons"]
                  else "every ratcheted quantity moved in its allowed direction")
    return out


def render(doc: Mapping[str, Any]) -> list[str]:
    """The fence in five lines: verdict, each ratchet, and the day's largest gap."""
    lines = [f"coverage drain: {doc.get('verdict')} -- {doc.get('why')}"]
    for row in doc.get("checks") or ():
        lines.append(f"  [{row.get('state')}] {row.get('metric')}: {row.get('why')}")
    gap = doc.get("largest_gap") or {}
    if gap:
        lines.append(f"  LARGEST GAP {gap.get('gap')} (EV {gap.get('ev')}): {gap.get('what')}")
        lines.append(f"    fix: {gap.get('fix')}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument("--require-state", action="store_true",
                    help="box mode: an absent or stale report is a FAILURE, not UNMEASURED")
    ap.add_argument("--report", default=None)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--audit", default=str(AUDIT))
    ap.add_argument("--json", action="store_true", help="print the verdict document")
    args = ap.parse_args(argv)

    doc = judge(report=Path(args.report) if args.report else None,
                ledger=Path(args.ledger) if args.ledger else None,
                require_state=bool(args.require_state))
    if args.json:
        print(json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    else:
        for line in render(doc):
            print(line)
    if args.audit:
        with suppress(OSError):
            _write(Path(args.audit), doc)
    return 1 if doc["verdict"] == "FAIL" else 0


__all__ = ["CEILINGS", "EPS", "FLOORS", "RULE", "STALE_H", "judge", "main", "render"]


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())
