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
    desks/mt5/data/release_identity.json the release the box runs (ADOPT LAG, below)
    desks/mt5/data/ADOPT_CLEARS.jsonl,
    desks/mt5/data/SEAL_CLEARS.jsonl     the box's vouch records (LEDGER, below)

ADOPT LAG AND LEDGER (zuck 2026-11-17, "this should never happen again"). On 11-14 one malformed
ADOPT_CLEARS row made the box's guard refuse every release for three days, and nothing paged:
the box's own lag check runs on the box's own (stuck) code. From GitHub's side, independent of
the box, this also says:
  * ADOPT LAG -- the oldest `release/*` tag the box has not adopted is older than ADOPT_LAG_H.
    Said again every RELAY_WINDOW_H while it lasts; its end is said once.
  * LEDGER BAD -- a row of either record that the box's line reader would refuse (not one JSON
    object on one line, or a row missing its commit/path and verdict). Said again every
    RELAY_WINDOW_H while any is there; its end is said once. The one row landed across 33 lines
    on 11-14 (LEGACY_MULTILINE) is known and read by the guard since #1216.
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
IDENTITY_REL = "desks/mt5/data/release_identity.json"
ADOPT_CLEARS_REL = "desks/mt5/data/ADOPT_CLEARS.jsonl"
SEAL_CLEARS_REL = "desks/mt5/data/SEAL_CLEARS.jsonl"
#: The box is lagging once a release it has not adopted is this old.
ADOPT_LAG_H = 6.0
#: Append-only means this row can never be rewritten; the guard reads it since #1216.
LEGACY_MULTILINE = frozenset({"e01e3e416c53fa2e52f8c72ccdae9eef995a33c8"})
TAG_RX = re.compile(r"^refs/tags/release/(\d{8}T\d{6}Z)-([0-9a-f]{7,40})$")
HEX40 = re.compile(r"[0-9a-f]{40}")
MAX_BODY = 60000
MARK = "desk-alerts-relay"
MARK_RX = re.compile(rf"<!-- {MARK}:(outbox|deadman|adoptlag|ledger):([A-Za-z0-9_.:+-]+) -->")

