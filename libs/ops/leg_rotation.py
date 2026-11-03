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

THAT BOUND WAS FALSE, AND A ONE-SECOND LEG STARVED FOR FOUR DAYS (measured 2026-10-29).
The proof above assumes the always-run set leaves SOME room. It stopped doing so: `tier_s` hit its
1,500 s LEG_TIMEOUT on every pass and `smoke_release` its 120 s, so the always-run set alone was
charged 3,749 s against a 2,640 s budget. `plan_pass` charged that set FIRST and unconditionally,
then admitted every other leg only if `spent + cost <= budget` -- which no leg can satisfy once
`spent` is already past the budget, however cheap and however long it has waited. Oldest-first
ranking decided the order of a queue nobody was being admitted from, so "it leads the next pass"
was printed beside every deferral and was true of none: `clock_ledger` (0.3-4.6 s) was last
admitted 2026-10-25 06:13Z, and `prop_challenge_allocator` -- money-side -- never ran at all.
The rotation had become exactly the tail-starvation it was written to end.

THE CLASS, CLOSED (rule 23). Waiting is now a COUNTED, PERSISTED quantity, not an inferred one:

    AGEING.  `starve_passes` counts, per roster leg, the consecutive passes it has not run
    (read from attendance `last_at` against the previous pass's start, so a leg admitted but
    never reached because the pass was killed still counts as waiting). Once it reaches
    MAX_DEFERRALS the leg joins the AGEING QUEUE, which is served longest-wait-first OUTSIDE the
    budget arithmetic -- into whatever the always-run set left, never less than AGED_MIN_FILL of
    the budget -- and its legs are exempt from the overrun yield. While the plan fits
    (`capacity.oversubscribed` false) no leg is deferred more than MAX_DEFERRALS passes in a row;
    past it every leg still runs within about `capacity.passes_to_cover` passes, in order of wait,
    and each one past its bound is RED by name.

    CHEAP LEGS.  Legs whose measured cost is at most CHEAP_LEG_S are admitted in a BATCH outside
    the budget each pass (longest-starved first, up to CHEAP_BATCH_FILL of it) and never yielded:
    deferring seconds of work buys no room for anything.

    MONEY-CRITICAL LEGS.  MONEY_CRITICAL (decay_monitor, prop_challenge_allocator, allocator_join,
    edge_reliability, release_identity, kelly_survival, desk_health, fill_markout,
    placement_interlock, box_state_freshness, and the PRODUCER_YIELD / CERTIFICATE_CLOCK_LAW /
    JUDGING_THROUGHPUT publishers) are admitted every pass outside the budget and carry
    a HARD staleness bound of MONEY_MAX_STALE_PASSES. Additive to ALWAYS_RUN: a leg in both is
    charged once, as always-run.

    CAPACITY.  `capacity` publishes whether the bound fits inside the budget at all
    (`oversubscribed`). Ageing admits on time either way; past capacity the scheduler's limit is
    what must move, never a leg.

    CHRONIC TIMEOUTS.  A leg whose last CHRONIC_TIMEOUT_RUNS ledger rows are all TIMEOUT is named in
    `chronic_timeouts`. Outside the always-run set it is ranked LAST among the budget-limited
    legs, so it cannot keep taking its full slot ahead of a starved leg; inside it (`tier_s`) it is
    still admitted and charged its realised cost -- the money path is not this module's to defer --
    but the aged and cheap legs no longer compete with it for room at all. Nothing is deleted and
    no leg's own budget is touched: this is admission order only.

    LIVENESS, RED BY NAME.  `liveness` in the record is RED, with the count and each leg named,
    whenever a roster leg has gone past its `stale_bound` (MAX_DEFERRALS passes; the money-critical
    MONEY_MAX_STALE_PASSES) without running, or a declared leg is still in `never_run`
    after a pass has run with it on the books. `scripts/check_leg_rotation.py` fails the fence on
    it and `desks/mt5/scripts/check_desk_health.py` reports it as a PROBLEM.
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
#: Where `department_resident` keeps its slot locks, FIFO wait tickets and per-dept queue records.
RESIDENT_LOCKS = DESK / "data" / "locks"

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

#: THE AGEING BOUND: the most consecutive passes any roster leg may be deferred before it joins the
#: ageing queue, which is served ahead of every newer wait. Two hourly passes.
MAX_DEFERRALS: int = 2

#: A leg whose measured median cost is at or below this many seconds is CHEAP. Measured on the box
#: 2026-10-29: clock_ledger 1.4 s, edge_confidence 3.2, edge_reliability 3.3, shortfall_model 4.8,
#: allocator_join 4.8, queue_compact 5.4, session_allocation 5.5, capacity 9.8, decay_monitor 10.8
#: -- all of them stale for days behind a budget they could not have dented.
CHEAP_LEG_S: float = 15.0

#: CHEAP LEGS ARE BATCHED: each pass admits cheap legs, longest-starved first, OUTSIDE the budget
#: up to this share of it (264 s of a 2,640 s core budget, ~30 cheap legs). A cheap leg the batch
#: does not reach this pass still ages in at MAX_DEFERRALS like every other leg, so the batch only
#: decides how soon, never whether.
CHEAP_BATCH_FILL: float = 0.10

#: MONEY-CRITICAL LEGS: a HARD maximum staleness. They feed the allocator, the sizing and the
#: release identity the gateway trades on, and each costs seconds, so they are admitted EVERY pass
#: outside the budget and never yielded, and are RED after MONEY_MAX_STALE_PASSES missed passes.
#: ADDITIVE TO ALWAYS_RUN, NEVER IN CONFLICT WITH IT: a leg in both is admitted and charged ONCE,
#: as always-run (`plan_pass` and `_capacity` test ALWAYS_RUN first), so a PR that moves one of
#: these into ALWAYS_RUN (decay_monitor, #494's Allocator work) lands cleanly in either order.
#: desk_health, fill_markout, placement_interlock and box_state_freshness were NEVER RUN on the
#: box on 2026-10-29.
MONEY_CRITICAL: frozenset[str] = frozenset({
    "decay_monitor", "prop_challenge_allocator", "allocator_join", "edge_reliability",
    "release_identity", "kelly_survival",
    "desk_health", "fill_markout", "placement_interlock", "box_state_freshness",
    # The publishers of three reports the hourly pass found stale on 2026-10-29: PRODUCER_YIELD
    # and CERTIFICATE_CLOCK_LAW (last 11:4xZ) and JUDGING_THROUGHPUT (14:18Z). judging_throughput
    # is already ALWAYS_RUN; listing it here only gives it the 1-pass RED bound (charged once).
    "productivity_census", "certificate_clock_law", "judging_throughput",
})
MONEY_MAX_STALE_PASSES: int = 1

#: THE AGEING QUEUE'S FLOOR. Aged legs are admitted longest-starved first into whatever budget the
#: always-run and money legs left -- and never into less than this share of the budget, so the
#: queue always drains even when the always-run set alone is past the budget (the box on
#: 2026-10-29: 3,749 s planned against 2,640 s). Unconditional admission of EVERY aged leg was
#: measured in simulation to livelock under a killing scheduler: file order hands the head of the
#: cycle the clock every time it re-ages, and the tail never runs. A queue ordered by wait cannot.
AGED_MIN_FILL: float = 0.25

