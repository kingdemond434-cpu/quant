"""The tape on disk: append-only, content-addressed, and unable to lose a completed day.

THE INVARIANT, stated first because everything else is a consequence of it:

    NO WRITER EVER OPENS AN EXISTING SEGMENT FOR WRITING.

A day is a growing list of immutable segments. New ticks make a NEW segment. A crash, a power
cut, a full disk or an OOM kill during a write can therefore destroy at most the segment being
written -- which does not yet exist under its real name -- and can never touch a byte of what was
already captured. That is the property the previous two collectors on this desk did not have and
the reason this module exists:

  * `mt5desk/tape.py` reads the day's parquet, concatenates, and writes the whole day back over
    itself on every append. A crash inside that write leaves a truncated parquet where a
    complete day used to be, and the ticks that were in it are unbuyable.
  * `moat/moat_silver.py` says so in its own docstring: "the parquet is rewritten from the full
    day file". Same defect, one layer down.

Both are correct-looking code. Neither can survive the box rebooting at the wrong millisecond,
and the box reboots on Windows Update.

HOW A WRITE ACTUALLY HAPPENS, in order, because the order is the safety:

  1. Encode the ticks to parquet bytes IN MEMORY.
  2. Write them to `.tmp-<uuid>` in the destination directory. flush(), then os.fsync() -- the
     bytes are on the platter, not in the page cache.
  3. os.replace() to `<sha256[:16]>.parquet`. Atomic on POSIX and on Windows (MoveFileEx with
     REPLACE_EXISTING). There is no instant at which a partial file exists under a real name.
  4. fsync the directory where the platform allows it, so the rename itself is durable.
  5. Append one line to `_manifest.jsonl`, flush, fsync.
  6. ONLY NOW advance the cursor.

Every crash point in that sequence is safe, and the failure modes are asymmetric ON PURPOSE:

  crash before 3  ->  an orphan `.tmp-*` file. Swept at startup. Nothing was recorded, the cursor
                      did not move, the window is re-pulled. No loss.
  crash between 3 and 5 -> a segment on disk that the manifest does not name. `reconcile()` finds
                      it, reads the manifest row back out of the file's own parquet metadata, and
                      re-registers it. No loss, and the integrity report counts it.
  crash after 5, before 6 -> the cursor is behind the tape. The window is re-pulled and the same
                      ticks arrive again. DUPLICATES, which are removed on read and measured by
                      the integrity checker.

That last line is the whole philosophy: duplicates are a nuisance, holes are permanent. Every
ambiguity in this module is resolved toward re-reading rather than skipping.

CONTENT ADDRESSING. A segment's filename is the first 16 hex of the sha256 of its own bytes, and
the manifest carries the full 256-bit digest. Three things follow. Writing identical bytes twice
is idempotent rather than duplicative. A reader can prove a segment is the one that was written
rather than a file that happens to sit at that path. And a segment is fully self-describing: its
manifest row is embedded in the parquet's own key-value metadata, so a segment separated from
its manifest -- by a crash, a partial copy, a restore from backup -- can always be re-registered
without guessing.

COMPACTION, AND WHY A DESIGN THAT LOSES NOTHING STILL HAD TO CHANGE. One segment per 60-second
cycle is what makes a crash cost at most one cycle. It is also 1,440 parquet files per symbol per
day, and a parquet file has a floor price: MEASURED 2026-09-05 in this container, 3.0-3.8 KB of
footer per segment REGARDLESS of how many ticks are in it. At 1,440 segments that is 4.3 MB per
symbol per day of pure container -- more than the ticks themselves for every symbol on this
account except XAUUSD, and 1.09 GB/day across the 251-symbol universe. The "keep everything
forever" policy below was written against 3.05 B/tick measured on ONE segment holding a whole
day. The recorder does not write that file. The arithmetic was out by 34x and nobody would have
found it by reading the code, because the code is correct -- it is the WRITE PATTERN that is
expensive, and only a measurement of the write pattern shows it.

So a day that has stopped receiving is COMPACTED before it is sealed: its segments are read,
merged, deduped and rewritten as ONE segment, the manifest is replaced by the short one that
describes what is actually there, and the originals are removed. The invariant at the top of this
file is untouched -- compaction never opens an existing SEGMENT for writing; it writes a NEW
content-addressed one and only then retires what it replaced. Every crash point is safe in the
same asymmetric direction, and the ORDER is what makes it so:

  1 write the compacted segment  -> crash: an orphan; `reconcile` re-registers it from its own
                                    embedded row and the day reads as the compacted segment PLUS
                                    its sources: duplicates, removed on read, never a hole
  2 append its manifest row      -> crash: same, duplicates
  3 append the compaction row    -> crash: same; this row is audit, not correctness
  4 replace the manifest         -> crash: the long manifest stands and is still correct
  5 delete the retired files     -> crash: they become orphans, get re-registered, read as
                                    duplicates, and the next compaction folds them away again.
                                    It converges rather than repeating byte-for-byte: `written_at`
                                    is inside the hashed metadata, so two compactions of the same
                                    ticks are content-equal and digest-different. That costs one
                                    extra file in a rare path; what matters is that the day
                                    converges to one segment with every tick still in it.

The one order that would be fatal is retiring the sources BEFORE the compacted segment is in the
manifest: that window reads as an EMPTY day while every byte is intact on disk, which is the worst
outcome available here. It is why step 2 precedes steps 3 and 4 rather than being batched with
them, and the code says so at the call site.

THE MANIFEST IS PRUNED AT COMPACTION, AND THAT IS A DELIBERATE RETREAT FROM "APPEND-ONLY FOREVER".
1,440 per-cycle rows cost 620 KB per symbol-day -- MEASURED -- which across this universe is
57 GB/year to record which minute each container was opened in, for containers that no longer
exist and whose contents are proven by the compacted segment's digest. That is more than the ticks
cost. What survives in `_superseded.jsonl` is the count folded, the ticks in and out (so the
duplicate rate the overlap policy costs stays measurable), and the digest of the manifest as it
stood, so the chain from live capture to compacted day stays checkable against the seal. The
manifest replacement itself is atomic and the manifest is rebuildable from the segments' own
embedded rows, so this is the one file here where a rewrite cannot lose anything a reader needs.

THE ENCODING IS INTEGER POINTS, AND IT IS MEASURED, NOT PREFERRED. Prices are stored as
`round(price / point)` in int64 columns with parquet's DELTA_BINARY_PACKED encoding under zstd.
Measured on a synthetic tape at this broker's own observed tick rates (`tick_volume` from the
desk's H1 parquets: 125,898 ticks/day at the median symbol, 553,742 for XAUUSD):

    gzip-jsonl  (what moat_recorder writes today)   6.88 - 7.28 bytes/tick
    parquet float64 + zstd                          4.97 - 5.18 bytes/tick
    parquet int-points, plain + zstd                4.44 - 4.66 bytes/tick
    parquet int-points, DELTA_BINARY_PACKED + zstd  3.05 - 3.35 bytes/tick   <- this

2.2x smaller than the format the desk uses now, while the LOGICAL schema stays absolute -- a
reader reads `bid_pts`, not a delta chain, so one corrupt page cannot poison the rows after it.
`point` travels in every manifest row because it is part of the unit: a segment decoded with a
different point is a segment of wrong prices, and `symbol_info` reports TODAY's point, so
re-deriving a past day's unit from tomorrow's registry silently re-prices yesterday's tape.

ROUND-TRIP IS VERIFIED, NEVER ASSUMED. Every encode is decoded back in memory and compared to
the input at the symbol's own `digits`. If a single price fails to round-trip -- an odd tick
size, a broker quoting more precision than `digits` claims -- the segment is written as float64
instead and says so in `encoding`. Lossy compression of the desk's only unrecoverable asset is
not a trade this module is allowed to make silently.

THE GAP LEDGER IS THE OTHER HALF, and it is not optional. A gap that is silently absent is worse
than a gap that is recorded as a gap: a feature built on a silent hole reads the absence as calm,
and "the market was quiet" is exactly the wrong conclusion to draw from "our recorder was down".
Every window this desk did not capture gets a row naming the reason, and a window later
backfilled gets a RESOLVED row rather than an edit -- the ledger is append-only for the same
reason the tape is.

================================================================================================
THE RETENTION POLICY, AND THE ARITHMETIC THAT DECIDES IT

    FULL TICK RESOLUTION IS KEPT FOREVER. NOTHING IS EVER DOWNSAMPLED OR DELETED.
    A DAY IS COMPACTED ONCE IT STOPS RECEIVING. COMPACTION IS NOT DOWNSAMPLING:
    EVERY TICK SURVIVES IT BYTE-FOR-BYTE; ONLY THE CONTAINERS ARE MERGED.

That is a strong claim, so here is the measurement behind it rather than a preference. The
previous version of this section was an honest estimate and it was WRONG BY 34x, which is worth
recording: it priced the encoding, and the cost of this recorder is not the encoding.

WHAT A DAY COSTS. Tick rates are the broker's own, taken from the `tick_volume` column of the
desk's H1 parquets over 2026-06-01..2026-09-05 -- counted quote updates, not estimates:

    XAUUSD   553,742 ticks/day (median)    the heaviest instrument the desk holds
    GBPJPY   182,834
    EURUSD    82,744
    USDCHF    56,796                       the lightest of the 24 with H1 history here
    ---------------------------------------------------------------------------
    median across those 24 symbols: 125,898 ticks/day; sum 3,021,558 ticks/day

MEASURED 2026-09-05 IN THIS CONTAINER, writing a full synthetic trading day at each of those
rates THE WAY THE RECORDER ACTUALLY WRITES -- one segment per 60-second cycle, 1,440 segments,
plus the manifest and the seal:

    ticks/day    UNCOMPACTED  B/tick   B/segment      COMPACTED  B/tick   segments
      552,960    6.07 MB/day   11.51       3,830    1.030 MB/day    1.86   1440 -> 1
      181,440    5.41 MB/day   29.79       3,368    0.403 MB/day    2.22   1440 -> 1
       82,080    5.19 MB/day   63.23       3,215    0.200 MB/day    2.44   1440 -> 1
       56,160    5.16 MB/day   91.86       3,194    0.141 MB/day    2.51   1440 -> 1
       28,800    5.12 MB/day  177.78       3,165    0.078 MB/day    2.70   1440 -> 1
        1,440    4.95 MB/day  3438.0       3,051    0.008 MB/day    5.87   1440 -> 1

READ THE `B/segment` COLUMN, BECAUSE IT IS THE WHOLE FINDING. It barely moves with the tick rate:
a parquet file costs ~3.0-3.8 KB of footer whether it holds 57 ticks or 3,447. Of the 3.08 KB
measured on a 57-row segment, 1.40 KB is the irreducible schema footer for six columns, 1.13 KB
is the embedded SegmentRecord and 0.55 KB is column statistics. Stripping the embedded record
would save a third and destroy the self-describing recovery this store is built on, so the
container cost cannot be argued away -- it has to be AMORTISED. The compacted read-back is
verified byte-for-byte against the uncompacted one in `test_tape_store.py`, so "compaction is not
downsampling" is a test rather than a promise.

Uncompacted, the universe costs ~1.26 GB/day (~458 GB/year) and is ~85% container. Compacted at
seal it costs ~24 MB/day (~8.9 GB/year) and is ~95% ticks. The estimate this section used to
carry -- "~32 MB/day, ~11.5 GB/year" -- happened to land near the compacted answer while being
blind to the containers entirely, which is worse than being wrong: it would have stayed
"confirmed" by the steady state right up until someone changed the cycle length.

THE OTHER 227 SYMBOLS ARE STILL AN EXTRAPOLATION AND ARE STILL LABELLED ONE. Only 24 of the 251
have H1 history on this host and they are the liquid end; the rest are equity CFDs and exotics
quoting far less. At an assumed 30,000 ticks/day each they add ~17.7 MB/day compacted on top of
the liquid 24's ~6.7 MB/day. The integrity report publishes `bytes_per_symbol_day` per symbol from
the tape itself, and that number REPLACES this paragraph within a day of the recorder running on
the box.

WHY "KEEP EVERYTHING" IS THE CORRECT POLICY AND NOT LAZINESS. The two sides of the trade are not
comparable quantities. On one side, roughly 11 GB a year -- a few pounds of disk, and less than
this desk's existing `data/` directory. On the other, an unbounded and permanent loss: a tick
discarded in 2026 cannot be re-acquired in 2029 at any price, from any vendor, because no archive
of one retail CFD broker's quote stream exists or ever will. A downsampling policy trades an
infinite-cost, irreversible loss against a rounding error on a hosting bill. There is no
discount rate at which that is a good trade, and the desk has already made the mistake in the
other direction: the crypto recorders' gzip-jsonl filled a disk at 2.2x this format's cost, and
the lesson taken from that was "record less", when the available lesson was "encode better".

WHAT IS DOWNSAMPLED, because something is. The DERIVED layers are cache, not asset:

    data/tape/ticks/<SYM>/<DAY>.parquet     silver, rebuildable from bronze in seconds
    data/tape/intrabar/<SYM>/<FREQ>/...     per-bar paths, rebuildable
    data/cost_surface_tick.json             a rebuildable aggregate

Those may be pruned to the last 90 days whenever disk pressure appears, because every one of
them is a pure function of the bronze tape and can be rebuilt. The manifests, the seals, the
superseded ledger, the gap ledger and the clock-skew rows are kept forever too: together they are
a few hundred bytes per symbol-day and they are what makes the tape auditable rather than merely
large.

THE PRESSURE VALVE IS PAUSING, NEVER PRUNING. When free space falls below the recorder's floor
it stops capturing and says so. It does not delete tape to make room. A recorder that can destroy
an unbuyable asset to acquire a cheaper one will eventually do it on a day the disk filled for an
entirely unrelated reason.

TRANSIENT PEAK IS THE NUMBER THE DISK FLOOR HAS TO CLEAR, not the steady state. A day is
uncompacted from its first tick until roughly six hours after it ends, so at any instant the tape
holds up to ~1.3 days uncompacted (1.4 GB across the universe) on top of the compacted history.
The 10 GB default floor clears that with room; a box with a smaller disk should raise the floor
rather than shorten `seal_after_hours`, because sealing early is a false completeness claim and
disk is cheaper than a lie.

FALSIFIER, stated so this policy can be overturned by evidence rather than by opinion: if the
measured `bytes_per_symbol_day` across the full 251-symbol universe exceeds ~200 MB/day COMPACTED
(6x the measurement above, i.e. ~70 GB/year), the arithmetic is no longer a rounding error and
the right response is a tiered policy -- full ticks for the traded universe, 1-second aggregates
for the rest -- decided on that measurement. The uncompacted figure is not the one to judge
against: it is a transient, and judging a policy on a transient is how a recorder gets throttled
for a cost it does not actually carry.
================================================================================================
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections.abc import Iterable, Iterator
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

SCHEMA = "mt5-tape-1"

#: Columns a segment always carries, whatever the encoding. `flags` says WHICH of bid/ask/last
#: changed on this tick, which is the difference between a quote revision and a repeat and is
#: not reconstructible from the prices alone.
TICK_COLUMNS = ("time_msc", "bid_pts", "ask_pts", "last_pts", "volume", "flags")

#: zstd level 9. Level 19 buys a further ~5% for several times the CPU, on a box that also runs
#: the live terminal; the recorder must never be the reason an order is late.
ZSTD_LEVEL = 9

_TMP_PREFIX = ".tmp-"
_MANIFEST = "_manifest.jsonl"
_SEAL = "_sealed.json"
#: Which segments a compaction folded into which. Append-only, like the manifest and the gap
#: ledger, and for the same reason: an edit is an opportunity to lose a row, and the one thing
#: this store may never do is forget that a segment existed.
_SUPERSEDED = "_superseded.jsonl"
_SEG_RE = re.compile(r"^[0-9a-f]{16}\.parquet$")

#: Reason codes for the gap ledger. Every one of these is a DIFFERENT question for the person
#: reading the integrity report, which is why they are not collapsed into "missing".
GAP_COLD_START = "COLD_START"                    # never recorded; history before us is not ours
GAP_RECORDER_DOWN = "RECORDER_DOWN"              # wall-clock hole between cycles
GAP_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"    # terminal not connected this cycle
GAP_PULL_FAILED = "PULL_FAILED"                  # the broker call raised or returned None
GAP_PULL_EMPTY = "PULL_EMPTY"                    # the call succeeded and there was nothing there
GAP_SYMBOL_ADDED = "SYMBOL_ADDED"                # newly listed; everything before is not ours
GAP_SYMBOL_REMOVED = "SYMBOL_REMOVED"            # delisted or hidden; capture stops here
GAP_TRUNCATED = "TRUNCATED"                      # pull hit its cap; the tail is deferred
GAP_DISK_FLOOR = "DISK_FLOOR"                    # capture paused to protect the box
GAP_WRITE_FAILED = "WRITE_FAILED"                # the segment did not land; cursor did not move
GAP_RESOLVED = "RESOLVED"                        # a previously recorded gap was later filled

GAP_REASONS: tuple[str, ...] = (
    GAP_COLD_START, GAP_RECORDER_DOWN, GAP_SOURCE_UNAVAILABLE, GAP_PULL_FAILED, GAP_PULL_EMPTY,
    GAP_SYMBOL_ADDED, GAP_SYMBOL_REMOVED, GAP_TRUNCATED, GAP_DISK_FLOOR, GAP_WRITE_FAILED,
    GAP_RESOLVED,
)


def broker_day(time_msc: int) -> str:
    """The day a broker-clock millisecond belongs to, as an ISO date string.

    DELIBERATELY NAMED `broker_day` AND NOT `utc_day`. MT5 stamps ticks in the SERVER's timezone
    and the Python API hands the integer through unconverted, so this is the broker's calendar
    day, which for a Europe/Athens-style server rolls at 21:00 or 22:00 UTC depending on DST.
    Partitioning on the broker's own day is the right choice -- it keeps a trading session in one
    file -- but a reader who thinks it is UTC will be out by hours across a DST change. The
    recorder writes `clock_probe` rows beside the tape so the offset is always recoverable.
    """
    return datetime.fromtimestamp(time_msc / 1000.0, tz=UTC).date().isoformat()


@dataclass(frozen=True)
class SegmentRecord:
    """One immutable slice of one symbol's day. This IS the manifest row and the parquet's
    embedded metadata -- one definition, so the two can never disagree."""

    schema: str
    symbol: str
    day: str
    sha256: str
    rows: int
    first_ms: int
    last_ms: int
    point: float
    digits: int
    encoding: str            # "int_points" or "f64"
    bytes: int
    written_at: str
    cycle_id: str = ""
    #: Set when this segment was re-registered by `reconcile` after a crash between the rename
    #: and the manifest append. Counted by the integrity report -- a recovery is a fact, not a
    #: detail to hide.
    recovered: bool = False
    #: Set when this segment is the OUTPUT of a compaction rather than a live capture. It carries
    #: the ticks of many cycles, so its `cycle_id` names no single one; the segments it replaced
    #: are named in `_superseded.jsonl` beside it.
    compacted: bool = False

    @property
    def filename(self) -> str:
        return f"{self.sha256[:16]}.parquet"


@dataclass(frozen=True)
class GapRecord:
    """A window this desk did not capture, and why. Append-only; never edited."""

    symbol: str
    from_ms: int
    to_ms: int
    reason: str
    detail: str = ""
    detected_at: str = ""
    cycle_id: str = ""
    #: For a RESOLVED row: how many ticks the backfill actually recovered.
    recovered_ticks: int = 0

    @property
    def seconds(self) -> float:
        return max(0.0, (self.to_ms - self.from_ms) / 1000.0)


@dataclass
class DaySeal:
    """A day declared complete: the segments it holds and the digest of that list.

    Sealing does not make the day immutable -- the segments already were. It records that the
    recorder believes nothing further will arrive, so the integrity checker can distinguish
    "today, still filling" from "a finished day with a hole in it", which are different alarms.
    """

    schema: str
    symbol: str
    day: str
    segments: int
    rows: int
    first_ms: int
    last_ms: int
    bytes: int
    manifest_sha256: str
    sealed_at: str
    gaps: int = 0
    gap_seconds: float = 0.0
    orphans_recovered: int = 0
    #: Segments folded away by compaction. Their manifest rows are still there; their files are
    #: not, and that is a recorded fact rather than a missing file.
    superseded: int = 0
    notes: list[str] = field(default_factory=list)


def _fsync_dir(path: Path) -> None:
    """Make a rename durable. Silently skipped where the platform will not open a directory --
    Windows is one of them, and a best-effort fsync is not worth failing a capture over."""
    fd = None
    try:
        fd = os.open(str(path), os.O_RDONLY)
        os.fsync(fd)
    except (OSError, AttributeError, PermissionError):
        pass
    finally:
        if fd is not None:
            with suppress(OSError):
                os.close(fd)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Durably place `payload` at `path`, or leave `path` exactly as it was."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f"{_TMP_PREFIX}{uuid.uuid4().hex}"
    with open(tmp, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def _append_line(path: Path, line: str) -> None:
    """Append one durable line. Opened per call rather than held open: a recorder that holds a
    file handle across a terminal restart is a recorder holding a handle to a deleted inode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def encode_segment(ticks: np.ndarray, symbol: str, day: str, point: float, digits: int,
                   cycle_id: str = "", compacted: bool = False) -> tuple[bytes, SegmentRecord]:
    """Ticks -> (parquet bytes, manifest row). Pure: touches no disk, so it is fully testable.

    The round trip is VERIFIED here rather than trusted. `round(price / point)` is exact for
    every sane (price, point) pair, but "sane" is an assumption about a broker's quoting, and
    this desk's whole cost is made of assumptions about brokers that turned out to be wrong on
    exactly one asset class. If the integer encoding cannot reproduce the input at the symbol's
    own `digits`, the segment falls back to float64 and SAYS SO in `encoding` -- a bigger file is
    a cost, a wrong price is a loss.
    """
    if ticks.size == 0:
        raise ValueError("refusing to encode an empty segment -- an empty capture is a GAP row, "
                         "not a zero-row file that reads as a successful write")
    tms = np.asarray(ticks["time_msc"], dtype=np.int64)
    bid = np.asarray(ticks["bid"], dtype=np.float64)
    ask = np.asarray(ticks["ask"], dtype=np.float64)
    last = np.asarray(ticks["last"], dtype=np.float64)
    vol = np.asarray(ticks["volume"], dtype=np.int64)
    flags = np.asarray(ticks["flags"], dtype=np.int64)

    encoding = "int_points"
    if point > 0:
        cols = {}
        ok = True
        # A THOUSANDTH OF A POINT. The first version of this check rounded BOTH sides to `digits`
        # before comparing, which made it structurally unable to see the case it exists for: a
        # broker quoting finer than its own `digits` claims. Rounding the input first means the
        # extra precision is destroyed on both sides of the comparison and the encoder reports a
        # clean round trip while silently discarding it. Caught by
        # test_a_price_that_cannot_round_trip_falls_back_to_float_and_says_so.
        #
        # The comparison is now against the RAW price with a tolerance chosen against the two
        # real magnitudes: float64 representation noise on a decoded integer price is ~1e-11
        # points, and any sub-point quoting that could matter is at least 1e-2 points. 1e-4
        # points sits three orders clear of the noise and two clear of anything meaningful.
        atol = point * 1e-4
        for name, arr in (("bid", bid), ("ask", ask), ("last", last)):
            pts = np.rint(arr / point).astype(np.int64)
            if not np.allclose(pts * point, arr, rtol=0.0, atol=atol):
                ok = False
                break
            cols[name] = pts
        if ok:
            table = pa.table({
                "time_msc": pa.array(tms, pa.int64()),
                "bid_pts": pa.array(cols["bid"], pa.int64()),
                "ask_pts": pa.array(cols["ask"], pa.int64()),
                "last_pts": pa.array(cols["last"], pa.int64()),
                "volume": pa.array(vol, pa.int64()),
                "flags": pa.array(flags, pa.int64()),
            })
        else:
            encoding = "f64"
    else:
        encoding = "f64"

    if encoding == "f64":
        table = pa.table({
            "time_msc": pa.array(tms, pa.int64()),
            "bid": pa.array(bid, pa.float64()),
            "ask": pa.array(ask, pa.float64()),
            "last": pa.array(last, pa.float64()),
            "volume": pa.array(vol, pa.int64()),
            "flags": pa.array(flags, pa.int64()),
        })

    rec_stub = SegmentRecord(
        schema=SCHEMA, symbol=symbol, day=day, sha256="", rows=int(tms.size),
        first_ms=int(tms.min()), last_ms=int(tms.max()), point=float(point), digits=int(digits),
        encoding=encoding, bytes=0, written_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        cycle_id=cycle_id, compacted=bool(compacted),
    )
    meta = {k: json.dumps(v) for k, v in asdict(rec_stub).items()}
    table = table.replace_schema_metadata({**meta, "schema_name": SCHEMA})

    delta = {c: "DELTA_BINARY_PACKED" for c in table.column_names
             if pa.types.is_integer(table.schema.field(c).type)}
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="zstd", compression_level=ZSTD_LEVEL,
                   use_dictionary=False, data_page_version="2.0",
                   column_encoding=delta or None, write_statistics=True)
    payload = sink.getvalue().to_pybytes()
    digest = hashlib.sha256(payload).hexdigest()
    rec = SegmentRecord(**{**asdict(rec_stub), "sha256": digest, "bytes": len(payload)})
    return payload, rec


