#!/usr/bin/env python3
"""A DESK ARTIFACT'S OWN GENERATION STAMP MAY NEVER GO BACKWARD (GAP 161).

MEASURED 2026-08-27. `desks/mt5/data/forward_reconcile.json` was read at `checked_at`
**2026-08-27T07:58:08Z** (enrolled 21, certified_clocks 17) and minutes later re-read as
**2026-08-26T02:02:32Z** (enrolled 19, certified_pairs 6) -- a full day backward, in the file that
records which forward clocks are enrolled. Same trample family as GAPs 155/156/157. GAP 157 built
`check_doc_replay_fence.py` for guarded DOCUMENTS; the `desks/mt5` tree had no equivalent, so the
desk's record of its own live book can regress to a stale snapshot and still read as authoritative.

WHY NOT THE DOCUMENT FENCE'S TEST. That fence asks "does the working blob appear in this file's own
git history?" -- exact for an append-mostly document that changes rarely. These artifacts are
rewritten every few minutes by the trading box and pulled here, so `working != HEAD` is their
NORMAL state and carries no signal, and healing from HEAD would itself roll them backward.

THE RIGHT INSTRUMENT IS ALREADY INSIDE THE FILE. Each of these carries the moment it was
generated, so monotonicity is checkable without git, without mtime (which `scp` and the pull have
both faked before -- GAP 153) and independently of which machine wrote it. A stamp that moves
backward is never legitimate: a regenerated artifact stamps NOW, so an older stamp means a stale
copy was written over a newer one.

REPAIR, THEN ESCALATE. A regression restores the newest content this fence has seen, atomically,
and counts the occurrence. If the same artifact regresses `ESCALATE_AFTER` times the restore
STOPS and the finding is re-labelled a source-side defect: at that point the writer upstream is
persistently republishing stale content, this box cannot win the fight by rewriting it, and
continuing to would hide a defect only a console session can kill. Repair is the default; refusing
to repair forever is the escalation, not the resting state.

    .venv/bin/python scripts/check_artifact_monotonic.py            # detect + repair
    .venv/bin/python scripts/check_artifact_monotonic.py --report   # detect only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "artifact_high_water"
OUT = ROOT / "data" / "artifact_monotonic.json"

#: Artifacts whose silent rollback changes a decision, and what each one decides. Deliberately
#: NOT every file: an artifact with no consumer costs nothing when it regresses, and a fence that
#: guards everything is one nobody can reason about.
WATCHED: dict[str, str] = {
    "desks/mt5/data/forward_reconcile.json":
        "which clocks are enrolled and certified -- GAP 161's observed regression",
    "desks/mt5/data/sleeve_registry.json":
        "the frozen identity and pre-registration boundary of every sleeve; a rollback here "
        "re-opens GAP 162 by a different route",
    # OBSERVED REGRESSING, 2026-09-04. The canon IS enrolment: every forward clock is started by
    # a certificate in this file, so a rollback here does not merely misreport the book -- it
    # UNENROLS it. Measured today: the box's copy was overwritten at 01:28 UTC with a sweep from
    # 2026-08-23 carrying ONE survivor, while reports/UNIVERSAL_SURVIVORS.json held the current
    # 2026-09-03 sweep with 58. Enrolment collapsed with it and 48 clocks went RETIRED_ORPHAN,
    # freezing 207 real forward trades -- more evidence than the identity bug had held. The
    # rollback was invisible because the file's MTIME was current; only its `swept_at` was twelve
    # days old, which is precisely the difference this fence reads.
    "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json":
        "the certificate set that IS forward enrolment; a rollback here unenrols the whole book",
    "desks/mt5/reports/UNIVERSAL_SURVIVORS.json":
        "the same certificate set the dashboard and the reconciler read",
    "desks/mt5/data/decay_live.json":
        "live-sleeve decay verdicts (L1.59 FADE/RETIRE)",
    "desks/mt5/reports/execution_quality.json":
        "the promotion gate's execution evidence",
    "desks/mt5/reports/shadow/shadow_state.json":
        "every forward clock's n, boundary and status",
    # OBSERVED REGRESSING, 2026-08-27. This is the ONE artifact the read-only shadow watchdog
    # judges the entire forward book by -- freshness, aggregate status, blocked count, missing
    # certificates -- and it was the only shadow file NOT watched here. During the repair of the
    # 5.5-hour outage its `updated_at` was measured going 21:25:47 -> 15:31:55 -> 21:39:08: a
    # six-hour jump BACKWARDS, carrying the pre-fix `KeyError: 'EURZAR'` back with it. The cause
    # of that single rollback was not established, which is exactly why it belongs to a fence
    # rather than to a diagnosis: a stamp that moves backwards is a defect whoever moved it, and
    # this fence restores the newer copy and escalates on a writer that keeps doing it.
    "desks/mt5/reports/shadow/shadow_health.json":
        "the aggregate the shadow watchdog reads; a rollback here re-reports a repaired outage "
        "as live, or a live one as repaired",
}

#: Recognised top-level generation stamps, newest wins. Producers name this field differently and
#: none of them is wrong; what matters is that SOME declared stamp exists (L1.46).
# `swept_at` is the certificate canon's own generation stamp. Without it here the canon reads as
# UNMEASURABLE and this fence cannot judge the one artifact that decides enrolment -- which is how
# a twelve-day-old sweep sat in place with a current mtime and nothing noticed.
STAMP_KEYS = ("checked_at", "updated_at", "measured_at", "reconciled_at", "assessed_at",
              "swept_at",
              "generated_at", "built_at", "last_run", "as_of")

#: Restores before a persistent regression is called what it is: a defect at the writer.
ESCALATE_AFTER = 3


def _slug(rel: str) -> str:
    return rel.replace("/", "__")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def stamp_of(doc) -> datetime | None:
    """The NEWEST declared generation stamp in `doc`, or None when it declares none.

    None is UNMEASURABLE, not 'old': an artifact with no stamp cannot be judged by this fence and
    must be reported as such rather than silently passing (L1.28a).
    """
    if not isinstance(doc, dict):
        return None
    best: datetime | None = None
    for key in STAMP_KEYS:
        raw = doc.get(key)
        if not isinstance(raw, str):
            continue
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        when = when if when.tzinfo else when.replace(tzinfo=UTC)
        if best is None or when > best:
            best = when
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true",
                    help="detect only; never restore (the default is detect AND repair)")
    args = ap.parse_args()

    now = datetime.now(tz=UTC)
    STORE.mkdir(parents=True, exist_ok=True)
    regressions, restored, unmeasurable, escalated, ok = [], [], [], [], []

    for rel, why in WATCHED.items():
        path = ROOT / rel
        doc = _read_json(path)
        stamp = stamp_of(doc)
        if stamp is None:
            unmeasurable.append({"file": rel, "why": (
                "absent, unparseable, or declaring no generation stamp -- this fence cannot judge "
                "it, which is a gap in coverage and never a clean verdict")})
            continue

        keep_path = STORE / f"{_slug(rel)}.json"
        keep = _read_json(keep_path) or {}
        kept_stamp = None
        if isinstance(keep.get("stamp"), str):
            try:
                kept_stamp = datetime.fromisoformat(keep["stamp"])
            except ValueError:
                kept_stamp = None

        text = path.read_text("utf-8")
        if kept_stamp is None or stamp > kept_stamp:
            _write_atomic(keep_path, json.dumps({
                "stamp": stamp.isoformat(), "saved_at": now.isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
                "regressions": int(keep.get("regressions") or 0), "content": text}, indent=1))
            ok.append(rel)
            continue
        if stamp == kept_stamp:
            ok.append(rel)
            continue

        # BACKWARD. Never legitimate: a regenerated artifact stamps NOW.
        count = int(keep.get("regressions") or 0) + 1
        back_h = (kept_stamp - stamp).total_seconds() / 3600.0
        finding = {"file": rel, "decides": why, "on_disk": stamp.isoformat(),
                   "newest_seen": kept_stamp.isoformat(), "hours_backward": round(back_h, 2),
                   "occurrence": count}
        regressions.append(finding)
        keep["regressions"] = count

        if count > ESCALATE_AFTER or args.report:
            finding["action"] = "ESCALATED" if count > ESCALATE_AFTER else "REPORT_ONLY"
            escalated.append(rel) if count > ESCALATE_AFTER else None
        elif isinstance(keep.get("content"), str):
            _write_atomic(path, keep["content"])
            finding["action"] = "RESTORED"
            restored.append(rel)
        else:
            finding["action"] = "NO_KEPT_CONTENT"
        _write_atomic(keep_path, json.dumps(keep, indent=1))

    doc = {"checked_at": now.isoformat(timespec="seconds"),
           "status": "BREACH" if regressions else ("UNMEASURED" if not ok else "OK"),
           "watched": len(WATCHED), "clean": sorted(ok), "regressions": regressions,
           "restored": restored, "escalated": escalated, "unmeasurable": unmeasurable,
           "measuring_command": "scripts/check_artifact_monotonic.py"}
    _write_atomic(OUT, json.dumps(doc, indent=1, sort_keys=True))

    print(f"artifact monotonic: {len(ok)}/{len(WATCHED)} at or ahead of their newest seen stamp")
    for row in regressions:
        print(f"  ROLLED BACK {row['hours_backward']:.2f}h: {row['file']} "
              f"({row['on_disk']} < {row['newest_seen']}) -- decides {row['decides']}; "
              f"occurrence {row['occurrence']}, {row['action']}")
    for rel in escalated:
        print(f"  ESCALATED: {rel} has regressed more than {ESCALATE_AFTER} times. The writer "
              f"upstream is republishing stale content; this box cannot win by rewriting it and "
              f"continuing to would hide a defect only a console session can kill.")
    for row in unmeasurable:
        print(f"  UNMEASURABLE: {row['file']} -- {row['why']}")
    return 1 if (regressions or unmeasurable) else 0


if __name__ == "__main__":
    sys.exit(main())
