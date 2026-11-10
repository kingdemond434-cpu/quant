"""ONE robots.txt reader for the desk's fetchers: a Disallow on the exact path stops the fetch.

Governance ruling 2026-11-10 (journal row in #819): a robots.txt Disallow on the exact fetched
path stops the fetch, and a source that answers 401/403/429/451 has said no. This module is the
shared reader, so a fetcher does not carry its own copy of the matching rules:

    gate = RobotsGate(get, agent="quant-research")      # get(url) -> (status | None, body)
    verdict = gate.check("https://host/path?page=2")    # "ALLOWED" | "DISALLOWED" | "UNREAD"

`ALLOWED` covers a readable robots.txt with no matching Disallow and a 404 (no robots.txt is
no restriction, as the standard says). `UNREAD` is any other failure to read the file: the policy
is unknown, and an unknown policy is not a yes, so callers stop on it exactly as on DISALLOWED.

Matching follows the published standard (RFC 9309): `*` matches any run of characters, a trailing
`$` anchors the end, the longest matching rule wins and Allow wins a tie. The group that names
our agent is used when one exists; otherwise the `*` group.
"""
from __future__ import annotations

import re
import threading
import urllib.parse
from collections.abc import Callable

Rules = list[tuple[str, bool]]

ALLOWED, DISALLOWED, UNREAD = "ALLOWED", "DISALLOWED", "UNREAD"

#: Statuses that are a refusal by the server. A fetcher that sees one stops; it does not retry,
#: change headers, or try a sibling host.
HARD_STOP: frozenset[int] = frozenset({401, 403, 429, 451})


def robots_rules(txt: str, agent: str = "quant-research") -> Rules:
    """(path pattern, allow) for the group that applies to `agent`, else the '*' group."""
    groups: list[tuple[list[str], Rules]] = []
    cur_agents: list[str] = []
    cur_rules: Rules = []
    last_was_agent = False
    for raw in (txt or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if not last_was_agent and (cur_agents or cur_rules):
                groups.append((cur_agents, cur_rules))
                cur_agents, cur_rules = [], []
            cur_agents.append(v.lower())
            last_was_agent = True
        elif k in ("allow", "disallow"):
            last_was_agent = False
            if v or k == "allow":
                cur_rules.append((v, k == "allow"))
        else:
            last_was_agent = False
    if cur_agents or cur_rules:
        groups.append((cur_agents, cur_rules))
    a = agent.lower()
    for agents, rules in groups:
        if any(x != "*" and x in a for x in agents):
            return rules
    for agents, rules in groups:
        if "*" in agents:
            return rules
    return []


def robots_allows(rules: Rules, url: str) -> bool:
    """Longest matching rule wins, Allow wins a tie, no matching rule allows."""
    p = urllib.parse.urlsplit(url)
    path = (p.path or "/") + (f"?{p.query}" if p.query else "")
    best: tuple[int, bool] | None = None
    for pat, allow in rules:
        if not pat:
            continue
        rx = "^" + re.escape(pat).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, path):
            key = (len(pat), allow)
            if best is None or key > best:
                best = key
    return True if best is None else best[1]


class RobotsGate:
    """Per-host robots.txt, read once per gate and cached. Thread-safe."""

    def __init__(self, get: Callable[[str], tuple[int | None, str]],
                 agent: str = "quant-research") -> None:
        self._get = get
        self._agent = agent
        self._rules: dict[str, Rules | None] = {}
        self._lock = threading.Lock()

    def _host_rules(self, scheme: str, host: str) -> Rules | None:
        with self._lock:
            if host in self._rules:
                return self._rules[host]
        try:
            code, body = self._get(f"{scheme}://{host}/robots.txt")
        except Exception:
            code, body = None, ""
        rules: Rules | None
        if code == 404:
            rules = []
        elif code is not None and 200 <= code < 300:
            rules = robots_rules(body, self._agent)
        else:
            rules = None
        with self._lock:
            self._rules.setdefault(host, rules)
            return self._rules[host]

    def check(self, url: str) -> str:
        p = urllib.parse.urlsplit(url)
        host = p.netloc.lower()
        if not host:
            return UNREAD
        rules = self._host_rules(p.scheme or "https", host)
        if rules is None:
            return UNREAD
        return ALLOWED if robots_allows(rules, url) else DISALLOWED