#: THE OUT-OF-BUDGET BANDS STOP SHORT OF THE KILL (MF3). The ageing floor and the cheap batch are
#: admitted outside the budget, and with the mining band filling the budget first they could plan
#: a pass past the scheduler's kill -- which then takes the tail, mining included. So they may plan
#: only up to this share of the way from the budget to the kill (2,640 s budget, 3,300 s kill:
#: 3,069 s), keeping the rest of BUDGET_FILL's margin for estimate error -- and so may a granted
#: cap raise on the ageing queue's head. 0.65, not more: at 0.75 the sim (13 seeds x 72 passes,
#: +-15% runtime noise, 30 stuck legs) killed 2 passes; at 0.65, none. EXCEPT when the always-run
#: and money legs alone are already past that line: file order cannot reach the tail at all then,
#: the floor stands, and the prelude (`_lift`) decides who runs before the kill.
OUT_OF_BUDGET_SHARE: float = 0.65

#: Consecutive ledger rows ending in TIMEOUT after which a leg is a CHRONIC timeout.
CHRONIC_TIMEOUT_RUNS: int = 3

#: THE LEG_TIMEOUT CLASS (2026-10-29): math_lab (720 s) and physics_lab (700 s) hit LEG_TIMEOUT on
#: every pass with 0 artifacts moved and had not donated since 10-10. A leg is STUCK when its last
#: STUCK_TIMEOUT_RUNS ledger rows are all TIMEOUT and none moved its declared artifact (the row's
#: `output_hash` unchanged, or no artifact hash at all). Stuck is RED by name, and `measured_cap`
#: sizes its next cap from what it measurably needs instead of re-killing it at the same second.
STUCK_TIMEOUT_RUNS: int = 3

#: How a stuck leg's cap grows per further stuck timeout, and the most it may grow to: a multiple
#: of its base cap, and never more than half the plan's pass budget (one leg may not take a whole
#: bounded pass). ONE-SIDED: a cap is only ever raised from the base, never cut below it.
TIMEOUT_GROWTH: float = 1.5
TIMEOUT_GROWTH_MAX: float = 4.0
TIMEOUT_PLAN_SHARE: float = 0.5

#: A leg that finishes is given at least this multiple of the longest of its recent finishing
#: runs, so a leg measured needing 1,228 s is not handed 720 s.
MEASURED_HEADROOM: float = 1.25

#: THE RAISE IS BOUNDED ACROSS LEGS, NOT ONLY PER LEG (Auditor MF2, 2026-10-29). `measured_cap`
#: bounds each leg's raise, but thirty stuck legs raised 300 -> 1,200 s each were charged by
#: `plan_pass` at their 300 s median and ran for 1,200: the sim killed 17 of 72 passes and missed
#: 74-85 money-critical passes. Now `plan_pass` GRANTS each raise, charges the raised cap, and
#: grants at most this share of the budget in raised seconds per pass. A leg not granted this
#: pass runs at its own cap, times out, stays stuck, and asks for a bigger raise next pass.
RAISE_PASS_SHARE: float = 0.25

#: RED: a roster leg that has gone this many consecutive passes without running. One more than
#: MAX_DEFERRALS, so RED means the ageing guarantee itself did not deliver -- the leg was admitted
#: and still did not run (killed pass, crash before the ledger row), which a person must look at.
RED_AFTER_PASSES: int = MAX_DEFERRALS + 1

#: Used only to SEED `starve_passes` from attendance age the first time a record without it is read
#: (adoption on a running box): the core clock fires hourly. The seed is NOT capped, so a leg dark
#: for days is RED by name on the first pass that can see it -- and admitted on that same pass.
PASS_CADENCE_S: float = 3600.0


def stale_bound(leg: str) -> int:
    """The most consecutive passes `leg` may go without running before it is RED."""
    return MONEY_MAX_STALE_PASSES if leg in MONEY_CRITICAL else MAX_DEFERRALS

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
    # THE PROMOTION DOOR'S WRITER (2026-09-30). The door fails closed on a missing or stale
    # (> 6h) verdict, so a deferred `tier_s` pass withholds every new LIVE row: it is on the
    # money path now, and it runs every hour.
    "tier_s",
    "tier_s_door",
    # ... and the writer of the door's fourth input, reports/REPLICATION.json (heavy plan).
    "replication_civilization",
    # Without this, the core rotation can leave the judge's worker plan and measured
    # verdict rate stale while the five-minute gauntlet task continues to fire.
    "judging_throughput",
    # Discovery must hand existing rules to the judge before generating more work.
    "intake_catchup",
    # THE ONLY OFF-BOX EVIDENCE THAT THE BAR AND TICK FEED IS ALIVE (2026-10-21). Bars never
    # cross the wire, so a deferred pass leaves every reader off the box measuring a stale
    # BARS_STATE.json. It cannot cost the overrun much: it stops itself at 20 s (cap 60 s).
    "bars_state",
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


def _bound_names(node: ast.AST) -> set[str]:
    """Every name a subtree binds: stores, function/lambda parameters, defs and import aliases."""
    out: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, (ast.Store, ast.Del)):
            out.add(sub.id)
        elif isinstance(sub, ast.arg):
            out.add(sub.arg)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(sub.name)
        elif isinstance(sub, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in sub.names)
        elif isinstance(sub, (ast.Global, ast.Nonlocal)):
            out.update(sub.names)
    return out


