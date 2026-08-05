"""MOAT UTILISATION -- what fraction of the one asset this desk cannot re-buy has ever been READ.

THE ASSET, AND WHY IT IS DIFFERENT FROM EVERY OTHER ROW IN THE REGISTRY. The recorded L2 tape
under ``data/moat/`` is the only dataset on this desk that cannot be bought, re-fetched, scraped
or replicated. A competitor can point a recorder at the same venue tomorrow; they cannot have OUR
snapshots from last month, and no amount of money buys an hour that was not recorded. It therefore
accrues ONLY in calendar time, which makes its cost structure the exact inverse of everything else
here: refetchable data costs bandwidth and is free to re-acquire, while this costs a running
process forever and is infinitely expensive to re-acquire. That asymmetry is the whole reason this
module exists.

THE MEASUREMENT NOBODY WAS TAKING. ``moat_audit.py`` scores book QUALITY. ``mine_moat.py`` and
``screen_moat.py`` track their own (cell x mechanism) COVERAGE grids. ``data_registry.py`` scores
the asset's moat and span. Not one of them answers the question that decides whether the recorders
are an asset or a cost centre:

    OF THE BYTES, SYMBOL-HOURS, SYMBOLS, VENUES AND DEPTH LEVELS ON DISK, WHAT FRACTION HAS EVER
    REACHED A SCREEN, A CAMPAIGN OR A FEATURE EXTRACTION?

A dataset you record and do not read is a cost centre wearing an asset's name, and the cost is
paid daily, silently, in disk and process supervision. Coverage grids cannot answer it because
they are denominated in the cells their own organ chose to enumerate; this is denominated in what
is ON DISK.

FIVE READINGS, AND THE FIFTH IS THE DELIVERABLE.

  1. COVERAGE OF RECORDING, IN BOTH DIRECTIONS. A symbol the desk trades or screens but never
     records is a hole that gets worse every hour and can never be backfilled. A symbol recorded
     but never read is spend with no return. Those are opposite defects with opposite fixes, and
     reporting only one of them is how a recorder universe drifts away from a research universe
     without anybody noticing (gap #39 on this desk: the recorder held 20 majors while the book
     held small-caps, ZERO intersection, and the cost model built on it was useless).
  2. CONTINUITY, MEASURED AS GAPS AND NOT AS ENDPOINTS. First..last is not evidence of coverage.
     Today's data-registry pass measured ``exchange_announcements`` claiming 2,356 elapsed days
     while holding 38 observed ones, because a single 2,318-day hole sat between the endpoints.
     The moat tape rotates HOURLY, so its unit of observation is one symbol-hour, and its gaps are
     recorder deaths -- the failure this desk has already had (silent recorder death is the first
     check ``moat_audit.py`` runs). Endpoint-only reporting hides exactly that.
  3. UTILISATION -- the number that matters, at three granularities because the evidence supports
     three: symbol-HOURS (exact, from readers that record which hours they consumed), symbol-DAYS
     (from cell-level coverage artifacts) and SYMBOLS (from artifacts that record only a symbol
     list). Each is reported with the granularity it was measured at, never promoted to a finer
     one it cannot support.
  4. HUNTING YIELD -- distinct hypotheses ever screened ON this tape, the ECONOMIC MECHANISM
     CLASSES they occupy (taken from ``mechanism_census.TAXONOMY`` -- this module invents no
     taxonomy of its own), and the best out-of-sample result. The known answer is a MEASURED
     NEGATIVE and is reported as one: the two moat "survivors" landed at OOS 0.103/0.098, the same
     0.100 noise ceiling 129 textbook mechanisms on public daily bars reached. That is knowledge,
     and it is not a lead.
  5. THE RANKED NEXT-ACTION LIST -- the highest-value UNREAD slice of the tape and the mechanism
     class it could test. Without this the module is a dashboard; with it, it is an ROI
     instrument, because every row is an experiment that can be run tomorrow on data already paid
     for.

HONESTY RAILS, NON-NEGOTIABLE, AND THE FIRST ONE IS THE WHOLE POINT.

  * THE TAPE IS VPS-ONLY. ``data/`` is gitignored and the recorders write only on the box, so a
    run in a checkout CANNOT measure utilisation. It says ``NOT-READABLE-HERE`` and names the
    exact missing paths. It never reports 0%.
  * "0% UTILISED" AND "CANNOT MEASURE UTILISATION HERE" ARE DIFFERENT FACTS AND ARE NEVER MERGED.
    The first is a measurement and it is damning. The second is an absence of one. Every
    utilisation figure is therefore ``None`` under NOT-READABLE-HERE and a real number -- possibly
    0.0 -- under MEASURED. Conflating them is precisely the defect this desk keeps finding in its
    own instruments, so it is pinned by test rather than by intention.
  * A THIRD STATE EXISTS AND IT IS ALSO NOT ZERO. Tape present, but no consumption record readable
    at all: then 0% and "the readers do not record what they read" are indistinguishable, and the
    status is ``PARTIAL`` with the missing artifacts named rather than a confident zero.
  * DOCUMENTED IS NOT MEASURED. Dated in-repo observations of the box (the 10 GB / 28,361-file
    tape, the n_obs 1,065 campaign) are carried in their own block, tagged
    ``DOCUMENTED-NOT-MEASURED``, with the citation and a token check that fails loudly if the
    source text changes. They never enter a measured field.

NO SECOND TAPE READER. This module does not parse a single depth row. Partition inventory is
filesystem metadata (path, name, size) and every question that needs the CONTENT of the tape is
answered by the existing audited readers -- ``libs.research.moat_microstructure.read_partition``,
``libs.hypmax.moat_mine._depth_snaps`` -- through the organs that already call them. The mixed
recorder schema (``k="d"`` from the Binance recorders, ``k="depth"`` from Bybit) has already
scarred one organ with a silent-zero; a second parser here would be a second place for it.

ZERO AUTHORITY. This is a measurement instrument. It promotes nothing, blocks nothing, sizes
nothing and changes no gate, threshold or verdict anywhere on the desk.

Pure stdlib plus the repo's own read-only helpers. No network, no keys, no writes of its own.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

from libs.data.universe import RECORDED_TOP_N, RESEARCH_TOP_N, TRADEABLE_TOP_N
from libs.hypmax.moat_mine import _EXTRACTORS
from libs.ops.disk import tape_bytes
from libs.research.data_registry import NOT_READABLE_HERE, measure_gaps
from libs.research.mechanism_census import CLASS_BY_ID, TAXONOMY, classify
from libs.research.orderbook_state import _DEEP_LEVELS

__all__ = [
    "DOCUMENTED",
    "GRAIN_COUNTS",
    "GRAIN_DAY",
    "GRAIN_HOUR",
    "GRAIN_SYMBOL",
    "MEASURED",
    "NOT_READABLE_HERE",
    "PARTIAL",
    "READERS",
    "RECORDERS",
    "SCHEMA_VERSION",
    "Continuity",
    "DepthLevelUse",
    "HourGaps",
    "NextAction",
    "Partition",
    "ReadRecord",
    "RecorderDecl",
    "UniverseSource",
    "Utilisation",
    "build_report",
    "consumed_depth_levels",
    "continuity",
    "depth_level_use",
    "documented_reference",
    "hunting_yield",
    "inventory",
    "measure_hour_gaps",
    "missing_tape_paths",
    "parse_partition",
    "rank_next_actions",
    "read_records",
    "recorder_declarations",
    "tape_opening_scripts",
    "tape_testable_classes",
    "universe_sources",
    "utilisation",
]

SCHEMA_VERSION = "1.0.0"

#: Status vocabulary. ``NOT_READABLE_HERE`` is imported rather than re-spelled so an operator can
#: grep one token across every artifact on this desk that has to admit the same thing.
MEASURED = "MEASURED"
#: Tape present, consumption records absent. NOT a zero: 0% read and "nobody records what they
#: read" produce identical evidence, and only one of them is a finding.
PARTIAL = "PARTIAL"
#: A dated in-repo observation of the live box. Carried, cited, and never merged into a measured
#: field.
DOCUMENTED = "DOCUMENTED-NOT-MEASURED"

#: ``data/moat/<venue>/<SYMBOL>/YYYYMMDD_HH.jsonl.gz`` -- the shape all three recorders write.
_PARTITION_NAME = re.compile(r"^(?P<day>\d{8})_(?P<hour>\d{2})$")

#: Milliseconds are irrelevant here; the tape's unit of observation is one hourly partition, which
#: is what ``check_clock_provenance``'s cadence argument already calls "one file per stream".
_HOUR = timedelta(hours=1)


# ------------------------------------------------------------------------------- inventory -----

@dataclass(frozen=True)
class Partition:
    """One hourly partition on disk. FILESYSTEM METADATA ONLY -- no row is parsed here."""

    venue: str
    symbol: str
    day: str            #: YYYYMMDD, as the recorder writes it
    hour: int           #: 0..23
    size_bytes: int

    @property
    def cell(self) -> tuple[str, str, str]:
        """(venue, symbol, day) -- the SAME grid mine_moat/screen_moat/screen_orderbook_state use,
        so an unread cell here is a visible hole rather than an accounting mismatch."""
        return (self.venue, self.symbol, self.day)

    @property
    def symbol_hour(self) -> tuple[str, str, str, int]:
        return (self.venue, self.symbol, self.day, self.hour)

    @property
    def start(self) -> datetime:
        return datetime(int(self.day[:4]), int(self.day[4:6]), int(self.day[6:8]),
                        self.hour, tzinfo=UTC)

    @property
    def iso_day(self) -> str:
        return f"{self.day[:4]}-{self.day[4:6]}-{self.day[6:8]}"


def parse_partition(path: Path, *, venue: str, symbol: str) -> Partition | None:
    """A partition from its path, or ``None`` when the name is not the recorder's.

    Returning ``None`` rather than guessing a day is deliberate: a mis-parsed name would land the
    file in the wrong hour and make a gap appear or disappear, and the gap is the product.
    """
    m = _PARTITION_NAME.match(path.name.split(".", 1)[0])
    if m is None:
        return None
    hour = int(m.group("hour"))
    if hour > 23:
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    return Partition(venue=venue, symbol=symbol, day=m.group("day"), hour=hour, size_bytes=size)


def inventory(moat_root: Path) -> list[Partition]:
    """Every hourly partition under ``data/moat/<venue>/<SYMBOL>/``, in a stable order.

    Empty when the tape is absent -- and the CALLER must treat that as NOT-READABLE-HERE rather
    than as an empty tape, which is why nothing in this function returns a percentage.
    """
    if not moat_root.is_dir():
        return []
    out: list[Partition] = []
    for vdir in sorted(p for p in moat_root.iterdir() if p.is_dir()):
        for sdir in sorted(p for p in vdir.iterdir() if p.is_dir()):
            for f in sorted(sdir.glob("*.jsonl.gz")):
                part = parse_partition(f, venue=vdir.name, symbol=sdir.name)
                if part is not None:
                    out.append(part)
    return out


def missing_tape_paths(moat_root: Path, venues: Sequence[str]) -> list[str]:
    """The exact paths a reader must be told about when the tape is not here.

    Named per VENUE, not as one blanket "data/moat missing", so the artifact says WHICH recorder
    is not running -- the same courtesy ``screen_orderbook_state.missing_paths`` extends.
    """
    out: list[str] = []
    if not moat_root.is_dir():
        out.append(f"{moat_root} (tape root absent -- no recorder has ever written here)")
    for v in venues:
        d = moat_root / v
        if not d.is_dir():
            out.append(f"{d} (venue root absent)")
        elif not any(d.rglob("*.jsonl.gz")):
            out.append(f"{d}/**/*.jsonl.gz (venue root exists, zero partitions)")
    return out


# --------------------------------------------------------------- declared recorder universe ----

@dataclass(frozen=True)
class RecorderDecl:
    """What one recorder SAYS it records, read from its source rather than from memory."""

    script: str
    venue: str
    symbols: tuple[str, ...]
    max_symbols: int | None
    depth_levels: int | None
    status: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"script": self.script, "venue": self.venue, "status": self.status,
                "declared_symbols": list(self.symbols), "n_declared": len(self.symbols),
                "max_symbols": self.max_symbols, "depth_levels_requested": self.depth_levels,
                "note": self.note}


#: script -> (venue root under data/moat, the module-level tuples that hold its universe).
#: READ BY ``ast``, NEVER IMPORTED. ``run_recorder_bybit`` calls ``_universe()`` at module scope,
#: which performs a NETWORK request to Bybit's instruments-info; importing it to ask what it
#: records would make a measurement instrument phone a venue. The other two read the trade log at
#: import time, which is a live-state dependency this module has no business acquiring either.
RECORDERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("scripts/run_recorder.py", "fut", ("_BENCH", "_CORE")),
    ("scripts/run_recorder_spot.py", "spot", ("_BENCH", "_CORE")),
    ("scripts/run_recorder_bybit.py", "bybit", ("_FALLBACK",)),
)

#: The depth request each recorder issues, e.g. ``limit=20``. ANCHORED ON THE ENDPOINT STRING
#: LITERAL (``"/fapi/v1/depth"``, ``"/v5/market/orderbook"``), not on the word "depth" anywhere on
#: the line. The looser form read 1000 out of the spot recorder, because its weight-budget COMMENT
#: mentions depth and then quotes ``aggTrades(limit=1000)`` -- a fifty-fold overstatement of
#: recorded book depth, and it would have manufactured 980 "unread levels" out of a comment.
_DEPTH_LIMIT = re.compile(r'"/[^"\n]*(?:depth|orderbook)"[^\n]*?limit=(\d+)', re.IGNORECASE)


def _module_tuples(tree: ast.Module, names: Sequence[str]) -> tuple[str, ...]:
    """Module-level string tuples/lists, concatenated in the order requested, deduped.

    Order is priority order in every recorder here (benchmark, then traded, then majors), so it is
    preserved: a universe reported alphabetically would hide which names get evicted when the
    weight cap binds.
    """
    found: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not isinstance(tgt, ast.Name) or tgt.id not in names:
                continue
            if not isinstance(node.value, ast.Tuple | ast.List):
                continue
            vals = tuple(e.value for e in node.value.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str))
            if vals and tgt.id not in found:
                found[tgt.id] = vals
    ordered: list[str] = []
    for n in names:
        for s in found.get(n, ()):
            if s not in ordered:
                ordered.append(s)
    return tuple(ordered)


def _module_int(tree: ast.Module, name: str) -> int | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if (isinstance(tgt, ast.Name) and tgt.id == name
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, int)):
                return int(node.value.value)
    return None


def recorder_declarations(root: Path) -> list[RecorderDecl]:
    """What each recorder declares it will record, parsed from source with ``ast``.

    A recorder whose source is unreadable is reported NOT-READABLE-HERE with its path, never as a
    recorder that declares nothing -- an empty declared universe would read as "the desk wants
    nothing recorded", which would turn every coverage hole into a non-hole.
    """
    out: list[RecorderDecl] = []
    for script, venue, tuple_names in RECORDERS:
        p = root / script
        try:
            src = p.read_text("utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError, ValueError):
            out.append(RecorderDecl(script=script, venue=venue, symbols=(), max_symbols=None,
                                    depth_levels=None, status=NOT_READABLE_HERE,
                                    note=f"cannot read or parse {p}"))
            continue
        m = _DEPTH_LIMIT.search(src)
        out.append(RecorderDecl(
            script=script, venue=venue,
            symbols=_module_tuples(tree, tuple_names),
            max_symbols=_module_int(tree, "_MAX_SYMBOLS"),
            depth_levels=int(m.group(1)) if m is not None else None,
            status=MEASURED,
            note=("static universe floor read from source: the LIVE universe additionally unions "
                  "held positions and recently traded names (gap #39), which are runtime state "
                  "and are reported separately"),
        ))
    return out


# ------------------------------------------------------------------- universes the desk wants --

@dataclass(frozen=True)
class UniverseSource:
    """One declaration of what the desk trades or screens, and whether it could be read."""

    name: str
    path: str
    kind: str                      #: "traded" | "screened" | "declared-breadth"
    symbols: tuple[str, ...]
    status: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "path": self.path, "kind": self.kind, "status": self.status,
                "n_symbols": len(self.symbols), "symbols": list(self.symbols), "note": self.note}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _base(sym: str) -> str:
    """``BTCUSDT`` and ``BTC`` are the same instrument wearing two conventions.

    Comparing them without normalising is how a coverage hole gets invented: every recorded name
    would read as absent from a panel that quotes bases, and the instrument's headline finding
    would be an artifact of a suffix.
    """
    s = sym.upper().strip()
    for quote in ("USDT", "USDC", "USD", "BUSD"):
        if s.endswith(quote) and len(s) > len(quote):
            return s[: -len(quote)]
    return s


def universe_sources(root: Path) -> list[UniverseSource]:
    """Every readable declaration of the universe the desk TRADES or SCREENS.

    Each source carries its own status. The two book files are VPS runtime state and are expected
    to be NOT-READABLE-HERE; saying so is the difference between "the desk trades nothing" and
    "this box cannot see what the desk trades", and only the second is true in a checkout.
    """
    out: list[UniverseSource] = []

    pos = _read_json(root / "data/cashcarry_positions.json")
    syms: tuple[str, ...] = ()
    if isinstance(pos, dict) and isinstance(pos.get("positions"), dict):
        syms = tuple(sorted(str(s) for s in pos["positions"]))
    out.append(UniverseSource(
        name="held_book", path="data/cashcarry_positions.json", kind="traded", symbols=syms,
        status=MEASURED if syms else NOT_READABLE_HERE,
        note=("live positions -- the universe the recorders union in-flight (gap #39). Runtime "
              "state on the VPS." if not syms else "live positions")))

    trades = _read_json(root / "data/cashcarry_trades.json")
    rows = trades if isinstance(trades, list) else (
        trades.get("trades") if isinstance(trades, dict) else None)
    tsyms: list[str] = []
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict):
                s = r.get("symbol") or r.get("sym")
                if isinstance(s, str) and s not in tsyms:
                    tsyms.append(s)
    out.append(UniverseSource(
        name="traded_log", path="data/cashcarry_trades.json", kind="traded",
        symbols=tuple(sorted(tsyms)),
        status=MEASURED if tsyms else NOT_READABLE_HERE,
        note="names the desk has actually traded -- the cost model's calibration universe"))

    panel = _read_json(root / "data/perp_close_panel.json")
    psyms = tuple(str(s) for s in panel["declared_universe"]) if (
        isinstance(panel, dict) and isinstance(panel.get("declared_universe"), list)) else ()
    out.append(UniverseSource(
        name="perp_close_panel", path="data/perp_close_panel.json", kind="screened",
        symbols=psyms, status=MEASURED if psyms else NOT_READABLE_HERE,
        note="the cross-sectional panel every daily screen is computed over"))

    out.append(UniverseSource(
        name="declared_breadth", path="libs/data/universe.py", kind="declared-breadth",
        symbols=(), status=MEASURED,
        note=(f"research={RESEARCH_TOP_N} tradeable={TRADEABLE_TOP_N} recorded={RECORDED_TOP_N} "
              "-- the desk's single source for breadth. RECORDED is bounded by the recorder's "
              "request budget, not by research appetite, so recorded < tradeable is a DECISION "
              "and the shortfall is a measured, permanent hole rather than an oversight")))
    return out


# ------------------------------------------------------------------------------ continuity -----

@dataclass(frozen=True)
class HourGaps:
    """Internal holes in an observed set of hours. Every field measured from the hours themselves.

    HOURS, NOT DAYS, and the granularity is load-bearing. ``data_registry.measure_gaps`` is the
    desk's day-level gap primitive and it is reused below for the day view, but a recorder that
    dies at 09:00 and is respawned at 21:00 loses twelve unbuyable hours while leaving BOTH days
    observed. A day-level reading of this tape would report that outage as no gap at all.
    """

    observed_hours: int
    elapsed_hours: int
    gap_hours: int
    n_gaps: int
    largest_gap_hours: int
    largest_gap_from: str | None
    largest_gap_to: str | None


def measure_hour_gaps(hours: Iterable[datetime]) -> HourGaps | None:
    """Holes between the first and last observed hour. ``None`` when there is nothing to measure.

    A gap is a maximal run of consecutive clock-hours carrying NO partition, strictly inside
    first..last -- leading/trailing absence is where the record begins and ends, not a hole. So
    ``gap_hours == elapsed_hours - observed_hours`` exactly, which is the identity that makes the
    two numbers impossible to quietly disagree (the same identity ``measure_gaps`` enforces one
    granularity up).
    """
    hs = sorted({h.replace(minute=0, second=0, microsecond=0) for h in hours})
    if len(hs) < 2:
        return None
    runs: list[tuple[int, datetime, datetime]] = []
    for prev, cur in pairwise(hs):
        missing = int((cur - prev) / _HOUR) - 1
        if missing > 0:
            runs.append((missing, prev + _HOUR, cur - _HOUR))
    biggest = max(runs, default=None, key=lambda r: r[0])
    elapsed = int((hs[-1] - hs[0]) / _HOUR) + 1
    return HourGaps(
        observed_hours=len(hs),
        elapsed_hours=elapsed,
        gap_hours=sum(r[0] for r in runs),
        n_gaps=len(runs),
        largest_gap_hours=0 if biggest is None else biggest[0],
        largest_gap_from=None if biggest is None else biggest[1].isoformat(),
        largest_gap_to=None if biggest is None else biggest[2].isoformat(),
    )


@dataclass(frozen=True)
class Continuity:
    """One (venue, symbol) stream's real extent -- recorded hours against elapsed hours."""

    venue: str
    symbol: str
    first_hour_utc: str
    last_hour_utc: str
    recorded_hours: int
    elapsed_hours: int
    coverage_pct: float | None
    gap_hours: int | None
    n_gaps: int | None
    largest_gap_hours: int | None
    largest_gap_from: str | None
    largest_gap_to: str | None
    hours_since_last: int | None
    observed_days: int
    day_gap_days: int | None
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue, "symbol": self.symbol,
            "first_hour_utc": self.first_hour_utc, "last_hour_utc": self.last_hour_utc,
            "recorded_hours": self.recorded_hours, "elapsed_hours": self.elapsed_hours,
            "coverage_pct": self.coverage_pct, "gap_hours": self.gap_hours,
            "n_gaps": self.n_gaps, "largest_gap_hours": self.largest_gap_hours,
            "largest_gap_from": self.largest_gap_from, "largest_gap_to": self.largest_gap_to,
            "hours_since_last": self.hours_since_last,
            "observed_days": self.observed_days, "day_gap_days": self.day_gap_days,
            "bytes": self.size_bytes,
        }


