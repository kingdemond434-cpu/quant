"""CLOCK PROVENANCE (L1.46) -- which clock stamped this row, and what is the offset.

THE DEFECT THIS EXISTS FOR. Every recorder writes its timestamp into a field called `t`, and `t`
means two different things in the same file:

    run_recorder.py:232   {"t": int(time.time() * 1000), "k": "d", ...}   <- OUR clock
    run_recorder.py:249   {"t": int(tr["T"]),            "k": "t", ...}   <- the VENUE's clock

Same name, same file, discriminated only by `k`, declared nowhere. Measured on disk in
data/moat/fut/BTCUSDT/20260725_07.jsonl.gz: 83 of 12,037 rows step BACKWARDS in `t`, the worst by
40.2 seconds. The corpus is 82% of all desk data and is not monotonic in its own time field.

THE COST IS NOT HYPOTHETICAL, AND IT IS NOT SMALL. Three of this desk's most prominent kills are
one defect class: kimchi_premium retracted as a ~73% timestamp artifact (E-02f2917dfb),
coinbase_premium_timing graveyarded as "close-timestamp microstructure", and R0060's leaky Upbit
look-ahead copies. The institutional response was a PROSE DUTY -- "DECLARE TIMESTAMP ALIGNMENT for
every cross-source series ... unstated alignment voids the screen" -- with no instrument. A duty
with no instrument is unsatisfiable by construction on the dataset it most needs to govern.

WHY A LIBRARY AND NOT A CONVENTION. moat_audit.py:71 read

    "t": d.get("t") or d.get("E") or d.get("ts")

-- the desk's own auditor coalescing three different clocks into one field, silently preferring
whichever happened to be present. A convention that every reader must remember is a convention
every reader will eventually forget. This module is the single place that knows.

BACKWARD COMPATIBILITY IS THE WHOLE DESIGN. 7.5 GB of tape already exists with no provenance
marker. Those rows are not ambiguous to US -- we wrote the code that stamped them, so their clock
is KNOWN, per (venue, kind), from the recorder source. _HISTORICAL encodes that knowledge, so the
existing corpus becomes readable rather than being written off. New rows carry an explicit `c`
marker and stop depending on inference at all.

THE FIX IS ADDITIVE, NEVER A RENAME. `t` keeps its existing meaning per (venue, kind); the venue
stamp arrives ALONGSIDE it. Renaming `t` would have broken every one of the 20 readers of the moat
corpus at once, to fix an ambiguity that a new field fixes at zero blast radius.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

#: The field that declares which clock stamped `t`. One byte of key, and it is the difference
#: between a measured alignment and an assumed one.
MARKER = "c"

#: `t` came from the venue's own stamp -- the event happened at `t` by the venue's reckoning.
CLOCK_VENUE = "venue"
#: `t` is OUR receipt instant. The event happened at some unknown earlier time.
CLOCK_RECV = "recv"
#: `t` is our receipt AND the venue offers no stamp on this endpoint at all. Distinct from
#: CLOCK_RECV: recv means "we also kept the venue's", recv_only means "there is none to keep".
#: Collapsing the two would let a venue limitation read exactly like a desk defect.
CLOCK_RECV_ONLY = "recv_only"
#: A (venue, kind) this module has never been taught. Never guessed -- see clock_of().
CLOCK_UNKNOWN = "unknown"

#: What stamped `t` for rows written BEFORE the provenance marker existed, per (venue, kind).
#: Read directly off the recorder sources; every entry cites the line it was read from. This is
#: knowledge, not inference: an unmarked row is unambiguous once you know which code wrote it.
_HISTORICAL: dict[tuple[str, str], str] = {
    ("fut", "d"): CLOCK_RECV,          # run_recorder.py:232      int(time.time() * 1000)
    ("fut", "t"): CLOCK_VENUE,         # run_recorder.py:249      int(tr["T"])
    ("spot", "d"): CLOCK_RECV_ONLY,    # run_recorder_spot.py:243 -- /api/v3/depth returns no stamp
    ("spot", "t"): CLOCK_VENUE,        # run_recorder_spot.py:260 int(tr["T"])
    ("bybit", "depth"): CLOCK_RECV,    # run_recorder_bybit.py:152 int(time.time() * 1000)
    ("bybit", "trades"): CLOCK_RECV,   # run_recorder_bybit.py:159 batch receipt; inner rows carry
                                       #   their own venue `time` -- see inner_venue_ms()
    ("bybit", "meta"): CLOCK_RECV,     # run_recorder_bybit.py:167 int(now * 1000)
}

#: Where the venue's own stamp lives on a NEW-schema row, per venue. Depth endpoints only; trade
#: rows are already venue-stamped in `t`. Ordered by preference -- Binance `E` (event time, when
#: the venue published) is the honest observation instant; `T` (transaction time) is the matching
#: instant and runs a few ms earlier.
_VENUE_FIELDS: dict[str, tuple[str, ...]] = {
    "fut": ("E", "T"),
    "spot": (),                        # /api/v3/depth genuinely returns none -- a venue limit
    "bybit": ("vt",),                  # result.ts, retained as "vt" to avoid colliding with `t`
}

#: Field names that carry a TIMESTAMP somewhere in this desk's tapes or the venue payloads they
#: come from. Used to tell a legitimate schema-spelling coalesce (`d.get("b") or d.get("bids")` --
#: two names for one quantity) from a clock coalesce (`d.get("t") or d.get("E")` -- two names for
#: two DIFFERENT instants). Only the second is the L1.46 defect, and a check that cannot tell them
#: apart fires on healthy code until somebody switches it off.
CLOCK_FIELDS: frozenset[str] = frozenset({
    "t", "r", "E", "T", "ts", "vt", "cts", "time", "eventTime", "transactTime", "timestamp"})

#: Endpoints where the venue publishes no timestamp AT ALL. A permanent venue property, not a
#: desk defect -- the fence must never demand a stamp that does not exist, or it cries wolf.
RECV_ONLY_STREAMS: frozenset[tuple[str, str]] = frozenset({("spot", "d")})

#: Configured poll periods, seconds, read from the recorder sources. Held here so the fence can
#: compare CONFIGURED against MEASURED: a constant that is 64% wrong is inherited as truth by
#: every downstream consumer that reads it instead of measuring.
CONFIGURED_PERIOD_S: dict[tuple[str, str], float] = {
    ("fut", "d"): 5.0,                 # run_recorder.py       _DEPTH_EVERY_S
    ("spot", "d"): 5.0,                # run_recorder_spot.py  _DEPTH_EVERY_S
    ("bybit", "depth"): 4.0,           # run_recorder_bybit.py _DEPTH_EVERY_S
}


def venue_of_path(path: Path | str) -> str:
    """Which recorder wrote this file, from its position under data/moat/<venue>/<SYMBOL>/.

    Returns "" when the path is not a moat tape -- the caller decides what that means, because a
    silent default here would attribute a stranger's file to a venue and mis-read every clock in
    it.
    """
    parts = Path(path).resolve().parts
    if "moat" not in parts:
        return ""
    i = parts.index("moat")
    return parts[i + 1] if i + 1 < len(parts) else ""


def clock_of(row: dict[str, Any], venue: str) -> str:
    """Which clock stamped row["t"].

    The explicit marker wins when present. Otherwise the (venue, kind) pair is looked up in
    _HISTORICAL -- knowledge read off the recorder source, not a guess.

    Returns CLOCK_UNKNOWN for a pair this module has never been taught, and that is deliberate: a
    new stream that nobody has classified must read as UNKNOWN so the fence reports it, rather
    than defaulting to the common case and being silently wrong on exactly the row that is new.
    """
    marked = row.get(MARKER)
    if isinstance(marked, str) and marked in (CLOCK_VENUE, CLOCK_RECV, CLOCK_RECV_ONLY):
        return marked
    kind = row.get("k")
    if not isinstance(kind, str):
        return CLOCK_UNKNOWN
    return _HISTORICAL.get((venue, kind), CLOCK_UNKNOWN)


def _as_ms(value: Any) -> int | None:
    """A millisecond epoch, or None. Venues return these as str and as int interchangeably."""
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return None
    # Bounds catch a seconds-vs-millis mixup, which is the one units error that produces a
    # plausible-looking number rather than an obvious one: 2001-09-09 to 2286-11-20 in ms.
    return ms if 1_000_000_000_000 <= ms <= 9_999_999_999_999 else None


def venue_ms(row: dict[str, Any], venue: str) -> int | None:
    """The venue's own stamp for this row, or None when the venue offers/offered none."""
    if clock_of(row, venue) == CLOCK_VENUE:
        return _as_ms(row.get("t"))
    for field in _VENUE_FIELDS.get(venue, ()):
        ms = _as_ms(row.get(field))
        if ms is not None:
            return ms
    return None


