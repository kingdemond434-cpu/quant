"""FRED and ALFRED are refused on their terms for every automated fetch (ruling 2026-11-13).

One place that says what the refusal is, so every door that used to reach a stlouisfed.org host
refuses in the same words: ``status`` BLOCKED_ON_TERMS, a ``reason`` that cites the ruling, and a
``missed_growth`` line naming what the desk gives up and when the route reopens.

The refusal is checked BEFORE a request is built. A key in the environment changes nothing.
Data already on disk (lake files, archives, caches, vintages) stays readable; only new fetches
are refused. Stdlib only, no side effects at import, so any organ can use it.

`desks/mt5/research/free_data.py` carries the same constants for the desk side (it sits in the
money closure, so it does not import this module); a test pins the two copies equal.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

RULING = "governance/fred-terms-ruling-2026-11-13.md"
STATUS = "BLOCKED_ON_TERMS"
#: The registrable domain. FRED, ALFRED, FRASER, the API host and fredaccount all sit under it.
DOMAIN = "stlouisfed.org"
REASON = (f"FRED/ALFRED ({DOMAIN}) terms refuse every automated fetch ({RULING}); "
          "nothing is requested, data already on disk stays readable")
MISSED_GROWTH: dict[str, str] = {
    "mechanism": "fred_terms_refusal",
    "what_is_lost": "fresh FRED/ALFRED series and vintages for the macro, rates and FX legs",
    "size": "UNMEASURED",
    "stand_in": ("primary publishers (Fed H.15/H.10/H.4.1, Treasury, BLS, BEA, ECB) and the "
                 "DBnomics mirrors of those publishers where a reader exists"),
    "reopens_when": "the St. Louis Fed grants written permission for automated use",
}


def is_fred_url(url: object) -> bool:
    """True when ``url`` points at stlouisfed.org or any subdomain of it."""
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return host == DOMAIN or host.endswith("." + DOMAIN)


def refusal(what: str = "") -> dict[str, Any]:
    """The refusal record a fenced door returns or writes beside its no-data shape."""
    out: dict[str, Any] = {"status": STATUS, "reason": REASON, "ruling": RULING,
                           "missed_growth": dict(MISSED_GROWTH)}
    if what:
        out["what"] = what
    return out


class FredTermsRefused(RuntimeError):
    """Raised by a door whose callers already handle a failed fetch by exception."""

    def __init__(self, what: str = "") -> None:
        super().__init__(f"{STATUS}: {what + ': ' if what else ''}{REASON}")
        self.record = refusal(what)
