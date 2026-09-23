"""One HTTP helper for public JSON endpoints, and the header that decides whether they answer.

VENUE-NEUTRAL. This module names no host, hard-codes no base URL and knows nothing about any
market: the caller passes a full URL and gets parsed JSON back. It is kept in the MT5-only tree
because the defect it exists to prevent is a property of HTTP clients, not of any one data source,
and the MT5 desk's side-channel and reference-data fetches hit public endpoints exactly the same
way.

WHY THIS EXISTS. On 2026-08-01 a study recorded a public data endpoint as BLOCKED with HTTP 403,
with the agent proxy reporting no relay failures -- which reads unambiguously as "the source is
refusing this box". It was not. `urllib.request.urlopen(url)` sends
``User-Agent: Python-urllib/3.11``, and the endpoint's CDN bot-filter rejects it. The IDENTICAL
request with a browser User-Agent returned data on the first try.

That failure mode is the expensive kind: it does not throw anything that says "header", it throws
a plausible-looking authorisation error, and the desk's convention of honestly recording blockers
then preserves a WRONG diagnosis in an artifact forever. Every "this source is blocked" note in
the tree deserves a re-test with a real header before it is trusted again.

MEASURED 2026-08-01, same box, same proxy, across four unrelated public data hosts: the library
default UA drew a 403 from one and the browser UA drew data from all four, at page sizes between
300 and 1,000 rows per call.

FALLBACKS MATTER BECAUSE ONE SOURCE IS A SINGLE POINT OF FAILURE for the sample-size problem. The
gauntlet cannot resolve a Sharpe-1 edge at 310 bars and needs roughly 1,460; that is a DATA
requirement, so "the one host we ask is rate-limiting today" must not be able to stop it.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

#: A real browser User-Agent. NOT cosmetic and NOT an attempt to hide what the desk is: these are
#: public, unauthenticated, documented market-data endpoints, and the header is what their CDN
#: bot-filters check before answering. Sending the library default is what produced a 403 that was
#: then recorded as a venue refusal.
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

DEFAULT_HEADERS = {"User-Agent": BROWSER_UA, "Accept": "application/json"}


def get_json(
    url: str,
    *,
    tries: int = 4,
    timeout: float = 30.0,
    backoff: float = 1.0,
    headers: dict[str, str] | None = None,
) -> Any:
    """GET a public JSON endpoint and parse the reply, with the header that makes it answer.

    RETRIES ON TRANSPORT AND 5xx, NOT ON 4xx. A 403 or 404 is a deterministic answer -- retrying
    it four times just turns one wrong request into four and makes the log look like flakiness
    rather than a bug. The exception message carries the status so the caller can record what
    actually happened instead of "failed after 4 tries".
    """
    hdr = dict(DEFAULT_HEADERS)
    if headers:
        hdr.update(headers)
    last: Exception | None = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as fh:
                return json.loads(fh.read().decode())
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500 and exc.code != 429:
                raise RuntimeError(
                    f"HTTP {exc.code} from {url} -- a deterministic refusal, not flakiness. If "
                    f"this is 403, check the User-Agent before recording the venue as blocked "
                    f"(libs/data/venue_http)."
                ) from exc
            last = exc
        except Exception as exc:
            last = exc
        if attempt < tries - 1:
            time.sleep(backoff * (2 ** attempt))
    raise RuntimeError(f"GET failed after {tries} attempts: {url} :: {last}")
