#!/usr/bin/env python3
"""Relay the box's desk alerts as github-actions[bot], so the principal is actually notified.

WHY (2026-11-11, #1002 follow-up). The trading box comments its RED/recovery transitions on the
"Desk alerts" issue with its own GITHUB_TOKEN, and every box push is made as the repository
owner. GitHub never notifies an account of its own activity, so those comments are recorded and
notify nobody (`DESK_ALERTS.json` says RECORDED_NOT_NOTIFIED). A comment written by this
workflow's bot identity notifies everyone subscribed to the issue, the owner included, with no
new secret: the workflow's own GITHUB_TOKEN with `issues: write`.

It also catches what nothing on the box can: a box that is DEAD (or can no longer publish).
`BOX_HEARTBEAT.json` is rewritten every 5 minutes and published every 15; older than
`STALE_MIN` is one comment, and its return is one more.

WHAT IT READS, from a sparse checkout of the LIVE branch:
    desks/mt5/reports/DESK_ALERTS.json   its `outbox`: the box's transition messages, with ids
    desks/mt5/reports/BOX_HEARTBEAT.json its `at`: when the box last beat
Both absent (the box has not published them yet): a no-op, exit 0.

DEDUPE IS IN THE ISSUE ITSELF. Every relayed message and every dead-man change carries an HTML
marker (`<!-- desk-alerts-relay:outbox:<id> -->`, `<!-- desk-alerts-relay:deadman:STALE|FRESH
-->`); a run reads the issue's comments, relays only outbox ids not yet marked and younger than
`RELAY_WINDOW_H` (so a first run never replays history), and posts a dead-man comment only when
the state differs from the last marked one. All of a run's news is ONE comment; a quiet run posts
nothing. Transitions only: a box that stays dead is said once.

Never posts book, account or position state: the outbox bodies are the box's own allowlisted
text (libs/ops/desk_alerts.public_detail), and `@` is defused so a body can never ping anyone.
Stdlib only.

    GH_TOKEN=... python .github/scripts/desk_alerts_relay.py --repo owner/name [--root DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

API = "https://api.github.com"
ISSUE_TITLE = "Desk alerts"
ALERTS_REL = "desks/mt5/reports/DESK_ALERTS.json"
HEARTBEAT_REL = "desks/mt5/reports/BOX_HEARTBEAT.json"
#: The heartbeat is written every 5 min and published every 15 (MT5-ShadowSync); 90 minutes is
#: six missed publications, so a slow sync is never called a dead box.
STALE_MIN = 90.0
#: Outbox messages older than this are history, never relayed (a first run, or a long outage of
#: this workflow, must not replay a day of transitions).
RELAY_WINDOW_H = 6.0
RELAY_KINDS = ("RED", "RECOVERED", "ALL_CLEAR")
MAX_BODY = 60000
MARK = "desk-alerts-relay"
MARK_RX = re.compile(rf"<!-- {MARK}:(outbox|deadman):([A-Za-z0-9_.:+-]+) -->")

Call = Callable[[str, str, dict[str, Any] | None], tuple[int, Any]]


def http(token: str) -> Call:
    def call(method: str, path: str, payload: dict[str, Any] | None) -> tuple[int, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{API}/{path.lstrip('/')}", data=data, method=method,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "quant-desk-alerts-relay",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28",
                     **({"Content-Type": "application/json"} if data else {})})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
                return r.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as exc:
            return exc.code, None
    return call


def _load(p: Path) -> dict[str, Any] | None:
    try:
        d = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _ts(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def defuse(text: str) -> str:
    """No body relayed here can mention anyone or close the marker comment."""
    return str(text).replace("@", "@​").replace("-->", "--​>")[:MAX_BODY // 4]


def find_issue(call: Call, repo: str) -> dict[str, Any] | None:
    q = urllib.parse.quote(f'repo:{repo} is:issue in:title "{ISSUE_TITLE}"')
    st, res = call("GET", f"search/issues?q={q}&per_page=20", None)
    if st != 200 or not isinstance(res, dict):
        raise RuntimeError(f"issue search refused (http {st})")
    hits = [i for i in res.get("items") or [] if i.get("title") == ISSUE_TITLE]
    hits.sort(key=lambda i: (i.get("state") != "open", i.get("number") or 0))
    return hits[0] if hits else None


def comments(call: Call, repo: str, number: int, pages: int = 30) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        st, res = call("GET", f"repos/{repo}/issues/{number}/comments?per_page=100&page={page}",
                       None)
        if st != 200 or not isinstance(res, list):
            raise RuntimeError(f"comment listing refused (http {st})")
        out += res
        if len(res) < 100:
            break
    return out


def marks(cmts: list[dict[str, Any]]) -> tuple[set[str], str | None]:
    """(outbox ids already relayed, the last dead-man state marked), in comment order."""
    relayed: set[str] = set()
    dead: str | None = None
    for c in cmts:
        for kind, val in MARK_RX.findall(str(c.get("body") or "")):
            if kind == "outbox":
                relayed.add(val)
            else:
                dead = val
    return relayed, dead


def plan(alerts: dict[str, Any] | None, heartbeat: dict[str, Any] | None,
         relayed: set[str], last_dead: str | None, now: datetime) -> dict[str, Any]:
    """What this run must say. Pure."""
    pending: list[dict[str, Any]] = []
    for m in (alerts or {}).get("outbox") or []:
        if not isinstance(m, dict):
            continue
        mid, at = str(m.get("id") or ""), _ts(m.get("at"))
        if (not re.fullmatch(r"[A-Za-z0-9_.:+-]{1,64}", mid) or mid in relayed or at is None
                or now - at > timedelta(hours=RELAY_WINDOW_H) or m.get("kind") not in RELAY_KINDS):
            continue
        pending.append(m)
    pending.sort(key=lambda m: str(m.get("at")))
    dead: dict[str, Any] | None = None
    if heartbeat is not None:
        at = _ts(heartbeat.get("at"))
        age = None if at is None else (now - at).total_seconds() / 60.0
        state = "STALE" if age is None or age > STALE_MIN else "FRESH"
        if (state == "STALE" and last_dead != "STALE") or (state == "FRESH"
                                                           and last_dead == "STALE"):
            dead = {"state": state, "age_min": None if age is None else round(age),
                    "at": heartbeat.get("at")}
    return {"pending": pending, "deadman": dead}


def compose(p: dict[str, Any], now: datetime) -> str | None:
    parts: list[str] = []
    d = p["deadman"]
    if d:
        if d["state"] == "STALE":
            parts.append(f"**BOX SILENT**: the trading box's heartbeat was last published "
                         f"{d['at']} ({d['age_min']} min ago, line {STALE_MIN:.0f}). The box "
                         "is down, or it can no longer push its state.")
        else:
            parts.append(f"**BOX BACK**: the heartbeat is fresh again ({d['at']}).")
        parts.append(f"<!-- {MARK}:deadman:{d['state']} -->")
    for m in p["pending"]:
        parts.append(defuse(str(m.get("body") or m.get("kind"))))
        parts.append(f"<!-- {MARK}:outbox:{m['id']} -->")
    if not parts:
        return None
    parts.append(f"<sub>relayed by desk-alerts-relay {now.strftime('%Y-%m-%d %H:%M')} UTC; "
                 "transitions only.</sub>")
    return "\n\n".join(parts)[:MAX_BODY]


def run(call: Call, repo: str, root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    alerts, hb = _load(root / ALERTS_REL), _load(root / HEARTBEAT_REL)
    if alerts is None and hb is None:
        return {"action": "NOOP", "why": "neither report is published on this ref"}
    issue = find_issue(call, repo)
    relayed, last_dead = marks(comments(call, repo, issue["number"])) if issue else (set(), None)
    p = plan(alerts, hb, relayed, last_dead, now)
    body = compose(p, now)
    if body is None:
        return {"action": "QUIET", "issue": issue and issue.get("number")}
    if issue is None:
        owner = repo.split("/", 1)[0]
        st, res = call("POST", f"repos/{repo}/issues", {
            "title": ISSUE_TITLE,
            "body": (f"@{owner} the desk's alarm. RED and recovery transitions from the trading "
                     "box, and a dead box, are posted here; nothing else is.")})
        if st not in (200, 201) or not isinstance(res, dict):
            raise RuntimeError(f"issue create refused (http {st})")
        issue = res
    st, _ = call("POST", f"repos/{repo}/issues/{issue['number']}/comments", {"body": body})
    if st not in (200, 201):
        raise RuntimeError(f"comment refused (http {st})")
    return {"action": "POSTED", "issue": issue["number"],
            "relayed": [m["id"] for m in p["pending"]],
            "deadman": (p["deadman"] or {}).get("state")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--root", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        print("desk-alerts-relay: no GH_TOKEN", file=sys.stderr)
        return 1
    print(json.dumps(run(http(token), a.repo, a.root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
