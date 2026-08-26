"""Central bank statement miner -- DATED point-in-time document stream.

REPAIR 2026-08-26 (unified frontier dig). The previous implementation scraped each bank's
HTML *landing page*, kept the first 2000 characters after tag-stripping (i.e. navigation
chrome), and counted policy keywords in it. It was structurally incapable of producing what
the desk's two absent-but-reachable families need:

  * NO TIMESTAMP anywhere in the output -> no event series, so `event_reaction` (needs an
    economic calendar) and `macro_conditional` (needs a macro state series) could never be
    fed by it. `scripts/check_miner_conversion.py` had it in the zero-yield list: 20+ rows,
    zero survivors in 14d.
  * `_extract_symbols` matched instrument tickers as literal substrings of a central bank's
    landing page. "EURUSD" does not appear on federalreserve.gov, so it returned [] on every
    run and the fallback `f"{currency}USD"` emitted "USDUSD" for the Fed -- not an instrument.
  * `confidence = keyword_count * 0.3` is a popularity score, not a mechanism (RESEARCH: social
    proof is never evidence).

The route this file now uses was probed live on 2026-08-26: every feed below returned HTTP 200
keyless with a per-item publication stamp (Fed/ECB/BoJ/BoE/RBA/BoC pubDate, BIS dc:date). The
stamp is the point-in-time property the old version lacked -- it is what makes an event study
admissible at all, so a row without one is DROPPED rather than emitted undated.

This miner produces ATTENTION (a dated pointer to ground), never a verdict. It applies no
threshold in either direction: the canonical ten gates decide (LAWS L1.60).
"""

from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "central_banks"
OUT.mkdir(parents=True, exist_ok=True)

#: Append-only dated archive. One JSON object per document, keyed by (bank, link).
ARCHIVE = OUT / "cb_documents.jsonl"

#: SEED, not a boundary (LAWS §1 anti-hardcode law): every entry is a feed the 2026-08-26 probe
#: confirmed live and dated. Adding a central bank is adding a row, never editing logic.
FEEDS: dict[str, dict[str, str]] = {
    "Fed": {"url": "https://www.federalreserve.gov/feeds/press_monetary.xml", "currency": "USD"},
    "ECB": {"url": "https://www.ecb.europa.eu/rss/press.html", "currency": "EUR"},
    "BoJ": {"url": "https://www.boj.or.jp/en/rss/whatsnew.xml", "currency": "JPY"},
    "BoE": {"url": "https://www.bankofengland.co.uk/rss/news", "currency": "GBP"},
    # RBA: BOTH published feed paths return HTTP 403 from this box under two distinct UAs
    # (probed 2026-08-26) -- an edge block on the IP, NOT an absent feed. The row stays so the
    # miner REPORTS the dead leg every run instead of AUD silently having no coverage; the
    # replacement route (§38) is owed. Absence must never read as a clean verdict (WS-005).
    "RBA": {"url": "https://www.rba.gov.au/rss/rss-cb-media-releases.xml", "currency": "AUD"},
    "BoC": {"url": "https://www.bankofcanada.ca/content_type/press-releases/feed/", "currency": "CAD"},
    "BIS": {"url": "https://www.bis.org/doclist/cbspeeches.rss", "currency": "XXX"},
}

#: Currency -> the MT5/Fusion instruments whose price a statement by that bank moves. Derived
#: from the currency, NEVER from substring-matching a ticker against the document text.
_CCY_INSTRUMENTS: dict[str, tuple[str, ...]] = {
    "USD": ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "XAUUSD"),
    "EUR": ("EURUSD", "EURJPY", "EURGBP", "EURAUD", "EURCHF"),
    "JPY": ("USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"),
    "GBP": ("GBPUSD", "GBPJPY", "EURGBP", "GBPAUD"),
    "AUD": ("AUDUSD", "AUDJPY", "AUDNZD", "AUDCAD", "EURAUD"),
    "CAD": ("USDCAD", "CADJPY", "NZDCAD", "AUDCAD"),
    "CHF": ("USDCHF", "EURCHF", "CHFJPY"),
    "NZD": ("NZDUSD", "NZDJPY", "NZDCAD", "AUDNZD"),
    "XXX": (),  # BIS speaks about everyone; the reader picks the leg, this miner does not guess.
}