def continuity(parts: Sequence[Partition], *, now: datetime | None = None) -> list[Continuity]:
    """Per (venue, symbol): recorded hours vs elapsed hours, and the largest hole.

    ``hours_since_last`` is reported alongside the internal gaps because a recorder that died an
    hour ago has NO internal gap at all and a perfect coverage_pct -- the endpoint failure mode,
    running forwards instead of backwards. Both are needed or a dead stream reads as a healthy one.
    """
    ts = (now or datetime.now(tz=UTC)).replace(minute=0, second=0, microsecond=0)
    by: dict[tuple[str, str], list[Partition]] = {}
    for p in parts:
        by.setdefault((p.venue, p.symbol), []).append(p)
    out: list[Continuity] = []
    for (venue, symbol), group in sorted(by.items()):
        hours = sorted(p.start for p in group)
        g = measure_hour_gaps(hours)
        dg = measure_gaps(sorted({p.iso_day for p in group}))
        elapsed = g.elapsed_hours if g is not None else len(hours)
        out.append(Continuity(
            venue=venue, symbol=symbol,
            first_hour_utc=hours[0].isoformat(), last_hour_utc=hours[-1].isoformat(),
            recorded_hours=len(set(hours)), elapsed_hours=elapsed,
            coverage_pct=(None if g is None
                          else round(100.0 * g.observed_hours / max(g.elapsed_hours, 1), 3)),
            gap_hours=None if g is None else g.gap_hours,
            n_gaps=None if g is None else g.n_gaps,
            largest_gap_hours=None if g is None else g.largest_gap_hours,
            largest_gap_from=None if g is None else g.largest_gap_from,
            largest_gap_to=None if g is None else g.largest_gap_to,
            hours_since_last=max(0, int((ts - hours[-1]) / _HOUR)),
            observed_days=len({p.iso_day for p in group}),
            day_gap_days=None if dg is None else dg.gap_days,
            size_bytes=sum(p.size_bytes for p in group),
        ))
    return out


