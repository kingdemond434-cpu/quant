"""R0523 -- THE FUNDING INTERVAL, AS OF A DATE, DERIVED FROM STAMPS RATHER THAN ASSERTED.

WHY THIS EXISTS RATHER THAN A JOIN TO `data/funding_caps.json`. That file is the only per-symbol
`fundingIntervalHours` on disk and it is a SINGLE-INSTANT SNAPSHOT: one file-level `fetched_at`,
no per-symbol as-of date, no history. Joining it to the 2019-2026 D1 panel asserts today's cadence
for every past bar, which is the `pct_circ_now` class this desk has already paid for once:

    "A `_now` field joined to historical events is a silent look-ahead in the CONDITIONING
     variable even when the return series is spotless -- and it fails toward a FALSE NULL, which
     is the direction no gate on this desk would ever catch."

AND THE DRIFT IS MEASURED, NOT HYPOTHETICAL. The R0523 card recorded 426/812 symbols on 4h at
2026-08-12; the same file on 2026-08-19 reads 445 on 4h, 314 on 8h, 1 on 1h of 760. The mix moved
in seven days. WORSE, THE LABEL IS ENDOGENOUS TO THE OUTCOME: a venue shortens a symbol's interval
in response to that symbol's own funding behaviour, so today's "4h" encodes the recent past of the
very series being predicted. That is not a stale label, it is the outcome leaking into the
conditioner.

THE LOOK-AHEAD-FREE SOURCE WAS ALREADY BEING COLLECTED AND DISCARDED (L1.28a). Every hourly row of
`data/funding_cross_section.jsonl` carries `next_funding_ms` per symbol -- the venue's own next
settlement stamp, as of that snapshot's receipt clock. The interval follows from WHICH UTC grid
that stamp sits on, using nothing from the future.

THE CATCH, AND IT IS THE WHOLE DESIGN. The 8h grid (00/08/16) is a SUBSET of the 4h grid
(00/04/08/12/16/20), so at most instants the two classes point at the SAME next stamp and are
indistinguishable. Measured on the desk's own tape:

    2026-08-05T11:52Z   next-stamp histogram {12: 519, 16: 305}   <- SEPARATES (12:00 is 4h-only)
    2026-08-13T06:07Z   next-stamp histogram {7: 11, 8: 820}      <- BLIND (08:00 is on both)
    2026-08-19T13:07Z   next-stamp histogram {14: 11, 16: 833}    <- BLIND (16:00 is on both)

So a snapshot is DISCRIMINATING only when the next 4h boundary is not also an 8h boundary -- the
hours after 00, 08 and 16. A blind snapshot yields None for every symbol, and None NEVER becomes
8.0: `libs/data/funding_caps.py:96-108` is emphatic that an unknown cadence must not be defaulted,
and defaulting here would silently label every 4h name as 8h in exactly the windows where the
measurement fails.

WHAT THIS DOES NOT DO. It does not make R0523 screenable today. The tape spans 2026-08-05 onward,
which is fewer observations than the screen's own 21-row z-score warm-up, so any daily screen built
on it is UNDERPOWERED BY CONSTRUCTION and must report that rather than a verdict. What it does is
start the clock: from today the desk accrues a look-ahead-free interval panel over ~830 symbols
from data it was already paying to collect, which is the observation L1.45 says to go and buy
rather than infer.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

_H = 3_600_000
_DAY = 86_400_000

#: The two cadences that actually populate the venue's USDT-M book. 1h symbols exist (1 of 760 at
#: last read) and are detected as "neither grid", never forced into one.
GRID_4H = (0, 4, 8, 12, 16, 20)
GRID_8H = (0, 8, 16)

def _next_boundary(t_ms: int, grid: tuple[int, ...]) -> int:
    """The first stamp strictly after ``t_ms`` on ``grid``."""
    day = (t_ms // _DAY) * _DAY
    for h in grid:
        cand = day + h * _H
        if cand > t_ms:
            return cand
    return day + _DAY + grid[0] * _H


def discriminating(t_ms: int) -> bool:
    """Can a snapshot taken at ``t_ms`` separate a 4h symbol from an 8h one?

    Only when the next 4h boundary is not ALSO the next 8h boundary. Derived by comparing the two
    grids rather than from a hand-written hour list: the first version of this function carried
    the list and got it wrong (it tested three exact hours instead of three four-hour RANGES), and
    the tests built from the measured tape caught it. The blind windows are (04,08], (12,16] and
    (20,24]; the discriminating ones are (00,04], (08,12] and (16,20].
    """
    return _next_boundary(t_ms, GRID_4H) != _next_boundary(t_ms, GRID_8H)


def as_of_intervals(snapshot: Mapping[str, Any]) -> dict[str, float | None]:
    """Per-symbol funding interval AS OF this snapshot, from its own `next_funding_ms` stamps.

    Returns {} when the snapshot cannot discriminate or carries no stamps. A symbol whose stamp
    matches neither grid maps to None -- an UNKNOWN cadence (a 1h symbol, a special settlement, or
    a stamp we do not understand), never a default. Absence resolving to 8.0 would mislabel every
    4h name in exactly the windows where the measurement fails (L1.28a).
    """
    t = int(snapshot.get("t") or 0)
    stamps = snapshot.get("next_funding_ms")
    if t <= 0 or not isinstance(stamps, Mapping) or not discriminating(t):
        return {}
    b4 = _next_boundary(t, GRID_4H)
    b8 = _next_boundary(t, GRID_8H)
    out: dict[str, float | None] = {}
    for sym, raw in stamps.items():
        try:
            nf = int(raw)
        except (TypeError, ValueError):
            out[str(sym)] = None
            continue
        if nf == b4:
            out[str(sym)] = 4.0
        elif nf == b8:
            out[str(sym)] = 8.0
        else:
            out[str(sym)] = None          # neither grid: 1h, or a cadence we cannot name
    return out


def build_history(snapshots: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """A look-ahead-free (date, symbol) -> interval panel, with its own coverage and attrition.

    One reading per UTC date per symbol, taken from that date's discriminating snapshots. Where a
    symbol's readings disagree WITHIN a date the value is None and the disagreement is counted: a
    venue can move a symbol mid-day, and silently picking one reading would invent a certainty the
    stamps do not support.
    """
    per_date: dict[str, dict[str, set[float]]] = {}
    attempted = 0
    blind = 0
    unusable = 0
    for snap in snapshots:
        attempted += 1
        if not isinstance(snap, Mapping):
            unusable += 1
            continue
        t = int(snap.get("t") or 0)
        if t <= 0:
            unusable += 1
            continue
        if not discriminating(t):
            blind += 1                    # COUNTED, never a silent skip (L1.60)
            continue
        day = datetime.fromtimestamp(t / 1000, UTC).date().isoformat()
        got = as_of_intervals(snap)
        if not got:
            unusable += 1
            continue
        bucket = per_date.setdefault(day, {})
        for sym, iv in got.items():
            if iv is not None:
                bucket.setdefault(sym, set()).add(iv)

    panel: dict[str, dict[str, float]] = {}
    conflicts = 0
    for day, syms in per_date.items():
        row: dict[str, float] = {}
        for sym, vals in syms.items():
            if len(vals) == 1:
                row[sym] = next(iter(vals))
            else:
                conflicts += 1            # mid-day move, or a stamp we misread: refuse, count it
        panel[day] = row

    dates = sorted(panel)
    all_syms = sorted({s for r in panel.values() for s in r})
    return {
        "measured": bool(dates),
        "snapshots_attempted": attempted,
        "snapshots_blind": blind,
        "snapshots_unusable": unusable,
        "snapshots_used": attempted - blind - unusable,
        "dates": dates,
        "n_dates": len(dates),
        "n_symbols": len(all_syms),
        "intra_day_conflicts": conflicts,
        "panel": panel,
        "clock": ("interval derived from the venue's own next-settlement stamp as of each "
                  "snapshot's receipt clock `t`; nothing from the future is read (L1.46)"),
        "note": ("a BLIND snapshot is one whose next 4h boundary is also an 8h boundary "
                 "(the hours after 04, 12 and 20) -- it cannot separate the classes and yields "
                 "nothing, rather than a default"),
    }
