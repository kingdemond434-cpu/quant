"""THE DESK'S ONE HONEST USER-AGENT (2026-11-18).

The desk's fetch law: every automated request names what is reading, so a host's robots.txt and
its operators can address us, and nothing the desk sends impersonates a browser. Before this
module, 88 fetchers carried a desktop-Chrome string (and one carried a personal e-mail address).

The token before the slash is ``ROBOTS_AGENT``, the name robots.txt rules are matched against
(the same token ``deep_forest_miner`` and ``alpha_capture`` already declare). The string names no
person, account or repository owner: the repository is public, and a client name is not a place
to publish who runs it.

A host that answers this name with 401/403/429/451 has REFUSED us. That is a hard stop and an
honest BLOCKED verdict with its missed_growth line; it is never a cue to retry under a browser's
name. ``tests/governance/test_honest_user_agent.py`` fences the whole tree against a browser
string coming back.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

#: The token robots.txt rules are matched against.
ROBOTS_AGENT = "quant-desk-research"
#: The User-Agent every desk fetcher sends.
HONEST_UA = f"{ROBOTS_AGENT}/1.0 (automated research; honours robots.txt)"
#: Ready-made headers for callers that only need the name.
HONEST_HEADERS: dict[str, str] = {"User-Agent": HONEST_UA}


# --------------------------------------------------------------------------- refusals
# THE AUDITOR'S FINDING (2026-11-18). Once the desk sends its own name, some grounds answer
# 401/403/429/451 or serve a challenge or wall page. Every fetcher used to book that as "HTTP 403",
# "error", "empty" or a failed run, and five failed runs made a source DEAD in
# libs/research/source_health -- so a ground that REFUSED the desk read as one that had nothing,
# and the alternatives hunter treated it as broken plumbing. A refusal is neither: it is the host's
# lawful answer to the desk as it really is. It is recorded as a row of its own, using the desk's
# existing vocabulary (HARD_STOP for a refusing status, BLOCKED_ON_TERMS for a wall), carrying the
# host, the status, the name we sent and the growth it costs. It is FINAL: never retried under
# another User-Agent, rotated, proxied or otherwise routed around. ``refusal_row`` is the one
# classifier; polite_fetch, venue_http, run_all_miners and source_health all call it.

#: The desk's existing status words (libs/ops/token_refresh, libs/data/refused_hosts).
HARD_STOP = "HARD_STOP"
BLOCKED_ON_TERMS = "BLOCKED_ON_TERMS"
REFUSAL_STATES: frozenset[str] = frozenset({HARD_STOP, BLOCKED_ON_TERMS})
#: Statuses that mean the host refused the honest name.
REFUSAL_STATUS: frozenset[int] = frozenset({401, 403, 429, 451})
REFUSAL_MISSED_GROWTH = ("missed_growth: ground refused the honest name; its discoveries are "
                         "forgone until a lawful route exists")
#: Markers of an interstitial wall rather than content. Deliberately narrow: an ordinary page
#: carrying a reCAPTCHA reply form, or Cloudflare's passive ``/cdn-cgi/challenge-platform/`` JS,
#: is CONTENT and must not be booked as a wall.
CHALLENGE_MARKERS: tuple[str, ...] = (
    "<title>just a moment", "<title>attention required", "_cf_chl_opt", "cf-chl-",
    "checking your browser before accessing", "verify you are human", "px-captcha",
    "captcha-delivery.com", "_incapsula_resource", "<title>access denied</title>",
)
_SCAN_CHARS = 20_000

_URL_IN_TEXT = re.compile(r"https?://[^\s)'\"<>]+")
_HTTP_IN_TEXT = re.compile(r"\bHTTP(?:\s*Error)?\s*(401|403|429|451)\b", re.I)


def challenge_marker(body: str | bytes | None) -> str | None:
    """The first wall marker in ``body`` (its head only), or None."""
    if not body:
        return None
    text = (body[:_SCAN_CHARS].decode("utf-8", "ignore") if isinstance(body, bytes)
            else body[:_SCAN_CHARS]).lower()
    return next((m for m in CHALLENGE_MARKERS if m in text), None)


def _status_in_text(text: str) -> int | None:
    m = _HTTP_IN_TEXT.search(text)
    return int(m.group(1)) if m else None


def refusal_row(url: str = "", *, status: int | None = None, body: str | bytes | None = None,
                error: str | None = None, user_agent: str = HONEST_UA) -> dict[str, object] | None:
    """The refused row for one answer, or None when the answer was not a refusal.

    A status in ``REFUSAL_STATUS`` (or one named in ``error``, for callers that only kept the
    text) is HARD_STOP; a recognisable challenge or wall page is BLOCKED_ON_TERMS. Pure."""
    code = status if status in REFUSAL_STATUS else None
    if code is None and status is None and error:
        code = _status_in_text(error)
    marker = None if code is not None else challenge_marker(body)
    if code is None and marker is None and error:
        marker = challenge_marker(error)
    if code is None and marker is None:
        return None
    if not url and error:                 # a caller that kept only the text: recover the URL
        m = _URL_IN_TEXT.search(error)
        url = m.group(0) if m else ""
    host = (urlparse(url).hostname or "") if url else ""
    state = HARD_STOP if code is not None else BLOCKED_ON_TERMS
    why = (f"HTTP {code} to {ROBOTS_AGENT}" if code is not None
           else f"challenge/wall page ({marker!r}) served to {ROBOTS_AGENT}")
    return {"status": state, "host": host, "url": url, "http_status": code if code else status,
            "user_agent": user_agent, "why": f"{state}: {why} -- the host refused the desk",
            "missed_growth": REFUSAL_MISSED_GROWTH, "retry": "never", "bypass": "refused"}


def is_refused(row: object) -> bool:
    """True for a row (or status word) this module classified as a refusal."""
    status = row.get("status") if isinstance(row, dict) else row
    return str(status or "") in REFUSAL_STATES
