"""THE HARD STOP: one implementation of the standing rule for a 401, 403, 429 or WAF challenge.

A producer that receives one stops the pass on the spot and places a HOLD on the refusing host.
A hold is RELEASED BY A PERSON AND BY NOTHING ELSE: there is no expiry, no backoff that lapses, no
timer of any kind (principal's scope rule 2026-10-13, "401/403/429 = HARD STOP, honest UA,
robots"; audit 0b66b08de). While it stands, every producer that uses that host sends ZERO requests
to it. A Retry-After is never read as permission. The producer never retries around the hold,
rotates identity or User-Agent, or takes another host or route to the same content.

THE HOLD RECORD (one row per refusing host, kept in the desk's one register of sources that
stopped yielding, `data/intelligence/blocked_sources.json`, under "holds"):

    {"key": "site:<refusing host>", "verdict": "HARD_STOP" | "ROBOTS_HOLD" | "WAF_CHALLENGE",
     "status": <http status or null>, "host": "<host>", "url": "<first 300 chars>",
     "held_at": <unix ts>, "released_by": null, "released_at": null}

Active while `released_by` is null. Released only by a person:

    python -m desks.mt5.research.hard_stop --release site:trends.google.com --by <name>

which writes `released_by` and `released_at`. A released record is kept: when the host refuses
again, the released row moves to "hold_history" and a new row is placed. Each producer also keeps a
copy of its hold in its own state (so a register write that fails still holds the next pass); that
copy is released by the register's release record for the same key, never by time.

ROBOTS (RFC 9309). `robots_verdict` reads robots.txt at the exact host, under the group naming
DESK_UA_PRODUCT (stacked User-agent lines are one group; '*' only when no group names us),
longest-match path rules with `*` and `$`, Allow winning a tie, matched against the exact path
and query about to be requested. A Disallow means THAT URL is not fetched; it is not a person
hold, because robots.txt is re-read at most once per 24h per host (`ROBOTS_TTL_S`), which is how a
site's change of mind is picked up. A 404/410 (or another 4xx) is ABSENT and allows. A 5xx or an
unreachable robots.txt means no fetch from that host this pass, and it is re-read next pass. A
401/403/429 or a challenge on robots.txt itself is a person-held ROBOTS_HOLD.

Used by `research/form4_lane.py`, `side_channels/google_trends_miner.py` and the gtrends path of
`libs/data/free_stack.py`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]

#: THE DESK'S DECLARED IDENTITY, with a contact path. These two strings mirror
#: `libs/data/polite_fetch.py` on the Global data branch byte for byte; change both or neither.
#: robots.txt groups are matched on the product token. One fixed value: never rotated.
DESK_UA_PRODUCT = "quant-mt5-research-desk"
DESK_UA = ("quant-mt5-research-desk/1.0 (+https://github.com/kingdemond434-cpu/quant/issues; "
           "internal research; honours robots.txt)")

#: Statuses that place a hold. The value is the producer's pass status.
HARD_STOP: dict[int, str] = {401: "NEEDS_KEY", 403: "METHOD_BLOCKED", 429: "METHOD_BLOCKED"}
VERDICT_HARD_STOP = "HARD_STOP"
VERDICT_ROBOTS_HOLD = "ROBOTS_HOLD"
VERDICT_WAF = "WAF_CHALLENGE"
#: The pass status of a challenge page (a 200 or a 503 that is a WAF, not the content).
CHALLENGED = "CHALLENGED"
#: The desk's one register of sources that stopped yielding (written by the regional survivor
#: hunters too); holds live there, never in a register of their own.
BLOCKED_REGISTER = DESK / "data" / "intelligence" / "blocked_sources.json"
#: robots.txt is re-read at most once per this many seconds per host.
ROBOTS_TTL_S = 86400.0
ROBOTS_MAX_CHARS = 200_000

#: Fingerprints of a WAF / bot challenge served in place of the content.
_CHALLENGE_MARKERS = ("/cdn-cgi/challenge-platform", "cf-chl-", "attention required! | cloudflare",
                      "g-recaptcha", "h-captcha", "hcaptcha.com", "_incapsula_resource",
                      "request unsuccessful. incapsula", "www.google.com/sorry/",
                      "our systems have detected unusual traffic", "px-captcha")


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


def _ts(now: datetime) -> float:
    return round(now.timestamp(), 3)


def host_of(url: str) -> str:
    return urllib.parse.urlsplit(str(url or "")).netloc.lower()


def host_key(host: str) -> str:
    return f"site:{str(host).lower()}"


def retry_after_s(value: str | None, now: datetime) -> float | None:
    """Retry-After as seconds from `now`: delta-seconds or an HTTP-date; None when absent/bad.
    RECORDED ONLY: it never releases a hold."""
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


def is_challenge(status: int, headers: Mapping[str, Any] | None, body: bytes | str | None
                 ) -> bool:
    """Is this response a WAF / bot challenge rather than the content?"""
    hdr = {str(k).lower(): str(v).lower() for k, v in (headers or {}).items()}
    if hdr.get("cf-mitigated") == "challenge":
        return True
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body or "")
    low = text[:20000].lower()
    return any(m in low for m in _CHALLENGE_MARKERS)


def refusal(status: int, headers: Mapping[str, Any] | None = None,
            body: bytes | str | None = None) -> str | None:
    """The hold verdict a response earns (HARD_STOP / WAF_CHALLENGE), or None."""
    if status in HARD_STOP:
        return VERDICT_HARD_STOP
    if is_challenge(status, headers, body):
        return VERDICT_WAF
    return None


def pass_status(record: Mapping[str, Any]) -> str:
    """The producer's pass status for a hold record."""
    st = record.get("status")
    if record.get("verdict") == VERDICT_WAF:
        return CHALLENGED
    if isinstance(st, int) and st in HARD_STOP:
        return HARD_STOP[st]
    return str(record.get("verdict") or "HELD")


