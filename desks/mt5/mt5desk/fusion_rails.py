"""THE FUSION BOOK'S RAILS LEDGER: one line per order the book's own rails changed or refused.

GROWTH GOVERNANCE requires a missed-growth line for every veto, cap and lift. The rail register
(`libs/portfolio/rails.py`) is a SEALED immutable-evaluator file, so these rails cannot be
registered there without a re-signed manifest; like the stop-geometry gate, they PUBLISH their
lines on their own ledger, and `research/missed_growth.published_fusion_book_lines` carries the
bill into MISSED_GROWTH.json beside the registered rails.

    rail                         kind   what a line records
    one_gold_at_risk             veto   a gold window not placed while another is at risk
    cross_account_opposite       veto   an order/leg refused against the other account's book
    fusion_daily_loss            veto   the day's first latch at -5% of its starting equity
    fusion_trade_risk_cap        veto   an entry refused because its stop risks > 10% of equity
    fusion_book_floor_lift       lift   an order sent at the 0.01 floor above its 0.75% target
    fusion_book_ceiling          cap    a boost clipped back to the book's own lot

Each line carries the lot and, where it can be priced, the risk fraction (`risk_frac`) that was
forgone, clipped or added, so the bill is in the desk's own units. Never raises: a ledger that
cannot be written costs the line, never the order -- but the failure is SURFACED (audit round 2):
`line` returns False, says so on stderr, and counts it in `WRITE_FAILURES`, which the gateway logs.
`ensure()` creates the ledger so that an ABSENT file means "never synced / never written", which
`missed_growth` reads as UNMEASURED, not as a clean zero.
"""
from __future__ import annotations

import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parent.parent
LEDGER = _DESK / "data" / "fusion_book_rails.jsonl"
RAILS = ("one_gold_at_risk", "cross_account_opposite", "fusion_daily_loss",
         "fusion_book_floor_lift", "fusion_book_ceiling", "fusion_trade_risk_cap",
         "principal_zero_pin", "cert_book_absent_window", "gold_late_send",
         "cert_book_void", "gold_retry_abandoned")
#: Lines this process could not write (rail -> count). The gateway logs it every pass.
WRITE_FAILURES: dict[str, int] = {}


def line(rail: str, **fields: Any) -> bool:
    """Append one rails-ledger line. Never raises; returns whether it was written."""
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        row = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "rail": str(rail),
               **fields}
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        return True
    except Exception as exc:
        WRITE_FAILURES[str(rail)] = WRITE_FAILURES.get(str(rail), 0) + 1
        with contextlib.suppress(Exception):
            print(f"fusion_rails: {rail} line NOT written ({type(exc).__name__}: {exc}); the "
                  f"missed-growth bill is short by it", file=sys.stderr)
        return False


def line_once(rail: str, dedupe: str, **fields: Any) -> bool:
    """`line`, unless the ledger's recent tail already holds this rail with this `dedupe` key
    (e.g. "<sleeve>/<day>") -- so a refusal re-checked every pass is billed once. An unreadable
    tail writes the line (a duplicate is better than a silent miss)."""
    try:
        tail = LEDGER.read_text(encoding="utf-8").splitlines()[-2000:] if LEDGER.exists() else []
        for ln in reversed(tail):
            if f'"dedupe": {json.dumps(dedupe)}' in ln and f'"rail": {json.dumps(rail)}' in ln:
                return True
    except Exception:
        pass
    return line(rail, dedupe=dedupe, **fields)


def ensure() -> bool:
    """Create the ledger if it is absent (no line). Never raises."""
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.touch(exist_ok=True)
        return True
    except Exception:
        return False
