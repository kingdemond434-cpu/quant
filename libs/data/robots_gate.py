"""ONE robots.txt reader for the desk's fetchers: a Disallow on the exact path stops the fetch.

Governance desk-wide robots ruling 2026-11-10 20:08Z (this module is the chosen single reader):

    robots.txt answer            verdict      reason                fetch?
    2xx, path allowed            ALLOWED      ROBOTS_ALLOWED        yes
    2xx, Disallow on the path    DISALLOWED   ROBOTS_DISALLOWED     no
    404/410/other 4xx            ALLOWED      ROBOTS_ABSENT         yes (no rules, as RFC 9309 says)
    401/403/429/451              UNREAD       ROBOTS_REFUSED        no  (the host said no)
    5xx/timeout/unreachable      UNREAD       ROBOTS_UNREACHABLE    no  (retry next pass)

429 and 451 are held with 401/403 because HARD_STOP already names them a refusal for pages; a
host that refuses or rate-limits its own robots.txt is not read as "no rules". Every check is
counted by reason in `gate.counts`, so a fetcher publishes how many routes fell in each case.

    gate = RobotsGate(get, agent="quant-research")      # get(url) -> (status | None, body)
    verdict = gate.check("https://host/path?page=2")    # "ALLOWED" | "DISALLOWED" | "UNREAD"
    gate.reason("https://host/path")                     # "ROBOTS_ABSENT", ...

Callers stop on DISALLOWED and UNREAD alike. The cache lives for one gate (one pass), so an
unreachable robots.txt is asked again on the next pass.

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

R_ALLOWED, R_DISALLOWED, R_ABSENT = "ROBOTS_ALLOWED", "ROBOTS_DISALLOWED", "ROBOTS_ABSENT"
R_REFUSED, R_UNREACHABLE = "ROBOTS_REFUSED", "ROBOTS_UNREACHABLE"

#: Statuses that are a refusal by the server. A fetcher that sees one stops; it does not retry,
#: change headers, or try a sibling host.
HARD_STOP: frozenset[int] = frozenset({401, 403, 429, 451})


def robots_rules(txt: str, agent: str = "quant-research") -> Rules:
    """(path pattern, allow) of every group that names `agent`, else of every '*' group."""
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
    # RFC 9309 s2.2.1: EVERY group that matches the product token is combined (a Disallow in a
    # second matching group must bind; taking only the first failed open). The '*' groups,
    # likewise combined, apply only when no group names the agent.
    a = agent.lower()
    named = [r for agents, rules in groups if any(x != "*" and x in a for x in agents)
             for r in rules]
    if any(any(x != "*" and x in a for x in agents) for agents, _ in groups):
        return named
    return [r for agents, rules in groups if "*" in agents for r in rules]


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


def classify_robots_status(code: int | None) -> str:
    """How the robots.txt answer reads under the 2026-11-10 ruling (2xx is parsed by the caller)."""
    if code is not None and 200 <= code < 300:
        return R_ALLOWED
    if code in HARD_STOP:
        return R_REFUSED
    if code is not None and 400 <= code < 500:
        return R_ABSENT
    return R_UNREACHABLE


class RobotsGate:
    """Per-host robots.txt, read once per gate and cached. Thread-safe."""

    def __init__(self, get: Callable[[str], tuple[int | None, str]],
                 agent: str = "quant-research") -> None:
        self._get = get
        self._agent = agent
        self._rules: dict[str, tuple[Rules | None, str]] = {}
        self._lock = threading.Lock()
        self.counts: dict[str, int] = {}

    def _host_rules(self, scheme: str, host: str) -> tuple[Rules | None, str]:
        with self._lock:
            if host in self._rules:
                return self._rules[host]
        try:
            code, body = self._get(f"{scheme}://{host}/robots.txt")
        except Exception:
            code, body = None, ""
        kind = classify_robots_status(code)
        rules: Rules | None
        if kind == R_ALLOWED:
            rules = robots_rules(body, self._agent)
        elif kind == R_ABSENT:
            rules = []
        else:
            rules = None
        with self._lock:
            self._rules.setdefault(host, (rules, kind))
            return self._rules[host]

    def _verdict(self, url: str) -> tuple[str, str]:
        p = urllib.parse.urlsplit(url)
        host = p.netloc.lower()
        if not host:
            return UNREAD, R_UNREACHABLE
        rules, kind = self._host_rules(p.scheme or "https", host)
        if rules is None:
            return UNREAD, kind
        if robots_allows(rules, url):
            return ALLOWED, kind
        return DISALLOWED, R_DISALLOWED

    def reason(self, url: str) -> str:
        """The ruling's case for this URL (reads robots.txt if not yet cached; not counted)."""
        return self._verdict(url)[1]

    def check(self, url: str) -> str:
        verdict, why = self._verdict(url)
        with self._lock:
            self.counts[why] = self.counts.get(why, 0) + 1
        return verdict
