"""RAN IS NOT COMPLETED, and this desk has spent months reading the first as the second.

THE CASE THAT NAMES THE CLASS, measured on this tree 2026-09-10. `pf_allocator` is the growth
sizer: it solves posterior E[log W] for the heat every sleeve should risk, and nothing else on
the desk answers "how big should this trade be" with an estimate of growth. It was armed
(`data/PF_ALLOCATOR_ARMED`, 2026-09-04). It had an hourly leg. `decision_core.allocator_heat`
read its artifact and `promoted_lot(from_book=True)` sized from its fractions. Every dashboard
panel that watches it read healthy.

    $ python desks/mt5/research/pf_allocator.py --mode normal
    REFUSING to project a portfolio without .../reports/hunt12_partial.json
    exit 1

`reports/pf_allocation.json` HAD NEVER EXISTED. For six days the leg ran on the hour, exited 1,
and the desk sized every sleeve off the authority ramp -- a count of closed trades with no
estimate of growth in it -- while reporting the allocator as armed and wired.

NOT ONE OF THE FENCES THIS DESK ALREADY OWNS COULD HAVE CAUGHT IT, and each was close:

    check_producer_schedules   asks "is there a clock?"           -- there was
    capability_graph           asks "does a consumer exist?"      -- one did
    module_rent                asks "is this node priced?"        -- it was
    compute_ledger             asks "what did the hour cost?"     -- it recorded the cost
    stall_watch                asks "did the task start?"         -- it started

Every one of them answered a question about ACTIVITY. The question none of them asked is whether
the thing the activity exists to produce is now on disk. That is the whole of this module.

WHAT IT JOINS, all of it already written down somewhere else -- this adds no registry:

    data/sync_marker.json        every leg of the last cycle and what it returned
    data/compute_ledger.jsonl    per-run history: when, what outcome, how expensive
    capability_graph.NODES       what each component DECLARES it writes, reads, and how fresh
                                 an authority node's inputs must be
    the filesystem               whether that declared artifact is actually there, and how old

THE VERDICTS, one per leg, in the order they are decided:

    UNDECLARED   the leg has no node in the capability graph, so NOTHING KNOWS what it should
                 have produced. This is the state pf_allocator's input was in and it is counted
                 as debt, never skipped: an undeclared leg cannot be judged by any of the rules
                 below, so it is permanently invisible to all of them.
    NEVER_RAN    no row in the ledger window and no key in the marker
    FAILING      the last observation failed -- a non-zero exit, a MISSING script, a recorded
                 exception, or a ledger outcome that is not ok
    NO_OUTPUT    the last run reported success AND a declared write is not on disk. THE
                 pf_allocator CLASS. A leg that returns 0 and produces nothing is the single
                 most expensive shape of failure here, because every downstream reader treats
                 the absence as "not yet" rather than "broken".
    STALE        the declared write exists but is older than the node's own freshness SLA
    UNREAD       fresh output that no node reads: work the desk pays for and never spends
    COMPLETED    ran, wrote, fresh, and something reads it

AND THE STREAK, because "repairs lack verified closure" is its own defect. A leg that has been
FAILING or NO_OUTPUT for N consecutive recorded runs is not a blip, and the count is what
separates "it failed once at 03:00" from "it has failed every hour since Tuesday". A repair is
closed by the streak returning to zero, never by a command having exited 0.

ABSENCE IS JUDGED, NEVER ASSUMED (L1.28a). On a two-machine desk an absent file has three
meanings, not two, and this uses the rule `microstructure_census.artifact_state` already
established: a path under a STATE_PREFIX that is NOT gitignored and is absent has never been
produced on ANY machine, because the box commits and pushes what it writes there; a gitignored
path says nothing from a research checkout and is reported UNKNOWN_HERE rather than failed.

WHAT GATES CI AND WHAT GATES THE BOX, kept apart on purpose. The STATIC findings -- a leg with no
node, a declared write nothing reads -- are true in any checkout and fail `check_completion.py`.
The RUNTIME findings -- NO_OUTPUT, STALE, FAILING -- need the machine that runs the clock, so
they are published to `reports/COMPLETION.json` for the issue board and fail only where the
artifact's absence is real. A gate that is red on every developer checkout is a gate nobody
reads, which is the failure this module exists to end, not to repeat.

    python -m libs.ops.completion            # the report
    python -m libs.ops.completion --json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"

MARKER = DESK / "data" / "sync_marker.json"
LEDGER = DESK / "data" / "compute_ledger.jsonl"
OUT_REL = "desks/mt5/reports/COMPLETION.json"

#: The cycles whose legs are judged. A leg is `_costed("name", ...)` in one of these.
CYCLES = ("desks/mt5/research/hourly_cycle.py", "desks/mt5/research/daily_cycle.py")

_LEG_RE = re.compile(r'_costed\(\s*"([^"]+)"')

#: How many recorded runs back the streak is counted over. Long enough that an organ on a daily
#: clock still shows several observations, short enough that a fix shows up as a falling streak
#: within a day rather than being averaged out by a fortnight of history.
STREAK_WINDOW = 200

#: Default freshness when a node declares none. A leg on the hourly cycle whose artifact is a day
#: old has missed twenty-three passes; anything longer would let a dead producer read healthy.
DEFAULT_SLA_S = 26 * 3600

UNDECLARED = "UNDECLARED"
NEVER_RAN = "NEVER_RAN"
FAILING = "FAILING"
NO_OUTPUT = "NO_OUTPUT"
STALE = "STALE"
UNREAD = "UNREAD"
COMPLETED = "COMPLETED"
UNKNOWN_HERE = "UNKNOWN_HERE"

#: The verdicts that mean the leg is not delivering. `UNKNOWN_HERE` is deliberately absent: it is
#: the honest answer of a checkout that cannot see the box, not a finding.
BREACH = (UNDECLARED, NEVER_RAN, FAILING, NO_OUTPUT, STALE, UNREAD)

#: Findings true in ANY checkout, so they can fail CI. The rest need the machine with the clock.
STATIC = (UNDECLARED, UNREAD)


@dataclass
class Leg:
    name: str
    cycle: str
    verdict: str = UNDECLARED
    why: str = ""
    node: str | None = None
    writes: tuple[str, ...] = ()
    readers: tuple[str, ...] = ()
    authority: tuple[str, ...] = ()
    last_at: str | None = None
    last_outcome: str | None = None
    streak: int = 0
    artifacts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))


# ------------------------------------------------------------------ the four sources


def legs(root: Path | None = None) -> dict[str, str]:
    """Every `_costed` leg in the cycles -> the cycle it belongs to.

    READ FROM THE CODE, NEVER A LIST. A hand-kept roster of legs is right on the day it is
    written and silently wrong afterwards -- which is how fifteen legs came to sit in the hourly
    cycle with no entry in the layer registry, nine of them added the same day the registry's own
    fence was written.
    """
    root = Path(root or ROOT)
    out: dict[str, str] = {}
    for rel in CYCLES:
        p = root / Path(*rel.split("/"))
        if not p.is_file():
            continue
        for name in _LEG_RE.findall(p.read_text(encoding="utf-8", errors="replace")):
            out.setdefault(name, rel)
    return out


def _ignored(root: Path, rel: str) -> bool:
    """`git check-ignore`, which is the only authority on this. A hand-parsed .gitignore gets
    negation patterns wrong, and `!desks/mt5/data/sleeves.json` is exactly such a pattern."""
    try:
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=str(root),
                           capture_output=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return True                     # cannot tell -> never claim NEVER_PRODUCED
    return r.returncode == 0


def artifact_state(root: Path, rel: str, now: datetime | None = None) -> dict[str, Any]:
    """PRESENT (with its age), UNKNOWN_HERE, or NEVER_PRODUCED -- and never a guess between them.

    The rule is `microstructure_census.artifact_state`'s, restated for a path that carries an
    age: `desks/mt5/data/` is a STATE_PREFIX the box commits and pushes, so an absent path there
    that is not gitignored has never been written by any machine. A gitignored path (everything
    under `reports/`) is invisible from a research checkout and says nothing either way.
    """
    p = root / Path(*rel.split("/"))
    if p.exists():
        age = ((now or datetime.now(UTC)).timestamp() - p.stat().st_mtime)
        return {"path": rel, "state": "PRESENT", "age_s": round(max(0.0, age), 1),
                "bytes": p.stat().st_size}
    if _ignored(root, rel):
        return {"path": rel, "state": UNKNOWN_HERE,
                "why": ("gitignored: its absence in this checkout is not evidence. The box may "
                        "hold it, and only the box can judge this line")}
    return {"path": rel, "state": "NEVER_PRODUCED",
            "why": ("absent, not gitignored, under a prefix the box commits and pushes -- so had "
                    "any machine ever written it, the next adopt would have carried it here")}


def marker(path: Path | None = None) -> dict[str, Any]:
    """The last cycle's per-leg results, or {} when the marker is unreadable."""
    try:
        doc = json.loads((path or MARKER).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def ledger_runs(path: Path | None = None,
                window: int = STREAK_WINDOW) -> dict[str, list[dict[str, Any]]]:
    """Per leg, its most recent recorded runs, oldest first, from the append-only ledger."""
    rows: list[dict[str, Any]] = []
    try:
        with open(path or LEDGER, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("run"):
                    rows.append(row)
    except OSError:
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(str(row["run"]), []).append(row)
    return {k: v[-window:] for k, v in out.items()}


def _nodes() -> dict[str, Any]:
    """The capability graph's nodes by name, or {} when it cannot be imported.

    NOT A FALLBACK ROSTER. Without the graph nothing here knows what a leg should produce, and
    the whole report says so rather than judging legs against nothing.
    """
    try:
        from libs.ops.capability_graph import NODES
    except Exception:
        return {}
    return {n.name: n for n in NODES}


# ------------------------------------------------------------------ the verdict


def _failed(result: Any) -> str | None:
    """Why the last observation counts as a failure, or None. Reads the shapes the cycles
    actually write: an exit code, a MISSING status, a recorded exception, a timeout."""
    if not isinstance(result, dict):
        return None
    if result.get("error"):
        return f"the leg raised: {result['error']}"
    status = str(result.get("status") or "")
    if status in ("MISSING", "FAILED", "ERROR"):
        return f"status {status}: {result.get('why') or result.get('note') or ''}".strip()
    code = result.get("exit_code")
    if code is None and result.get("timeout_s"):
        return f"stopped at its {result['timeout_s']}s budget before finishing"
    if isinstance(code, int) and code != 0:
        tail = str(result.get("tail") or "").strip().replace("\n", " ")[-160:]
        return f"exit {code}{': ' + tail if tail else ''}"
    return None


def _streak(runs: list[dict[str, Any]]) -> int:
    """Consecutive non-ok recorded runs, counting back from the most recent.

    THE COUNT IS THE DIFFERENCE BETWEEN A BLIP AND AN OUTAGE, and it is what closes a repair: a
    fix is verified when this returns to zero, not when a command exits 0.
    """
    n = 0
    for row in reversed(runs):
        if str(row.get("outcome") or "ok") == "ok":
            break
        n += 1
    return n


def judge(root: Path | None = None, now: datetime | None = None,
          marker_path: Path | None = None, ledger_path: Path | None = None) -> list[Leg]:
    """One verdict per leg of the two cycles."""
    root = Path(root or ROOT)
    now = now or datetime.now(UTC)
    nodes = _nodes()
    mk = marker(marker_path)
    runs = ledger_runs(ledger_path)
    readers: dict[str, list[str]] = {}
    for node in nodes.values():
        for rel in getattr(node, "reads", ()):
            readers.setdefault(rel, []).append(node.name)

    out: list[Leg] = []
    for name, cycle in sorted(legs(root).items()):
        leg = Leg(name=name, cycle=cycle)
        mine = runs.get(name) or []
        if mine:
            leg.last_at = str(mine[-1].get("at") or "")
            leg.last_outcome = str(mine[-1].get("outcome") or "")
            leg.streak = _streak(mine)

        node = nodes.get(name)
        if node is None:
            leg.verdict = UNDECLARED
            leg.why = ("no node in libs/ops/capability_graph declares what this leg writes, so "
                       "nothing can tell a pass that produced its artifact from one that "
                       "produced nothing. Every check below is blind to it")
            out.append(leg)
            continue

        leg.node = node.name
        leg.writes = tuple(getattr(node, "writes", ()))
        leg.authority = tuple(getattr(node, "authority", ()))
        leg.readers = tuple(sorted({r for w in leg.writes for r in readers.get(w, [])
                                    if r != node.name}))

        if not mine and name not in mk:
            leg.verdict = NEVER_RAN
            leg.why = (f"no row in {LEDGER.name} and no key in {MARKER.name}: this leg is on a "
                       f"clock and there is no record of it ever completing a pass")
            out.append(leg)
            continue

        why = _failed(mk.get(name))
        if why is None and leg.last_outcome and leg.last_outcome != "ok":
            why = f"last recorded outcome {leg.last_outcome!r}"
        if why is not None:
            leg.verdict, leg.why = FAILING, why
            if leg.streak > 1:
                leg.why += (f" -- and it has failed {leg.streak} recorded runs in a row, so this "
                            f"is an outage, not a blip")
            out.append(leg)
            continue

        leg.artifacts = [artifact_state(root, w, now) for w in leg.writes]
        never = [a for a in leg.artifacts if a["state"] == "NEVER_PRODUCED"]
        if never:
            leg.verdict = NO_OUTPUT
            leg.why = (f"the last run reported success and {len(never)} declared artifact(s) have "
                       f"never been produced on any machine: {', '.join(a['path'] for a in never)}"
                       f". A leg that returns 0 and writes nothing reads downstream as 'not yet' "
                       f"rather than 'broken', which is how pf_allocator went six days unnoticed")
            out.append(leg)
            continue

        present = [a for a in leg.artifacts if a["state"] == "PRESENT"]
        if not present:
            leg.verdict = UNKNOWN_HERE
            leg.why = ("every declared artifact is gitignored and absent here, so this checkout "
                       "cannot judge the leg. Read it on the box")
            out.append(leg)
            continue

        sla = getattr(node, "freshness_s", {}) or {}
        old = [a for a in present
               if a["age_s"] > float(sla.get(a["path"], DEFAULT_SLA_S))]
        if old:
            worst = max(old, key=lambda a: a["age_s"])
            leg.verdict = STALE
            leg.why = (f"{worst['path']} is {worst['age_s'] / 3600:.1f}h old against an SLA of "
                       f"{float(sla.get(worst['path'], DEFAULT_SLA_S)) / 3600:.1f}h: the leg is "
                       f"running and its output is not moving")
            out.append(leg)
            continue

        if leg.writes and not leg.readers:
            leg.verdict = UNREAD
            leg.why = ("the output is fresh and no other node reads it: compute the desk pays "
                       "for every pass and never spends")
            out.append(leg)
            continue

        leg.verdict = COMPLETED
        leg.why = (f"ran, wrote {len(present)} artifact(s), inside SLA, and "
                   f"{len(leg.readers)} node(s) read them")
        out.append(leg)
    return out


def report(root: Path | None = None, now: datetime | None = None,
           **kw: Any) -> dict[str, Any]:
    root = Path(root or ROOT)
    rows = judge(root, now, **kw)
    by: dict[str, int] = {}
    for leg in rows:
        by[leg.verdict] = by.get(leg.verdict, 0) + 1
    static = [x.to_dict() for x in rows if x.verdict in STATIC]
    runtime = [x.to_dict() for x in rows
               if x.verdict in BREACH and x.verdict not in STATIC]
    return {
        "at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "n_legs": len(rows),
        "by_verdict": dict(sorted(by.items())),
        "graph_available": bool(_nodes()),
        "static_findings": static,
        "runtime_findings": runtime,
        "authority_breaches": [x.to_dict() for x in rows
                               if x.authority and x.verdict in BREACH],
        "legs": [x.to_dict() for x in rows],
        "rule": (
            "RAN IS NOT COMPLETED. A leg completes when its declared artifact is on disk, inside "
            "its freshness SLA, and something reads it. Every fence this desk owned asked "
            "whether a component was ACTIVE; none asked whether the thing it exists to produce "
            "is there. pf_allocator ran hourly, exited 1, and sized the whole book off the "
            "authority ramp for six days while every panel read healthy."),
        "closure": (
            "A repair is closed when the streak returns to zero, never when a command exits 0. "
            "`streak` counts consecutive non-ok recorded runs, so a fix that did not take shows "
            "as a number that keeps climbing rather than as a green run somebody remembers."),
    }


def render(doc: dict[str, Any]) -> str:
    lines = [f"COMPLETION  {doc['n_legs']} legs: " +
             ", ".join(f"{k} {v}" for k, v in doc["by_verdict"].items())]
    if not doc["graph_available"]:
        lines.append("  capability_graph UNIMPORTABLE -- no leg could be judged against a "
                     "declaration; every verdict below is UNDECLARED for that reason alone")
    for key, title in (("authority_breaches", "AUTHORITY"), ("static_findings", "STATIC"),
                       ("runtime_findings", "RUNTIME")):
        rows = doc[key]
        if not rows:
            continue
        lines.append(f"  {title} ({len(rows)}):")
        for r in rows[:20]:
            streak = f" x{r['streak']}" if r.get("streak", 0) > 1 else ""
            lines.append(f"    {r['verdict']:<11}{streak:<5} {r['name']}  {r['why'][:110]}")
        if len(rows) > 20:
            lines.append(f"    ... and {len(rows) - 20} more")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="whether a leg that ran actually completed")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = report(root)
    out = root / Path(*OUT_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(doc, indent=1, default=str) if args.json else render(doc))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
