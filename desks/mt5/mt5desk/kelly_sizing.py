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
