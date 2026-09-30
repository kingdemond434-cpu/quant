#!/usr/bin/env python3
"""Are the box's three infrastructure tasks actually REGISTERED and firing? Read-only fence.

    python scripts/check_box_infra.py [--json]

WHY (audit of PR #124, 2026-09-30). MT5-BoxHeartbeat, MT5-OffsiteBackup and MT5-PrivateNetAudit
arrived with installers and manifest lines, and the runtime attestation read all three NEVER:
code in the repo is not a task on the box, and nothing said so. A task that was never
registered is indistinguishable, from git, from one that runs -- until the day the box dies and
the alarm that was supposed to page someone turns out never to have existed.

WHAT IT CHECKS. Each task writes one artifact every run, whether or not its credential is armed
(NOT_ARMED is a recorded state, and still proves the task fired). A missing artifact is NEVER
(the installer was not run); one older than twice its cadence is STALE (registered, not firing).
Either turns this fence red ON THE TRADING BOX. On any other host the artifacts cannot exist,
so the verdict is UNMEASURED and the exit is 0 -- this is not evidence either way (L1.28a).

INSTALL (on the box, once): the three installers named in each row's `install`.
Writes desks/mt5/reports/BOX_INFRA.json on the box.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "BOX_INFRA.json"

#: task, artifact, cadence (s), installer
TASKS: tuple[tuple[str, Path, int, str], ...] = (
    ("MT5-BoxHeartbeat", DESK / "reports" / "BOX_HEARTBEAT.json", 300,
     "desks/mt5/scripts/install_box_heartbeat_task.ps1"),
    ("MT5-OffsiteBackup", DESK / "reports" / "OFFSITE_BACKUP.json", 6 * 3600,
     "desks/mt5/scripts/install_offsite_backup_task.ps1"),
    ("MT5-PrivateNetAudit", DESK / "data" / "private_net.json", 86_400,
     "desks/mt5/scripts/install_private_net_audit_task.ps1"),
)


def on_trading_box() -> bool:
    """The trading box is the Windows host that runs the terminal; nothing else writes these."""
    return os.name == "nt" and (DESK / "data" / "sleeves.json").exists()


def measure(now: float | None = None, tasks: tuple[tuple[str, Path, int, str], ...] = TASKS,
            ) -> dict[str, Any]:
    t = now if now is not None else time.time()
    rows = []
    for name, art, cadence, installer in tasks:
        try:
            age = t - art.stat().st_mtime
        except OSError:
            age = None
        state = ("NEVER" if age is None else "STALE" if age > 2 * cadence else "REGISTERED")
        armed = None
        if age is not None:
            try:
                doc = json.loads(art.read_text("utf-8"))
                armed = ((doc.get("ping") or {}).get("status") if "ping" in doc
                         else doc.get("status") or doc.get("verdict"))
            except (OSError, ValueError, AttributeError):
                armed = "UNREADABLE"
        rel = art.relative_to(ROOT) if art.is_relative_to(ROOT) else art
        rows.append({"task": name, "artifact": str(rel), "state": state,
                     "age_s": None if age is None else round(age), "max_age_s": 2 * cadence,
                     "reported": armed, "install": installer})
    bad = [r["task"] for r in rows if r["state"] != "REGISTERED"]
    return {"at": datetime.fromtimestamp(t, tz=UTC).isoformat(timespec="seconds"),
            "tasks": rows, "not_registered": bad,
            "verdict": "FAIL" if bad else "PASS"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not on_trading_box():
        doc = {"verdict": "UNMEASURED",
               "why": "not the trading box: the three task artifacts only exist there"}
        print(json.dumps(doc) if a.json else f"box infra: {doc['verdict']} -- {doc['why']}")
        return 0
    doc = measure()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    if a.json:
        print(json.dumps(doc))
    else:
        print(f"box infra: {doc['verdict']}")
        for r in doc["tasks"]:
            print(f"  {r['state']:<10} {r['task']:<20} reported={r['reported']}"
                  + (f"  -> run {r['install']}" if r["state"] == "NEVER" else ""))
    return 1 if doc["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
