"""NEWS SHOCK CAPTURE DESK (docs/NEWS_LINEAGE.md).

Deterministic capture layer for scheduled macro releases. Runs forever under the
supervisor. While the gateway is paused (Fusion pending) it idles and reports
readiness; after Fusion go-live it will:

  1. read data/news_schedule.json (populated by a LICENSED calendar source only;
     the file starts EMPTY - no invented release data, ever)
  2. at each scheduled_release_time - pre: snapshot positions/vol
  3. on source_publish_time: parse actual vs consensus, classify surprise
     (z-scored), store HEADLINE/CORE/REVISION/COMPONENT/BREADTH surprise
  4. capture MARKET_RESPONSE (0-60m of our symbols' H1 bars via the gateway
     feed), compute REACTION_RESIDUAL = actual response - expected response
     (expected from the historical reaction model once N events exist)
  5. timestamp EVERYTHING (scheduled/publish/arrival/parse/decision/send/ack/fill)
     and write data/news_captures.jsonl

LLM is NEVER in the capture path (structured parser -> deterministic model ->
execution). Directional families (NEWS_001-036) are registered in the lineage
doc; they become testable only with real captured events + real broker
event-window cost distributions.

Marker (perpetual watcher): reports/DONE_news_final is intentionally NOT
written; the supervisor keeps this alive like research_loop.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCHEDULE = BASE / "data" / "news_schedule.json"
CAPTURES = BASE / "data" / "news_captures.jsonl"
LOG = BASE / "logs" / "news_desk.log"


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def poll_official_rss() -> int:
    """Poll FREE official-government RSS feeds (Fed/BLS/ECB/BOJ/BOE/SNB) and
    record every headline with the four clocks. No invented data: only items
    that actually appeared in a first-party feed. Deduped by guid/link/title."""
    import free_data as fd
    seen = set()
    if CAPTURES.exists():
        try:
            for line in CAPTURES.read_text("utf-8").splitlines():
                try:
                    e = json.loads(line)
                    seen.add(e.get("key", ""))
                except Exception:
                    pass
        except Exception:
            pass
    new = 0
    for src, url in fd.RSS_FEEDS.items():
        for item in fd.rss_fetch(url):
            title = item.get("title", "").strip()
            link = item.get("link", "").strip() or item.get("guid", "").strip()
            key = f"{src}:{title[:80]}:{link[:120]}"
            if not title or key in seen:
                continue
            happened = item.get("pubDate") or item.get("published") or item.get("updated")
            rec = {
                "key": key, "source": src, "title": title, "url": link,
                "happened_at": happened,
                "published_at": happened,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "lane": "deep",  # RSS headlines -> deep lane (no LLM in capture path)
                "raw": True,
            }
            with open(CAPTURES, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            seen.add(key)
            new += 1
    if new:
        log(f"RSS capture: {new} new first-party headlines stored")
    return new


def main() -> None:
    log("news desk ready. schedule empty (licensed calendar source pending); "
        "capture activates after Fusion gateway go-live.")
    while True:
        try:
            poll_official_rss()
        except Exception as ex:
            log(f"rss poll error: {ex!r}")
        if SCHEDULE.exists():
            try:
                events = json.loads(SCHEDULE.read_text("utf-8"))
                due = [e for e in events
                       if e.get("enabled", True)
                       and datetime.fromisoformat(e["scheduled_release_time"]).timestamp()
                       <= time.time() + 120
                       and not e.get("captured")]
                for e in due:
                    log(f"EVENT DUE: {e.get('event_id')} {e.get('name')} "
                        f"scheduled {e.get('scheduled_release_time')} - capture pending "
                        f"gateway feed (Fusion)")
                    e["captured"] = False
                    e["note"] = "arrival logged; live capture requires gateway"
            except Exception as ex:
                log(f"schedule parse error: {ex!r}")
        time.sleep(60)


if __name__ == "__main__":
    main()