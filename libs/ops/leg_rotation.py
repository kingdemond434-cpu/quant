"""POSITION DECIDED WHETHER A LEG RAN, AND NINETEEN LEGS LOST (measured 2026-09-23).

`desks/mt5/research/hourly_cycle.py` is a 4,500-line straight line: `main()` calls `_costed(name,
fn)` three hundred times, front to back, and `MT5-HourlyCore` gives that line 40 minutes
(`ExecutionTimeLimit=PT40M`). A pass that runs out of clock is killed WHERE IT STANDS, and the
next hourly trigger starts again at the top -- so the legs past the kill point are not late, they
are unreachable, and they are the SAME legs every hour.

WHAT THAT COST, from the desk's own compute ledger (89,986 rows, 503 distinct runs):

    19 of 112 CORE_LEGS had NEVER executed once.  Not slow: zero rows, ever.

And the reach was COLLAPSING, which is the part a snapshot hides. On 2026-09-23 the legs at the
head of `main()` last ran at 21:15; the ones a third of the way down at 11:15; and everything past
`residual_queue` had not run since 2026-09-22 23:05 -- twenty-two hours -- because each new organ
wired into the head pushed the kill point further up the file. The nineteen dark legs were all
wired on 2026-09-23 itself, into a pass whose last completing run predated every one of them.

Among the lost: `clock_liveness` and `clock_ledger` (how the desk knows its forward clocks are
alive), `fill_recorder` (how it learns from real executions) and `evidence_chain` (provenance).
A leg that never runs raises no error and writes no artifact, so it reads exactly like a leg with
nothing to do -- which is why this went unmeasured for as long as it did.

NO AMOUNT OF SPEEDING UP THE HEAD IS A FIX. The head grows every time an organ is wired, and the
tail is structurally last. The cure is the one the law-gate battery already uses
(`scripts/run_law_gate.py:rotate_gate`): ROTATE the roster across passes inside a STATED window,
and publish by name every member the window has not reached.

WHAT THIS MODULE DOES, AND WHAT IT REFUSES TO DO

    It decides MEMBERSHIP, never order.  Legs still execute in file order, so every
    "must run after" comment in the cycle still holds. Rotation only decides which legs run in
    THIS pass; a deferred leg returns a dict in microseconds, so the pass races past it and the
    clock reaches the tail.

    It NEVER SHRINKS THE WORK (principal's standing order: never reduce aggressiveness). The
    budget is the wall clock the scheduler already imposed -- rotation does not create it. The
    same seconds are spent; they stop being spent on the same prefix every hour. Before: 19 legs
    at zero runs forever. After: every leg runs inside the window. That is strictly more work
    reaching the tail, not less attempted.

    A LEG THAT HAS NEVER RUN OUTRANKS EVERYTHING (except the always-run set). It is admitted
    ahead of any merely-stale leg, so the dark set drains monotonically and cannot be re-starved
    by fast legs -- the same property `rotate_gate` states as "nothing is ever skipped for being
    slow: it only ever climbs the queue".

    IT PUBLISHES WHAT IT COULD NOT REACH.  `never_run` and `outside_window` are written by name
    to reports/LEG_ROTATION.json every pass, and `scripts/check_leg_rotation.py` fails the law
    gate on either. UNMEASURED is a real answer (L1.28a); a silent absence is not.

THE BOUND, STATED. Admitted cost per pass is held under the scheduler's own limit, so every
admitted leg is actually REACHED. A leg therefore waits at most ceil(total_roster_cost / budget)
passes, and never-run legs wait at most ceil(never_run_cost / budget) -- with the measured roster
and a 40-minute core window that is a small number of hours, well inside ROTATION_WINDOW_H.
"""
from __future__ import annotations

import ast
import json
import os
import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
LEDGER = DESK / "data" / "compute_ledger.jsonl"
CYCLE = DESK / "research" / "hourly_cycle.py"
RECORD = DESK / "reports" / "LEG_ROTATION.json"

#: How long a leg's run stands before the rotation is failing it. Chosen to be REACHABLE by the
#: clock that owns the roster: the core plan fires hourly, so 24 h is twenty-four chances. A leg
#: with no run inside this window is published as `outside_window` and fails the fence -- the
#: same shape and the same reason as `run_law_gate.ROTATION_WINDOW_H`.
ROTATION_WINDOW_H: float = 24.0

#: The share of the scheduler's wall-clock limit this module will plan into. The remainder pays
#: for the legs that overrun their own `--budget-s`, for interpreter start-up and for the pass
#: epilogue. MEASURED: the last core pass to finish (2026-09-22) took 42 minutes against a
#: 40-minute limit and was killed in its epilogue, so planning to the full limit plans a pass
#: that does not finish.
BUDGET_FILL: float = 0.80

