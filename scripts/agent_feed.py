#!/usr/bin/env python3
"""
Shared Agent Feed - the single source of truth for ALL agents (BRAIN #3, Claude, Codex, etc.)

Every finding, defect, survivor, data axis, hypothesis, fix, calibration, governance event
is appended here. All agents read this to know the current state without duplication.

    python scripts/agent_feed.py write --type finding --title "..." --payload '{"k": "v"}'
    python scripts/agent_feed.py read --since "2h" --type finding
    python scripts/agent_feed.py tail --lines 50
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

FEED_DIR = Path("data/agent_feed")
FEED_DIR.mkdir(parents=True, exist_ok=True)
INDEX = FEED_DIR / "index.jsonl"
BY_TYPE = FEED_DIR / "by_type"
BY_TYPE.mkdir(parents=True, exist_ok=True)
BY_AGENT = FEED_DIR / "by_agent"
BY_AGENT.mkdir(parents=True, exist_ok=True)

AGENT_ID = os.getenv("AGENT_ID", "brain3")


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def write_entry(
    *,
    type_: str,
    title: str,
    payload: dict[str, Any],
    agent: str = AGENT_ID,
    tags: list[str] | None = None,
    priority: str = "normal",  # low, normal, high, critical
    related: list[str] | None = None,  # other entry IDs
) -> str:
    """Append an entry to the shared feed."""
    entry_id = str(uuid.uuid4())[:8]
    now = _now_iso()
    entry = {
        "id": entry_id,
        "timestamp": now,
        "agent": agent,
        "type": type_,
        "title": title,
        "payload": payload,
        "tags": tags or [],
        "priority": priority,
        "related": related or [],
    }
    # Main index
    with INDEX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    # By type
    (BY_TYPE / f"{type_}.jsonl").open("a", encoding="utf-8").write(json.dumps(entry, default=str) + "\n")
    # By agent
    (BY_AGENT / f"{agent}.jsonl").open("a", encoding="utf-8").write(json.dumps(entry, default=str) + "\n")
    return entry_id


def read_entries(
    *,
    since: str | None = None,
    type_: str | None = None,
    agent: str | None = None,
    priority: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Read entries with filters."""
    cutoff = None
    if since:
        try:
            h = int(since.rstrip("h"))
            cutoff = datetime.now(tz=UTC) - timedelta(hours=h)
        except ValueError:
            cutoff = datetime.fromisoformat(since.replace("Z", "+00:00"))

    path = BY_TYPE / f"{type_}.jsonl" if type_ else INDEX
    if not path.exists():
        return []

    entries = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if cutoff and datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")) < cutoff:
                continue
            if agent and e.get("agent") != agent:
                continue
            if priority and e.get("priority") != priority:
                continue
            entries.append(e)
    return entries[-limit:]


def tail_entries(n: int = 50) -> list[dict]:
    """Last N entries from main index."""
    if not INDEX.exists():
        return []
    with INDEX.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[-n:]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Shared Agent Feed")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write", help="Write an entry")
    p_write.add_argument("--type", required=True, choices=[
        "finding", "defect", "survivor", "data_axis", "hypothesis", "fix", "calibration",
        "governance", "law_fence", "blind_spot", "capability", "mechanism", "promotion",
        "x_signal", "horizon", "miner_output", "screen", "paper_sleeve", "forward_clock",
    ])
    p_write.add_argument("--title", required=True)
    p_write.add_argument("--payload", type=json.loads, default="{}")
    p_write.add_argument("--agent", default=AGENT_ID)
    p_write.add_argument("--tags", default="")
    p_write.add_argument("--priority", default="normal", choices=["low", "normal", "high", "critical"])
    p_write.add_argument("--related", default="")

    p_read = sub.add_parser("read", help="Read entries")
    p_read.add_argument("--since", default="24h")
    p_read.add_argument("--type")
    p_read.add_argument("--agent")
    p_read.add_argument("--priority")
    p_read.add_argument("--limit", type=int, default=100)

    p_tail = sub.add_parser("tail", help="Tail last N entries")
    p_tail.add_argument("-n", type=int, default=50)

    args = parser.parse_args()

    if args.cmd == "write":
        eid = write_entry(
            type_=args.type,
            title=args.title,
            payload=args.payload,
            agent=args.agent,
            tags=args.tags.split(",") if args.tags else [],
            priority=args.priority,
            related=args.related.split(",") if args.related else [],
        )
        print(f"Written: {eid}")
    elif args.cmd == "read":
        entries = read_entries(
            since=args.since,
            type_=args.type,
            agent=args.agent,
            priority=args.priority,
            limit=args.limit,
        )
        for e in entries:
            print(json.dumps(e, default=str))
    elif args.cmd == "tail":
        for e in tail_entries(args.n):
            print(json.dumps(e, default=str))


if __name__ == "__main__":
    main()