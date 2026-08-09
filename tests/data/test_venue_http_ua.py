"""L0052, graduated into enforcement -- the browser UA is the difference between data and a
false BLOCKED verdict.

THE COST THIS PINS. On 2026-08-01 the permutation study recorded OKX as BLOCKED off an HTTP 403
that was actually a bot-filter rejecting Python-urllib's default User-Agent; the identical request
with a browser UA returned full data. An honestly-recorded wrong diagnosis outlives the outage it
describes -- the venue would have stayed "blocked" in every later plan. The remedy lives in
`libs/data/venue_http.py`; these tests make sure it cannot silently rot back to the library
default, which is precisely how the wrong verdict got written the first time.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.data.venue_http import BROWSER_UA, DEFAULT_HEADERS


def test_the_default_headers_carry_a_browser_ua_not_the_library_default() -> None:
    ua = DEFAULT_HEADERS.get("User-Agent", "")
    assert ua == BROWSER_UA
    assert ua.startswith("Mozilla/"), (
        "the User-Agent no longer impersonates a browser -- the OKX 403-that-was-not-a-block "
        "comes straight back (L0052)")
    assert "python" not in ua.lower() and "urllib" not in ua.lower()


def test_the_403_remedy_is_documented_at_the_seam_itself() -> None:
    """The instruction to re-check the UA before recording BLOCKED must live in the module that
    raises the error, where the person diagnosing a 403 is actually looking."""
    src = (Path(__file__).resolve().parents[2] / "libs/data/venue_http.py").read_text("utf-8")
    assert "403" in src and "User-Agent" in src
