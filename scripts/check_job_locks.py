"""Hourly: every held research lock's owner is PROGRESSING, or it is named WEDGED and cured.

2026-10-29: the canonical docket writer lane (`merge_hypotheses`) was held 15 h by a living pid
at ~1.5 GB that used 2.3 s of CPU a minute and did no IO, and every docket intake refused behind
it reading "owner ALIVE". `job_lock` only looked at the owner when someone contended, and only
asked whether it was alive. This leg looks at every held lock every hour and asks whether the
owner is progressing (`job_lock.owner_progress`): by its BEATS when it beats
(`job_lock.heartbeat`, phase by phase -- CPU alone read that 2.3 s-a-minute owner as working),
else by the CPU of its WHOLE process tree (a parent waiting on a busy child is progressing). It
rewrites `reports/JOB_LOCK_HEALTH.json` in full every pass, and exits
`EXIT_WEDGED` (named OWNER_WEDGED in hourly_cycle.NAMED_FAILURE_EXITS) while any owner is WEDGED.

THE CURE, UNDER THE ITEM-21 RAILS. WEDGED is called after `job_lock.WEDGED_AFTER_S` (30 min) of
no progress (or a beaten phase's own longer limit). A lock on the research allowlist whose owner
has then made no progress for `AUTO_STOP_AFTER_S` (two hours) is stopped with its descendants:
the tree is frozen, listed until nothing new appears, then terminated children first. Never by bare pid: the owner must be a Python
interpreter whose argv carries the lock's own script as an ELEMENT (a path or a `-m` module, not
a substring of some other argument), and it must have been created no later than the lock's
`started_at`, so a recycled pid is never touched. The stop is SIGTERM on POSIX and
TerminateProcess on Windows -- not graceful: `finally` blocks may not run. That is covered, not
assumed away: `job_lock` reclaims a dead owner's lock, and merge_hypotheses sweeps a killed
pass's orphan temp files. Every stop is journaled (a JOB_LOCK_STOPPED event and the report's
`stops` history). Nothing on the money path, the judge, the certifier or the terminal lane is on
the list; those are named RED and left to an operator. A stop the OS refuses (a SYSTEM-owned
process) says so and stays RED.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import job_lock as J  # noqa: E402

#: The leg's artifact, `job_lock.HEALTH_REPORT`, bound by name so the component registry and the
#: runtime attestation can see what this organ writes (a test pins the two equal).
OUT = ROOT / "desks" / "mt5" / "reports" / "JOB_LOCK_HEALTH.json"
#: The exit while any owner is WEDGED. A failure, named (hourly_cycle.NAMED_FAILURE_EXITS), not
#: a verdict: a wedged lock is a stage that is not running. Not 2, argparse's usage error.
EXIT_WEDGED = 3
#: A WEDGED research owner is stopped once its tree has made no CPU progress for this long.
AUTO_STOP_AFTER_S = 2 * 3600.0
#: Listing rounds while freezing the owner's tree before a stop.
STOP_LIST_ROUNDS = 20
#: Seconds of clock slack when checking the owner was created before its lock was written.
CREATE_SLACK_S = 2.0
#: Lock name -> the scripts (file stem or module leaf) that legitimately hold it. The owner's
#: argv must carry one of them as an element before it may be stopped. `hourly_cycle` is not
#: here: it drives the promoter and allocator legs, so a lock it holds is named RED, never cured.
AUTO_STOP_JOBS: dict[str, tuple[str, ...]] = {
    "merge_hypotheses": ("merge_hypotheses", "local_converter", "breadth_sweep",
                         "session_chart_equivalents"),
    "miner_candidate_compiler": ("miner_candidate_compiler",),
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
                  if not p.name.endswith((".peaks.json", ".progress.json", ".beat.json")))


def _leaf(arg: str) -> str:
    base = arg.replace("\\", "/").rsplit("/", 1)[-1]
    return base[:-3] if base.endswith(".py") else base


def runs_script(argv: list[str], scripts: tuple[str, ...]) -> bool:
    """True when `argv` is a Python interpreter running one of `scripts` -- as a script path
    element or a `-m` module -- never because a script name appears inside another argument
    (audit of v5, MF2: `bash -c "...gateway.py --log merge_hypotheses.log"` matched)."""
    exe = _leaf(argv[0]).lower() if argv else ""
    if "python" not in exe and exe not in ("py", "py.exe"):
        return False
    # THE FIRST SCRIPT ELEMENT ONLY (audit of v6, SF6): it is what the interpreter runs; a later
    # `.py` is an argument to it (`python other.py --in merge_hypotheses.py`).
    for i, arg in enumerate(argv[1:], start=1):
        if argv[i - 1] == "-m":
            return arg.rsplit(".", 1)[-1] in scripts
        if arg == "-c":
            return False
        if arg.startswith("-"):
            continue
        return arg.endswith(".py") and not any(c.isspace() for c in arg) \
            and _leaf(arg) in scripts
    return False


def _epoch(stamp: object) -> float | None:
    try:
        return datetime.fromisoformat(str(stamp)).timestamp()
    except (TypeError, ValueError):
        return None


def _stop(pid: int, scripts: tuple[str, ...], started_at: object = None) -> dict[str, Any]:
    try:
        import psutil

        proc = psutil.Process(pid)
        argv = proc.cmdline()
        if not runs_script(argv, scripts):
            return {"stopped": False, "why": f"pid {pid} does not run {scripts} (pid reused?)"}
        born, lock_at = proc.create_time(), _epoch(started_at)
        if lock_at is None:
            return {"stopped": False, "why": "lock has no readable started_at; not stopped"}
        if born > lock_at + CREATE_SLACK_S:
            return {"stopped": False, "why": (f"pid {pid} was created after the lock was "
                                              "written (pid reused); not stopped")}
        # FREEZE, THEN LIST (audit of v6, SF1): an owner that spawns in a loop added children
        # between one listing and the terminate -- 5 orphans in 130, the two-writers case. The
        # owner is suspended first, then every descendant found, re-listed until a pass finds
        # nothing new, so nothing can be born after the tree is known.
        proc.suspend()
        tree: list = []
        seen: set[int] = set()
        for _ in range(STOP_LIST_ROUNDS):
            fresh = [c for c in proc.children(recursive=True) if c.pid not in seen]
            if not fresh:
                break
            for c in fresh:
                seen.add(c.pid)
                with contextlib.suppress(psutil.NoSuchProcess):
                    c.suspend()
            tree.extend(fresh)
        for p in reversed(tree):          # deepest descendants first, the owner last
            with contextlib.suppress(psutil.NoSuchProcess):
                p.terminate()
        proc.terminate()
        for p in [*tree, proc]:           # SIGTERM waits on a stopped process until SIGCONT
            with contextlib.suppress(psutil.NoSuchProcess):
                p.resume()
        _, alive = psutil.wait_procs([*tree, proc], timeout=30)
        for p in alive:
            with contextlib.suppress(psutil.NoSuchProcess):
                p.kill()
        return {"stopped": True, "tree": 1 + len(tree),
                "why": f"terminated pid {pid} and {len(tree)} descendant(s) "
                       f"({' '.join(argv)[:120]})"}
    except Exception as exc:
        return {"stopped": False, "why": f"stop refused: {type(exc).__name__}: {exc}"[:200]}


def _journal(name: str, health: dict[str, Any]) -> None:
    try:
        from libs.ops import events

        events.emit("JOB_LOCK_STOPPED", producer="job_lock_health", lock=name,
                    pid=health.get("pid"), idle_s=health.get("idle_s"),
                    why=(health.get("auto_stop") or {}).get("why"))
    except Exception as exc:              # the report's `stops` history still carries it
        print(f"job_lock_health: JOB_LOCK_STOPPED not journaled ({type(exc).__name__}: {exc})")


def run(*, root: Path | None = None, now: float | None = None, stop=_stop,
        cpu_of=None) -> dict[str, Any]:
    lock_root = root or J.LOCK_ROOT
    t = time.time() if now is None else now
    rows: dict[str, dict[str, Any]] = {}
    stops: list[dict[str, Any]] = []
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
            health["auto_stop"] = stop(health["pid"], AUTO_STOP_JOBS[name],
                                       health.get("started_at"))
            if health["auto_stop"].get("stopped"):
                health["status"] = "STOPPED"
                _journal(name, health)
                stops.append({"lock": name, "pid": health["pid"], "idle_s": health.get("idle_s"),
                              "at": datetime.fromtimestamp(t, UTC).isoformat(timespec="seconds"),
                              "why": health["auto_stop"].get("why")})
        rows[name] = health
    J.write_health_report(rows, now=t, new_stops=stops)
    wedged = sorted(n for n, r in rows.items() if r.get("status") == "WEDGED")
    return {"status": "RED" if wedged else "OK", "wedged": wedged, "locks": rows,
            "stops": stops}


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args(argv)
    out = run()
    print(json.dumps({"status": out["status"], "wedged": out["wedged"],
                      "locks": {k: v.get("status") for k, v in out["locks"].items()}}))
    return EXIT_WEDGED if out["status"] == "RED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
