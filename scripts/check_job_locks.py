"""Hourly: every held research lock's owner is PROGRESSING, or it is named WEDGED and cured.

2026-10-29: the canonical docket writer lane (`merge_hypotheses`) was held 15 h by a living pid
at ~1.5 GB that used 2.3 s of CPU a minute and did no IO, and every docket intake refused behind
it reading "owner ALIVE". `job_lock` only looked at the owner when someone contended, and only
asked whether it was alive. This leg looks at every held lock every hour, measures the owner's
CPU progress (`job_lock.owner_progress`), publishes `reports/JOB_LOCK_HEALTH.json`, and exits 1
while any owner is WEDGED.

THE CURE, UNDER THE ITEM-21 RAILS. A lock on the research allowlist whose owner has been WEDGED
for `AUTO_STOP_AFTER_S` is stopped -- terminate, never by bare pid: the process's command line
must name the lock's own script, so a recycled pid is never touched. Nothing on the money path,
the judge, the certifier or the terminal lane is on the list; those are named RED and left to an
operator. A stop the OS refuses (a SYSTEM-owned process) says so and stays RED. Once the owner is
gone `job_lock` reclaims the lock on the next attempt ("reclaiming lock from dead owner").
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import job_lock as J  # noqa: E402

#: A WEDGED research owner is stopped after this long with no CPU progress.
AUTO_STOP_AFTER_S = 2 * 3600.0
#: Lock name -> a command-line fragment the owner must carry before it may be stopped.
AUTO_STOP_JOBS: dict[str, tuple[str, ...]] = {
    "merge_hypotheses": ("merge_hypotheses", "local_converter", "breadth_sweep",
                         "session_chart_equivalents"),
    "miner_candidate_compiler": ("miner_candidate_compiler", "hourly_cycle"),
    "style_novelty": ("style_novelty",),
    "orthogonal_sweep": ("orthogonal_sweep",),
    "edge_search": ("edge_search",),
    "macro_desk": ("macro_desk",),
    "falsifier_run": ("falsifier_run",),
    "backfill_coverage": ("backfill_coverage",),
    "warm_gauntlet_cache": ("warm_gauntlet_cache",),
}
#: Never stopped automatically, whatever their state: the judge, the certifier, the terminal lane
#: and the money path. Listed so a test can prove the allowlist never reaches them.
NEVER_STOP = frozenset({"external_gauntlet", "certification_lane",
                        "fusion_terminal_research_lane", "pf_allocator", "tape_features"})


def _locks(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("*.json")
                  if not p.name.endswith((".peaks.json", ".progress.json")))


def _stop(pid: int, fragments: tuple[str, ...]) -> dict[str, Any]:
    try:
        import psutil

        proc = psutil.Process(pid)
        cmd = " ".join(proc.cmdline())
        if not any(f in cmd for f in fragments):
            return {"stopped": False, "why": f"pid {pid} does not run {fragments} (pid reused?)"}
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except psutil.TimeoutExpired:
            proc.kill()
        return {"stopped": True, "why": f"terminated pid {pid} ({cmd[:120]})"}
    except Exception as exc:
        return {"stopped": False, "why": f"stop refused: {type(exc).__name__}: {exc}"[:200]}


def run(*, root: Path | None = None, now: float | None = None, stop=_stop,
        cpu_of=None) -> dict[str, Any]:
    lock_root = root or J.LOCK_ROOT
    t = time.time() if now is None else now
    rows: dict[str, dict[str, Any]] = {}
    for lock in _locks(lock_root):
        name = lock.stem
        state = J._owner_state(lock)
        if state != "ALIVE":
            rows[name] = {"status": "OK" if state == "DEAD" else "UNMEASURED",
                          "owner": state, "why": f"owner {state}"}
            continue
        health = J.owner_progress(lock, now=t, cpu_of=cpu_of)
        if (health.get("status") == "WEDGED" and name in AUTO_STOP_JOBS
                and name not in NEVER_STOP
                and float(health.get("idle_s") or 0.0) >= AUTO_STOP_AFTER_S
                and isinstance(health.get("pid"), int)):
            health["auto_stop"] = stop(health["pid"], AUTO_STOP_JOBS[name])
            if health["auto_stop"].get("stopped"):
                health["status"] = "STOPPED"
        rows[name] = health
        J._publish_health(name, health, now=t)
    wedged = sorted(n for n, r in rows.items() if r.get("status") == "WEDGED")
    return {"status": "RED" if wedged else "OK", "wedged": wedged, "locks": rows}


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args(argv)
    out = run()
    print(json.dumps({"status": out["status"], "wedged": out["wedged"],
                      "locks": {k: v.get("status") for k, v in out["locks"].items()}}))
    return 1 if out["status"] == "RED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
