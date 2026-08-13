#!/usr/bin/env python3
"""STALE-DAEMON REPAIR -- the actuator the stale-code detector never had (L1.28b).

DETECT IMPLIES REPAIR. max_audit's `daemon-stale-code-*` has fired repeatedly (2026-07-26
carry-leak alarm inert 8.7h over a bleeding book; 2026-08-05 executor 139 commits stale feeding
$4,805.61 into hurdle_rate; 2026-08-11 executor up 127.3h importing 2 modified files) and every
instance was closed BY HAND, because the detector had no standing actuator: polkit denies this
user systemctl, so a human -- or a brain cycle that happened to be awake -- had to notice the
defect and run scripts/ship_restart.py themselves. A detector whose repairs arrive by luck is
half an organ (L1.28b: an organ that only detects runs at HALF its deliverable), and this exact
class recurred 4x in 12 days because each closure was per-instance.

WHAT THIS DOES: for every unit in max_audit._DAEMONS, recompute the staleness verdict with
max_audit's own instruments (process start from /proc/<pid>/stat field 22 + btime, content
change from COMMIT DATES with mtime only for uncommitted edits -- both weld-classes this desk
already paid to learn), and where the RUNNING process imports files modified since it started,
restart it through ship_restart.ship() -- which owns every refusal (ruin tier, unknown unit,
no-autorestart) and never leaves a unit down.

THE GATES, in order (each is a named verdict, never a silent skip):
  * SKIP-FRESH        -- the normal, healthy outcome; this run restarts nothing.
  * SKIP-RUIN-TIER    -- the dead-man is restarted by an operator or nobody (L1.23). Its
                         staleness still prints loudly for the human; automation ends here.
  * SKIP-STERILE      -- L1.38: a restart SHIPS whatever is on disk into the money path, which
                         is what the sterile cockpit forbids mid-window. Money-path units wait
                         for the window; everything else repairs regardless.
  * SKIP-UNKNOWN-TIER -- ship() would refuse an unmapped unit; named here so the count is honest.

KNOWN LIMIT, deliberate: an ORPHANED worker (daemon-unsupervised-*) is NOT auto-killed -- ship()
only signals the unit's own MainPID, and killing a process systemd does not own is an operator
decision (the 2026-07-09 precautionary-kill lesson). Such a unit reports STILL-STALE after its
restart, which is the correct loud outcome, not a bug.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.deploy_plan import TIER_RUIN, tier_for_unit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = ROOT / "data/stale_daemon_repair.json"


def _money_path(rel: str, money: tuple[str, ...]) -> bool:
    """True when `rel` is on the money path -- exact file or directory-prefix entry."""
    return any(rel == m or (m.endswith("/") and rel.startswith(m)) for m in money)


def decide(rel: str, n_stale: int, *, window_status: str, tier: int | None,
           money: tuple[str, ...]) -> str:
    """One unit's action, as a pure function so the gating is testable without systemd."""
    if n_stale == 0:
        return "SKIP-FRESH"
    if tier is None:
        return "SKIP-UNKNOWN-TIER"
    if tier >= TIER_RUIN:
        return "SKIP-RUIN-TIER"
    if window_status != "OPEN" and _money_path(rel, money):
        return "SKIP-STERILE"
    return "REPAIR"


def _stale_state(rel: str) -> tuple[int | None, list[str]]:
    """(oldest worker pid, repo-relative files modified since it started). (None, []) if down."""
    from scripts.max_audit import _import_closure, _proc_start, _sources_changed_since, _worker_pids
    entry = ROOT / rel
    if not entry.exists():
        return None, []
    workers = _worker_pids(rel)
    if not workers:
        return None, []
    try:
        pid = min(workers, key=_proc_start)
        started = _proc_start(pid)
    except (OSError, ValueError):
        return None, []
    stale = _sources_changed_since(_import_closure(entry), started)
    return pid, [p.relative_to(ROOT).as_posix() for p in stale]


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="classify only; restart nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from scripts.check_change_window import MONEY_PATH, build_report
    from scripts.max_audit import _DAEMONS
    from scripts.ship_restart import ship

    window = "UNMEASURED"
    try:
        window = str(build_report().get("status") or "UNMEASURED")
    except Exception as exc:  # a broken window fence must fail toward STERILE, never OPEN
        print(f"stale-daemon-repair: change-window fence unreadable ({type(exc).__name__}: "
              f"{exc}) -- treating as UNMEASURED, money-path repairs held")

    results: list[dict[str, object]] = []
    failed = 0
    for svc, rel in sorted(_DAEMONS.items()):
        pid, stale = _stale_state(rel)
        if pid is None:
            action = "SKIP-NOT-RUNNING"       # check_organs owns a down unit, not this repairer
        else:
            action = decide(rel, len(stale), window_status=window,
                            tier=tier_for_unit(f"{svc}.service"), money=MONEY_PATH)
        row: dict[str, object] = {"unit": svc, "entry": rel, "pid": pid,
                                  "stale": stale[:6], "n_stale": len(stale), "action": action}
        if action == "REPAIR" and not args.dry_run:
            verdict = ship(f"{svc}.service")
            row["ship"] = verdict
            if verdict.get("verdict") == "RESTARTED":
                _, still = _stale_state(rel)
                # STILL-STALE after a successful restart = an orphaned worker or a mid-repair
                # commit; loud either way, and max_audit's next sweep re-fires on it.
                row["verified"] = "FRESH" if not still else f"STILL-STALE:{len(still)}"
            elif verdict.get("verdict") == "FAILED":
                failed += 1
        results.append(row)

    payload = {"generated": datetime.now(UTC).isoformat(), "window": window,
               "scanned": len(_DAEMONS), "results": results,
               "law": ("L1.28b -- detect implies repair: the stale-code detector's standing "
                       "actuator. Zero repairs is the healthy verdict, not an idle organ.")}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1) + "\n", "utf-8")
    if args.json:
        print(json.dumps(payload, indent=1))
    else:
        for r in results:
            extra = f" stale={r['n_stale']}" if r["n_stale"] else ""
            ship_v = r.get("ship")
            shipped = f" -> {ship_v['verdict']}" if isinstance(ship_v, dict) else ""
            verified = f" [{r['verified']}]" if "verified" in r else ""
            print(f"stale-daemon-repair | {r['unit']}: {r['action']}{extra}{shipped}{verified}")
        print(f"-> {_OUT} (window={window}, scanned={len(_DAEMONS)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
