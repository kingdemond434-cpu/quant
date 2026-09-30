"""Reddit trading community miner -- FENCED 2026-09-30, BLOCKED_WITH_SUBSTITUTE.

Until 2026-09-30 this read the subreddit RSS feeds (r/Forex, r/algotrading, r/wallstreetbets,
r/Gold, r/silverbugs, r/ForexTrading, r/Daytrading) through `run_all_miners` and wrote
`data/intelligence/reddit/discoveries_*.json`, which `miner_candidate_compiler` read into cells.

WHY IT NO LONGER FETCHES. Reddit's User Agreement and Data API terms cover ALL automated access --
the RSS feeds and the anonymous JSON included -- and require a separate agreement for commercial
use. The desk is commercial and holds none (project coordinator ruling 2026-09-30, the same basis
as the Discord ruling; `libs/data/terms_fence.py`). So:

  * nothing is requested from any Reddit host (and `polite_fetch.get` refuses one anyway);
  * nothing is written under `data/intelligence/reddit/` -- the compiler refuses that directory's
    rows with a counted reason in any case, and the cells already judged from it keep their
    verdicts, labelled `provenance_label=reddit_fenced` by the organs that write docket rows;
  * each call writes `data/terms_fences/reddit_miner.json`: the status, the ruling and the lawful
    substitutes that carry retail attention now (`research/attention_substitutes.py`: Wikipedia
    pageviews, GDELT, and the existing Google Trends miner).

The module keeps its name and `run_and_save` so the miner roster still lists it -- as a fenced
source, never a silently absent one.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data import terms_fence as tf  # noqa: E402

#: The fence artifact. NOT under data/intelligence/ -- the compiler reads that tree, and a
#: refusal is not a discovery.
FENCE_OUT = BASE / "data" / "terms_fences" / "reddit_miner.json"

SUBREDDITS = ["Forex", "algotrading", "wallstreetbets", "Gold",
              "silverbugs", "ForexTrading", "Daytrading"]


def mine_subreddit(sub: str) -> list[dict]:
    """Refused: returns nothing and requests nothing (Reddit terms fence)."""
    return []


def mine_all() -> list[dict]:
    return []


def run_and_save() -> list[dict]:
    doc = tf.refusal("reddit", organ="desks/mt5/side_channels/reddit_miner.py",
                     subreddits_not_read=SUBREDDITS, written_to_intelligence=False,
                     at=datetime.now(UTC).isoformat(timespec="seconds"),
                     substitute_organ="desks/mt5/research/attention_substitutes.py")
    try:
        FENCE_OUT.parent.mkdir(parents=True, exist_ok=True)
        FENCE_OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    except OSError as exc:
        print(f"reddit: fence artifact not written ({type(exc).__name__})")
    print(f"reddit: {doc['status']} -- nothing fetched ({tf.REDDIT_TERMS_REASON[:80]}...)")
    return []


if __name__ == "__main__":
    run_and_save()
