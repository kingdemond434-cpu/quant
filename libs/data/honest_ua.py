"""THE DESK'S ONE HONEST USER-AGENT (2026-11-18).

The desk's fetch law: every automated request names what is reading, so a host's robots.txt and
its operators can address us, and nothing the desk sends impersonates a browser. Before this
module, 88 fetchers carried a desktop-Chrome string (and one carried a personal e-mail address).

The token before the slash is ``ROBOTS_AGENT``, the name robots.txt rules are matched against
(the same token ``deep_forest_miner`` and ``alpha_capture`` already declare). The string names no
person, account or repository owner: the repository is public, and a client name is not a place
to publish who runs it.

A host that answers this name with 401/403/429/451 has REFUSED us. That is a hard stop and an
honest BLOCKED verdict with its missed_growth line; it is never a cue to retry under a browser's
name. ``tests/governance/test_honest_user_agent.py`` fences the whole tree against a browser
string coming back.
"""
from __future__ import annotations

#: The token robots.txt rules are matched against.
ROBOTS_AGENT = "quant-desk-research"
#: The User-Agent every desk fetcher sends.
HONEST_UA = f"{ROBOTS_AGENT}/1.0 (automated research; honours robots.txt)"
#: Ready-made headers for callers that only need the name.
HONEST_HEADERS: dict[str, str] = {"User-Agent": HONEST_UA}