def decode_segment(payload_or_path: bytes | Path) -> pd.DataFrame:
    """A segment back to bid/ask/last in PRICE units, whatever it was encoded as.

    The `point` comes out of the file's own embedded metadata, never out of today's registry.
    """
    if isinstance(payload_or_path, bytes):
        table = pq.read_table(pa.BufferReader(payload_or_path))
    else:
        table = pq.read_table(payload_or_path)
    meta = table.schema.metadata or {}

    def _m(key: str, default: Any) -> Any:
        raw = meta.get(key.encode())
        if raw is None:
            return default
        try:
            return json.loads(raw.decode())
        except (ValueError, UnicodeDecodeError):
            return default

    point = float(_m("point", 0.0))
    df = table.to_pandas()
    if "bid_pts" in df.columns:
        if point <= 0:
            raise ValueError("int-points segment carries no point in its metadata -- refusing to "
                             "guess the unit (a guessed point is a wrong price)")
        for src, dst in (("bid_pts", "bid"), ("ask_pts", "ask"), ("last_pts", "last")):
            df[dst] = df[src].astype("int64") * point
        df = df.drop(columns=["bid_pts", "ask_pts", "last_pts"])
    df["symbol"] = str(_m("symbol", ""))
    return df[["time_msc", "bid", "ask", "last", "volume", "flags", "symbol"]]


