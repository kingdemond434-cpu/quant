"""Turn "135 modules are unreachable" into owned work that cannot be forgotten.

THE STEP BETWEEN A CENSUS AND A FIX. `wiring_audit` measures; this makes each finding a durable,
OWNED task with a supervisor above it. Without it the census is a number that gets larger, which
is the shape every one of this desk's long-running failures took: correct evidence, produced on a
clock, that nothing acted on.

IT IS ALSO WHAT MAKES THE QUEUE REAL. `task_queue`, `worker` and `org` were each built and then
sat unwired -- exactly the defect the audit exists to find, in the modules written to fix it. This
is their first producer, so the whole stack now does work instead of describing it.

THE CAMPAIGN IS BOUNDED ON PURPOSE. Queueing 135 tasks at once produces a backlog nobody can read
and a census that never visibly moves; `BATCH` per pass keeps the queue short enough that the
oldest ready task is a real answer to "what is being worked on". The findings are already ordered
worst-first, so a batch is the top of that order.

WHAT IT WILL NOT DO. It does not edit code. A wiring fix is a choice of CONSUMER and CALL SITE,
and for most of these that is a design decision -- `libs.research.alpha_rl` is an 880-line
Q-learner over the alpha-construction MDP, and the question is not which line calls it but at what
cadence, on what budget, feeding what. Queueing the decision with its evidence attached is the
honest automation; generating a call site would be inventing an answer and shipping it to a money
path. RETIRE findings are not queued as wiring at all: no caller and no proof means wiring would
put unverified code on a clock, which is worse than deleting it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from libs.ops.org import Org, desk_org
from libs.ops.task_queue import TaskQueue
from libs.ops.wiring_audit import Finding, findings

#: Task kinds, both owned by the ops role in `org.DESK_ROLES`. The two verdicts are queued under
#: separate kinds so a batch of one never silently becomes a batch of the other.
#:
#: `retire_module` AND NOT `retire`, because `retire` is already owned by the PORTFOLIO role and
#: means retiring a live sleeve -- pulling capital from a decayed strategy. Queueing module
#: cleanup under that name would have routed "delete some dead code" to the organ that
#: de-allocates capital, and the roster would have accepted it: one kind, one owner, two entirely
#: different meanings. The kind namespace is shared, so a collision is silent by construction.
WIRE_KIND = "wire"
RETIRE_KIND = "retire_module"

#: Findings queued per pass. Small deliberately -- see the header.
BATCH = 8

#: A module in a money-path tree carries this so the applier can gate it on the full desk suite
#: rather than on the module's own tests.
MONEY_KEY = "money_path"


def priority_of(f: Finding) -> float:
    """Value already paid for, per unit of work to claim it.

    Lines are a proxy for investment: a 900-line module with tests represents someone's week, and
    reaching it costs the same as reaching a 40-line one. `has_tests` doubles it because a tested
    module can be wired and verified, while an untested one cannot be trusted once it is.
    ONE-LINK-SHORT rows rank above plain orphans at equal size: the alarm for those is already
    silenced, so nothing else will report them.
    """
    base = float(f.lines) / 100.0
    if f.has_tests:
        base *= 2.0
    if f.kind == "sole_importer_unreachable":
        base *= 1.5
    return round(base, 3)


def enqueue(queue: TaskQueue, found: list[Finding], *, org: Org | None = None,
            batch: int = BATCH) -> dict[str, Any]:
    """Queue the worst `batch` findings as owned tasks. Idempotent by module name.

    DEDUPE IS THE MODULE, so a module already queued or being worked is not queued again while
    the audit keeps reporting it every hour. It becomes queueable again only once the earlier task
    is DONE or DEAD -- and a DEAD one is escalated by `org.sweep_dead`, so a module that defeats
    the campaign reaches a person rather than quietly re-queueing forever.
    """
    o = org or desk_org()
    queued: list[str] = []
    skipped: list[str] = []
    for f in found:
        if len(queued) >= batch:
            break
        kind = WIRE_KIND if f.verdict == "WIRE" else RETIRE_KIND
        if o.owner_of(kind) is None:
            skipped.append(f"{f.module} (no role owns {kind!r})")
            continue
        task = o.delegate(
            queue, kind, frm="ops",
            payload={"module": f.module, "lines": f.lines, "reason": f.why,
                     "public": list(f.public), "finding_kind": f.kind,
                     "detail": f.detail, MONEY_KEY: f.money_path},
            priority=priority_of(f), dedupe_key=f"{kind}:{f.module}")
        (queued.append(f.module) if task is not None
         else skipped.append(f"{f.module} (already live)"))
    return {"queued": queued, "skipped": skipped, "batch": batch,
            "why": ("bounded per pass so the oldest ready task is a real answer to what is being "
                    "worked on, rather than the head of a backlog nobody reads")}


def progress(queue: TaskQueue, root: Path) -> dict[str, Any]:
    """What the campaign has actually moved, which is not the same as what it has queued."""
    tasks = list(queue.tasks().values())
    mine = [t for t in tasks if t.kind in (WIRE_KIND, RETIRE_KIND)]
    done = [t for t in mine if t.state == "DONE"]
    dead = [t for t in mine if t.state == "DEAD"]
    open_ = [t for t in mine if t.state in ("READY", "LEASED")]
    remaining = len(findings(root))
    return {
        "remaining_unreachable": remaining,
        "queued_open": len(open_),
        "completed": len(done),
        "dead": len(dead),
        "money_path_open": sum(1 for t in open_ if t.payload.get(MONEY_KEY)),
        "oldest_open": min((t.created_at for t in open_), default=""),
        "why": ("`remaining_unreachable` is the only number that means anything -- completed "
                "tasks that did not reduce it are wiring that did not land"),
    }


def run(root: Path, queue: TaskQueue, *, batch: int = BATCH) -> dict[str, Any]:
    """One campaign pass: audit, queue the worst, escalate anything that died.

    THE ESCALATION IS NOT OPTIONAL and runs even when nothing new is queued. A wiring task that
    exhausts its attempts is a module the campaign cannot fix by itself, which is precisely the
    thing a person needs to be told about -- and the failure mode of every previous version of
    this idea on this desk was that nobody was.
    """
    org = desk_org()
    found = findings(root)
    got = enqueue(queue, found, org=org, batch=batch)
    swept = org.sweep_dead(queue)
    return {"audit_total": len(found), **got,
            "escalated": swept["escalated"], "not_escalated": swept["not_escalated"],
            "progress": progress(queue, root)}
