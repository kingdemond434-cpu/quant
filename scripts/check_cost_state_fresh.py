"""Is the desk's cost state current? RED when any cost artifact is older than one cycle.

WHY (measured 2026-10-14). Every consumer that prices a trade reads the symbol x hour spread
surface (`data/cost_surface.json`) and the overnight financing table (`data/carry_state.json`).
On origin the first read `built_at` 2026-09-23 and the second `generated_at` 2026-08-29 (the VPS
cron's last write), and the triangle tape (`data/tape/triangle_executable.json`) read 2026-09-16.
None of the three was in the box's publish allowlist, so a reader off the box could not tell a
dead organ from an unpublished file -- and `ops/run_cost_state.cmd` ended `exit /b 0`, so the
scheduler reported success whatever the two producers returned. This fence reads each artifact's
OWN stamp on the box that writes it, names its age against its cycle, and publishes the verdict.

An absent or unstamped artifact is UNMEASURED and fails exactly like a stale one (L1.28a).

    python scripts/check_cost_state_fresh.py      # writes the report; exit 1 on any non-FRESH
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "COST_STATE_FRESHNESS.json"
#: The runner's own per-step exit lines (`ops/run_cost_state.cmd`), read for the diagnosis.
LOG_REL = "logs/MT5-CostState.log"

#: (artifact, stamp key, producer, max age in hours). One cycle plus the slack its clock needs:
#: MT5-CostState fires daily at 04:20, so 26 h; the triangle runs inside the hourly
#: `record_tape` leg, so 2 h -- red after ONE missed cycle, not two. Breadth's hourly carry rebuild only ever makes carry fresher.
ARTIFACTS: tuple[tuple[str, str, str, float], ...] = (
    ("data/cost_surface.json", "built_at", "MT5-CostState: research/cost_surface.py", 26.0),
    ("data/carry_state.json", "generated_at", "MT5-CostState: research/carry_state.py", 26.0),
    ("data/tape/triangle_executable.json", "at",
     "hourly_cycle record_tape: mt5desk/triangle_tape.py", 2.0),
)


#: A stamp further in the future than this is no reading of age at all (a wrong clock or a wrong
#: field), so it is UNMEASURED, never FRESH. Five minutes absorbs two hosts' ordinary skew.
FUTURE_SKEW_H = 5 / 60


def _stamp(raw: object) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def judge(path: Path, key: str, max_h: float, now: datetime) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"status": "UNMEASURED", "why": "artifact absent"}
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "why": f"unreadable ({type(exc).__name__})"}
    at = _stamp(doc.get(key)) if isinstance(doc, dict) else None
    if at is None:
        return {"status": "UNMEASURED", "why": f"no `{key}` stamp"}
    # Compare RAW seconds; round only for display (audit of 0004: rounding first let a stamp
    # ~5m15s in the future, or 2h17s past a 2h window, read FRESH).
    secs = (now - at).total_seconds()
    age = round(secs / 3600, 2)
    if secs < -FUTURE_SKEW_H * 3600:
        return {"status": "UNMEASURED", "stamp": at.isoformat(), "age_h": age,
                "why": f"`{key}` is {-age:g} h in the FUTURE; a future stamp measures nothing"}
    fresh = secs <= max_h * 3600
    return {"status": "FRESH" if fresh else "STALE", "stamp": at.isoformat(),
            "age_h": age, "why": "" if fresh else f"{age:g} h old against a {max_h:g} h cycle"}


def last_runs(log: Path, limit: int = 6) -> list[str]:
    """The newest `MT5-CostState step=... rc=...` lines the runner stamped, newest last."""
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.startswith("MT5-CostState step=")][-limit:]


def build(desk: Path = DESK, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    rows = []
    for rel, key, producer, max_h in ARTIFACTS:
        rows.append({"artifact": f"desks/mt5/{rel}", "producer": producer, "max_age_h": max_h,
                     **judge(desk / rel, key, max_h, now)})
    bad = [r["artifact"] for r in rows if r["status"] != "FRESH"]
    return {"schema": "cost_state_freshness/1", "generated_at": now.isoformat(timespec="seconds"),
            "status": "RED" if bad else "GREEN", "not_fresh": bad, "n_not_fresh": len(bad),
            "n_unmeasured": sum(1 for r in rows if r["status"] == "UNMEASURED"), "artifacts": rows,
            "runner_exits": last_runs(desk / LOG_REL)}


def main(argv: list[str] | None = None) -> int:
    rep = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    for r in rep["artifacts"]:
        print(f"  {r['status']:<10} {r['artifact']}  {r.get('age_h', '-')} h  {r['why']}")
    for ln in rep["runner_exits"]:
        print(f"  {ln}")
    print(f"cost state: {rep['status']} -> {OUT}")
    return 1 if rep["not_fresh"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
