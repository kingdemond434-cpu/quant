"""DATA ASSET REGISTRY -- one measured row per dataset (EXECUTION_QUEUE.md RANK 4).

WHY THIS EXISTS: GAP_REGISTER row #77. The desk's previous data inventory was hand-written, and it
failed in BOTH directions at once, which is why "just keep it updated" was never the fix:

  * OVERSTATED. It reported ROW COUNTS as if they were SPANS. ``liquidations.parquet`` read as
    "33,867 rows" -- it is **17 days / 15 symbols**. ``hyperliquid_funding`` and ``crypto_metrics``
    read as large; both are **28 days**. A "14k+ events" framing invites monthly-horizon work the
    span cannot support, and it did: a BIS Table-7 replication was started and had to be downgraded
    before it became a 17-day overfit.
  * UNDERSTATED. ``data/lake/bronze/crypto/<SYM>/D1/*.parquet`` -- **267 symbols, daily, from
    2019-09-08**, funding + basis + taker_buy_frac, all non-null -- was **absent entirely**, and it
    is the desk's best panel (wider and longer than the BIS paper's own).

So the map hid which mechanisms were blocked AND which were unblocked, and research organs were
choosing what to test off it. The binding constraint on the whole forgotten-literature ground turned
out to be HISTORY LENGTH -- a conclusion only reachable once real spans were measured.

THREE DESIGN CONSEQUENCES, each aimed at one of those failures:

1. SPAN IS MEASURED, NEVER COUNTED. ``measure_span`` opens the data and reads the min/max of its
   real date column. ``rows`` is still reported but as a separate field that cannot be mistaken for
   duration. A span this cannot measure is ``None`` with a status saying why -- never 0, never a
   guess. An honest hole is navigable; a confident wrong number is not.

2. DISCOVERY IS DERIVED, NOT LISTED. Assets are found by scanning the paths the desk's own
   collectors write, plus a recursive sweep of the lake that follows partitioned
   ``<axis>/<SYM>/<TF>/`` trees. That is precisely what a flat hand-list missed: the best panel was
   invisible because it is 267 per-symbol directories rather than one file. A registry that can be
   out of date the moment somebody adds a collector rebuilds the original defect.

3. MOAT AND RESEARCH VALUE ARE SEPARATE SCORES. Conflating them mis-ranks in both directions, and
   the desk's own doctrine already draws the line: ``data/moat`` order-book snapshots are "the only
   PROPRIETARY dataset the desk owns: nobody else has these snapshots at these timestamps.
   Everything else it researches (GitHub, TVL, on-chain, social) is available to anyone"
   (``scripts/moat_audit.py``:9-11). So:

     * ``data/cot_zcache.parquet`` -- CFTC COT, 26 YEARS, 11 assets -- has ZERO moat (anyone can
       re-download all of it) and very HIGH research value. Scoring it as a moat would be a lie;
       dismissing it for having no moat would waste the longest panel on the desk. Row #77 also
       notes nothing reads it, which is why ``consumers`` is a field.
     * Perishable public feeds (funding, OI, long/short) DO earn moat: the venue serves only recent
       history, so the archive exists only because the desk was recording. Being early is the moat,
       not exclusivity.

FOURTH CONSEQUENCE, added 2026-08-05: A SPAN IS NOT EVIDENCE UNTIL ITS HOLES ARE SUBTRACTED.
``t = SR * sqrt(years)`` is the only lever ``docs/research/gate_power_audit.md`` measured as moving
power at all, and ``data/type2_cost.json`` records 119 of 228 negatives UNDERPOWERED -- so the
number an organ reads off this registry when it chooses what to test deeply is a number that
directly sizes a t-stat. Reporting ``first..last`` alone repeats row #77's overstatement in a new
place: the desk's own BTCUSDT daily cache runs 2020-12-01..2026-07-31 (2069 elapsed days) but is
MISSING 2025-10 entirely -- 2038 observed days. Quoting 5.66 years there is a 1.6 % overstatement of
sqrt-t on one series and a much larger one on any feed whose recorder died for a season. So every
measured span now also carries ``observed_days``, the gap runs that separate them, and
``evidence_years`` -- observed days, not elapsed days -- which is the term a power calculation may
use. For a PANEL the same trap has a second shape: 25 symbols whose union spans 2069 days is not a
25-symbol 2069-day panel if 4 of them start in 2023, so ``balanced_first/last/days`` report the
window EVERY partition actually covers.

FIFTH: NOT-READABLE-HERE IS A MEASUREMENT, WITH AN ADDRESS. This checkout is not the collecting box.
The moat tape, the recorder output and most declared collector paths live only on the VPS, and an
asset that cannot be opened here is recorded ``readable_here=False`` with ``missing_path`` naming
the EXACT path that was absent -- never 0, never a guess, and never a span quietly omitted. The
same ``scripts/build_data_registry.py`` run on the VPS completes exactly those rows, which is why
the script bootstraps its own ``sys.path`` and holds no repo-root assumption.

Pure stdlib + optional pandas (parquet) / numpy (npz). Import from ``libs.research.data_registry``;
the CLI is ``scripts/build_data_registry.py``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field, replace
from itertools import pairwise
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
#: this module, excluded from its own consumer grep -- declaring a path is not reading the data
_SELF = "libs/research/data_registry.py"

#: Column names that carry a row's date, most-specific first. A dataset whose date lives under a
#: name absent here is reported ``no-date-column`` rather than silently spanless -- the whole point
#: is that an unmeasured span is visible.
#:
#: The tail of this tuple was added 2026-08-05 after four assets that ARE readable on this box read
#: ``no-date-column`` and therefore counted as unmeasured: ``drill_log``/``copytrading_panel`` key
#: their timestamp ``at``, ``exchange_announcements`` uses ``published_at``, ``model_upgrade_log``
#: uses ``generated``. "The desk has no span for it" and "the desk did not look under the right
#: key" are different findings and only one of them is about the data. ``at`` is LAST because it is
#: the least specific: a record carrying both ``at`` and ``published_at`` must be read on the
#: latter.
_DATE_COLS = ("date", "day", "ts", "timestamp", "time", "open_time", "dt", "datetime",
              "published_at", "first_seen", "generated", "created_at", "recorded_at",
              "as_of", "run_at", "at")

#: Array names inside an ``.npz`` cache that carry the observation clock, most-specific first.
_NPZ_TIME_KEYS = ("open_time", "time", "ts", "timestamp", "date", "funding_time")

#: Where partitioned trees live. Depth-2 under the axis dir is ``<SYM>/<TF>/`` (the shape that was
#: invisible to the flat inventory); depth-1 is ``<SYM>/``.
_LAKE = "data/lake/bronze"

#: Flat directories of ``<SYM>-<INTERVAL>-<START>-<END>.npz`` caches. Same row-#77 shape as the
#: lake -- a panel invisible to a flat scan -- but partitioned by FILENAME rather than by
#: directory, which is why the lake sweep alone never saw it. ``data/binance_vision`` is the
#: desk's longest measurable panel on this checkout and was absent from its own map entirely.
_NPZ_CACHES = ("data/binance_vision",)

#: Reported instead of a span when the declared path is not on this box. The house spelling
#: (``libs/execution/economics.py``:51, ``libs/research/mechanism_census.py``:166) so an operator
#: greps one token across every artifact that has to admit the same thing.
NOT_READABLE_HERE = "NOT-READABLE-HERE"

#: Days per year used to turn a day count into the ``sqrt(years)`` term of a t-stat. Julian, to
#: match libs/validation's convention rather than inventing a second calendar here.
DAYS_PER_YEAR = 365.25

#: How hard is this to obtain if the desk lost it today? This decides MOAT, not size.
REPL_REFETCHABLE = "public-refetchable"    #: anyone can re-download the full history -> no moat
REPL_PERISHABLE = "public-perishable"      #: public API, recent-only -> the archive IS the moat
REPL_PROPRIETARY = "proprietary-recorded"  #: our own snapshots at our own timestamps -> max moat

#: Feeds whose venue serves only a short recent window, so history cannot be re-acquired. Matched
#: against the asset id. Being early is the moat.
_PERISHABLE = ("funding", "oi_ls", "oi_", "long_short", "liquidation", "premium", "breadth",
               "deribit", "surface", "taker", "defi_lending", "stablecoin", "tail_")

#: Recorded-by-us datasets. Nobody else holds these timestamps.
_PROPRIETARY = ("moat", "orderbook", "book_snapshot", "venue_truth")


@dataclass(frozen=True)
class AssetSpan:
    """A dataset's real time extent. ``None`` fields mean UNMEASURED, and ``status`` says why.

    The first four fields are the original contract and keep their positions -- callers construct
    this positionally. Everything after them answers the question ``first..last`` cannot: how much
    of that window is actually OBSERVED. ``days`` is elapsed calendar time; ``observed_days`` is
    days carrying at least one row; the difference is ``gap_days``, broken out into the runs that
    produced it. ``evidence_years`` is the honest input to ``t = SR*sqrt(years)`` -- a 5-year span
    with a 2-year hole is 3 years of evidence and must never be quoted as 5.
    """

    first: str | None = None
    last: str | None = None
    days: int | None = None
    status: str = "unmeasured"
    #: elapsed years, first..last inclusive. Overstates evidence whenever gap_days > 0.
    years: float | None = None
    #: distinct calendar days carrying >=1 observation. None = the day set was sampled, not counted.
    observed_days: int | None = None
    gap_days: int | None = None
    n_gaps: int | None = None
    largest_gap_days: int | None = None
    largest_gap_from: str | None = None      #: first missing day of the largest run
    largest_gap_to: str | None = None        #: last missing day of the largest run
    #: observed_days in years -- the term a power calculation may use. NEVER `years` when gapped.
    evidence_years: float | None = None
    #: PANEL ONLY: the window every partition covers. A union span flatters a ragged panel.
    balanced_first: str | None = None
    balanced_last: str | None = None
    balanced_days: int | None = None
    #: False when the declared path could not be opened on this box; missing_path names which.
    readable_here: bool = True
    missing_path: str | None = None

    @property
    def measured(self) -> bool:
        return self.status == "measured"

    @property
    def gapped(self) -> bool:
        """True only when holes were MEASURED and found. Unmeasured gaps are not 'no gaps'."""
        return self.gap_days is not None and self.gap_days > 0


@dataclass(frozen=True)
class DataQuality:
    """DQS and its components, measured from the data. ``None`` means UNMEASURED, never "fine".

    The three components are the ones moat_audit already found matter on this desk's own data
    (``scripts/moat_audit.py``:14-19): a feed can be present and still be worthless because it has
    HOLES (the recorder died and nobody noticed), because it is STALE (the recorder echoing its last
    value rather than reading), or because it is full of NULLs. A row count catches none of those --
    which is the same family of error as reporting row counts as spans.
    """

    completeness: float | None = None   #: observed days / span days -- 1.0 means no missing days
    stale_frac: float | None = None     #: fraction of consecutive-identical rows (recorder echo)
    null_frac: float | None = None      #: fraction of null cells
    dqs: float | None = None            #: 0..100 composite; None when it could not be measured

    @property
    def measured(self) -> bool:
        return self.dqs is not None


@dataclass
class DataAsset:
    """One row of the registry. Every numeric field is measured or explicitly absent."""

    id: str
    path: str
    kind: str = "flat"                       #: "flat" | "partitioned"
    collector: str | None = None             #: the script that WRITES it
    consumers: list[str] = field(default_factory=list)   #: scripts that READ it
    dependencies: list[str] = field(default_factory=list)  #: assets its collector READS to build it
    span: AssetSpan = field(default_factory=AssetSpan)
    quality: DataQuality = field(default_factory=DataQuality)
    rows: int | None = None                  #: reported SEPARATELY from span, never as duration
    breadth: int | None = None               #: distinct symbols / partitions
    bytes: int | None = None
    cadence_h: float | None = None           #: from ops/crontab.manifest, None = unscheduled
    replication: str = REPL_REFETCHABLE
    moat_score: float = 0.0
    research_value: float = 0.0
    #: ALPHA CONTRIBUTION is deliberately None, not 0.0, while the desk holds 0 validated alphas.
    #: A zero would read as "measured and worthless"; None reads as "nothing has been attributed
    #: yet", which is the true state and the difference organs must not have to guess at.
    alpha_contribution: float | None = None
    maintenance_runs_per_day: float | None = None   #: scheduled runs/day -- the real recurring cost
    needs_credentials: bool = False          #: a feed that can silently die on an expired key
    last_validated: str | None = None        #: ISO date the asset was last measured on disk
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["span"] = asdict(self.span)
        d["quality"] = asdict(self.quality)
        return d


# --------------------------------------------------------------------------- span measurement

def _iso_day(v: Any) -> str | None:
    """Best-effort ISO date from a cell that may be a date string or an epoch in s/ms/us/ns."""
    from datetime import UTC, datetime

    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    try:
        n = float(s)
    except ValueError:
        return None
    # epoch unit inferred by magnitude; a 2001-09-09 s-timestamp is 1e9, ms is 1e12, ...
    for div in (1.0, 1e3, 1e6, 1e9):
        t = n / div
        if 3e8 < t < 4e9:                     # ~1979..2096, the only plausible band
            return datetime.fromtimestamp(t, tz=UTC).date().isoformat()
    return None


def _years(days: int | None) -> float | None:
    return None if days is None else round(days / DAYS_PER_YEAR, 3)


@dataclass(frozen=True)
class DayGaps:
    """Internal holes in an observed day set. Every field measured from the days themselves."""

    observed_days: int
    gap_days: int
    n_gaps: int
    largest_gap_days: int
    largest_gap_from: str | None
    largest_gap_to: str | None


def measure_gaps(days: Iterable[str]) -> DayGaps | None:
    """Holes between the first and last observed day. ``None`` when there is nothing to measure.

    A "gap" is a maximal run of consecutive calendar days carrying NO observation, strictly inside
    first..last -- leading/trailing absence is not a hole, it is just where the record begins and
    ends. ``gap_days`` is therefore exactly ``elapsed_days - observed_days``, which is the identity
    that makes the two numbers impossible to quietly disagree.

    This is deliberately cadence-blind. A daily bar series missing a month and an event log that is
    simply quiet for a month produce the same numbers, and that is correct for the use this feeds:
    both give the desk the same number of days on which it holds evidence, which is what sizes t.
    """
    from datetime import date, timedelta

    ds = sorted({d for d in days if d})
    if len(ds) < 2:
        return None
    try:
        parsed = [date.fromisoformat(d) for d in ds]
    except ValueError:
        return None
    runs: list[tuple[int, date, date]] = []
    for prev, cur in pairwise(parsed):
        missing = (cur - prev).days - 1
        if missing > 0:
            runs.append((missing, prev + timedelta(days=1), cur - timedelta(days=1)))
    biggest = max(runs, default=None, key=lambda r: r[0])
    return DayGaps(
        observed_days=len(parsed),
        gap_days=sum(r[0] for r in runs),
        n_gaps=len(runs),
        largest_gap_days=0 if biggest is None else biggest[0],
        largest_gap_from=None if biggest is None else biggest[1].isoformat(),
        largest_gap_to=None if biggest is None else biggest[2].isoformat(),
    )


def _span_from_days(days: Iterable[str], *, complete: bool = True) -> AssetSpan:
    """Span from observed days. ``complete=False`` means the caller only knows the EXTREMES.

    A sampled day set can prove where a record starts and ends but cannot prove there are no holes
    between, so the gap fields stay ``None`` rather than reading as a clean panel. "Not measured"
    and "measured and continuous" are the exact pair this module refuses to conflate.
    """
    from datetime import date

    ds = sorted(d for d in days if d)
    if not ds:
        return AssetSpan(status="no-date-column")
    try:
        n = (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[0])).days + 1
    except ValueError:
        return AssetSpan(first=ds[0], last=ds[-1], status="measured")
    span = AssetSpan(first=ds[0], last=ds[-1], days=n, status="measured", years=_years(n))
    if not complete:
        return span
    g = measure_gaps(ds)
    if g is None:
        return replace(span, observed_days=len(set(ds)), gap_days=0, n_gaps=0,
                       largest_gap_days=0, evidence_years=_years(len(set(ds))))
    return replace(span, observed_days=g.observed_days, gap_days=g.gap_days, n_gaps=g.n_gaps,
                   largest_gap_days=g.largest_gap_days, largest_gap_from=g.largest_gap_from,
                   largest_gap_to=g.largest_gap_to, evidence_years=_years(g.observed_days))


@dataclass(frozen=True)
class Measurement:
    """One file, opened and read. ``days`` is the FULL observed day set, which is what makes the
    internal-gap numbers measurable rather than inferred from the two extremes."""

    span: AssetSpan
    rows: int | None = None
    breadth: int | None = None
    days: frozenset[str] = frozenset()


def _measure_jsonl(p: Path) -> Measurement:
    """Span/rows/breadth/days for newline-delimited JSON, streamed (these grow unbounded)."""
    days: set[str] = set()
    syms: set[str] = set()
    rows = 0
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rows += 1
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                for c in _DATE_COLS:
                    if c in rec:
                        d = _iso_day(rec[c])
                        if d:
                            days.add(d)
                        break
                for k in ("symbol", "sym", "ticker", "pair", "asset"):
                    if rec.get(k):
                        syms.add(str(rec[k]))
                        break
    except OSError:
        return Measurement(AssetSpan(status="unreadable"))
    # the DISTINCT day set, not one entry per row: it is bounded by the span in days, and it is the
    # only thing that can prove a HOLE. Keeping just the extremes cannot, which is why it stopped.
    return Measurement(_span_from_days(days), rows, len(syms) or None, frozenset(days))


def _measure_parquet(p: Path) -> Measurement:
    try:
        import pandas as pd
    except ImportError:
        return Measurement(AssetSpan(status="no-parquet-reader"))
    try:
        df = pd.read_parquet(p)
    except Exception:
        return Measurement(AssetSpan(status="unreadable"))
    rows = len(df)
    col = next((c for c in _DATE_COLS if c in df.columns), None)
    if col is None:
        idx = df.index
        got = getattr(idx, "is_all_dates", False) or "datetime" in str(getattr(idx, "dtype", ""))
        if not got:
            return Measurement(AssetSpan(status="no-date-column"), rows)
        days = {d for d in (_iso_day(v) for v in idx) if d}
    else:
        s = df[col].dropna()
        days = {d for d in (_iso_day(v) for v in s) if d} if len(s) else set()
    breadth = None
    for k in ("symbol", "sym", "ticker", "pair", "asset"):
        if k in df.columns:
            breadth = int(df[k].nunique())
            break
    return Measurement(_span_from_days(days), rows, breadth, frozenset(days))


#: ``date(1970, 1, 1).toordinal()`` -- epoch day zero, for the vectorised day extraction below.
_EPOCH_ORDINAL = 719163


def _days_from_epoch(arr: Any) -> set[str] | None:
    """Distinct UTC days from a numeric epoch array, vectorised. ``None`` if it is not numeric.

    Per-element ``_iso_day`` is fine for a jsonl ledger and wrong for a bar cache: the 5-minute
    binance_vision panel is ~950k timestamps and this runs daily. The unit is inferred from the
    array's own median with the same plausibility band ``_iso_day`` uses, so s/ms/us/ns all land.
    """
    from datetime import date

    import numpy as np

    try:
        t = np.asarray(arr, dtype="float64").ravel()
    except (TypeError, ValueError):
        return None
    t = t[np.isfinite(t)]
    if not t.size:
        return set()
    mid = float(np.median(t))
    div = next((d for d in (1.0, 1e3, 1e6, 1e9) if 3e8 < mid / d < 4e9), None)
    if div is None:
        return None
    ordinals = np.unique(np.floor(t / div / 86400.0)).astype("int64")
    return {date.fromordinal(_EPOCH_ORDINAL + int(o)).isoformat() for o in ordinals}


def _measure_npz(p: Path) -> Measurement:
    """Span/rows/days for a numpy ``.npz`` cache -- the shape ``data/binance_vision`` holds.

    Only the time array is decompressed (``np.load`` on an npz is lazy per-array), so measuring a
    3-year 5-minute cache costs one column rather than the whole file.
    """
    try:
        import numpy as np
    except ImportError:                                    # pragma: no cover - numpy is a hard dep
        return Measurement(AssetSpan(status="no-npz-reader"))
    try:
        with np.load(p, allow_pickle=True) as z:
            key = next((k for k in _NPZ_TIME_KEYS if k in z.files), None)
            if key is None:
                return Measurement(AssetSpan(status="no-date-column"))
            arr = z[key]
            rows = int(arr.shape[0]) if arr.ndim else 0
            fast = _days_from_epoch(arr)
            # a string/object clock (rare, but "date" is a legal key here) falls back to the
            # per-element reader rather than being reported dateless
            days = fast if fast is not None else {d for d in (_iso_day(v) for v in arr.tolist())
                                                  if d}
    except Exception:
        return Measurement(AssetSpan(status="unreadable"))
    return Measurement(_span_from_days(days), rows, None, frozenset(days))


def measure(path: Path) -> Measurement:
    """Open one file and measure it. An absent path is NOT-READABLE-HERE, never a zero-day span."""
    if not path.exists():
        return Measurement(AssetSpan(status="absent", readable_here=False,
                                     missing_path=path.as_posix()))
    if path.suffix == ".parquet":
        return _measure_parquet(path)
    if path.suffix in (".jsonl", ".ndjson"):
        return _measure_jsonl(path)
    if path.suffix == ".npz":
        return _measure_npz(path)
    return Measurement(AssetSpan(status="unsupported-format"))


def measure_span(path: Path) -> tuple[AssetSpan, int | None, int | None]:
    """(span, rows, breadth) for one file -- the original 3-tuple contract, unchanged."""
    m = measure(path)
    return m.span, m.rows, m.breadth


def measure_quality(path: Path, span: AssetSpan, rows: int | None,
                    breadth: int | None) -> DataQuality:
    """DQS from the data itself. Every component is measured or the whole score stays ``None``.

    COMPLETENESS is the one that catches the failure this desk actually has: a recorder dies, the
    file keeps existing, the span still looks long, and only the count of DISTINCT DAYS against the
    span reveals the hole. STALENESS catches the other half -- a recorder that is alive but echoing
    its previous value reads as perfect completeness and carries no information at all.
    """
    if not span.measured or not span.days or path.suffix != ".parquet":
        # jsonl/absent assets: completeness is still computable from span vs rows when both exist,
        # but a partial score invites the same false confidence a partial map does. Report None.
        return DataQuality()
    try:
        import pandas as pd
        df = pd.read_parquet(path)
    except Exception:
        return DataQuality()
    if df.empty:
        return DataQuality()

    col = next((c for c in _DATE_COLS if c in df.columns), None)
    completeness = None
    if col is not None:
        days_seen = df[col].map(_iso_day).dropna().nunique()
        expected = span.days * max(1, breadth or 1) if breadth and breadth > 1 else span.days
        # per-symbol panels have breadth*days expected rows; a flat series has days
        completeness = min(1.0, float(days_seen) / float(span.days)) if span.days else None
        del expected

    num = df.select_dtypes(include="number")
    stale = None
    if len(num) > 1 and not num.empty:
        same = (num.diff().abs().sum(axis=1) == 0)
        stale = float(same.iloc[1:].mean())

    null_frac = float(df.isna().to_numpy().mean()) if df.size else None

    parts = [p for p in (completeness,
                         None if stale is None else 1.0 - stale,
                         None if null_frac is None else 1.0 - null_frac) if p is not None]
    dqs = round(100.0 * sum(parts) / len(parts), 1) if parts else None
    return DataQuality(
        completeness=None if completeness is None else round(completeness, 4),
        stale_frac=None if stale is None else round(stale, 4),
        null_frac=None if null_frac is None else round(null_frac, 4),
        dqs=dqs)


# --------------------------------------------------------------------------- classification

def classify_replication(asset_id: str) -> str:
    low = asset_id.lower()
    if any(t in low for t in _PROPRIETARY):
        return REPL_PROPRIETARY
    if any(t in low for t in _PERISHABLE):
        return REPL_PERISHABLE
    return REPL_REFETCHABLE


def score(asset: DataAsset) -> tuple[float, float]:
    """(moat_score, research_value), 0..100, deliberately driven by DIFFERENT inputs.

    MOAT answers "could a competitor stand this up tomorrow?" -- so it is replication class first,
    and length only matters for a perishable feed (where length IS the head start). A fully
    re-fetchable public panel scores 0 no matter how long it is: 26 years of CFTC COT is not an
    advantage the desk owns, it is an advantage the desk noticed.

    RESEARCH VALUE answers "what can be tested on it?" -- so it is span and breadth, because those
    are what bound the horizons and cross-sections a study can support. This is the axis row #77's
    "binding constraint is HISTORY LENGTH" conclusion lives on, and it is why an unread 26-year
    public panel can be the most valuable row here while scoring zero moat.
    """
    days = asset.span.days or 0
    breadth = asset.breadth or 1

    if asset.replication == REPL_PROPRIETARY:
        moat = 70.0 + min(30.0, days / 365.0 * 30.0)
    elif asset.replication == REPL_PERISHABLE:
        moat = min(60.0, days / 365.0 * 60.0)      # a 28-day funding archive is ~4.6, honestly
    else:
        moat = 0.0

    # span dominates: a 17-day/15-symbol set supports nothing a 267-symbol/6-year set does
    span_pts = min(60.0, days / 365.0 * 20.0)
    breadth_pts = min(30.0, breadth / 10.0)
    unread = 10.0 if (days > 365 and not asset.consumers) else 0.0   # #77's paralysis bonus
    return round(moat, 1), round(min(100.0, span_pts + breadth_pts + unread), 1)


# --------------------------------------------------------------------------- discovery

#: ``"data/foo.jsonl"`` written as one literal.
_SLASH_PATH = re.compile(r'["\']((?:data/)[A-Za-z0-9_./-]+\.(?:parquet|jsonl|ndjson|npz))["\']')
#: ``_ROOT / "data" / "foo.jsonl"`` -- the SAME asset spelled as a Path join. Missing this form is
#: the flat-hand-list defect wearing a different hat: ``data/source_health.jsonl`` is a live ledger
#: that ``scripts/hunt_source_alternatives.py`` reads every day and it was absent from the desk's
#: own map because ``libs/research/source_health.py`` joins its path instead of spelling it.
_JOIN_PATH = re.compile(
    r'["\']data["\']\s*[,/]\s*["\']([A-Za-z0-9_.\-]+\.(?:parquet|jsonl|ndjson|npz))["\']')


_WRITE_CALL = re.compile(r"to_parquet|write_text|open\([^)]*[\"']a|\.write\(|dump|append|savez")
#: ``_CACHE = _ROOT / "data" / "binance_vision"`` -- the constant a module binds a directory to.
_BINDS_DIR = re.compile(r"([A-Za-z_]\w*)\s*=[^=\n]*$")


def _dir_ref_pattern(rel: str) -> re.Pattern[str]:
    """Match a DIRECTORY asset named either as one literal or as a Path join of its segments.

    A partitioned asset is addressed by its directory, never by a filename, so the file-path
    patterns above cannot see its consumers: ``data/binance_vision`` is loaded by three research
    scripts through ``_ROOT / "data" / "binance_vision"`` and the registry reported it as history
    NOBODY READS -- row #77's own paralysis finding, produced by the registry's blind spot rather
    than by the desk's behaviour. A false paralysis alarm spends exactly the attention a real one
    needs.
    """
    segs = rel.split("/")
    join = r"\s*[,/]\s*".join(f'["\']{re.escape(s)}["\']' for s in segs)
    return re.compile(f'["\']{re.escape(rel)}["\']|{join}')


def _writers_and_readers(
    root: Path, dirs: Iterable[str] = (),
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Map data paths -> the script that writes them, and -> scripts that read them.

    Grep-derived on purpose: a hand-kept owner column is the field most likely to be stale, and a
    stale OWNER is how row #77's inventory drifted from reality in the first place. ``dirs`` are
    partitioned assets, addressed by directory rather than by filename.
    """
    writers: dict[str, str] = {}
    readers: dict[str, list[str]] = {}
    dir_pats = [(d, _dir_ref_pattern(d)) for d in sorted(set(dirs))]

    def record(path: str, rel: str, near: str) -> None:
        if _WRITE_CALL.search(near):
            writers.setdefault(path, rel)
        else:
            readers.setdefault(path, [])
            if rel not in readers[path]:
                readers[path].append(rel)

    for py in sorted((root / "scripts").glob("*.py")) + sorted((root / "libs").rglob("*.py")):
        try:
            src = py.read_text("utf-8", errors="replace")
        except OSError:
            continue
        rel = py.relative_to(root).as_posix()
        for m in _SLASH_PATH.finditer(src):
            # a writer names the path near a write call; everything else is a reader
            record(m.group(1), rel, src[max(0, m.start() - 220):m.end() + 220])
        for m in _JOIN_PATH.finditer(src):
            record(f"data/{m.group(1)}", rel, src[max(0, m.start() - 220):m.end() + 220])
        for d, pat in dir_pats:
            if rel == _SELF:                       # naming an asset is not consuming it
                continue
            for m in pat.finditer(src):
                # A DIRECTORY asset defeats the proximity rule above: the fetcher binds the dir at
                # module level and does its np.savez 90 lines later, while a reader passes the same
                # dir as a kwarg next to unrelated dump/append text. The signal that separates them
                # is mkdir -- a consumer never creates the directory it reads from.
                line = src[src.rfind("\n", 0, m.start()) + 1:m.end()]
                bind = _BINDS_DIR.match(line.strip())
                name = bind.group(1) if bind is not None else None
                if name is not None and re.search(rf"\b{re.escape(name)}\.mkdir\(", src):
                    writers.setdefault(d, rel)
                else:
                    readers.setdefault(d, [])
                    if rel not in readers[d]:
                        readers[d].append(rel)
    return writers, readers


