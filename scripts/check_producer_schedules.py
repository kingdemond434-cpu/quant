#!/usr/bin/env python3
"""Every decision-affecting producer must be named by SOMETHING that runs it.

THE DEFECT CLASS THIS ENDS, and it is the one this desk pays for most often. Five separate organs
were found unscheduled on 2026-09-05 alone, each built carefully, each reported healthy, each
running never:

    deepening_worker           908 queued tasks, 0 decided in its lifetime -- no cron, no cycle
    heal_identity_broken_clocks  calls itself a "standing fixer" in line one; only ever mentioned
                               in a comment, while ~30 of ~53 clocks sat IDENTITY_BROKEN
    edge_search                dashboard: "37.7h old (hourly leg)" -- it had no schedule at all
    orthogonal_sweep           dashboard: "32.4h old (hourly leg)" -- same
    miner_candidate_compiler   the ONE step between what the crawlers fetch and what the gauntlet
                               can judge, scheduled by nothing

The pattern is always identical and always invisible: an organ is written, its consumers are
wired, its artifact is read by a dashboard that reports the artifact as STALE -- and the staleness
is attributed to the organ failing rather than to the organ never having been started. "Hourly
leg" in a health report is a claim about intent, not about a schedule.

WHAT THIS CHECKS. For every DECISION_AFFECTING node in the capability graph, at least one
scheduler surface must name it. The surfaces are every place on this tree that can cause code to
run on a clock:

    ops/crontab.manifest                the VPS's DR floor
    desks/mt5/ops/box_tasks.manifest     the Windows box's DR floor
    desks/mt5/research/research_supervisor.py  the PERIODIC job list
    desks/mt5/research/hourly_cycle.py   the hourly legs
    desks/mt5/research/daily_cycle.py    the daily chain

A node named by none of them is UNSCHEDULED, and that is a defect whatever its code quality: a
producer nothing runs has the same effect on the desk as a producer that does not exist, and a
worse effect on the reader, who sees the file and assumes it runs.

RATCHETED, NOT ZERO. Some decision-affecting nodes are legitimately event-driven or manual -- the
immutable evaluator signs a manifest when a judge changes, and putting it on a clock would be
wrong. Those are listed by name with the reason. The ratchet is what stops the list growing.

Exit: 2 above the ratchet or on an unexplained exemption; 0 clean. stdlib-only.

    python scripts/check_producer_schedules.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REPORT = ROOT / "desks" / "mt5" / "reports" / "PRODUCER_SCHEDULES.json"

#: Everything on this tree that can make code run on a clock.
SURFACES = (
    "ops/crontab.manifest",
    "desks/mt5/ops/box_tasks.manifest",
    "desks/mt5/research/research_supervisor.py",
    "desks/mt5/research/hourly_cycle.py",
    "desks/mt5/research/daily_cycle.py",
)

#: Decision-affecting nodes that are CORRECTLY not on a clock, with the reason each is exempt.
#: An exemption without a reason is not an exemption -- it is an unscheduled organ with a note.
EVENT_DRIVEN: dict[str, str] = {
    "immutable_evaluator": ("signs the judge manifest when a judge CHANGES; a clock would re-sign "
                            "drift into legitimacy, which is the opposite of what it is for"),
    "release": ("sealed by CI on a push to a branch the boxes pull -- the event IS the commit, "
                "and a clock would seal untested code"),
    "gateway": ("a continuous loop, not a scheduled job: it is started once and runs, and its "
                "liveness is watched by MT5-StallWatch rather than by a cadence"),
    "fill_surface": ("a LIBRARY the gateway imports, not a job: it has no `main()` and nothing "
                     "could schedule it. It runs whenever an order is priced, which is a stronger "
                     "guarantee than any cadence -- and if the gateway stops calling it, that is "
                     "a wiring defect the capability graph catches, not a schedule defect"),
}

#: Decision-affecting nodes with no schedule and no exemption. RATCHET: may fall, never rise.
#: ZERO, 2026-09-05. Eight organs were unscheduled when this fence was written; five had been
#: found by hand over the preceding hours (the deepening worker, the clock healer, edge_search,
#: orthogonal_sweep and -- worst -- the miner candidate compiler, the single step between what the
#: crawlers fetch and what the gauntlet can judge). This fence found the last three, two of which
#: are now hourly legs and one of which is a library the gateway calls in-process.
#:
#: THE RATCHET IS AT ITS FLOOR AND THAT IS THE POINT. A new decision-affecting producer can no
#: longer land unscheduled: it either appears on a scheduler surface, or it arrives with a written
#: reason for being event-driven. "It is an hourly leg" stops being something a health report
#: claims and becomes something this checks.
MAX_UNSCHEDULED = 0


def _surfaces_text(root: Path) -> str:
    out = []
    for rel in SURFACES:
        p = root / rel
        if p.exists():
            out.append(p.read_text("utf-8", errors="ignore"))
    return "\n".join(out)


def check(root: Path | None = None) -> dict[str, object]:
    base = ROOT if root is None else root
    try:
        from libs.ops.capability_graph import NODES, stages
    except Exception as exc:
        return {"status": "BREACH", "problems": [f"capability graph unreadable: {exc}"],
                "unscheduled": [], "scheduled": 0}
    st = stages()
    text = _surfaces_text(base)
    scheduled, unscheduled = [], []
    for n in NODES:
        if not (st.get(n.name) or {}).get("decision_affecting"):
            continue
        if n.name in EVENT_DRIVEN:
            continue
        if n.name in text or f"{n.name}.py" in text:
            scheduled.append(n.name)
        else:
            unscheduled.append(n.name)
    unscheduled.sort()

    problems: list[str] = []
    if len(unscheduled) > MAX_UNSCHEDULED:
        problems.append(
            f"{len(unscheduled)} decision-affecting producers are named by NO scheduler surface, "
            f"above the ratchet of {MAX_UNSCHEDULED}. A producer nothing runs has the same effect "
            f"on the desk as one that does not exist, and a worse effect on the reader: "
            f"{unscheduled}")
    for name, why in EVENT_DRIVEN.items():
        if not why:
            problems.append(f"{name} is exempted with no reason, which is not an exemption")
    return {
        "surfaces": list(SURFACES),
        "scheduled": len(scheduled),
        "unscheduled": unscheduled,
        "unscheduled_ratchet": MAX_UNSCHEDULED,
        "event_driven": EVENT_DRIVEN,
        "status": "BREACH" if problems else ("RATCHETED" if unscheduled else "OK"),
        "problems": problems,
        "rule": ("'hourly leg' in a health report is a claim about INTENT. This checks the "
                 "schedule."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    out = check()
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
    except OSError:
        pass
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"producer schedules: {out['scheduled']} scheduled, "
              f"{len(out['unscheduled'])} unscheduled (ratchet {MAX_UNSCHEDULED}) "
              f"-- {out['status']}")
        for n in out["unscheduled"]:
            print(f"  UNSCHEDULED {n}")
        for p in out["problems"]:
            print(f"  BREACH {p}")
    return 2 if out["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
