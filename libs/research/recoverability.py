"""RECOVERABILITY AND SPAN HIGH-WATER (L1.65) -- what did the desk LOSE, and can it be bought back.

THE QUESTION NO INSTRUMENT ON THIS DESK ASKS. Every data metric here is computed from what is on
disk RIGHT NOW, so all of them get BETTER when data is destroyed:

  * ``mine_moat.py`` publishes ``cells_filled / cells_total`` where ``cells_total`` counts the
    hours that EXIST. Delete the tape and both collapse together; the ratio is unmoved.
  * ``moat_utilisation.measure_hour_gaps`` measures holes BETWEEN the first and last observed
    hour. A left-truncation moves ``first_hour_utc``, so destroying history reads as PERFECT
    CONTINUITY rather than as a gap. That module's own docstring warns "first..last is not
    evidence of coverage" and then frames itself in exactly those endpoints.
  * L1.44 ``read_fresh``, L1.55 provenance, L1.57 denominators and L1.60 attrition all ask
    IS THIS DATA RECENT ENOUGH. None asks IS THIS DATA DEEP ENOUGH. For a self-recorded tape
    those are OPPOSITE quantities: a freshness contract is maximally green on a tape deleted five
    minutes ago.
  * L1.60 forbids losing denominator members SILENTLY INSIDE A LOOP. It has no vocabulary for a
    denominator that shrank because the underlying asset was destroyed -- the count was honest,
    and it counted exactly what the run found.

L1.0 NAMES "DATA SPAN" AS A RATCHET, BY NAME. It is the only metric in that list with no floor
artifact, and the only one where a fall CANNOT BE RE-EARNED BY WORKING HARDER. An hour not
recorded is not recoverable by trying harder tomorrow.

THE PROVING INSTANCE, FROM THE DESK'S OWN LEDGER. ``data/moat_coverage_history.jsonl``, three
consecutive rows around 2026-08-17T22:01::

    22:01:11  coverage_pct 100.0  cells_total 12852  tape_bytes 19,462,669,049  files 40720
    22:01:35  coverage_pct 100.0  cells_total  2212  tape_bytes             0   files     0
    (now)     coverage_pct  99.75 cells_total  1631  tape_bytes    819,373,346  files  1644

THE METRIC PRINTED A PERFECT SCORE ON AN EMPTY DIRECTORY, 24 seconds after 19.46 GB of tape was
destroyed, and it reads 99.75% today on 4.2% of the bytes. ``grep -c`` over
``data/alert_delivery.jsonl``: ZERO alerts have ever carried a moat/tape/data-loss title. The
second row also carries ``cells_filled: 2212`` beside ``tape_files: 0`` IN THE SAME RECORD -- an
L1.61 contradiction inside a single artifact, which that law's hand-built money-path registry
cannot reach.

AND THE HALF THAT MAKES IT ACTIONABLE. ``moat_utilisation.py`` opens by calling the tape "the only
dataset on this desk that cannot be bought, re-fetched, scraped or replicated".
``data/bybit_archive_retention.json`` says Bybit publishes its OWN L2 book, unauthenticated, at
200 levels and event-level resolution, ``span_days 363``, ``status FIXED``, ``n_unreachable 0``.
THOSE TWO ARTIFACTS CONTRADICT EACH OTHER AND NOTHING COMPARES THEM. Verified by fetch on
2026-08-19: one day of BTCUSDT is 938.9 MB uncompressed carrying ``topic/type/ts/cts/data.u/
data.seq/b/a`` -- a strict SUPERSET of the market state we record at 25 levels and ~4s sampling.
The only field it lacks is our own receipt clock ``t``/``c``, which is desk-private latency
metadata (L1.46) and genuinely irreplaceable. So the market-state half of the lost 19.46 GB is
RE-BUYABLE, free, today -- and it sat unfetched because NO ARTIFACT ANYWHERE SAID A BYTE WAS LOST.

WHAT THIS MODULE PUBLISHES. Per stream: ``span_now``, ``span_high_water``, a RECOVERY class read
from probe artifacts rather than asserted, and a status. The statuses are the deliverable:

  ``OK``                 span at or above its high-water mark.
  ``LOSS-RECOVERABLE``   span below high-water AND a verified free path exists -> emits the fetch.
  ``LOSS-PERMANENT``     span below high-water with no path -> pages. This is the one that pays.
  ``CONTRADICTED``       a stream doctrine calls irreplaceable while a probe shows it reachable.
  ``UNMEASURED``         no high-water history yet, or the tape is not readable from this host.

HONESTY RAILS, AND THE FIRST TWO ARE THE WHOLE POINT.

  * AN UNPROBED STREAM IS ``UNMEASURED``, NEVER ``IRREPLACEABLE``. "We have not looked for a
    source" and "no source exists" are different claims and only one is evidence (L1.28a, and the
    free-frontier law's documented-failed-search requirement). Asserting irreplaceability is how a
    desk talks itself out of a free 363-day archive.
  * ``data/`` IS GITIGNORED AND VPS-ONLY. A run in a fresh checkout CANNOT measure span and says
    ``NOT-READABLE-HERE``, naming the missing path. It never reports 0, and never reports OK.
  * HIGH-WATER IS A RATCHET (L1.0/L2.0). ``span_now > high_water`` is the ONLY write that moves
    it; a fall is a FENCE FAILURE, not a new baseline. A floor edited to fit a measurement is not
    a floor.
  * THE LEDGER IS APPEND-ONLY and bootstraps from evidence the desk already holds
    (``moat_coverage_history.jsonl``), so the first run is informative rather than blind.

ANTI-TIMIDITY READING, THE ENTIRE PURPOSE. This is a MEASUREMENT duty and a SCOPE EXPANSION. It
lifts nothing, sizes nothing, promotes nothing, opens no gate, loosens no statistical bar and has
no vocabulary for changing any value it reads. Its whole effect is to make "this tape is intact"
distinguishable from "this tape was destroyed and every gauge rounded up" -- byte-identical on
this desk until now, and only one of them is evidence. It ARGUES FOR ACQUISITION: every status it
emits points at data to go and get.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.box_state import data_root, describe, resolved

_ROOT = Path(__file__).resolve().parents[2]

MOAT = _ROOT / "data/moat"
HISTORY = _ROOT / "data/moat_coverage_history.jsonl"
RETENTION = _ROOT / "data/bybit_archive_retention.json"
HIGH_WATER = _ROOT / "data/span_high_water.jsonl"

#: Recovery classes. UNMEASURED is the default and the only honest one absent a probe.
RE_BUYABLE = "RE-BUYABLE"           # a verified, reachable, first-party archive covers it
RE_DERIVABLE = "RE-DERIVABLE"       # reconstructable from something else the desk holds
IRREPLACEABLE = "IRREPLACEABLE"     # a DOCUMENTED failed search, never an assumption
UNMEASURED_RECOVERY = "UNMEASURED"

OK = "OK"
LOSS_RECOVERABLE = "LOSS-RECOVERABLE"
LOSS_PERMANENT = "LOSS-PERMANENT"
CONTRADICTED = "CONTRADICTED"
UNMEASURED = "UNMEASURED"
NOT_READABLE_HERE = "NOT-READABLE-HERE"

#: Statuses a passing fence run may hold. Everything else, including UNMEASURED, fails.
PASSING = frozenset({OK, NOT_READABLE_HERE})

_HOUR_FILE = re.compile(r"^(\d{8})_(\d{2})\.jsonl\.gz$")


@dataclass
class Stream:
    """One recorded stream and everything known about getting it back."""

    key: str
    kind: str
    span_now: int                    # symbol-hours (tape) or rows (archive)
    unit: str
    bytes_now: int
    symbols: int
    earliest: str | None
    latest: str | None
    recovery: str = UNMEASURED_RECOVERY
    recovery_source: str = ""
    recovery_detail: str = ""
    span_high_water: int | None = None
    high_water_at: str | None = None
    status: str = UNMEASURED
    why: str = ""
    fetch_command: str = ""
    #: iterations attempted vs counted, so a skipped file is never invisible (L1.60).
    attempted: int = 0
    skipped: int = 0
    #: quarantined predecessors -- a loss event that a restarted stream would otherwise erase.
    quarantined: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Report:
    generated: str
    status: str
    streams: list[Stream] = field(default_factory=list)
    n_streams: int = 0
    n_loss_permanent: int = 0
    n_loss_recoverable: int = 0
    n_contradicted: int = 0
    n_unmeasured: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated": self.generated,
            "status": self.status,
            "n_streams": self.n_streams,
            "n_loss_permanent": self.n_loss_permanent,
            "n_loss_recoverable": self.n_loss_recoverable,
            "n_contradicted": self.n_contradicted,
            "n_unmeasured": self.n_unmeasured,
            "notes": self.notes,
            "streams": [s.as_dict() for s in self.streams],
        }


# -- measurement -----------------------------------------------------------------------------

def measure_tape(root: Path | None = None) -> list[Stream]:
    """Walk ``data/moat/<venue>/<symbol>/<YYYYMMDD_HH>.jsonl.gz`` into per-venue streams.

    SPAN IS DISTINCT SYMBOL-HOURS PRESENT, never last-minus-first. Endpoint arithmetic is exactly
    what lets a left-truncation read as health, which is the defect this module exists for.
    """
    moat = (root or _ROOT) / "data/moat"
    out: list[Stream] = []
    if not moat.is_dir():
        return out
    for venue_dir in sorted(p for p in moat.iterdir() if p.is_dir()):
        hours: set[tuple[str, str]] = set()
        nbytes = 0
        symbols = 0
        attempted = skipped = 0
        for sym_dir in sorted(p for p in venue_dir.iterdir() if p.is_dir()):
            symbols += 1
            for f in sym_dir.iterdir():
                attempted += 1                      # counted BEFORE any skip (L1.60)
                m = _HOUR_FILE.match(f.name)
                if not m:
                    skipped += 1                    # attrition-ok: not an hourly tape file
                    continue
                try:
                    nbytes += f.stat().st_size
                except OSError:
                    skipped += 1
                    continue
                hours.add((sym_dir.name, f"{m.group(1)}{m.group(2)}"))
        stamps = sorted(h for _, h in hours)
        out.append(Stream(
            key=f"moat/{venue_dir.name}", kind="l2_depth_tape",
            span_now=len(hours), unit="symbol-hours", bytes_now=nbytes, symbols=symbols,
            earliest=stamps[0] if stamps else None, latest=stamps[-1] if stamps else None,
            attempted=attempted, skipped=skipped,
        ))
    return out


def measure_recorder_archives(root: Path | None = None) -> list[Stream]:
    """Discover non-tape recorder archives BY THE RECORDER CONVENTION, never a hardcoded list.

    A hardcoded roster would itself be the L1.57 defect: a denominator counting what the author
    wrote down rather than what the run found, unable to fall when a recorder disappears. The
    desk's recorders all pair ``data/<name>.parquet`` with a ``data/<name|stem>_since`` or
    ``_heartbeat`` stamp, so the pairing IS the registry and it self-builds.
    """
    data = (root or _ROOT) / "data"
    out: list[Stream] = []
    if not data.is_dir():
        return out
    for pq in sorted(data.glob("*.parquet")):
        stem = pq.stem
        singular = stem[:-1] if stem.endswith("s") else stem
        stamps = [data / f"{stem}_since", data / f"{singular}_since",
                  data / f"{stem}_heartbeat", data / f"{singular}_heartbeat"]
        if not any(s.exists() for s in stamps):
            continue                                # not a supervised recorder output
        rows, why = _parquet_rows(pq)
        try:
            nbytes = pq.stat().st_size
        except OSError:
            nbytes = 0
        # A QUARANTINED CORPSE IS EVIDENCE OF A LOSS THAT A RESTARTED STREAM WOULD OTHERWISE HIDE.
        # This module's own first run proved the need: once the liquidation listener was repaired
        # and began a fresh archive, span went from -1 (unreadable) to 10 rows and the stream read
        # OK -- the instrument built to catch "a gauge denominated in what survives" rounding a
        # permanent loss up to health, doing exactly that to itself one level up. The corpses are
        # counted so the event survives the recovery of the stream that suffered it.
        corpses = sorted(data.glob(f"{stem}.corrupt-*{pq.suffix}"))
        out.append(Stream(
            key=f"recorder/{stem}", kind="event_archive", span_now=rows, unit="rows",
            bytes_now=nbytes, symbols=0, earliest=None, latest=None, why=why,
            attempted=1, skipped=0, quarantined=[p.name for p in corpses],
        ))
    return out


def _parquet_rows(p: Path) -> tuple[int, str]:
    """Row count, or -1 with a reason. A CORRUPT ARCHIVE IS NOT AN EMPTY ONE.

    Returning 0 here would be the defect in miniature: an unreadable archive would read as a
    stream that simply has no data yet, and the ratchet would happily accept the fall.
    """
    try:
        import pandas as pd
        return len(pd.read_parquet(p)), ""
    except Exception as e:
        return -1, f"UNREADABLE: {type(e).__name__}: {e}"[:200]


# -- recovery classification, read from probes and never asserted ----------------------------

def classify_recovery(stream: Stream, root: Path | None = None) -> None:
    """Attach a recovery class READ FROM A PROBE ARTIFACT. Absent a probe: UNMEASURED."""
    r = (root or _ROOT) / "data/bybit_archive_retention.json"
    if stream.key.startswith("moat/bybit"):
        try:
            doc = json.loads(r.read_text("utf-8"))
        except Exception:
            stream.recovery = UNMEASURED_RECOVERY
            stream.recovery_detail = "no reachability probe has run for this venue"
            return
        syms = doc.get("symbols") or {}
        if doc.get("n_unreachable") == 0 and syms:
            span = max(int(v.get("span_days") or 0) for v in syms.values())
            stream.recovery = RE_BUYABLE
            stream.recovery_source = str(doc.get("source") or "")
            stream.recovery_detail = (
                f"first-party archive verified reachable, span {span}d, status "
                f"{doc.get('status')}; 200 levels and event-level vs our 25 levels at ~4s. "
                "Our receipt clock t/c is NOT in the archive and stays irreplaceable (L1.46).")
        return
    stream.recovery = UNMEASURED_RECOVERY
    stream.recovery_detail = (
        "no reachability probe exists for this stream -- UNMEASURED, never IRREPLACEABLE. "
        "A documented failed search is what earns the IRREPLACEABLE class.")


# -- the high-water ratchet -------------------------------------------------------------------

def load_high_water(path: Path | None = None) -> dict[str, tuple[int, str]]:
    """Best mark ever recorded per stream. Append-only ledger; later rows never lower a mark."""
    p = path or HIGH_WATER
    marks: dict[str, tuple[int, str]] = {}
    if not p.exists():
        return marks
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                                # attrition-ok: a torn append, never a mark
        key, span = str(row.get("key") or ""), row.get("span")
        if not key or not isinstance(span, int):
            continue
        prev = marks.get(key)
        if prev is None or span > prev[0]:
            marks[key] = (span, str(row.get("ts") or ""))
    return marks


def bootstrap_marks(root: Path | None = None) -> dict[str, int]:
    """Seed the tape's high-water from evidence the desk ALREADY HOLDS.

    ``moat_coverage_history.jsonl`` has recorded ``tape_files`` every ~20s for months, so the
    deepest span this desk ever held is already on disk. Starting blind would make the first run
    report UNMEASURED everywhere and see nothing -- and the 19.46 GB event would go unnoticed a
    second time, by the very instrument built to catch it.

    THE FIELD IS ``tape_files`` AND THE CHOICE IS LOAD-BEARING. The first version of this function
    read ``cells_total``, which ``mine_moat._cells_on_disk`` documents as ``(venue/symbol, day)``
    -- symbol-DAYS. ``span_now`` here counts symbol-HOURS. Comparing them yielded a real-looking
    "1644 below 23436" from two different questions sharing one name: the exact L1.61 defect this
    module cites in its own header, committed by the instrument built to catch it. ``tape_files``
    counts hourly tape files, one per symbol-hour, so it is the unit-matched series.
    ``cells_total`` is additionally unusable as a ratchet because its definition FLAPS -- the
    08-12T06:33 rows step 23436 -> 12432 -> 23436 in thirteen seconds with the bytes unchanged.
    """
    h = (root or _ROOT) / "data/moat_coverage_history.jsonl"
    best = 0
    if not h.exists():
        return {}
    for line in h.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                                # attrition-ok: torn tail of an append
        files = row.get("tape_files")
        if isinstance(files, int) and files > best:
            best = files
    return {"moat/__desk_total__": best} if best else {}


def record_marks(streams: list[Stream], path: Path | None = None) -> int:
    """Append a row for every stream whose span EXCEEDS its mark. Rises only, by construction."""
    p = path or HIGH_WATER
    marks = load_high_water(p)
    rows = []
    now = datetime.now(tz=UTC).isoformat()
    for s in streams:
        if s.span_now < 0:
            continue                                # unreadable: never a mark
        cur = marks.get(s.key)
        if cur is None or s.span_now > cur[0]:
            rows.append({"ts": now, "key": s.key, "span": s.span_now, "unit": s.unit,
                         "bytes": s.bytes_now})
    if rows:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    return len(rows)


# -- verdict ------------------------------------------------------------------------------------

def adjudicate(stream: Stream, marks: dict[str, tuple[int, str]]) -> None:
    """Assign the status. UNMEASURED IS A REAL ANSWER AND NEVER ROUNDS TO OK."""
    if stream.span_now < 0:
        stream.status = LOSS_PERMANENT if stream.recovery != RE_BUYABLE else LOSS_RECOVERABLE
        stream.why = (f"archive unreadable -- {stream.why or 'corrupt'}. A corrupt archive is not "
                      "an empty one; every row it held is gone unless a path exists.")
        return
    if stream.quarantined:
        # The stream may be healthy NOW and the loss is still real. Reporting the current span
        # without this would be the law's own defect: a gauge that improves once the damaged data
        # is out of the denominator. Recovery class decides whether it can be bought back.
        stream.status = (LOSS_RECOVERABLE if stream.recovery == RE_BUYABLE else LOSS_PERMANENT)
        stream.why = (
            f"{len(stream.quarantined)} quarantined predecessor(s) "
            f"({', '.join(stream.quarantined[:3])}) -- this stream suffered an unrecovered loss "
            f"event. It currently holds {stream.span_now} {stream.unit} in a FRESH archive, which "
            "is why every span-only gauge reads healthy. The corpse is retained as evidence; "
            "clear it only once the loss is accounted for.")
        return
    mark = marks.get(stream.key)
    if mark is None:
        stream.status = UNMEASURED
        stream.why = ("no high-water history for this stream yet -- a first observation cannot "
                      "detect a fall. This is UNMEASURED, never OK (L1.28a).")
        return
    stream.span_high_water, stream.high_water_at = mark
    if stream.span_now >= mark[0]:
        stream.status = OK
        stream.why = f"span {stream.span_now} {stream.unit} at or above high-water {mark[0]}"
        return
    lost = mark[0] - stream.span_now
    pct = 100.0 * lost / mark[0] if mark[0] else 0.0
    if stream.recovery == RE_BUYABLE:
        stream.status = LOSS_RECOVERABLE
        stream.why = (f"span fell {lost} {stream.unit} ({pct:.1f}%) below high-water {mark[0]} "
                      f"set {mark[1]}; a verified free path exists -- GO AND FETCH IT.")
        stream.fetch_command = "python scripts/probe_bybit_archive.py  # then the bulk ingest"
    else:
        stream.status = LOSS_PERMANENT
        stream.why = (f"span fell {lost} {stream.unit} ({pct:.1f}%) below high-water {mark[0]} "
                      f"set {mark[1]}, and NO recovery path is known ({stream.recovery}). "
                      "This is unbuyable time.")


def detect_contradictions(streams: list[Stream]) -> list[str]:
    """A stream doctrine calls irreplaceable while a probe shows it reachable (L1.61 class)."""
    out = []
    for s in streams:
        if s.kind == "l2_depth_tape" and s.recovery == RE_BUYABLE:
            out.append(
                f"{s.key}: moat_utilisation.py calls the tape 'the only dataset on this desk that "
                f"cannot be bought, re-fetched, scraped or replicated', while {s.recovery_source} "
                "is verified reachable and RICHER. Both artifacts are honest; nothing compared "
                "them. The doctrine holds for our RECEIPT CLOCK only, not for market state.")
    return out


def build_report(root: Path | None = None) -> Report:
    """The full pass. Refuses to grade what it cannot read."""
    now = datetime.now(tz=UTC).isoformat()
    # THE VANTAGE POINT IS RESOLVED, NEVER ASSUMED. `data/` is gitignored, so a linked worktree --
    # which this desk MANDATES for concurrent sessions (R0423) -- sees an empty data dir and would
    # otherwise report a fabricated verdict about the box. box_state.data_root walks the worktree
    # marker back to the main checkout and reports the BASIS it did so on, so an absent file is
    # distinguishable from an absent vantage point.
    base, basis = data_root(root or _ROOT)
    if not resolved(basis):
        return Report(generated=now, status=NOT_READABLE_HERE, n_streams=0, notes=[
            f"{describe(base, basis)} -- the box's data root could not be established, so span "
            "cannot be measured. NOT-READABLE-HERE is not 0% and is not OK."])
    if not (base / "data/moat").is_dir():
        return Report(generated=now, status=NOT_READABLE_HERE, n_streams=0, notes=[
            f"{base / 'data/moat'} is absent -- data/ is gitignored and VPS-only, so span cannot "
            f"be measured from this host ({describe(base, basis)}). NOT-READABLE-HERE is not 0% "
            "and is not OK."])

    streams = measure_tape(base) + measure_recorder_archives(base)
    for s in streams:
        classify_recovery(s, base)

    # The mark ledger is read from the SAME tree the tape was measured in. Reading it from the
    # module's own root would compare a live tape against a worktree's marks -- a ratchet split
    # across two trees is not a ratchet.
    marks = load_high_water(base / "data/span_high_water.jsonl")
    for key, span in bootstrap_marks(base).items():
        if key not in marks:
            marks[key] = (span, "bootstrapped from moat_coverage_history.jsonl")
    # The desk-total bootstrap is the only mark that can speak for the tape as a whole.
    total = sum(s.span_now for s in streams if s.kind == "l2_depth_tape" and s.span_now > 0)
    desk = marks.get("moat/__desk_total__")
    for s in streams:
        adjudicate(s, marks)

    notes = detect_contradictions(streams)
    if desk is not None and total < desk[0]:
        notes.insert(0, (
            f"DESK-TOTAL TAPE SPAN {total} symbol-hours is BELOW the high-water {desk[0]} recorded "
            f"{desk[1]}. Every coverage gauge reads healthy because each is denominated in what "
            "survives."))
    rep = Report(generated=now, status=OK, streams=streams, n_streams=len(streams),
                 notes=[describe(base, basis), *notes])
    rep.n_loss_permanent = sum(1 for s in streams if s.status == LOSS_PERMANENT)
    rep.n_loss_recoverable = sum(1 for s in streams if s.status == LOSS_RECOVERABLE)
    rep.n_unmeasured = sum(1 for s in streams if s.status == UNMEASURED)
    rep.n_contradicted = len(notes)
    if not streams:
        rep.status = UNMEASURED
    elif rep.n_loss_permanent:
        rep.status = LOSS_PERMANENT
    elif rep.n_loss_recoverable or (desk is not None and total < desk[0]):
        rep.status = LOSS_RECOVERABLE
    elif rep.n_unmeasured == len(streams):
        rep.status = UNMEASURED
    elif notes:
        rep.status = CONTRADICTED
    return rep
