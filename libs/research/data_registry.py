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

Pure stdlib + optional pandas (parquet). Import from ``libs.research.data_registry``; the CLI is
``scripts/build_data_registry.py``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: Column names that carry a row's date, most-specific first. A dataset whose date lives under a
#: name absent here is reported ``no-date-column`` rather than silently spanless -- the whole point
#: is that an unmeasured span is visible.
_DATE_COLS = ("date", "day", "ts", "timestamp", "time", "open_time", "dt", "datetime")

#: Where partitioned trees live. Depth-2 under the axis dir is ``<SYM>/<TF>/`` (the shape that was
#: invisible to the flat inventory); depth-1 is ``<SYM>/``.
_LAKE = "data/lake/bronze"

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
    """A dataset's real time extent. ``None`` fields mean UNMEASURED, and ``status`` says why."""

    first: str | None = None
    last: str | None = None
    days: int | None = None
    status: str = "unmeasured"

    @property
    def measured(self) -> bool:
        return self.status == "measured"


@dataclass
class DataAsset:
    """One row of the registry. Every numeric field is measured or explicitly absent."""

    id: str
    path: str
    kind: str = "flat"                       #: "flat" | "partitioned"
    collector: str | None = None             #: the script that WRITES it
    consumers: list[str] = field(default_factory=list)   #: scripts that READ it
    span: AssetSpan = field(default_factory=AssetSpan)
    rows: int | None = None                  #: reported SEPARATELY from span, never as duration
    breadth: int | None = None               #: distinct symbols / partitions
    bytes: int | None = None
    cadence_h: float | None = None           #: from ops/crontab.manifest, None = unscheduled
    replication: str = REPL_REFETCHABLE
    moat_score: float = 0.0
    research_value: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["span"] = asdict(self.span)
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


def _span_from_days(days: list[str]) -> AssetSpan:
    from datetime import date

    ds = sorted(d for d in days if d)
    if not ds:
        return AssetSpan(status="no-date-column")
    try:
        n = (date.fromisoformat(ds[-1]) - date.fromisoformat(ds[0])).days + 1
    except ValueError:
        return AssetSpan(first=ds[0], last=ds[-1], status="measured")
    return AssetSpan(first=ds[0], last=ds[-1], days=n, status="measured")


def _measure_jsonl(p: Path) -> tuple[AssetSpan, int | None, int | None]:
    """Span/rows/breadth for newline-delimited JSON, streamed (these grow unbounded)."""
    days: list[str] = []
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
                            days.append(d)
                        break
                for k in ("symbol", "sym", "ticker", "pair", "asset"):
                    if rec.get(k):
                        syms.add(str(rec[k]))
                        break
    except OSError:
        return AssetSpan(status="unreadable"), None, None
    # keep only the extremes; holding every day of a multi-year feed is pointless memory
    return _span_from_days(days), rows, len(syms) or None


def _measure_parquet(p: Path) -> tuple[AssetSpan, int | None, int | None]:
    try:
        import pandas as pd
    except ImportError:
        return AssetSpan(status="no-parquet-reader"), None, None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return AssetSpan(status="unreadable"), None, None
    rows = len(df)
    col = next((c for c in _DATE_COLS if c in df.columns), None)
    if col is None:
        idx = df.index
        got = getattr(idx, "is_all_dates", False) or "datetime" in str(getattr(idx, "dtype", ""))
        if not got:
            return AssetSpan(status="no-date-column"), rows, None
        days = [d for d in (_iso_day(v) for v in (idx.min(), idx.max())) if d]
    else:
        s = df[col].dropna()
        days = [d for d in (_iso_day(s.min()), _iso_day(s.max())) if d] if len(s) else []
    breadth = None
    for k in ("symbol", "sym", "ticker", "pair", "asset"):
        if k in df.columns:
            breadth = int(df[k].nunique())
            break
    return _span_from_days(days), rows, breadth