def recv_ms(row: dict[str, Any], venue: str) -> int | None:
    """OUR receipt instant for this row, or None when only the venue stamp was retained."""
    if clock_of(row, venue) in (CLOCK_RECV, CLOCK_RECV_ONLY):
        return _as_ms(row.get("t"))
    return _as_ms(row.get("r"))


def delta_ms(row: dict[str, Any], venue: str) -> int | None:
    """Delta = t_recv - t_venue: our end-to-end observation latency for this record.

    None when either clock is missing -- which is the normal state of the pre-marker corpus and
    precisely what the fence counts. This series is structurally unbuyable: a vendor can sell the
    venue's stamp or THEIR box's receipt, never when a message reached OURS, and it cannot be
    backfilled after the fact.
    """
    r, v = recv_ms(row, venue), venue_ms(row, venue)
    return None if r is None or v is None else r - v


def inner_venue_ms(row: dict[str, Any]) -> int | None:
    """Newest venue stamp inside a Bybit batched-trades payload.

    Bybit trade batches are stamped with OUR poll receipt on the outer row while every inner trade
    carries the venue's own `time`. That makes Delta measurable RETROSPECTIVELY across the whole
    existing archive at zero collection cost -- the archive contains its own control. The newest
    inner stamp is the right one: it is the most recent event the venue could have shown us, so
    receipt-minus-newest is observation latency plus at most one trade-arrival gap.
    """
    rows = row.get("v")
    if not isinstance(rows, list):
        return None
    stamps = [ms for ms in (_as_ms(r.get("time")) for r in rows if isinstance(r, dict))
              if ms is not None]
    return max(stamps) if stamps else None


def sort_key(row: dict[str, Any], venue: str) -> tuple[int, int]:
    """An ordering key that is monotonic across a MIXED-CLOCK file.

    A reader that sorts the raw `t` interleaves two clocks and silently reorders events -- which
    is the mechanism behind every timestamp-artifact kill in the graveyard. Receipt time is the
    honest common axis: it is the only instant the desk observed BOTH kinds of row at, so it is
    the only one on which "what did we know, and when" is answerable. Rows whose receipt cannot be
    recovered sort by their own `t` and are flagged by the second element, never dropped.
    """
    r = recv_ms(row, venue)
    if r is not None:
        return (r, 0)
    return (_as_ms(row.get("t")) or 0, 1)
