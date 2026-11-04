"""MQL5 SOURCE POLICY ROW: www.mql5.com is IDEAS_ONLY. It is a per-source policy, not a ban.

PRINCIPAL RULING 2026-10-13: "no source should be banned". The category refusal this module once
enforced (every mql5.com fetch refused, every harvester walled BLOCKED_TERMS) is RETIRED. What stays
off is a METHOD -- getting past a login, paywall, CAPTCHA, rate limit or region lock -- and that is
enforced for every source alike by THE ONE FETCH DOOR (`libs.data.terms_fence.guarded_urlopen`,
re-exported as `libs.data.polite_fetch.fenced_urlopen`).

WHY IDEAS_ONLY AND NOT PUBLIC_PAGE. The site's own Terms of Use clause 3.7 names automated access,
and the desk holds no separate agreement with MetaQuotes Ltd. Its public pages are read politely,
at the harvesters' existing rate limits, for IDEAS -- a mechanism, an instrument, a parameter --
and the cell that results is built and judged on MT5's own data. An mql5 page is never a cell's
live input. Idea provenance never blocks a cell (rule 4).

ONE TABLE. The row (status, why, terms URL and the verbatim clause) lives in
`libs/data/terms_fence.SOURCE_POLICY["mql5"]`; this module is a read-only view of it, kept for the
callers and tests that import it. Stdlib only; nothing here opens a socket.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from libs.data import terms_fence as _tf  # noqa: E402

SOURCE = "mql5"
_ROW: dict[str, Any] = _tf.SOURCE_POLICY[SOURCE]
STATUS = _tf.status(SOURCE)
TERMS_URL = str(_ROW["terms"]["url"])
CHECKED_AT = str(_ROW["terms"]["checked_at"])
HOSTS: tuple[str, ...] = tuple(_ROW["hosts"])
#: Verbatim, clause by clause, from TERMS_URL on CHECKED_AT.
CLAUSES: dict[str, str] = dict(_ROW["terms"]["clauses"])
WHY = str(_ROW["why"])

#: The policy row, as `terms_fence.SOURCE_POLICY` holds it.
POLICY: dict[str, Any] = {
    "source": SOURCE,
    "status": STATUS,
    "why": WHY,
    "hosts": list(HOSTS),
    "terms_url": TERMS_URL,
    "clauses": dict(CLAUSES),
    "checked_at": CHECKED_AT,
    "live_input": _tf.input_source(SOURCE) is None,
}


def is_live_input_permitted() -> bool:
    """An IDEAS_ONLY source is never a cell's live input; reading it for ideas is permitted."""
    return _tf.input_source(SOURCE) is None
