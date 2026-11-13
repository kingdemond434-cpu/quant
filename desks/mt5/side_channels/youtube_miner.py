"""YouTube trading video miner.

Scrapes YouTube for recent trading strategy videos, extracts mentioned
symbols/timeframes/patterns, and outputs structured alpha candidates.

Uses YouTube Data API v3 (free tier: 10,000 units/day).
Falls back to web scraping if no API key available.
"""

import json
import time
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "intelligence" / "youtube"
OUT.mkdir(parents=True, exist_ok=True)

#: The key: the environment first (the VPS unit set it), else the box's key file -- the one
#: `scripts/collect_youtube_corpus.py` already reads. The box residents never carried the
#: environment variable, so without the file fallback this miner ran keyless and returned [] for
#: every query: dark for want of a key it was sitting next to. The value is never printed.
KEYFILE = BASE.parent.parent / "data" / "secrets" / "youtube_api_key"


def _key() -> str:
    env = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if env:
        return env
    try:
        return KEYFILE.read_text("utf-8").strip()
    except OSError:
        return ""


API_KEY = _key()
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# Trading-related search queries
QUERIES = [
    "forex trading strategy 2026",
    "gold XAUUSD trading strategy",
    "JPY trading strategy",
    "session breakout strategy forex",
    "price action trading strategy",
    "algorithmic trading strategy",
    "mean reversion trading",
    "momentum trading strategy forex",
    "central bank trading strategy",
    "NFP trading strategy",
]

SYMBOLS = [
    "XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
    "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY",
    "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY", "EURAUD",
    "GBPAUD", "AUDNZD", "NZDCAD", "AUDCAD", "BTCUSD",
    "ETHUSD", "US500", "NAS100",
]


@dataclass
class YTDiscovery:
    source: str = "youtube"
    title: str = ""
    channel: str = ""
    url: str = ""
    published: str = ""
    symbols_mentioned: list = field(default_factory=list)
    timeframes_mentioned: list = field(default_factory=list)
    patterns_mentioned: list = field(default_factory=list)
    raw_snippet: str = ""
    confidence: float = 0.0


def _extract_symbols(text: str) -> list[str]:
    text_upper = text.upper()
    return [s for s in SYMBOLS if s in text_upper]


def _extract_timeframes(text: str) -> list[str]:
    patterns = [
        r'\b(\d+)\s*(min|m|hour|h|day|d|week|w)\b',
        r'\b(H[1-4]|M[1-9]\d*|D1|W1|MN)\b',
        r'\b(scalp|intraday|swing|position)\b',
    ]
    found = []
    for p in patterns:
        found.extend(re.findall(p, text, re.IGNORECASE))
    return list(set(found))


def _extract_patterns(text: str) -> list[str]:
    known = [
        "breakout", "breakdown", "reversal", "pullback", "retest",
        "support", "resistance", "trendline", "fibonacci", "fib",
        "moving average", "EMA", "SMA", "RSI", "MACD", "Bollinger",
        "engulfing", "doji", "hammer", "head and shoulders", "H&S",
        "double top", "double bottom", "triangle", "flag", "pennant",
        "order block", "fair value gap", "FVG", "liquidity", "smart money",
        "ICT", "supply and demand", "zone", "accumulation", "distribution",
        "session range", "asia range", "london open", "NY open",
    ]
    text_lower = text.lower()
    return [p for p in known if p.lower() in text_lower]


#: Errors from this run, typed, for the state file. Never contains the key.
ERRORS: list[str] = []


class QuotaRefused(RuntimeError):
    """The API refused on quota or rate; stop spending this run."""


def _search_api(query: str, max_results: int = 10) -> list[dict]:
    """Search YouTube via Data API v3."""
    if not API_KEY:
        return []
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": "date",
        "publishedAfter": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "key": API_KEY,
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=15)
        if resp.status_code in (403, 429):
            # QUOTA IS A VERDICT, NOT AN EMPTY RESULT. Every later query would spend the same
            # refusal, and a swallowed 403 made "quota gone" read exactly like "no new videos".
            reason = "quota" if "quota" in resp.text.lower() else f"http_{resp.status_code}"
            ERRORS.append(f"{reason}: {query}")
            raise QuotaRefused(reason)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except QuotaRefused:
        raise
    except Exception as exc:
        ERRORS.append(f"{type(exc).__name__}: {query}")
        return []


def _search_web(query: str) -> list[dict]:
    """Fallback: scrape YouTube search results via HTML."""
    # Minimal fallback — returns empty if API unavailable
    return []


