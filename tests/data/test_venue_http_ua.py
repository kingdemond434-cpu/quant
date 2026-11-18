"""L0052, re-read under the fetch law (2026-11-18): an honest name, never the library default.

THE ORIGINAL COST. On 2026-08-01 the permutation study recorded a venue as BLOCKED off an HTTP 403
that was a bot-filter rejecting Python-urllib's default User-Agent. The remedy then was a browser
UA. The desk's fetch law has since forbidden impersonating a browser: every request names what is
reading, so a host's robots.txt and operators can address it. Half of L0052 still stands -- the
library default is never sent -- and the other half is reversed: a 403 to the desk's own declared
name is a real refusal, recorded as one, never retried under a browser's name.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.data.honest_ua import HONEST_UA, ROBOTS_AGENT
from libs.data.venue_http import BROWSER_UA, DEFAULT_HEADERS


def test_the_default_headers_carry_the_desks_honest_name() -> None:
    ua = DEFAULT_HEADERS.get("User-Agent", "")
    assert ua == BROWSER_UA == HONEST_UA
    assert ua.startswith(ROBOTS_AGENT + "/")
    assert "mozilla" not in ua.lower() and "chrome" not in ua.lower()


def test_the_library_default_is_never_what_goes_out() -> None:
    ua = DEFAULT_HEADERS["User-Agent"].lower()
    assert "python" not in ua and "urllib" not in ua


def test_the_403_rule_is_documented_at_the_seam_itself() -> None:
    """The reading of a 403 must live in the module that raises the error, where the person
    diagnosing it is looking: a refusal of the honest name is recorded, never routed around."""
    src = (Path(__file__).resolve().parents[2] / "libs/data/venue_http.py").read_text("utf-8")
    assert "403" in src and "User-Agent" in src and "never retry it under a browser" in src
