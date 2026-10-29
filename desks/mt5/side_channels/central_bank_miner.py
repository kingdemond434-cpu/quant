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

try:
    from libs.data import polite_fetch as _pf
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data import polite_fetch as _pf
DESK_UA = _pf.DESK_UA

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "central_banks"
OUT.mkdir(parents=True, exist_ok=True)

#: Append-only dated archive. One JSON object per document, keyed by (bank, link).
ARCHIVE = OUT / "cb_documents.jsonl"
#: The hourly leg's artifact (`hourly_cycle:central_bank_miner`): per feed what the pass got, the
#: refusal word when the polite door refused it, and the register row each feed reads under.
REPORT = BASE / "reports" / "CENTRAL_BANK_MINER.json"

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
    # BIS REMOVED 2026-08-28 (§13). https://www.bis.org/doclist/cbspeeches.rss lives under
    # `Disallow: /doclist/` in bis.org/robots.txt -- the access boundary is a hard limit, not a
    # preference, and this miner had been reading it. BIS's own RSS path now redirects to the
    # allowed listing page whose only content link is the free full-text research download at
    # /speeches/speeches.zip (no robots bar, terms allow noncommercial use). That corpus is
    # strictly better ground anyway -- 20,728 DATED speeches with BODIES back to 1996, against
    # this feed's headline-only stream -- and it is mined by side_channels/bis_speech_tone.py.
    # Its currency was "XXX", so no MT5 leg loses coverage by the removal.
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


def _feed_terms(url: str) -> dict[str, Any]:
    """The ONE register's reading of a feed URL. Every feed here yields ATTENTION (a dated
    pointer read for ideas), never a live data series, so an IDEAS_ONLY row does not stop it;
    the label is recorded so a consumer can see which pointers came from such a row."""
    try:
        from libs.data import terms_fence as tf
        pol = tf.policy_of_url(url)
        return {"policy_row": pol.get("source"), "status": pol.get("status")}
    except Exception as exc:  # the register unreadable is a reading too, never a pass
        return {"policy_row": None, "status": "UNMEASURED", "why": f"{type(exc).__name__}"}


def mine_central_banks(fetch: Any = None,
                       feed_log: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Fetch every seeded feed and return the DATED rows not already archived.

    EVERY FETCH GOES THROUGH THE POLITE DOOR (`polite_fetch.get`): the desk's honest UA, the
    feed origin's robots.txt asked first, and a 401/403/429 or challenge a HARD STOP that holds
    the site for a person (the RBA's edge 403 becomes that recorded hold, never a retry under
    another UA). `fetch` is the test seam (same signature as `polite_fetch.get`)."""
    get = fetch or _pf.get
    fresh: list[dict[str, Any]] = []
    seen = _seen_keys()
    for bank, info in FEEDS.items():
        entry: dict[str, Any] = {"bank": bank, "currency": info["currency"], "url": info["url"],
                                 **_feed_terms(info["url"])}
        resp = get(info["url"], timeout=20.0, retries=1, leg="central_bank_miner")
        if getattr(resp, "verdict", "") or not getattr(resp, "ok", False):
            # A dead or refused feed is a REPORTED fact, never a silent empty result.
            entry.update({"state": "REFUSED" if resp.verdict else "FAILED",
                          "verdict": resp.verdict or None, "http_status": resp.status,
                          "error": (resp.error or "")[:200]})
            print(f"central_bank: {bank} feed not read -- {resp.verdict or resp.status} "
                  f"{(resp.error or '')[:120]}")
            if feed_log is not None:
                feed_log.append(entry)
            continue
        rows = parse_feed(resp.text, bank, info["currency"], info["url"])
        new = 0
        for row in rows:
            key = f"{row['bank']}|{row['link']}"
            if key in seen:
                continue
            seen.add(key)
            fresh.append(row)
            new += 1
        entry.update({"state": "OK", "http_status": resp.status, "dated_items": len(rows),
                      "new_items": new})
        if feed_log is not None:
            feed_log.append(entry)
    return fresh


def run_and_save(fetch: Any = None, report: Path | None = None) -> list[dict[str, Any]]:
    feed_log: list[dict[str, Any]] = []
    rows = mine_central_banks(fetch, feed_log)
    if rows:
        with ARCHIVE.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        # an hour with nothing new writes no empty snapshot: the compiler reads every file here
        snap = OUT / f"discoveries_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
        try:
            from side_channels.discovery_io import write_discoveries
        except ModuleNotFoundError:
            from discovery_io import write_discoveries
        rows = write_discoveries(snap, rows)
    total = sum(1 for _ in ARCHIVE.open(encoding="utf-8")) if ARCHIVE.exists() else 0
    print(f"central_bank: {len(rows)} new dated document(s); archive now {total} row(s) -> {ARCHIVE}")
    read = sum(1 for e in feed_log if e.get("state") == "OK")
    doc = {
        "generated_at": datetime.now(UTC).isoformat(),
        "organ": "desks/mt5/side_channels/central_bank_miner.py",
        "leg": "hourly_cycle:central_bank_miner",
        "feeds": feed_log,
        "feeds_read": read, "feeds_total": len(FEEDS),
        # nothing read is UNMEASURED, never "no new documents"
        "new_documents": len(rows) if read else "UNMEASURED",
        "archive_rows": total, "archive": "desks/mt5/data/intelligence/central_banks/"
                                          "cb_documents.jsonl",
        "consumer": ("data/intelligence/central_banks/discoveries_*.json -> the compiler "
                     "(data/intelligence/**); the archive feeds nlp_event_factors"),
        "rule": ("attention only (dated pointers read for ideas), never a live data series; "
                 "every fetch through polite_fetch.get (robots first, 401/403/429 a held site)"),
    }
    out = report or REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(out)
    return rows


if __name__ == "__main__":
    import argparse as _argparse
    _ap = _argparse.ArgumentParser(description="dated central-bank document stream")
    _ap.add_argument("--once", action="store_true", help="one pass (the default)")
    _ap.parse_args()
    run_and_save()
