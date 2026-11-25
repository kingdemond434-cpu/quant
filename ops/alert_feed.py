"""BOX ALERTS GO TO CLAUDE, NOT TO A PHONE (principal 2026-11-20, restated 2026-11-25 01:50Z).

THE DEFECT. Every box pager (run_alerts, page_digest, the deadman, the plumbing pager, the
model-upgrade notice) posts to the one ntfy.sh topic in data/secrets/ntfy.json, and the only
subscriber to that topic was the principal's phone. Nothing Claude reads ever saw a page.

WHAT THIS DOES. Every 5 minutes it reads the topic back (ntfy's own poll API, the same call
run_alerts._poll_replies already makes) and appends each new message, one JSON line each, to
desks/mt5/reports/alerts/CLAUDE_ALERT_FEED.jsonl. The box-state sync publishes that file, the
health board and the hourly pass read it, and every new line is a fault to route. The senders
are untouched: rotating the topic (a box config step, no code) takes the phone off without
losing a single page, because this reader follows whatever topic the file names.

WHAT IT WILL NOT DO. It never posts, never acks, never prints or stores the topic, and never
raises into a caller: a failed poll is a recorded state in the feed's status file, not silence.

    python ops/alert_feed.py            # one poll
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SECRETS = (ROOT / "data" / "secrets" / "ntfy.json",
           ROOT / "desks" / "mt5" / "data" / "secrets" / "ntfy.json")
FEED = ROOT / "desks" / "mt5" / "reports" / "alerts" / "CLAUDE_ALERT_FEED.jsonl"
STATUS = ROOT / "desks" / "mt5" / "reports" / "alerts" / "CLAUDE_ALERT_FEED_STATUS.json"
CURSOR = ROOT / "data" / ".alert_feed_cursor.json"
#: First poll with no cursor reaches back this far (ntfy keeps 12h of messages).
FIRST_SINCE = "12h"
#: THE PUBLIC WIRE CARRIES NO BODIES (Audit MF1, 2026-11-25). The feed is published by the
#: box-state sync to a public origin, and page text carries money figures (daily loss, equity),
#: hosts and human replies. So the feed row holds structured fields only (id, at, priority,
#: tags, kind, title_class: the title's plain words with every number, host, URL and email
#: removed), and the full title/body go to BODIES, a box-local file under data/ that no sync
#: path names. A reader on the box joins the two by id.
BODIES = ROOT / "data" / "alert_feed_bodies.jsonl"
BODY_MAX = 400
#: The feed and the bodies file keep their last FEED_KEEP rows. The trim is not a loss of
#: evidence: every published feed revision stays in the box-state sync's git history, and the
#: pages themselves stay with their senders' own logs.
FEED_KEEP = 2000
_WORD = re.compile(r"[A-Za-z]{2,}")
_DROP = re.compile(r"\S*(?:@|://|\d|\.[A-Za-z])\S*")
TIMEOUT_S = 20.0
#: INVARIANT I5 (principal 2026-11-25 01:55Z, PERMANENT: every box alert reaches Claude). An
#: alert counts as ROUTED only once the box-state publish that carries the feed has landed after
#: it (BOX_STATE_FLOW.last_published_at); written to the feed alone is not routed, because a feed
#: nobody can fetch is the phone-only defect again.
ROUTING = ROOT / "desks" / "mt5" / "reports" / "ALERT_ROUTING.json"
FLOW = ROOT / "desks" / "mt5" / "reports" / "BOX_STATE_FLOW.json"
EVENTS = ROOT / "desks" / "mt5" / "data" / "events.jsonl"
ROUTING_WINDOW_H = 24.0


def _topic() -> str | None:
    for p in SECRETS:
        with contextlib.suppress(OSError, ValueError):
            t = json.loads(p.read_text("utf-8-sig")).get("topic")
            if isinstance(t, str) and t.strip():
                return t.strip()
    return None


def _fetch(topic: str, since: str) -> list[dict[str, Any]]:
    url = f"https://ntfy.sh/{topic}/json?poll=1&since={since}"
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
        lines = resp.read().decode("utf-8", "replace").splitlines()
    out = []
    for ln in lines:
        with contextlib.suppress(ValueError):
            m = json.loads(ln)
            if isinstance(m, dict) and m.get("event") == "message":
                out.append(m)
    return out


def title_class(text: str) -> str:
    """The plain words of a title: any token carrying a digit, a host/URL or an email is gone,
    so no amount, account, IP or host can reach the public wire."""
    kept = _DROP.sub(" ", str(text or ""))
    return " ".join(_WORD.findall(kept)).lower()[:80]


def _tags(raw: Any) -> list[str]:
    return [t for t in (title_class(str(x)) for x in (raw if isinstance(raw, list) else [])) if t]


def _row(m: dict[str, Any]) -> dict[str, Any]:
    """The PUBLIC feed row: structured fields only, never a body (Audit MF1)."""
    t = m.get("time")
    at = datetime.fromtimestamp(t, tz=UTC).isoformat() if isinstance(t, int | float) else None
    return {"id": str(m.get("id") or ""), "at": at,
            "title_class": title_class(str(m.get("title") or "")),
            "priority": m.get("priority") if isinstance(m.get("priority"), int) else None,
            "tags": _tags(m.get("tags")),
            # a titled message is a desk page; an untitled one is a human reply (run_alerts)
            "kind": "page" if m.get("title") else "reply"}


def _body(m: dict[str, Any]) -> dict[str, Any]:
    """The BOX-LOCAL row: the full title and body, joined to the feed by id."""
    return {"id": str(m.get("id") or ""), "title": str(m.get("title") or "")[:200],
            "message": str(m.get("message") or "")[:BODY_MAX]}


def _write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, p)


def poll(*, fetch: Any = None, topic: str | None = None, now: datetime | None = None,
         feed: Path = FEED, status: Path = STATUS, cursor: Path = CURSOR,
         bodies: Path = BODIES) -> dict[str, Any]:
    t_now = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    topic = topic if topic is not None else _topic()
    st: dict[str, Any] = {"at": t_now, "ok": False, "new": 0}
    if not topic:
        st["why"] = "NOT ARMED: no ntfy topic in data/secrets/ntfy.json (nothing to read back)"
        with contextlib.suppress(OSError):
            _write_atomic(status, json.dumps(st, indent=1) + "\n")
        return st
    cur: dict[str, Any] = {}
    with contextlib.suppress(OSError, ValueError):
        cur = json.loads(cursor.read_text("utf-8"))
    since = str(cur.get("last_id") or FIRST_SINCE)
    try:
        msgs = (fetch or _fetch)(topic, since)
    except Exception as exc:
        st["why"] = f"poll failed: {type(exc).__name__}"
        with contextlib.suppress(OSError):
            _write_atomic(status, json.dumps(st, indent=1) + "\n")
        return st
    seen: set[str] = set()
    old: list[str] = []
    with contextlib.suppress(OSError):
        old = feed.read_text("utf-8").splitlines()
    for ln in old[-FEED_KEEP:]:
        with contextlib.suppress(ValueError):
            seen.add(str(json.loads(ln).get("id")))
    fresh = [m for m in msgs if str(m.get("id") or "") not in seen]
    new = [_row(m) for m in fresh]
    if new:
        old_b: list[str] = []
        with contextlib.suppress(OSError):
            old_b = bodies.read_text("utf-8").splitlines()
        kept_b = old_b[-max(0, FEED_KEEP - len(fresh)):] + [
            json.dumps(_body(m), separators=(",", ":")) for m in fresh]
        _write_atomic(bodies, "\n".join(kept_b) + "\n")
        kept = old[-max(0, FEED_KEEP - len(new)):] + [json.dumps(r, separators=(",", ":"))
                                                      for r in new]
        _write_atomic(feed, "\n".join(kept) + "\n")
        _write_atomic(cursor, json.dumps({"last_id": new[-1]["id"],
                                          "last_at": new[-1]["at"]}) + "\n")
    st.update(ok=True, new=len(new), pages=sum(r["kind"] == "page" for r in new),
              last_at=new[-1]["at"] if new else cur.get("last_at"))
    with contextlib.suppress(OSError):
        _write_atomic(status, json.dumps(st, indent=1) + "\n")
    return st


def _iso(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def routing(*, now: datetime | None = None, feed: Path = FEED, events: Path = EVENTS,
            flow: Path = FLOW, out: Path = ROUTING) -> dict[str, Any]:
    """ALERT_ROUTING.json: every alert of the last 24h and whether it has reached Claude."""
    t_now = now or datetime.now(tz=UTC)
    alerts: list[dict[str, Any]] = []
    for path, src in ((feed, "ntfy"), (events, "guardian")):
        lines: list[str] = []
        with contextlib.suppress(OSError):
            lines = path.read_text("utf-8").splitlines()[-5000:]
        for ln in lines:
            with contextlib.suppress(ValueError, AttributeError):
                r = json.loads(ln)
                if src == "guardian" and r.get("kind", r.get("event")) != "PLUMBING_DEFECT":
                    continue
                if src == "ntfy" and r.get("kind") != "page":
                    continue
                at = _iso(r.get("at") or r.get("ts"))
                if at and (t_now - at).total_seconds() <= ROUTING_WINDOW_H * 3600:
                    alerts.append({"source": src, "at": at.isoformat(timespec="seconds"),
                                   # a page's words only (no figures/hosts); a guardian
                                   # row names the desk's own organ (a task name)
                                   "what": title_class(str(r.get("title_class")
                                                           or r.get("title") or ""))
                                   or str(r.get("organ") or "")[:160]})
    flow_doc: Any = {}
    with contextlib.suppress(OSError, ValueError):
        flow_doc = json.loads(flow.read_text("utf-8-sig"))
    published = _iso((flow_doc or {}).get("last_published_at")) if isinstance(flow_doc, dict) \
        else None
    unrouted = [a for a in alerts if published is None or _iso(a["at"]) > published]  # type: ignore[operator]
    doc = {"schema": "alert_routing/1", "at": t_now.isoformat(timespec="seconds"),
           "window_h": ROUTING_WINDOW_H, "alerts_24h": len(alerts),
           "routed_24h": len(alerts) - len(unrouted), "unrouted": unrouted[-50:],
           "all_routed": not unrouted,
           "last_published_at": published.isoformat() if published else "UNMEASURED",
           "rule": "routed = carried by a box-state publish that landed after the alert"}
    with contextlib.suppress(OSError):
        _write_atomic(out, json.dumps(doc, indent=1) + "\n")
    return doc


def main() -> int:
    st = poll()
    routing()
    print(f"alert feed: ok={st['ok']} new={st.get('new', 0)} {st.get('why', '')}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
