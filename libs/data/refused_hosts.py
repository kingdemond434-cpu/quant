"""Hosts whose own terms refuse automated contact: one list, matched by domain suffix.

A route probe, a canary, a crawler page and a robots.txt read are all automated contact, so a
host on this list is refused before any of them builds a request. The match is the registrable
domain or any subdomain of it (``alfred.stlouisfed.org`` is FRED too), after lowercasing and
dropping userinfo, port and a trailing dot. An unparseable URL is refused: its host's terms
cannot be read, and unclear terms fail closed.

Only hosts whose refusal is settled are listed, each with the reading that settled it. A host
whose terms are merely unread is not here; each collector fails closed on those itself.
"""
from __future__ import annotations

from urllib.parse import urlsplit

#: domain -> why. Every entry is a settled terms refusal, not a guess.
REFUSED_HOSTS: dict[str, str] = {
    "stlouisfed.org": "FRED: refused for all automated fetches (terms ruling 2026-11-13)",
    "dukascopy.com": ("Dukascopy terms of use refuse bots and commercial use of its data "
                      "(data_universe_map.json dukascopy_bi5_datafeed_VERDICT)"),
    "yahoo.com": ("Yahoo terms s2(d)(9) refuse automated collection without express prior "
                  "permission"),
    "yahooapis.com": "Yahoo: the same terms cover its API host",
    "archive.org": "archive.org: terms refuse automated collection (ruling 2026-11-14)",
    "youtube.com": "YouTube: terms refuse automated access; the trading box never contacts it",
    "youtu.be": "YouTube: terms refuse automated access; the trading box never contacts it",
    "youtube-nocookie.com": "YouTube: terms refuse automated access",
    "ytimg.com": "YouTube: terms refuse automated access",
    "cboe.com": "Cboe: terms refuse automated collection of its data",
}


def host_of(url: str) -> str | None:
    """The lowercased hostname, or None when the URL does not parse to one."""
    try:
        host = urlsplit(str(url or "")).hostname
    except ValueError:
        return None
    return (host or "").lower().rstrip(".") or None


def refusal(url: str) -> str | None:
    """Why ``url`` may not be contacted, or None. A URL with no readable host is refused."""
    host = host_of(url)
    if host is None:
        return "the URL does not parse to a host, so its terms cannot be read"
    for domain, why in REFUSED_HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return why
    return None
