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
    # CENTRAL BANKS AND THE FX REGULATOR (read 2026-11-18, policy_doc_nlp row 47; the full
    # clauses are on their rows in desks/mt5/research/policy_doc_sources.json once #1344 lands).
    # The fullwidth comma in the clause is written as \uff0c so the quote stays verbatim.
    "safe.gov.cn": ("SAFE 法律声明 (read 2026-11-18): \"任何媒体、互联网站和商业机构不得利用"
                    "本网发布的内容进行商业性转载\uff0c也不得歪曲和篡改本网发布的内容。\" "
                    "\"经许可的媒体、网站可对本网内容进行非商业性转载\""),
    # MAS: the site terms govern www.mas.gov.sg; MAS datasets and its API carry their own licence
    # that allows commercial use, so only the website host is listed.
    "www.mas.gov.sg": ("MAS Terms of Use (read 2026-11-18): \"No Content ... may be reproduced, "
                       "republished, uploaded, posted, transmitted or distributed in any way ... "
                       "without the prior written permission of MAS\", except one copy \"for "
                       "your own personal non-commercial use\"; \"caching and links to, and the "
                       "framing of this Web Site or any of the Contents are prohibited\""),
    "rbi.org.in": ("RBI Disclaimer (read 2026-11-18): \"Except as set forth below, caching and "
                   "links to, and the framing of this Web Site or any of the contents are "
                   "prohibited.\" \"© Reserve Bank of India. All Rights Reserved.\""),
    "resbank.co.za": ("SARB Disclaimer (read 2026-11-18): the material on this website \"may not "
                      "be copied, reproduced, adapted, published or distributed in any form "
                      "whatsoever without the prior written consent of the South African "
                      "Reserve Bank.\""),
    "boj.or.jp": ("BoJ copyright page (read 2026-11-17, #1254): \"copying or reproduction of "
                  "the content for commercial purposes requires the Bank's prior permission\" "
                  "(Public Relations Department)"),
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
