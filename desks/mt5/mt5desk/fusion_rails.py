"""THE FUSION BOOK'S RAILS LEDGER: one line per order the book's own rails changed or refused.

GROWTH GOVERNANCE requires a missed-growth line for every veto, cap and lift. The rail register
(`libs/portfolio/rails.py`) is a SEALED immutable-evaluator file, so these rails cannot be
registered there without a re-signed manifest; like the stop-geometry gate, they PUBLISH their
lines on their own ledger, and `research/missed_growth.published_fusion_book_lines` carries the
bill into MISSED_GROWTH.json beside the registered rails.

    rail                         kind   what a line records
    one_gold_at_risk             veto   a gold window not placed while another is at risk
    cross_account_opposite       veto   an order/leg refused against the other account's book
    fusion_daily_loss            veto   a pass that took no new risk after the day's -10%
    fusion_book_floor_lift       lift   an order sent at the 0.01 floor above its 0.75% target
    fusion_book_ceiling          cap    a boost clipped back to the book's own lot

Each line carries the lot and, where it can be priced, the risk fraction (`risk_frac`) that was
forgone, clipped or added, so the bill is in the desk's own units. Never raises: a ledger that
cannot be written costs the line, never the order.
"""
from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parent.parent
LEDGER = _DESK / "data" / "fusion_book_rails.jsonl"
RAILS = ("one_gold_at_risk", "cross_account_opposite", "fusion_daily_loss",
         "fusion_book_floor_lift", "fusion_book_ceiling")


def line(rail: str, **fields: Any) -> None:
    """Append one rails-ledger line. Never raises."""
    with contextlib.suppress(Exception):
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        row = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "rail": str(rail),
               **fields}
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
