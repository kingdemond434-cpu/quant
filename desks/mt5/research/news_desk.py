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


def main() -> None:
    log("news desk ready. schedule empty (licensed calendar source pending); "
        "capture activates after Fusion gateway go-live.")
    while True:
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