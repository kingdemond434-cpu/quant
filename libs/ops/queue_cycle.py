"""THE QUEUE'S CLOCK. Everything below it was built, tested, and never once instantiated.

MEASURED 2026-09-10, by grepping the repo for the constructor:

    grep -rn 'TaskQueue(' --include=*.py . | grep -v tests   ->   no results

`task_queue` (durable journal, leases, bounded attempts, dedupe), `worker` (claim, capacity,
outcomes), `org` (roles, ownership, escalation to a human inbox), `wiring_campaign` (the first
producer) and `research.coverage_governor` (the second) are five modules, all tested, forming one
complete loop -- and no process on this desk has ever opened the file they all write to. That is
the exact defect `wiring_audit` was written to find, occurring in the modules written to fix it,
for the second time. The first time was fixed by wiring the audit; this fixes it by giving the
queue a clock.

WHAT ONE PASS DOES, and the order is the argument:

    1. PRODUCE. `wiring_campaign` queues the worst unreachable modules; `coverage_governor`
       queues a hunt for the mechanism clusters the book has no bet in. Both are idempotent by
       key, so an hourly clock does not build a backlog of duplicates.
    2. SWEEP. Every task that exhausted its attempts is escalated to its owner's supervisor, and
       a task owned by the TOP role reaches `org.HUMAN_INBOX` -- a kind no worker owns, so it
       cannot be claimed and stays on the census until a person acts.
    3. PUBLISH. One artifact carrying the queue census, the org census, and the human inbox, so
       "work died and nobody was told" is a state the dashboard can show rather than a thing that
       happens quietly. This is the half of alerting that does not need a channel.

IT RUNS NO TASKS, AND THAT IS DELIBERATE. A `wire` task is a choice of consumer and call site --
`libs.research.alpha_rl` is an 880-line Q-learner, and the question is not which line calls it but
at what cadence, on what budget, feeding what. Queueing that decision with its evidence attached
is the honest automation; a handler that edited money-path source unattended would be automation
of a different kind. `libs/ops/worker.py` exists for the kinds that DO have mechanical handlers,
and this leg deliberately registers none: a producer that also executes is a producer nobody can
audit.

WHY THE ARTIFACT IS THE DELIVERABLE RATHER THAN THE QUEUE FILE. The journal is append-only and
grows; the census is a fold of it and is small. A reader that had to fold the journal to answer
"is anything dead" would be re-implementing the queue, which is how two answers to one question
appear on a desk.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.org import HUMAN_INBOX, desk_org  # noqa: E402
from libs.ops.task_queue import TaskQueue  # noqa: E402

#: The desk's one queue. Relative to the repo root so a worktree, the box and CI each get their
#: own rather than sharing one across checkouts -- the journal records leases held by processes
#: that only exist on the machine that wrote them.
QUEUE_REL = "desks/mt5/data/task_queue.jsonl"

#: Where the fold is published for anything that reads state without folding a journal.
OUT_REL = "desks/mt5/reports/QUEUE.json"

#: Producers, in the order they run. Each is (name, callable(root, queue) -> dict). A producer
#: that raises is recorded by name and the pass continues: the sweep in step 2 is what tells a
#: person about failures, so it must not be skipped because a producer was broken.
PRODUCERS = ("wiring_campaign", "coverage_governor", "cost_evidence", "pit_lag_rejudge")


def queue_path(root: Path) -> Path:
    return root / Path(*QUEUE_REL.split("/"))


def _wiring_campaign(root: Path, queue: TaskQueue) -> dict[str, Any]:
    from libs.ops.wiring_campaign import run
    return run(root, queue)


def _coverage_governor(root: Path, queue: TaskQueue) -> dict[str, Any]:
    from libs.research.coverage_governor import census, enqueue
    return {**enqueue(queue, root), "coverage": census(root)}


def _cost_evidence(root: Path, queue: TaskQueue) -> dict[str, Any]:
    """Certificates whose own 3x cost gate demonstrably never reached the hours they can fire in.

    THE WORK IS RECERTIFICATION, NOT A VETO, and the kind says so. The honest response to "this
    cell was judged at the wrong cost" is to judge it again at the right one; refusing the cell
    here would be reducing the book by fiat on evidence no gauntlet has weighed.

    IT QUEUES NOTHING TODAY, AND THAT IS THE CORRECT ANSWER. `entry_timing` first reported 15
    uncovered cells, and every one of them was a producer artifact: `median_spread_pts` is
    written by three producers with three different meanings, and the cells named carried
    provenance `realized_fills` -- the desk's own executions, which outrank the H1 bar's stamped
    spread column. With the provenance gate in place the count is zero. This producer stays wired
    because the day a genuinely comparable symbol drifts, it queues that cell the same hour --
    and because a finding that turns out to be an artifact costs far more than no finding: acting
    on that one would have re-judged 15 certified cells on a bug the desk had already documented.

    OWNED BY VALIDATION, which owns `recertify` in `DESK_ROLES`. That routes it to the organ that
    re-runs gates, and gives it a supervisor: a recertification the desk cannot perform escalates
    to portfolio and then to a person, instead of the finding being published hourly forever.
    """
    from desks.mt5.research.entry_timing import UNCOVERED, census

    doc = census(root)
    o = desk_org()
    queued, skipped = [], []
    for w in doc["windows"]:
        if w["verdict"] != UNCOVERED:
            continue
        task = o.delegate(
            queue, "recertify", frm="ops",
            payload={"cell": w["cell"], "symbol": w["symbol"], "selector": w["selector"],
                     "charged_pts": w["charged_pts"], "charged_source": w["charged_source"],
                     "understatement": w["understatement"], "dearest_pts": w["dearest_pts"],
                     "why": w["why"]},
            priority=float(w["understatement"] or 0.0),
            dedupe_key=f"recertify:cost:{w['cell']}")
        (queued.append(w["cell"]) if task is not None
         else skipped.append(f"{w['cell']} (already queued for recertification)"))
    return {"queued": queued, "skipped": skipped,
            # PUBLISHED EVEN WHEN NOTHING IS QUEUED, because "no comparable symbol drifted" and
            # "almost nothing is comparable" are different states and only the second is a defect.
            "n_comparable_symbols": doc["n_symbols_comparable"],
            "n_symbols_no_provenance": doc["n_symbols_no_provenance"],
            "n_charged_zero": doc["n_symbols_charged_zero"],
            "why": ("a cell judged at the wrong cost is recertified at the right one; a ratio is "
                    "only taken where the registry records that both sides are the same "
                    "quantity, because a producer flip read as a cost error re-judges cells that "
                    "were fine")}


#: Where the certificates live (`certificate_truth.Paths`): the gauntlet's authority file and its
#: seal. Read only.
CANON_RELS = ("desks/mt5/reports/UNIVERSAL_SURVIVORS.json",
              "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json")
#: Above the cost producer's understatement scale and below the clock-breach front of the queue
#: (`clock_certificate.BREACH_PRIORITY`): a certificate judged on unpublished data is a wrong
#: verdict, but not a clock running with no certificate at all.
PIT_REJUDGE_PRIORITY = 500.0


def _canon_rows(root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for rel in CANON_RELS:
        try:
            doc = json.loads((root / Path(*rel.split("/"))).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        surv = doc.get("survivors") if isinstance(doc, dict) else None
        for name, row in (surv.items() if isinstance(surv, dict) else ()):
            if isinstance(row, dict):
                rows.setdefault(str(name), row)
    return rows


def _family_of(name: str, row: dict[str, Any]) -> str:
    raw = row.get("shadow_spec")
    spec: dict[str, Any] = raw if isinstance(raw, dict) else {}
    fam = spec.get("family") or row.get("family")
    if fam:
        return str(fam)
    cell = str(row.get("cell") or name)
    return next((p for p in cell.replace("#", ".").split(".") if p == "macro_conditional"), "")


def conditioning_series(row: dict[str, Any], default: str) -> tuple[str, str]:
    """(FRED id, how it was found) for a macro_conditional certificate: the `fred:<id>` its
    identity records, else the gauntlet's default -- `external_gauntlet.build_cell` calls
    `_macro_series(h1.index)` with no name, which picks the first `DAILY_MACRO_SERIES` entry."""
    def _walk(v: Any) -> str | None:
        if isinstance(v, str) and v.startswith("fred:") and len(v) > 5:
            return v[5:]
        if isinstance(v, dict):
            for x in v.values():
                got = _walk(x)
                if got:
                    return got
        if isinstance(v, (list, tuple)):
            for x in v:
                got = _walk(x)
                if got:
                    return got
        return None
    got = _walk(row)
    return (got, "recorded") if got else (default, "gauntlet_default")


def _pit_lag_rejudge(root: Path, queue: TaskQueue) -> dict[str, Any]:
    """Certificates judged under a publication lag the desk has since made LONGER.

    THE REMEDY IS THE GAUNTLET, NOT A VETO (the `cost_evidence` rule). Each revision in
    `data_os.LAG_REVISIONS` names a source, its series and the families that condition on them;
    every certificate of those families conditioned on a revised series and GATED BEFORE THE
    REVISION REACHED THIS BOX is listed in ONE `recertify` task, which the hourly
    `recertify_canon` leg claims and answers by re-running the ten gates on every standing
    certificate at today's declared lags. Nothing is demoted here; what the re-judge finds is the
    gauntlet's verdict, read by the promoter the way every recertification is.

    ONCE PER REVISION, EVER. The journal is the memory: a revision that already has a task in it
    (any state) is not queued again, and the earliest such task's `created_at` is when the
    revision reached this box -- a certificate gated after that was judged at the new lag and is
    not listed. A canon that cannot be read queues nothing and says so (UNMEASURED, L1.28a).
    """
    from libs.tiers import data_os

    rows = _canon_rows(root)
    if not rows:
        return {"queued": [], "skipped": [], "status": "UNMEASURED",
                "why": "no canon readable at " + ", ".join(CANON_RELS)}
    try:
        import importlib
        sweep = importlib.import_module("desks.mt5.research.orthogonal_sweep")
        default = str(sweep.DAILY_MACRO_SERIES[0])
    except Exception:                       # the box's import layout differs: use the default
        default = "DTWEXBGS"
    tasks = list(queue.tasks().values())
    queued: list[str] = []
    skipped: list[str] = []
    revisions: dict[str, Any] = {}
    for rev in data_os.LAG_REVISIONS:
        key = f"recertify:pit_lag:{rev['id']}"
        prior = [t for t in tasks if t.dedupe_key == key]
        adopted = min((str(t.created_at) for t in prior), default=None)
        hit: dict[str, list[str]] = {}
        for name, row in sorted(rows.items()):
            if _family_of(name, row) not in rev["families"]:
                continue
            sid, how = conditioning_series(row, default)
            if sid not in rev["series"]:
                continue
            gated = str(row.get("gated_at") or "")
            if adopted is not None and gated and gated >= adopted:
                continue                                   # judged at the revised lag already
            hit.setdefault(sid, []).append(f"{name} ({how})")
        n = sum(len(v) for v in hit.values())
        revisions[rev["id"]] = {"certificates": n, "by_series": {k: len(v) for k, v in hit.items()},
                                "adopted_at": adopted}
        if prior:
            skipped.append(f"{rev['id']}: already queued at {adopted} "
                           f"({prior[0].state}); {n} certificate(s) predate it")
            continue
        if not n:
            skipped.append(f"{rev['id']}: no certificate conditioned on a revised series")
            continue
        task = desk_org().delegate(
            queue, "recertify", frm="ops",
            payload={"cell": f"pit_lag:{rev['id']}", "revision": rev["id"],
                     "source": rev["source"], "was": rev["was"], "now": rev["now"],
                     "why": rev["why"], "certificates": hit, "n_certificates": n,
                     "remedy": ("re-run the ten gates on the standing canon at today's declared "
                                "lags (recertify_canon); no certificate is demoted by this task")},
            priority=PIT_REJUDGE_PRIORITY, dedupe_key=key)
        if task is None:
            skipped.append(f"{rev['id']}: the queue refused it (already live)")
        else:
            queued.append(rev["id"])
    return {"queued": queued, "skipped": skipped, "revisions": revisions,
            "why": ("a certificate conditioned on a print before it was published is re-judged "
                    "at the declared lag through the gauntlet; the verdict is the gauntlet's")}


_IMPL = {"wiring_campaign": _wiring_campaign, "coverage_governor": _coverage_governor,
         "cost_evidence": _cost_evidence, "pit_lag_rejudge": _pit_lag_rejudge}


def human_inbox(queue: TaskQueue) -> list[dict[str, Any]]:
    """Work that reached the top of the chart and stopped there. Non-empty means someone is owed
    a sentence. Ordered oldest first, because the oldest is the one that has been ignored longest.
    """
    out = [
        {"id": t.id, "created_at": t.created_at, "why": t.why,
         "about": t.payload.get("kind") or t.payload.get("about") or "",
         "payload": {k: v for k, v in t.payload.items() if not k.startswith("_")}}
        for t in queue.tasks().values()
        if t.kind == HUMAN_INBOX and t.state in ("READY", "LEASED")
    ]
    out.sort(key=lambda r: str(r["created_at"]))
    return out


def run(root: Path | None = None, *, queue: TaskQueue | None = None) -> dict[str, Any]:
    """One pass of the whole loop. Never raises on a producer failure; records it instead."""
    root = Path(root or _ROOT)
    q = queue if queue is not None else TaskQueue(queue_path(root))
    org = desk_org()

    produced: dict[str, Any] = {}
    failed: dict[str, str] = {}
    for name in PRODUCERS:
        try:
            produced[name] = _IMPL[name](root, q)
        except Exception as exc:
            failed[name] = f"{type(exc).__name__}: {exc}"

    swept = org.sweep_dead(q)
    inbox = human_inbox(q)
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "queue": q.census(),
        "org": org.census(q),
        "produced": produced,
        "producers_failed": failed,
        "escalated": swept["escalated"],
        "human_inbox": inbox,
        "needs_a_person": len(inbox),
        "why": ("producers queue, the sweep escalates what died, and the inbox is where work "
                "that reached the top of the chart waits -- a non-empty inbox is the desk asking "
                "for a decision, not a backlog"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="one pass of the desk task queue: produce, sweep, publish")
    ap.add_argument("--root", default=str(_ROOT))
    ap.add_argument("--json", action="store_true", help="print the whole artifact")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = run(root)
    out = root / Path(*OUT_REL.split("/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")

    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        c = doc["queue"]
        print(f"queue: {c['total']} tasks {c['by_state']} expired_leases={c['expired_leases']}")
        for name in PRODUCERS:
            got = doc["produced"].get(name)
            if got is None:
                print(f"  {name}: FAILED {doc['producers_failed'].get(name, '')}")
                continue
            print(f"  {name}: queued {len(got.get('queued') or [])}, "
                  f"skipped {len(got.get('skipped') or [])}")
        if doc["needs_a_person"]:
            print(f"NEEDS A PERSON: {doc['needs_a_person']} item(s) in the human inbox")
            for row in doc["human_inbox"][:5]:
                print(f"  {row['created_at']} {row['id']} {row['why'] or row['about']}")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