def liftable_legs(source: Path | None = None) -> dict[str, str]:
    """Legs whose call can be built OUTSIDE `main()`, so the rotation may run them first (MF1).

    `main()` passes results between legs through its locals, so a leg can only be run ahead of
    file order when its `fn` -- the second argument of `_costed(name, fn)` -- refers to nothing
    but MODULE-LEVEL names: a bare module function (`allocator_join`), or a lambda over literals
    and module functions (`lambda: _producer("desk_health", "scripts/check_desk_health.py")`).
    A name `main()` binds itself disqualifies the leg, even if a global of that name exists. A leg
    costed more than once is liftable only when every call is the same expression.

    Returns {leg: source of its fn expression}, for `hourly_cycle` to evaluate in its own
    module globals. Read from the AST for the same reason `legs_in_order` is.
    """
    path = source or CYCLE
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return {}
    module = _bound_names(ast.Module(body=[n for n in tree.body if not isinstance(
        n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))], type_ignores=[]))
    module |= {n.name for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    import builtins
    known = module | set(dir(builtins))
    found: dict[str, str | None] = {}
    for func in tree.body:
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = _bound_names(func) - {func.name}
        for node in ast.walk(func):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "_costed" and len(node.args) >= 2
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                continue
            name, expr = node.args[0].value, node.args[1]
            inner = _bound_names(expr)
            free = {n.id for n in ast.walk(expr)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} - inner
            ok = bool(free) and free <= known and not (free & local)
            src = ast.unparse(expr) if ok else None
            if name in found and found[name] != src:
                src = None
            found[name] = src
    return {k: v for k, v in found.items() if v is not None}


def kill_for(budget_s: float) -> float:
    """The scheduler's kill line behind a plan budget: the budget is BUDGET_FILL of it."""
    return budget_s / BUDGET_FILL if budget_s > 0 else 0.0


@dataclass
class Attendance:
    """What the ledger says about each leg: how often it ran, when last, and what it costs."""

    runs: dict[str, int] = field(default_factory=dict)
    last_at: dict[str, str] = field(default_factory=dict)
    costs: dict[str, list[float]] = field(default_factory=dict)
    offset: int = 0
    #: consecutive TIMEOUT outcomes at the end of each leg's ledger history (0 = last row was not)
    timeouts: dict[str, int] = field(default_factory=dict)
    #: consecutive TIMEOUT rows that moved NO artifact (see STUCK_TIMEOUT_RUNS)
    stuck: dict[str, int] = field(default_factory=dict)
    #: the last `output_hash` each leg's ledger row carried
    last_output: dict[str, str] = field(default_factory=dict)
    #: wall seconds of each leg's recent runs that FINISHED (not TIMEOUT)
    ok_walls: dict[str, list[float]] = field(default_factory=dict)

    def stuck_timeout(self, leg: str) -> bool:
        """Has this leg timed out STUCK_TIMEOUT_RUNS times running without moving an artifact?"""
        return self.stuck.get(leg, 0) >= STUCK_TIMEOUT_RUNS

    def chronic_timeout(self, leg: str) -> bool:
        """Has this leg timed out on each of its last CHRONIC_TIMEOUT_RUNS runs?"""
        return self.timeouts.get(leg, 0) >= CHRONIC_TIMEOUT_RUNS

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
                "costs": {k: v[-COST_SAMPLES:] for k, v in self.costs.items()},
                "timeouts": {k: v for k, v in self.timeouts.items() if v},
                "stuck": {k: v for k, v in self.stuck.items() if v},
                "last_output": self.last_output,
                "ok_walls": {k: v[-COST_SAMPLES:] for k, v in self.ok_walls.items()}}

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
        tos = {str(k): int(v) for k, v in (doc.get("timeouts") or {}).items()
               if isinstance(v, (int, float))}
        stuck = {str(k): int(v) for k, v in (doc.get("stuck") or {}).items()
                 if isinstance(v, (int, float))}
        outs = {str(k): str(v) for k, v in (doc.get("last_output") or {}).items() if v}
        oks: dict[str, list[float]] = {}
        for k, v in (doc.get("ok_walls") or {}).items():
            if isinstance(v, list):
                oks[str(k)] = [float(x) for x in v if isinstance(x, (int, float))]
        return cls(runs=runs, last_at=last, costs=costs, offset=offset, timeouts=tos,
                   stuck=stuck, last_output=outs, ok_walls=oks)


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
        att.runs, att.last_at, att.costs, att.timeouts = {}, {}, {}, {}
        att.stuck, att.last_output, att.ok_walls = {}, {}, {}
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
                timed_out = str(row.get("outcome") or "").upper().startswith("TIMEOUT")
                out_hash = row.get("output_hash")
                moved = bool(out_hash) and out_hash != att.last_output.get(name)
                if out_hash:
                    att.last_output[name] = str(out_hash)
                if timed_out:
                    att.timeouts[name] = att.timeouts.get(name, 0) + 1
                    att.stuck[name] = 0 if moved else att.stuck.get(name, 0) + 1
                else:
                    att.timeouts[name] = 0
                    att.stuck[name] = 0
                    ok_wall = row.get("wall_s")
                    if isinstance(ok_wall, (int, float)) and ok_wall > 0:
                        att.ok_walls.setdefault(name, []).append(float(ok_wall))
                        del att.ok_walls[name][:-COST_SAMPLES]
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
    #: every leg the cycle declares (the roster of every plan), so the next pass can tell a leg
    #: that has been on the books through a whole pass from one wired since
    declared: list[str] = field(default_factory=list)
    #: consecutive passes each roster leg has gone without running, as of the start of this pass
    starve_passes: dict[str, int] = field(default_factory=dict)
    #: admitted OUTSIDE the budget arithmetic and never yielded on overrun: aged or cheap legs
    protected: set[str] = field(default_factory=set)
    aged: list[str] = field(default_factory=list)
    cheap: list[str] = field(default_factory=list)
    #: mining legs admitted in the mining band this pass (MF3)
    mining: list[str] = field(default_factory=list)
    #: aged legs the ageing queue could not reach this pass (oversubscribed): first next pass
    queued: list[str] = field(default_factory=list)
    chronic_timeouts: list[str] = field(default_factory=list)
    #: timing out every run with no artifact moved (STUCK_TIMEOUT_RUNS) -- RED by name
    stuck_timeouts: list[str] = field(default_factory=list)
    #: RED legs by name, each with the reason; empty means GREEN
    red: dict[str, str] = field(default_factory=dict)
    #: whether the bound is satisfiable inside the budget (see `_capacity`)
    capacity: dict[str, Any] = field(default_factory=dict)
    #: the scheduler's kill line for this pass (`kill_for`); 0 = unbounded
    kill_s: float = 0.0
    #: RUN FIRST, before file order (Auditor MF1): protected legs (money-critical, then the ageing
    #: queue) whose file-order position the plan projects past the budget line. Prelude order.
    lifted: list[str] = field(default_factory=list)
    #: protected legs projected past the budget line that could NOT be run first (their call
    #: closes over `main()` locals, or lifting would push a reachable always-run leg past the kill)
    unreachable: list[str] = field(default_factory=list)
    #: the seconds `plan_pass` charged each admitted leg (its median, plus any granted raise)
    charged: dict[str, float] = field(default_factory=dict)
    #: per-leg cap seconds this pass GRANTS above the leg's median (MF2); absent = no raise
    raise_grants: dict[str, float] = field(default_factory=dict)

    def cap_for(self, leg: str, att: Attendance | None, base_s: float) -> tuple[float, str]:
        """The cap `leg` runs under this pass: `measured_cap`, clamped to what the plan GRANTED.

        On a bounded plan a raise the plan did not grant is not applied: an ungranted raise is
        seconds the plan never charged, which is how thirty stuck legs killed the pass (MF2). An
        unbounded plan (the department residents, no time limit) keeps `measured_cap` as is."""
        base = float(base_s)
        if self.budget_s <= 0:
            return measured_cap(leg, att, base, 0.0)
        grant = self.raise_grants.get(leg)
        if not grant:
            return base, ""
        cap, why = measured_cap(leg, att, base, self.budget_s)
        if att is not None and att.stuck_timeout(leg):
            # A GRANTED STUCK LEG GETS ITS WHOLE BOUNDED CEILING AT ONCE: rationed, it gets a turn
            # only every few passes, and growing x1.5 per turn would take a day to reach what it
            # needs -- while every turn short of it is another zero-output kill.
            ceiling = max(base, min(base * TIMEOUT_GROWTH_MAX, TIMEOUT_PLAN_SHARE * self.budget_s))
            cap, why = max(cap, ceiling), (f"stuck: {att.stuck.get(leg, 0)} zero-output "
                                           f"LEG_TIMEOUTs at {base:.0f}s; granted its bounded "
                                           f"ceiling")
        cap = min(cap, max(base, float(grant)))
        if cap <= base:
            return base, ""
        return cap, f"{why}; granted {grant:.0f}s of this pass's raise allowance"

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
        Nothing is cancelled: a yielded leg's `starve_passes` grows, and at MAX_DEFERRALS it joins
        the ageing queue.

        The always-run set, the never-run set and the PROTECTED set (aged or cheap legs) are never
        yielded. That last exemption is load-bearing: when an always-run leg times out early in the
        pass the clock is past the budget for the rest of it, and without the exemption an aged
        leg would be admitted on paper and yielded in fact -- the same starvation by another door.
        """
        if leg in self.deferred:
            return False, self.why.get(leg, "deferred by rotation")
        if leg in ALWAYS_RUN or leg in self.protected:
            return True, ""
        if self.budget_s > 0 and elapsed_s > self.budget_s and att.runs.get(leg, 0) > 0:
            waited = self.starve_passes.get(leg, 0) + 1
            return False, (f"budget overrun at {elapsed_s:.0f}s of {self.budget_s:.0f}s: this "
                           f"pass yields to legs that have never run (wait {waited} of at most "
                           f"{MAX_DEFERRALS}; then it joins the ageing queue)")
        return True, ""


def _pid_alive(pid: int) -> bool:
    """Is `pid` running? True when it cannot be measured: a guess must never hide a wait."""
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
    except ImportError:
        return True
    try:
        return bool(psutil.pid_exists(pid))
    except Exception:
        return True


def resident_liveness(locks: Path | None = None, *, now: datetime | None = None,
                      max_wait_s: float | None = None) -> dict[str, Any]:
    """THE DEPARTMENT RESIDENTS' QUEUE, SAME CLASS AS A STARVED LEG (2026-10-29).

    ~15 dept/forest residents finished passes of 1,200-9,231 s and then sat 3-5 h waiting for one
    of `DEPT_CONCURRENT_PASSES` slots, unmeasured. The queue is longest-wait-first
    (`department_resident._wait_ticket`), so the wait is bounded by the passes ahead of it -- and
    this is where that bound is checked. Reads only what the residents wrote:

        waiting   every live FIFO ticket, longest wait first, with seconds waited so far
        last      each department's last admitted wait and last pass seconds
        red       a resident CURRENTLY waiting past `max_wait_s`, by name
        expected_wait_s / oversubscribed
                  sum of every department's last pass over the slot count: the wait a resident
                  must expect at the back of the queue. Past the bound, re-ordering cannot help;
                  the slot count is the box's to raise. It is never cut here.
    """
    where = locks or RESIDENT_LOCKS
    t1 = now or datetime.now(tz=UTC)
    waiting: list[dict[str, Any]] = []
    last: dict[str, dict[str, Any]] = {}
    bound_seen: float | None = None
    slots_seen: int | None = None
    try:
        tickets = list(where.glob("dept_wait_*.ticket"))
        queues = list(where.glob("dept_queue_*.json"))
    except OSError:
        tickets, queues = [], []
    for path in tickets:
        try:
            _, _, stamp, pid, dept = path.stem.split("_", 4)
            since = datetime.fromtimestamp(int(stamp) / 1e9, tz=UTC)
            owner = int(pid)
        except (ValueError, OSError, OverflowError):
            continue
        if not _pid_alive(owner):
            continue
        waiting.append({"dept": dept, "waiting_s": round((t1 - since).total_seconds(), 1),
                        "since": since.isoformat(timespec="seconds")})
    for path in queues:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not doc.get("dept"):
            continue
        last[str(doc["dept"])] = {k: doc.get(k) for k in
                                  ("waited_s", "admitted_at", "pass_s", "pass_status")}
        if isinstance(doc.get("max_wait_s"), (int, float)):
            bound_seen = float(doc["max_wait_s"])
        if isinstance(doc.get("slots"), (int, float)):
            slots_seen = int(doc["slots"])
    bound = float(max_wait_s if max_wait_s is not None else
                  bound_seen if bound_seen is not None else
                  float(os.environ.get("DEPT_MAX_WAIT_S", "7200") or 7200))
    slots = max(1, slots_seen or int(os.environ.get("DEPT_CONCURRENT_PASSES", "3") or 3))
    waiting.sort(key=lambda w: -float(w["waiting_s"]))
    red = {w["dept"]: (f"resident waiting {w['waiting_s']:.0f}s for one of {slots} department "
                       f"slots, past the {bound:.0f}s bound (since {w['since']})")
           for w in waiting if float(w["waiting_s"]) > bound}
    total = sum(float(v["pass_s"]) for v in last.values()
                if isinstance(v.get("pass_s"), (int, float)))
    expected = total / slots if last else None
    return {"max_wait_s": bound, "slots": slots, "n_waiting": len(waiting),
            "waiting": waiting, "last": dict(sorted(last.items())),
            "expected_wait_s": None if expected is None else round(expected, 1),
            "oversubscribed": bool(expected is not None and expected > bound),
            "red": dict(sorted(red.items()))}


def liveness(ageing: dict[str, Any], residents: dict[str, Any] | None = None) -> dict[str, Any]:
    """RED/GREEN over every plan's latest pass, naming each RED leg and the plan it starved in,
    and every department resident waiting past its slot-queue bound."""
    by_plan: dict[str, list[str]] = {}
    why: dict[str, str] = {}
    for plan, st in sorted(ageing.items()):
        red = st.get("red") if isinstance(st, dict) else None
        if isinstance(red, dict) and red:
            by_plan[plan] = sorted(map(str, red))
            for leg, reason in red.items():
                why.setdefault(str(leg), f"[{plan}] {reason}")
    res_red = dict((residents or {}).get("red") or {})
    return {"verdict": "RED" if why or res_red else "GREEN", "n_red": len(why) + len(res_red),
            "red_legs": sorted(why),
            "red_residents": sorted(res_red), "residents_why": res_red,
            "red_by_plan": by_plan, "why": dict(sorted(why.items())),
            "max_deferrals": MAX_DEFERRALS, "red_after_passes": RED_AFTER_PASSES,
            "money_critical": sorted(MONEY_CRITICAL),
            "money_max_stale_passes": MONEY_MAX_STALE_PASSES}


def measured_cap(leg: str, att: Attendance | None, base_s: float,
                 plan_budget_s: float = 0.0) -> tuple[float, str]:
    """THE CAP A LEG MEASURABLY NEEDS, never less than the cap it was given (`base_s`).

    A cap below a leg's real runtime is the truncated-job defect: the leg is killed at the same
    second every pass and moves nothing (math_lab at 720 s, physics_lab at 700 s, 0 artifacts,
    no donation since 10-10). Two one-sided raises:

      MEASURED  -- MEASURED_HEADROOM x the longest of its recent FINISHING runs.
      STUCK     -- after STUCK_TIMEOUT_RUNS zero-output timeouts, base x TIMEOUT_GROWTH per stuck
                   run past the threshold (starting at one step), until it finishes; a finish
                   resets `stuck` and the MEASURED raise then holds the cap at what it took.

    Both are bounded by TIMEOUT_GROWTH_MAX x base and, on a bounded plan, TIMEOUT_PLAN_SHARE of the
    plan budget. ALWAYS_RUN legs are never raised here (tier_s's cap is its owner's), and the cap
    never falls below `base_s`.
    """
    base = float(base_s)
    if att is None or base <= 0 or leg in ALWAYS_RUN:
        return base, ""
    ceiling = base * TIMEOUT_GROWTH_MAX
    if plan_budget_s > 0:
        ceiling = min(ceiling, TIMEOUT_PLAN_SHARE * plan_budget_s)
    ceiling = max(base, ceiling)
    want, why = base, ""
    oks = att.ok_walls.get(leg) or []
    if oks:
        need = MEASURED_HEADROOM * max(oks)
        if need > want:
            want, why = need, (f"measured: longest recent finish {max(oks):.0f}s x "
                               f"{MEASURED_HEADROOM}")
    n = att.stuck.get(leg, 0)
    if n >= STUCK_TIMEOUT_RUNS:
        grown = base * TIMEOUT_GROWTH ** (n - STUCK_TIMEOUT_RUNS + 1)
        if grown > want:
            want, why = grown, (f"stuck: {n} zero-output LEG_TIMEOUTs at {base:.0f}s; cap "
                                f"grown x{TIMEOUT_GROWTH} per stuck run")
    if want > ceiling:
        want, why = ceiling, why + f" (held at the {ceiling:.0f}s ceiling)"
    return max(base, want), why


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


def _rank(leg: str, att: Attendance, now: datetime, order: dict[str, int],
          dec: Decision | None = None) -> tuple[int, int, float, int]:
    """Sort key for the budget band: never-run first, then stale, then CHRONIC TIMEOUTS last;
    within a tier the longest-starved, then the oldest, then file order."""
    if leg in ALWAYS_RUN:
        tier = 0
    elif dec is not None and leg in dec.chronic_timeouts:
        tier = 3
    elif att.runs.get(leg, 0) <= 0:
        tier = 1
    else:
        tier = 2
    waited = dec.starve_passes.get(leg, 0) if dec is not None else 0
    age = att.age_s(leg, now)
    return (tier, -waited, -age if age != float("inf") else float("-inf"), order.get(leg, 0))


def _parse_at(raw: Any) -> datetime | None:
    """An ISO stamp as an aware UTC datetime, or None. Naive stamps are read as UTC."""
    if not raw:
        return None
    try:
        t = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _plan_state(prior: dict[str, Any] | None, plan: str) -> dict[str, Any] | None:
    """The previous pass OF THIS PLAN's ageing state, from the record's `ageing[plan]`.

    PER PLAN, BECAUSE THE RECORD IS SHARED. The core task and every department resident
    (`department_resident.run_pass`, HOURLY_PLAN=dept:<name>) write the same LEG_ROTATION.json.
    Reading one top-level map would let a dept pass's write reset the core plan's counts every
    hour, and nothing would ever age."""
    if not prior:
        return None
    ageing = prior.get("ageing")
    state = ageing.get(plan) if isinstance(ageing, dict) else None
    return state if isinstance(state, dict) else None


def starvation(roster: list[str], att: Attendance, prior: dict[str, Any] | None,
               now: datetime, plan: str = "core") -> dict[str, int]:
    """Consecutive passes each roster leg has gone without running, as of THIS pass's start.

    A leg whose ledger `last_at` is at or after the previous pass's start ran in it: 0. Otherwise
    it is the previous count plus one -- whether it was deferred, yielded, or admitted and never
    reached because the pass was killed. All three are the same thing to the leg.

    No prior record at all is a fresh box: nothing is known to have waited, so every count is 0.
    A prior record with no ageing state for this plan is a running box adopting this code (or a
    plan's first pass): the count is seeded from attendance age in PASS_CADENCE_S units, capped
    nowhere (a never-run leg is seeded at MAX_DEFERRALS), so a leg already starved for days is
    admitted on the very first pass and is RED by name until it has run.
    """
    if not prior:
        return dict.fromkeys(roster, 0)
    state = _plan_state(prior, plan)
    prev_start = _parse_at(state.get("pass_started")) if state else None
    raw_map = state.get("starve_passes") if state else None
    prev_map = ({str(k): int(v) for k, v in raw_map.items() if isinstance(v, (int, float))}
                if isinstance(raw_map, dict) and prev_start is not None else None)
    cutoff = prev_start.replace(microsecond=0) if prev_start is not None else None
    out: dict[str, int] = {}
    for leg in roster:
        last = _parse_at(att.last_at.get(leg))
        if cutoff is not None and last is not None and last >= cutoff:
            out[leg] = 0
        elif prev_map is not None:
            # A leg absent from the previous map was wired since: it has missed no pass yet.
            out[leg] = prev_map[leg] + 1 if leg in prev_map else 0
        else:
            age = att.age_s(leg, now)
            out[leg] = (MAX_DEFERRALS if age == float("inf")
                        else int(max(0.0, age) // PASS_CADENCE_S))
    return out


def _red(dec: Decision, prior: dict[str, Any] | None,
         att: Attendance | None = None) -> dict[str, str]:
    """RED by name: a roster leg past its `stale_bound`, or still never-run after a pass ran."""
    red: dict[str, str] = {}
    for leg in dec.roster:
        n = dec.starve_passes.get(leg, 0)
        if n > stale_bound(leg):
            kind = "money-critical " if leg in MONEY_CRITICAL else ""
            red[leg] = (f"starved: {n} consecutive passes without a run, past its {kind}bound "
                        f"of {stale_bound(leg)}")
    for leg in dec.stuck_timeouts:
        n = att.stuck.get(leg, 0) if att is not None else STUCK_TIMEOUT_RUNS
        red.setdefault(leg, f"LEG_TIMEOUT {n} runs running with 0 artifacts moved: the leg is "
                            "killed before it writes or donates (needs incremental "
                            "checkpoint/donate; its cap is now sized by `measured_cap`)")
    if prior:
        declared_before = prior.get("declared")
        known = (set(map(str, declared_before)) if isinstance(declared_before, list) else None)
        for leg in dec.never_run:
            # Adoption (no `declared` yet): every never-run leg has had passes to run in.
            if known is None or leg in known:
                red.setdefault(leg, "never run: still absent from the compute ledger after a "
                                    "pass of the cycle ran with it declared")
    return red


def _capacity(roster: list[str], att: Attendance, bud: float,
              kill_s: float | None = None) -> dict[str, Any]:
    """CAN THE BOUND BE MET AT ALL? Published so an oversubscribed plan is a number, not a guess.

    Per pass, the non-always legs get the budget the always-run and money legs leave (never less
    than AGED_MIN_FILL of it) plus the cheap batch: `headroom_s`. `passes_to_cover` is how many
    passes the rest of the roster takes at that rate; the plan fits the MAX_DEFERRALS bound when it
    is at most MAX_DEFERRALS + 1. Past it (`oversubscribed`), the ageing queue still runs every leg
    within about `passes_to_cover` passes -- longest wait first, so the wait is bounded and fair --
    but legs past their bound are RED by name, and the scheduler's limit is what must move. Never a
    leg. `always_run_past_kill` says the always-run set ALONE is past the scheduler's kill line:
    file order then cannot reach the tail at all, which is why protected legs are run first."""
    kill = kill_for(bud) if kill_s is None else float(kill_s)
    always = sum(att.cost_s(leg) for leg in roster if leg in ALWAYS_RUN)
    money = sum(att.cost_s(leg) for leg in roster
                if leg in MONEY_CRITICAL and leg not in ALWAYS_RUN)
    other = sum(att.cost_s(leg) for leg in roster
                if leg not in ALWAYS_RUN and leg not in MONEY_CRITICAL)
    per_pass = max(bud - always - money, AGED_MIN_FILL * bud) + CHEAP_BATCH_FILL * bud
    cover = (other / per_pass) if per_pass > 0 else float("inf")
    return {"always_run_s": round(always, 1), "money_critical_s": round(money, 1),
            "other_legs_s": round(other, 1), "per_pass_s": round(per_pass, 1),
            "headroom_s": round(per_pass, 1), "kill_s": round(kill, 1),
            "always_run_past_kill": bool(kill > 0 and always > kill),
            "passes_to_cover": None if cover == float("inf") else round(cover, 2),
            "bound_passes": MAX_DEFERRALS + 1,
            "oversubscribed": cover > MAX_DEFERRALS + 1}


def _lift(dec: Decision, roster: list[str], liftable: set[str] | frozenset[str],
          line: float, kill: float) -> None:
    """MF1: RUN THE PROTECTED LEGS THE KILL WOULD OTHERWISE TAKE, FIRST.

    `main()` runs in file order and the scheduler kills the pass where it stands, so a leg the plan
    ADMITTED is still lost if the seconds admitted ahead of it pass the kill -- on the box the
    always-run set alone (3,749 s) is past the 3,300 s kill, and the eight money-critical legs in
    the last third of the file missed 72 of 72 passes in simulation (desk_health, the reader of
    this very RED, is the last leg of all). So the plan projects file-order finish times from the
    charged seconds, and every PROTECTED leg (money-critical first, then the ageing queue longest
    wait first) whose projected finish passes the budget line is moved into a PRELUDE that runs
    before the first leg. Legs that fit keep their file-order place, and every "must run after"
    in `main()` with them: only a leg that would otherwise not run at all gives that up, and it
    then reads the previous pass's inputs -- one pass stale, against never.

    Refused, and published in `unreachable` by name, when the leg's call cannot be built outside
    `main()` (`liftable_legs`), or when moving its seconds to the front would push an always-run
    leg that is projected to finish inside the kill past it."""
    money = [leg for leg in roster if leg in MONEY_CRITICAL and leg in dec.admitted
             and leg not in ALWAYS_RUN]
    cands = money + [leg for leg in dec.aged if leg not in money]
    order = {leg: i for i, leg in enumerate(roster)}
    lifted: list[str] = []
    refused: dict[str, str] = {}

    def finish() -> dict[str, float]:
        t = sum(dec.charged.get(leg, 0.0) for leg in lifted)
        out: dict[str, float] = {}
        for leg in roster:
            if leg in dec.admitted and leg not in lifted:
                t += dec.charged.get(leg, 0.0)
                out[leg] = t
        return out

    changed = True
    while changed:
        changed = False
        for leg in cands:
            if leg in lifted or leg in refused:
                continue
            fin = finish()
            if fin.get(leg, 0.0) <= line:
                continue
            cost = dec.charged.get(leg, 0.0)
            pushed = [a for a in roster[:order[leg]] if a in ALWAYS_RUN and a in fin
                      and fin[a] <= kill < fin[a] + cost]
            if leg not in liftable:
                refused[leg] = ("its call closes over main() locals, so it cannot run ahead of "
                                "file order")
            elif pushed:
                refused[leg] = (f"running it first would push always-run {pushed[0]} past the "
                                f"{kill:.0f}s kill")
            else:
                lifted.append(leg)
                changed = True
    dec.lifted = sorted(lifted, key=lambda n: (n not in MONEY_CRITICAL, cands.index(n)))
    for leg in dec.lifted:
        dec.why[leg] = (dec.why.get(leg, "") + f"; RUN FIRST: its file-order place is projected "
                        f"past the {line:.0f}s budget line ({kill:.0f}s kill), where it would not "
                        "run at all")
    fin = finish()
    for leg, reason in refused.items():
        dec.unreachable.append(leg)
        dec.why[leg] = (dec.why.get(leg, "") + f"; UNREACHABLE: projected to finish at "
                        f"{fin.get(leg, 0.0):.0f}s, past the {line:.0f}s budget line; {reason}")


def plan_pass(roster: list[str], att: Attendance, *, plan: str, budget_s: float | None = None,
              now: datetime | None = None, full_roster: list[str] | None = None,
              prior: dict[str, Any] | None = None, kill_s: float | None = None,
              liftable: set[str] | frozenset[str] | None = None,
              mining: set[str] | frozenset[str] | None = None) -> Decision:
    """Choose this pass's membership so that every admitted leg is actually REACHED.

    Four bands, in this order:

      1. ALWAYS_RUN -- admitted, charged its realised cost (a chronic timeout included).
      2. PROTECTED, outside the budget arithmetic, never yielded -- MONEY_CRITICAL every pass;
         the AGEING QUEUE (legs that waited MAX_DEFERRALS passes), longest wait first, into
         max(budget left, AGED_MIN_FILL * budget); the CHEAP BATCH (cost <= CHEAP_LEG_S) into
         CHEAP_BATCH_FILL * budget. THIS IS THE FIX: before it, every one of these was judged by
         `spent + cost <= budget` after band 1 had already spent past the budget, so a one-second
         leg could wait forever behind a timing-out always-run leg.
      3. BUDGET -- the rest, oldest-first (never-run first, chronic timeouts last), while the
         planned seconds stay inside the budget.
      4. DEFERRED -- what band 3 could not fit. Each deferral increments `starve_passes`, so it is a
         turn to wait that ends in the ageing queue, never a leg removed.

    EVERY LEG IS CHARGED WHAT IT WILL BE ALLOWED TO RUN (MF2). A leg `measured_cap` would raise
    is charged its median plus the raise, and the raise is GRANTED (`raise_grants`, read by
    `Decision.cap_for`) only while this pass's raised seconds stay inside RAISE_PASS_SHARE of the
    budget; past it the leg is charged and capped at its own cap this pass.

    MINING IS NEVER THROTTLED (MF3; constitution: no subsystem may throttle mining). `mining`
    (the discovery department's legs, from `hourly_cycle.department_of`) is admitted FIRST in the
    budget band -- every pass, while the planned seconds stay inside the budget -- and never
    yielded. Before this the out-of-budget bands (ageing floor, cheap batch, raises) took the
    budget the mining legs had under the LIVE policy: -0..4% mining runs on a healthy box, ~9% with
    stuck legs. A mining leg the budget cannot fit this pass ages in like every other leg.

    ADMITTED IS NOT ENOUGH: IT MUST BE REACHED (MF1). With `liftable` (the legs whose call can be
    built outside `main()`), `_lift` moves protected legs projected past the budget line into a
    prelude that runs first. Without it, file order is unchanged.

    An unbounded budget (0.0) admits the whole roster: the department residents have no time
    limit, and adding one here would be the throttle this desk does not permit.

    `roster` is what THIS plan may run; `full_roster` is every leg the cycle declares. Admission
    is charged against the first, but `never_run` and `outside_window` are measured against the
    second -- a leg dark on the heavy clock is still dark, and a report that only ever named the
    legs of the plan that happened to be running would hide exactly the defect this file exists
    to end. `prior` is the previous published record (`load_record()`), which carries the
    persisted per-plan `ageing` state; without it nothing ages.
    """
    t0 = now or datetime.now(tz=UTC)
    bud = budget_for(plan) if budget_s is None else budget_s
    kill = kill_for(bud) if kill_s is None else float(kill_s)
    order = {leg: i for i, leg in enumerate(roster)}
    everything = list(full_roster) if full_roster is not None else list(roster)
    dec = Decision(plan=plan, budget_s=bud, roster=list(roster), declared=sorted(everything),
                   kill_s=kill if bud > 0 else 0.0)
    dec.never_run = sorted(leg for leg in everything if att.runs.get(leg, 0) <= 0)
    window_s = ROTATION_WINDOW_H * 3600.0
    dec.outside_window = sorted(leg for leg in everything if att.age_s(leg, t0) > window_s)
    dec.starve_passes = starvation(roster, att, prior, t0, plan=plan)
    dec.chronic_timeouts = sorted(leg for leg in roster if att.chronic_timeout(leg))
    dec.stuck_timeouts = sorted(leg for leg in roster if att.stuck_timeout(leg))
    dec.red = _red(dec, prior, att)
    if bud <= 0:
        dec.admitted = set(roster)
        dec.why = dict.fromkeys(roster, "unbounded plan: no time limit to rotate against")
        dec.planned_s = sum(att.cost_s(leg) for leg in roster)
        return dec
    spent = 0.0
    raise_left = RAISE_PASS_SHARE * bud

    def want(leg: str) -> tuple[float, float]:
        """(median cost, the raise `measured_cap` would add), with the median standing in for
        the leg's own cap. Only for a leg whose cap is binding: its last run hit it (a TIMEOUT
        row), or it last FINISHED well past its median -- a median held down by capped runs, the
        stuck leg that has just finished at its raised cap and must keep it."""
        cost = att.cost_s(leg)
        oks = att.ok_walls.get(leg) or []
        binding = att.timeouts.get(leg, 0) > 0 or (bool(oks) and max(oks) > TIMEOUT_GROWTH * cost)
        if leg in ALWAYS_RUN or not binding:
            return cost, 0.0
        cap = measured_cap(leg, att, cost, bud)[0]
        if att.stuck_timeout(leg):
            cap = max(cap, min(cost * TIMEOUT_GROWTH_MAX, TIMEOUT_PLAN_SHARE * bud))
        return cost, max(0.0, cap - cost)

    def charge(leg: str, commit: bool = False, raise_ok: bool = True) -> float:
        """Seconds to charge `leg`; on commit, record the charge and grant its raise."""
        nonlocal raise_left
        cost, extra = want(leg)
        extra = extra if raise_ok else 0.0
        # WHOLE OR NOT AT ALL: a part-raise still kills a stuck leg short of what it needs, so it
        # is seconds spent for nothing. The first raise of a pass is always whole (the per-leg
        # ceiling bounds it), so the allowance can never starve every stuck leg forever.
        granted = extra if extra > 0 and (extra <= raise_left or not dec.raise_grants) else 0.0
        if commit:
            dec.charged[leg] = cost + granted
            if granted > 0:
                raise_left = max(0.0, raise_left - granted)
                dec.raise_grants[leg] = cost + granted
        return cost + granted

    rest: list[str] = []
    cheap_pool: list[str] = []
    aged_pool: list[str] = []
    mine_pool: list[str] = []
    for leg in roster:
        cost = att.cost_s(leg)
        waited = dec.starve_passes.get(leg, 0)
        if leg in ALWAYS_RUN:
            dec.admitted.add(leg)
            spent += charge(leg, commit=True)
            dec.why[leg] = ("always-run: irreversible or on the money path"
                            + (f" (CHRONIC TIMEOUT: charged its realised {cost:.0f}s)"
                               if leg in dec.chronic_timeouts else ""))
        elif leg in MONEY_CRITICAL:
            dec.admitted.add(leg)
            dec.protected.add(leg)
            spent += charge(leg, commit=True)
            dec.why[leg] = (f"money-critical: admitted every pass outside the budget (hard bound "
                            f"{MONEY_MAX_STALE_PASSES} missed pass)")
        elif mining and leg in mining and waited >= 1:
            mine_pool.append(leg)
        elif waited >= MAX_DEFERRALS:
            aged_pool.append(leg)
        elif leg in att.costs and cost <= CHEAP_LEG_S:
            cheap_pool.append(leg)
        else:
            rest.append(leg)
    line = bud + OUT_OF_BUDGET_SHARE * max(0.0, kill - bud)
    past_line = spent >= line
    # MINING, INSIDE THE BUDGET AND AHEAD OF EVERY OTHER BAND THAT SPENDS IT (MF3).
    for leg in sorted(mine_pool, key=lambda n: _rank(n, att, t0, order, dec)):
        if spent + charge(leg) <= bud:
            spent += charge(leg, commit=True)
            dec.admitted.add(leg)
            dec.protected.add(leg)
            dec.mining.append(leg)
            dec.why[leg] = ("mining: admitted every pass inside the budget, ahead of the ageing, "
                            "cheap and rotation bands, and never yielded (mining is never "
                            "throttled)")
        elif dec.starve_passes.get(leg, 0) >= MAX_DEFERRALS:
            aged_pool.append(leg)
        else:
            rest.append(leg)
    # THE AGEING QUEUE: longest-starved first, then oldest `last_at`, then file order -- into what
    # the budget has left, never less than AGED_MIN_FILL of it, and never fewer than one leg.
    floor = AGED_MIN_FILL * bud if past_line else min(AGED_MIN_FILL * bud, max(0.0, line - spent))
    aged_allow = max(bud - spent, floor)
    aged_spent = 0.0
    queue = sorted(aged_pool, key=lambda n: (-dec.starve_passes.get(n, 0),
                                             -min(att.age_s(n, t0), 1e18), order.get(n, 0)))
    for pos, leg in enumerate(queue):
        cost = charge(leg)
        waited = dec.starve_passes.get(leg, 0)
        fits = aged_spent + cost <= aged_allow
        # The queue's head is admitted even when it does not fit -- but not its RAISE, when the
        # raise would plan the pass past the kill-side line: that raise waits for a pass with room
        # (the leg still runs, at its own cap, and stays RED by name while it is stuck).
        raise_ok = fits or past_line or spent + cost <= line
        if not dec.aged or fits:
            cost = charge(leg, commit=True, raise_ok=raise_ok)
            dec.admitted.add(leg)
            dec.protected.add(leg)
            dec.aged.append(leg)
            aged_spent += cost
            spent += cost
            dec.why[leg] = (f"aged: {waited} consecutive passes without a run reached the "
                            f"{MAX_DEFERRALS}-pass bound; admitted from the ageing queue")
        else:
            dec.deferred.add(leg)
            dec.queued.append(leg)
            dec.why[leg] = (f"aged, queued: position {pos + 1} of {len(queue)} in the ageing "
                            f"queue ({waited} passes waited; {aged_allow:.0f}s of aged "
                            "admission this pass); it is ahead of every newer wait next pass")
    # THE CHEAP BATCH: longest-starved first, then oldest, outside the budget up to its allowance.
    allowance = max(CHEAP_LEG_S, CHEAP_BATCH_FILL * bud)
    if not past_line:
        allowance = min(allowance, max(0.0, line - spent))
    cheap_spent = 0.0
    for leg in sorted(cheap_pool, key=lambda n: _rank(n, att, t0, order, dec)):
        cost = charge(leg)
        if cheap_spent + cost <= allowance:
            cost = charge(leg, commit=True)
            dec.admitted.add(leg)
            dec.protected.add(leg)
            dec.cheap.append(leg)
            cheap_spent += cost
            spent += cost
            dec.why[leg] = (f"cheap: measured {cost:.1f}s <= {CHEAP_LEG_S:.0f}s; admitted in "
                            f"this pass's {allowance:.0f}s cheap batch")
        else:
            rest.append(leg)
    for leg in sorted(rest, key=lambda n: _rank(n, att, t0, order, dec)):
        cost = charge(leg)
        if spent + cost <= bud:
            spent += charge(leg, commit=True)
            dec.admitted.add(leg)
            dec.why[leg] = ("never run: admitted ahead of every stale leg"
                            if att.runs.get(leg, 0) <= 0 else
                            f"rotation: idle {att.age_s(leg, t0) / 3600.0:.1f}h")
        else:
            dec.deferred.add(leg)
            waited = dec.starve_passes.get(leg, 0) + 1
            dec.why[leg] = (f"deferred this pass ({waited} of at most {MAX_DEFERRALS}): "
                            f"{cost:.0f}s would pass the {bud:.0f}s budget ({spent:.0f}s "
                            f"planned); it joins the ageing queue (longest wait first) once "
                            f"it has waited {MAX_DEFERRALS} passes"
                            + (" [CHRONIC TIMEOUT: ranked last]"
                               if leg in dec.chronic_timeouts else ""))
    for leg, cap in dec.raise_grants.items():
        dec.why[leg] = (dec.why.get(leg, "") + f"; cap raise GRANTED: charged {cap:.0f}s "
                        f"(median {att.cost_s(leg):.0f}s)")
    dec.planned_s = spent
    dec.capacity = _capacity(roster, att, bud, kill)
    dec.capacity["raised_s"] = round(sum(cap - att.cost_s(leg)
                                         for leg, cap in dec.raise_grants.items()), 1)
    dec.capacity["raise_allowance_s"] = round(RAISE_PASS_SHARE * bud, 1)
    if liftable is not None:
        _lift(dec, roster, liftable, line, kill)
    return dec


def record(dec: Decision, att: Attendance, ran: list[str], *, path: Path | None = None,
           started: datetime | None = None, now: datetime | None = None,
           complete: bool = True, residents: dict[str, Any] | None = None) -> dict[str, Any]:
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
        "pass_started": (started or t1).isoformat(),
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
        "max_deferrals": MAX_DEFERRALS,
        "cheap_leg_s": CHEAP_LEG_S,
        "starve_passes": dict(sorted(dec.starve_passes.items())),
        "aged_admitted": sorted(dec.aged),
        "aged_queued": list(dec.queued),
        "cheap_admitted": sorted(dec.cheap),
        "chronic_timeouts": list(dec.chronic_timeouts),
        "stuck_timeouts": list(dec.stuck_timeouts),
        "capacity": dict(dec.capacity),
        "declared": list(dec.declared),
        "attendance": att.to_json(),
    }
    out = path or RECORD
    # ONE WRITER AT A TIME (Auditor 2026-10-29). The core task and ~23 department residents share
    # this file and each MERGES the others' `ageing` state into its own write: a read-modify-write
    # done unlocked lets two writers read the same file and the second write silently drops the
    # first's plan state -- which resets that plan's wait counts, the defect `ageing` exists to
    # end. The merge and the replace now run under the repo's OS lock on a sidecar
    # (`alert_ledger.os_lock`: a kernel lock, released when its holder dies), and the temp file is
    # per-writer so two replaces never share one. A lock that cannot be had in time is recorded as
    # `write_error`; the pass is never failed by its own measurement.
    try:
        from libs.ops.alert_ledger import os_lock
        out.parent.mkdir(parents=True, exist_ok=True)
        with os_lock(out.with_name(out.name + ".flock"), timeout_s=RECORD_LOCK_WAIT_S):
            _merge_and_write(doc, dec, t1, out, residents)
    except (OSError, TimeoutError, ImportError) as exc:
        doc["write_error"] = f"{type(exc).__name__}: {exc}"
        doc.setdefault("liveness", liveness({dec.plan: {"red": dict(sorted(dec.red.items()))}},
                                            residents))
    return doc


#: How long `record` waits for the shared LEG_ROTATION.json writer lock.
RECORD_LOCK_WAIT_S: float = 30.0


def _merge_and_write(doc: dict[str, Any], dec: Decision, t1: datetime, out: Path,
                     residents: dict[str, Any] | None) -> None:
    """Merge the other plans' ageing state into `doc` and atomically replace `out` (caller holds
    the writer lock)."""
    # THE AGEING STATE, PER PLAN, CARRIED ACROSS WRITERS. Core and every department resident
    # share this file, so each write keeps the other plans' fresh state and replaces only its own.
    # The next pass of this plan reads `ageing[plan]` to count how long each leg has waited.
    ageing: dict[str, Any] = {}
    prev = load_record(out).get("ageing")
    for name, st in (prev.items() if isinstance(prev, dict) else ()):
        gen = _parse_at(st.get("generated")) if isinstance(st, dict) else None
        if name != dec.plan and gen is not None and \
                (t1 - gen).total_seconds() <= ROTATION_WINDOW_H * 3600.0:
            ageing[str(name)] = st
    ageing[dec.plan] = {"generated": t1.isoformat(), "pass_started": doc["pass_started"],
                        "capacity": dict(dec.capacity),
                        "starve_passes": dict(sorted(dec.starve_passes.items())),
                        "red": dict(sorted(dec.red.items()))}
    doc["ageing"] = dict(sorted(ageing.items()))
    # RED BY NAME, ACROSS EVERY PLAN STILL RUNNING: what `check_leg_rotation` and
    # `check_desk_health` read. A dept pass writing GREEN must not paper over a RED core leg.
    try:
        res = residents if residents is not None else resident_liveness(now=t1)
    except Exception as exc:                          # measurement must never fail the pass
        res = {"error": f"{type(exc).__name__}: {exc}", "red": {}}
    doc["residents"] = res
    doc["liveness"] = liveness(ageing, res)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f"{out.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, out)
    except OSError as exc:
        doc["write_error"] = f"{type(exc).__name__}: {exc}"


def load_record(path: Path | None = None) -> dict[str, Any]:
    """The last published rotation, or an empty dict when there is none."""
    try:
        doc = json.loads((path or RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}
