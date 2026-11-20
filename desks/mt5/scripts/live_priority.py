"""LIVE TRADING RUNS ABOVE EVERYTHING ELSE ON THE BOX (coordinator for zuck, 2026-11-20 13:54Z).

THE DEFECT. The MT5 terminals were measured at BELOW_NORMAL, the miners' class, and the E8/FTMO
executors are registered at NORMAL. So the processes that place and manage real orders competed
for CPU on equal terms with ~100 research processes, and the judge could never be given its
reserved cores, because the judge is never allowed above an observed live process
(judge_priority.judge_target, Audit MF-1 of 40ff5587cc).

THE RULE THIS ORGAN KEEPS, every minute, whoever launched the process (a scheduled task, a
watchdog, an RDP click):

    live (terminal64.exe and the live scripts judge_priority classifies as live, with every
    child they spawn) runs at ABOVE_NORMAL.

It ONLY RAISES a live process that sits below ABOVE_NORMAL, and never past ABOVE_NORMAL (no
HIGH, no REALTIME). It never lowers anything and never touches a process that is not live. A
pid is changed only if it is still the process the census saw (start time and command line
re-read: judge_priority._default_setter). AccessDenied is reported, not retried around.

So the box's order is live (ABOVE_NORMAL) > judge on its reserved cores (NORMAL) > miners
(BELOW_NORMAL).

REVERT without a push: data/LIVE_PRIORITY.json = {"enabled": false}. The organ then changes
nothing; a raised process keeps its class until it restarts.

    python scripts/live_priority.py            # census + raise, writes reports/LIVE_PRIORITY.json
    python scripts/live_priority.py --dry-run  # census only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from scripts import judge_priority as jp  # noqa: E402

SWITCH = DESK / "data" / "LIVE_PRIORITY.json"
REPORT = DESK / "reports" / "LIVE_PRIORITY.json"
TARGET_RANK = jp.CLASS_RANK[jp.ABOVE_NORMAL]


def enabled(path: Path | None = None) -> dict[str, Any]:
    """On by default; only an explicit {"enabled": false} turns it off. Malformed reads as on,
    because the off state is the defect this organ exists to remove."""
    p = path or SWITCH
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return {"enabled": True, "why": f"{p.name} absent or unreadable: default on"}
    if isinstance(doc, dict) and doc.get("enabled") is False:
        return {"enabled": False, "why": f"{p.name} says enabled=false"}
    return {"enabled": True, "why": f"{p.name} present, not disabled"}


def plan(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every live row and what to do with it. Pure: no process is read or changed here."""
    out = []
    for r in jp.classify(rows):
        if r.get("cls") != "live":
            continue
        rank = r.get("rank")
        if not isinstance(rank, int):
            action = "unreadable"
        elif rank < TARGET_RANK:
            action = "raise"
        else:
            action = "keep"  # at or above ABOVE_NORMAL: never lowered
        out.append({
            "pid": r.get("pid"),
            "name": r.get("name"),
            "command": jp._short(r.get("cmdline") or []),
            "from": jp.RANK_NAME.get(rank) if isinstance(rank, int) else None,
            "action": action,
            "_row": r,
        })
    return out


def apply(items: list[dict[str, Any]], setter: Any = None) -> list[dict[str, Any]]:
    """Raise every `raise` item to ABOVE_NORMAL. Never anything else."""
    setter = setter or jp._default_setter
    target = jp.RANK_CLASS[TARGET_RANK]
    done = []
    for it in items:
        row = it.pop("_row", {})
        if it["action"] != "raise":
            done.append(it)
            continue
        try:
            setter(int(it["pid"]), target, row)
            done.append({**it, "to": jp.RANK_NAME[TARGET_RANK], "applied": True})
        except Exception as exc:  # AccessDenied, a vanished pid, a reused pid
            done.append({**it, "applied": False, "error": f"{type(exc).__name__}: {exc}"})
    return done


def summarise(items: list[dict[str, Any]]) -> dict[str, Any]:
    raised = [i for i in items if i.get("applied")]
    failed = [i for i in items if i["action"] == "raise" and not i.get("applied")]
    kept = [i for i in items if i["action"] == "keep"]
    unreadable = [i for i in items if i["action"] == "unreadable"]
    if not items:
        verdict = jp.UNMEASURED  # no live process seen: nothing proven either way
    elif failed or unreadable:
        verdict = "PARTIAL"
    else:
        verdict = "OK"
    return {"verdict": verdict, "live_processes": len(items), "raised": len(raised),
            "already_at_or_above": len(kept), "failed": len(failed),
            "unreadable": len(unreadable)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="census only; change nothing")
    ap.add_argument("--no-write", action="store_true", help="print only; write no report")
    a = ap.parse_args(argv)
    sw = enabled()
    items = plan(jp.snapshot(0.0))
    if a.dry_run or not sw["enabled"]:
        for it in items:
            it.pop("_row", None)
        done = items
    else:
        done = apply(items)
    doc = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": os.environ.get("COMPUTERNAME") or "",
        "mode": "dry-run" if a.dry_run else ("disabled" if not sw["enabled"] else "apply"),
        "switch": sw,
        "target": jp.RANK_NAME[TARGET_RANK],
        **summarise(done),
        "processes": done,
        "rule": ("live (terminal64 + live scripts + their children) runs at ABOVE_NORMAL; "
                 "raise only, never past ABOVE_NORMAL, never lower, never touch non-live"),
    }
    print(json.dumps({k: v for k, v in doc.items() if k != "processes"}, indent=1))
    if not a.no_write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        tmp = REPORT.with_name(f"{REPORT.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
