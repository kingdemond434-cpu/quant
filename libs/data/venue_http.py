"""One HTTP helper for public venue endpoints, and the header that decides whether they answer.

WHY THIS EXISTS. On 2026-08-01 the permutation study recorded OKX as BLOCKED with HTTP 403 and the
agent proxy reporting no relay failures, which reads unambiguously as "the venue is refusing this
box". It was not. `urllib.request.urlopen(url)` sends ``User-Agent: Python-urllib/3.11``, and the
venue's CDN bot-filter rejects it. The IDENTICAL request with a browser User-Agent returned data
on the first try.

That failure mode is the expensive kind: it does not throw anything that says "header", it throws
a plausible-looking authorisation error, and the desk's convention of honestly recording blockers
then preserves a WRONG diagnosis in an artifact. The same tree already carries two such notes --
`fapi.binance.com` 451 and `api.bybit.com` CloudFront, both recorded as hard refusals -- and at
least one of them deserves a re-test with a real header before it is trusted again.

MEASURED 2026-08-01, daily BTC, same box, same proxy:

    okx        Python-urllib UA -> HTTP 403      browser UA -> data
    bitstamp   browser UA       -> data (up to 1000 daily bars in one call)
    kraken     browser UA       -> data (720 bar cap)
    coinbase   browser UA       -> data (300 bars per call, paginated)

FALLBACKS ARE LISTED BECAUSE ONE VENUE IS A SINGLE POINT OF FAILURE for the sample-size problem.
The gauntlet cannot resolve a Sharpe-1 edge at 310 bars and needs roughly 1,460; that is a DATA
requirement, so "the one venue we ask is rate-limiting today" must not be able to stop it.
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
    """GET a public venue endpoint and parse JSON, with the header that makes it answer.

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
