"""ROBOTS GATE -- one shared answer to "may this desk fetch that URL, as itself?"

Four organs each carried their own robots reader (index_discovery, futures_state, asia_collector,
shadow_institutional) and they did not agree: asia_collector treated an unreadable robots.txt as
permission, index_discovery and futures_state did not. This module is the stricter rule, which
Governance ruled governs (2026-11-10, PR #819), written once so a new organ does not pick a side
by accident:

    robots.txt 200        parsed; the exact URL is asked for OUR agent token
    robots.txt 404 / 410  no rules: allowed (that is what the standard says a missing file means)
    robots.txt 401 / 403  everything disallowed
    anything else         REFUSED -- an unread policy is never read as permission

THE AGENT NAMES ITSELF. `honest_ua(organ)` returns a User-Agent that says what is asking and where
its code lives. No browser impersonation: a site that would refuse a research client is a site
whose answer this desk takes.

The fetcher is injectable (`get_text(url) -> (status, text)`), so every caller can be tested on
recorded robots files without touching the network. One read per host per gate instance.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable

#: The token robots rules are matched against. A rule written for this token, or for `*`, binds.
ROBOTS_AGENT = "quant-research"
CONTACT = "+https://github.com/kingdemond434-cpu/quant"

#: (status, text). status 0 = transport failure (no HTTP answer at all).
GetText = Callable[[str], tuple[int, str]]


def honest_ua(organ: str) -> str:
    """`quant-research/1.0 (+repo; <organ>)` -- what is asking, and where its source is."""
    return f"{ROBOTS_AGENT}/1.0 ({CONTACT}; {organ})"


def _urllib_get_text(ua: str, timeout: float) -> GetText:
    def get(url: str) -> tuple[int, str]:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return int(getattr(r, "status", 200) or 200), r.read(500_000).decode(
                    "utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return int(exc.code or 0), ""
        except Exception:
            return 0, ""
    return get


class RobotsGate:
    """Per-host robots rules, read once, asked per URL. `refusal(url)` is None when allowed."""

    def __init__(self, organ: str, get_text: GetText | None = None,
                 timeout: float = 15.0) -> None:
        self.organ = organ
        self.ua = honest_ua(organ)
        self._get = get_text or _urllib_get_text(self.ua, timeout)
        self._rules: dict[str, urllib.robotparser.RobotFileParser | str] = {}
        #: host -> what the gate decided about its robots file, for the organ's report
        self.consulted: dict[str, str] = {}

    def _for(self, scheme: str, host: str) -> urllib.robotparser.RobotFileParser | str:
        key = f"{scheme}://{host}"
        if key in self._rules:
            return self._rules[key]
        status, text = self._get(f"{key}/robots.txt")
        rp = urllib.robotparser.RobotFileParser()
        out: urllib.robotparser.RobotFileParser | str
        if 200 <= status < 300:
            rp.parse(text.splitlines())
            out, note = rp, "robots.txt read"
        elif status in (404, 410):
            rp.parse([])
            out, note = rp, f"no robots.txt (HTTP {status}): no rules"
        elif status in (401, 403):
            rp.parse(["User-agent: *", "Disallow: /"])
            out, note = rp, f"robots.txt HTTP {status}: everything disallowed"
        else:
            out = note = (f"robots.txt unreadable (HTTP {status})" if status
                          else "robots.txt unreadable (no HTTP answer)")
        self._rules[key] = out
        self.consulted[host] = note
        return out

    def refusal(self, url: str) -> str | None:
        """None when this exact URL may be fetched by this agent; otherwise the reason it may not.

        The robots.txt request itself is the one fetch that cannot be gated by its own answer.
        """
        parts = urllib.parse.urlsplit(url)
        if parts.path == "/robots.txt":
            return None
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return f"not an http(s) URL: {url[:80]}"
        rules = self._for(parts.scheme, parts.netloc)
        if isinstance(rules, str):
            return rules
        if not rules.can_fetch(ROBOTS_AGENT, url):
            return "robots.txt disallows this path for our agent"
        return None

    def allowed(self, url: str) -> bool:
        return self.refusal(url) is None
