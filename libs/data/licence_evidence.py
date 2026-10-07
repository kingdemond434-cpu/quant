"""Licence evidence for a data source, verified FAIL CLOSED.

A source may be fetched only when a stored quote of its licence's PERMITTING clause (free,
worldwide, use including commercial use, with attribution) was read from the licensor's own
host. Three ways a matcher can lie, each closed here (audit of #263, 2026-10-07):

  * a NEGATED or PROHIBITING sentence ("commercial use is not permitted", "prohibits commercial
    exploitation", "worldwide ... except commercial") carries the right words and the opposite
    meaning, so any negation or prohibition in the quoted clause refuses it;
  * a licence link from ANY host was followed and believed, so only the licensor's hosts count
    (`ALLOWED_HOSTS`, https only);
  * Creative Commons text is published everywhere, so CC BY 4.0 wording proves nothing about a
    dataset unless the licensor's own host served it -- the same host rule, applied to it too.

`verified(ev)` is the one test both the ERA5 reader and the paid-substitute engine apply to an
evidence file: `confirmed` on its own is a word, not evidence.
"""
from __future__ import annotations

import html as _html
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

#: The licensor's hosts for Copernicus/ECMWF data: exactly cds.climate.copernicus.eu, or any
#: subdomain of copernicus.eu or ecmwf.int. https only.
ALLOWED_EXACT = ("cds.climate.copernicus.eu",)
ALLOWED_SUFFIXES = (".copernicus.eu", ".ecmwf.int")

CC_BY_GRANT = re.compile(
    r"the licensor hereby grants you a worldwide, royalty-free, non-sublicensable, "
    r"non-exclusive, irrevocable license to exercise the licensed rights in the licensed "
    r"material to: a\. reproduce and share the licensed material, in whole or in part; and "
    r"b\. produce, reproduce, and share adapted material\.")
KINDS = ("cc-by-4.0", "licence_clause")

#: Anything that negates, restricts or conditions a grant. Deliberately broad: a false refusal
#: costs a human read; a false confirmation costs a licence breach.
_PROHIBIT = re.compile(
    r"\b(?:not|no|never|nor|cannot|can't|won't|mustn't|shan't|without|unless|except|excepting|"
    r"excluding|exclude[sd]?|only)\b"
    r"|prohibit|forbid|forbade|disallow|restrict|refus|\bden(?:y|ied|ies)\b|banned|\bbars?\b"
    r"|non-?commercial|noncommercial|n't\b")
_NONCOMMERCIAL = re.compile(r"non-?commercial|noncommercial")
_COMMERCIAL = re.compile(r"(?<!non-)(?<!non )\bcommercial")
_FREE = re.compile(r"free of charge|royalty-free|\bfree\b")


def norm(text: str) -> str:
    t = _html.unescape(text)
    t = t.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip()


def allowed_url(url: str | None) -> bool:
    """Is ``url`` an https URL on a Copernicus/ECMWF host?"""
    try:
        parts = urlsplit(str(url or ""))
    except ValueError:
        return False
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme != "https" or not host:
        return False
    return host in ALLOWED_EXACT or any(host.endswith(s) for s in ALLOWED_SUFFIXES)


def prohibited(clause: str) -> bool:
    """Does the clause negate, restrict or prohibit anything?"""
    return _PROHIBIT.search(norm(clause).lower()) is not None


def _cc(low: str) -> str:
    return re.sub(r"\s*([ab])\.\s+", r" \1. ", low)


def permitting_clause(text: str, url: str | None) -> dict[str, str] | None:
    """The permitting clause of a licence text served by ``url``, verbatim, or None.

    None when the URL is not a licensor host, when the text restricts use to non-commercial
    anywhere, when it never asks for attribution, or when the only candidate clause negates or
    prohibits something."""
    if not allowed_url(url):
        return None
    n = norm(text)
    low = n.lower()
    if _NONCOMMERCIAL.search(low) or re.search(r"attribut|acknowledg", low) is None:
        return None
    if CC_BY_GRANT.search(_cc(low)) and "creative commons attribution 4.0" in low:
        i = low.find("the licensor hereby grants you")
        j = low.find("share adapted material.", i)
        if i >= 0 and j > i:
            quote = n[i:j + len("share adapted material.")]
            if clause_holds("cc-by-4.0", quote, url):
                return {"kind": "cc-by-4.0", "quote": quote}
    for sent in re.split(r"(?<=[.;])\s+", n):
        if clause_holds("licence_clause", sent, url):
            return {"kind": "licence_clause", "quote": sent.strip()}
    return None


def clause_holds(kind: str, quote: str, url: str | None) -> bool:
    """Re-read a STORED quote against its URL: does it still say what was accepted?"""
    low = norm(quote).lower()
    if not low or not allowed_url(url) or prohibited(low):
        return False
    if kind == "cc-by-4.0":
        return CC_BY_GRANT.search(_cc(low)) is not None
    if kind == "licence_clause":
        return ("worldwide" in low and _FREE.search(low) is not None
                and _COMMERCIAL.search(low) is not None)
    return False


def verified(ev: Any) -> tuple[bool, str]:
    """(ok, why) for an evidence document. ok only for verdict `confirmed` with an allowed
    `terms_url`, a known `kind`, a quote that re-reads as permitting, `sha256` and `checked_at`."""
    if not isinstance(ev, Mapping):
        return False, "no evidence document"
    if str(ev.get("verdict") or "").lower() != "confirmed":
        return False, f"verdict is {ev.get('verdict')!r}, not confirmed"
    url = str(ev.get("terms_url") or "")
    if not allowed_url(url):
        return False, f"terms_url {url!r} is not a Copernicus/ECMWF https host"
    kind = str(ev.get("kind") or "")
    if kind not in KINDS:
        return False, f"unknown clause kind {kind!r}"
    if not clause_holds(kind, str(ev.get("terms_quote") or ""), url):
        return False, "the stored quote does not read as a permitting clause (or prohibits)"
    if not ev.get("sha256") or not ev.get("checked_at"):
        return False, "evidence lacks sha256 or checked_at"
    return True, "verified"
