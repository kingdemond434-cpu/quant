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

import urllib.error
import urllib.request
from typing import IO, Any
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
    "comtrade.un.org": "UN Comtrade: terms refuse automated use (ruling 2026-11-13)",
    "comtradeplus.un.org": "UN Comtrade: terms refuse automated use (ruling 2026-11-13)",
    "comtradeapi.un.org": "UN Comtrade: terms refuse automated use (ruling 2026-11-13)",
    "theice.com": "ICE: terms refuse automated collection of its data",
    "spdrgoldshares.com": ("SPDR Gold Shares terms: personal, non-commercial use only; no "
                           "access other than the website's navigational structure "
                           "(re-read 2026-11-17)"),
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
    return host_refusal(host)


#: The status word a refused fetch is recorded under: the repo's existing vocabulary for a
#: source refused by its own terms (axis_ingest, data_axis_miner, shadow_institutional).
STATUS = "BLOCKED_ON_TERMS"


def host_refusal(host: str) -> str | None:
    """Why a bare hostname may not be contacted, or None. Empty is not refused here: a caller
    holding no host has no request to make (``refusal`` refuses an unparseable URL)."""
    h = str(host or "").lower().rstrip(".")
    if not h:
        return None
    for domain, why in REFUSED_HOSTS.items():
        if h == domain or h.endswith("." + domain):
            return why
    return None


class RefusedSource(urllib.error.URLError):
    """A request to a host whose terms refuse automated contact. Raised BEFORE the wire, so every
    caller that already handles a failed fetch (URLError) handles a refusal the same way, and the
    message carries the status word so it is never read as an outage."""


def guard(url: str) -> None:
    """Raise ``RefusedSource`` when ``url`` may not be contacted; return None otherwise. The one
    line every transport puts in front of its socket."""
    why = refusal(url)
    if why:
        raise RefusedSource(f"{STATUS}: {why}")


class RefusedRedirect(urllib.error.URLError):
    """A redirect whose target host is refused on terms. Raised before the hop is requested."""


class RefusingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Checks every redirect hop against the list: a lawful host that redirects to a refused
    one never causes the refused host to be contacted."""

    def redirect_request(self, req: urllib.request.Request, fp: IO[bytes], code: int,
                         msg: str, headers: Any, newurl: str) -> urllib.request.Request | None:
        why = refusal(newurl)
        if why:
            raise RefusedRedirect(f"BLOCKED_ON_TERMS: redirect target refused ({why})")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def opener(*handlers: urllib.request.BaseHandler) -> urllib.request.OpenerDirector:
    """An opener whose redirects are checked hop by hop against the refused list."""
    return urllib.request.build_opener(RefusingRedirectHandler(), *handlers)