# ---------------------------------------------------------------------------- consumption ------

#: How precisely an artifact records what it consumed. The ladder is the whole reason utilisation
#: is reported at three granularities: an artifact that says "12 symbols" cannot be promoted into
#: a statement about hours, and promoting it would manufacture utilisation the desk has not earned.
GRAIN_HOUR = "SYMBOL-HOUR"
GRAIN_DAY = "SYMBOL-DAY"
GRAIN_SYMBOL = "SYMBOL"
GRAIN_COUNTS = "COUNTS-ONLY"


@dataclass(frozen=True)
class ReadRecord:
    """What one consumer artifact proves was READ off the tape."""

    artifact: str
    script: str
    grain: str
    status: str
    hours: frozenset[tuple[str, str, str, int]] = frozenset()
    days: frozenset[tuple[str, str, str]] = frozenset()
    symbols: frozenset[tuple[str, str]] = frozenset()
    files_declared: int | None = None
    n_obs: int | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"artifact": self.artifact, "script": self.script, "grain": self.grain,
                "status": self.status, "symbol_hours_recorded": len(self.hours),
                "symbol_days_recorded": len(self.days), "symbols_recorded": len(self.symbols),
                "files_declared": self.files_declared, "n_obs": self.n_obs, "note": self.note}


def _split_symbol(raw: str, *, default_venue: str | None = None) -> tuple[str, str] | None:
    """``fut/BTCUSDT``, ``fut|BTCUSDT`` or a bare ``BTCUSDT`` under a known venue."""
    s = raw.strip()
    for sep in ("/", "|", ":"):
        if sep in s:
            venue, _, sym = s.partition(sep)
            return (venue.strip(), sym.strip()) if venue and sym else None
    return (default_venue, s) if default_venue is not None and s else None