#: What a leg is assumed to cost when the ledger has never seen it. It cannot be zero (a roster
#: of unknowns would all be admitted and the pass would be killed exactly as before) and it must
#: not be so large that one unknown crowds out the pass. This is the median declared `--budget-s`
#: of the cycle's `_producer` legs, which is the desk's own statement of what such a leg costs.
UNKNOWN_LEG_COST_S: float = 60.0

#: How many recent costs are kept per leg. Enough to take a median that survives one slow pass.
COST_SAMPLES: int = 5

#: THE ALWAYS-RUN SET: legs that may never be rotated out, each for a reason that is about money
#: or about irreversibility, never about tidiness. Kept SMALL on purpose -- every name here is a
#: leg the rotation can no longer use to buy room for a starved one.
#:
#:   record_tape       A tick not recorded is gone. Capture is irreversible and is the one leg
#:                     the principal's order names outright ("do NOT fix this by cutting tick
#:                     capture").
#:   promoter          AUTOMATIC PROMOTION is a standing order: a candidate whose clock matures
#:                     is written LIVE on the SAME cycle. A deferred promoter is a delayed fill.
#:   forward_reconcile The forward evidence the promoter reads. Deferring it would hand the
#:                     promoter a stale book.
#:   heal_clocks       Repairs the forward clocks the whole promotion path is measured on.
#:   smoke_release     The pass's own integrity check; a pass that cannot import is not a pass.
#:   health            The liveness the watchdogs read to decide the desk is up.
#:   publish_state     Delivers what the pass produced; deferring it hides the pass from the
#:                     dashboards and the board that reads them.
ALWAYS_RUN: frozenset[str] = frozenset({
    "record_tape", "promoter", "forward_reconcile", "heal_clocks",
    "smoke_release", "health", "publish_state",
})


def legs_in_order(source: Path | None = None) -> list[str]:
    """Every leg name `main()` costs, in the order it costs them, read from the AST.

    THE AST, NOT THE LINE TEXT, and not a hand-kept table. A second list of leg names would be
    wrong the first time someone wired an organ and forgot it -- which is the exact failure mode
    this module exists to end. Parsing the source means the roster cannot drift from the cycle.
    """
    path = source or CYCLE
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return []
    found: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_costed" and node.args):
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        name = first.value
        if name in seen:
            continue
        seen.add(name)
        found.append((node.lineno, node.col_offset, name))
    return [name for _, _, name in sorted(found)]


@dataclass
class Attendance:
    """What the ledger says about each leg: how often it ran, when last, and what it costs."""

    runs: dict[str, int] = field(default_factory=dict)
    last_at: dict[str, str] = field(default_factory=dict)
    costs: dict[str, list[float]] = field(default_factory=dict)
    offset: int = 0

    def cost_s(self, leg: str) -> float:
        """The seconds to plan for this leg: the median of what it recently cost."""
        samples = [c for c in self.costs.get(leg, []) if c > 0]
        if not samples:
            return UNKNOWN_LEG_COST_S
        return float(statistics.median(samples))

    def age_s(self, leg: str, now: datetime) -> float:
        """Seconds since this leg last ran; infinite when it never has."""
        raw = self.last_at.get(leg)
        if not raw:
            return float("inf")
        try:
            return (now - datetime.fromisoformat(raw)).total_seconds()
        except (TypeError, ValueError):
            return float("inf")

    def to_json(self) -> dict[str, Any]:
        return {"offset": self.offset, "runs": self.runs, "last_at": self.last_at,
                "costs": {k: v[-COST_SAMPLES:] for k, v in self.costs.items()}}

    @classmethod
    def from_json(cls, doc: Any) -> Attendance:
        if not isinstance(doc, dict):
            return cls()
        runs = {str(k): int(v) for k, v in (doc.get("runs") or {}).items()
                if isinstance(v, (int, float))}
        last = {str(k): str(v) for k, v in (doc.get("last_at") or {}).items()}
        costs: dict[str, list[float]] = {}
        for k, v in (doc.get("costs") or {}).items():
            if isinstance(v, list):
                costs[str(k)] = [float(x) for x in v if isinstance(x, (int, float))]
        try:
            offset = int(doc.get("offset") or 0)
        except (TypeError, ValueError):
            offset = 0
        return cls(runs=runs, last_at=last, costs=costs, offset=offset)


