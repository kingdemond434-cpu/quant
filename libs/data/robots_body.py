"""Turn a robots.txt reply into rules or a refusal, FAILING CLOSED.

`urllib.robotparser.RobotFileParser` parses whatever it is given. A site that answers
/robots.txt with HTTP 200 and an HTML page (a soft 404, a WAF or bot challenge, a redirect to the
homepage) yields no rules, and an empty parser allows everything: the reader fails OPEN. The law
is the opposite (deep_forest_miner.access_refusal, Governance ruling 2026-11-10, PR #819):

* 404 / 410             -> there is no file: empty rules, everything allowed (RFC 9309).
* 401 / 403 / 429 / 451 -> a HARD STOP for the host, never a timed back-off.
* any other status, a transport failure (status None/0), an HTML body or a non-text content
  type                  -> UNREAD. Unread robots are not permission.

Standard library only and no import-time side effects: money-closure modules may import it.
"""
from __future__ import annotations

import urllib.robotparser

#: robots.txt answers that stop the host outright, whatever RFC 9309 says about a 4xx.
HARD_STOP_STATUSES = frozenset({401, 403, 429, 451})
#: The only answers that mean "there is no robots file".
NO_FILE_STATUSES = frozenset({404, 410})

HARD_STOP = "ROBOTS_HARD_STOP"
UNREAD = "ROBOTS_UNREAD"

#: How far into the body the HTML markers are looked for.
_SNIFF = 512


def is_html_body(body: str | bytes | None) -> bool:
    """True when the body is markup, not robots rules.

    A real robots file never starts with "<"; a WAF page may begin with <head>, <body>, <?xml
    or a comment, so any leading "<" counts, as does "<html" or "<!doctype" anywhere in the
    first 512 characters."""
    if body is None:
        return False
    if isinstance(body, bytes):
        body = body[: _SNIFF * 4].decode("utf-8", errors="replace")
    head = body.lstrip("﻿ \t\r\n\f\v")[:_SNIFF]
    if head.startswith("<"):
        return True
    low = body[:_SNIFF].lower()
    return "<html" in low or "<!doctype" in low


def _content_type_refusal(content_type: str | None) -> str | None:
    """None when the declared type may hold robots rules (text/* other than HTML, or none)."""
    ctype = str(content_type or "").split(";", 1)[0].strip().lower()
    if not ctype:
        return None
    if ctype in ("text/html", "application/xhtml+xml"):
        return f"{UNREAD}: robots.txt answered HTML ({ctype})"
    if not ctype.startswith("text/"):
        return f"{UNREAD}: robots.txt answered {ctype}, not text"
    return None


def body_refusal(content_type: str | None, body: str | bytes | None) -> str | None:
    """Why a 2xx robots body cannot be read as rules, or None when it can."""
    why = _content_type_refusal(content_type)
    if why:
        return why
    if is_html_body(body):
        return f"{UNREAD}: robots.txt answered HTML"
    return None


def deny_all() -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(["User-agent: *", "Disallow: /"])
    return rp


def robots_rules_or_refusal(status: int | None, content_type: str | None,
                            body: str | bytes | None) -> urllib.robotparser.RobotFileParser | str:
    """Parsed rules, or a refusal string starting with HARD_STOP or UNREAD.

    `status` None or 0 is a transport failure. A returned parser is safe to `can_fetch` on."""
    code = int(status or 0)
    if code in NO_FILE_STATUSES:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse([])
        return rp
    if code in HARD_STOP_STATUSES:
        return f"{HARD_STOP}: robots.txt HTTP {code}"
    if code == 0:
        return f"{UNREAD}: robots.txt unreachable"
    if not 200 <= code < 300:
        return f"{UNREAD}: robots.txt HTTP {code}"
    why = body_refusal(content_type, body)
    if why:
        return why
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body or "")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    return rp


def is_hard_stop(refusal: object) -> bool:
    return isinstance(refusal, str) and refusal.startswith(HARD_STOP)