def _adapt_micro_feature_store(obj: Any, root: Path) -> ReadRecord:
    """``micro_factory``'s cache: ``{"SYM/YYYYMMDD_HH": row}`` -- the ONLY exact symbol-HOUR record.

    Its venue is implicit: ``scripts/micro_factory.py`` reads ``data/moat/fut`` only, so the key
    carries no venue and the venue is supplied here from the script's own constant rather than
    guessed. An hour in this cache was decompressed and turned into features, which is the
    strictest available definition of "read".
    """
    art = "data/micro_feature_store.json"
    if not isinstance(obj, dict):
        return ReadRecord(artifact=art, script="scripts/micro_factory.py", grain=GRAIN_HOUR,
                          status=NOT_READABLE_HERE,
                          note=f"absent or unparseable: {root / art}")
    hours: set[tuple[str, str, str, int]] = set()
    for key in obj:
        sym, _, stamp = str(key).partition("/")
        m = _PARTITION_NAME.match(stamp)
        if sym and m is not None:
            hours.add(("fut", sym, m.group("day"), int(m.group("hour"))))
    return ReadRecord(artifact=art, script="scripts/micro_factory.py", grain=GRAIN_HOUR,
                      status=MEASURED, hours=frozenset(hours),
                      days=frozenset({(v, s, d) for v, s, d, _ in hours}),
                      symbols=frozenset({(v, s) for v, s, _, _ in hours}),
                      note="hours turned into microstructure features and cached as immutable")


def _adapt_moat_coverage(obj: Any, root: Path) -> ReadRecord:
    """``mine_moat``'s grid: ``filled["<venue>/<SYM>|<YYYYMMDD>"]`` -- symbol-DAY."""
    art = "data/moat_coverage.json"
    if not isinstance(obj, dict) or not isinstance(obj.get("filled"), dict):
        return ReadRecord(artifact=art, script="scripts/mine_moat.py", grain=GRAIN_DAY,
                          status=NOT_READABLE_HERE, note=f"absent or unparseable: {root / art}")
    days: set[tuple[str, str, str]] = set()
    for key in obj["filled"]:
        head, _, day = str(key).partition("|")
        vs = _split_symbol(head)
        if vs is not None and day:
            days.add((vs[0], vs[1], day))
    return ReadRecord(artifact=art, script="scripts/mine_moat.py", grain=GRAIN_DAY,
                      status=MEASURED, days=frozenset(days),
                      symbols=frozenset({(v, s) for v, s, _ in days}),
                      note="cells where at least one reconstruction produced a finite observation")


def _adapt_screen_coverage(obj: Any, root: Path) -> ReadRecord:
    """``screen_moat``'s grid: ``screened["<venue>|<SYM>|<YYYYMMDD>"]`` -- symbol-DAY."""
    art = "data/moat_screen_coverage.json"
    if not isinstance(obj, dict) or not isinstance(obj.get("screened"), dict):
        return ReadRecord(artifact=art, script="scripts/screen_moat.py", grain=GRAIN_DAY,
                          status=NOT_READABLE_HERE, note=f"absent or unparseable: {root / art}")
    days: set[tuple[str, str, str]] = set()
    files = 0
    for key, rec in obj["screened"].items():
        bits = str(key).split("|")
        if len(bits) == 3:
            days.add((bits[0], bits[1], bits[2]))
        if isinstance(rec, dict) and isinstance(rec.get("files"), int):
            files += int(rec["files"])
    return ReadRecord(artifact=art, script="scripts/screen_moat.py", grain=GRAIN_DAY,
                      status=MEASURED, days=frozenset(days),
                      symbols=frozenset({(v, s) for v, s, _ in days}),
                      files_declared=files or None,
                      note="cells a Stage-A screen has consumed at least once")


def _adapt_moat_screen(obj: Any, root: Path) -> ReadRecord:
    """``screen_moat``'s report: a SYMBOL list plus counts. No cell identities."""
    art = "data/moat_screen.json"
    if not isinstance(obj, dict):
        return ReadRecord(artifact=art, script="scripts/screen_moat.py", grain=GRAIN_SYMBOL,
                          status=NOT_READABLE_HERE, note=f"absent or unparseable: {root / art}")
    raw = obj.get("symbols")
    syms: set[tuple[str, str]] = set()
    if isinstance(raw, list):
        for s in raw:
            vs = _split_symbol(str(s))
            if vs is not None:
                syms.add(vs)
    fr = obj.get("files_read")
    return ReadRecord(artifact=art, script="scripts/screen_moat.py", grain=GRAIN_SYMBOL,
                      status=MEASURED, symbols=frozenset(syms),
                      files_declared=int(fr) if isinstance(fr, int) else None,
                      note="symbols screened in the LAST run only; the cumulative record is the "
                           "coverage artifact")


def _adapt_orderbook_state(obj: Any, root: Path) -> ReadRecord:
    """``screen_orderbook_state``: counts only. Reported as such, and it is a named defect below."""
    art = "data/orderbook_state_screen.json"
    if not isinstance(obj, dict):
        return ReadRecord(artifact=art, script="scripts/screen_orderbook_state.py",
                          grain=GRAIN_COUNTS, status=NOT_READABLE_HERE,
                          note=f"absent or unparseable: {root / art}")
    if str(obj.get("status")) == NOT_READABLE_HERE:
        return ReadRecord(artifact=art, script="scripts/screen_orderbook_state.py",
                          grain=GRAIN_COUNTS, status=NOT_READABLE_HERE,
                          note="the screen itself reported NOT-READABLE-HERE: no tape to read")
    fr = obj.get("files_read")
    return ReadRecord(artifact=art, script="scripts/screen_orderbook_state.py",
                      grain=GRAIN_COUNTS, status=MEASURED,
                      files_declared=int(fr) if isinstance(fr, int) else None,
                      note="records HOW MANY partitions it read, never WHICH -- so its "
                           "consumption cannot be attributed to any symbol-hour")


def _adapt_moat_campaign(obj: Any, root: Path) -> ReadRecord:
    """``run_moat_campaign``: ``bars_per_symbol`` keys plus the scored ``n_obs``."""
    art = "reports/moat_campaign.json"
    if not isinstance(obj, dict):
        return ReadRecord(artifact=art, script="scripts/run_moat_campaign.py", grain=GRAIN_SYMBOL,
                          status=NOT_READABLE_HERE, note=f"absent or unparseable: {root / art}")
    venue = str(obj.get("venue") or "")
    bps = obj.get("bars_per_symbol")
    syms: set[tuple[str, str]] = set()
    if isinstance(bps, dict):
        for s, n in bps.items():
            if isinstance(n, int) and n > 0 and venue:
                syms.add((venue, str(s)))
    n_obs = obj.get("n_obs")
    status = MEASURED if syms else NOT_READABLE_HERE
    note = ("symbols folded into bars; n_obs is the SCORED window, which is smaller than the read "
            "window" if syms else
            f"artifact status {obj.get('status')!r}: {obj.get('blocker')} -- nothing was read")
    return ReadRecord(artifact=art, script="scripts/run_moat_campaign.py", grain=GRAIN_SYMBOL,
                      status=status, symbols=frozenset(syms),
                      n_obs=int(n_obs) if isinstance(n_obs, int) else None, note=note)


def _adapt_moat_quality(obj: Any, root: Path) -> ReadRecord:
    """``moat_audit``: ``symbols["<side>/<SYM>"]`` -- a SAMPLED read, six files per symbol."""
    art = "data/moat_quality.json"
    if not isinstance(obj, dict) or not isinstance(obj.get("symbols"), dict):
        return ReadRecord(artifact=art, script="scripts/moat_audit.py", grain=GRAIN_SYMBOL,
                          status=NOT_READABLE_HERE, note=f"absent or unparseable: {root / art}")
    syms: set[tuple[str, str]] = set()
    for key in obj["symbols"]:
        vs = _split_symbol(str(key))
        if vs is not None:
            syms.add(vs)
    return ReadRecord(artifact=art, script="scripts/moat_audit.py", grain=GRAIN_SYMBOL,
                      status=MEASURED, symbols=frozenset(syms),
                      note="a QUALITY sample, not a research read: six random files per symbol")


def _adapt_micro_features(obj: Any, root: Path) -> ReadRecord:
    art = "data/micro_features.json"
    if not isinstance(obj, dict) or not isinstance(obj.get("symbols"), list):
        return ReadRecord(artifact=art, script="scripts/micro_factory.py", grain=GRAIN_SYMBOL,
                          status=NOT_READABLE_HERE, note=f"absent or unparseable: {root / art}")
    syms = {("fut", str(s)) for s in obj["symbols"] if str(s)}
    return ReadRecord(artifact=art, script="scripts/micro_factory.py", grain=GRAIN_SYMBOL,
                      status=MEASURED, symbols=frozenset(syms),
                      note="withdrawal-vs-volatility feature pass over the futures leg")


