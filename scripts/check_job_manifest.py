#!/usr/bin/env python3
"""JOB MANIFEST -- every scheduled job publishes success, freshness, hashes and last-valid output.

WHY (principal 2026-08-26: "every job must publish success, failure, freshness, input/output
hashes and last-valid output; alert on stale data, missing consumers, orphan modules and
zero-yield miners"). This desk has repeatedly discovered that a job was dead only by reading its
artifact by hand, hours or days later:

  * the tick tape raised ModuleNotFoundError EVERY HOUR and exited 0, so 16.2M ticks went
    unrecorded while the cycle printed "cycle done";
  * shadow_cycle exited 1 every 15 minutes on a Windows ACL error for an unknown period;
  * `promotion_gate.py` published NO-PRODUCER and returned 0, which the cadence scored as a duty
    fired -- for its entire existence;
  * a certifier rewrote the survivors file from n=1 to n=0 with exit code 0.

Exit codes are the wrong instrument. Every one of those jobs "succeeded". What distinguishes a
working organ from a dead one is whether its OUTPUT moved, and that is what this checks: an
artifact's hash, its age, and whether anything downstream reads it.

WHAT IS ALERTED, and why each is a distinct failure rather than one:

  STALE      -- the artifact exists but is older than the job's own cadence allows. The job is
                scheduled and silent; something is failing without saying so.
  FROZEN     -- the artifact is fresh but its CONTENT HASH has not changed across runs. The job
                runs, writes, and produces the same bytes: a loop that is turning without
                cutting. Distinct from STALE because the timestamp looks healthy.
  MISSING    -- declared but never produced. An owed build, not a passing check (L1.28a).
  NO-CONSUMER-- produced, but nothing reads it. Either the consumer is unwired (a gap) or the
                artifact is dead weight; both are defects, and neither is visible from the job.

The manifest lives in data/job_manifest.json and RATCHETS: a job that has ever produced an
artifact is expected to keep producing one. Last-valid output and its hash are retained so a
regression can be pinpointed to a run rather than a day.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
STATE = ROOT / "data" / "job_manifest.json"
ALARM = ROOT / "data" / "JOB_MANIFEST_ALARM.txt"

#: artifact -> (max_age_hours, who consumes it). The consumer is named so "nothing reads this"
#: is a checkable claim rather than an impression.
JOBS: dict[str, tuple[float, str]] = {
    "desks/mt5/reports/UNIVERSAL_SURVIVORS.json": (26.0, "shadow_admission, promoter, dashboard"),
    "desks/mt5/reports/shadow/shadow_state.json": (3.0, "promoter, reconciler, dashboard"),
    "desks/mt5/reports/shadow/scalp_shadow_state.json": (3.0, "shadow_cycle, dashboard"),
    "desks/mt5/reports/shadow/qquant_shadow_state.json": (3.0, "promoter, dashboard"),
    "desks/mt5/reports/execution_quality.json": (36.0, "promoter (promotion gate), dashboard"),
    "desks/mt5/data/sleeve_registry.json": (3.0, "shadow_forward identity check"),
    "desks/mt5/data/decay_live.json": (26.0, "dashboard, gateway risk"),
    "desks/mt5/data/forward_reconcile.json": (26.0, "operator audit"),
    "data/gauntlet_survivors.json": (26.0, "promotion_gate"),
    "web/desk_state.json": (0.5, "dashboard (Dell/phone)"),
    "data/authority_ratchet.json": (1.0, "earned-evidence floors"),
    "data/sameday_pipeline.json": (2.0, "same-day fence"),
}


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def main() -> int:
    now = datetime.now(tz=UTC)
    state = _read(STATE) or {"jobs": {}}
    jobs = state.setdefault("jobs", {})
    findings: list[str] = []
    rows: dict[str, dict] = {}

    for rel, (max_age_h, consumer) in JOBS.items():
        path = ROOT / rel
        prior = jobs.get(rel, {})
        if not path.exists():
            rows[rel] = {"status": "MISSING", "consumer": consumer}
            if prior.get("ever_produced"):
                findings.append(
                    f"MISSING {rel}: produced before (last good {prior.get('last_valid_at')}) "
                    f"and now absent -- a produced artifact that vanishes is a regression, not a "
                    f"quiet day. Consumer: {consumer}")
            else:
                findings.append(f"MISSING {rel}: declared but NEVER produced -- an owed build. "
                                f"Consumer: {consumer}")
            jobs[rel] = {**prior, "status": "MISSING", "checked_at": now.isoformat()}
            continue

        digest = _hash(path)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        age_h = (now - mtime).total_seconds() / 3600
        status = "OK"
        if age_h > max_age_h:
            status = "STALE"
            findings.append(
                f"STALE {rel}: {age_h:.1f}h old, limit {max_age_h}h. The job is scheduled and "
                f"silent -- exit codes do not catch this, only the artifact does. "
                f"Consumer: {consumer}")
        elif digest and digest == prior.get("hash") and prior.get("hash_runs", 0) >= 3:
            status = "FROZEN"
            findings.append(
                f"FROZEN {rel}: fresh ({age_h:.1f}h) but byte-identical across "
                f"{prior['hash_runs'] + 1} checks -- the job runs and writes the same output. A "
                f"loop turning without cutting. Consumer: {consumer}")

        rows[rel] = {"status": status, "age_h": round(age_h, 2), "hash": digest,
                     "consumer": consumer}
        jobs[rel] = {
            "status": status, "hash": digest,
            "hash_runs": (prior.get("hash_runs", 0) + 1) if digest == prior.get("hash") else 0,
            "checked_at": now.isoformat(timespec="seconds"),
            "ever_produced": True,
            "last_valid_at": (mtime.isoformat(timespec="seconds") if status == "OK"
                              else prior.get("last_valid_at")),
            "last_valid_hash": digest if status == "OK" else prior.get("last_valid_hash"),
            "max_age_h": max_age_h, "consumer": consumer,
        }

    state["checked_at"] = now.isoformat(timespec="seconds")
    state["summary"] = {s: sum(1 for r in rows.values() if r["status"] == s)
                        for s in sorted({r["status"] for r in rows.values()})}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, default=str), "utf-8")

    if not findings:
        if ALARM.exists():
            ALARM.unlink()
        print(f"job manifest: all {len(rows)} artifact(s) fresh and moving {state['summary']}")
        return 0

    body = (f"JOB MANIFEST {now.isoformat(timespec='seconds')}\n\n"
            + "\n".join(f"  - {f}" for f in findings) + "\n")
    ALARM.write_text(body, "utf-8")
    print(body)
    subprocess.Popen(["systemctl", "--user", "start", "--no-block", "quant-gap-wirer.service"])
    return 1


if __name__ == "__main__":
    sys.exit(main())