_POLICY_KEYWORDS: tuple[str, ...] = (
    "hawkish", "dovish", "rate hike", "rate cut", "tightening", "easing",
    "quantitative easing", "taper", "pause", "hold", "inflation target",
    "price stability", "forward guidance", "intervention", "yield curve control",
)

_ITEM_RE = re.compile(r"<item[\s>].*?</item>|<item>.*?</item>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def _field(block: str, tag: str) -> str:
    """Return the text of ``tag`` inside ``block``, CDATA-unwrapped and whitespace-collapsed."""
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.S | re.I)
    if not m:
        return ""
    raw = m.group(1).strip()
    cd = re.match(r"^<!\[CDATA\[(.*?)\]\]>$", raw, re.S)
    if cd:
        raw = cd.group(1)
    return " ".join(html.unescape(_TAG_RE.sub(" ", raw)).split())


def _parse_stamp(raw: str) -> str | None:
    """Normalise an RSS/RDF publication stamp to a UTC ISO-8601 string, or None if absent.

    NONE IS A REAL ANSWER (L1.28a): an undated document is dropped, never emitted with a
    fabricated `now` stamp -- a collection timestamp standing in for a publication timestamp
    is exactly the clock-provenance defect L1.46 names.
    """
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).astimezone(UTC).isoformat()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC).isoformat()
    except ValueError:
        return None


def _extract_policy_signals(text: str) -> list[str]:
    low = text.lower()
    return [k for k in _POLICY_KEYWORDS if k in low]


def parse_feed(body: str, bank: str, currency: str, url: str) -> list[dict[str, Any]]:
    """Parse one feed body into dated document rows. Pure -- no network, so it is testable."""
    rows: list[dict[str, Any]] = []
    blocks = _ITEM_RE.findall(body)
    if not blocks:  # RDF feeds (BIS) use <item rdf:about=...> which the RE above also catches.
        blocks = re.findall(r"<item\b.*?</item>", body, re.S | re.I)
    for block in blocks:
        stamp = _parse_stamp(_field(block, "pubDate") or _field(block, "dc:date"))
        if stamp is None:
            continue  # undated -> unusable for an event study; dropped, and the drop is counted.
        title = _field(block, "title")
        if not title:
            continue
        text = f"{title} {_field(block, 'description')}"
        rows.append({
            "source": "central_bank",
            "bank": bank,
            "currency": currency,
            "feed": url,
            "published_utc": stamp,
            "title": title,
            "link": _field(block, "link") or _field(block, "guid"),
            "policy_signals": _extract_policy_signals(text),
            "instruments": list(_CCY_INSTRUMENTS.get(currency, ())),
        })
    return rows


def _seen_keys() -> set[str]:
    if not ARCHIVE.exists():
        return set()
    keys: set[str] = set()
    with ARCHIVE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            keys.add(f"{row.get('bank')}|{row.get('link')}")
    return keys


def mine_central_banks() -> list[dict[str, Any]]:
    """Fetch every seeded feed and return the DATED rows not already archived."""
    fresh: list[dict[str, Any]] = []
    seen = _seen_keys()
    for bank, info in FEEDS.items():
        try:
            resp = requests.get(info["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            # A dead feed is a REPORTED fact, never a silent empty result (the heartbeat lesson).
            print(f"central_bank: {bank} feed unreachable -- {type(exc).__name__}: {exc}")
            continue
        for row in parse_feed(resp.text, bank, info["currency"], info["url"]):
            key = f"{row['bank']}|{row['link']}"
            if key in seen:
                continue
            seen.add(key)
            fresh.append(row)
    return fresh


def run_and_save() -> list[dict[str, Any]]:
    rows = mine_central_banks()
    if rows:
        with ARCHIVE.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    snap = OUT / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    snap.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(1 for _ in ARCHIVE.open(encoding="utf-8")) if ARCHIVE.exists() else 0
    print(f"central_bank: {len(rows)} new dated document(s); archive now {total} row(s) -> {ARCHIVE}")
    return rows


if __name__ == "__main__":
    run_and_save()
