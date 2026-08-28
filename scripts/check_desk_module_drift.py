"""Keep the desk box running the code that was committed here -- and re-ship it when it drifts.

WHY THIS EXISTS

Deploying to the desk box is verified by hash, which answers "did this land". It does not answer
"is this still there", and only the second question matters an hour later. Measured 2026-08-28:
job_lock.py was deployed and hash-verified TWICE, and both times was gone within the hour --
the box was running a copy with no memory admission at all, so the cache warmer died on
`TypeError: exclusive_job() got an unexpected keyword argument 'need_mb'`. orthogonal_sweep.py
went the same way an hour later, taking the calendar-key repair with it.

The box holds its own git checkout on a branch that diverged hundreds of commits ago, and
something there restores the working tree from it. So a fix does not fail on arrival; it decays
afterwards, silently, and the desk quietly resumes running last week's engine while every log
says the deployment succeeded.

WHAT THIS DOES

Compares each remotely-executed module's `git hash-object` on both boxes and re-ships the ones
that drifted. Cheap enough to run every few minutes, which is the point: the window between a
revert and the next sweep is where the damage happens.

THE ONE SAFETY PROPERTY THAT MATTERS: it only ever ships a file that matches HEAD. This box has a
replayer of its own that reverts working-tree files to ancient copies, and a healer that shipped
whatever happened to be on disk would faithfully propagate a trampled file to the box that
trades. A dirty file is REPORTED and skipped, never sent.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "desk_module_drift.json"
REMOTE = "contabo-mt5"

#: Everything the desk box EXECUTES that is authored here. Keep this list in step with
#: run_external_pipeline's REMOTE_MODULES plus the PowerShell the box runs on a schedule; a
#: module missing from here is one that can silently decay back to the box's own stale branch.
MODULES = [
    "desks/mt5/mt5desk/families.py",
    "desks/mt5/mt5desk/families_orthogonal.py",
    "desks/mt5/mt5desk/engine.py",
    "desks/mt5/mt5desk/universe.py",
    "desks/mt5/research/job_lock.py",
    "desks/mt5/research/edge_search.py",
    "desks/mt5/research/orthogonal_sweep.py",
    "desks/mt5/research/merge_hypotheses.py",
    "desks/mt5/research/hourly_cycle.py",
    "desks/mt5/research/backfill_coverage.py",
    "desks/mt5/scripts/external_gauntlet.py",
    "desks/mt5/scripts/warm_gauntlet_cache.py",
    "desks/mt5/scripts/stall_watch.ps1",
    "libs/research/bar_span.py",
    # The program-level gates the sweep imports. reality_check was NOT on this list and
    # was stale on the box by a full optimisation (2026-08-28) -- a module can be central
    # to certification and still be invisible to every sync, because nothing names it.
    "libs/validation/reality_check.py",
    "libs/validation/pbo.py",
    "libs/validation/bootstrap.py",
]


def _run(cmd: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return 124, ""


def _local_hash(rel: str) -> str | None:
    rc, out = _run(["git", "hash-object", str(ROOT / rel)])
    return out if rc == 0 and out else None


def _head_hash(rel: str) -> str | None:
    """The hash HEAD says this file should have -- the only version safe to ship."""
    rc, out = _run(["git", "rev-parse", f"HEAD:{rel}"])
    return out if rc == 0 and out else None


def _remote_hash(rel: str) -> str | None:
    rc, out = _run(["ssh", "-o", "ConnectTimeout=25", REMOTE,
                    f"cd C:\\opt\\quant && git hash-object {rel}"])
    if rc != 0:
        return None
    line = out.replace("\r", "").strip().splitlines()
    return line[-1].strip() if line else None


def main() -> int:
    now = datetime.now(tz=UTC)
    report: dict = {"checked_at": now.isoformat(timespec="seconds"),
                    "drifted": [], "healed": [], "dirty_skipped": [], "unreachable": []}

    for rel in MODULES:
        if not (ROOT / rel).exists():
            continue
        local, head = _local_hash(rel), _head_hash(rel)
        if local is None or head is None:
            report["unreachable"].append(rel)
            continue
        # NEVER SHIP WHAT DOES NOT MATCH HEAD. A trampled local file is exactly the thing this
        # must not propagate to the box that trades.
        if local != head:
            report["dirty_skipped"].append(rel)
            print(f"  DIRTY {rel}: local copy differs from HEAD -- not shipped (heal it here "
                  f"first; shipping a trampled file is how the desk got an ancient engine)")
            continue
        remote = _remote_hash(rel)
        if remote is None:
            report["unreachable"].append(rel)
            continue
        if remote == local:
            continue
        report["drifted"].append(rel)
        rc, _ = _run(["scp", "-o", "ConnectTimeout=45", "-q",
                      str(ROOT / rel), f"{REMOTE}:C:/opt/quant/{rel}"], timeout=180)
        after = _remote_hash(rel) if rc == 0 else None
        if after == local:
            report["healed"].append(rel)
            print(f"  RE-SHIPPED {rel}: box had {remote[:8]}, now {after[:8]} (matches HEAD)")
        else:
            print(f"  FAILED to re-ship {rel}: box still {str(after)[:8]}")

    OUT.write_text(json.dumps(report, indent=1), "utf-8")
    n_d, n_h = len(report["drifted"]), len(report["healed"])
    if report["dirty_skipped"]:
        print(f"DIRTY LOCALLY (not shipped): {', '.join(report['dirty_skipped'])}")
    if n_d:
        print(f"desk module drift: {n_d} drifted, {n_h} healed -> {OUT}")
        return 1
    print(f"desk modules: all {len(MODULES)} match HEAD on both boxes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
