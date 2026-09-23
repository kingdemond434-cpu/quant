#!/usr/bin/env python3
"""CLOCK PROVENANCE FENCE (L1.46) -- does the tape's time axis mean what its schema implies?

WHICH CORPUS. BOTH, and that is the 2026-09-23 repoint. This fence was written against the crypto
venue tape under `data/moat/<venue>/<SYMBOL>/*.jsonl.gz`, and the MT5 universe mandate
(2026-08-18) retired every one of those recorders permanently -- `data/RECORDERS_OFF` has been set
since 2026-08-25 and `data/moat/` now holds the world crawler's intel corpus (raw_intel /
normalized_intel / sources) and not one tape row. So the fence read zero files, reported NO-DATA,
and its `next_action` told every reader to "start the recorders" that the principal had
deliberately stopped: a PERMANENT RED that was in fact correct behaviour, which is the shape of
alarm that gets a gate switched off.

L1.46 did not retire; the recorders did. The desk records a tape every minute -- the Fusion tick
tape at `desks/mt5/data/tape/ticks/<SYMBOL>/<DAY>.parquet`, 249 symbol directories and ~11.7k day
files measured 2026-09-23 -- and it has exactly the property this law is about. The moat scan is
KEPT (a corpus that comes back is checked again the hour it does); the MT5 tape is now scanned
beside it, under the same ladder, with the same statuses and no threshold moved.

WHY THIS FENCE EXISTS. Every other data fence on this desk asks whether the COLLECTOR RAN. Gapless
collection was verified GOOD in the data-moat sweep on the same corpus that, measured here, is not
monotonic in its own `t` field. Nothing asked whether the TIMESTAMPS MEAN WHAT THE SCHEMA IMPLIES,
so a file could interleave two clocks under one field name and every liveness metric would read
green -- which is exactly what 7.5 GB of it does.

The cost is on the record three times over. kimchi_premium, the desk's flagship, was retracted as a
~73% timestamp artifact; coinbase_premium_timing was graveyarded as "close-timestamp
microstructure"; R0060 found leaky Upbit look-ahead copies surviving their own retraction. Three of
the most prominent kills in the graveyard are ONE defect class, and the institutional response was
a prose duty with no instrument ("DECLARE TIMESTAMP ALIGNMENT for every cross-source series ...
unstated alignment voids the screen"). This is the instrument.

WHAT IT MEASURES, and the second one is why the fence is not only about clocks: both are claims the
schema makes about the time axis that nobody was checking.
  WHICH CLOCK -- does each row declare the clock that stamped it, and do we retain the venue's own
      stamp wherever the venue offers one? Delta = t_recv - t_venue is structurally unbuyable (a
      vendor sells the venue's stamp or THEIR receipt, never when a message reached OURS) and it
      cannot be backfilled, so a day not recorded is a Delta day gone permanently.
  HOW OFTEN -- is the CONFIGURED poll period the one actually achieved? Measured 2026-08-01: the
      futures depth stream runs at 8.2s against _DEPTH_EVERY_S = 5.0, with p05 at 7.8s and nothing
      near 5.0 -- the loop cannot finish inside its own period, so the constant is a fiction that
      every consumer reading it instead of measuring inherits as truth.

FENCE STATUS (exit 2 on the first five -- a gate, not a report):
  NO-DATA       the corpus is absent or unreadable; there is no tape to check.
  UNMEASURED    files exist but no row could be classified -- never read as fine (L1.28a).
  MIXED-CLOCK   a stream carries rows on two different clocks with no marker declaring which, or
                one symbol's tape directory holds files from two WRITERS with nothing saying which
                wrote which. Worst status because a reader sorting the raw time axis silently
                REORDERS events, and that is the mechanism behind every timestamp artifact in the
                graveyard.
  RECV-ONLY     the stream keeps only ONE of the two clocks, so Delta is unrecoverable for every
                row written this way. Stated in the general form because the desk has now seen it
                in both directions: the venue tape dropped the VENUE's stamp and kept ours
                (Binance fut/d), the MT5 tape drops OUR receipt and keeps the broker's
                (mt5desk_tape, mt5desk_features). Same law, same permanent loss -- Delta cannot be
                backfilled from either side. Streams where the venue genuinely offers nothing
                (Binance spot /api/v3/depth) are EXEMPT: a venue limitation must never read as a
                desk defect, or the fence cries wolf and gets switched off.
  PERIOD-DRIFT  the achieved sampling period exceeds its configured constant by >1.5x.
  OK            every live stream declares its clock, Delta is measurable wherever the venue
                offers a stamp, and the achieved cadence matches the configured one.

THE ONE THING THIS FENCE MAY NEVER DO is report OK because it found nothing to look at. An absent
corpus, an unparseable file and a stream nobody has classified are all LOUDER than a healthy desk.

    python scripts/check_clock_provenance.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# L1.42 LAWFUL ENTRY: TTL-cached, pages but does not block -- a governance fault must never
# silence the only instrument that reports on the desk's largest dataset.
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research import clock_provenance as cp  # noqa: E402

#: Symbols sampled per venue, newest file each. The question is "is the tape being written
#: correctly RIGHT NOW", not "was it ever" -- every hour written wrong is an unrecoverable Delta
#: hour, so the fence must scream about today rather than average it into eight days of history.
_SAMPLE_SYMBOLS = 4
#: Rows read per sampled file. Read from the FRONT: gzip streams, so this stops early instead of
#: decompressing 7.5 GB on an hourly cron.
_SAMPLE_ROWS = 4000
#: Achieved period over configured before the constant counts as fiction rather than jitter.
#: Discriminating at 2026-08-01 values: futures 8.2/5.0 = 1.64x fires, Bybit 4.2/4.0 = 1.05x does
#: not. A gate that fires on everything or nothing carries zero information (GATE-OPTIMALITY).
_PERIOD_TOLERANCE = 1.5

#: Symbol directories sampled from the MT5 tick tape. Reading every file's parquet footer across
#: the whole tape costs 45.7s MEASURED on the trading box -- on an hourly fence, on the box that
#: holds the live terminal, that is a cost the recorder should not have to share. Twelve
#: directories is ~2s and is a COMPLETE census within each one (see `_mt5_scan`).
_MT5_SAMPLE_SYMBOLS = 12
#: Hard cap on footers read per sampled directory, so a symbol with years of tape cannot make this
#: fence the slowest thing on the box.
_MT5_MAX_FILES_PER_SYMBOL = 400
#: Day files ROW-sampled per (symbol, writer). The schema census above answers "which writers",
#: which is the finding; rows are only needed for Delta and cadence, and one file gives both.
_MT5_ROW_FILES_PER_WRITER = 1

#: Delta readings outside this bound are a clock that is not merely skewed but wrong, and are
#: dropped from the percentile summary rather than dragging it. The same bound latency_lab uses.
_MT5_DELTA_SANE_MS = 3_600_000


def _sample_files(venue_dir: Path) -> list[Path]:
    """Newest file for each of the first _SAMPLE_SYMBOLS symbols that has one."""
    out: list[Path] = []
    for sym_dir in sorted(p for p in venue_dir.iterdir() if p.is_dir()):
        files = sorted(sym_dir.glob("*.jsonl.gz"))
        if files:
            out.append(files[-1])
        if len(out) >= _SAMPLE_SYMBOLS:
            break
    return out


def _read_rows(path: Path) -> list[dict[str, Any]]:
    """Rows from the front of a tape file. An unreadable file yields nothing and is COUNTED by the
    caller as unreadable -- never silently treated as an empty-but-healthy file."""
    rows: list[dict[str, Any]] = []
    try:
        with gzip.open(path, "rt") as fh:
            for line in fh:
                if len(rows) >= _SAMPLE_ROWS:
                    break
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except (OSError, EOFError, gzip.BadGzipFile):
        return []
    return rows


def _period_s(rows: list[dict[str, Any]], venue: str, kind: str) -> float | None:
    """Median achieved interval between consecutive rows of one kind, in seconds."""
    stamps = sorted(s for s in (cp.recv_ms(r, venue) or r.get("t")
                                for r in rows if r.get("k") == kind)
                    if isinstance(s, int))
    gaps = [(b - a) / 1000.0 for a, b in itertools.pairwise(stamps) if 0 < b - a < 600_000]
    return statistics.median(gaps) if len(gaps) >= 10 else None


def _mt5_sample(ticks_dir: Path) -> list[tuple[str, list[Path]]]:
    """(symbol, every day file it holds) for a spread sample of symbol directories.

    STRIDED, NOT THE FIRST N. The first twelve directories alphabetically are all equity CFDs
    (3M, ADAUSD, ADP, Accenture, ...) and the symbol the desk actually trades -- XAUUSD -- sits
    near the end, so a head sample would never once look at the tape the live book is priced on.
    An even stride over the sorted list is deterministic, stable run to run, and covers the
    alphabet.

    EVERY FILE IN THE SAMPLED DIRECTORY, not the newest few. Which writers a directory holds IS
    the finding, and it is answerable only by a complete census: the writers interleave by DATE,
    not by recency, so a newest-N sample reported `mt5desk_features+mt5desk_tape` on the trading
    box while 245 directories also held recorder files -- a sampler that cannot see a writer
    reports a corpus cleaner than it is. Footers are ~4ms each, capped per directory.
    """
    out: list[tuple[str, list[Path]]] = []
    dirs = sorted(p for p in ticks_dir.iterdir() if p.is_dir())
    if not dirs:
        return out
    stride = max(1, len(dirs) // _MT5_SAMPLE_SYMBOLS)
    for sym_dir in dirs[::stride]:
        files = sorted(sym_dir.glob("*.parquet"))[:_MT5_MAX_FILES_PER_SYMBOL]
        if files:
            out.append((sym_dir.name, files))
        if len(out) >= _MT5_SAMPLE_SYMBOLS:
            break
    return out


def _mt5_scan(root: Path, streams: dict[str, dict[str, Any]], deltas: dict[str, list[int]],
              period_samples: dict[str, tuple[float, list[float]]],
              mixed: list[str], mixed_dirs: list[str]) -> tuple[int, int, int, bool]:
    """Sample the MT5 tick tape into the shared stream/delta/period accumulators.

    Returns (files_read, files_unreadable, rows_sampled, corpus_present). A file this run could
    not open is COUNTED as unreadable and never as an empty-but-healthy file -- including the case
    where pyarrow itself is missing, which would otherwise let "we could not read the corpus" exit
    down the same path as "the corpus is clean" (L1.28a).
    """
    ticks = root / cp.MT5_TICKS_REL
    if not ticks.is_dir():
        return 0, 0, 0, False
    sample = _mt5_sample(ticks)
    if not sample:
        return 0, 0, 0, True
    try:
        import pandas as pd
        import pyarrow.parquet as pq
    except ImportError:
        return 0, sum(len(fs) for _s, fs in sample), 0, True

    files_read = unreadable = rows_seen = 0
    for symbol, paths in sample:
        # ---- the CENSUS: which writers does this directory hold, and how many rows each --------
        by_writer: dict[str, list[tuple[Path, list[str], int]]] = {}
        for path in paths:
            try:
                meta = pq.read_metadata(path)  # type: ignore[no-untyped-call]
                names = list(meta.schema.names)
                n_rows = int(meta.num_rows)
            except (OSError, ValueError, pa_error()):
                unreadable += 1
                continue
            files_read += 1
            rows_seen += n_rows
            writer, clocks = cp.mt5_writer_of(names)
            by_writer.setdefault(writer, []).append((path, names, n_rows))
            key = f"mt5_ticks/{writer}"
            st = streams.setdefault(key, {
                "venue": "mt5_ticks", "kind": writer, "corpus": "mt5_ticks", "rows": 0,
                "marked": 0, "clocks": set(), "venue_stamped": 0, "delta_measurable": 0,
                "symbols": set()})
            # ROW COUNTS COME FROM THE FOOTER, not from the sampled batch. A file with no clock
            # column at all still has rows a reader will consume, and counting it as zero would
            # let the shape that lost BOTH clocks vanish from the denominator it is the defect in.
            st["rows"] += n_rows
            # THE COLUMN NAME IS THE MARKER on a columnar tape, so a row is "marked" exactly when
            # this module has been taught which writer produces that column set. An untaught shape
            # marks nothing, which is what drives it onto `unknown_streams` below.
            st["marked"] += n_rows if writer != "unknown" else 0
            st["clocks"].update(clocks)
            st["symbols"].add(symbol)

        # ---- the ROW SAMPLE: Delta and achieved cadence, one file per (symbol, writer) ---------
        for writer, entries in by_writer.items():
            key = f"mt5_ticks/{writer}"
            st = streams[key]
            for path, names, _n in entries[-_MT5_ROW_FILES_PER_WRITER:]:
                cols = [c for c in (cp.MT5_VENUE_COL, cp.MT5_RECV_COL) if c in names]
                if not cols:
                    continue
                try:
                    pf = pq.ParquetFile(path)  # type: ignore[no-untyped-call]
                    batch = next(pf.iter_batches(  # type: ignore[no-untyped-call]
                        batch_size=_SAMPLE_ROWS, columns=cols))
                    frame = batch.to_pandas()
                except (StopIteration, OSError, ValueError, pa_error()):
                    unreadable += 1
                    continue
                if cp.MT5_VENUE_COL in frame.columns:
                    st["venue_stamped"] += int(frame[cp.MT5_VENUE_COL].notna().sum())
                if not {cp.MT5_VENUE_COL, cp.MT5_RECV_COL} <= set(frame.columns):
                    continue
                recv = pd.to_datetime(frame[cp.MT5_RECV_COL], utc=True, errors="coerce")
                venue = pd.to_numeric(frame[cp.MT5_VENUE_COL], errors="coerce")
                ok = recv.notna() & venue.notna()
                if not bool(ok.any()):
                    continue
                recv_ms = recv[ok].astype("int64") // 10**6
                d = recv_ms - venue[ok].astype("int64")
                # NEGATIVES ARE KEPT AND COUNTED (latency_lab does the same). Dropping them would
                # turn a broker-clock offset into a flattering one-sided receipt delay made
                # entirely of the positive tail -- the denominator trick, wearing a timestamp.
                vals = [int(v) for v in d.to_numpy()
                        if -_MT5_DELTA_SANE_MS < int(v) < _MT5_DELTA_SANE_MS]
                st["delta_measurable"] += len(vals)
                deltas.setdefault("mt5_ticks", []).extend(vals)
                # ACHIEVED CADENCE is the gap between DISTINCT receipt stamps: one
                # `copy_ticks_range` call stamps every row it returned with one instant, so the
                # distinct stamps ARE the poll cycles and the row count is not the cadence.
                cfg = cp.MT5_CONFIGURED_CYCLE_S.get(writer)
                stamps = sorted({int(v) for v in recv_ms.to_numpy()})
                gaps = [(b - a) / 1000.0 for a, b in itertools.pairwise(stamps)
                        if 0 < b - a < 600_000]
                if cfg and len(gaps) >= 10:
                    period_samples.setdefault(key, (cfg, []))[1].append(statistics.median(gaps))

        if len(by_writer) > 1:
            # TWO WRITERS, ONE DIRECTORY, NOTHING SAYING WHICH WROTE WHICH DAY. A reader globbing
            # `ticks/<SYM>/*.parquet` gets both time axes; `moat_series.tape_index` resolves the
            # collision by keeping the LARGER file, which silently drops the other writer's rows,
            # and `latency_lab.tape_receipt_pairs` already reports its stage UNMEASURED because
            # "the two writers disagree". This is the MIXED-CLOCK defect one level up from the row.
            #
            # THE DIRECTORY FINDING GOES IN ITS OWN LIST and only the STREAM KEYS go in `mixed`.
            # `capability_ratchet._recorder_tape` scores this fence as
            # `len(streams) - len(mixed_clock_streams)`, so a per-symbol row in `mixed` makes that
            # numerator go NEGATIVE once more directories are sampled than streams exist -- a
            # fence breaking a scorer it never declared it was feeding.
            mixed_dirs.append(f"mt5_ticks/{symbol} ({'+'.join(sorted(by_writer))} in one "
                              f"directory, nothing declares which wrote which day)")
            for writer in by_writer:
                key = f"mt5_ticks/{writer}"
                if key not in mixed:
                    mixed.append(key)
    return files_read, unreadable, rows_seen, True


def pa_error() -> type[BaseException]:
    """pyarrow's own read error, or a type that can never be raised when pyarrow is absent.

    Naming it once keeps the `except` clauses above honest: catching bare Exception around a
    parquet read would swallow a bug in this fence as readily as a corrupt file.
    """
    try:
        import pyarrow as pa
    except ImportError:
        class _Never(BaseException):
            pass
        return _Never
    err: type[BaseException] = pa.ArrowInvalid
    return err


def build_report(root: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Pure: sample the tape, classify every stream, return the verdict. No writes -- tests call
    this directly, and a fence that could only be exercised through its side effects would be
    tested through its least interesting surface."""
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    moat = root / "data/moat"

    streams: dict[str, dict[str, Any]] = {}
    deltas: dict[str, list[int]] = {}
    # One achieved period per sampled file, collapsed to a median per stream below. Reporting a
    # row per file would put the same finding on screen four times and bury the streams that are
    # healthy -- a fence nobody reads to the end is a fence that catches nothing.
    period_samples: dict[str, tuple[float, list[float]]] = {}
    files_read = unreadable = rows_seen = 0
    #: STREAM KEYS only -- `capability_ratchet` scores `len(streams) - len(mixed_clock_streams)`.
    mixed: list[str] = []
    #: The symbol directories that hold more than one writer, which is where the MT5 form of this
    #: defect actually lives. Reported in full; never mixed into the line above.
    mixed_dirs: list[str] = []

    venue_dirs = sorted(p for p in moat.iterdir() if p.is_dir()) if moat.is_dir() else []
    for venue_dir in venue_dirs:
        venue = venue_dir.name
        for path in _sample_files(venue_dir):
            rows = _read_rows(path)
            if not rows:
                unreadable += 1
                continue
            files_read += 1
            rows_seen += len(rows)
            kinds = {r.get("k") for r in rows if isinstance(r.get("k"), str)}
            for kind in sorted(k for k in kinds if k):
                sub = [r for r in rows if r.get("k") == kind]
                key = f"{venue}/{kind}"
                st = streams.setdefault(key, {
                    "venue": venue, "kind": kind, "rows": 0, "marked": 0,
                    "clocks": set(), "venue_stamped": 0, "delta_measurable": 0})
                st["rows"] += len(sub)
                st["marked"] += sum(1 for r in sub if isinstance(r.get(cp.MARKER), str))
                for r in sub:
                    st["clocks"].add(cp.clock_of(r, venue))
                    if cp.venue_ms(r, venue) is not None:
                        st["venue_stamped"] += 1
                    d = cp.delta_ms(r, venue)
                    if d is not None:
                        st["delta_measurable"] += 1
                        deltas.setdefault(venue, []).append(d)
                cfg = cp.CONFIGURED_PERIOD_S.get((venue, kind))
                measured = _period_s(sub, venue, kind) if cfg else None
                if cfg and measured:
                    period_samples.setdefault(key, (cfg, []))[1].append(measured)

    # THE CORPUS THIS DESK ACTUALLY RECORDS TODAY. Scanned beside the venue tape, never instead
    # of it: a corpus that comes back is checked again the hour it does.
    mt5_read, mt5_unreadable, mt5_rows, mt5_present = _mt5_scan(
        root, streams, deltas, period_samples, mixed, mixed_dirs)
    files_read += mt5_read
    unreadable += mt5_unreadable
    rows_seen += mt5_rows

    # ---- classify each stream -------------------------------------------------------------
    recv_only_defect: list[str] = []
    unknown_streams: list[str] = []
    for key, st in sorted(streams.items()):
        clocks = st.pop("clocks")
        st["clocks"] = sorted(clocks)
        if isinstance(st.get("symbols"), set):
            st["symbols"] = sorted(st["symbols"])[:8]
        real = {c for c in clocks if c != cp.CLOCK_UNKNOWN}
        st["fully_marked"] = st["marked"] == st["rows"]
        if cp.CLOCK_UNKNOWN in clocks:
            # Classify NOTHING about a stream whose clock we cannot name. Every finding below is
            # derived from knowing which clock stamped the row, so deriving one here would be
            # asserting a content verdict on an assumption -- the exact move this fence exists to
            # stop. It goes on unknown_streams and the ladder reports UNMEASURED.
            unknown_streams.append(key)
            continue
        # A file may legitimately multiplex clocks -- the defect is multiplexing them UNDECLARED.
        if len(real) > 1 and not st["fully_marked"]:
            mixed.append(key)
        if st.get("corpus") == "mt5_ticks":
            # THE SAME QUESTION, ASKED OF A COLUMNAR TAPE. Delta needs BOTH clocks on the row, and
            # on this tape that is a SCHEMA fact -- which columns the writer emits -- not a data
            # accident, so it is read off the declared clocks rather than off `delta_measurable`.
            # A stream whose sampled deltas all fell outside the sanity bound is a different
            # (louder) problem and must not be laundered into this one, and a stream whose sample
            # happened to be small must not clear it.
            st["venue_limit_exempt"] = False
            if not {cp.CLOCK_VENUE, cp.CLOCK_RECV} <= real:
                recv_only_defect.append(key)
            continue
        exempt = (st["venue"], st["kind"]) in cp.RECV_ONLY_STREAMS
        st["venue_limit_exempt"] = exempt
        if not exempt and st["venue_stamped"] == 0 and cp.CLOCK_VENUE not in real:
            recv_only_defect.append(key)

    # Two streams written by the SAME recorder into the same file on different clocks are the
    # ambiguity even when each stream is internally consistent, so long as neither declares it.
    by_venue: dict[str, set[str]] = {}
    for st in streams.values():
        if not st["fully_marked"]:
            by_venue.setdefault(st["venue"], set()).update(
                c for c in st["clocks"] if c != cp.CLOCK_UNKNOWN)
    for venue, clocks in sorted(by_venue.items()):
        if len(clocks) > 1 and venue not in {k.split("/")[0] for k in mixed}:
            mixed.append(f"{venue}/* ({'+'.join(sorted(clocks))} undeclared in one file)")

    periods: list[dict[str, Any]] = [
        {"stream": key, "configured_s": cfg, "n_files": len(xs),
         "measured_s": round(statistics.median(xs), 2),
         "ratio": round(statistics.median(xs) / cfg, 2)}
        for key, (cfg, xs) in sorted(period_samples.items())]
    drift = [p for p in periods if float(p["ratio"]) > _PERIOD_TOLERANCE]

    delta_stats = {}
    for venue, xs in sorted(deltas.items()):
        xs.sort()
        delta_stats[venue] = {
            "n": len(xs), "p50_ms": xs[len(xs) // 2],
            "p95_ms": xs[int(len(xs) * 0.95)], "max_ms": xs[-1],
            "negative_share": round(sum(1 for x in xs if x < 0) / len(xs), 4)}

    # ---- STATUS -- worst first, and every empty-input case ranks ABOVE OK (L1.28a) ---------
    roots = f"{moat} or {root / cp.MT5_TICKS_REL}"
    if (not venue_dirs and not mt5_present) or (files_read == 0 and unreadable == 0):
        status = "NO-DATA"
        detail = f"no tape under {roots} -- there is no corpus to check"
    elif files_read == 0:
        status = "NO-DATA"
        detail = f"all {unreadable} sampled files were unreadable -- the corpus cannot be parsed"
    elif not streams or rows_seen == 0:
        status = "UNMEASURED"
        detail = f"{files_read} files read but no row carried a usable kind -- nothing classified"
    elif unknown_streams:
        # An unclassified stream must never fall through to a CONTENT verdict. Before this branch
        # existed a brand-new venue reported RECV-ONLY -- a confident claim about a stream whose
        # clock we cannot name -- because `unknown_streams` was computed, reported, and never
        # consulted. Not knowing which clock stamped a row is an UNMEASURED time axis, and under
        # L1.28a that outranks any finding derived from assuming one.
        status = "UNMEASURED"
        detail = (f"{len(unknown_streams)} stream(s) nobody has classified: "
                  f"{', '.join(unknown_streams[:4])} -- teach them to "
                  f"clock_provenance._HISTORICAL before any verdict on them means anything")
    elif mixed:
        status = "MIXED-CLOCK"
        detail = (f"{len(mixed)} stream(s) mix clocks with no marker: {', '.join(mixed[:4])}"
                  f" -- a reader sorting the raw time axis reorders events silently"
                  + (f"; {len(mixed_dirs)} symbol director(ies) hold more than one writer, e.g. "
                     f"{'; '.join(mixed_dirs[:2])}" if mixed_dirs else ""))
    elif recv_only_defect:
        status = "RECV-ONLY"
        detail = (f"{len(recv_only_defect)} stream(s) keep only ONE of the two clocks: "
                  f"{', '.join(recv_only_defect[:4])} -- Delta unrecoverable for every such row")
    elif drift:
        worst = max(drift, key=lambda p: float(p["ratio"]))
        status = "PERIOD-DRIFT"
        detail = (f"{worst['stream']} samples every {worst['measured_s']}s against a configured "
                  f"{worst['configured_s']}s ({worst['ratio']}x) -- the constant is a fiction")
    else:
        status = "OK"
        detail = (f"{len(streams)} streams all declare their clock; Delta measurable on "
                  f"{sum(s['delta_measurable'] for s in streams.values())} sampled rows")

    return {
        "generated": now.isoformat(),
        "law": ("L1.46 -- a timestamp whose clock is undeclared is an assumption wearing a "
                "measurement's clothes; the tape declares which clock stamped it and retains the "
                "venue's own stamp beside ours, making alignment a measured number"),
        "status": status,
        "detail": detail,
        "files_read": files_read,
        "files_unreadable": unreadable,
        "rows_sampled": rows_seen,
        "streams": dict(sorted(streams.items())),
        "mixed_clock_streams": mixed,
        "mixed_writer_directories": mixed_dirs,
        "recv_only_defects": recv_only_defect,
        "unknown_streams": unknown_streams,
        "period_checks": periods,
        "period_drift": drift,
        "delta_ms": delta_stats,
        "next_action": (
            # NOT "start the recorders". That was this fence's next_action until 2026-09-23 and
            # it named the CRYPTO collectors, which the principal stopped permanently under the
            # MT5 universe mandate -- so the desk's only L1.46 instrument spent every hour
            # instructing the next reader to undo a standing order. The only tape writer this
            # desk still runs is the Fusion tick recorder, and that is what to check.
            "No tape under either corpus. desks/mt5/recorders/tick_recorder.py is the only tape "
            "writer this desk still runs (the data/moat venue recorders were retired with the "
            "crypto universe on 2026-08-18) -- check that its task is running and writing "
            "desks/mt5/data/tape/ticks/<SYMBOL>/"
            if status == "NO-DATA" else
            "Teach the sampled streams to libs/research/clock_provenance -- _HISTORICAL for a "
            "venue-tape (venue, kind), _MT5_WRITERS for an MT5 tape column set -- reading the "
            "writer's source for which clock stamps which field"
            if status == "UNMEASURED" else
            # THE REMEDY NAMES ONLY THE CORPUS THAT ACTUALLY FIRED. Leading with "restart the
            # recorders" when every mixed stream is an MT5 one would reintroduce the exact defect
            # this repoint removed: a remedy pointing at collectors the principal permanently
            # stopped, at the top of a red the desk reads every hour.
            (("MT5 tape: make the writer that produced each day file identifiable from the file "
              "itself, so a reader globbing ticks/<SYM>/ cannot interleave two time axes -- today "
              "moat_series.tape_index resolves the collision by keeping the LARGER file, which "
              "silently drops the other writer's rows, and latency_lab.tape_receipt_pairs already "
              "reports its stage UNMEASURED because the two writers disagree. Writers: "
              "desks/mt5/recorders/tick_recorder.py (keeps both clocks) and "
              "desks/mt5/mt5desk/tape.py (keeps the broker's only)."
              if any(k.startswith("mt5_ticks/") for k in mixed) else "")
             + (" Venue tape: restart the recorders so new rows carry the `c` marker; historical "
                "rows stay readable through clock_provenance._HISTORICAL."
                if any(not k.startswith("mt5_ticks/") for k in mixed) else "")).strip()
            if status == "MIXED-CLOCK" else
            "Keep BOTH clocks on the named stream(s) -- the venue's own stamp and our receipt, on "
            "the same row. Every hour written with one of them is a Delta hour that cannot be "
            "backfilled from either side"
            if status == "RECV-ONLY" else
            "Correct the configured period to the achieved one, or make the poll loop concurrent "
            "so it finishes inside its own period (R0275)"
            if status == "PERIOD-DRIFT" else
            "Delta is a first-class series now: join it to the free first-party Bybit archive on "
            "the venue stamp to measure our own information disadvantage per symbol"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report()
    out = _ROOT / "data/clock_provenance_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2) + "\n", "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"clock provenance (L1.46): {rep['status']} -- {rep['detail']}")
        print(f"  files {rep['files_read']} read / {rep['files_unreadable']} unreadable | "
              f"rows {rep['rows_sampled']} | streams {len(rep['streams'])}")
        for key, st in rep["streams"].items():
            flag = "" if st["fully_marked"] else "  <- UNDECLARED"
            print(f"    {key:16s} rows={st['rows']:6d} marked={st['marked']:6d} "
                  f"clocks={'+'.join(st['clocks'])}{flag}")
        for p in rep["period_checks"]:
            print(f"    period {p['stream']:16s} {p['measured_s']}s vs {p['configured_s']}s "
                  f"configured ({p['ratio']}x)")
        for venue, d in rep["delta_ms"].items():
            print(f"    delta {venue:11s} n={d['n']} p50={d['p50_ms']}ms p95={d['p95_ms']}ms "
                  f"neg={d['negative_share']:.1%}")
        print(f"  next: {rep['next_action']}")
    if args.report_only:
        return 0
    # L1.57 (R0417): denominator = market-data files this run actually opened. A collector
    # directory that has moved or emptied yields zero files, zero unmarked streams, and an OK
    # verdict about clock provenance the run never observed.
    return fence_exit(rep["status"], {"OK"}, scanned=rep.get("files_read", 0),
                      of="market-data files read", fence="check_clock_provenance.py")


if __name__ == "__main__":
    sys.exit(main())