def segment_record_from_file(path: Path) -> SegmentRecord | None:
    """Read a segment's own manifest row back out of it. THIS IS WHAT MAKES RECOVERY POSSIBLE.

    A segment that lost its manifest line to a crash is not a mystery file: it carries its own
    row. Returns None only for a file that is not a segment of this schema.
    """
    try:
        meta = pq.read_schema(path).metadata or {}
    except (OSError, pa.ArrowInvalid, ValueError):
        return None
    fields: dict[str, Any] = {}
    for key in SegmentRecord.__dataclass_fields__:
        raw = meta.get(key.encode())
        if raw is None:
            continue
        try:
            fields[key] = json.loads(raw.decode())
        except (ValueError, UnicodeDecodeError):
            return None
    if fields.get("schema") != SCHEMA:
        return None
    try:
        size = path.stat().st_size
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
    fields["bytes"] = size
    fields["sha256"] = digest
    fields["recovered"] = True
    try:
        return SegmentRecord(**fields)
    except TypeError:
        return None


class TapeStore:
    """The tape's filesystem. Every write goes through here; nothing else touches these paths."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.ticks_dir = self.root / "ticks"
        self.gaps_dir = self.root / "gaps"
        self.state_dir = self.root / "state"
        self.clock_dir = self.root / "clock"

    # ------------------------------------------------------------------ paths --
    def day_dir(self, symbol: str, day: str) -> Path:
        return self.ticks_dir / _safe(symbol) / day

    def manifest_path(self, symbol: str, day: str) -> Path:
        return self.day_dir(symbol, day) / _MANIFEST

    def seal_path(self, symbol: str, day: str) -> Path:
        return self.day_dir(symbol, day) / _SEAL

    def superseded_path(self, symbol: str, day: str) -> Path:
        return self.day_dir(symbol, day) / _SUPERSEDED

    def gap_path(self, symbol: str, day: str) -> Path:
        return self.gaps_dir / _safe(symbol) / f"{day}.jsonl"

    # ------------------------------------------------------------------ write --
    def write_segment(self, symbol: str, day: str, ticks: np.ndarray, point: float, digits: int,
                      cycle_id: str = "") -> SegmentRecord:
        """Durably add one immutable segment and register it. Returns its manifest row.

        Idempotent by content: writing the same ticks twice produces the same digest, the same
        filename and a manifest that names it once.
        """
        payload, rec = encode_segment(ticks, symbol, day, point, digits, cycle_id)
        dest = self.day_dir(symbol, day) / rec.filename
        # THE MANIFEST IS ONLY SCANNED WHEN THE DESTINATION ALREADY EXISTED, and that is a
        # measured cost rather than a micro-optimisation. By the end of a trading day the
        # manifest holds 1,440 rows and the naive form re-parses all of them on every write --
        # over a million json.loads per symbol-day, on a box that is also running the terminal
        # that holds live positions. A destination that did not exist a moment ago cannot be in
        # the manifest, so the scan is only needed on the collision path, which is exactly the
        # crash-between-rename-and-append case it exists to cover.
        existed = dest.exists()
        _atomic_write_bytes(dest, payload)                       # steps 2-4 of the write order
        if not existed or rec.sha256 not in {r.sha256 for r in self.manifest(symbol, day)}:
            _append_line(self.manifest_path(symbol, day),
                         json.dumps(asdict(rec), separators=(",", ":")))   # step 5
        return rec

    def manifest(self, symbol: str, day: str) -> list[SegmentRecord]:
        """Every segment this day is known to hold, in write order.

        A malformed line is SKIPPED AND COUNTED by `reconcile`, never silently dropped: a
        manifest that quietly shortens is a tape that quietly shortens.
        """
        path = self.manifest_path(symbol, day)
        out: list[SegmentRecord] = []
        if not path.exists():
            return out
        try:
            lines = path.read_text("utf-8").splitlines()
        except OSError:
            return out
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                out.append(SegmentRecord(**row))
            except (ValueError, TypeError):
                continue
        return out

    def compactions(self, symbol: str, day: str) -> list[dict[str, Any]]:
        """Every compaction this day has been through, newest last.

        WHAT THIS KEEPS AND WHAT IT LETS GO. It keeps the count of segments folded, the ticks in
        and out (so the duplicate rate the overlap policy costs stays measurable after the rows
        that showed it are gone), and the digest of the manifest as it stood -- enough to prove
        the seal's chain and to see that a compaction happened at all. It does NOT keep 1,440
        per-cycle rows. That history was MEASURED at 620 KB per symbol-day, which across this
        universe is 57 GB/year -- more than the ticks it describes -- to record which minute each
        container was opened in, for containers that no longer exist and whose contents are proven
        by the compacted segment's own digest. Paying more for the receipt than for the goods is
        not rigour.
        """
        path = self.superseded_path(symbol, day)
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        try:
            lines = path.read_text("utf-8").splitlines()
        except OSError:
            return out
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out

    def reconcile(self, symbol: str, day: str) -> dict[str, Any]:
        """Bring the manifest back into agreement with the directory. Safe to run any time.

        Three findings, all reported rather than fixed silently:
          orphans   a segment on disk the manifest does not name -- RE-REGISTERED from its own
                    embedded row (this is the crash-between-rename-and-append case)
          missing   a manifest row whose file is gone -- reported; nothing can bring it back and
                    pretending otherwise would make a hole read as a full day
          corrupt   a file whose bytes no longer hash to the digest the manifest recorded
        """
        d = self.day_dir(symbol, day)
        rows = self.manifest(symbol, day)
        by_name = {r.filename: r for r in rows}
        orphans, missing, corrupt, swept = [], [], [], []
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.name.startswith(_TMP_PREFIX):
                    # A temp file is a crash before the rename: nothing was recorded, the cursor
                    # never moved, the window is re-pulled. Removing it is the whole recovery.
                    with suppress(OSError):
                        f.unlink()
                    swept.append(f.name)
                    continue
                if not _SEG_RE.match(f.name):
                    continue
                if f.name in by_name:
                    continue
                rec = segment_record_from_file(f)
                if rec is None:
                    corrupt.append(f.name)
                    continue
                _append_line(self.manifest_path(symbol, day),
                             json.dumps(asdict(rec), separators=(",", ":")))
                orphans.append(f.name)
        for r in rows:
            p = d / r.filename
            if not p.exists():
                missing.append(r.filename)
                continue
            try:
                if hashlib.sha256(p.read_bytes()).hexdigest() != r.sha256:
                    corrupt.append(r.filename)
            except OSError:
                corrupt.append(r.filename)
        return {"orphans_recovered": orphans, "missing": missing, "corrupt": corrupt,
                "temp_swept": swept}

    def sweep_temp(self) -> int:
        """Remove every leftover `.tmp-*` under the tape. Run at startup: each one is a write
        that was interrupted, and each one is harmless precisely because it never got a name."""
        n = 0
        for base in (self.ticks_dir, self.gaps_dir, self.state_dir, self.clock_dir):
            if not base.is_dir():
                continue
            for f in base.rglob(f"{_TMP_PREFIX}*"):
                with suppress(OSError):
                    f.unlink()
                    n += 1
        return n

    # ------------------------------------------------------------------- read --
    def read_day(self, symbol: str, day: str, *, verify: bool = False) -> pd.DataFrame:
        """One symbol-day, every segment merged, sorted, and DEDUPED ON READ.

        Deduping on read rather than on write is the deliberate consequence of the invariant at
        the top of this file: removing a duplicate from a sealed segment would mean rewriting it,
        which is the one operation that can lose data. A duplicate costs a few bytes and is
        measured by the integrity checker; a rewrite can cost a day.
        """
        recs = self.manifest(symbol, day)
        frames: list[pd.DataFrame] = []
        d = self.day_dir(symbol, day)
        for r in recs:
            p = d / r.filename
            if not p.exists():
                continue
            if verify:
                try:
                    if hashlib.sha256(p.read_bytes()).hexdigest() != r.sha256:
                        continue
                except OSError:
                    continue
            with suppress(OSError, ValueError, pa.ArrowInvalid):
                frames.append(decode_segment(p))
        if not frames:
            return pd.DataFrame(columns=["time_msc", "bid", "ask", "last", "volume", "flags",
                                         "symbol"])
        df = pd.concat(frames, ignore_index=True)
        df = df.sort_values("time_msc", kind="mergesort")
        df = df.drop_duplicates(subset=["time_msc", "bid", "ask", "last", "volume", "flags"],
                                keep="first")
        return df.reset_index(drop=True)

    def symbols(self) -> list[str]:
        if not self.ticks_dir.is_dir():
            return []
        return sorted(p.name for p in self.ticks_dir.iterdir() if p.is_dir())

    def days(self, symbol: str) -> list[str]:
        d = self.ticks_dir / _safe(symbol)
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir()
                      if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name))

    def day_bytes(self, symbol: str, day: str) -> int:
        d = self.day_dir(symbol, day)
        if not d.is_dir():
            return 0
        return sum(f.stat().st_size for f in d.iterdir() if f.is_file())

    def minute_mask(self, symbol: str, day: str) -> np.ndarray:
        """Which of the day's 1,440 minutes carried at least one tick, cached per day.

        WHY A CACHE IS THE DIFFERENCE BETWEEN A REPORT AND A REPORT NOBODY RUNS. Building a
        symbol's session model needs the minute coverage of 90 days, and computing it the obvious
        way decodes 90 full days of ticks PER SYMBOL -- 22,590 whole-day parquet decodes per
        integrity pass across the universe, growing with every day recorded, on an hourly job.
        The mask itself is 1,440 bits. It is keyed by the digest of the day's manifest, so a day
        that GREW recomputes and a day that did not is a 200-byte read; a stale cache is
        structurally impossible rather than merely unlikely.

        The cache lives under `state/` and never inside the day directory: the day directory is
        the ASSET and its byte count is the number the retention policy is defended with, so a
        derived file must not inflate it.
        """
        token = self._day_token(symbol, day)
        cache = self.state_dir / "minutes" / _safe(symbol) / f"{day}.json"
        if cache.exists():
            try:
                doc = json.loads(cache.read_text("utf-8"))
                if str(doc.get("token")) == token and isinstance(doc.get("mask"), str):
                    raw = bytes.fromhex(doc["mask"])
                    if len(raw) == 180:
                        return np.unpackbits(np.frombuffer(raw, dtype=np.uint8)).astype(bool)
            except (OSError, ValueError, TypeError):
                pass
        df = self.read_day(symbol, day)
        mask = np.zeros(1440, dtype=bool)
        if not df.empty:
            day_start = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
            minute = (np.asarray(df["time_msc"], dtype=np.int64) - day_start) // 60_000
            minute = minute[(minute >= 0) & (minute < 1440)]
            if minute.size:
                mask[np.unique(minute)] = True
        with suppress(OSError, ValueError):
            _atomic_write_bytes(cache, json.dumps({
                "token": token, "n_ticks": len(df),
                "mask": np.packbits(mask).tobytes().hex(),
            }, separators=(",", ":")).encode("utf-8"))
        return mask

    def _day_token(self, symbol: str, day: str) -> str:
        """A content token for one symbol-day: the digest of its manifest and superseded ledger.

        Both, because a compaction rewrites what the day HOLDS without adding a manifest row that
        a manifest-only digest would notice on its own -- it appends one and retires several, and
        a token blind to the retirement would serve a mask built from double-counted segments.
        """
        h = hashlib.sha256()
        for p in (self.manifest_path(symbol, day), self.superseded_path(symbol, day)):
            with suppress(OSError):
                if p.exists():
                    h.update(p.read_bytes())
            h.update(b"|")
        return h.hexdigest()[:32]

    # -------------------------------------------------------------- compaction --
    def compact_day(self, symbol: str, day: str) -> dict[str, Any]:
        """Fold a day's live segments into one, then remove what it replaced.

        ONLY EVER CALL THIS ON A DAY THAT HAS STOPPED RECEIVING. It is safe to call on a live one
        -- nothing is lost, because the compacted segment is written before anything is deleted
        and a concurrently-written segment is simply not in it -- but it would be pointless work
        that the next cycle undoes.

        Segments are grouped by (point, digits, encoding) and each group is compacted separately.
        A broker re-quote mid-day leaves a symbol with two units in one day, and merging those
        into one segment would have to pick one point and silently re-price half the ticks --
        which is the exact failure `mt5desk/tape.py` warns about, one layer down. Two units means
        two compacted segments and both are right.
        """
        out: dict[str, Any] = {"symbol": symbol, "day": day, "status": "NOTHING_TO_DO",
                               "segments_before": 0, "segments_after": 0, "superseded": 0,
                               "rows_in": 0, "rows_out": 0, "duplicates_removed": 0,
                               "bytes_before": 0, "bytes_after": 0, "groups": 0,
                               "missing_kept": 0, "skipped_unreadable": 0}
        self.reconcile(symbol, day)
        live = self.manifest(symbol, day)
        out["segments_before"] = len(live)
        out["bytes_before"] = self.day_bytes(symbol, day)
        if len(live) < 2:
            return out
        d = self.day_dir(symbol, day)
        groups: dict[tuple[float, int, str], list[SegmentRecord]] = {}
        keep: list[SegmentRecord] = []
        for r in live:
            if (d / r.filename).exists():
                groups.setdefault((float(r.point), int(r.digits), r.encoding), []).append(r)
            else:
                # A ROW WHOSE FILE IS GONE IS KEPT IN THE MANIFEST, DELIBERATELY. The rewrite
                # below replaces the manifest, and dropping this row would erase the only record
                # that a segment was ever lost -- `reconcile` would then report missing=[] and a
                # day with a hole in it would seal clean. A compaction may reorganise containers;
                # it may never launder a loss into a tidy manifest.
                keep.append(r)
                out["missing_kept"] = out.get("missing_kept", 0) + 1

        changed = False
        for (point, digits, _enc), recs in sorted(groups.items()):
            if len(recs) < 2:
                keep.extend(recs)
                continue
            frames = []
            for r in recs:
                with suppress(OSError, ValueError, pa.ArrowInvalid):
                    frames.append(decode_segment(d / r.filename))
            if len(frames) != len(recs):
                # ONE UNREADABLE SEGMENT ABORTS THE WHOLE GROUP. Compacting the readable ones and
                # deleting the rest would destroy the only copy of ticks that might still be
                # recoverable -- a corrupt read can be transient, a bad sector can be partially
                # salvageable, and either way the decision belongs to a person looking at an
                # integrity report, not to a housekeeping pass optimising disk. The day stays
                # uncompacted and `reconcile` goes on reporting the segment as corrupt.
                keep.extend(recs)
                out["skipped_unreadable"] = out.get("skipped_unreadable", 0) + (
                    len(recs) - len(frames))
                continue
            rows_in = sum(len(f) for f in frames)
            df = pd.concat(frames, ignore_index=True).sort_values("time_msc", kind="mergesort")
            df = df.drop_duplicates(subset=["time_msc", "bid", "ask", "last", "volume", "flags"],
                                    keep="first")
            arr = _ticks_from_frame(df)
            if arr.size == 0:
                keep.extend(recs)
                continue
            payload, rec = encode_segment(arr, symbol, day, point, digits,
                                          cycle_id=f"compaction:{len(recs)}", compacted=True)
            # THE COMPACTED SEGMENT MAY ALREADY BE ONE OF ITS OWN SOURCES, when an interrupted
            # compaction re-runs: identical ticks give identical bytes and therefore an identical
            # digest. Retiring it would retire the only file holding the day. It is excluded from
            # its own victim list, and a group with no other victim is already compacted.
            victims = [r for r in recs if r.sha256 != rec.sha256]
            if not victims:
                keep.append(rec)
                continue

            # THE ORDER BELOW IS THE SAFETY AND EVERY STEP IS A CRASH POINT ON PURPOSE.
            #   after 1: an orphan segment -> re-registered by reconcile; the day reads as the
            #            compacted segment PLUS its sources, which is duplicates, never a hole
            #   after 2: the manifest names both -> duplicates on read, removed on read
            #   after 3: audit row written; the day still reads correctly either way
            #   after 4: the manifest names only what is live; victims are now orphans on disk
            #   after 5: done
            # The one order that would be fatal is writing the supersede/prune BEFORE the
            # compacted segment reaches the manifest -- that window reads as an EMPTY day while
            # every byte is intact on disk, which is the worst outcome available here.
            _atomic_write_bytes(d / rec.filename, payload)                            # 1
            if rec.sha256 not in {r.sha256 for r in self.manifest(symbol, day)}:
                _append_line(self.manifest_path(symbol, day),                          # 2
                             json.dumps(asdict(rec), separators=(",", ":")))
            _append_line(self.superseded_path(symbol, day), json.dumps({               # 3
                "compacted_into": rec.sha256, "folded": len(victims),
                "rows_in": int(rows_in), "rows_out": rec.rows,
                "duplicates_removed": int(max(0, rows_in - rec.rows)),
                "bytes": rec.bytes, "point": point, "digits": digits,
                "manifest_sha256": self.manifest_digest(symbol, day),
                "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            }, separators=(",", ":")))
            keep.append(rec)
            changed = True
            out["superseded"] += len(victims)
            out["rows_in"] += int(rows_in)
            out["rows_out"] += rec.rows
            out["duplicates_removed"] += int(max(0, rows_in - rec.rows))
            out["groups"] += 1
            out["_victims"] = [*out.get("_victims", []), *(r.filename for r in victims)]

        if changed:
            _atomic_write_bytes(self.manifest_path(symbol, day), "".join(                # 4
                json.dumps(asdict(r), separators=(",", ":")) + "\n" for r in keep
            ).encode("utf-8"))
            for name in out.pop("_victims", []):
                with suppress(OSError):
                    (d / name).unlink()                                                  # 5
            _fsync_dir(d)
        out.pop("_victims", None)
        out["segments_after"] = len(self.manifest(symbol, day))
        out["bytes_after"] = self.day_bytes(symbol, day)
        out["status"] = "COMPACTED" if changed else "NOTHING_TO_DO"
        return out

    def manifest_digest(self, symbol: str, day: str) -> str:
        """The digest of the manifest exactly as it stands. Carried into the seal and into every
        compaction row, so the chain from a live capture to a compacted day is checkable."""
        p = self.manifest_path(symbol, day)
        try:
            return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
        except OSError:
            return ""

    # ------------------------------------------------------------------- seal --
    def seal_day(self, symbol: str, day: str) -> DaySeal:
        """Declare a day complete. Reconciles first, then records what it holds.

        The seal is a CLAIM ABOUT COMPLETENESS, not a lock. It exists so the integrity checker
        can tell "today, still filling" from "a finished day with a hole in it" -- the same
        missing hour means nothing in the first case and is an alarm in the second.
        """
        rec = self.reconcile(symbol, day)
        rows = self.manifest(symbol, day)
        gaps = self.gaps(symbol, day)
        manifest_bytes = b""
        p = self.manifest_path(symbol, day)
        if p.exists():
            with suppress(OSError):
                manifest_bytes = p.read_bytes()
        seal = DaySeal(
            schema=SCHEMA, symbol=symbol, day=day, segments=len(rows),
            rows=sum(r.rows for r in rows),
            first_ms=min((r.first_ms for r in rows), default=0),
            last_ms=max((r.last_ms for r in rows), default=0),
            bytes=self.day_bytes(symbol, day),
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            sealed_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
            gaps=len([g for g in gaps if g.reason != GAP_RESOLVED]),
            gap_seconds=round(sum(g.seconds for g in gaps if g.reason != GAP_RESOLVED), 3),
            orphans_recovered=len(rec["orphans_recovered"]),
            superseded=sum(int(c.get("folded") or 0)
                           for c in self.compactions(symbol, day)),
            notes=([f"missing segments: {', '.join(rec['missing'][:5])}"] if rec["missing"] else [])
                  + ([f"corrupt segments: {', '.join(rec['corrupt'][:5])}"] if rec["corrupt"]
                     else []),
        )
        _atomic_write_bytes(self.seal_path(symbol, day),
                            (json.dumps(asdict(seal), indent=1) + "\n").encode("utf-8"))
        return seal

    def seal(self, symbol: str, day: str) -> DaySeal | None:
        p = self.seal_path(symbol, day)
        if not p.exists():
            return None
        try:
            return DaySeal(**json.loads(p.read_text("utf-8")))
        except (OSError, ValueError, TypeError):
            return None

    # -------------------------------------------------------------- gap ledger --
    def record_gap(self, gap: GapRecord) -> GapRecord:
        """Append one gap fact. The ledger is append-only; a gap is never edited or removed."""
        if gap.reason not in GAP_REASONS:
            raise ValueError(f"unknown gap reason {gap.reason!r} -- a gap with an unnamed reason "
                             f"is an absence again, which is what this ledger exists to end")
        row = GapRecord(**{**asdict(gap),
                           "detected_at": gap.detected_at
                           or datetime.now(tz=UTC).isoformat(timespec="seconds")})
        # A gap can straddle midnight; it is filed under every day it touches so a per-day
        # integrity check cannot miss the half that fell outside its window.
        for day in _days_spanned(row.from_ms, row.to_ms):
            _append_line(self.gap_path(row.symbol, day),
                         json.dumps(asdict(row), separators=(",", ":")))
        return row

    def resolve_gap(self, gap: GapRecord, recovered_ticks: int, detail: str = "") -> GapRecord:
        """Record that a previously reported window was later filled. APPEND, never edit."""
        return self.record_gap(GapRecord(
            symbol=gap.symbol, from_ms=gap.from_ms, to_ms=gap.to_ms, reason=GAP_RESOLVED,
            detail=detail or f"backfilled a {gap.reason} window", cycle_id=gap.cycle_id,
            recovered_ticks=int(recovered_ticks)))

    def gaps(self, symbol: str, day: str) -> list[GapRecord]:
        path = self.gap_path(symbol, day)
        if not path.exists():
            return []
        out: list[GapRecord] = []
        try:
            lines = path.read_text("utf-8").splitlines()
        except OSError:
            return out
        for line in lines:
            if not line.strip():
                continue
            try:
                out.append(GapRecord(**json.loads(line)))
            except (ValueError, TypeError):
                continue
        return out

    def open_gaps(self, symbol: str, day: str) -> list[GapRecord]:
        """Gaps with no RESOLVED row against the same window. What is still MISSING."""
        rows = self.gaps(symbol, day)
        resolved = {(g.from_ms, g.to_ms) for g in rows if g.reason == GAP_RESOLVED}
        return [g for g in rows if g.reason != GAP_RESOLVED
                and (g.from_ms, g.to_ms) not in resolved]

    # ------------------------------------------------------------------ state --
    def read_state(self, name: str, default: Any = None) -> Any:
        p = self.state_dir / f"{name}.json"
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text("utf-8"))
        except (OSError, ValueError):
            return default

    def write_state(self, name: str, payload: Any) -> None:
        _atomic_write_bytes(self.state_dir / f"{name}.json",
                            (json.dumps(payload, indent=1, sort_keys=True) + "\n").encode("utf-8"))

    def record_clock(self, local_ms: int, server_ms: int, symbol: str) -> None:
        """The broker-clock offset, dated. Unbuyable after the fact and two lines to keep.

        Without this, a tape recorded across a server DST change cannot be aligned to a
        UTC-stamped macro calendar, and every event study built on it is quietly out by an hour.
        """
        day = broker_day(local_ms)
        _append_line(self.clock_dir / f"{day}.jsonl", json.dumps({
            "at": datetime.fromtimestamp(local_ms / 1000.0, tz=UTC).isoformat(timespec="seconds"),
            "symbol": symbol, "local_ms": int(local_ms), "server_ms": int(server_ms),
            "skew_ms": int(server_ms - local_ms),
        }, separators=(",", ":")))

    def free_bytes(self) -> int | None:
        """Free space at the tape root, or at the nearest existing ancestor.

        WALKING UP MATTERS ON THE FIRST CYCLE. `disk_usage` on a directory that does not exist
        yet raises, and returning None there means the disk-floor guard is DISABLED for exactly
        the run where the tape root is being created -- which on a fresh box is the run most
        likely to be pointed at the wrong, nearly-full volume.
        """
        p = self.root
        for _ in range(8):
            try:
                return int(shutil.disk_usage(p).free)
            except (OSError, ValueError):
                if p.parent == p:
                    return None
                p = p.parent
        return None


def _safe(symbol: str) -> str:
    """A filesystem-safe directory name for a broker symbol.

    Broker symbols carry '&' (AT&T), '.', '-' and '/' -- and on Windows several of those are
    legal while others are not. Sanitising is not optional: a symbol that cannot become a
    directory is a symbol that silently never gets recorded, which is the failure class this
    whole package exists to end. The mapping is one-way and lossy by design, so the original is
    always carried INSIDE the segment metadata, never inferred from the path.
    """
    return re.sub(r"[^A-Za-z0-9_.+=-]", "_", str(symbol)) or "_"


def _days_spanned(from_ms: int, to_ms: int) -> list[str]:
    """Every broker-day an interval touches, so a straddling gap is filed under both."""
    if to_ms <= from_ms:
        return [broker_day(from_ms)]
    d0 = datetime.fromtimestamp(from_ms / 1000.0, tz=UTC).date()
    d1 = datetime.fromtimestamp((to_ms - 1) / 1000.0, tz=UTC).date()
    out: list[str] = []
    cur: date = d0
    # Bounded: a gap longer than a year is filed at its ends rather than exploding the ledger.
    while cur <= d1 and len(out) < 400:
        out.append(cur.isoformat())
        cur = cur + timedelta(days=1)
    if cur <= d1:
        out.append(d1.isoformat())
    return out


def split_by_day(ticks: np.ndarray) -> Iterator[tuple[str, np.ndarray]]:
    """Ticks grouped into broker-days, in order. A pull that straddles midnight writes two
    segments rather than one file that belongs to neither day."""
    if ticks.size == 0:
        return
    tms = np.asarray(ticks["time_msc"], dtype=np.int64)
    order = np.argsort(tms, kind="mergesort")
    ticks = ticks[order]
    tms = tms[order]
    days = np.array([broker_day(int(t)) for t in tms])
    for day in pd.unique(days):
        yield str(day), ticks[days == day]


def _ticks_from_frame(df: pd.DataFrame) -> np.ndarray:
    """A decoded frame back into the capture dtype, so compaction can re-encode it.

    The round trip is exact for an int-points segment -- decoding is `pts * point` and encoding is
    `rint(price / point)`, which recovers the same integer -- and `encode_segment` verifies it
    again anyway rather than trusting this comment. `time` and `volume_real` are DERIVED here
    rather than carried: neither is stored (see TICK_COLUMNS), and a compaction that invented
    values for them would be writing numbers the broker never sent.
    """
    from recorders.tick_source import TICK_DTYPE
    n = len(df)
    out = np.empty(n, dtype=TICK_DTYPE)
    tms = np.asarray(df["time_msc"], dtype=np.int64)
    out["time_msc"] = tms
    out["time"] = tms // 1000
    out["bid"] = np.asarray(df["bid"], dtype=np.float64)
    out["ask"] = np.asarray(df["ask"], dtype=np.float64)
    out["last"] = np.asarray(df["last"], dtype=np.float64)
    out["volume"] = np.asarray(df["volume"], dtype=np.int64).astype(np.uint64)
    out["flags"] = np.asarray(df["flags"], dtype=np.int64).astype(np.uint32)
    out["volume_real"] = 0.0
    return out


def dedupe(ticks: np.ndarray) -> np.ndarray:
    """Exact duplicates removed, order preserved. Applied before a write so an overlapped pull
    does not store the same tick twice; the read path deduplicates again across segments."""
    if ticks.size == 0:
        return ticks
    keys = np.stack([np.asarray(ticks[c], dtype=np.float64)
                     for c in ("time_msc", "bid", "ask", "last", "volume", "flags")], axis=1)
    _, idx = np.unique(keys, axis=0, return_index=True)
    return ticks[np.sort(idx)]


def total_bytes(store: TapeStore, symbols: Iterable[str] | None = None) -> dict[str, int]:
    """Measured bytes per symbol across every day it holds. The retention policy is defended
    with THIS number, never with an estimate."""
    out: dict[str, int] = {}
    for sym in (list(symbols) if symbols is not None else store.symbols()):
        out[sym] = sum(store.day_bytes(sym, d) for d in store.days(sym))
    return out
