"""THE HARD STOP: one implementation of the standing rule for a 401, 403 or 429.

A producer that receives one stops the pass on the spot, marks itself METHOD_BLOCKED (403/429) or
NEEDS_KEY (401) with the reason, persists a backoff (the response's Retry-After when it names one,
else 1h doubling per consecutive block, capped at 7 days) that makes its later passes request
nothing until it expires, and records the block in the desk's one register of sources that stopped
yielding, `data/intelligence/blocked_sources.json`. It never retries around the block, rotates
identity or User-Agent, or takes another host or route to the same gated content.

ROBOTS (audit 0b66b08de MF5; principal's scope rule 2026-10-13: "401/403/429 = HARD STOP, honest
UA, robots"). `robots_verdict` reads the host's robots.txt under RFC 9309: the group naming the
desk's OWN product token (stacked User-agent lines are one group; '*' only when no group names us),
longest-match path rules with `*` and `$`, Allow winning a tie, matched against the exact path and
query about to be requested. A 2xx is parsed; a 404/410 (or another 4xx) is ABSENT and allows; a 5xx
or an unreachable host is UNAVAILABLE and disallows; a 401/403/429 on robots.txt itself is a hold
(the caller's hard stop). A disallowed path is NOT fetched: `robots_marker` records it as a hold
exactly as a 401/403/429 is recorded (persisted backoff, the blocked-sources register), carrying the
verdict, and robots.txt is re-read when the backoff expires.

Used by `research/form4_lane.py`, `side_channels/google_trends_miner.py` and the gtrends path of
`libs/data/free_stack.py`.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]

HARD_STOP: dict[int, str] = {401: "NEEDS_KEY", 403: "METHOD_BLOCKED", 429: "METHOD_BLOCKED"}
#: The status a robots hold carries (a Disallow for our agent, or robots.txt unavailable).
ROBOTS_HOLD = "ROBOTS_HOLD"
#: Backoff when the response names no Retry-After: 1h, doubling per consecutive block, capped.
BACKOFF_BASE_S = 3600.0
BACKOFF_MAX_S = 7 * 86400.0
#: The desk's one register of sources that stopped yielding (written by the regional survivor
#: hunters too); a block is recorded there, never in a register of its own.
BLOCKED_REGISTER = DESK / "data" / "intelligence" / "blocked_sources.json"


def _parse_time(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def retry_after_s(value: str | None, now: datetime) -> float | None:
    """Retry-After as seconds from `now`: delta-seconds or an HTTP-date; None when absent/bad."""
    if not value:
        return None
    v = str(value).strip()
    if v.isdigit():
        return float(v)
    try:
        from email.utils import parsedate_to_datetime
        at = parsedate_to_datetime(v)
    except (TypeError, ValueError, IndexError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return max(0.0, (at - now).total_seconds())


def block_marker(status: int, url_class: str, headers: dict[str, str], now: datetime,
                 prior: dict[str, Any] | None) -> dict[str, Any]:
    """The persisted marker: who refused, which URL class, when, and until when."""
    hdr = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    consecutive = int((prior or {}).get("consecutive") or 0) + 1
    ra = retry_after_s(hdr.get("retry-after"), now)
    wait = ra if ra is not None else min(BACKOFF_MAX_S,
                                         BACKOFF_BASE_S * 2 ** (consecutive - 1))
    return {"status": HARD_STOP[status], "http_status": status, "url_class": url_class,
            "at": now.isoformat(timespec="seconds"),
            "until": (now + timedelta(seconds=wait)).isoformat(timespec="seconds"),
            "backoff_s": wait, "backoff_source": "retry_after" if ra is not None else
            "exponential", "consecutive": consecutive}


def active(marker: Any, now: datetime) -> bool:
    """Is this persisted marker still in force at `now`?"""
    if not isinstance(marker, dict):
        return False
    until = _parse_time(marker.get("until"))
    return until is not None and now < until


def record_block(marker: dict[str, Any], register: Path, *, key: str, host: str,
                 region: str = "global") -> None:
    """Add or update `key` in the existing blocked-sources register (same schema as the regional
    survivor hunters' entries); every other entry is kept."""
    reg = _read_json(register, None)
    if not isinstance(reg, dict):
        reg = {"note": "sources that returned no survivor records -- a WORK QUEUE, never a "
                       "discovery.", "sources": {}}
    e = reg.setdefault("sources", {}).setdefault(key, {"first_seen": marker["at"],
                                                       "region": region})
    robots = marker.get("robots") if isinstance(marker.get("robots"), dict) else None
    if robots is not None:
        e.update({"last_seen": marker["at"], "url": f"{host} {marker['url_class']}",
                  "diagnosis": marker["status"],
                  "fix_hint": (f"ROBOTS HOLD: {robots.get('state')} ({robots.get('detail')}) -- "
                               f"not fetched; robots.txt re-read after {marker['until']}"),
                  "error": f"robots {robots.get('state')} on {marker['url_class']}",
                  "blocked_until": marker["until"],
                  "attempts": int(e.get("attempts", 0)) + 1})
        _write_json(register, reg)
        return
    e.update({"last_seen": marker["at"], "url": f"{host} {marker['url_class']}",
              "diagnosis": marker["status"],
              "fix_hint": (f"HARD STOP: HTTP {marker['http_status']} -- backed off until "
                           f"{marker['until']}; no retry around the block, no identity or "
                           "User-Agent rotation, no other host or route to the same content"
                           + ("; a key/credential is needed" if marker["status"] == "NEEDS_KEY"
                              else "")),
              "error": f"HTTP {marker['http_status']} on {marker['url_class']}",
              "blocked_until": marker["until"],
              "attempts": int(e.get("attempts", 0)) + 1})
    _write_json(register, reg)


# ------------------------------------------------------------------------------------ robots

def robots_url(url: str) -> str:
    """The robots.txt of `url`'s OWN scheme and host (robots is host-scoped: never another's)."""
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def product_token(user_agent: str) -> str:
    """The product token a robots group is matched on: the UA up to its first '/' or space."""
    return re.split(r"[/\s]", str(user_agent or "").strip(), maxsplit=1)[0].lower()


def _groups(body: str) -> list[tuple[set[str], list[tuple[bool, str]]]]:
    groups: list[tuple[set[str], list[tuple[bool, str]]]] = []
    agents: set[str] = set()
    rules: list[tuple[bool, str]] = []
    in_rules = False
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            if in_rules:                       # a new group starts after the last one's rules
                groups.append((agents, rules))
                agents, rules, in_rules = set(), [], False
            agents.add(val.lower())            # stacked User-agent lines ACCUMULATE (L0221)
        elif key in ("allow", "disallow") and agents:
            in_rules = True
            rules.append((key == "allow", val))
    if agents:
        groups.append((agents, rules))
    return groups


def _pattern_matches(pattern: str, path: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.match(rx + ("$" if anchored else ""), path) is not None


def robots_verdict(url: str, user_agent: str, status: int, body: bytes | str | None
                   ) -> dict[str, object]:
    """RFC 9309 verdict for fetching `url` as `user_agent`, from the robots.txt response
    (`status`, `body`) read at `robots_url(url)` under that same UA. Never names the UA itself.

    `allowed` is True only on a positive reading: a served file that does not disallow the path,
    or an ABSENT one (4xx other than 401/403/429). 5xx and status 0 (unreachable) are UNAVAILABLE
    and disallow; 401/403/429 is REFUSED and the caller applies its hard stop."""
    parts = urllib.parse.urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    out: dict[str, object] = {"robots_url": robots_url(url), "http_status": int(status),
                              "path": path}
    if status in HARD_STOP:
        return {**out, "state": "REFUSED", "allowed": False,
                "detail": f"robots.txt answered HTTP {status}: a route refusal, held"}
    if status == 0 or status >= 500:
        return {**out, "state": "UNAVAILABLE", "allowed": False,
                "detail": f"robots.txt {'unreachable' if status == 0 else f'HTTP {status}'}: "
                          "RFC 9309 reads an unavailable robots.txt as a full disallow"}
    if 400 <= status < 500:
        return {**out, "state": "ABSENT", "allowed": True,
                "detail": f"robots.txt HTTP {status}: no robots file, unrestricted (RFC 9309)"}
    if not 200 <= status < 300:
        return {**out, "state": "UNAVAILABLE", "allowed": False,
                "detail": f"robots.txt HTTP {status}: not a readable answer, held"}
    if path == "/robots.txt":
        return {**out, "state": "ALLOWED", "allowed": True, "detail": "robots.txt itself"}
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body or "")
    token = product_token(user_agent)
    groups = _groups(text)
    mine = [r for a, r in groups if token and token in a]
    scope = "own agent"
    if not mine:
        mine = [r for a, r in groups if "*" in a]
        scope = "'*'" if mine else "no group"
    best: tuple[int, bool] | None = None          # (pattern length, allow) -- longest wins
    for allow, pattern in (rule for rules in mine for rule in rules):
        if not pattern or not _pattern_matches(pattern, path):
            continue
        cand = (len(pattern), allow)
        if best is None or cand[0] > best[0] or (cand[0] == best[0] and allow):
            best = cand
    allowed = best is None or best[1]
    return {**out, "state": "ALLOWED" if allowed else "DISALLOWED", "allowed": allowed,
            "group": scope,
            "detail": (f"robots.txt {'allows' if allowed else 'disallows'} {path[:80]} for the "
                       f"{scope} group")}


def robots_marker(verdict: dict[str, object], url_class: str, now: datetime,
                  prior: dict[str, Any] | None) -> dict[str, Any]:
    """The persisted hold for a robots verdict that does not allow the fetch: the same marker,
    backoff and register as a 401/403/429, with status ROBOTS_HOLD and the verdict attached."""
    consecutive = int((prior or {}).get("consecutive") or 0) + 1
    wait = min(BACKOFF_MAX_S, BACKOFF_BASE_S * 2 ** (consecutive - 1))
    return {"status": ROBOTS_HOLD, "http_status": verdict.get("http_status"),
            "url_class": url_class, "at": now.isoformat(timespec="seconds"),
            "until": (now + timedelta(seconds=wait)).isoformat(timespec="seconds"),
            "backoff_s": wait, "backoff_source": "exponential", "consecutive": consecutive,
            "robots": dict(verdict)}