def _dependencies_of(collector: str | None, own: str,
                     readers: Mapping[str, list[str]]) -> list[str]:
    """Assets this one is DERIVED from: paths its own collector also reads.

    Lineage matters for a reason row #77 makes concrete: a derived asset can never be longer or
    cleaner than its source, so a study sized off the derived span is really sized off the source's.
    """
    if not collector:
        return []
    return sorted({Path(src).stem for src, rdrs in readers.items()
                   if collector in rdrs and src != own})


def _needs_credentials(root: Path, collector: str | None) -> bool:
    """Does the collector read a secret? Those are the feeds that die silently on key expiry."""
    if not collector:
        return False
    try:
        src = (root / collector).read_text("utf-8", errors="replace")
    except OSError:
        return False
    return "data/secrets" in src or "API_KEY" in src or "api_key" in src


def _mtime_day(p: Path) -> str | None:
    from datetime import UTC, datetime
    try:
        return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC).date().isoformat()
    except OSError:
        return None


def _cadence_hours(root: Path) -> dict[str, float]:
    """script -> hours between runs, parsed from ops/crontab.manifest."""
    mf = root / "ops/crontab.manifest"
    if not mf.exists():
        return {}
    out: dict[str, float] = {}
    for line in mf.read_text("utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(("SYSTEMD", "QUANT_ROOT")):
            continue
        parts = s.split(None, 5)
        if len(parts) < 6:
            continue
        minute, hour = parts[0], parts[1]
        every = 24.0
        if minute.startswith("*/"):
            with_ = minute[2:]
            every = float(with_) / 60.0 if with_.isdigit() else 1.0
        elif hour.startswith("*/") and hour[2:].isdigit():
            every = float(hour[2:])
        elif hour == "*":
            every = 1.0
        for m in re.finditer(r"(scripts/[A-Za-z0-9_./-]+\.py)", parts[5]):
            out[m.group(1)] = min(every, out.get(m.group(1), 1e9))
    return out


@dataclass(frozen=True)
class _Panel:
    """A dataset that is many files. ``partitions`` is the exact partition map, never a sample."""

    id: str
    rel: str                              #: repo-relative dir, used for writer/reader lookup
    display: str                          #: what goes in the artifact's ``path``
    files: list[Path]                     #: every member on disk
    members: list[Path]                   #: the members actually opened
    partitions: dict[str, list[Path]]     #: partition key -> its files
    note: str


def _partitioned_assets(root: Path) -> list[tuple[str, Path, list[Path]]]:
    """(id, axis_dir, member files) for each partitioned lake tree.

    THE ROW-#77 CASE. ``data/lake/bronze/crypto/<SYM>/D1/*.parquet`` is 267 symbol directories, so
    a flat scan of ``data/`` sees nothing and the desk's best panel vanishes from its own map.
    """
    base = root / _LAKE
    if not base.is_dir():
        return []
    out = []
    for axis in sorted(p for p in base.iterdir() if p.is_dir()):
        files = sorted(axis.rglob("*.parquet")) + sorted(axis.rglob("*.jsonl"))
        if files:
            out.append((f"lake_{axis.name}", axis, files))
    return out


def _lake_panels(root: Path, *, deep: bool) -> list[_Panel]:
    panels = []
    for aid, axis_dir, files in _partitioned_assets(root):
        sample = files[:1] + files[len(files) // 2:len(files) // 2 + 1] + files[-1:]
        # dict.fromkeys dedupes while keeping order: a 1- or 2-file tree would otherwise "sample"
        # the same file three times and then read as sampled when it was in fact read whole.
        members = files if deep else list(dict.fromkeys(sample))
        parts: dict[str, list[Path]] = {}
        for f in files:
            parts.setdefault(f.relative_to(axis_dir).parts[0], []).append(f)
        rel = axis_dir.relative_to(root).as_posix()
        panels.append(_Panel(
            id=aid, rel=rel, display=rel + "/**", files=files, members=members, partitions=parts,
            note=(f"{len(files)} partition file(s) across {len(parts)} partition(s)"
                  + ("" if deep else f"; span sampled from {len(members)}, breadth exact"))))
    return panels


#: ``<SYM>-<INTERVAL>-<START>-<END>.npz`` -- the fetcher writes provenance into the FILENAME
#: (scripts/fetch_binance_vision.py:119), so the partition key is readable without opening anything.
_NPZ_NAME = re.compile(r"^([A-Z0-9]+)-([0-9]+[smhdwM])-(\d{4}-\d{2})-(\d{4}-\d{2})$")


def _npz_panels(root: Path) -> list[_Panel]:
    """One panel per (cache dir, bar interval) -- row #77's shape a third time.

    ``data/binance_vision`` is 55 files of 5.7-year daily and 3-year intraday USD-M perp history and
    it was invisible to BOTH existing sweeps: the flat scan only knows parquet/jsonl, and the lake
    sweep only walks ``data/lake/bronze``. It is the longest thing this checkout can measure, three
    research scripts already load from it, and the desk's map did not carry a single row for it.

    Split by INTERVAL because a 5-minute panel and a daily panel bound completely different studies
    and merging them would report one span for two datasets. Every member is opened -- an npz reads
    one lazily-decompressed column, so exactness is affordable here in a way it is not for the lake.
    """
    panels = []
    for cache in _NPZ_CACHES:
        d = root / cache
        if not d.is_dir():
            continue
        by_interval: dict[str, dict[str, list[Path]]] = {}
        for f in sorted(d.glob("*.npz")):
            m = _NPZ_NAME.match(f.stem)
            key, sym = (m.group(2), m.group(1)) if m is not None else ("unkeyed", f.stem)
            by_interval.setdefault(key, {}).setdefault(sym, []).append(f)
        for interval, parts in sorted(by_interval.items()):
            files = sorted(f for fs in parts.values() for f in fs)
            panels.append(_Panel(
                id=f"{d.name}_{interval}", rel=cache,
                display=f"{cache}/*-{interval}-*.npz",
                files=files, members=files, partitions=parts,
                note=(f"{len(files)} cache file(s) across {len(parts)} symbol(s) at {interval}; "
                      f"every member measured")))
    return panels


def _balanced_window(firsts: list[str], lasts: list[str]) -> tuple[str | None, str | None,
                                                                  int | None]:
    """The window EVERY partition covers: latest start, earliest end.

    A union span flatters a ragged panel and that flattery is expensive. ``binance_vision_1d`` is a
    25-symbol panel whose union runs 2069 days, but 4 symbols only start in 2023-08: a study that
    uses all 25 has 1096 days of cross-section, not 2069, and sizing it off the union would
    overstate ``sqrt(years)`` by 38 %.
    """
    from datetime import date

    if not firsts or not lasts or len(firsts) != len(lasts):
        return None, None, None
    lo, hi = max(firsts), min(lasts)
    try:
        n = (date.fromisoformat(hi) - date.fromisoformat(lo)).days + 1
    except ValueError:
        return None, None, None
    return (lo, hi, n) if n > 0 else (lo, hi, 0)


def _gap_notes(span: AssetSpan) -> list[str]:
    """Say the overstatement out loud ON THE ROW, so nobody has to join two fields to see it."""
    if not span.gapped or span.days is None or span.observed_days is None:
        return []
    return [f"GAPPED: {span.days}d elapsed but only {span.observed_days}d observed "
            f"({span.gap_days}d missing in {span.n_gaps} run(s), largest {span.largest_gap_days}d "
            f"{span.largest_gap_from}..{span.largest_gap_to}) -- this is "
            f"{span.evidence_years}y of evidence, NOT {span.years}y"]


def _partition_gap_note(holes: list[tuple[str, AssetSpan]], breadth: int) -> list[str]:
    """A panel's UNION span hides a per-partition hole: one symbol's dead month is covered by the
    other 24. That is the right union number and the wrong answer for a per-symbol study, so the
    holes are named separately rather than averaged away."""
    if not holes:
        return []
    named = "; ".join(f"{k} -{s.gap_days}d ({s.largest_gap_from}..{s.largest_gap_to})"
                      for k, s in holes[:3])
    tail = f" and {len(holes) - 3} more" if len(holes) > 3 else ""
    return [f"PARTITION HOLES: {len(holes)}/{breadth} partition(s) have internal gaps the union "
            f"span hides -- {named}{tail}"]


def _not_readable_note(rel: str) -> str:
    """One sentence, one address. An operator must be able to grep the token and get a path."""
    return (f"{NOT_READABLE_HERE}: {rel} is declared by the desk's own code but NOT PRESENT on "
            f"this box -- span UNMEASURED, not zero and not guessed (this box may not be the "
            f"collecting box; the VPS run of scripts/build_data_registry.py completes this row)")


def build(root: Path | None = None, *, deep: bool = False) -> list[DataAsset]:
    """Discover and MEASURE every data asset. ``deep`` measures every lake partition member.

    Without ``deep`` a lake tree is measured from a sample of members (first/middle/last), which is
    what makes a 267-symbol daily panel affordable to register every day; the sampled span keeps its
    gap fields UNMEASURED rather than reading as hole-free. Breadth is always exact -- it is a
    partition count, not a sample. npz caches are always measured in full (one column per file).
    """
    root = root or _ROOT
    # panels first: their directories are what the consumer grep must also look for
    panels = _lake_panels(root, deep=deep) + _npz_panels(root)
    writers, readers = _writers_and_readers(root, {p.rel for p in panels})
    cadence = _cadence_hours(root)
    assets: list[DataAsset] = []
    seen: set[str] = set()

    def cad_for(collector: str | None) -> float | None:
        return cadence.get(collector) if collector else None

    for rel in sorted(set(writers) | set(readers)):
        p = root / rel
        if p.is_dir() or rel in seen:
            continue
        seen.add(rel)
        aid = Path(rel).stem
        m = measure(p)
        span, rows, breadth = m.span, m.rows, m.breadth
        if not span.readable_here:
            span = replace(span, missing_path=rel)
        collector = writers.get(rel)
        cad = cad_for(collector)
        a = DataAsset(
            id=aid, path=rel, kind="flat", collector=collector,
            consumers=readers.get(rel, []),
            dependencies=_dependencies_of(collector, rel, readers),
            span=span, quality=measure_quality(p, span, rows, breadth),
            rows=rows, breadth=breadth,
            bytes=p.stat().st_size if p.exists() else None,
            cadence_h=cad, replication=classify_replication(aid),
            maintenance_runs_per_day=(round(24.0 / cad, 2) if cad else None),
            needs_credentials=_needs_credentials(root, collector),
            last_validated=_mtime_day(p),
        )
        if span.status == "absent":
            a.notes.append(_not_readable_note(rel))
        a.notes += _gap_notes(span)
        a.moat_score, a.research_value = score(a)
        assets.append(a)

    for panel in panels:
        complete = len(panel.members) == len(panel.files)
        days: set[str] = set()
        firsts: list[str] = []
        lasts: list[str] = []
        rows = 0
        owner = {f: k for k, fs in panel.partitions.items() for f in fs}
        per_partition: dict[str, tuple[list[str], list[str]]] = {}
        holes: list[tuple[str, AssetSpan]] = []
        for f in panel.members:
            mm = measure(f)
            rows += mm.rows or 0
            days |= mm.days
            if mm.span.gapped:
                holes.append((f.stem, mm.span))
            if mm.span.first is not None and mm.span.last is not None:
                lo, hi = per_partition.setdefault(owner.get(f, f.stem), ([], []))
                lo.append(mm.span.first)
                hi.append(mm.span.last)
        holes.sort(key=lambda h: -(h[1].gap_days or 0))
        for lo_list, hi_list in per_partition.values():
            firsts.append(min(lo_list))
            lasts.append(max(hi_list))
        span = _span_from_days(days, complete=complete)
        if complete and span.measured:
            b_first, b_last, b_days = _balanced_window(firsts, lasts)
            span = replace(span, balanced_first=b_first, balanced_last=b_last,
                           balanced_days=b_days)
        breadth = len(panel.partitions)          # EXACT partition count, never the sample size
        coll = writers.get(panel.rel)
        cad = cad_for(coll)
        a = DataAsset(
            id=panel.id, path=panel.display, kind="partitioned",
            collector=coll, consumers=readers.get(panel.rel, []),
            dependencies=_dependencies_of(coll, panel.rel, readers),
            span=span,
            # quality is measured on ONE representative member: reading 267 symbol files to score
            # the panel would cost more than the score is worth, and the failure modes it catches
            # (recorder holes, echoed values) are per-file properties anyway
            quality=(measure_quality(panel.members[0], span, rows, breadth)
                     if panel.members else DataQuality()),
            rows=rows if complete else None,
            breadth=breadth,
            bytes=sum(f.stat().st_size for f in panel.files),
            cadence_h=cad,
            replication=classify_replication(panel.id),
            maintenance_runs_per_day=(round(24.0 / cad, 2) if cad else None),
            needs_credentials=_needs_credentials(root, coll),
            last_validated=_mtime_day(panel.members[0]) if panel.members else None,
        )
        a.notes.append(panel.note)
        if span.balanced_days is not None and span.days is not None \
                and span.balanced_days < span.days:
            a.notes.append(
                f"RAGGED PANEL: the union runs {span.days}d but only "
                f"{span.balanced_first}..{span.balanced_last} ({span.balanced_days}d) is covered "
                f"by all {breadth} partition(s) -- a cross-sectional study on the full breadth has "
                f"{_years(span.balanced_days)}y, not {span.years}y")
        a.notes += _gap_notes(span) + _partition_gap_note(holes, breadth)
        a.moat_score, a.research_value = score(a)
        assets.append(a)

    return sorted(assets, key=lambda x: (-x.research_value, x.id))