def mine(query: str = None, max_per_query: int = 10) -> list[YTDiscovery]:
    """Run YouTube mining for a query or all queries."""
    queries = [query] if query else QUERIES
    discoveries = []

    # FINISH INSIDE THE HARNESS BUDGET, OR THE HARNESS KILLS US AND WE RETURN NOTHING.
    # run_all_miners kills a miner at QUANT_MINER_TIMEOUT_S (180s default) and a killed miner
    # loses every discovery it had already collected. Ten queries at the 15s request timeout is
    # 150s before any parsing, so a few slow responses put this miner over the edge -- it was
    # reported TIMED OUT on most runs and had produced nothing for seven days. Stop issuing new
    # queries once the budget is nearly spent and RETURN WHAT WE HAVE: partial evidence is a
    # result, being killed is not.
    _budget = float(os.environ.get("QUANT_MINER_TIMEOUT_S", "180"))
    _deadline = time.monotonic() + max(20.0, _budget * 0.75)

    for q in queries:
        if time.monotonic() >= _deadline:
            print(f"youtube: budget reached, stopping after {len(discoveries)} discovery(ies) "
                  f"from {queries.index(q)} of {len(queries)} queries")
            break
        try:
            items = _search_api(q) if API_KEY else _search_web(q)
        except QuotaRefused as exc:
            print(f"youtube: API refused ({exc}); stopping after {queries.index(q)} queries")
            break
        for item in items:
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            desc = snippet.get("description", "")
            combined = f"{title} {desc}"

            syms = _extract_symbols(combined)
            tfs = _extract_timeframes(combined)
            pats = _extract_patterns(combined)

            if not syms:
                continue

            confidence = min(1.0, len(syms) * 0.2 + len(pats) * 0.15 + len(tfs) * 0.1)

            d = YTDiscovery(
                title=title,
                channel=snippet.get("channelTitle", ""),
                url=f"https://youtube.com/watch?v={item.get('id', {}).get('videoId', '')}",
                published=snippet.get("publishedAt", ""),
                symbols_mentioned=syms,
                timeframes_mentioned=tfs,
                patterns_mentioned=pats,
                raw_snippet=desc[:500],
                confidence=confidence,
            )
            discoveries.append(d)

    return discoveries


def run_and_save() -> list[dict]:
    """Mine all queries and save results."""
    all_discoveries = mine()
    results = []
    for d in all_discoveries:
        results.append({
            "source": d.source,
            "title": d.title,
            "channel": d.channel,
            "url": d.url,
            "published": d.published,
            "symbols": d.symbols_mentioned,
            "timeframes": d.timeframes_mentioned,
            "patterns": d.patterns_mentioned,
            "confidence": d.confidence,
        })

    out_file = OUT / f"discoveries_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    results = write_discoveries(out_file, results)
    print(f"youtube: {len(results)} discoveries saved to {out_file.name}")
    return results


if __name__ == "__main__":
    run_and_save()


# ---------------------------------------------------------------------------------------------
# THE BOX CLOCK (2026-11-03). This miner's only clock was `run_all_miners`, which only the VPS
# ran; the box held a mirror and nothing on it ever called the miner, so its discoveries stopped
# when the VPS did (last 2026-11-01 07:01Z). hourly_cycle now runs it as the `youtube_miner` leg
# of the intel department. Every query is a `search` call at 100 units, so ten queries are 1,000
# units against a 10,000/day project quota shared with the corpus collector: the leg is gated to
# one real pass per MIN_INTERVAL_S (6 per day at most = 6,000 units) and a faster intel clock
# returns NOT_DUE without a call.
STATE = OUT / "_box_miner_state.json"
MIN_INTERVAL_S = int(os.environ.get("QUANT_YOUTUBE_MINER_INTERVAL_S", str(4 * 3600)))


def _due(now: float, force: bool = False) -> tuple[bool, dict]:
    try:
        st = json.loads(STATE.read_text("utf-8"))
        st = st if isinstance(st, dict) else {}
    except (OSError, ValueError):
        st = {}
    last = st.get("last_run_epoch")
    if force or not isinstance(last, (int, float)):
        return True, st
    return (now - float(last)) >= MIN_INTERVAL_S, st


def box_main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="ignore the cadence gate")
    a = ap.parse_args(argv)
    now = time.time()
    due, st = _due(now, a.force)
    if not due:
        print(f"youtube: NOT_DUE (last real pass {int(now - st['last_run_epoch'])}s ago, "
              f"interval {MIN_INTERVAL_S}s)")
        return 0
    rows = run_and_save() if API_KEY else []
    state = {
        "last_run_epoch": now,
        "last_run_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "key_present": bool(API_KEY),
        "discoveries": len(rows),
        "errors": ERRORS[-20:],
        "quota_refused": any(e.startswith(("quota", "http_403", "http_429")) for e in ERRORS),
        "interval_s": MIN_INTERVAL_S,
    }
    if not API_KEY:
        state["blocker"] = "NO_KEY: neither YOUTUBE_API_KEY nor data/secrets/youtube_api_key"
        print("youtube: BLOCKER no key on this host -- nothing fetched")
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), "utf-8")
    os.replace(tmp, STATE)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(box_main())
