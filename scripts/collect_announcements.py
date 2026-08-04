#!/usr/bin/env python3
"""UNSTRUCTURED EVENT COLLECTOR (R0122b) -- the feed the LLM discretionary sleeve actually trades.

WHAT MAKES THIS MORE THAN A SCRAPER, and it is the whole reason it is worth building: it measures
ITS OWN INFORMATION LATENCY. Every item carries `published_at` (when the world learned) and
`first_seen` (when THIS desk learned), and their difference is the only number that decides
whether an event-reading strategy can exist at all. If the desk sees a listing announcement 90
seconds after publication and the market takes ten minutes to finish pricing it, there is a
window. If the desk sees it two hours later, there is no edge and the sleeve must be told so
rather than trading into an already-priced event. A scraper that cannot answer "was I early?"
produces confident noise -- that is the difference between an information edge and a news reader.

SOURCES, all public and unauthenticated (s13 legitimacy gate; no logins, no paywalls, no
closed groups). Each is independent, and a source that fails is RECORDED as failed rather than
silently contributing nothing -- three dead sources and one live one must never look like a quiet
news day:
  * exchange announcement APIs  -- listings, delistings, contract-spec changes, margin-tier
    changes, maintenance windows. The highest-value class: a spec change FORCES repositioning.
  * DefiLlama hacks feed        -- chain incidents and exploits, which move whole sectors.
  * public RSS                  -- broad crypto press, for context rather than for the edge.

THE DESK'S OWN DISCIPLINE APPLIED TO NEWS:
  * DEDUP BY CONTENT HASH across runs -- an item seen yesterday is not news today, and a
    collector that re-emits it manufactures fake events for the sleeve to trade.
  * MATERIALITY is scored, never assumed: a delisting is not a UI update. The keyword tiers here
    are a cheap PRE-FILTER only -- the LLM does the real judging, because that is exactly the
    reading task it is better at than a regex.
  * SYMBOLS EXTRACTED so a call can name what it trades.
  * APPEND-ONLY, so the record of what the desk knew and WHEN survives -- that history is itself
    moat (nobody else has our first_seen stamps).

    python scripts/collect_announcements.py [--once] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = "data/exchange_announcements.jsonl"
_SEEN = "data/.announcement_hashes.json"
_STATUS = "data/announcement_collector.json"
_UA = "quant-desk-research/1.0 (public-endpoint reader)"
_TIMEOUT = 20

#: An event older than this is HISTORY, not news. THE FIRST LIVE RUN PROVED WHY THIS IS NOT
#: optional: DefiLlama's hacks endpoint returns the full historical archive, so the collector
#: cheerfully ingested the 2021 CREAM exploit ($130M) as a tier-1 event with a 2.5-million-minute
#: latency. Without this gate the sleeve would have traded three-year-old news as breaking. The
#: threshold is generous because prose events price over hours, not seconds -- the point is to
#: exclude ARCHIVES, not to chase latency the desk cannot win anyway.
TRADEABLE_MAX_AGE_MIN = 24 * 60

#: MATERIALITY TIERS -- a cheap pre-filter, deliberately not the decision. Tier 1 events FORCE
#: someone to reposition, which is the mechanism class the sleeve is allowed to trade.
_TIER1 = ("delist", "will be removed", "contract spec", "leverage tier", "margin tier",
          "funding rate will", "settlement", "hard fork", "chain split", "exploit", "hack",
          "halt", "suspend", "emergency", "insolven")
_TIER2 = ("list", "launch", "perpetual", "new pair", "airdrop", "snapshot", "upgrade",
          "maintenance", "migration", "rebrand", "token swap")

#: KNOWN TICKERS. The first live run proved why a whitelist is mandatory: a bare
#: "any uppercase word" regex extracted ACROSS, BANKS, AFFECT, AN, LED and AS as tradeable
#: symbols from ordinary English headlines. A sleeve handed those would place calls on nonsense,
#: and the failure is invisible because the field LOOKS populated. Recall is deliberately traded
#: for precision here: a missed symbol costs one call, a fabricated one costs a wrong trade.
_KNOWN = {
    "BTC", "XBT", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "TRX", "AVAX", "LINK", "DOT",
    "MATIC", "POL", "TON", "SHIB", "LTC", "BCH", "UNI", "ATOM", "XLM", "ETC", "FIL", "APT",
    "ARB", "OP", "SUI", "SEI", "INJ", "TIA", "NEAR", "ICP", "HBAR", "VET", "ALGO", "AAVE",
    "MKR", "CRV", "LDO", "SNX", "COMP", "SUSHI", "1INCH", "GMX", "DYDX", "PENDLE", "ENA",
    "PEPE", "WIF", "BONK", "FLOKI", "JUP", "PYTH", "JTO", "W", "STRK", "BLUR", "ENS",
    "USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE", "PYUSD",
    "HYPE", "AERO", "VIRTUAL", "AI16Z", "GRASS", "MOVE", "ME", "EIGEN", "ZRO", "ZK",
}
_SYMBOL_RE = re.compile(r"\b([A-Z0-9]{2,10})\b")


def _get(url: str) -> tuple[Any, str]:
    """(payload, error). Never raises: one dead source must not kill the collector."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:120]}"
    try:
        return json.loads(raw), ""
    except ValueError:
        return raw, ""                                   # RSS/XML handled by the caller


