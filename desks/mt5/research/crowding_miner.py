"""CROWDING MINER (meta item 7 + anti-crowding intelligence #28).

Perpetual supervised desk. Every cycle (hourly):
  1. GitHub public search (unauthenticated, rate-limited ~10/min -> one query
     per cycle, rotating) for adoption/star growth of mechanism keywords
  2. Reddit r/algotrading hot + comments as retail-adoption proxy
  3. keyword frequency counters in our OWN captured news (news_captures.jsonl)
     as the mechanism-topic current
  4. data/crowding_state.json: {query, stars_top5, count, reddit_activity,
     delta_vs_prev} + EDGE_PUBLICITY/EXPECTED_DECAY flags for our active
     mechanism families (rft_retrack etc.)

No marker: perpetual watcher (supervisor keeps alive like research_loop).
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import free_data as fd

BASE = Path(__file__).resolve().parent.parent
STATE_F = BASE / "data" / "crowding_state.json"
HIST_F = BASE / "data" / "crowding_history.jsonl"
CAPTURES = BASE / "data" / "news_captures.jsonl"
LOG = BASE / "logs" / "crowding_miner.log"

# mechanism -> GitHub query (rotate one per cycle to respect rate limits)
MECHANISM_QUERIES = [
    ("rft_retrack", "retrack trading strategy"),
    ("saleh_kama", "KAMA Kauffman adaptive moving average strategy"),
    ("squeeze", "TTM squeeze trading"),
    ("breakout_fakeout", "fakeout breakout trading"),
    ("mean_reversion", "mean reversion forex strategy"),
    ("vol_surface", "implied volatility skew trading"),
    ("cross_asset", "cross asset momentum lead lag"),
]


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def news_topic_counts() -> dict[str, int]:
    topics = {"fed": 0, "cpi": 0, "nonfarm": 0, "rates": 0, "oil": 0,
              "gold": 0, "bonds": 0, "inflation": 0, "crypto": 0}
    if not CAPTURES.exists():
        return topics
    try:
        for line in CAPTURES.read_text("utf-8").splitlines():
            try:
                e = json.loads(line)
                t = (e.get("title", "") + " " + e.get("source", "")).lower()
                for k in topics:
                    if k in t:
                        topics[k] += 1
            except Exception:
                pass
    except Exception:
        pass
    return topics


def main() -> None:
    log("crowding miner started (GitHub search + Reddit, no keys)")
    hist = []
    if HIST_F.exists():
        try:
            hist = [json.loads(l) for l in HIST_F.read_text("utf-8").splitlines() if l.strip()]
        except Exception:
            pass
    i = 0
    while True:
        t0 = time.time()
        try:
            mech, query = MECHANISM_QUERIES[i % len(MECHANISM_QUERIES)]
            i += 1
            gh = fd.github_search(query)
            reddit = fd.reddit_hot("algotrading")
            reddit_activity = {"posts": len(reddit),
                               "avg_score": round(sum(r["score"] for r in reddit) /
                                                  max(1, len(reddit)), 1),
                               "comments": sum(r["num_comments"] for r in reddit)}
            topics = news_topic_counts()
            prev = None
            if hist:
                prev = [h for h in reversed(hist) if h.get("query") == query]
                prev = prev[0] if prev else None
            row = {"ts": fd.now_iso(), "query": query, "mechanism": mech,
                   "github": gh, "reddit": reddit_activity,
                   "github_stars_delta": ((gh.get("top_stars", [0])[0] or 0) -
                                          ((prev or {}).get("github", {}).get("top_stars", [0]) or [0])[0]
                                          if prev else None),
                   "news_topics": topics,
                   "edge_publicity": "HIGH" if ((gh.get("top_stars", [0]) or [0])[0] or 0) > 5000
                   else "MEDIUM" if ((gh.get("top_stars", [0]) or [0])[0] or 0) > 500 else "LOW",
                   "expected_decay": "WATCH" if ((prev or {}).get("github", {}).get("top_stars", [0]) or [0])[0]
                   and ((gh.get("top_stars", [0]) or [0])[0] or 0) >
                   (prev["github"].get("top_stars", [0])[0] or 0) * 1.5 else "NORMAL"}
            hist.append(row)
            hist = hist[-500:]
            with open(HIST_F, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            STATE_F.write_text(json.dumps(
                {"updated": fd.now_iso(), "latest": row,
                 "history_len": len(hist)}, indent=1), "utf-8")
            log(f"{mech}: gh_stars={row['github'].get('top_stars')} "
                f"publicity={row['edge_publicity']} decay={row['expected_decay']}")
        except Exception as e:
            log(f"cycle error: {e!r}")
        time.sleep(max(60, 3600 - (time.time() - t0)))


if __name__ == "__main__":
    main()