Call = Callable[[str, str, dict[str, Any] | None], tuple[int, Any]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is refused, never followed: urlopen would copy the bearer token to whatever
    host a 30x names (tests/data/test_keyed_fetch_fence.py). The API answers this call directly."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


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
            with _OPENER.open(req, timeout=30) as r:
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


def _text(p: Path) -> str | None:
    try:
        return p.read_text("utf-8")
    except (OSError, ValueError):
        return None


def defuse(text: str) -> str:
    """No body relayed here can mention anyone or close the marker comment."""
    return str(text).replace("@", "@\u200b").replace("-->", "--\u200b>")[:MAX_BODY // 4]


def find_issue(call: Call, repo: str) -> dict[str, Any] | None:
    q = urllib.parse.quote(f'repo:{repo} is:issue in:title "{ISSUE_TITLE}"')
    st, res = call("GET", f"search/issues?q={q}&per_page=20", None)
    if st != 200 or not isinstance(res, dict):
        raise RuntimeError(f"issue search refused (http {st})")
    hits = [i for i in res.get("items") or [] if i.get("title") == ISSUE_TITLE]
    hits.sort(key=lambda i: (i.get("state") != "open", i.get("number") or 0))
    return hits[0] if hits else None


#: The most comment pages one run reads (100 each): the scan is bounded whatever the issue's size.
MAX_PAGES = 10


def comments(call: Call, repo: str, number: int, total: int, now: datetime,
             max_pages: int = MAX_PAGES) -> list[dict[str, Any]]:
    """The issue's comments, NEWEST FIRST, back to the relay window (audit of #1024: reading
    oldest-first from page 1 stopped seeing the newest markers once an issue passed the page
    cap). The per-issue endpoint takes no sort/direction, so the pages are walked from the last
    one (the issue's own comment count) backwards. It stops at the first page that reaches past
    `RELAY_WINDOW_H` once a dead-man marker has been seen (the dead-man state may be older than
    the window), and never reads more than `max_pages`. Returned in chronological order."""
    floor = now - timedelta(hours=RELAY_WINDOW_H)
    last = max(1, -(-int(total or 0) // 100))
    got: list[list[dict[str, Any]]] = []
    seen_dead = False
    for page in range(last, max(0, last - max_pages), -1):
        st, res = call("GET", f"repos/{repo}/issues/{number}/comments?per_page=100&page={page}",
                       None)
        if st != 200 or not isinstance(res, list):
            raise RuntimeError(f"comment listing refused (http {st})")
        got.append(res)
        seen_dead = seen_dead or any(f"{MARK}:deadman:" in str(c.get("body") or "")
                                     for c in res)
        oldest = min((t for t in (_ts(c.get("created_at")) for c in res) if t), default=None)
        if seen_dead and (oldest is None or oldest < floor):
            break
    return [c for chunk in reversed(got) for c in chunk]


def marks(cmts: list[dict[str, Any]]) -> tuple[set[str], str | None]:
    """(outbox ids already relayed, the last dead-man state marked), in comment order."""
    relayed: set[str] = set()
    dead: str | None = None
    for c in cmts:
        for kind, val in MARK_RX.findall(str(c.get("body") or "")):
            if kind == "outbox":
                relayed.add(val)
            elif kind == "deadman":
                dead = val
    return relayed, dead


def said(cmts: list[dict[str, Any]], kind: str, now: datetime) -> tuple[str | None, bool]:
    """(the last `kind` state marked in the comments read, whether it was marked inside the
    relay window). Outside the window a bad state is said again: a reminder, not a replay."""
    last: str | None = None
    recent = False
    floor = now - timedelta(hours=RELAY_WINDOW_H)
    for c in cmts:
        for k, val in MARK_RX.findall(str(c.get("body") or "")):
            if k == kind:
                at = _ts(c.get("created_at"))
                last, recent = val, at is not None and at >= floor
    return last, recent


def ledger_faults(adopt_text: str | None, seal_text: str | None) -> list[str]:
    """Rows the box's line readers would refuse (pure). Never raises."""
    out: list[str] = []
    if adopt_text is not None:
        dec = json.JSONDecoder()
        i, end = 0, len(adopt_text)
        while i < end:
            while i < end and adopt_text[i] in " \t\r\n":
                i += 1
            if i >= end:
                break
            n = adopt_text.count("\n", 0, i) + 1
            try:
                d, j = dec.raw_decode(adopt_text, i)
            except ValueError:
                out.append(f"ADOPT_CLEARS.jsonl:{n} is not JSON")
                k = adopt_text.find("\n", i)
                i = end if k < 0 else k + 1
                continue
            one_line = "\n" not in adopt_text[i:j]
            ok = (isinstance(d, dict) and isinstance(d.get("commit"), str)
                  and HEX40.fullmatch(d["commit"]) is not None
                  and d.get("verdict") in ("CLEAR", "HOLD"))
            if not ok:
                out.append(f"ADOPT_CLEARS.jsonl:{n} is not a row (commit, verdict)")
            elif not one_line and d["commit"] not in LEGACY_MULTILINE:
                out.append(f"ADOPT_CLEARS.jsonl:{n} spans several lines")
            i = j
    for n, line in enumerate((seal_text or "").splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            out.append(f"SEAL_CLEARS.jsonl:{n} is not JSON")
            continue
        if not (isinstance(d, dict) and isinstance(d.get("path"), str) and d.get("path")
                and d.get("verdict") in ("CLEAR", "HOLD")):
            out.append(f"SEAL_CLEARS.jsonl:{n} is not a row (path, verdict)")
    return out


def adopt_lag(identity: dict[str, Any] | None, refs: list[str], now: datetime
              ) -> dict[str, Any] | None:
    """{hours, oldest, running} for the oldest release tag newer than the one the box runs, or
    None when that cannot be measured (pure). A tag names its commit by prefix."""
    if not identity:
        return None
    running = str(identity.get("release_sha") or "")
    if not HEX40.fullmatch(running):
        return None
    tags = sorted((m.group(1), m.group(2)) for r in refs if (m := TAG_RX.match(str(r))))
    if not tags:
        return None
    mine = [ts for ts, sha in tags if running.startswith(sha)]
    newer = [(ts, sha) for ts, sha in tags if not mine or ts > max(mine)]
    newer = [(ts, sha) for ts, sha in newer if not running.startswith(sha)]
    if not newer:
        return {"hours": 0.0, "oldest": None, "running": running[:12]}
    ts, sha = newer[0]
    at = datetime.strptime(ts, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    return {"hours": round((now - at).total_seconds() / 3600.0, 1),
            "oldest": f"release/{ts}-{sha}", "running": running[:12]}


def watch(lag: dict[str, Any] | None, faults: list[str],
          lag_said: tuple[str | None, bool], ledger_said: tuple[str | None, bool]
          ) -> dict[str, Any]:
    """What to say about adoption lag and the ledgers this run (pure)."""
    out: dict[str, Any] = {}
    if lag is not None:
        bad = lag["hours"] > ADOPT_LAG_H
        last, recent = lag_said
        if bad and not (last == "LAGGING" and recent):
            out["adoptlag"] = {"state": "LAGGING", **lag}
        elif not bad and last == "LAGGING":
            out["adoptlag"] = {"state": "CURRENT", **lag}
    last, recent = ledger_said
    if faults and not (last == "BAD" and recent):
        out["ledger"] = {"state": "BAD", "faults": faults}
    elif not faults and last == "BAD":
        out["ledger"] = {"state": "OK", "faults": []}
    return out


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
    w = p.get("watch") or {}
    lag = w.get("adoptlag")
    if lag:
        if lag["state"] == "LAGGING":
            parts.append(f"**BOX NOT ADOPTING**: the box still runs release {lag['running']}, and "
                         f"{lag['oldest']} has waited {lag['hours']} h (line {ADOPT_LAG_H:.0f} h). "
                         "Its adopt task is refusing or not running.")
        else:
            parts.append(f"**BOX ADOPTING AGAIN**: it runs release {lag['running']}.")
        parts.append(f"<!-- {MARK}:adoptlag:{lag['state']} -->")
    led = w.get("ledger")
    if led:
        if led["state"] == "BAD":
            shown = "; ".join(defuse(f) for f in led["faults"][:10])
            parts.append(f"**LEDGER ROW THE BOX CANNOT READ**: {shown}. Fix it with a new "
                         "well-formed row; never edit the append-only record.")
        else:
            parts.append("**LEDGERS READABLE AGAIN**.")
        parts.append(f"<!-- {MARK}:ledger:{led['state']} -->")
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


REF_PAGE = 100
REF_PAGES_MAX = 200


def release_refs(call: Call, repo: str) -> list[str] | None:
    """Every refs/tags/release/* name, or None when the full list cannot be read. The endpoint
    pages (30 a page by default) and the repo has thousands of release tags, so reading only
    the first page would miss the running release and page a false lag forever."""
    out: list[str] = []
    for page in range(1, REF_PAGES_MAX + 1):
        st, res = call("GET", f"repos/{repo}/git/matching-refs/tags/release/"
                              f"?per_page={REF_PAGE}&page={page}", None)
        if st != 200 or not isinstance(res, list):
            return None
        out += [str(r.get("ref")) for r in res if isinstance(r, dict)]
        if len(res) < REF_PAGE:
            return out
    return None


def run(call: Call, repo: str, root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    alerts, hb = _load(root / ALERTS_REL), _load(root / HEARTBEAT_REL)
    identity = _load(root / IDENTITY_REL)
    adopt_text, seal_text = _text(root / ADOPT_CLEARS_REL), _text(root / SEAL_CLEARS_REL)
    if alerts is None and hb is None and identity is None and adopt_text is None \
            and seal_text is None:
        return {"action": "NOOP", "why": "neither report is published on this ref"}
    issue = find_issue(call, repo)
    cmts = (comments(call, repo, issue["number"], int(issue.get("comments") or 0), now)
            if issue else [])
    relayed, last_dead = marks(cmts)
    p = plan(alerts, hb, relayed, last_dead, now)
    lag = None
    if identity is not None:
        refs = release_refs(call, repo)
        lag = None if refs is None else adopt_lag(identity, refs, now)
    p["watch"] = watch(lag, ledger_faults(adopt_text, seal_text), said(cmts, "adoptlag", now),
                       said(cmts, "ledger", now))
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
            "deadman": (p["deadman"] or {}).get("state"),
            **{k: v["state"] for k, v in p["watch"].items()}}


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