def hold_record(verdict: str, status: int | None, url: str, now: datetime,
                key: str | None = None) -> dict[str, Any]:
    """The hold row, exactly the shape the module docstring names."""
    host = host_of(url)
    return {"key": key or host_key(host), "verdict": verdict,
            "status": int(status) if status is not None else None, "host": host,
            "url": str(url)[:300], "held_at": _ts(now), "released_by": None,
            "released_at": None}


def _register(register: Path) -> dict[str, Any]:
    reg = _read_json(register, None)
    if not isinstance(reg, dict):
        reg = {"note": "sources that returned no survivor records -- a WORK QUEUE, never a "
                       "discovery.", "sources": {}}
    return reg


def place_hold(record: dict[str, Any], register: Path, *, source_key: str | None = None,
               region: str = "global") -> None:
    """Write `record` as the register's hold for its key. A released row already there moves to
    "hold_history"; an unreleased one is kept (the first refusal stands). With `source_key`, the
    work-queue entry under "sources" is updated too, every other entry kept."""
    reg = _register(register)
    holds = reg.setdefault("holds", {})
    cur = holds.get(record["key"])
    if isinstance(cur, dict) and not _named(cur.get("released_by")):
        pass                                   # already held: the standing record is kept
    else:
        if isinstance(cur, dict):
            reg.setdefault("hold_history", []).append(cur)
        holds[record["key"]] = record
    if source_key:
        at = datetime.fromtimestamp(float(record["held_at"]), tz=UTC).isoformat(
            timespec="seconds")
        e = reg.setdefault("sources", {}).setdefault(source_key, {"first_seen": at,
                                                                  "region": region})
        e.update({"last_seen": at, "url": record["url"], "diagnosis": record["verdict"],
                  "hold_key": record["key"],
                  "fix_hint": (f"{record['verdict']}: HTTP {record['status']} from "
                               f"{record['host']}. HELD UNTIL A PERSON RELEASES IT "
                               f"(python -m desks.mt5.research.hard_stop --release "
                               f"{record['key']} --by <name>); no retry, no identity or "
                               "User-Agent rotation, no other host or route"),
                  "error": f"{record['verdict']} HTTP {record['status']}",
                  "attempts": int(e.get("attempts", 0)) + 1})
        e.pop("blocked_until", None)
    _write_json(register, reg)


def note_robots(verdict: Mapping[str, Any], register: Path, *, source_key: str,
                region: str = "global") -> None:
    """Record a robots Disallow on the work-queue entry. NOT a hold: robots is re-read daily."""
    reg = _register(register)
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    e = reg.setdefault("sources", {}).setdefault(source_key, {"first_seen": now,
                                                              "region": region})
    e.update({"last_seen": now, "url": str(verdict.get("robots_url")),
              "diagnosis": "ROBOTS_DISALLOW", "robots": dict(verdict),
              "fix_hint": "robots.txt disallows this path for our agent: not fetched; "
                          "robots.txt is re-read at most once a day"})
    _write_json(register, reg)


def _named(released_by: Any) -> bool:
    """A release names a person: an empty or whitespace `released_by` releases nothing."""
    return released_by is not None and bool(str(released_by).strip())