#: THE READER REGISTRY -- every artifact on this desk that RECORDS what it took off the tape.
#: Explicit rather than discovered, because "a script mentions data/moat" is not evidence that it
#: read anything, and counting prose as consumption would inflate utilisation with imagination.
#: A script that opens the tape and appears in no row here is reported separately as a reader whose
#: consumption is INVISIBLE -- which is a defect in that script, not a zero in this one.
READERS: tuple[tuple[str, Callable[[Any, Path], ReadRecord]], ...] = (
    ("data/micro_feature_store.json", _adapt_micro_feature_store),
    ("data/moat_coverage.json", _adapt_moat_coverage),
    ("data/moat_screen_coverage.json", _adapt_screen_coverage),
    ("data/moat_screen.json", _adapt_moat_screen),
    ("data/orderbook_state_screen.json", _adapt_orderbook_state),
    ("reports/moat_campaign.json", _adapt_moat_campaign),
    ("data/moat_quality.json", _adapt_moat_quality),
    ("data/micro_features.json", _adapt_micro_features),
)


def read_records(root: Path) -> list[ReadRecord]:
    """Every consumption record this box can read, one row per registered artifact."""
    return [fn(_read_json(root / rel), root) for rel, fn in READERS]


#: Tokens that mean a script actually OPENS the tape rather than mentioning it. Used to find
#: readers whose consumption leaves no record -- the population this instrument is blind to, and
#: which must therefore be named rather than silently excluded from the denominator.
_TAPE_OPEN = ("read_partition", "gzip.open", ".glob(", "rglob", "partitions(")

#: ``data/moat`` THE DIRECTORY, not ``data/moat_screen.json`` and not this module's own artifact.
#: A bare substring test matches every sibling artifact name and would report half the desk --
#: including this instrument -- as an unrecorded tape reader.
_TAPE_DIR_REF = re.compile(r"data/moat(?![\w-])")


def tape_opening_scripts(root: Path) -> list[str]:
    """Scripts that reference the ``data/moat`` DIRECTORY and contain a tape-opening call."""
    out: list[str] = []
    sdir = root / "scripts"
    if not sdir.is_dir():
        return out
    for p in sorted(sdir.glob("*.py")):
        try:
            src = p.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _TAPE_DIR_REF.search(src) is not None and any(tok in src for tok in _TAPE_OPEN):
            out.append(f"scripts/{p.name}")
    return out


def unscheduled_readers(root: Path, scripts: Iterable[str]) -> dict[str, Any]:
    """Which tape readers the DR floor actually schedules, and which run only when remembered.

    A reader that is not on the scheduler reads the tape at whatever rate a human remembers to
    start it, and the tape grows every hour regardless -- so utilisation falls monotonically while
    nothing anywhere turns red. ``ops/crontab.manifest`` is the desk's scheduler-as-source (gap
    #58) and is the authority checked here; an unreadable manifest is reported as such rather than
    as "nothing is scheduled", which would accuse every organ at once.
    """
    p = root / "ops/crontab.manifest"
    try:
        text = p.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return {"status": NOT_READABLE_HERE, "manifest": str(p),
                "why": "the scheduler manifest is not readable, so scheduling is UNKNOWN -- "
                       "which is not the same as unscheduled"}
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    body = "\n".join(lines)
    missing = sorted(s for s in scripts if s not in body)
    return {"status": MEASURED, "manifest": "ops/crontab.manifest",
            "unscheduled": missing,
            "note": ("a tape reader absent from the scheduler runs only when a human remembers, "
                     "while the tape grows every hour regardless -- so utilisation falls with "
                     "nothing anywhere turning red")}


# ---------------------------------------------------------------------------- depth levels -----

@dataclass(frozen=True)
class DepthLevelUse:
    """Levels a venue RECORDS against levels any consumer has ever READ."""

    venue: str
    recorder: str
    recorded_levels: int | None
    consumed_levels: int | None
    deepest_consumer: str
    unread_levels: int | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"venue": self.venue, "recorder": self.recorder,
                "recorded_levels": self.recorded_levels, "consumed_levels": self.consumed_levels,
                "deepest_consumer": self.deepest_consumer, "unread_levels": self.unread_levels,
                "status": self.status}


def consumed_depth_levels() -> tuple[int, str]:
    """The deepest book level any consumer on this desk actually reads, and who reads it.

    READ FROM THE IMPLEMENTATIONS, NOT DECLARED HERE. Every reconstruction in ``moat_mine`` takes
    its depth as a ``top_n`` default, and ``orderbook_state`` sums a fixed ``_DEEP_LEVELS``; both
    are introspected so that deepening a consumer automatically shrinks the unread band instead of
    leaving this module asserting a number that stopped being true.
    """
    best, who = int(_DEEP_LEVELS), "libs/research/orderbook_state._DEEP_LEVELS"
    for name, fn in _EXTRACTORS.items():
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            continue
        d = params["top_n"].default if "top_n" in params else None
        if isinstance(d, int) and d > best:
            best, who = d, f"libs/hypmax/moat_mine.{name}(top_n={d})"
    return best, who


def depth_level_use(decls: Sequence[RecorderDecl]) -> list[DepthLevelUse]:
    """Per venue: recorded levels minus the deepest level any consumer reads.

    THIS IS MEASURABLE IN A CHECKOUT, and it is the one slice of the tape whose under-use can be
    proven without the tape: the recorders' request limits and the consumers' depth constants are
    both source. A venue that records 25 levels while the deepest reader sums 20 is paying request
    weight, disk and process supervision for five levels that have never entered a statistic.
    """
    consumed, who = consumed_depth_levels()
    out: list[DepthLevelUse] = []
    for d in decls:
        if d.depth_levels is None:
            out.append(DepthLevelUse(venue=d.venue, recorder=d.script, recorded_levels=None,
                                     consumed_levels=consumed, deepest_consumer=who,
                                     unread_levels=None, status=NOT_READABLE_HERE))
            continue
        out.append(DepthLevelUse(venue=d.venue, recorder=d.script, recorded_levels=d.depth_levels,
                                 consumed_levels=consumed, deepest_consumer=who,
                                 unread_levels=max(0, d.depth_levels - consumed),
                                 status=MEASURED))
    return out


# ------------------------------------------------------------------------------ utilisation ----

def _pct(num: int, den: int) -> float | None:
    """A percentage, or ``None`` when the denominator is not a measurement.

    Zero denominator returns ``None``, never 0.0 and never 100.0: nothing divided by nothing is
    not a utilisation, and both defaults would be a lie in a different direction.
    """
    return None if den <= 0 else round(100.0 * num / den, 4)


@dataclass
class Utilisation:
    """The headline, at every granularity the evidence supports and no finer."""

    status: str
    missing_paths: list[str] = field(default_factory=list)
    symbol_hours_on_disk: int | None = None
    symbol_hours_read: int | None = None
    symbol_hours_read_pct: float | None = None
    symbol_hours_read_pct_upper_bound: float | None = None
    symbol_days_on_disk: int | None = None
    symbol_days_read: int | None = None
    symbol_days_read_pct: float | None = None
    symbols_on_disk: int | None = None
    symbols_read: int | None = None
    symbols_read_pct: float | None = None
    bytes_on_disk: int | None = None
    bytes_in_read_hours: int | None = None
    bytes_read_pct: float | None = None
    bytes_read_pct_upper_bound: float | None = None
    unread_symbols: list[str] = field(default_factory=list)
    unread_ranges: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status, "missing_paths": self.missing_paths,
            "symbol_hours_on_disk": self.symbol_hours_on_disk,
            "symbol_hours_read": self.symbol_hours_read,
            "symbol_hours_read_pct": self.symbol_hours_read_pct,
            "symbol_hours_read_pct_upper_bound": self.symbol_hours_read_pct_upper_bound,
            "symbol_days_on_disk": self.symbol_days_on_disk,
            "symbol_days_read": self.symbol_days_read,
            "symbol_days_read_pct": self.symbol_days_read_pct,
            "symbols_on_disk": self.symbols_on_disk, "symbols_read": self.symbols_read,
            "symbols_read_pct": self.symbols_read_pct,
            "bytes_on_disk": self.bytes_on_disk, "bytes_in_read_hours": self.bytes_in_read_hours,
            "bytes_read_pct": self.bytes_read_pct,
            "bytes_read_pct_upper_bound": self.bytes_read_pct_upper_bound,
            "unread_symbols": self.unread_symbols, "unread_ranges": self.unread_ranges,
            "note": self.note,
        }


def _runs(days: Sequence[str], read: frozenset[str]) -> list[list[str]]:
    """Maximal runs of unread days, in order. Pure over the two inputs so it is testable alone."""
    out: list[list[str]] = []
    run: list[str] = []
    for d in days:
        if d in read:
            if run:
                out.append(run)
            run = []
        else:
            run.append(d)
    if run:
        out.append(run)
    return out


