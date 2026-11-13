"""Hosts whose published terms refuse the desk's automated use: no request is ever sent.

FRED / ALFRED (Federal Reserve Bank of St. Louis), every host, website and API alike. Governance
ruling 2026-11-13 (governance/fred-terms-ruling-2026-11-13.md, read from fred.stlouisfed.org/
legal/ and /docs/api/terms_of_use.html):
  - the licence is "solely for your personal, non-commercial use";
  - the FAQ says "Don't do any data mining, scraping or extraction of FRED data";
  - Section II bars, for ALL users, use "in connection with the development or training of any
    software program or system or machine learning", which a trading system is;
  - third-party series (Cboe VIX/GVZ/OVX, ICE BofA, S&P ...) need the OWNER's permission, and
    "the Bank cannot give you such permission".
An API key changes none of it.

WHAT CALLERS DO ON A REFUSAL. Treat it exactly like a failed fetch: keep reading the LAST HELD
copy (LAWS 5e: a label routes use, it never drops a row) and never overwrite a held file with
an empty one. Public-domain US series move to their primary publishers (Fed, Treasury, BLS,
BEA, EIA, Census); third-party series come from their owner under the owner's terms or are
fenced.

missed_growth: until each primary-publisher replacement lands, the series it replaces is frozen
at its last held value, so any edge in its fresh prints goes unharvested; third-party series
with no lawful owner route (Cboe vol indices, ICE BofA spreads) stay fenced and untested.
"""
from __future__ import annotations

from urllib.parse import urlsplit

#: Registrable domain -> why. Every host under the domain is refused.
REFUSED_DOMAINS: dict[str, str] = {
    "stlouisfed.org": (
        "FRED/ALFRED terms refuse automated and system-building use (personal non-commercial "
        "licence; FAQ: no data mining, scraping or extraction; Section II: no use in "
        "developing any software system); governance ruling 2026-11-13 -- never fetched, "
        "the last held copy is read instead"),
}
#: Hosts under a refused domain exempted because THEIR OWN terms allow automated use, each with
#: the terms URL that says so. Empty: FRASER and the Bank's research pages are separate services,
#: but their terms have not been read as allowing it, so they are refused with the rest (fail
#: closed; Governance 2026-11-13). Add a host here only with its terms URL beside it.
EXEMPT_HOSTS: frozenset[str] = frozenset()
STATUS = "BLOCKED_TERMS"
OWNER_FENCED: dict[str, str] = {
    "VIXCLS": "Cboe", "VXVCLS": "Cboe", "GVZCLS": "Cboe", "OVXCLS": "Cboe", "VXNCLS": "Cboe",
    "VXDCLS": "Cboe", "EVZCLS": "Cboe", "BAMLH0A0HYM2": "ICE Data Indices",
    "BAMLC0A0CM": "ICE Data Indices", "SP500": "S&P Dow Jones Indices",
    "NASDAQCOM": "Nasdaq", "NIKKEI225": "Nikkei", "GOLDAMGBD228NLBM": "ICE Benchmark Admin",
    "GOLDPMGBD228NLBM": "ICE Benchmark Admin"}


def host_of(url: str) -> str:
    return (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower().rstrip(".")


def refused(url: str) -> str | None:
    """The refusal reason when `url` is on a terms-refused host, else None."""
    try:
        host = host_of(url)
    except ValueError:
        return None
    if host in EXEMPT_HOSTS:
        return None
    for dom, why in REFUSED_DOMAINS.items():
        if host == dom or host.endswith("." + dom):
            return f"{why} [{host}]"
    return None


class TermsRefused(RuntimeError):
    """Raised by a fetch path in place of a request; callers treat it as a failed fetch."""


def guard(url: str) -> None:
    """Raise TermsRefused before any request to a refused host."""
    why = refused(url)
    if why:
        raise TermsRefused(why)