def _tier(title: str, body: str = "") -> int:
    t = f"{title} {body}".lower()
    if any(k in t for k in _TIER1):
        return 1
    if any(k in t for k in _TIER2):
        return 2
    return 3


def _symbols(text: str) -> list[str]:
    """Only WHITELISTED tickers. An empty list is the correct, honest answer for a headline that
    names no asset -- far better than a plausible-looking list of English words."""
    return sorted({m for m in _SYMBOL_RE.findall(text.upper()) if m in _KNOWN})[:8]


def _iso(ts: Any) -> str | None:
    """Publisher timestamps arrive as epoch s, epoch ms, or ISO. None when truly absent -- and
    absent must stay absent, because a fabricated published_at destroys the latency measurement
    that is this collector's whole point."""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)) or str(ts).isdigit():
            v = float(ts)
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=UTC).isoformat()
        raw = str(ts).strip()
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            # RSS publishes RFC-822 ("Fri, 31 Jul 2026 12:00:00 GMT"). Without this branch every
            # RSS item reported UNMEASURED latency -- 55 of 80 on the first live run.
            d = parsedate_to_datetime(raw)
        return (d if d.tzinfo else d.replace(tzinfo=UTC)).isoformat()
    except (ValueError, OSError, OverflowError, TypeError):
        return None


def _rss_items(xml: str, source: str) -> list[dict[str, Any]]:
    out = []
    for block in re.findall(r"<item>(.*?)</item>", xml, re.DOTALL | re.IGNORECASE)[:40]:
        def _f(tag: str, block: str = block) -> str:
            m = re.search(rf"<{tag}[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", block,
                          re.DOTALL | re.IGNORECASE)
            return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        title = _f("title")
        if title:
            out.append({"source": source, "title": title, "body": _f("description")[:600],
                        "url": _f("link"), "published_at": _iso(_f("pubDate"))})
    return out