def _unread_ranges(parts: Sequence[Partition],
                   read_days: frozenset[tuple[str, str, str]]) -> list[dict[str, Any]]:
    """Maximal runs of consecutive RECORDED days a stream holds that nothing has ever read.

    Consecutive in the RECORDED day series, not in the calendar: a run interrupted only by a day
    the recorder never wrote is still one contiguous unread slice of tape, and splitting it there
    would fragment the ranked list on the recorder's outages rather than on the reader's.
    """
    by: dict[tuple[str, str], list[Partition]] = {}
    for p in parts:
        by.setdefault((p.venue, p.symbol), []).append(p)
    out: list[dict[str, Any]] = []
    for (venue, symbol), group in sorted(by.items()):
        days = sorted({p.day for p in group})
        read = frozenset(d for d in days if (venue, symbol, d) in read_days)
        for run in _runs(days, read):
            hit = [p for p in group if p.day in set(run)]
            out.append({"venue": venue, "symbol": symbol, "from_day": run[0], "to_day": run[-1],
                        "days": len(run), "symbol_hours": len(hit),
                        "bytes": sum(p.size_bytes for p in hit)})
    out.sort(key=lambda r: (-int(r["symbol_hours"]), -int(r["bytes"]), str(r["venue"]),
                            str(r["symbol"])))
    return out


def utilisation(parts: Sequence[Partition], reads: Sequence[ReadRecord], *,
                moat_root: Path, venues: Sequence[str]) -> Utilisation:
    """THE HEADLINE. Read fractions against what is ON DISK, or an honest refusal to state one.

    THREE STATES, NEVER TWO.
      * ``NOT-READABLE-HERE`` -- no tape on this box. Every figure is ``None`` and the missing
        paths are named. This is NOT 0%: nothing was measured.
      * ``PARTIAL`` -- tape present, but not one consumption record is readable. 0% read and
        "the readers keep no record" are indistinguishable from this evidence, so no percentage is
        published and the absent artifacts are named instead.
      * ``MEASURED`` -- tape and at least one consumption record both present. The percentages are
        real, and 0.0 is then a finding rather than a gap in the instrument.

    THE BRACKET, AND WHY BOTH ENDS ARE PUBLISHED. Only ``micro_feature_store`` records which HOURS
    it consumed; the coverage grids record DAYS. The lower bound counts only hours proven read; the
    upper bound credits every hour of a day some organ touched. The truth is between them, and
    publishing one number would hide which reading it is.
    """
    if not parts:
        return Utilisation(
            status=NOT_READABLE_HERE,
            missing_paths=missing_tape_paths(moat_root, venues),
            note=("the L2 tape is VPS-only and data/ is gitignored, so this is EXPECTED in a "
                  "checkout and a REAL blocker on the box. NOT 0% UTILISED -- utilisation was not "
                  "measured. Run this script on the recording box to obtain the number."))

    hours_disk = {p.symbol_hour for p in parts}
    days_disk = {p.cell for p in parts}
    syms_disk = {(p.venue, p.symbol) for p in parts}
    bytes_by_hour = {p.symbol_hour: p.size_bytes for p in parts}
    total_bytes = sum(p.size_bytes for p in parts)

    live = [r for r in reads if r.status == MEASURED]
    if not live:
        return Utilisation(
            status=PARTIAL,
            missing_paths=[r.artifact for r in reads if r.status != MEASURED],
            symbol_hours_on_disk=len(hours_disk), symbol_days_on_disk=len(days_disk),
            symbols_on_disk=len(syms_disk), bytes_on_disk=total_bytes,
            note=("the tape is here and NOT ONE consumption record is readable. 0% read and "
                  "'the readers keep no record of what they read' produce identical evidence, so "
                  "no percentage is published. Re-run after any moat organ has written its "
                  "artifact; if they have run, the defect is that they do not record their reads."))

    hours_read = {h for r in live for h in r.hours} & hours_disk
    days_read = {d for r in live for d in r.days} & days_disk
    days_read |= {(v, s, d) for v, s, d, _ in hours_read}
    syms_read = {x for r in live for x in r.symbols} & syms_disk
    syms_read |= {(v, s) for v, s, _ in days_read}

    bytes_hours = sum(bytes_by_hour[h] for h in hours_read)
    bytes_days = sum(p.size_bytes for p in parts if p.cell in days_read)
    unread_syms = sorted(f"{v}/{s}" for v, s in (syms_disk - syms_read))

    return Utilisation(
        status=MEASURED,
        symbol_hours_on_disk=len(hours_disk), symbol_hours_read=len(hours_read),
        symbol_hours_read_pct=_pct(len(hours_read), len(hours_disk)),
        symbol_hours_read_pct_upper_bound=_pct(
            sum(1 for p in parts if p.cell in days_read), len(hours_disk)),
        symbol_days_on_disk=len(days_disk), symbol_days_read=len(days_read),
        symbol_days_read_pct=_pct(len(days_read), len(days_disk)),
        symbols_on_disk=len(syms_disk), symbols_read=len(syms_read),
        symbols_read_pct=_pct(len(syms_read), len(syms_disk)),
        bytes_on_disk=total_bytes, bytes_in_read_hours=bytes_hours,
        bytes_read_pct=_pct(bytes_hours, total_bytes),
        bytes_read_pct_upper_bound=_pct(bytes_days, total_bytes),
        unread_symbols=unread_syms,
        unread_ranges=_unread_ranges(parts, frozenset(days_read))[:40],
        note=("lower bound counts only hours PROVEN read (micro_feature_store is the sole "
              "hour-grained record); the upper bound credits every hour of any day some organ "
              "touched. A 0.0 here is a MEASUREMENT, not a missing input."))


# --------------------------------------------------------------------------- hunting yield -----

#: Tokens in a mechanism class's OWN declared datasets that this tape satisfies. The class list is
#: therefore DERIVED from ``mechanism_census.TAXONOMY`` rather than asserted here: this module
#: names no mechanism the census does not, and a taxonomy edit propagates automatically.
_TAPE_DATASET_TOKENS = ("data/moat", "l2 ", "l2 tick", "book snapshot", "aggtrade", "signed flow")


def tape_testable_classes() -> list[dict[str, Any]]:
    """Census classes whose OWN data requirement is satisfied by the recorded tape."""
    out: list[dict[str, Any]] = []
    for c in TAXONOMY:
        for ds in c.data.datasets:
            low = ds.lower()
            hit = [t for t in _TAPE_DATASET_TOKENS if t in low]
            if hit:
                out.append({"class_id": c.id, "name": c.name, "payer": c.payer,
                            "plausibility": c.plausibility, "orthogonality": c.orthogonality,
                            "satisfied_by": ds, "matched_tokens": hit})
                break
    return out


def hunting_yield(root: Path) -> dict[str, Any]:
    """How many distinct hypotheses have EVER been screened on this tape, and to what effect.

    THE ANSWER IS A MEASURED NEGATIVE AND IS REPORTED AS ONE. The two moat campaign "survivors"
    landed at OOS Sharpe 0.103 and 0.098 -- the identical 0.100 ceiling that 129 textbook
    mechanisms on public daily bars reached on the same day. An in-sample annualised Sharpe of 97
    delivering 0.10 out of sample is a 99.9% collapse, the classic one-minute-bar overfit
    signature. Nothing here is a lead; what it establishes is that the pipeline runs end to end and
    produces gate-level verdicts on real depth. Anyone reading this row as promising has read it
    backwards.
    """
    classes = tape_testable_classes()
    hyps: set[str] = set()
    by_class: dict[str, set[str]] = {}
    best_oos: float | None = None
    sources: list[dict[str, Any]] = []

    camp = _read_json(root / "reports/moat_campaign.json")
    rows = camp.get("rows") if isinstance(camp, dict) else None
    if isinstance(rows, list) and rows:
        for r in rows:
            if not isinstance(r, dict):
                continue
            name = str(r.get("name") or "")
            construction = name.split(":")[0]
            if construction:
                hyps.add(construction)
                by_class.setdefault(_class_of(construction), set()).add(construction)
            v = r.get("oos_sharpe")
            if isinstance(v, int | float):
                best_oos = float(v) if best_oos is None else max(best_oos, float(v))
        sources.append({"artifact": "reports/moat_campaign.json", "status": MEASURED,
                        "rows": len(rows)})
    else:
        why = (f"artifact status {camp.get('status')!r}: {camp.get('blocker')}"
               if isinstance(camp, dict) else f"absent: {root / 'reports/moat_campaign.json'}")
        sources.append({"artifact": "reports/moat_campaign.json",
                        "status": NOT_READABLE_HERE, "why": why})

    scr = _read_json(root / "data/moat_screen.json")
    mechs = scr.get("mechanisms") if isinstance(scr, dict) else None
    if isinstance(mechs, list) and mechs:
        for m in mechs:
            hyps.add(str(m))
            by_class.setdefault(_class_of(str(m)), set()).add(str(m))
        sources.append({"artifact": "data/moat_screen.json", "status": MEASURED,
                        "mechanisms": len(mechs)})
    else:
        sources.append({"artifact": "data/moat_screen.json", "status": NOT_READABLE_HERE,
                        "why": f"absent or empty: {root / 'data/moat_screen.json'}"})

    obs = _read_json(root / "data/orderbook_state_screen.json")
    if isinstance(obs, dict) and str(obs.get("status")) == "SCREENED":
        for r in obs.get("rows") or []:
            if isinstance(r, dict) and r.get("construction"):
                c = str(r["construction"])
                hyps.add(c)
                by_class.setdefault(_class_of(c), set()).add(c)
        sources.append({"artifact": "data/orderbook_state_screen.json", "status": MEASURED})
    else:
        sources.append({"artifact": "data/orderbook_state_screen.json",
                        "status": NOT_READABLE_HERE,
                        "why": "the screen reported NOT-READABLE-HERE or is absent"})

    measurable = any(s["status"] == MEASURED for s in sources)
    return {
        "status": MEASURED if measurable else NOT_READABLE_HERE,
        "tape_testable_classes": classes,
        "n_tape_testable_classes": len(classes),
        "hypotheses_screened_on_tape": (sorted(hyps) if measurable else None),
        "n_hypotheses": len(hyps) if measurable else None,
        "mechanism_classes_occupied": (
            {k: sorted(v) for k, v in sorted(by_class.items())} if measurable else None),
        "n_mechanism_classes_occupied": len(by_class) if measurable else None,
        "best_oos_sharpe": best_oos,
        "sources": sources,
        "taxonomy": "libs/research/mechanism_census.TAXONOMY (no taxonomy is defined here)",
        "reading": (
            "MEASURED NEGATIVE, NEVER A LEAD. The moat campaign's two screen survivors landed at "
            "OOS Sharpe 0.103 and 0.098 -- the same 0.100 ceiling 129 textbook mechanisms on "
            "public daily bars reached the same day. An in-sample annualised Sharpe of 97 that "
            "delivers 0.10 out of sample is a 99.9% collapse, the one-minute-bar overfit "
            "signature. What the run establishes is that the pipeline works, not that the tape "
            "pays. See documented_reference for the citation; those rows are VPS state and are "
            "NOT reconstructed here."),
    }


