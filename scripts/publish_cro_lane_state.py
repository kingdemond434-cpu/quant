#!/usr/bin/env python3
"""THE NOON LANE'S OWN STATE, PUBLISHED: its checkpoint and the tail of its log, scrubbed.

    python scripts/publish_cro_lane_state.py [--lane noon] [--tail 80] [--out <json>]

Clock: hourly leg `cro_lane_state` (desks/mt5/research/hourly_cycle.py, meta), run just before
`cro_noon_freshness`, which reads this file. Artifact: desks/mt5/reports/CRO_NOON_STATE.json,
carried to origin by sync_shadow_to_git.ps1's $reportPaths.

WHY (backlog finding K6, 2026-11-17). `Run-DeskCycle.ps1 -Lane noon` writes its checkpoint to
desks/mt5/data/cycle_state_noon.json and its log to desks/mt5/logs/cycle_noon.log, and neither
ever left the box: the lane exited 5 on 11-13 (lease not acquired) and 1 on 11-17, and no cloud
session could see either. An early exit writes no ledger row at all, so the only trace was a log
line on a machine nobody outside it reads. This leg copies the checkpoint and the last N log
lines into a report the box's state sync already publishes. It runs from the hourly cycle rather
than from the launcher because the launcher's early exits (2, 3, 4, 5) end before any step that
could publish.

WHAT IS PUBLISHED, AND WHAT IS NOT. The checkpoint's fields except `pid`, and at most `--tail`
log lines. Every string passes the desk's two publish scrubbers -- `agent_denials.scrub` (key-
shaped substrings, the secrets path) and `account_withhold.public_text` (money figures,
server/login/host values, addresses, host names) -- and then a path scrub (drive and home paths,
box host names), so no key, account figure, host or local path crosses the wire. A key whose name
is money- or host-shaped is withheld by name. Nothing here reads data/secrets.

THE LAST EXIT IS READ, NEVER ASSUMED (L1.28a). The launcher writes `launcher exit rc=N` before
every early exit and `cycle end rc=N` after the agent, so the newest such line is the lane's last
exit code. With no such line the checkpoint's `last_exit` is used; with neither, `last_rc` is
null and the verdict is UNMEASURED, never OK. An absent checkpoint and an absent log are ABSENT.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.account_withhold import public_text  # noqa: E402
from libs.ops.agent_denials import scrub as scrub_keys  # noqa: E402
from libs.ops.win_write import write_text_resilient  # noqa: E402

DESK = ROOT / "desks" / "mt5"
TAIL_LINES = 80
#: Read at most this much of the log's end: the log only grows, and the tail is all we publish.
TAIL_BYTES = 256 * 1024
#: A published string is cut here, after scrubbing (a scrub must see the whole string).
TEXT_CAP = 2000
#: Checkpoint keys never published: the process id is a host fact, not a lane fact.
DROP_KEYS = frozenset({"pid"})

_RC = re.compile(r"^(?P<at>\S+)\s+\[\w+\]\s+(?:launcher exit|cycle end) rc=(?P<rc>-?\d+)")
_DRIVE_PATH = re.compile(r"(?i)\b[A-Z]:\\[^\s\"'|<>]*")
_UNC_PATH = re.compile(r"\\\\[^\s\"'|<>]+")
_POSIX_HOME = re.compile(r"(?<![\w.])/(?:home|Users|root|mnt|opt|var|tmp|srv)/[^\s\"'|<>]*")
_BOX_HOST = re.compile(r"(?i)\b(?:vmi\d+|ubuntu-[\w-]+|WIN-[A-Z0-9]+)\b")
_MONEY_KEY = re.compile(r"(?i)(?:^|_)(balance|equity|margin|free_margin|profit|pnl|nav)$")
_HOST_KEY = re.compile(r"(?i)(?:^|_)(server|login|host|hostname|account)$")


def clean_text(text: str, cap: int = TEXT_CAP) -> str:
    """One published string: keys, money, hosts and local paths out, then capped."""
    s = scrub_keys(text)
    s = public_text(s)
    s = _DRIVE_PATH.sub("<path>", s)
    s = _UNC_PATH.sub("<path>", s)
    s = _POSIX_HOME.sub("<path>", s)
    s = _BOX_HOST.sub("<host>", s)
    return s if len(s) <= cap else s[: cap - 3] + "..."


def clean(node: Any) -> Any:
    if isinstance(node, str):
        return clean_text(node)
    if isinstance(node, list):
        return [clean(v) for v in node]
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            key = str(k)
            if key in DROP_KEYS:
                continue
            if v is not None and not isinstance(v, (dict, list, bool)) and (
                    _MONEY_KEY.search(key) or _HOST_KEY.search(key)):
                out[key] = "[withheld]"
            else:
                out[key] = clean(v)
        return out
    return node


def read_state(path: Path) -> tuple[str, dict[str, Any] | None]:
    if not path.exists():
        return "ABSENT", None
    try:
        # utf-8-sig: PowerShell 5.1's Set-Content -Encoding UTF8 writes a BOM.
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return "UNREADABLE", None
    return ("PRESENT", doc) if isinstance(doc, dict) else ("UNREADABLE", None)


def read_tail(path: Path, n: int) -> tuple[str, list[str]]:
    if not path.exists():
        return "ABSENT", []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            raw = fh.read()
    except OSError:
        return "UNREADABLE", []
    # Add-Content on PS 5.1 writes the system code page; replace what is not UTF-8.
    lines = [ln.rstrip("\r") for ln in raw.decode("utf-8", errors="replace").split("\n")]
    if size > TAIL_BYTES and lines:
        lines = lines[1:]  # the first line was cut mid-way by the seek
    lines = [ln for ln in lines if ln.strip()]
    return "PRESENT", lines[-n:] if n > 0 else []


def last_exit(lines: list[str], state: dict[str, Any] | None) -> tuple[int | None, str | None, str]:
    """(rc, when, where it was read): the newest launcher rc line, else the checkpoint."""
    for ln in reversed(lines):
        m = _RC.match(ln)
        if m:
            return int(m.group("rc")), m.group("at"), "log"
    if state is not None:
        rc = state.get("last_exit")
        if isinstance(rc, int) and not isinstance(rc, bool):
            return rc, state.get("started_at"), "state.last_exit"
        if state.get("status") == "DONE":
            return 0, state.get("finished_at"), "state.status"
    return None, None, "none"


def build(lane: str, state_path: Path, log_path: Path, tail: int, now: datetime) -> dict[str, Any]:
    state_status, state = read_state(state_path)
    log_status, all_lines = read_tail(log_path, max(tail, 0) or 1)
    # The rc is read from the whole read window, not only the published tail.
    _, window = read_tail(log_path, 10_000)
    rc, rc_at, rc_from = last_exit(window, state)
    if rc is None:
        verdict, why = "UNMEASURED", "no launcher exit line in the log and no exit in the checkpoint"
    elif rc == 0:
        verdict, why = "OK", f"last {lane} launch exited 0 ({rc_from})"
    else:
        verdict, why = "FAILED", f"last {lane} launch exited rc={rc} ({rc_from})"
    return {
        "at": now.isoformat(), "lane": lane,
        "source": {"state": f"desks/mt5/data/{state_path.name}",
                   "log": f"desks/mt5/logs/{log_path.name}"},
        "state_status": state_status, "state": clean(state) if state is not None else None,
        "log_status": log_status, "log_tail_lines": len(all_lines) if tail > 0 else 0,
        "log_tail": [clean_text(ln, 500) for ln in all_lines] if tail > 0 else [],
        "last_rc": rc, "last_rc_at": clean_text(rc_at) if isinstance(rc_at, str) else None,
        "last_rc_from": rc_from, "verdict": verdict, "why": why,
        "scrubbed_by": ["libs.ops.agent_denials.scrub", "libs.ops.account_withhold.public_text",
                        "local paths and box host names"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lane", choices=("noon", "midnight"), default="noon")
    ap.add_argument("--tail", type=int, default=TAIL_LINES)
    ap.add_argument("--state", type=Path)
    ap.add_argument("--log", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    state = a.state or DESK / "data" / f"cycle_state_{a.lane}.json"
    log = a.log or DESK / "logs" / f"cycle_{a.lane}.log"
    out = a.out or DESK / "reports" / f"CRO_{a.lane.upper()}_STATE.json"
    doc = build(a.lane, state, log, a.tail, datetime.now(UTC))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_text_resilient(out, json.dumps(doc, indent=1) + "\n")
    print(json.dumps({"lane": a.lane, "verdict": doc["verdict"], "last_rc": doc["last_rc"],
                      "state": doc["state_status"], "log": doc["log_status"]}))
    # A FAILED lane is the reading, not this leg's failure: the freshness check turns it RED.
    return 0


if __name__ == "__main__":
    sys.exit(main())
