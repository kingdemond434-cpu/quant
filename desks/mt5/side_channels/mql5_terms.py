"""MQL5 TERMS FENCE: no process on this desk fetches www.mql5.com. Fail-closed.

WHY. MQL5's Terms of Use prohibit what the desk's harvesters were doing, and the desk holds no
separate agreement with MetaQuotes Ltd that permits it:

    3.7   no access "through any automated means, including use of scripts, crawlers, or similar
          technologies";
    3.9   no reproducing, duplicating or copying the site's content;
    3.13  no copying, adapting or preparing derivative works from the software on the site.

The quotes below are verbatim from https://www.mql5.com/en/about/terms as read on 2026-10-06
(PR #231 recorded the same three clauses for the trader genome). A terms page that PROHIBITS is a
refusal in writing, so the rule here is fail-closed: no harvester, crawler, probe or rediscovery
loop opens an mql5.com URL. Unlike a robots or HTTP wall there is nothing to re-probe, because the
only thing that lifts this verdict is a permitting agreement, and that is a human act.

WHAT IS KEPT. Rows already harvested stay where they are as research history; nothing here
deletes them. They are never refetched, refreshed or extended.

WHAT A REFUSAL LOOKS LIKE. Each harvester still runs on its schedule and writes a `walled` row
with `verdict: BLOCKED_TERMS` (the compiler and the miner-health fence already treat `walled` as
operational, never as evidence), so the hour records a refusal rather than a silence. The seat
censuses (`check_seat_health`, `check_producer_yield`, `libs/ops/producer_census`) read
`MQL5_SEATS` and report those seats BLOCKED_TERMS -- never stale, unfed, dead or dark.

Stdlib only, and nothing is imported at module load that could open a socket.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

STATUS = "BLOCKED_TERMS"
REASON = "MQL5 ToU 3.7/3.9/3.13: automated access not permitted"
TERMS_URL = "https://www.mql5.com/en/about/terms"
CHECKED_AT = "2026-10-06"
#: Every host the fence refuses. A subdomain of either is refused too (`is_mql5_url`).
HOSTS: tuple[str, ...] = ("www.mql5.com", "mql5.com")

#: Verbatim, clause by clause, from TERMS_URL on CHECKED_AT.
CLAUSES: dict[str, str] = {
    "3.7": ("You agree not to use the website www.mql5.com by any means other than through the "
            "interface that is provided by MetaQuotes Ltd on www.mql5.com or the MetaTrader "
            "Software interface, unless You have been specifically allowed to do so in a "
            "separate agreement with MetaQuotes Ltd. You specifically agree not to access the "
            "website www.mql5.com through any automated means, including use of scripts, "
            "crawlers, or similar technologies."),
    "3.9": ("You agree that You will not reproduce, duplicate, copy, sell, trade or resell the "
            "content of the website www.mql5.com, unless you have been specifically permitted "
            "to do so in a separate agreement with MetaQuotes Ltd."),
    "3.13": ("You agree that You will not, and will not allow any third party to, (I) copy, "
             "sell, license, distribute, transfer, modify, adapt, translate, prepare derivative "
             "works from, decompile, reverse engineer, disassemble or otherwise attempt to "
             "derive the source code of the software located on the website www.mql5.com, "
             "unless otherwise permitted"),
}

#: THE TERMS_EVIDENCE RECORD (same keys as `alt_proxies.TERMS_EVIDENCE`, plus the verdict).
MQL5_TERMS: dict[str, Any] = {
    "host": "www.mql5.com",
    "hosts": list(HOSTS),
    "verdict": "PROHIBITS",
    "status": STATUS,
    "reason": REASON,
    "terms_url": TERMS_URL,
    "prohibiting_quote": " ".join(f'{k}: "{v}"' for k, v in CLAUSES.items()),
    "clauses": dict(CLAUSES),
    "permitting_clause": None,
    "checked_at": CHECKED_AT,
    "recorded_in": "PR #231 (book_forensics TERMS_EVIDENCE) and this module",
}

#: The five harvesters this fence was written for, by the source name each one stamps.
HARVESTERS: tuple[str, ...] = ("mql5_signals", "mql5_survivors", "mql5_forum", "mql5_articles",
                               "mql5_codebase")
#: Intelligence seat directories that only ever held mql5.com output. Every census reports these
#: as BLOCKED_TERMS. `mql5_catalog`, `mql5_prospector` and `mql5_reputation` were retired earlier
#: with an inheritor; their inheritors are themselves fenced now.
MQL5_SEATS: frozenset[str] = frozenset({"mql5", "mql5_signals", "mql5_survivors",
                                        "mql5_catalog", "mql5_prospector", "mql5_reputation"})

#: The SOURCE_WALLS entry (seed_miners): `probe: never`, because no fetch of any kind -- not
#: robots.txt, not the target page -- can lift a written prohibition.
WALL: dict[str, Any] = {
    "verdict": STATUS,
    "host": "www.mql5.com",
    "evidence": f"{REASON}. {MQL5_TERMS['prohibiting_quote']}"[:1500],
    "probe": "never",
    "url": TERMS_URL,
    "since": CHECKED_AT,
}


class MQL5TermsRefused(PermissionError):
    """Raised by `guard` instead of opening an mql5.com URL."""


#: An mql5.com host named INSIDE another URL: an archive snapshot (web.archive.org/web/2024/
#: https://www.mql5.com/...), a reader proxy (r.jina.ai/https://www.mql5.com/...), a cache or
#: translate wrapper (...?url=https%3A%2F%2Fwww.mql5.com...). Each of those fetches MQL5's
#: content by automated means through a third party, which ToU 3.7/3.9 refuse just the same.
_WRAPPED = re.compile(r"(?:^|[^a-z0-9-])(?:[a-z0-9-]+\.)*mql5\.com(?:[/:?#&]|$)", re.I)


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return unicodedata.normalize("NFKC", host).rstrip(".")


def is_mql5_url(url: object) -> bool:
    """True for any URL whose host is mql5.com or a subdomain of it, or that wraps such a URL
    in its path, query or fragment (archives, reader proxies, caches). Fullwidth and other
    compatibility forms of the host are folded first. Never raises."""
    try:
        text = str(url)
        host = _host(text)
        if any(host == h or host.endswith("." + h) for h in HOSTS):
            return True
        parts = urlparse(text)
        tail = unicodedata.normalize("NFKC", unquote(unquote(
            f"{parts.path}?{parts.query}#{parts.fragment}")))
    except ValueError:
        return False
    return bool(_WRAPPED.search(tail))


def guard(url: object) -> None:
    """Call before any request. Raises MQL5TermsRefused for an mql5.com URL."""
    if is_mql5_url(url):
        raise MQL5TermsRefused(f"{STATUS}: {REASON} ({url})")


def refuse_redirect(resp: Any, *args: Any, **kwargs: Any) -> Any:
    """A `requests` response hook that refuses a redirect INTO mql5.com before it is followed.

    `requests` dispatches response hooks on every hop before `resolve_redirects` sends the next
    one, so raising here means the Location is never opened. A checked first URL is not enough:
    a link shortener or a moved page can 302 straight onto www.mql5.com.
    """
    guard(getattr(resp, "url", ""))
    if getattr(resp, "is_redirect", False):
        location = (getattr(resp, "headers", None) or {}).get("location") or ""
        guard(urljoin(str(getattr(resp, "url", "")), str(location)))
    return resp


#: Pass as `hooks=HOOKS` on any `requests` call that is not on a fenced session.
HOOKS: dict[str, list[Any]] = {"response": [refuse_redirect]}


def fence_session(session: Any) -> Any:
    """Make a `requests.Session` refuse mql5.com URLs before it opens a connection, including a
    redirect target."""
    opened = session.request

    def request(method: str, url: object, *args: Any, **kwargs: Any) -> Any:
        guard(url)
        return opened(method, url, *args, **kwargs)

    session.request = request
    session.hooks.setdefault("response", []).append(refuse_redirect)
    return session


def refusal_row(source: str, url: str = TERMS_URL) -> dict[str, Any]:
    """The `walled` row a refused harvester writes in place of its discoveries."""
    return {
        "source": source, "kind": "walled", "title": f"{STATUS}: {REASON}", "url": url,
        "text": MQL5_TERMS["prohibiting_quote"][:1500], "symbols": [],
        "found_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "verdict": STATUS, "status": STATUS, "reason": REASON,
        "terms_url": TERMS_URL, "walled_since": CHECKED_AT, "needs_selector_work": False,
    }


def refuse(source: str, out: Path | None = None) -> dict[str, Any]:
    """Record a refusal for `source` WITHOUT any request, and return the status.

    When `out` is given the refusal row is written there through the canonical discovery door
    (`discovery_io.write_discoveries`), so the seat's hourly artifact says BLOCKED_TERMS instead
    of nothing. The file name is fixed per harvester, so a refused hour overwrites the last one
    rather than adding a file per hour.
    """
    status: dict[str, Any] = {"source": source, "status": STATUS, "reason": REASON,
                              "terms_url": TERMS_URL, "requests_made": 0,
                              "artifact": str(out) if out is not None else None}
    if out is not None:
        try:
            from side_channels.discovery_io import write_discoveries
        except ModuleNotFoundError:
            here = str(Path(__file__).resolve().parent)
            if here not in sys.path:
                sys.path.insert(0, here)
            from discovery_io import write_discoveries
        write_discoveries(out, [refusal_row(source)])
    print(f"{source}: {STATUS} -- {REASON}; no request made")
    return status
