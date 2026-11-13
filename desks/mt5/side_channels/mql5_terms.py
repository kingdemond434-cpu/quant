"""MQL5 SOURCE POLICY ROW: www.mql5.com is IDEAS_ONLY. It is a per-source policy, not a ban.

PRINCIPAL RULING 2026-10-13: "no source should be banned". The category refusal this module once
enforced (every mql5.com fetch refused, every harvester walled BLOCKED_TERMS) is RETIRED. What stays
off is a METHOD -- getting past a login, paywall, CAPTCHA, rate limit or region lock -- and that is
enforced for every source alike by `libs.data.polite_fetch.fenced_urlopen` (a redirect into a login
wall is refused and every redirect hop stays visible on the response).

WHY IDEAS_ONLY AND NOT PUBLIC_PAGE. The site's own Terms of Use speak to automated access in
writing, and the desk holds no separate agreement with MetaQuotes Ltd. A source whose own terms
explicitly prohibit automated access stays IDEAS_ONLY: its public pages are read politely, at the
harvesters' existing rate limits, for IDEAS -- a mechanism, an instrument, a parameter -- and the
cell that results is built and judged on MT5's own data. An mql5 page is never a cell's live input.
Idea provenance never blocks a cell (rule 4). Whether to read these pages at all, given clause
3.7, is the principal's call and is recorded here so the clause is not lost.

The table lives here, minimal, because `libs/data/terms_fence.SOURCE_POLICY` is introduced on a
sibling branch (#162); when both land the row moves there unchanged.
Stdlib only; nothing here opens a socket.
"""
from __future__ import annotations

from typing import Any

SOURCE = "mql5"
STATUS = "IDEAS_ONLY"
TERMS_URL = "https://www.mql5.com/en/about/terms"
CHECKED_AT = "2026-10-06"
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

WHY = ("public pages read politely for ideas; ToU 3.7 names automated access, so an mql5 page "
       "is never live input data and no content is reproduced -- the cell trades on MT5 data")

#: The policy row, in the same shape as `terms_fence.SOURCE_POLICY` rows on #162.
POLICY: dict[str, Any] = {
    "source": SOURCE,
    "status": STATUS,
    "why": WHY,
    "hosts": list(HOSTS),
    "terms_url": TERMS_URL,
    "clauses": dict(CLAUSES),
    "checked_at": CHECKED_AT,
    "live_input": False,
}


def is_live_input_permitted() -> bool:
    """An IDEAS_ONLY source is never a cell's live input; reading it for ideas is permitted."""
    return False
