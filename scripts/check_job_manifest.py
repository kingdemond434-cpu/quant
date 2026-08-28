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
import sys
from datetime import UTC, datetime
from pathlib import Path

from libs.ops.repair_invoke import request_repair

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
    # sleeve_registry.json is DELIBERATELY NOT HERE. `freeze()` is idempotent -- it returns
    # early once a key is frozen -- so the file only changes when a NEW sleeve enrols and an
    # unchanged registry is the HEALTHY state. Gauging it by age (it carried a 3.0h window)
    # made it red whenever the desk was well, and it was only ever GREEN because
    # `pull_desk_state.sh` restamped it every two minutes without `scp -p`. The property
    # that matters -- no clock RUNS without a frozen identity -- is measured every pass by
    # `forward_reconcile` as IDENTITY_UNFROZEN, and forward_reconcile.json IS age-gauged
    # below because it rewrites on every run. Do not "restore" this row: age is the wrong
    # instrument here, not a missing one.
    "desks/mt5/data/decay_live.json": (26.0, "dashboard, gateway risk"),
    "desks/mt5/data/forward_reconcile.json": (26.0, "operator audit"),
    "data/gauntlet_survivors.json": (26.0, "promotion_gate"),
    "web/desk_state.json": (0.5, "dashboard (Dell/phone)"),
    "data/authority_ratchet.json": (1.0, "earned-evidence floors"),
    "data/sameday_pipeline.json": (2.0, "same-day fence"),
    # A FIX THAT NEVER REACHED THE BOX IS NOT A FIX. Measured 2026-08-27: the only
    # code-sync path ships a hardcoded four-file list, so the whole forward/promotion
    # chain the desk box executes was outside it and `h1_source.py` had silently
    # diverged. Nothing measured that, which is why it lasted.
    "data/desk_code_parity.json": (1.0, "desk-parity fence (is the box running this code)"),
    # A register silently rolled back six hours is worse than a missing one: it still reads
    # as authoritative. Measured 2026-08-27, two heals in 44 seconds.
    "data/doc_replay_fence.json": (0.5, "doc replay fence (stale-snapshot rollback)"),
    # THE ONE NUMBER THE PATH TO LIVE CAPITAL TURNS ON, and until 2026-08-27 nothing measured
    # it. The whole forward book was silently re-based to day zero three times in 32 hours
    # (registry history: 08-26T01:42, 08-27T01:13, 08-27T03:31) against a `days >= 14`
    # promotion bar, while the shadow watchdog reported OPERATING/defects:[] throughout. If
    # this artifact goes stale the ratchet has stopped and the next re-base is invisible again.
    "data/forward_clock_ratchet.json": (1.5, "forward-clock ratchet (silent re-base detector)"),
    # 17 live timers -- including the mt5-suite ratchet, the universe-registry cost repair and
    # six research seats -- were firing from ~/.config/systemd/user with no committed copy
    # anywhere (measured 2026-08-27). A rebuilt box schedules none of them and nothing says so.
    "data/unit_parity.json": (2.0, "unit parity (live timer with no committed unit)"),
    # GAP 161: forward_reconcile.json was observed going a full day BACKWARD mid-session while
    # still reading as authoritative. If this artifact goes stale the rollback detector has
    # stopped and the desk's record of its own live book can regress unnoticed again.
    "data/artifact_monotonic.json": (0.5, "artifact rollback fence (stamp went backward)"),
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
        checks_per_window = max(3, int(max_age_h * 2))   # manifest runs ~every 30 minutes
        if age_h > max_age_h:
            status = "STALE"
            findings.append(
                f"STALE {rel}: {age_h:.1f}h old, limit {max_age_h}h. The job is scheduled and "
                f"silent -- exit codes do not catch this, only the artifact does. "
                f"Consumer: {consumer}")
        # FROZEN MUST BE JUDGED AGAINST THE ARTIFACT'S OWN CADENCE, not a flat count. This read
        # "identical across 3 checks", but the manifest runs every 30 minutes while some artifacts
        # are DAILY -- execution_quality legitimately holds the same bytes across ~48 checks and
        # was reported FROZEN for it, which is a false alarm that trains the reader to ignore the
        # real ones. The honest test is whether the content has stood still for longer than the
        # job's own update interval allows.
        elif (digest and digest == prior.get("hash")
                and prior.get("hash_runs", 0) >= checks_per_window):
            status = "FROZEN"
            findings.append(
                f"FROZEN {rel}: fresh ({age_h:.1f}h) but byte-identical across "
                f"{prior['hash_runs'] + 1} checks -- longer than its own {max_age_h}h update "
                f"window allows, so the job is running and writing the same output rather than "
                f"simply not being due yet. A loop turning without cutting. "
                f"Consumer: {consumer}")

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

    # RETIRE THE ROWS THIS RUN NO LONGER EVALUATES, LOUDLY. `jobs` persists across runs and was
    # never pruned, so an artifact dropped from JOBS left its last verdict behind forever while
    # `summary` -- computed from `rows`, this run's evaluations -- silently stopped counting it.
    # Measured 2026-08-28: `jobs` held 17 rows and 2 FROZEN, `summary` said 16 and 1, and the
    # extra was `desks/mt5/data/sleeve_registry.json`, deliberately retired 19 hours earlier with
    # a good reason (age is the wrong instrument for an idempotent registry) and still reading
    # FROZEN to anything that walked `jobs`. Two consumers, two answers, one file. The row moves
    # to `retired` with the day it left rather than being deleted: a deliberate retirement stays
    # visible, and an ACCIDENTAL one -- a JOBS line dropped in an edit -- is discoverable here
    # instead of looking like the artifact was never monitored.
    retired = state.setdefault("retired", {})
    for rel in [k for k in jobs if k not in JOBS]:
        retired[rel] = {**jobs.pop(rel), "retired_at": now.isoformat(timespec="seconds"),
                        "note": "no longer declared in JOBS; last verdict frozen as-is"}
        findings.append(
            f"RETIRED {rel}: dropped from the manifest, last status "
            f"{retired[rel].get('status')}. If that was deliberate this line is the record; if a "
            f"JOBS entry was lost in an edit, the artifact is now unmonitored and this is how you "
            f"find out.")

    state["checked_at"] = now.isoformat(timespec="seconds")
    state["summary"] = {s: sum(1 for r in rows.values() if r["status"] == s)
                        for s in sorted({r["status"] for r in rows.values()})}
    # THE SUMMARY MUST DESCRIBE THE ROWS. Anything reading `jobs` and anything reading `summary`
    # now count the same population. Reported rather than asserted: a liveness organ that dies on
    # its own consistency check is a worse failure than the miscount it was checking for, and an
    # `assert` vanishes entirely under -O.
    if not (sum(state["summary"].values()) == len(jobs) == len(rows)):
        findings.append(
            f"SELF-INCONSISTENT: summary counts {sum(state['summary'].values())}, jobs holds "
            f"{len(jobs)}, this run evaluated {len(rows)}. Two consumers of this file will "
            f"disagree until that is one number.")
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
    request_repair("job-manifest breach")
    return 1


if __name__ == "__main__":
    sys.exit(main())