def _class_of(construction: str) -> str:
    """Map a construction name onto a census class id, never onto an invented one.

    Falls back to ``orderbook_microstructure_state`` ONLY when the census itself cannot place the
    name, because every construction reaching this function was computed off recorded L2 depth --
    and a silent ``unclassified`` bucket would understate class occupancy, which is the number the
    diversity reading depends on. The fallback is a census class id, so the taxonomy stays the sole
    authority on what a mechanism class is.
    """
    cid, _ = classify(construction.replace("_", " "), construction=construction)
    if cid is not None and cid in CLASS_BY_ID:
        return cid
    return "orderbook_microstructure_state"


# ------------------------------------------------------------------------ documented evidence --

#: THE ONE DATED IN-REPO OBSERVATION OF THE LIVE TAPE, with the literal tokens that must still be
#: present in it. If the source text changes, the citation is reported as ROTTED and the numbers
#: are NOT used -- a citation that cannot be re-checked is a rumour with a file name.
_DOC_PATH = "docs/research/VPS_STATE_20260805.md"
_DOC_TOKENS: tuple[tuple[str, str], ...] = (
    ("28,361 files", "tape file count"),
    ("10 GB", "tape size"),
    ("n_obs 1,065", "scored observations in the 2026-08-02 campaign"),
    ("48 candidates", "campaign width"),
    ("0.103", "best survivor OOS Sharpe"),
    ("0.098", "second survivor OOS Sharpe"),
)


def documented_reference(root: Path) -> dict[str, Any]:
    """The box's own numbers, carried as DOCUMENTED-NOT-MEASURED with their arithmetic shown.

    WHY THE ARITHMETIC IS HERE AND WHY IT IS FENCED. 1,065 one-minute bars is 17.75 hours of
    ALIGNED sample per candidate column. The tape holds 28,361 hourly partitions. Even crediting
    the campaign's full 12-symbol cap, the scored window is at most 12 x 17.75 = 213 symbol-hours,
    i.e. 0.75% of the tape -- and that is an UPPER BOUND on what was scored, not a measurement of
    what was read. It sits in its own block, tagged, cited and token-checked, and never touches a
    measured field. The desk should find the number uncomfortable; it should not be able to mistake
    it for something this box measured.
    """
    p = root / _DOC_PATH
    try:
        text = p.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return {"status": NOT_READABLE_HERE, "source": _DOC_PATH,
                "why": f"citation source absent: {p}"}
    missing = [f"{tok} ({what})" for tok, what in _DOC_TOKENS if tok not in text]
    if missing:
        return {"status": "DOCUMENTED-SOURCE-CHANGED", "source": _DOC_PATH,
                "missing_tokens": missing,
                "why": ("the cited text no longer carries these tokens, so the numbers below are "
                        "NOT used. Re-read the source and update the citation rather than "
                        "trusting a stale quote.")}
    bars, bar_min = 1065, 1.0
    files, gib = 28_361, 10.0
    max_syms = 12
    hours_per_column = bars * bar_min / 60.0
    upper_hours = hours_per_column * max_syms
    return {
        "status": DOCUMENTED,
        "source": f"{_DOC_PATH} (read live off the box 2026-08-05)",
        "tape_files": files,
        "tape_size_gb": gib,
        "campaign": {"date": "2026-08-02", "candidates": 48, "n_obs": bars, "n_survivors": 2,
                     "survivor_oos_sharpe": [0.103, 0.098],
                     "third_candidate_oos": 0.068,
                     "public_daily_bar_ceiling": 0.100},
        "scored_hours_per_candidate_column": round(hours_per_column, 2),
        "scored_symbol_hours_upper_bound": round(upper_hours, 1),
        "scored_fraction_of_tape_pct_upper_bound": round(100.0 * upper_hours / files, 3),
        "arithmetic": (f"{bars} one-minute bars = {hours_per_column:.2f} h per candidate column; "
                       f"x{max_syms} symbols (the campaign's --max-symbols cap) = "
                       f"{upper_hours:.1f} symbol-hours against {files:,} hourly partitions"),
        "reading": (f"the deepest read this desk has ever taken of its only un-replicable asset "
                    f"covered at most {100.0 * upper_hours / files:.2f}% of it, and returned an "
                    f"OOS Sharpe at the public-data noise ceiling. Both halves matter: the tape "
                    f"is barely read, AND the part that was read paid nothing."),
        "caveat": ("DOCUMENTED, NOT MEASURED. These are numbers from a dated observation of the "
                   "VPS, carried with their citation and re-checked against the source text on "
                   "every run. They are never merged into a measured field, and this block is "
                   "absent from every percentage above."),
    }


# ------------------------------------------------------------------------------ next actions ---

#: Why the trade half of the tape is its own action rather than a footnote: the recorders write
#: aggressor-signed prints into the SAME partitions as the depth snapshots, and the census's
#: ``informed_order_flow`` class names exactly that as its required dataset -- so a second
#: mechanism class is already recorded, already paid for, and screened only incidentally.
_FLOW_NOTE = (
    "the recorders write aggressor-signed prints into the same partitions as the depth "
    "snapshots, and informed_order_flow's declared dataset is trade-level signed flow. A second "
    "census class is therefore already on disk, already paid for, and has only ever been screened "
    "incidentally as a by-product of the depth work"
)


@dataclass(frozen=True)
class NextAction:
    """One ranked experiment: the biggest unread slice and the class it could test."""

    rank: int
    action: str
    slice_id: str
    unread_symbol_hours: int | None
    unread_bytes: int | None
    mechanism_class: str
    why: str
    command: str

    def to_dict(self) -> dict[str, Any]:
        return {"rank": self.rank, "action": self.action, "slice": self.slice_id,
                "unread_symbol_hours": self.unread_symbol_hours,
                "unread_bytes": self.unread_bytes, "mechanism_class": self.mechanism_class,
                "why": self.why, "command": self.command}


