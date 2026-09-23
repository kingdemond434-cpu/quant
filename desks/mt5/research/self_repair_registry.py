#!/usr/bin/env python3
"""FIX THE CLASS, ON A CLOCK, OR IT IS NOT FIXED (LAWS 7, principal's order 2026-09-23).

    python desks/mt5/research/self_repair_registry.py --once --budget-s 120
    python scripts/check_self_repair.py

THE TWIN OF THE BIRTH FENCE. `scripts/check_birth_obligations.py` stops a NEW thing arriving
without its obligations. This stops a KNOWN defect returning. Between them there is no room for a
builder to be the mechanism: one guards arrivals, the other guards recurrences, and both run on
the desk's own clock.

WHAT A CLASS MUST CARRY, AND WHY EACH PART. A defect class is closed only when four things exist:

    detector   how the desk finds EVERY instance, derived from the tree -- never a hand list,
               because a hand list is exactly the artefact that goes stale between sessions
    repair     the actuator that closes an instance, run through the existing control-plane
               reconciler -- never a new fixer, because a fixer per instance is the defect
    fence      what FAILS if the class returns, so the repair cannot quietly stop working
    evidence   when the detector last ran and what it found, read from the detector's own
               artifact -- a class whose detector has not run inside its window is UNMEASURED,
               which is a verdict and never a pass (L1.28a)

THE ONE NUMBER FOR A HUMAN. Every class lands in exactly one bucket: AUTOMATED (detected and
repaired without hands), DETECTED (found automatically, still needs a builder to close), or
MANUAL (found by a person, no detector exists). MANUAL is the count that matters and it ratchets
DOWN: `scripts/check_self_repair.py` fails when it rises, when a class has no detector, no repair
AND no owner, or when a detector has gone silent past its own window.

THIS FILE REFERENCES, IT DOES NOT REIMPLEMENT. Every detector, repair and fence named below was
built elsewhere -- most of them on 2026-09-23, each paying for a defect that had already cost this
desk real evidence. The registry's whole job is to PROVE the four parts exist for each class, to
name the classes that are short a part, and to put the lot on one clock.

Clock: `hourly_cycle:self_repair` (department `meta`, layer `meta`).
Artifact: `desks/mt5/reports/SELF_REPAIR.json` + `docs/research/SELF_REPAIR.md` (committed).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]

UNMEASURED = "UNMEASURED"
CADENCE_S = 3600

#: The buckets. Exactly one per class, and none of them is blank.
BUCKETS: tuple[str, ...] = ("AUTOMATED", "DETECTED", "MANUAL", UNMEASURED)


@dataclass(frozen=True)
class DefectClass:
    """One defect class and the four parts that close it."""

    key: str
    title: str
    cost: str                         # what this class already cost the desk, measured
    detector: str                     # repo-relative path that enumerates every instance
    repair: str                       # a control-plane actuator, or "" when hands are needed
    fence: str                        # repo-relative check that fails if the class returns
    artifact: str                     # the detector's own artifact, read for evidence
    window_s: int = 24 * CADENCE_S    # how long the detector may be silent. A DAY,
    #: not an hour: several detectors here are law-gate fences, not hourly legs, and a
    #: window shorter than a detector's own clock reports the clock as the defect.
    counts: tuple[str, ...] = ()      # top-level scalar keys of the artifact worth publishing
    owner: str = "department:meta"
    notes: str = ""
    instances: dict[str, Any] = field(default_factory=dict)


#: THE CLASSES, seeded from what the desk measured in the last day. Each one is a defect that
#: RECURRED or cost evidence, with the organ that now finds it and the actuator that closes it.
CLASSES: tuple[DefectClass, ...] = (
    DefectClass(
        "producer_without_clock",
        "a producer exists and nothing ever runs it",
        "126 organs read NEVER on the build box and 8 on the trading box, 2026-09-23",
        "scripts/check_component_registry.py",
        "run_once (libs/ops/control_plane/reconciler._actuator_for)",
        "scripts/check_birth_obligations.py",
        "desks/mt5/reports/COMPONENT_REGISTRY.json",
        counts=("unclocked", "components", "n"),
        notes="the registry derives every executable from the tree; run_once relights one leg "
              "and proves it by the artifact moving, never by rc=0"),
    DefectClass(
        "artifact_nobody_reads",
        "a producer writes an artifact no consumer is declared for",
        "the wiring audit's standing finding; an unread artifact is compute spent on nothing",
        "scripts/check_dead_architecture.py",
        "wiring (libs/ops/control_plane/actuators.desk_actuators)",
        "scripts/check_dead_architecture.py",
        "desks/mt5/reports/dead_architecture.json",
        counts=("dead", "organs", "n"),
        notes="check_birth_obligations' executable axis carries the same obligation at birth"),
    DefectClass(
        "store_emptied_by_second_writer",
        "two writers on one store, and the second one truncates the first",
        "the 1,078 lines removed from gateway.py by the hourly Dell sync (CLAUDE.md)",
        "scripts/check_protected_records.py",
        "",
        "scripts/check_protected_records.py",
        "desks/mt5/reports/PROTECTED_RECORDS.json",
        counts=("losses", "protected", "n"),
        owner="principal",
        notes="REPAIR IS DELIBERATELY EMPTY: an automated repair here would itself be a second "
              "writer. The moneypath pre-commit guard blocks the write; a human decides"),
    DefectClass(
        "retirement_on_absence",
        "an organ retires or voids a row because a reference was absent or stale",
        "GOLD_RETIRED re-derivation: an empty ledger once voided a live window",
        "scripts/check_no_retirement_on_absence.py",
        "",
        "scripts/check_no_retirement_on_absence.py",
        "desks/mt5/reports/DESTRUCTIVE_PATHS.json",
        counts=("unguarded", "paths", "n"),
        owner="builder",
        notes="check_birth_obligations' destructive axis stops a NEW unguarded path arriving"),
    DefectClass(
        "queue_ordered_on_unmeasured",
        "a queue is ordered by a field nothing measured, so the order is noise",
        "the research queue's priority field, repeatedly unmeasured",
        "scripts/check_research_queue.py",
        "run_once:leg:queue_census",
        "scripts/check_research_queue.py",
        "desks/mt5/reports/QUEUE_CENSUS.json",
        counts=("unmeasured", "rows", "n"),
        notes=""),
    DefectClass(
        "one_word_two_measurements",
        "two organs use one word for two different measurements",
        "'coverage' meaning both axis coverage and bar coverage; verdicts silently disagreed",
        "scripts/check_claim_consistency.py",
        "",
        "scripts/check_claim_consistency.py",
        # THE PATH THE DETECTOR ACTUALLY WRITES, not the one this row wished for. Until
        # 2026-09-23 this named desks/mt5/reports/CLAIM_CONSISTENCY.json, which
        # check_claim_consistency.py has never written on any host: its _OUT is
        # data/claim_consistency.json. A row that names an artifact its own detector cannot
        # produce pins the class in MANUAL for ever -- the registry reporting the registry's
        # own typo as a defect the desk still finds by hand.
        "data/claim_consistency.json",
        counts=("status", "n_compared", "n_contradicted", "n_unresolved"),
        owner="builder",
        notes="repair is a rename, which is a code change: detected automatically, closed by "
              "hands, and that is the honest bucket"),
    DefectClass(
        "task_silently_expired",
        "a scheduled task expired, was disabled, or was never registered at all",
        "MT5-Dept-Mathlab was declared in box_tasks.manifest with installer=NONE and had never "
        "existed on the box; its five legs read NEVER for as long as the manifest had claimed it",
        "scripts/check_box_tasks.py",
        "restart:task (libs/ops/control_plane/actuators.restart_resident)",
        "scripts/check_scheduled_tasks.py",
        "desks/mt5/reports/BOX_TASKS.json",
        counts=("missing", "expired", "tasks", "n"),
        notes="registered 2026-09-23 from MT5-Dept-Meta's own XML, SYSTEM principal"),
    DefectClass(
        "leaked_worker_pool",
        "a worker pool leaks processes that hold commit until the box thrashes",
        "14 resident pythons and 239 MB free during an external_gauntlet stand-down",
        "desks/mt5/scripts/reap_orphaned_workers.py",
        "reap_orphans (libs/ops/control_plane/actuators.desk_actuators)",
        "scripts/check_orphanable_writers.py",
        "desks/mt5/reports/ORPHAN_REAPER.json",
        counts=("reaped", "orphans", "n"),
        notes="the reconciler reaps FIRST on every apply pass, before it plans anything"),
    DefectClass(
        "lock_another_principal_cannot_open",
        "a lock is created so that the other principal can never take it",
        "SYSTEM-created locks the interactive session could not open, and the reverse",
        "scripts/check_plumbing_invariants.py",
        "",
        "scripts/check_plumbing_invariants.py",
        "desks/mt5/reports/PLUMBING_INVARIANTS.json",
        counts=("violations", "locks", "n"),
        owner="principal",
        notes="an automated chmod here would be a second writer on a lock; named, not repaired"),
    DefectClass(
        "clock_stops_accruing",
        "a clock still fires but stops accruing, so nothing downstream advances",
        "~960 silent merge aborts; 57 VPS commits never reached the compiler",
        "desks/mt5/research/clock_liveness.py",
        "heal_clocks (libs/ops/control_plane/actuators.desk_actuators)",
        "scripts/check_clock_liveness.py",
        "desks/mt5/reports/CLOCK_LIVENESS.json",
        counts=("dead", "clocks", "n"),
        notes=""),
    DefectClass(
        "source_stops_at_bytes",
        "a source is collected and never reaches cells the judge can read",
        "495 of 503 grounds hold no position in the chain (birth fence, 2026-09-23)",
        "scripts/check_source_drain.py",
        "run_once:leg:ingestion_ledger",
        "scripts/check_birth_obligations.py",
        "desks/mt5/reports/SOURCE_DRAIN.json",
        counts=("stalled", "sources", "n"),
        notes=""),
    DefectClass(
        "family_never_reaches_judge",
        "a family accumulates cells that no judge ever reads",
        "0 of 79 families showed a judge reach on the build box, 2026-09-23",
        "scripts/check_judge_coverage.py",
        "run_once:leg:judge_coverage",
        "scripts/check_judge_coverage.py",
        "desks/mt5/reports/JUDGE_COVERAGE.json",
        counts=("unjudged", "families", "n"),
        notes="the judge's family set is DERIVED from the registry, so a new family is inside "
              "its coverage the moment it exists"),
)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _scalars(path: Path, keys: tuple[str, ...]) -> dict[str, Any]:
    try:
        if path.stat().st_size > 8_000_000:
            return {"_": f"{UNMEASURED} (artifact too large to parse in budget)"}
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict):
        return {}
    return {k: doc[k] for k in keys if k in doc and isinstance(doc[k], (int, float, bool, str))}


def judge(dc: DefectClass, root: Path, now: float | None = None) -> dict[str, Any]:
    """One class, with each of its four parts resolved against THIS tree."""
    t = now if now is not None else time.time()
    det = (root / dc.detector).is_file() if dc.detector else False
    fen = (root / dc.fence).is_file() if dc.fence else False
    rep = bool(dc.repair.strip())
    art = root / dc.artifact
    try:
        st = art.stat()
        age_s: float | None = t - st.st_mtime
        ran_at = _iso(st.st_mtime)
    except OSError:
        age_s, ran_at = None, UNMEASURED
    fresh = age_s is not None and age_s <= dc.window_s

    if not det:
        bucket, why = "MANUAL", (f"no detector in this tree ({dc.detector or 'none declared'}): "
                                 f"instances of this class are found by a person")
    elif age_s is None:
        # NEVER PRODUCED HERE is the MANUAL bucket, not a fence failure: the detector is written
        # but nothing on this host has ever run it, so instances of this class are still found by
        # a person. It is counted, and the manual count ratchets down -- which drives it closed
        # instead of leaving a fence red on the day it was built (L1.43).
        bucket, why = "MANUAL", (f"the detector exists but its artifact {dc.artifact} has never "
                                 f"appeared on this host: instances are still found by hand")
    elif not fresh:
        bucket, why = UNMEASURED, (f"the detector last produced {age_s / 3600:.1f}h ago, past its "
                                   f"{dc.window_s / 3600:.1f}h window: a stopped detector is not "
                                   f"a clean class")
    elif rep and fen:
        bucket, why = "AUTOMATED", ("detected and repaired without hands; the fence fails if the "
                                    "class returns")
    else:
        bucket, why = "DETECTED", ("found automatically, closed by hands"
                                   + ("" if rep else " -- no actuator declared")
                                   + ("" if fen else " -- no fence declared"))
    return {
        "key": dc.key, "title": dc.title, "cost": dc.cost, "owner": dc.owner,
        "bucket": bucket, "why": why, "notes": dc.notes,
        "detector": dc.detector, "detector_present": det,
        "repair": dc.repair or UNMEASURED, "repair_declared": rep,
        "fence": dc.fence, "fence_present": fen,
        "artifact": dc.artifact,
        "last_detection_at": ran_at,
        "last_detection_age_h": None if age_s is None else round(age_s / 3600, 2),
        "window_h": round(dc.window_s / 3600, 2),
        "found": _scalars(art, dc.counts) or ({} if age_s is None else {"_": UNMEASURED}),
    }


def measure(root: Path | None = None, now: float | None = None) -> dict[str, Any]:
    base = Path(root or ROOT)
    t = now if now is not None else time.time()
    rows = [judge(c, base, t) for c in CLASSES]
    census = {b: sum(1 for r in rows if r["bucket"] == b) for b in BUCKETS}
    uncovered = [r["key"] for r in rows
                 if not r["detector_present"] and not r["repair_declared"]
                 and r["owner"] == "department:meta"]
    return {
        "schema": "self_repair_registry/1",
        "generated_at": _iso(t),
        "cadence_s": CADENCE_S,
        "classes": len(rows),
        "census": census,
        "manual": census["MANUAL"],
        "uncovered": uncovered,
        "buckets": {
            "AUTOMATED": "detector, repair and fence all present and the detector is inside its "
                         "window: this class closes itself",
            "DETECTED": "found automatically, but a builder still closes each instance",
            "MANUAL": "no detector exists: instances are found by a person, which is the count "
                      "that must reach zero",
            UNMEASURED: "the detector exists but has not produced inside its own window -- a "
                        "stopped detector is never a clean class",
        },
        "rows": rows,
    }


def render(doc: dict[str, Any]) -> str:
    c = doc["census"]
    out = ["# SELF-REPAIR REGISTRY -- which defect classes close themselves", "",
           "<!-- DERIVED. Written by desks/mt5/research/self_repair_registry.py on the clock "
           "`hourly_cycle:self_repair`. Edit the organ, never this file. -->", "",
           f"Measured **{doc['generated_at']}** over **{doc['classes']}** declared classes.", "",
           "| bucket | classes | meaning |", "|---|---:|---|"]
    out += [f"| **{b}** | {c.get(b, 0)} | {doc['buckets'][b]} |" for b in BUCKETS]
    out += ["", f"**{doc['manual']} class(es) are still found by hand.** That is the number this "
                f"registry exists to drive to zero; it ratchets down and "
                f"`scripts/check_self_repair.py` fails when it rises.", "",
            "| class | bucket | detector | repair | fence | last detection | found |",
            "|---|---|---|---|---|---|---|"]
    for r in doc["rows"]:
        found = "; ".join(f"{k}={v}" for k, v in (r["found"] or {}).items()) or UNMEASURED
        age = (UNMEASURED if r["last_detection_age_h"] is None
               else f"{r['last_detection_age_h']}h")
        out.append(f"| `{r['key']}` | **{r['bucket']}** | `{r['detector'] or '-'}` | "
                   f"`{r['repair']}` | `{r['fence'] or '-'}` | {age} | {found} |")
    out += ["", "## What each class already cost", ""]
    out += [f"- **{r['key']}** -- {r['title']}. {r['cost']}. {r['why']}" for r in doc["rows"]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root)
    doc = measure(root)
    try:
        _atomic(root / "desks" / "mt5" / "reports" / "SELF_REPAIR.json",
                json.dumps(doc, indent=1, default=str))
        _atomic(root / "docs" / "research" / "SELF_REPAIR.md", render(doc))
    except OSError as exc:
        print(f"self_repair_registry: NOT written ({type(exc).__name__}: {exc})")
        return 1
    try:
        from libs.ops import events
        events.emit("STATE_PUBLISHED", path=root / "desks" / "mt5" / "data" / "events.jsonl",
                    leg="self_repair", classes=doc["classes"], manual=doc["manual"],
                    automated=doc["census"]["AUTOMATED"])
    except Exception:                                        # pragma: no cover - event log only
        pass
    if a.json:
        print(json.dumps({k: v for k, v in doc.items() if k != "rows"}, indent=1, default=str))
    else:
        c = doc["census"]
        print(f"self_repair: {doc['classes']} defect class(es): AUTOMATED {c['AUTOMATED']}, "
              f"DETECTED {c['DETECTED']}, MANUAL {c['MANUAL']}, {UNMEASURED} {c[UNMEASURED]} "
              f"-> SELF_REPAIR.json + SELF_REPAIR.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
