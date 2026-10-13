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
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.org import DESK_ROLES, ESCALATION_KIND, HUMAN_INBOX, desk_org  # noqa: E402
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
#: The information kind one new data version becomes; the `lanes` producer drains it itself.
INGEST_KIND = "ingest_version"
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
        got = queue.submit(INGEST_KIND, lane=INFORMATION,
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
        task = queue.claim(QUEUE_WORKER, kinds=LANES_CLAIMS, lane=INFORMATION)
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


# ---------------------------------------------------------------------- strategy-lane consumers
# THE TWO STRATEGY KINDS THE LANES QUEUE, AND THE WORK EACH ONE NAMES (auditor HOLD, PR #289).
# `_lanes` queues `invalidate` (one per lineage dependent of a new data version) and the
# `acquire_class` -> `screen_class` link queues a class screen when a mission is met. Until these
# consumers existed nothing claimed either kind, so every row sat READY forever: a queue nothing
# drains is a list of regrets. The hourly leg `queue_consumers` calls `consume()` beside the
# `recertify` claim; `scripts/check_no_queues.py` fails when READY rows of any kind age past
# its bound, so a consumer that stops is a red fence, not a quiet backlog.

#: acquire_datasets.MIN_ROWS, inlined: importing the desk module from libs/ drags the
#: mypy-excluded desks/ tree into the type gate. A test pins the two equal.
SCREEN_MIN_ROWS = 200

INVALIDATE_KIND = "invalidate"
SCREEN_KIND = "screen_class"
CONSUMED_KINDS = (INVALIDATE_KIND, SCREEN_KIND)

#: THE CLAIM LISTS, in one place, and every consumer claims FROM them -- `consume` above claims
#: CONSUMED_KINDS, `_lanes` claims LANES_CLAIMS, the hourly cycle's `_recertify_canon_claimed`
#: claims RECERTIFY_CLAIMS -- so `CLAIMED_KINDS` is derived from what is actually claimed, never
#: typed a second time. `scripts/check_no_queues.py` reads it: a READY row of a claimed kind past
#: its bound is a BREACH (its consumer stopped); a READY row of any other kind (`wire`, the human
#: inbox, `acquire_class`) has no automated consumer by design and is reported as unconsumed.
#: `tests/ops/test_queue_cycle_lanes.py` fails if a claim call names a kind outside this set.
RECERTIFY_CLAIMS = ("recertify",)
LANES_CLAIMS = (INGEST_KIND,)
CLAIMED_KINDS = frozenset((*RECERTIFY_CLAIMS, *LANES_CLAIMS, *CONSUMED_KINDS))

#: The leg that drains each claimed kind -- the `owner_leg` the no-queues fence names when that
#: kind backs up (it named `queue_consumers` for every kind, including ones it never claims).
KIND_OWNER_LEG: dict[str, str] = {
    **dict.fromkeys(RECERTIFY_CLAIMS, "recertify_canon"),
    **dict.fromkeys(LANES_CLAIMS, "queue_cycle"),
    **dict.fromkeys(CONSUMED_KINDS, "queue_consumers"),
}

#: KINDS THAT INTENTIONALLY HAVE NO AUTOMATED CONSUMER, each with its reason (auditor MUST on
#: #289). A READY row of one of these is reported in `unconsumed_kinds` and never fails. A READY
#: row of ANY OTHER unclaimed kind past the bound is PARKED and fails the no-queues fence: an
#: unknown kind is a producer whose consumer was never written, which is exactly a queue.
#: `tests/ops/test_queue_cycle_lanes.py` fails if a `submit()` names a kind outside
#: CLAIMED_KINDS | NO_CONSUMER_KINDS.
NO_CONSUMER_KINDS: dict[str, str] = {
    "wire": ("an ops work order from wiring_campaign: wiring a module is a code change a session "
             "makes, not a task a worker can perform"),
    "retire_module": ("an ops work order from wiring_campaign to delete dead code: a code change "
                      "a session makes, not a task a worker can perform"),
    "generate": ("a coverage_governor hunt brief for a dark axis: read by the research seats and "
                 "sessions as a brief, never claimed by a worker"),
    "acquire_class": ("an information-lane mission completed by discovery_loop when a matching "
                      "source is acquired: it waits on the world, not on a worker"),
    HUMAN_INBOX: "work that reached the top of the chart: a person answers it",
    **{f"{ESCALATION_KIND}:{r.escalates_to}": (
        f"an escalation to the {r.escalates_to!r} role, which no worker runs as: a person reads "
        f"it on QUEUE.json") for r in DESK_ROLES if r.escalates_to},
}
#: Tasks one pass may consume. Each is a few file reads; the bound only stops a pathological
#: journal from holding the hourly cycle, and the leftover is the next pass's first work.
CONSUME_MAX = 500
#: Every invalidation this consumer performed, append-only, so "what was dropped and why" is a
#: record rather than an absence in genomes.json.
INVALIDATIONS_REL = "desks/mt5/data/feature_genome/invalidations.jsonl"
#: Per-class screen outcomes (latest per class).
CLASS_SCREEN_REL = "desks/mt5/reports/CLASS_SCREEN.json"
#: A class whose series are acquired but not yet research-eligible is re-screened a day later,
#: at most this many times; after that the screen completes as NOT_ELIGIBLE with the reasons.
SCREEN_REARM_MAX = 7
SCREEN_REARM_H = 24


def _rel(root: Path, rel: str) -> Path:
    return root / Path(*rel.split("/"))


def _atomic_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    os.replace(tmp, path)


def _end_lease_in_lineage_db(root: Path, artifact_id: str, at: str) -> bool:
    """End the control-plane lease of `artifact_id`: its latest lineage row's `valid_until` is
    set to now, so `lease.valid` / `check_no_staleness` read it STALE until its producer writes
    a new run. False when the store does not hold the artifact."""
    db = root / "desks" / "mt5" / "data" / "lineage.sqlite"
    if not db.exists():
        return False
    import sqlite3
    try:
        conn = sqlite3.connect(str(db), timeout=10)
        try:
            row = conn.execute(
                "SELECT rowid FROM lineage_artifacts WHERE artifact_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1", (artifact_id,)).fetchone()
            if row is None:
                return False
            conn.execute("UPDATE lineage_artifacts SET valid_until = ? WHERE rowid = ?",
                         (at, row[0]))
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return True


def invalidate_artifact(root: Path, artifact_id: str, *, because: str = "", version: str = "",
                        now: datetime | None = None) -> dict[str, Any]:
    """Invalidate ONE artifact a new data version made stale. Returns what was invalidated where.

    * `feature:<id>` -- the feature genome's record is dropped from `feature_genome/genomes.json`
      (the compiler re-types it from the new version on its next pass) and, when the feature is a
      minted representation, its manifest row and stored file are dropped so the forge re-mints
      it from the new inputs (`propose` skips ids already in the manifest).
    * anything else -- its lease in the control-plane lineage store ends now.

    An artifact no store on this host holds is NOT_HELD: there was nothing stale to drop.
    """
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    aid = str(artifact_id)
    where: list[str] = []
    if aid.startswith("feature:"):
        fid = aid.split(":", 1)[1]
        store = root / "desks" / "mt5" / "data" / "feature_genome"
        gp = store / "genomes.json"
        try:
            gdoc = json.loads(gp.read_text("utf-8"))
        except (OSError, ValueError):
            gdoc = None
        genomes = gdoc.get("genomes") if isinstance(gdoc, dict) else None
        if isinstance(genomes, dict) and fid in genomes:
            genomes.pop(fid)
            gdoc["n"] = len(genomes)
            _atomic_json(gp, gdoc)
            where.append("feature_genome")
        rstore = root / "desks" / "mt5" / "data" / "representations"
        mp = rstore / "manifest.json"
        try:
            mdoc = json.loads(mp.read_text("utf-8"))
        except (OSError, ValueError):
            mdoc = None
        rows = mdoc.get("representations") if isinstance(mdoc, dict) else None
        if isinstance(rows, list):
            hit = [r for r in rows if isinstance(r, dict) and str(r.get("id")) == fid]
            if hit:
                mdoc["representations"] = [r for r in rows if r not in hit]
                mdoc["n"] = len(mdoc["representations"])
                _atomic_json(mp, mdoc)
                for r in hit:
                    name = str(r.get("file") or "")
                    if name and "/" not in name and "\\" not in name and name not in (".", ".."):
                        (rstore / name).unlink(missing_ok=True)
                where.append("representation_store")
    if _end_lease_in_lineage_db(root, aid, at):
        where.append("lineage_lease")
    rec = {"at": at, "artifact_id": aid, "because": str(because), "version": str(version),
           "invalidated_in": where, "outcome": "INVALIDATED" if where else "NOT_HELD"}
    if where:
        lp = _rel(root, INVALIDATIONS_REL)
        lp.parent.mkdir(parents=True, exist_ok=True)
        with lp.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def _norm_host(h: str) -> str:
    s = str(h or "").strip().lower()
    s = s.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    return s[4:] if s.startswith("www.") else s


def class_terms(raw: Any) -> tuple[tuple[str, ...], ...]:
    """A class's terms as LITERAL word sequences, never a compiled pattern (auditor SHOULD on
    #289): the payload is queue data that a fetched page can shape, and a regex compiled from it
    is a catastrophic-backtracking surface. Classes write their terms as `\\bnight\\W+lights\\b`
    (`unknowns._terms`) and may join alternatives with `|`; each alternative becomes the tuple
    of its alphanumeric words, and every other metacharacter is dropped, never interpreted."""
    parts = [str(x) for x in raw] if isinstance(raw, (list, tuple)) else str(raw or "").split("|")
    out: list[tuple[str, ...]] = []
    for p in parts:
        flat = p.replace("\\W+", " ").replace("\\W", " ").replace("\\b", " ").lower()
        words = tuple(_WORDS.findall(flat))
        if words and words not in out:
            out.append(words)
    return tuple(out)


_WORDS = re.compile(r"[a-z0-9]+")


def _names_term(name: str, terms: tuple[tuple[str, ...], ...]) -> bool:
    """True when the series name's words contain one term's words contiguously, in order."""
    words = _WORDS.findall(str(name).lower())
    for t in terms:
        n = len(t)
        if any(tuple(words[i:i + n]) == t for i in range(len(words) - n + 1)):
            return True
    return False


def screen_class(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Screen a met class through the acquired-data screen. PURE over the registry.

    The class's series are the registry series acquired from the source that met it (`produced
    .source`) plus any whose name matches the class's own `terms`. Each is put through the gate
    `acquire_datasets.acquired_series` applies before a series enters the `ext_<name>`
    vocabulary -- PIT authority and at least `MIN_ROWS` rows -- because that vocabulary is what
    the anomaly miner scans and `family_discovered` executes every hour. A series that passes is
    SCREENED into that search; one that does not is named with its reason. This writes no trial
    charge: the scans that evaluate cells charge their own.
    """
    reg_p = root / "desks" / "mt5" / "data" / "acquired" / "registry.json"
    try:
        reg = json.loads(reg_p.read_text("utf-8"))
    except (OSError, ValueError):
        return {"outcome": "UNMEASURED", "why": f"acquired registry unreadable at {reg_p.name}",
                "series": []}
    raw = payload.get("produced")
    produced: dict[str, Any] = raw if isinstance(raw, dict) else {}
    host = _norm_host(str(produced.get("source") or ""))
    terms = class_terms(payload.get("terms"))
    rows: list[dict[str, Any]] = []
    for name, meta in sorted((reg.get("series") or {}).items()):
        if not isinstance(meta, dict):
            continue
        by_host = bool(host) and _norm_host(str(meta.get("host") or "")) == host
        by_terms = _names_term(str(name), terms)
        if not (by_host or by_terms):
            continue
        why = []
        if meta.get("pit_authority") is not True:
            why.append("no PIT authority")
        try:
            n = int(meta.get("rows") or 0)
        except (TypeError, ValueError):
            n = 0
        if n < SCREEN_MIN_ROWS:
            why.append(f"{n} rows < {SCREEN_MIN_ROWS}")
        rows.append({"series": str(name), "matched_by": "host" if by_host else "terms",
                     "eligible": not why, "why": "; ".join(why)})
    eligible = [r["series"] for r in rows if r["eligible"]]
    if eligible:
        outcome = "SCREENED"
    elif rows:
        outcome = "NOT_YET_ELIGIBLE"
    else:
        outcome = "UNRESOLVED"
    return {"outcome": outcome, "class": payload.get("key"), "source": host or None,
            "series": rows, "vocabulary": [f"ext_{s}" for s in eligible],
            "screens": ["anomaly_miner", "family_discovered"] if eligible else []}


def _record_class_screen(root: Path, key: str, res: dict[str, Any], at: str) -> None:
    p = _rel(root, CLASS_SCREEN_REL)
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
    classes = doc.get("classes") if isinstance(doc, dict) else None
    classes = classes if isinstance(classes, dict) else {}
    classes[str(key)] = {**res, "at": at}
    _atomic_json(p, {"at": at, "n": len(classes), "classes": classes,
                     "rule": ("a met class's series pass the acquired-data vocabulary gate (PIT "
                              "authority, MIN_ROWS) into the ext_ search the anomaly miner and "
                              "family_discovered run hourly; no trial charge is written here")})


#: First retry delay after a failed consume; each further attempt waits RETRY_BACKOFF_X longer.
RETRY_BACKOFF_H = 1.0
RETRY_BACKOFF_X = 4.0


def retry_backoff(attempts: int) -> timedelta:
    """1 h after the first failure, 4 h after the second: a transient fault (a registry being
    rewritten, a lock held) gets two later chances before the task goes DEAD and escalates,
    instead of all three attempts being spent inside one drain pass."""
    return timedelta(hours=RETRY_BACKOFF_H * RETRY_BACKOFF_X ** max(0, int(attempts) - 1))


def consume(root: Path | None = None, *, queue: TaskQueue | None = None,
            max_tasks: int = CONSUME_MAX, now: datetime | None = None) -> dict[str, Any]:
    """Claim and do every ready `invalidate` and `screen_class` task (up to `max_tasks`).

    Each task is completed with its outcome or failed with its reason; a failure returns it to
    READY until its attempts run out, then the org sweep escalates it.
    """
    root = Path(root or _ROOT)
    q = queue if queue is not None else TaskQueue(queue_path(root))
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    done: dict[str, int] = dict.fromkeys(CONSUMED_KINDS, 0)
    failed: list[dict[str, str]] = []
    outcomes: dict[str, int] = {}
    rearmed = 0
    n = 0
    while n < max_tasks:
        task = q.claim(QUEUE_WORKER, kinds=CONSUMED_KINDS, now=now)
        if task is None:
            break
        n += 1
        p = dict(task.payload or {})
        try:
            if task.kind == INVALIDATE_KIND:
                if not p.get("artifact_id"):
                    raise ValueError("invalidate task names no artifact_id")
                res = invalidate_artifact(root, str(p["artifact_id"]),
                                          because=str(p.get("because") or ""),
                                          version=str(p.get("version") or ""), now=now)
            else:
                res = screen_class(root, p)
                if res["outcome"] == "UNMEASURED":
                    raise RuntimeError(res["why"])
                _record_class_screen(root, str(p.get("key") or task.id), res, at)
                rearm = int(p.get("rearm") or 0)
                if res["outcome"] == "NOT_YET_ELIGIBLE" and rearm < SCREEN_REARM_MAX:
                    again = q.submit(
                        SCREEN_KIND, lane=task.lane or "strategy",
                        payload={**p, "rearm": rearm + 1},
                        priority=float(task.priority),
                        dedupe_key=f"{SCREEN_KIND}|{p.get('key')}|rearm{rearm + 1}",
                        not_before=(now or datetime.now(tz=UTC))
                        + timedelta(hours=SCREEN_REARM_H), parent=task.id)
                    rearmed += int(again is not None)
            outcome = str(res.get("outcome"))
            q.complete(task.id, QUEUE_WORKER, why=outcome,
                       produced={k: res.get(k) for k in ("outcome", "invalidated_in",
                                                         "vocabulary") if k in res})
            done[task.kind] = done.get(task.kind, 0) + 1
            outcomes[f"{task.kind}:{outcome}"] = outcomes.get(f"{task.kind}:{outcome}", 0) + 1
        except Exception as exc:  # one bad task never stops the drain
            why = f"{type(exc).__name__}: {exc}"[:200]
            q.fail(task.id, QUEUE_WORKER, why=why,
                   retry_after=(now or datetime.now(tz=UTC)) + retry_backoff(task.attempts))
            failed.append({"id": task.id, "kind": task.kind, "why": why})
    left = sum(1 for t in q.tasks().values()
               if t.kind in CONSUMED_KINDS and t.state == "READY" and t.is_ready(
                   now or datetime.now(tz=UTC)))
    return {"at": at, "claimed": n, "completed": done, "outcomes": outcomes,
            "failed": failed, "rearmed": rearmed, "ready_left": left,
            "status": "STOOD_DOWN" if n == 0 else "CONSUMED"}


_IMPL = {"wiring_campaign": _wiring_campaign, "coverage_governor": _coverage_governor,
         "cost_evidence": _cost_evidence, "lanes": _lanes}


#: Hours past release after which a READY row is reported as waiting (the no-queues bound).
READY_BOUND_H = 3.0


def ready_ages(tasks: Any, now: datetime) -> dict[str, list[float | None]]:
    """kind -> the age in hours, past its RELEASE time, of every claimable row (READY, or LEASED
    to a holder that died). None where the row carries no readable timestamp."""
    out: dict[str, list[float | None]] = {}
    for t in tasks:
        if not t.is_ready(now):
            continue
        since = None
        for raw in (t.not_before, t.created_at):
            if raw:
                try:
                    since = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                except ValueError:
                    since = None
                if since is not None:
                    since = since if since.tzinfo else since.replace(tzinfo=UTC)
                    break
        out.setdefault(str(t.kind), []).append(
            None if since is None else (now - since).total_seconds() / 3600.0)
    return out


def unconsumed_kinds(by_kind: dict[str, list[float | None]],
                     bound_h: float = READY_BOUND_H) -> list[dict[str, Any]]:
    """The READY rows of the DECLARED no-consumer kinds (NO_CONSUMER_KINDS), with counts, ages
    and the declared reason: visible on QUEUE.json and the no-queues fence, never a breach.
    An unclaimed kind that is NOT declared is not listed here; see `undeclared_kinds`."""
    rows = []
    for kind, ages in sorted(by_kind.items()):
        if kind in CLAIMED_KINDS or kind not in NO_CONSUMER_KINDS:
            continue
        known = [a for a in ages if a is not None]
        rows.append({"kind": kind, "ready": len(ages),
                     "past_bound": sum(1 for a in known if a > bound_h),
                     "oldest_age_h": round(max(known), 3) if known else None,
                     "undated": len(ages) - len(known), "bound_h": bound_h,
                     "why_no_consumer": NO_CONSUMER_KINDS[kind]})
    return rows


def undeclared_kinds(by_kind: dict[str, list[float | None]]) -> list[str]:
    """READY kinds that nothing claims AND nobody declared consumer-less: each is a queue."""
    return sorted(k for k in by_kind if k not in CLAIMED_KINDS and k not in NO_CONSUMER_KINDS)


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
    at = datetime.now(tz=UTC)
    return {
        "at": datetime.now(tz=UTC).isoformat(),
        "queue": q.census(),
        "org": org.census(q),
        "produced": produced,
        "producers_failed": failed,
        "escalated": swept["escalated"],
        "human_inbox": inbox,
        "needs_a_person": len(inbox),
        "claimed_kinds": sorted(CLAIMED_KINDS),
        "unconsumed_kinds": unconsumed_kinds(ready_ages(q.tasks().values(), at)),
        "undeclared_kinds": undeclared_kinds(ready_ages(q.tasks().values(), at)),
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