def rank_next_actions(util: Utilisation, depth: Sequence[DepthLevelUse],
                      holes: Mapping[str, Sequence[str]], *, limit: int = 12) -> list[NextAction]:
    """THE DELIVERABLE -- what to point at tomorrow, biggest unread slice first.

    RANKED BY UNREAD SYMBOL-HOURS, not by bytes and not by recency. Hours are the unit the tape
    accrues in and the unit a screen's power is denominated in; bytes reward whichever venue writes
    the fattest snapshots, and recency rewards the slice a newest-first scheduler would have read
    anyway -- which is the exact bias ``screen_moat``'s hole-first scheduler was written to remove.

    The class attached to each row is a census class id, never a label invented here, so a row can
    be handed to ``mechanism_census`` without a translation layer.
    """
    out: list[NextAction] = []
    primary = "orderbook_microstructure_state"
    for row in util.unread_ranges:
        out.append(NextAction(
            rank=0,
            action="screen this unread slice",
            slice_id=f"{row['venue']}/{row['symbol']} {row['from_day']}..{row['to_day']}",
            unread_symbol_hours=int(row["symbol_hours"]),
            unread_bytes=int(row["bytes"]),
            mechanism_class=primary,
            why=("recorded and never read by any organ that records what it reads -- the highest "
                 "unread hour count on the tape"),
            command=(f"python scripts/screen_orderbook_state.py --files {int(row['symbol_hours'])}"
                     " # then scripts/screen_moat.py for the reconstruction set"),
        ))
    for sym in util.unread_symbols:
        if any(a.slice_id.startswith(sym) for a in out):
            continue
        out.append(NextAction(
            rank=0, action="screen a symbol nothing has ever read", slice_id=sym,
            unread_symbol_hours=None, unread_bytes=None, mechanism_class=primary,
            why="recorded continuously and absent from every consumption record",
            command="python scripts/screen_moat.py --files 24",
        ))
    for d in depth:
        if d.unread_levels is not None and d.unread_levels > 0:
            out.append(NextAction(
                rank=0,
                action=f"read the {d.unread_levels} deepest book levels on {d.venue}",
                slice_id=f"{d.venue} levels {(d.consumed_levels or 0) + 1}-{d.recorded_levels}",
                unread_symbol_hours=None, unread_bytes=None,
                mechanism_class=primary,
                why=(f"{d.recorder} requests {d.recorded_levels} levels and the deepest consumer "
                     f"({d.deepest_consumer}) reads {d.consumed_levels}. Those levels cost request "
                     "weight, disk and supervision and have never entered a statistic -- and the "
                     "shape BEHIND the touch is the part no public feed publishes"),
                command="raise the depth constant in the consumer, then re-screen",
            ))
    for sym in holes.get("wanted_never_recorded", ()):
        out.append(NextAction(
            rank=0, action="START RECORDING -- this hole grows every hour and never backfills",
            slice_id=sym, unread_symbol_hours=None, unread_bytes=None,
            mechanism_class=primary,
            why=("the desk trades or screens this name and no recorder writes it. Unlike every "
                 "other row here, waiting makes this strictly worse: an unrecorded hour cannot be "
                 "bought back at any price"),
            command="add to _CORE in scripts/run_recorder{,_spot}.py within the weight budget",
        ))
    flow = "informed_order_flow"
    if flow in CLASS_BY_ID:
        out.append(NextAction(
            rank=0,
            action="screen the tape's TRADE half against its second census class",
            slice_id="data/moat/**/*.jsonl.gz k=t|trades records",
            unread_symbol_hours=None, unread_bytes=None, mechanism_class=flow,
            why=_FLOW_NOTE,
            command="python scripts/screen_moat.py  # aggressor-signed flow constructions",
        ))
    out.sort(key=lambda a: (-(a.unread_symbol_hours or 0), -(a.unread_bytes or 0), a.slice_id))
    return [NextAction(rank=i + 1, action=a.action, slice_id=a.slice_id,
                       unread_symbol_hours=a.unread_symbol_hours, unread_bytes=a.unread_bytes,
                       mechanism_class=a.mechanism_class, why=a.why, command=a.command)
            for i, a in enumerate(out[:limit])]


# ---------------------------------------------------------------------------------- report -----

def build_report(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """The whole instrument, as one artifact. Every section carries its own status."""
    moat_root = root / "data/moat"
    decls = recorder_declarations(root)
    venues = [d.venue for d in decls]
    parts = inventory(moat_root)
    reads = read_records(root)
    util = utilisation(parts, reads, moat_root=moat_root, venues=venues)
    cont = continuity(parts, now=now)
    depth = depth_level_use(decls)
    sources = universe_sources(root)

    recorded_bases = {_base(p.symbol) for p in parts}
    declared_bases = {_base(s) for d in decls for s in d.symbols}
    wanted: dict[str, set[str]] = {}
    for s in sources:
        if s.kind in ("traded", "screened") and s.status == MEASURED:
            wanted[s.name] = {_base(x) for x in s.symbols}
    wanted_all: set[str] = set()
    for names in wanted.values():
        wanted_all |= names

    # BOTH DIRECTIONS, ALWAYS. Recorded-vs-declared is measurable in a checkout (both sides are
    # source or artifact); recorded-vs-on-disk needs the tape and says NOT-READABLE-HERE without it.
    holes: dict[str, list[str]] = {
        "wanted_never_declared": sorted(wanted_all - declared_bases),
        "wanted_never_recorded": (sorted(wanted_all - recorded_bases) if parts else []),
        "declared_never_recorded": (sorted(declared_bases - recorded_bases) if parts else []),
        "recorded_never_wanted": (sorted(recorded_bases - wanted_all) if parts and wanted else []),
        "recorded_never_read": list(util.unread_symbols),
    }

    opening = tape_opening_scripts(root)
    registered = {r.script for r in reads}
    invisible = [s for s in opening if s not in registered
                 and not s.startswith("scripts/run_recorder")]

    total_bytes, total_files = tape_bytes(moat_root)
    largest = max((c for c in cont if c.largest_gap_hours is not None),
                  default=None, key=lambda c: c.largest_gap_hours or 0)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": (now or datetime.now(tz=UTC)).isoformat(),
        "module": "libs/research/moat_utilisation.py",
        "script": "scripts/run_moat_utilisation.py",
        "status": util.status,
        "question": ("of the bytes, symbol-hours, symbols, venues and depth levels recorded, what "
                     "fraction has EVER reached a screen, a campaign or a feature extraction?"),
        "tape": {
            "root": str(moat_root),
            "status": MEASURED if parts else NOT_READABLE_HERE,
            "missing_paths": [] if parts else missing_tape_paths(moat_root, venues),
            "partitions": len(parts) or None,
            "bytes_partitions": sum(p.size_bytes for p in parts) or None,
            "bytes_all_files": total_bytes or None,
            "files_all": total_files or None,
            "venues": sorted({p.venue for p in parts}) or None,
            "symbols": len({(p.venue, p.symbol) for p in parts}) or None,
            "why_it_is_different": (
                "the only dataset on this desk that cannot be bought, re-fetched or replicated. "
                "It accrues ONLY in calendar time, so an unrecorded hour is unbuyable at any "
                "price and an unread hour is a cost already paid for no return."),
        },
        "coverage_of_recording": {
            "status": MEASURED if parts else PARTIAL,
            "recorders": [d.to_dict() for d in decls],
            "universe_sources": [s.to_dict() for s in sources],
            "holes": holes,
            "note": ("BOTH DIRECTIONS. A wanted-but-unrecorded name is a hole that widens every "
                     "hour and never backfills; a recorded-but-unread name is spend with no "
                     "return. Opposite defects, opposite fixes. Symbol names are compared on the "
                     "BASE asset so BTCUSDT and BTC are one instrument, not a manufactured hole."),
            "measurable_without_the_tape": (
                "wanted_never_declared -- both sides are source/artifact, so this row is real in "
                "a checkout. The rows that need the tape are empty and the tape status says why."),
        },
        "continuity": {
            "status": MEASURED if cont else NOT_READABLE_HERE,
            "unit": "one hourly partition per (venue, symbol) -- the tape's own rotation",
            "streams": [c.to_dict() for c in cont][:200],
            "largest_gap": largest.to_dict() if largest is not None else None,
            "note": ("gaps, not endpoints. first..last is not coverage: today's data-registry "
                     "pass measured exchange_announcements claiming 2,356 elapsed days while "
                     "holding 38, because one 2,318-day hole sat between the extremes. "
                     "hours_since_last is reported alongside, because a recorder that died an "
                     "hour ago has no internal gap and a perfect coverage_pct."),
        },
        "utilisation": {
            **util.to_dict(),
            "readers": [r.to_dict() for r in reads],
            # THE POPULATION THIS INSTRUMENT IS BLIND TO, NAMED RATHER THAN EXCLUDED. These
            # scripts open the tape directory and write no record of which partitions they took,
            # so their consumption cannot be attributed to any symbol-hour in either direction.
            # Not an accusation -- a backup pass or a file COUNT is not a research read -- but the
            # instrument cannot tell those apart from a real read, and neither can the desk.
            "tape_openers_without_consumption_record": sorted(invisible),
            "grain_ladder": [GRAIN_HOUR, GRAIN_DAY, GRAIN_SYMBOL, GRAIN_COUNTS],
            "depth_levels": [d.to_dict() for d in depth],
            "documented_reference": documented_reference(root),
            "measurement_defect": (
                "only data/micro_feature_store.json records WHICH hours were consumed. The "
                "coverage grids record days; screen_orderbook_state records counts alone. So the "
                "exact figure is bracketed rather than pinned, and the fix is one line per organ: "
                "write the cell ids you read."),
        },
        "hunting_yield": hunting_yield(root),
        "next_actions": [a.to_dict() for a in rank_next_actions(util, depth, holes)],
        "authority": ("NONE -- measurement only. This module promotes nothing, blocks nothing, "
                      "sizes nothing and changes no gate, threshold or verdict."),
    }