def _released(reg: Mapping[str, Any], key: str, held_at: Any) -> bool:
    """Has a person released `key` at or after `held_at`?"""
    rows = [(reg.get("holds") or {}).get(key), *(reg.get("hold_history") or [])]
    try:
        at = float(held_at)
    except (TypeError, ValueError):
        at = float("-inf")
    for r in rows:
        if isinstance(r, dict) and r.get("key") == key and _named(r.get("released_by")):
            try:
                if float(r.get("released_at") or 0) >= at:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def active_hold(register: Path, keys: Iterable[str],
                mirror: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """The hold in force on any of `keys`, or None. The register's row is in force while
    `released_by` is null; the producer's own copy (`mirror`) while the register holds no release
    for its key made at or after it was placed. No time field is read as a release."""
    reg = _register(register)
    holds = reg.get("holds") or {}
    for k in keys:
        row = holds.get(k)
        if isinstance(row, dict) and not _named(row.get("released_by")):
            return dict(row)
    if isinstance(mirror, dict) and mirror.get("key") and not _named(mirror.get("released_by")) \
            and not _released(reg, str(mirror["key"]), mirror.get("held_at")):
        return dict(mirror)
    return None


def release(register: Path, key: str, by: str, now: datetime | None = None
            ) -> dict[str, Any]:
    """A person releases `key`: `released_by` and `released_at` are written on its row (a key
    with no row gets a release row, so a producer's own copy is released too)."""
    if not str(by or "").strip():
        raise ValueError("a release names the person who made it (--by)")
    now = now or datetime.now(tz=UTC)
    reg = _register(register)
    holds = reg.setdefault("holds", {})
    row = holds.get(key)
    if not isinstance(row, dict):
        row = {"key": key, "verdict": None, "status": None,
               "host": key.split(":", 1)[1] if key.startswith("site:") else "", "url": "",
               "held_at": None, "released_by": None, "released_at": None}
        holds[key] = row
    row["released_by"] = str(by).strip()
    row["released_at"] = _ts(now)
    _write_json(register, reg)
    return dict(row)


# ------------------------------------------------------------------------------------ robots

def robots_url(url: str) -> str:
    """The robots.txt of `url`'s OWN scheme and host (robots is host-scoped: never another's)."""
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def robots_cached(cache: Mapping[str, Any], url: str, now: datetime
                  ) -> tuple[int, str] | None:
    """A robots.txt reading for `url`'s host taken within ROBOTS_TTL_S, or None (read it)."""
    row = (cache or {}).get(robots_url(url))
    if not isinstance(row, dict):
        return None
    try:
        age = _ts(now) - float(row["read_at"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 0 <= age < ROBOTS_TTL_S:
        return None
    return int(row.get("status") or 0), str(row.get("body") or "")


def robots_remember(cache: dict[str, Any], url: str, status: int, body: bytes | str | None,
                    now: datetime) -> None:
    """Keep a DEFINITIVE reading (a 2xx, or a 4xx that is no refusal) for a day. A 5xx or an
    unreachable host is not kept, so the next pass reads again."""
    if not (200 <= status < 300 or (400 <= status < 500 and status not in HARD_STOP)):
        cache.pop(robots_url(url), None)
        return
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body or "")
    cache[robots_url(url)] = {"status": int(status), "body": text[:ROBOTS_MAX_CHARS],
                              "read_at": _ts(now)}


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


def robots_verdict(url: str, status: int, body: bytes | str | None,
                   product: str = DESK_UA_PRODUCT) -> dict[str, Any]:
    """RFC 9309 verdict for fetching `url` as `product`, from the robots.txt response
    (`status`, `body`) read at `robots_url(url)`. States: ALLOWED, DISALLOWED, ABSENT (4xx, allows),
    UNAVAILABLE (5xx / unreachable: no fetch this pass), REFUSED (401/403/429: the caller holds)."""
    parts = urllib.parse.urlsplit(url)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    out: dict[str, Any] = {"robots_url": robots_url(url), "http_status": int(status),
                           "path": path[:300]}
    if status in HARD_STOP:
        return {**out, "state": "REFUSED", "allowed": False,
                "detail": f"robots.txt answered HTTP {status}: a refusal, held for a person"}
    if status == 0 or status >= 500:
        return {**out, "state": "UNAVAILABLE", "allowed": False,
                "detail": f"robots.txt {'unreachable' if status == 0 else f'HTTP {status}'}: "
                          "RFC 9309 reads it as a full disallow; no fetch this pass, re-read next"}
    if 400 <= status < 500:
        return {**out, "state": "ABSENT", "allowed": True,
                "detail": f"robots.txt HTTP {status}: no robots file, unrestricted (RFC 9309)"}
    if not 200 <= status < 300:
        return {**out, "state": "UNAVAILABLE", "allowed": False,
                "detail": f"robots.txt HTTP {status}: not a readable answer, no fetch"}
    if path == "/robots.txt":
        return {**out, "state": "ALLOWED", "allowed": True, "detail": "robots.txt itself"}
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body or "")
    token = str(product or "").lower()
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


# ------------------------------------------------------------------------------------ the CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="List or release hard-stop holds (a person's act).")
    ap.add_argument("--register", type=Path, default=BLOCKED_REGISTER)
    ap.add_argument("--release", metavar="KEY", help="e.g. site:trends.google.com")
    ap.add_argument("--by", metavar="NAME", help="who releases it (required with --release)")
    ap.add_argument("--list", action="store_true", help="print every hold and its state")
    a = ap.parse_args(argv)
    if a.release:
        if not a.by:
            print("hard_stop: --release needs --by <name>", file=sys.stderr)
            return 2
        row = release(a.register, a.release, a.by)
        print(f"hard_stop: released {row['key']} by {row['released_by']} at "
              f"{row['released_at']}")
        return 0
    reg = _register(a.register)
    for k, row in sorted((reg.get("holds") or {}).items()):
        state = "RELEASED" if row.get("released_by") else "HELD"
        print(f"{state:8} {k}  {row.get('verdict')} HTTP {row.get('status')} at "
              f"{row.get('held_at')}" + (f" released by {row['released_by']}"
                                         if row.get("released_by") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
