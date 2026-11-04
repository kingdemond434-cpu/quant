"""One HTTP helper for public JSON endpoints, and the header that decides whether they answer.

VENUE-NEUTRAL. This module names no host, hard-codes no base URL and knows nothing about any
market: the caller passes a full URL and gets parsed JSON back. It is kept in the MT5-only tree
because the defect it exists to prevent is a property of HTTP clients, not of any one data source,
and the MT5 desk's side-channel and reference-data fetches hit public endpoints exactly the same
way.

WHY THIS EXISTS. On 2026-08-01 a study recorded a public data endpoint as BLOCKED with HTTP 403,
with the agent proxy reporting no relay failures. The library default UA
(``Python-urllib/3.11``) had drawn the 403, and the request was then re-sent with a browser
User-Agent, which answered. That fix was impersonation and is REVERSED (auditor ruling
2026-10-14): the desk identifies itself as itself, `polite_fetch.DESK_UA`, everywhere.

WHAT A 403 MEANS NOW. A 403 to the desk's honest, named User-Agent is the venue's answer to the
desk, and it is recorded as METHOD_BLOCKED -- a site hold in the shared access state, with its
missed-growth line -- never re-tried with a browser string. A venue that answers only browsers is
a refused venue, not a reason to pretend to be one. 401 reads NEEDS_KEY, 429 is a hold rechecked
after 24h, and robots.txt LABELS every request (never refuses: LAWS 5e), as for every polite
fetch: this module is a JSON wrapper over `polite_fetch.get`, not a second HTTP client.

FALLBACKS MATTER BECAUSE ONE SOURCE IS A SINGLE POINT OF FAILURE for the sample-size problem. The
gauntlet cannot resolve a Sharpe-1 edge at 310 bars and needs roughly 1,460; that is a DATA
requirement -- met by another source that accepts the desk, never by a disguise.
"""

from __future__ import annotations

import json
from typing import Any

from libs.data import polite_fetch as _pf

#: The desk's honest User-Agent. Kept under its own name so a reader of this module sees what is
#: sent; it IS `polite_fetch.DESK_UA`, and `honest_headers` replaces any browser string a caller
#: tries to pass.
DESK_UA = _pf.DESK_UA

DEFAULT_HEADERS = {"User-Agent": DESK_UA, "Accept": "application/json"}


def get_json(
    url: str,
    *,
    tries: int = 4,
    timeout: float = 30.0,
    backoff: float = 1.0,
    headers: dict[str, str] | None = None,
) -> Any:
    """GET a public JSON endpoint politely and parse the reply.

    RETRIES ON TRANSPORT AND 5xx, NEVER ON A REFUSAL. 401/403/429 and a challenge record a site
    hold and raise at once; a robots.txt Disallow is a label, never a refusal; a 404 is a
    deterministic answer and is not retried. The exception message carries the verdict and status
    so the caller records what actually happened instead of "failed after 4 tries".
    """
    hdr = dict(DEFAULT_HEADERS)
    if headers:
        hdr.update(headers)
    r = _pf.get(url, headers=hdr, timeout=timeout, retries=max(0, tries - 1),
                backoff_s=backoff, leg="venue_http")
    if r.verdict:
        raise RuntimeError(
            f"{r.verdict} from {url} ({r.error}) -- a refusal of the desk's honest User-Agent, "
            "held for the site and never re-sent with a browser string (libs/data/venue_http)")
    if not r.ok:
        raise RuntimeError(f"GET failed after {r.attempts} attempt(s): {url} :: {r.error}")
    return json.loads(r.text)
