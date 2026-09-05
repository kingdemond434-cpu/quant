"""FORWARD CLOCK -- the elapsed forward window is DERIVED from the pre-registration stamp,
never read back from a stored day count.

WHAT WENT WRONG (measured on disk 2026-08-27). `days_active` used to be computed from
`first_entry` -- the first trade the sleeve EVER took, including trades taken while the cell was
still being SELECTED. `shadow_forward` was corrected on 2026-08-26 to derive it from
`forward_start` instead, but the correction only reached rows that engine still enrols. Rows it
no longer enrols kept the old number frozen in place, and every OTHER consumer of the 14-day
forward gate read that stored field verbatim:

    XAGUSD.level_breakout   forward_start = 2026-08-25T23:26   (true elapsed: 1 day)
                            first_entry   = 2026-08-17 08:00
                            days_active   = 9                  <-- counted from first_entry

`check_live_readiness` published "best clock is day 9/14" from it -- an eight-day overstatement on
the one artifact that says whether the desk may arm capital -- and the promote lanes gate on
`days_active >= 14`, so the same row would have satisfied a forward window it had not served.
That is exactly the leakage the two-stage law exists to stop (LAWS L1.6/L1.58, RESEARCH 6a: the
gauntlet screens, only PRE-REGISTERED forward evidence promotes), and it is the desk's own
promotion rule 5 -- import the number, never restate it.

THE RULE. A consumer asks this module. It derives from `forward_start`, and it returns None --
UNMEASURED, never 0 and never the stored value -- when the row carries no stamp (L1.28a: absence
is a real answer and must never resolve to a clean verdict). Deriving can only ever SHORTEN a
reported window relative to a contaminated stored one, so this tightens gates and can never
loosen a rail.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

#: A consumer deriving at a slightly later `now` than the writer legitimately reads one day more.
#: Anything beyond that is a stored count the stamp cannot account for.
OVERSTATEMENT_TOLERANCE_DAYS = 1


def parse_stamp(value: Any) -> datetime | None:
    """Parse a forward_start stamp to an aware UTC datetime, or None if it is not one."""
    if value in (None, ""):
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)


def forward_days(row: Any, now: datetime | None = None) -> int | None:
    """Whole days elapsed since this row's pre-registered `forward_start`.

    Returns None when the row carries no parseable stamp. None is UNMEASURED: a caller must
    treat it as "has not served the window", never as zero days and never as a pass.
    """
    if not isinstance(row, dict):
        return None
    start = parse_stamp(row.get("forward_start"))
    if start is None:
        return None
    now = now or datetime.now(tz=UTC)
    return max(0, (now - start).days)


def served_window(row: Any, min_days: int, now: datetime | None = None) -> bool:
    """True only when the DERIVED window is at least `min_days`. Unstamped fails closed."""
    days = forward_days(row, now)
    return days is not None and days >= min_days


def overstatement(row: Any, now: datetime | None = None) -> int | None:
    """Days by which a row's STORED `days_active` exceeds what its own stamp allows.

    None when there is nothing to compare (no stamp, or no stored count). A positive value is a
    contaminated day count: the row is being credited with forward time it did not serve.
    """
    derived = forward_days(row, now)
    if derived is None or not isinstance(row, dict):
        return None
    stored: object = row.get("days_active")
    if not isinstance(stored, (int, float, str)) or isinstance(stored, bool):
        return None
    try:
        stored_i = int(stored)
    except (TypeError, ValueError):
        return None
    gap = stored_i - derived - OVERSTATEMENT_TOLERANCE_DAYS
    return gap if gap > 0 else None


def overstated_rows(rows: dict[str, Any],
                    now: datetime | None = None) -> dict[str, dict[str, int]]:
    """Every row whose stored day count outruns its own pre-registration stamp."""
    out: dict[str, dict[str, int]] = {}
    for key, row in (rows or {}).items():
        gap = overstatement(row, now)
        if gap is not None:
            out[key] = {"stored": int(row["days_active"]),
                        "derived": int(forward_days(row, now) or 0),
                        "overstated_by": int(gap)}
    return out
