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
from libs.ops.task_queue import INFORMATION, TaskQueue  # noqa: E402

#: The desk's one queue. Relative to the repo root so a worktree, the box and CI each get their
#: own rather than sharing one across checkouts -- the journal records leases held by processes
#: that only exist on the machine that wrote them.
QUEUE_REL = "desks/mt5/data/task_queue.jsonl"

#: Where the fold is published for anything that reads state without folding a journal.
OUT_REL = "desks/mt5/reports/QUEUE.json"

#: Producers, in the order they run. Each is (name, callable(root, queue) -> dict). A producer
#: that raises is recorded by name and the pass continues: the sweep in step 2 is what tells a
#: person about failures, so it must not be skipped because a producer was broken.
PRODUCERS = ("wiring_campaign", "coverage_governor", "cost_evidence", "lanes")


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


#: Data versions the `lanes` producer has already turned into information work.
VERSIONS_REL = "desks/mt5/data/queue_data_versions.json"
#: Information tasks the `lanes` producer may execute in one pass (its own bookkeeping only).
LANE_DRAIN_MAX = 500


def lineage_rows(root: Path) -> list[dict[str, Any]]:
    """Every lineage record that names an input, from BOTH lineage stores, in one shape
    (`artifact_id`, `input_artifact_ids`): the control plane's `lineage.sqlite` and the feature
    compiler's `feature_genome/lineage.jsonl` (feature <- dataset)."""
    rows: list[dict[str, Any]] = []
    db = root / "desks" / "mt5" / "data" / "lineage.sqlite"
    if db.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            try:
                for aid, inputs in conn.execute(
                        "SELECT artifact_id, input_artifact_ids FROM lineage_artifacts "
                        "WHERE input_artifact_ids IS NOT NULL AND input_artifact_ids != ''"):
                    rows.append({"artifact_id": str(aid), "input_artifact_ids": str(inputs)})
            finally:
                conn.close()
        except sqlite3.Error:
            pass
    fl = root / "desks" / "mt5" / "data" / "feature_genome" / "lineage.jsonl"
    try:
        lines = fl.read_text("utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("feature_id") and r.get("dataset_id"):
            rows.append({"artifact_id": f"feature:{r['feature_id']}",
                         "input_artifact_ids": [f"dataset:{r['dataset_id']}"]})
    return rows


def data_versions(root: Path) -> dict[str, dict[str, Any]]:
    """dataset artifact id -> {version, host, release_at} for every acquired series."""
    reg_p = root / "desks" / "mt5" / "data" / "acquired" / "registry.json"
    try:
        reg = json.loads(reg_p.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name, meta in (reg.get("series") or {}).items():
        if not isinstance(meta, dict):
            continue
        ver = "|".join(str(meta.get(k) or "") for k in ("rows", "last", "sha256", "revisions"))
        out[f"dataset:{name}"] = {
            "version": ver, "host": str(meta.get("host") or ""),
            # THE RELEASE TIME: when the version became available to the desk -- the series'
            # own availability stamp when it carries one, else the time it was acquired.
            "release_at": str(meta.get("available_at") or meta.get("acquired_at") or "")}
    return out


def _lanes(root: Path, queue: TaskQueue) -> dict[str, Any]:
    """DATA-50: the two linked lanes, release timing, per-host rate limits, targeted invalidation.

    1. LINKS: an `acquire_class` mission's completion queues `screen_class` (strategy).
    2. RATE LIMITS: one token bucket per catalogue host at the roster's own minimum gap.
    3. VERSIONS: every new data version is an INFORMATION task `ingest_version`, not claimable
       before its release time, on its host's bucket.
    4. DRAIN, NO IDLE GAP: claim the information lane until nothing is eligible; each
       `ingest_version` invalidates ONLY the features and cells whose lineage names that dataset
       (STRATEGY tasks), then completes. Everything else is counted as untouched.
    """
    queue.link("acquire_class", "screen_class")
    roster_p = root / "desks" / "mt5" / "data" / "catalog_routes" / "roster.json"
    limited = 0
    try:
        roster = json.loads(roster_p.read_text("utf-8"))
        gap = float((roster.get("defaults") or {}).get("min_gap_s") or 1.0)
        have = queue.rate_limits()
        for p in roster.get("portals") or []:
            host = str(p.get("base") or "").split("//", 1)[-1].split("/", 1)[0].lower()
            if host and host not in have:
                queue.set_rate_limit(host, per_s=1.0 / max(gap, 0.01), burst=1.0)
                limited += 1
    except (OSError, ValueError, AttributeError):
        pass
    vpath = root / Path(*VERSIONS_REL.split("/"))
    try:
        seen = json.loads(vpath.read_text("utf-8"))
    except (OSError, ValueError):
        seen = {}
    seen = seen if isinstance(seen, dict) else {}
    versions = data_versions(root)
    submitted = []
    for aid, v in sorted(versions.items()):
        if seen.get(aid) == v["version"]:
            continue
        # NO HOST ON THIS TASK: ingesting a version reads the local registry and lineage and
        # sends nothing to the publisher, so it must not spend the publisher's token. The
        # buckets above govern tasks that FETCH (a mission's acquisition, a catalogue page).
        got = queue.submit("ingest_version", lane=INFORMATION,
                           payload={"artifact_id": aid, "version": v["version"],
                                    "publisher_host": v["host"]},
                           dedupe_key=f"ingest_version|{aid}@{v['version']}",
                           not_before=v["release_at"] or None)
        if got is not None:
            submitted.append(aid)
        seen[aid] = v["version"]
    vpath.parent.mkdir(parents=True, exist_ok=True)
    vpath.write_text(json.dumps(seen, indent=1, sort_keys=True), "utf-8")
    rows = lineage_rows(root)
    invalidated: list[dict[str, Any]] = []
    drained = 0
    while drained < LANE_DRAIN_MAX:
        task = queue.claim(QUEUE_WORKER, kinds=("ingest_version",), lane=INFORMATION)
        if task is None:
            break
        drained += 1
        res = queue.invalidate(str(task.payload.get("artifact_id")),
                               str(task.payload.get("version")), lineage_rows=rows,
                               parent=task.id)
        queue.complete(task.id, QUEUE_WORKER, why=f"{len(res['affected'])} dependent(s)",
                       produced={"artifact_id": res["artifact_id"], "version": res["version"]})
        invalidated.append({k: res[k] for k in ("artifact_id", "affected", "untouched")})
    return {"queued": submitted, "skipped": [],
            "rate_limits_added": limited, "lineage_rows": len(rows),
            "drained_information": drained,
            "invalidations": invalidated[:50],
            "affected_total": sum(len(x["affected"]) for x in invalidated),
            "untouched_total": sum(int(x["untouched"]) for x in invalidated),
            "next_eligible_at": queue.next_eligible_at(),
            "why": ("a new data version re-queues only the features and cells whose lineage "
                    "names it; information work drains before strategy work and a throttled "
                    "host is skipped, never waited on")}


#: The worker name the lanes producer claims under (the hourly cycle's own).
QUEUE_WORKER = "hourly_cycle"


_IMPL = {"wiring_campaign": _wiring_campaign, "coverage_governor": _coverage_governor,
         "cost_evidence": _cost_evidence, "lanes": _lanes}


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