def read_attendance(ledger: Path | None = None, prior: Attendance | None = None) -> Attendance:
    """Fold the compute ledger into per-leg attendance, reading only what is new.

    INCREMENTAL BY BYTE OFFSET, because the ledger is append-only and already 39 MB on the
    trading box: a full re-parse every pass would spend the rotation's own budget measuring it.
    A file SHORTER than the recorded offset has been rotated or truncated, so the offset is
    dropped and the whole file is re-read -- an unreadable ledger must never silently produce an
    attendance record that says every leg is starved.
    """
    path = ledger or LEDGER
    att = prior or Attendance()
    try:
        size = path.stat().st_size
    except OSError:
        return att
    start = att.offset if 0 <= att.offset <= size else 0
    if start == 0:
        att.runs, att.last_at, att.costs = {}, {}, {}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(start)
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                name = row.get("run")
                if not isinstance(name, str) or not name:
                    continue
                att.runs[name] = att.runs.get(name, 0) + 1
                at = row.get("at")
                if isinstance(at, str) and at:
                    att.last_at[name] = at
                wall = row.get("wall_s")
                if isinstance(wall, (int, float)) and wall >= 0:
                    att.costs.setdefault(name, []).append(float(wall))
                    if len(att.costs[name]) > COST_SAMPLES:
                        del att.costs[name][:-COST_SAMPLES]
            att.offset = fh.tell()
    except OSError:
        return att
    # `tell()` on a text handle is an opaque cookie, not a byte count on every platform; the
    # file size is the honest resume point and is never past the end.
    att.offset = min(att.offset, size) if att.offset else size
    return att


@dataclass
class Decision:
    """This pass's membership: who runs, who waits, and what the window has not reached."""

    plan: str
    budget_s: float
    admitted: set[str] = field(default_factory=set)
    deferred: set[str] = field(default_factory=set)
    never_run: list[str] = field(default_factory=list)
    outside_window: list[str] = field(default_factory=list)
    roster: list[str] = field(default_factory=list)
    planned_s: float = 0.0
    why: dict[str, str] = field(default_factory=dict)

    def runs(self, leg: str) -> bool:
        """Does `leg` run in this pass? An unknown leg always runs (rotation never invents a veto
        for something it does not know about)."""
        return leg not in self.deferred

    def should_run(self, leg: str, att: Attendance, elapsed_s: float) -> tuple[bool, str]:
        """The runtime half of the decision: admission, then the clock that is actually elapsing.

        PLANNED SECONDS ARE AN ESTIMATE AND ESTIMATES ARE WRONG. When the head of a pass overruns
        what the ledger said it would cost, the legs that pay are the ones at the tail -- which is
        the original defect, re-entering through the estimate. So once the pass is past its
        budget, a leg that HAS run before yields the rest of the pass to the legs that never have.
        Nothing is cancelled: a yielded leg is the oldest one next pass and therefore leads it.

        The always-run set and the never-run set are never yielded. A never-run leg is the whole
        point of the pass, and it carries its own `--budget-s`, so it cannot run away with the
        clock it was finally given.
        """
        if leg in self.deferred:
            return False, self.why.get(leg, "deferred by rotation")
        if leg in ALWAYS_RUN:
            return True, ""
        if self.budget_s > 0 and elapsed_s > self.budget_s and att.runs.get(leg, 0) > 0:
            return False, (f"budget overrun at {elapsed_s:.0f}s of {self.budget_s:.0f}s: this "
                           f"pass yields to legs that have never run; it leads the next pass")
        return True, ""


