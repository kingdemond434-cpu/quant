"""The gold book's sizes from the survival-constrained growth solve, read for both venues.

`research/kelly_survival.py` writes `reports/KELLY_SURVIVAL.json` hourly (principal 2026-09-30:
"maximum aggressiveness within survival"). `prop/e8_gold.py` reads its `e8` block; the Fusion
gateway reads its `fusion` block. Kept out of `decision_core` so the gateway's re-export surface
does not grow a name only the sizing readers use.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

#: How old `reports/KELLY_SURVIVAL.json` may be before the gold book stops obeying it. Two hours:
#: the solve runs on the hourly cycle, so this is one missed run plus the run in flight.
KELLY_SURVIVAL_MAX_AGE_S = 7200


def load_kelly_survival(path: Path, venue: str, now: datetime | None = None,
                        max_age_s: float = KELLY_SURVIVAL_MAX_AGE_S) -> dict[str, float] | None:
    """Per gold window, the size the survival-constrained Kelly solve chose for `venue`, or None.

    `research/kelly_survival.py` writes it (principal 2026-09-30: "maximum aggressiveness within
    survival"). Fusion values are LOTS, E8 values are RISK FRACTIONS of equity; 0 means the
    window stands aside because trading it lowers growth or breaks survival at any size the
    venue can send.

    NONE -- TODAY'S SIZING, UNCHANGED -- when the file is absent, unreadable, older than
    `max_age_s`, or the venue's solve did not reach an OK status. A stale solve is a claim about
    an equity and a posterior that have moved, and the fallback is the book the desk ran before
    this organ existed, never a flat account.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    try:
        made = datetime.fromisoformat(str(doc.get("generated_at")))
    except ValueError:
        return None
    if made.tzinfo is None:
        made = made.replace(tzinfo=UTC)
    age = ((now or datetime.now(tz=UTC)) - made).total_seconds()
    if not (0 <= age <= max_age_s):
        return None
    block = doc.get(venue)
    if not isinstance(block, dict) or block.get("status") != "OK":
        return None
    key = "lots" if venue == "fusion" else "risk_frac"
    out: dict[str, float] = {}
    for w, row in (block.get("windows") or {}).items():
        try:
            v = float(row[key])
        except (KeyError, TypeError, ValueError):
            return None
        if v != v or v < 0:
            return None
        out[str(w)] = v
    return out or None


#: The principal-set certified sleeve book (principal 2026-10-06/07: "put the max-growth sleeve
#: books live"). Data with an author and a date, read by the Fusion gateway and the E8 lanes.
CERT_BOOK_FILE = Path(__file__).resolve().parents[1] / "data" / "CERT_BOOK_LIVE.json"


def load_cert_book(path: Path, venue: str) -> dict[str, float] | None:
    """{book key: risk fraction of equity} for `venue` ("fusion" or "e8") from the certified
    sleeve book, or None.

    The keys are the allocator's own (`SYMBOL_family_selector`, or a gold window `gold_asia`), so
    the gateway lays them over the allocator's book with no translation. A key the file does not
    name keeps whatever the allocator set.

    NONE -- TODAY'S SIZING, UNCHANGED -- when the file is absent, unreadable, `enabled` is not
    true, the venue block is missing, or ANY value is not a number in [0, MAX_RISK_FRAC]. One bad
    entry voids the whole block: a half-read book would size some legs from the principal's
    table and their siblings from the allocator, which is neither.
    """
    from mt5desk.sizing import MAX_RISK_FRAC
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("enabled") is not True:
        return None
    block = doc.get(venue)
    if not isinstance(block, dict) or not block:
        return None
    out: dict[str, float] = {}
    for key, raw in block.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        v = float(raw)
        if v != v or not 0.0 <= v <= MAX_RISK_FRAC:
            return None
        out[str(key)] = v
    return out