def measure_span(path: Path) -> tuple[AssetSpan, int | None, int | None]:
    """(span, rows, breadth) for one file. Absent is ``absent``, never a zero-length span."""
    if not path.exists():
        return AssetSpan(status="absent"), None, None
    if path.suffix == ".parquet":
        return _measure_parquet(path)
    if path.suffix in (".jsonl", ".ndjson"):
        return _measure_jsonl(path)
    return AssetSpan(status="unsupported-format"), None, None


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

def _writers_and_readers(root: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Map data paths -> the script that writes them, and -> scripts that read them.

    Grep-derived on purpose: a hand-kept owner column is the field most likely to be stale, and a
    stale OWNER is how row #77's inventory drifted from reality in the first place.
    """
    writers: dict[str, str] = {}
    readers: dict[str, list[str]] = {}
    pat = re.compile(r'["\']((?:data/)[A-Za-z0-9_./-]+\.(?:parquet|jsonl|ndjson))["\']')
    for py in sorted((root / "scripts").glob("*.py")) + sorted((root / "libs").rglob("*.py")):
        try:
            src = py.read_text("utf-8", errors="replace")
        except OSError:
            continue
        rel = py.relative_to(root).as_posix()
        for m in pat.finditer(src):
            path = m.group(1)
            # a writer names the path near a write call; everything else is a reader
            near = src[max(0, m.start() - 220):m.end() + 220]
            if re.search(r"to_parquet|write_text|open\([^)]*[\"']a|\.write\(|dump|append", near):
                writers.setdefault(path, rel)
            else:
                readers.setdefault(path, [])
                if rel not in readers[path]:
                    readers[path].append(rel)
    return writers, readers


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


def build(root: Path | None = None, *, deep: bool = False) -> list[DataAsset]:
    """Discover and MEASURE every data asset. ``deep`` measures every partition member.

    Without ``deep`` a partitioned tree is measured from a sample of members (first/middle/last),
    which is what makes a 267-symbol daily panel affordable to register every day. Breadth is
    always exact -- it is a directory count, not a sample.
    """
    root = root or _ROOT
    writers, readers = _writers_and_readers(root)
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
        span, rows, breadth = measure_span(p)
        collector = writers.get(rel)
        a = DataAsset(
            id=aid, path=rel, kind="flat", collector=collector,
            consumers=readers.get(rel, []), span=span, rows=rows, breadth=breadth,
            bytes=p.stat().st_size if p.exists() else None,
            cadence_h=cad_for(collector), replication=classify_replication(aid),
        )
        if span.status == "absent":
            a.notes.append("declared by a collector but NOT PRESENT on this box -- span "
                           "unmeasured, not zero (this box may not be the collecting box)")
        a.moat_score, a.research_value = score(a)
        assets.append(a)

    for aid, axis_dir, files in _partitioned_assets(root):
        members = files if deep else (files[:1] + files[len(files) // 2:len(files) // 2 + 1]
                                      + files[-1:])
        days: list[str] = []
        rows = 0
        for f in members:
            s, r, _ = measure_span(f)
            rows += r or 0
            days += [d for d in (s.first, s.last) if d]
        # breadth is the EXACT partition count, never the sample size
        breadth = len({f.relative_to(axis_dir).parts[0] for f in files})
        rel = axis_dir.relative_to(root).as_posix()
        a = DataAsset(
            id=aid, path=rel + "/**", kind="partitioned",
            collector=writers.get(rel), consumers=readers.get(rel, []),
            span=_span_from_days(days),
            rows=rows if deep else None,
            breadth=breadth,
            bytes=sum(f.stat().st_size for f in files),
            cadence_h=cad_for(writers.get(rel)),
            replication=classify_replication(aid),
        )
        a.notes.append(f"{len(files)} partition file(s) across {breadth} partition(s)"
                       + ("" if deep else f"; span sampled from {len(members)}, breadth exact"))
        a.moat_score, a.research_value = score(a)
        assets.append(a)

    return sorted(assets, key=lambda x: (-x.research_value, x.id))
