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
request with a browser User-Agent returned data on the first try. (Since 2026-11-18 the desk
sends its own declared name, libs/data/honest_ua.py, never a browser's: a host that refuses that
name has refused the desk, and that is recorded, not routed around.)

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

from libs.data.honest_ua import HONEST_UA, REFUSAL_STATUS, refusal_row

#: THE DESK'S HONEST User-Agent (2026-11-18). This was a desktop-Chrome string; the desk's fetch
#: law forbids impersonating a browser, so every request now names what is reading
#: (libs/data/honest_ua.py). The name BROWSER_UA is kept only so existing importers resolve. A 403
#: to this name is the host's answer to the desk as it really is: record it as a refusal (a hard
#: stop with its missed_growth line), never retry it under a browser's name. The L0052 lesson
#: below still holds for the library default (``Python-urllib``), which is not a name the desk
#: chose and is never sent.
BROWSER_UA = HONEST_UA

DEFAULT_HEADERS = {"User-Agent": BROWSER_UA, "Accept": "application/json"}


class HostRefused(RuntimeError):
    """The host answered the honest name with 401/403/429/451: a HARD_STOP, final.

    ``row`` is the refused row (libs/data/honest_ua.refusal_row): host, status, the UA sent, the
    missed_growth line, ``retry: never`` and ``bypass: refused``. A RuntimeError so every existing
    ``except RuntimeError`` still catches it; a caller that records outcomes reads ``row``."""

    def __init__(self, row: dict[str, object]) -> None:
        super().__init__(f"{row['why']} ({row['url']}); {row['missed_growth']}")
        self.row = row


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
            exc.close()
            refused = refusal_row(url, status=exc.code, user_agent=hdr.get("User-Agent", ""))
            # 401/403/451 are final at once; a 429 is paced under the same name and is final
            # when it is still the answer on the last try. Never another User-Agent.
            if refused is not None and (exc.code != 429 or attempt == tries - 1):
                raise HostRefused(refused) from exc
            if 400 <= exc.code < 500 and exc.code not in REFUSAL_STATUS:
                raise RuntimeError(
                    f"HTTP {exc.code} from {url} -- a deterministic answer, not flakiness."
                ) from exc
            last = exc
        except Exception as exc:
            last = exc
        if attempt < tries - 1:
            time.sleep(backoff * (2 ** attempt))
    raise RuntimeError(f"GET failed after {tries} attempts: {url} :: {last}")