def fetch_all() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Every source, with per-source failures RECORDED (never silently absent)."""
    items: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    # 1. EXCHANGE ANNOUNCEMENTS -- the highest-value class, because a listing, delisting or
    # spec change FORCES someone to reposition. Probed live 2026-07-31: OKX's public API works
    # unauthenticated and returns exactly this class; Binance's CMS endpoint 400s without a
    # signed context and Bybit's CloudFront blocks this egress region. Both are recorded as
    # source errors rather than quietly dropped -- a missing exchange feed is the difference
    # between this sleeve having an edge and reading press.
    doc, err = _get("https://www.okx.com/api/v5/support/announcements")
    if err:
        errors["okx_announcements"] = err
    elif isinstance(doc, dict):
        for grp in doc.get("data", []) or []:
            for art in (grp.get("details", []) or []):
                items.append({"source": "okx", "title": str(art.get("title", "")),
                              "body": str(art.get("annType", "")),
                              "url": str(art.get("url", "")),
                              "published_at": _iso(art.get("pTime"))})
    errors.setdefault("binance_announcements",
                      "HTTP 400 -- CMS endpoint requires a signed context (probed 2026-07-31)")
    errors.setdefault("bybit_announcements",
                      "CloudFront blocks this egress country (probed 2026-07-31) -- would need "
                      "the second VPS in a different region")

    # 2. DefiLlama hacks -- chain incidents move whole sectors, and they are pure prose events.
    doc, err = _get("https://api.llama.fi/hacks")
    if err:
        errors["defillama_hacks"] = err
    elif isinstance(doc, list):
        for h in doc[-25:]:
            if isinstance(h, dict):
                items.append({"source": "defillama_hacks",
                              "title": f"{h.get('name','?')} exploit: ${h.get('amount',0):,.0f}",
                              "body": str(h.get("classification", ""))[:300],
                              "url": str(h.get("link", "")), "published_at": _iso(h.get("date"))})

    # 3. Public RSS -- context, not edge. Named as such so nothing over-weights press coverage.
    for name, url in (("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
                      ("cointelegraph", "https://cointelegraph.com/rss")):
        doc, err = _get(url)
        if err:
            errors[name] = err
        elif isinstance(doc, str):
            items.extend(_rss_items(doc, name))
    return items, errors


def _load_seen(root: Path) -> set[str]:
    try:
        return set(json.loads((root / _SEEN).read_text("utf-8")).get("hashes", []))
    except (OSError, ValueError):
        return set()


def collect(root: Path, items: list[dict[str, Any]], errors: dict[str, str]) -> dict[str, Any]:
    """Dedup, enrich, append. Returns the run's status artifact."""
    now = datetime.now(tz=UTC)
    seen = _load_seen(root)
    fresh: list[dict[str, Any]] = []
    for it in items:
        title = str(it.get("title", "")).strip()
        if not title:
            continue
        h = hashlib.sha256(f"{it.get('source')}|{title}".encode()).hexdigest()[:16]
        if h in seen:
            continue                                     # already known -- not news twice
        seen.add(h)
        pub = it.get("published_at")
        # THE NUMBER THIS COLLECTOR EXISTS FOR: how late were we? None when the publisher gave
        # no timestamp -- unmeasured latency must never be reported as zero latency.
        lat = None
        if pub:
            try:
                lat = round((now - datetime.fromisoformat(pub)).total_seconds() / 60.0, 2)
            except ValueError:
                lat = None
        text = f"{title} {it.get('body', '')}"
        tier = _tier(title, str(it.get("body", "")))
        # TRADEABLE requires BOTH a material tier AND arrival inside the window. Unmeasured
        # latency is NOT tradeable: "we do not know how old this is" must never be treated as
        # "it is fresh" (L1.28a applied to news).
        tradeable = bool(lat is not None and lat <= TRADEABLE_MAX_AGE_MIN and tier <= 2)
        fresh.append({**it, "hash": h, "first_seen": now.isoformat(),
                      "latency_minutes": lat, "tier": tier, "tradeable": tradeable,
                      "not_tradeable_reason": (
                          None if tradeable else
                          "latency unmeasured -- age unknown, treated as not fresh"
                          if lat is None else
                          f"stale: {lat:.0f}min old (> {TRADEABLE_MAX_AGE_MIN}min) -- history, "
                          "not news" if lat > TRADEABLE_MAX_AGE_MIN else
                          "tier 3: no forced repositioning implied"),
                      "symbols": _symbols(text)})

    if fresh:
        p = root / _OUT
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for row in fresh:
                fh.write(json.dumps(row) + "\n")
        (root / _SEEN).write_text(json.dumps({"hashes": sorted(seen)[-5000:]}), "utf-8")

    measured = [f["latency_minutes"] for f in fresh if f["latency_minutes"] is not None]
    n_src = 4
    status = ("ALL-SOURCES-DOWN" if len(errors) >= n_src else
              "DEGRADED" if errors else
              "NO-NEW-ITEMS" if not fresh else "OK")
    return {
        "generated": now.isoformat(), "status": status,
        "n_fetched": len(items), "n_new": len(fresh),
        "n_tier1": sum(1 for f in fresh if f["tier"] == 1),
        "n_tradeable": sum(1 for f in fresh if f["tradeable"]),
        "source_errors": errors,
        "median_latency_minutes": (sorted(measured)[len(measured) // 2] if measured else None),
        "latency_unmeasured": len(fresh) - len(measured),
        "detail": (f"{len(fresh)} new of {len(items)} fetched; "
                   f"{sum(1 for f in fresh if f['tier'] == 1)} tier-1, "
                   f"{sum(1 for f in fresh if f['tradeable'])} TRADEABLE (fresh + material); "
                   f"{len(errors)} source(s) failed"),
        "why_latency_matters": (
            "first_seen minus published_at is the only number that decides whether an "
            "event-reading strategy can exist. Early enough to trade, or already priced -- a "
            "collector that cannot answer that produces confident noise."),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    items, errors = fetch_all()
    rep = collect(_ROOT, items, errors)
    (_ROOT / _STATUS).write_text(json.dumps(rep, indent=2), "utf-8")
    print(json.dumps(rep, indent=2) if args.json else
          f"announcements (R0122b): {rep['status']} -- {rep['detail']}")
    return 0                     # a dead source is recorded, never a build failure


if __name__ == "__main__":
    sys.exit(main())
