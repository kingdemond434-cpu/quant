#!/usr/bin/env python3
"""
Collect free X/Twitter signals for crypto narratives -> data/x_signals.parquet + web/x_signals.json.

Uses free/public endpoints: Nitter instances, RSS feeds, public API v2 (if bearer available).
Emits: tweet volume, engagement, sentiment keywords, cashtag mentions per symbol.
Runs hourly on executor flywheel.

    python scripts/collect_x_signals.py
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _try_xcom_ssr(account: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch tweets from x.com server-side-rendered profile HTML (no auth)."""
    import html as _html
    import re as _re
    import urllib.request
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    try:
        req = urllib.request.Request(
            f"https://x.com/{account}",
            headers={"User-Agent": ua, "Accept": "text/html"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    items: list[dict] = []
    seen: set[str] = set()
    for tid in sorted(set(_re.findall(r'data-tweet-id="(\d+)"', html))):
        if len(items) >= limit:
            break
        idx = html.find(f'data-tweet-id="{tid}"')
        if idx < 0:
            continue
        window = html[idx:idx + 12000]
        segments = [_html.unescape(s.strip()) for s in _re.findall(r">([^<>]{40,800})<", window)]
        parts: list[str] = []
        for s in segments:
            if s not in seen and not s.startswith("http") and " " in s and len(s) >= 40:
                seen.add(s)
                parts.append(s)
            if len(parts) >= 3:
                break
        text = " ".join(parts).strip()
        if not text:
            continue
        likes = _re.search(r'aria-label="([\d,]+) likes"', window)
        replies = _re.search(r'aria-label="([\d,]+) replies"', window)
        reposts = _re.search(r'aria-label="([\d,]+) reposts"', window)
        posted = _re.search(r'<time datetime="([^"]+)"', window)
        metrics = {}
        if likes:
            metrics["like_count"] = int(likes.group(1).replace(",", ""))
        if replies:
            metrics["reply_count"] = int(replies.group(1).replace(",", ""))
        if reposts:
            metrics["retweet_count"] = int(reposts.group(1).replace(",", ""))
        items.append({
            "account": account,
            "text": text[:500],
            "url": f"https://x.com/{account}/status/{tid}",
            "timestamp": posted.group(1) if posted else "",
            "cashtags": list(CASTAG_RE.findall(text.upper())),
            "metrics": metrics,
            "source": "xcom_ssr",
        })
    return items


# Optional: Twitter API v2 (requires bearer token in env)
BEARER = os.getenv("TWITTER_BEARER_TOKEN")
_ARCH = Path("data/x_signals.parquet")
_WEB = Path("web/x_signals.json")

# Free Nitter instances (public, no auth)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.fdn.fr",
    "https://nitter.privacydev.net",
    "https://nitter.42l.fr",
]

# Crypto-relevant accounts to track (high-signal, not shills)
CRYPTO_ACCOUNTS = [
    "whale_alert", "lookonchain", "arkhamintel", "spotonthechain",
    "thedefiedge", "cryptohayes", "cz_binance", "vitalikbuterin",
    "aeyakovenko", "gcr_classic", "pentosh1", "cryptokaleo",
    "rovercrc", "crypto_birb", "crediblecrypto", "jacks_",
    "l1vsun", "shmidtqq", "antpalkin",
]

# Narrative keywords + cashtag pattern
NARRATIVE_KEYWORDS = {
    "ai": ["ai agent", "ai16z", "virtuals", "aixbt", "eliza", "deai", "decentralized ai"],
    "memecoin": ["memecoin", "pump.fun", "raydium", "moonshot", "bonding curve"],
    "defi": ["defi", "yield", "points", "airdrop", "liquidity mining", "restaking"],
    "l2": ["arbitrum", "optimism", "base", "blast", "linea", "scroll", "zksync", "starknet"],
    "solana": ["solana", "jito", "kamino", "marginfi", "drift", "tensor", "magic eden"],
    "btc": ["bitcoin", "btc", "etf", "microstrategy", "hodl", "halving"],
    "eth": ["ethereum", "eth", "eigenlayer", "restaking", "blob", "dencun"],
    "regulation": ["sec", "etf approval", "regulation", "lawsuit", "wells notice"],
    "macro": ["fed", "cpi", "rates", "inflation", "dxy", "liquidity", "qt", "qe"],
    "exchange": ["binance", "coinbase", "bybit", "okx", "kraken", "delisting", "listing"],
    "hack": ["hack", "exploit", "drained", "vulnerability", "audit", "reentrancy"],
}

CASTAG_RE = re.compile(r"\$([A-Z]{2,10})\b")


def _try_nitter(account: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch latest tweets from a Nitter instance (HTML scrape)."""
    for base in NITTER_INSTANCES:
        try:
            url = f"{base}/{account}/rss"
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml = resp.read()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml)
            items = []
            for item in root.findall(".//item")[:limit]:
                title = item.findtext("title", "") or ""
                desc = item.findtext("description", "") or ""
                link = item.findtext("link", "") or ""
                pub = item.findtext("pubDate", "") or ""
                text = f"{title} {desc}"
                items.append({
                    "account": account,
                    "text": text[:500],
                    "url": link,
                    "timestamp": pub,
                    "cashtags": list(CASTAG_RE.findall(text.upper())),
                    "source": "nitter_rss",
                })
            if items:
                return items
        except Exception:
            continue
    return []


def _try_api_v2(query: str, max_results: int = 50) -> list[dict[str, Any]]:
    """Twitter API v2 recent search (requires bearer)."""
    if not BEARER:
        return []
    try:
        import urllib.request
        url = "https://api.twitter.com/2/tweets/search/recent"
        params = f"?query={urllib.parse.quote(query)}&max_results={max_results}&tweet.fields=public_metrics,created_at,author_id"
        req = urllib.request.Request(f"{url}{params}", headers={"Authorization": f"Bearer {BEARER}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        items = []
        for tweet in data.get("data", []):
            text = tweet.get("text", "")
            items.append({
                "text": text[:500],
                "metrics": tweet.get("public_metrics", {}),
                "created_at": tweet.get("created_at"),
                "author_id": tweet.get("author_id"),
                "cashtags": list(CASTAG_RE.findall(text.upper())),
                "source": "api_v2",
            })
        return items
    except Exception:
        return []


def _aggregate_signals(raw_items: list[dict]) -> dict[str, Any]:
    """Aggregate raw tweets into per-symbol + per-narrative signals."""
    now = datetime.now(tz=UTC)
    by_symbol: dict[str, dict] = {}
    by_narrative: dict[str, dict] = {k: {"count": 0, "engagement": 0} for k in NARRATIVE_KEYWORDS}

    for item in raw_items:
        text = (item.get("text") or "").lower()
        cashtags = item.get("cashtags", [])
        engagement = item.get("metrics", {}).get("like_count", 0) + item.get("metrics", {}).get("retweet_count", 0) * 2

        # Per-cashtag
        for tag in cashtags:
            if tag not in by_symbol:
                by_symbol[tag] = {"mentions": 0, "engagement": 0, "tweets": []}
            by_symbol[tag]["mentions"] += 1
            by_symbol[tag]["engagement"] += engagement
            by_symbol[tag]["tweets"].append(item.get("text", "")[:200])

        # Per-narrative
        for narr, kws in NARRATIVE_KEYWORDS.items():
            if any(kw in text for kw in kws):
                by_narrative[narr]["count"] += 1
                by_narrative[narr]["engagement"] += engagement

    # Compute scores
    symbol_scores = {}
    for sym, data in by_symbol.items():
        eng = data["engagement"]
        eng_factor = np.log1p(eng) if eng else 1.0
        symbol_scores[sym] = {
            "mentions": data["mentions"],
            "engagement": eng,
            "score": min(1.0, data["mentions"] / 10.0) * eng_factor,
        }

    narrative_scores = {}
    for narr, data in by_narrative.items():
        eng = data["engagement"]
        eng_factor = np.log1p(eng) if eng else 1.0
        narrative_scores[narr] = {
            "count": data["count"],
            "engagement": eng,
            "score": min(1.0, data["count"] / 20.0) * eng_factor,
        }

    return {
        "timestamp": now.isoformat(),
        "symbols": symbol_scores,
        "narratives": narrative_scores,
        "raw_count": len(raw_items),
        "accounts_checked": len(CRYPTO_ACCOUNTS),
    }


def main() -> None:
    all_items: list[dict] = []

    # 1) Nitter RSS -> x.com SSR fallback for high-signal accounts
    for acct in CRYPTO_ACCOUNTS:
        items = _try_nitter(acct, limit=15)
        if not items:
            items = _try_xcom_ssr(acct, limit=15)
        all_items.extend(items)
        time.sleep(0.3)

    # 2) API v2 search for narrative queries (if bearer available)
    if BEARER:
        queries = [
            "$BTC OR $ETH OR $SOL OR $AI OR $MEME",
            "crypto airdrop OR points farming",
            "defi yield OR restaking",
            "memecoin pump.fun",
        ]
        for q in queries:
            all_items.extend(_try_api_v2(q, max_results=30))

    # 3) Aggregate
    signals = _aggregate_signals(all_items)

    # Write artifacts
    _ARCH.parent.mkdir(parents=True, exist_ok=True)
    row = pd.DataFrame([signals])
    if _ARCH.exists():
        existing = pd.read_parquet(_ARCH)
        combined = pd.concat([existing, row], ignore_index=True)
        combined.to_parquet(_ARCH, index=False)
    else:
        row.to_parquet(_ARCH, index=False)

    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(signals, indent=2), "utf-8")

    print(f"X signals: {signals['raw_count']} tweets, {len(signals['symbols'])} symbols, {len(signals['narratives'])} narratives")


if __name__ == "__main__":
    main()