def budget_for(plan: str, env: dict[str, str] | None = None) -> float:
    """The wall-clock seconds this pass may plan into.

    The number is the SCHEDULER'S, not this module's: `MT5-HourlyCore` carries
    ExecutionTimeLimit=PT40M, so the core plan plans into 40 minutes times BUDGET_FILL. Every
    other plan runs on a department resident registered with NO limit (PT0S), so it is unbounded
    and this module defers nothing -- rotation is a cure for a bounded window and would be a
    throttle anywhere else.
    """
    src = env if env is not None else os.environ
    raw = str(src.get("HOURLY_BUDGET_S") or "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return 2400.0 * BUDGET_FILL if plan == "core" else 0.0


def _rank(leg: str, att: Attendance, now: datetime,
          order: dict[str, int]) -> tuple[int, float, int]:
    """Sort key: always-run first, then never-run, then oldest-first, then file order."""
    if leg in ALWAYS_RUN:
        tier = 0
    elif att.runs.get(leg, 0) <= 0:
        tier = 1
    else:
        tier = 2
    age = att.age_s(leg, now)
    return (tier, -age if age != float("inf") else float("-inf"), order.get(leg, 0))


def plan_pass(roster: list[str], att: Attendance, *, plan: str, budget_s: float | None = None,
              now: datetime | None = None, full_roster: list[str] | None = None) -> Decision:
    """Choose this pass's membership so that every admitted leg is actually REACHED.

    Greedy oldest-first admission under the scheduler's own clock. The greed is the point: a leg
    is admitted because it has waited longest, not because it is cheap, so a slow leg only ever
    climbs. Admission stops when the planned seconds reach the budget -- and NOT admitting a leg
    costs nothing, because a deferred leg returns a dict without running.

    An unbounded budget (0.0) admits the whole roster: the department residents have no time
    limit, and adding one here would be the throttle this desk does not permit.

    `roster` is what THIS plan may run; `full_roster` is every leg the cycle declares. Admission
    is charged against the first, but `never_run` and `outside_window` are measured against the
    second -- a leg dark on the heavy clock is still dark, and a report that only ever named the
    legs of the plan that happened to be running would hide exactly the defect this file exists
    to end.
    """
    t0 = now or datetime.now(tz=UTC)
    bud = budget_for(plan) if budget_s is None else budget_s
    order = {leg: i for i, leg in enumerate(roster)}
    everything = list(full_roster) if full_roster is not None else list(roster)
    dec = Decision(plan=plan, budget_s=bud, roster=list(roster))
    dec.never_run = sorted(leg for leg in everything if att.runs.get(leg, 0) <= 0)
    window_s = ROTATION_WINDOW_H * 3600.0
    dec.outside_window = sorted(leg for leg in everything if att.age_s(leg, t0) > window_s)
    if bud <= 0:
        dec.admitted = set(roster)
        dec.why = dict.fromkeys(roster, "unbounded plan: no time limit to rotate against")
        dec.planned_s = sum(att.cost_s(leg) for leg in roster)
        return dec
    spent = 0.0
    for leg in sorted(roster, key=lambda n: _rank(n, att, t0, order)):
        cost = att.cost_s(leg)
        if leg in ALWAYS_RUN:
            dec.admitted.add(leg)
            spent += cost
            dec.why[leg] = "always-run: irreversible or on the money path"
            continue
        if spent + cost <= bud:
            dec.admitted.add(leg)
            spent += cost
            dec.why[leg] = ("never run: admitted ahead of every stale leg"
                            if att.runs.get(leg, 0) <= 0 else
                            f"rotation: idle {att.age_s(leg, t0) / 3600.0:.1f}h")
        else:
            dec.deferred.add(leg)
            dec.why[leg] = (f"deferred this pass: {cost:.0f}s would pass the "
                            f"{bud:.0f}s budget ({spent:.0f}s planned); it leads the next pass")
    dec.planned_s = spent
    return dec


def record(dec: Decision, att: Attendance, ran: list[str], *, path: Path | None = None,
           started: datetime | None = None, now: datetime | None = None,
           complete: bool = True) -> dict[str, Any]:
    """Publish the pass: what ran, what waited, and -- by NAME -- what has never run at all.

    WRITTEN TWICE, AND THE FIRST WRITE IS THE ONE THAT MATTERS. A pass killed at its 40-minute
    limit never reaches its own epilogue -- which is how the cycle came to have no record of the
    legs it could not reach. So the plan is published the moment it is decided (`complete=False`,
    `ran` still empty) and again when the pass ends. `never_run` and `outside_window` are both
    known at plan time, so the fence can be cashed even for a pass that was killed.
    """
    t1 = now or datetime.now(tz=UTC)
    doc: dict[str, Any] = {
        "generated": t1.isoformat(),
        "pass_complete": bool(complete),
        "plan": dec.plan,
        "window_h": ROTATION_WINDOW_H,
        "budget_s": round(dec.budget_s, 1),
        "planned_s": round(dec.planned_s, 1),
        "elapsed_s": round((t1 - started).total_seconds(), 1) if started else None,
        "n_roster": len(dec.roster),
        "n_admitted": len(dec.admitted),
        "n_deferred": len(dec.deferred),
        "ran_this_pass": list(ran),
        "deferred_this_pass": sorted(dec.deferred),
        # THE TWO LINES THE FENCE READS. A leg that never ran is a claim the desk cannot cash
        # (L1.49), so it is published by name rather than inferred from an absent artifact.
        "never_run": list(dec.never_run),
        "outside_window": list(dec.outside_window),
        "why": dec.why,
        "attendance": att.to_json(),
    }
    out = path or RECORD
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        tmp.replace(out)
    except OSError as exc:
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def load_record(path: Path | None = None) -> dict[str, Any]:
    """The last published rotation, or an empty dict when there is none."""
    try:
        doc = json.loads((path or RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}
