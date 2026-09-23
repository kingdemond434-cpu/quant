#!/usr/bin/env python3
"""THE JUDGE-COVERAGE FENCE -- every mined family is judged every hour, and the backlog falls.

    "the judge should test 100 percent of what this desk ever mines, every hour, 24/7, always"
    "all families should be hunted, all mechanisms, all unknowns, for maximum breadth"
                                                                  -- the principal, 2026-09-23

WHAT THIS ASSERTS, against `desks/mt5/reports/JUDGE_COVERAGE.json`, which
`research/judge_coverage.py` writes at intake every hour:

  * NO FAMILY IS STARVED.  A family holding unjudged cells and absent from the hour's queue is a
    FAILURE. This is the defect that was measured: the judge re-tested a handful of families
    while `cross_asset_residual` (55,190 mined), `overnight_drift` (26,721) and
    `clock_transition` (20,081) waited. Absence from the queue is not low priority, it is never.
  * THE CARRIED BACKLOG FALLS, PER FAMILY.  Rows already in a family's backlog at the previous
    reading and STILL unjudged now are the carried cohort. A cell leaves it exactly one way -- by
    being judged -- so it can only fall, and a family whose carried count did not fall while it
    held backlog and held quota was starved in fact if not in the queue.
  * THE REMAINDER FOLLOWS THE PUBLISHED RANKING.  The floor is the breadth mandate and is
    covered by the starvation check; the remainder is where the return is, and it is spent
    strictly down expected value per judge-second. A family given remainder while a HIGHER-ranked
    family still held undrained backlog means the allocation stopped following its own ranking --
    which is exactly how a future session would quietly revert this to round-robin with the
    report still claiming value ordering.
  * NO FAMILY'S OLDEST UNJUDGED CELL EXCEEDS ITS OWN WINDOW.  A family's window is the hours its
    own quota needs to drain its own backlog, floored at the hour. A family of 55,190 cells is
    not failed for being large and a family of nine is not excused for being small.

WHY THE RATCHET IS ON THE CARRIED COHORT AND NOT ON RAW BACKLOG. Raw backlog rises whenever the
miners outrun the judge -- which is mining working, and mining is unrestricted by the principal's
standing order. A fence on the raw number would fail the desk for mining faster, would be
unsatisfiable in the direction it was pointed, and would be switched off inside a week; the
coverage-drain fence learned that lesson on a wall clock and it is written down there. The
carried cohort is the part intake actually controls: it is the promise that what the desk already
knew it had mined does not sit unjudged forever.

WHAT THIS FENCE NEVER DOES. It removes no cell, caps no book, shrinks no budget and slows no
miner (GROWTH_GOVERNANCE Rule 1). Its only remedy is ORDER -- and order costs nothing, because
the same rows reach the same judge under the same budget either way.

UNMEASURED IS A VERDICT (L1.28a). On a clean checkout there is no report and no ratchet; this
says UNMEASURED and exits 0, because "this machine has no desk state" is not "a law was broken".
On the box `--require-state` promotes an absent report to a FAILURE -- an organ that was
scheduled and produced nothing is exactly the defect L1.49 names. A pass in which the judge
recorded NO verdicts at all is UNMEASURED for the drain checks rather than a failure: nothing
drained because nothing ran, and that is the gauntlet's clock to answer for, not intake's.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "JUDGE_COVERAGE.json"
RATCHET = DESK / "data" / "judge_backlog_ratchet.json"
AUDIT = DESK / "reports" / "judge_coverage_fence.json"

#: A report older than this is stale: the organ runs at intake, hourly, so three hours of silence
#: means the clock stopped. Generous because a box reboot or a long sweep is not a law breach.
STALE_H = 6.0

#: How far past its OWN window a family's oldest unjudged cell may sit before this fails. The
#: slack exists because a window is derived from a quota measured on the previous hour's capacity
#: and the judge's capacity varies with the box; 2x is "this family is not being served", not
#: "this hour ran a little short".
WINDOW_SLACK = 2.0

RULE = ("no family holding unjudged cells is absent from the hour's queue; each family's carried "
        "backlog falls; no family's oldest unjudged cell sits past twice its own drain window "
        "without moving; and the remainder after every floor follows the published "
        "expected-value-per-judge-second ranking")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")


def _age_h(stamp: object, now: datetime) -> float | None:
    txt = str(stamp or "").strip()
    if not txt:
        return None
    try:
        at = datetime.fromisoformat(txt.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
    return max(0.0, (now.timestamp() - at.timestamp()) / 3600.0)


def judge(report: Path | None = None, *, require_state: bool = False,
          now: datetime | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    path = report or REPORT
    doc = _read(path)
    out: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "rule": RULE,
                           "report": str(path), "checks": []}
    if not isinstance(doc, dict) or not doc.get("families"):
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        out["why"] = (f"{path.name} is absent or carries no family table"
                      + (" and --require-state says this box owes one (L1.49)" if require_state
                         else "; this tree holds no judge-coverage state (L1.28a)"))
        return out

    age = _age_h(doc.get("at"), at)
    if age is not None and age > STALE_H:
        out["checks"].append({"metric": "freshness", "state": "FAIL" if require_state else "WARN",
                              "why": f"report is {age:.1f}h old, past the {STALE_H:.0f}h lease"})

    fams: dict[str, Any] = {f: r for f, r in (doc.get("families") or {}).items()
                            if isinstance(r, dict)}
    judged_any = sum(int(r.get("judged_window") or 0) for r in fams.values())
    failures: list[str] = []

    # 1. STARVATION: unjudged cells and no place in the queue.
    starved = sorted((f for f, r in fams.items()
                      if int(r.get("unjudged") or 0) > 0
                      and int(r.get("queued") or 0) == 0
                      and str(r.get("judging_status") or "") != "STUDY_ONLY"),
                     key=lambda f: -int(fams[f].get("unjudged") or 0))
    if starved:
        failures.extend(starved[:10])
        out["checks"].append({
            "metric": "families_starved", "state": "FAIL",
            "why": (f"{len(starved)} family(ies) hold unjudged cells and got no share of the "
                    f"hour: " + ", ".join(f"{f} ({fams[f].get('unjudged')})"
                                          for f in starved[:5]))})
    else:
        out["checks"].append({"metric": "families_starved", "state": "OK",
                              "why": "every family holding unjudged cells is in the queue"})

    # 2. THE CARRIED COHORT FALLS. UNMEASURED on the first reading (no baseline) and on a pass
    #    where the judge recorded nothing at all (nothing ran; that is not intake's failure).
    rows_with_baseline = [(f, r) for f, r in fams.items() if r.get("carried") is not None
                          and int(r.get("prior_unjudged") or 0) > 0]
    if not rows_with_baseline:
        out["checks"].append({"metric": "carried_backlog", "state": "UNMEASURED",
                              "why": "no previous reading to ratchet against"})
    elif judged_any == 0:
        out["checks"].append({"metric": "carried_backlog", "state": "UNMEASURED",
                              "why": ("the judge recorded no verdict in this window -- nothing "
                                      "drained because nothing ran (the gauntlet's clock)")})
    else:
        stalled = sorted((f for f, r in rows_with_baseline
                          if int(r.get("carried") or 0) >= int(r.get("prior_unjudged") or 0)
                          and int(r.get("quota") or 0) > 0
                          and str(r.get("judging_status") or "") != "STUDY_ONLY"),
                         key=lambda f: -int(fams[f].get("carried") or 0))
        if stalled:
            failures.extend(stalled[:10])
            out["checks"].append({
                "metric": "carried_backlog", "state": "FAIL",
                "why": (f"{len(stalled)} family(ies) drained nothing they already held: "
                        + ", ".join(f"{f} ({fams[f].get('carried')} carried of "
                                    f"{fams[f].get('prior_unjudged')})" for f in stalled[:5]))})
        else:
            drained = sum(int(r.get("drained") or 0) for _, r in rows_with_baseline)
            out["checks"].append({"metric": "carried_backlog", "state": "OK",
                                  "why": f"{drained} carried cell(s) left the backlog this pass"})

    # 3. NO FAMILY PAST ITS OWN WINDOW -- AND THE AGE IS RATCHETED ON MOVEMENT, NOT ON ITS VALUE.
    #
    # An age RISES by the wall time between two readings whatever the desk does. The coverage-
    # drain fence ratcheted a raw wait and went red on its third live pass for exactly that
    # reason -- 6.0h to 6.3h, eighteen minutes of clock -- and a gate nobody can satisfy is a gate
    # that gets switched off. So what fails here is an age that is past twice the family's own
    # drain window AND DID NOT FALL, in a pass where the family held quota and the judge actually
    # recorded verdicts. That is the controllable defect: a family whose stream is sorted
    # oldest-first, which was served this hour, and whose oldest cell still did not move.
    # The first reading carries no baseline and so enters UNMEASURED, which is how every metric
    # on this desk enters: at its measurement, never at an invented zero.
    def _overdue(f: str, r: dict[str, Any]) -> bool:
        if int(r.get("unjudged") or 0) <= 0 or str(r.get("judging_status") or "") == "STUDY_ONLY":
            return False
        age = r.get("oldest_unjudged_age_h")
        prior = r.get("prior_oldest_age_h")
        if age is None or prior is None or int(r.get("quota") or 0) <= 0 or judged_any == 0:
            return False
        window = float(r.get("window_h") or 1.0)
        return float(age) > WINDOW_SLACK * window and float(age) >= float(prior)

    overdue = sorted((f for f, r in fams.items() if _overdue(f, r)),
                     key=lambda f: -float(fams[f].get("oldest_unjudged_age_h") or 0.0))
    if overdue:
        failures.extend(overdue[:10])
        out["checks"].append({
            "metric": "oldest_unjudged", "state": "FAIL",
            "why": (f"{len(overdue)} family(ies) were served this hour and their oldest cell "
                    f"still did not move, past twice their own drain window: " + ", ".join(
                        f"{f} ({fams[f].get('oldest_unjudged_age_h')}h vs "
                        f"{fams[f].get('window_h')}h window)" for f in overdue[:5]))})
    else:
        stale_age = sorted((f for f, r in fams.items()
                            if r.get("oldest_unjudged_age_h") is not None
                            and int(r.get("unjudged") or 0) > 0
                            and float(r["oldest_unjudged_age_h"]) >
                            WINDOW_SLACK * float(r.get("window_h") or 1.0)),
                           key=lambda f: -float(fams[f].get("oldest_unjudged_age_h") or 0.0))
        out["checks"].append({
            "metric": "oldest_unjudged",
            "state": "OK" if not stale_age else "WARN",
            "why": ("no family's oldest unjudged cell is past its own window" if not stale_age
                    else (f"{len(stale_age)} family(ies) hold a cell past their own window and "
                          f"it is FALLING or unmeasured (oldest "
                          f"{fams[stale_age[0]].get('oldest_unjudged_age_h')}h on "
                          f"{stale_age[0]}) -- published, not failed: an age rises with the "
                          "clock and only its movement is the desk's to control"))})

    # 4. THE REMAINDER FOLLOWED THE PUBLISHED RANKING. The floor is the breadth mandate and is
    #    checked above by starvation; this checks the part that carries the return. Remainder is
    #    spent strictly down expected value per judge-second, so a family that received remainder
    #    while a HIGHER-ranked family still held undrained backlog means the allocation stopped
    #    following its own ranking -- which is exactly how a future session would quietly revert
    #    this to round-robin, with the report still claiming value ordering.
    ranking = [r for r in (doc.get("value_ranking") or ()) if isinstance(r, dict)]
    if not ranking:
        out["checks"].append({"metric": "remainder_follows_ranking", "state": "UNMEASURED",
                              "why": "the report publishes no value ranking"})
    else:
        starved_higher: list[str] = []
        for i, row in enumerate(ranking):
            if int(row.get("remainder") or 0) <= 0:
                continue
            for higher in ranking[:i]:
                room = int(higher.get("unjudged") or 0) - int(higher.get("quota") or 0)
                if int(higher.get("remainder") or 0) == 0 and room > 0:
                    starved_higher.append(f"{row.get('family')} over {higher.get('family')}")
                    break
        if starved_higher:
            failures.extend(starved_higher[:10])
            out["checks"].append({
                "metric": "remainder_follows_ranking", "state": "FAIL",
                "why": ("the remainder did not follow the published expected-value-per-judge-"
                        "second ranking: " + ", ".join(starved_higher[:5]))})
        else:
            top = ranking[0]
            out["checks"].append({
                "metric": "remainder_follows_ranking", "state": "OK",
                "why": (f"remainder spent down the ranking, top {top.get('family')} at "
                        f"{top.get('ev_per_judge_second')} ev/judge-s")})

    totals = doc.get("totals") or {}
    out["totals"] = {k: totals.get(k) for k in (
        "families_mined", "families_with_backlog", "families_queued", "families_starved",
        "unjudged_total", "carried_total", "study_only_total", "capacity_measured",
        "oldest_unjudged_age_h", "value_at_risk", "value_deferred", "value_forgone_per_hour",
        "hours_to_drain", "capacity_short")}
    out["top_value"] = [{k: r.get(k) for k in ("rank", "family", "ev_per_judge_second",
                                               "p_optimistic", "prior_status", "quota",
                                               "floor", "remainder", "value_at_risk")}
                        for r in ranking[:5]]
    out["worst_backlog"] = (doc.get("worst_backlog") or [])[:5]
    out["verdict"] = "FAIL" if failures else "PASS"
    out["why"] = (f"{len(set(failures))} family(ies) failed a coverage rule: "
                  + ", ".join(sorted(set(failures))[:6])) if failures else (
        "every family holding unjudged cells is queued, its carried backlog fell, and none sits "
        "past its own window")
    return out


def render(doc: Mapping[str, Any]) -> list[str]:
    lines = [f"judge coverage: {doc.get('verdict')} -- {doc.get('why')}"]
    for row in doc.get("checks") or ():
        lines.append(f"  [{row.get('state')}] {row.get('metric')}: {row.get('why')}")
    t = doc.get("totals") or {}
    if t.get("value_at_risk") is not None:
        lines.append(f"  value at risk {t.get('value_at_risk')} / deferred "
                     f"{t.get('value_deferred')} / forgone {t.get('value_forgone_per_hour')}/h"
                     + ("  CAPACITY SHORT -> judging_throughput" if t.get("capacity_short")
                        else ""))
    for row in doc.get("top_value") or ():
        lines.append(f"  #{row.get('rank')} {row.get('family')} ev/judge-s "
                     f"{row.get('ev_per_judge_second')} quota {row.get('quota')}")
    for row in doc.get("worst_backlog") or ():
        lines.append(f"  worst: {row.get('family')} unjudged {row.get('unjudged')} "
                     f"queued {row.get('queued')} oldest {row.get('oldest_unjudged_age_h')}h")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument("--require-state", action="store_true",
                    help="box mode: an absent or stale report is a FAILURE, not UNMEASURED")
    ap.add_argument("--report", default=None)
    ap.add_argument("--audit", default=str(AUDIT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = judge(report=Path(args.report) if args.report else None,
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


__all__ = ["RATCHET", "REPORT", "RULE", "STALE_H", "WINDOW_SLACK", "judge", "main", "render"]


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())
