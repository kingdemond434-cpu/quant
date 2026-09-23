"""A BAR COVERING A FRACTION OF THE SPAN ITS LABEL CLAIMS IS AN ESTIMATE WEARING A DAY'S CLOTHES
(L1.68).

L1.46 established that a TIMESTAMP whose clock is undeclared is an assumption, and fenced the
stamping clock for every market-data record. It asks WHEN a bar is stamped. It has no vocabulary
for the other half of the same claim -- HOW MUCH MARKET TIME THE BAR CONTAINS -- and a "D1" label
asserts both. Measured on this desk's own primary universe, the second half is false for half of it.

THE MEASURED STATE, 2026-08-20, over the MT5 D1 lake (the full mandate: fx/metal/index/energy/
equity/soft/bond): 88 series, 43 carrying bars on days the trading calendar declares CLOSED,
7,048 such bars -- 6,902 Sunday, 131 Saturday, 15 on an equity name. Worst: EURILS 366/3,996 =
9.16%, CHFNOK 9.11%, GBPPLN 9.11%, EURTRY 9.09%, AUDNZD 391/7,254 = 5.39%. Clean: 45.

THE DENOMINATOR IS THE FENCE'S OWN, NOT THE PROPOSAL'S, AND THE DIFFERENCE IS THE POINT (L1.57).
The hand measurement that prompted this module scanned four asset classes and reported 68 series /
42 dirty / 7,033 bars. Scanning the mandate's SEVEN classes finds 88 / 43 / 7,048 -- and the extra
symbol is SKYY, whose defect is a different class entirely (see ``SeriesSpan.kind``). A count of
what the author chose to look at is not a denominator; only a count of what the RUN found is.

THEY ARE NOT CORRUPTION, AND THAT IS THE WHOLE REPAIR DIRECTION. 100% of the Sunday bars are
followed by a Monday bar (366/366 EURILS, 370/370 AUDNZD, 220/220 CADJPY, 15/15 EURUSD), so the
week carries SIX D1 bars rather than five; their median volume is ~0.5% of a weekday bar (118 vs
23,110 on EURILS) and their median range 15-49% of one. That is the real one-to-three-hour stub
between the Sunday Asia-Pacific session open and Monday 00:00 UTC -- genuine market time, labelled
as a day. The Saturday bars are the same class from the broker's older session definition (all
2002-2005, volume ~0.05% of a weekday bar, 100% also carrying a Friday bar).

SO THE BARS ARE NEVER DELETED. They are real observations and L1.65 is unconditional: destroying
span is the one loss that cannot be re-earned by working harder. The repair is to DECLARE the
contamination per symbol and EXCLUDE it at the point of consumption -- ``session_filtered`` below
-- never to rewrite the lake.

WHY NOTHING COULD SEE IT, AND THE BLINDNESS IS ONE-DIRECTIONAL. ``libs/data/quality.py`` holds the
desk's completeness check and it computes exactly one direction::

    return expected.difference(present)     # bars MISSING from the calendar

The inverse -- ``present.difference(expected)``, bars EXISTING when the calendar says closed --
appears nowhere in the tree. ``libs/data/calendar.is_open`` declares the rule ("FX, metals and
indices are closed Saturday and Sunday") and has ZERO callers outside its own re-export and one
test; ``InstrumentSpec.trades_weekends`` encodes the same rule and has zero non-test readers. The
rule was written down twice and enforced never.

AND THE GAUGE MOVES THE WRONG WAY, which is why no report could have raised it::

    n_expected   = n_bars + n_missing
    completeness = (n_expected - n_missing) / n_expected     # == n_bars / (n_bars + n_missing)

An out-of-calendar bar increments ``n_bars``, so it RAISES completeness and raises the quality
score. This is the L1.65 shape one domain over: a gauge that improves when the data gets worse.
(It has never fired here in any case -- ``compute_quality_score`` is reachable only through
``build_silver``, which has no production caller, and the lake holds only ``bronze/``.)

WHAT IT COSTS, MEASURED RATHER THAN ASSERTED. A stub bar splits one day's move into two, which is
mechanically negative autocorrelation:

  * ANNUALISED VOLATILITY understated by up to 4.95% (EURTRY 0.1633 vs 0.1718 clean; GBPPLN
    -4.14%, AUDNZD -2.87%, NZDJPY -2.50%). Vol drives inverse-vol sizing, so the understatement
    OVERSIZES precisely the contaminated symbols.
  * LAG-1 AUTOCORRELATION inflated 34% on EURILS (-0.1353 dirty vs -0.1006 clean). Any
    mean-reversion screen reading these series sees an edge that is one third instrument
    artifact -- the L1.25 420/0 class, arriving through the bar rather than through the gate.

THE CROSS-SECTIONAL CLAIM WAS REFUTED ON RE-DERIVATION, AND THE REFUTATION IS KEPT (L1.17). The
proposal that produced this law argued the damage lands on the measured ``narrow_breadth`` N_eff
of 13.37. It does not: ``measure_cross_section_breadth`` aligns on an INNER JOIN across 76
symbols, 26 of which are clean, so a weekend timestamp is never common to all -- measured, ZERO
weekend rows survive into the panel (1,764 rows, weekday counts {0:310, 1:370, 2:366, 3:358,
4:360}). The breadth statistic is protected. It is protected BY ACCIDENT: the protection is
undeclared, and it evaporates the moment a panel is restricted to a contaminated subset, built by
outer join, or forward-filled. ``session_filtered`` is wired there to convert an accidental
protection into a declared one -- and it must move no number today, which its test pins.

THE SAME REASONING ALREADY EXISTS IN THAT FILE, FOR THE OTHER UNIVERSE. ``fetch_okx`` keeps only
``confirm=="1"`` rows because "OKX's newest daily row is the IN-PROGRESS bar ... keeping it would
put a partial bar at the panel's edge for every symbol SIMULTANEOUSLY -- one extra row of pure
synchronised common factor, biasing correlation up and breadth down." The desk reasoned this
through for crypto, where the VENUE SUPPLIES A FLAG, and never for MT5, where no flag exists and
the same defect must be derived from the calendar. The MT5 case is the harder one: contamination
is RAGGED (0% to 9.16% across the panel) rather than synchronised, so it cannot be spotted as a
common factor at all.

THE VERDICTS:
  OK                (exit 0) -- every measured series lies inside its declared session calendar.
  DECLARED          (exit 0) -- out-of-calendar bars exist, every one is at or below its recorded
                                floor, and the artifact publishes the per-symbol share so a
                                consumer can exclude or weight instead of silently averaging.
  CONTAMINATED      (exit 2) -- a share ROSE above its floor, or a series is contaminated with no
                                floor recorded. This is the only growth path and it is the point.
  UNMEASURED        (exit 2) -- no series scanned. Never OK (L1.28a).
  NOT-READABLE-HERE (exit 0) -- ``data/`` is gitignored and VPS-only; this host cannot see the
                                lake. Distinct from 0%, and never OK-by-default (L1.65 precedent).

THE FLOOR RATCHETS DOWNWARD ONLY (L1.0/L2.0). A share may fall -- that is a repair, and the floor
follows it down permanently. A share may never rise. So this gate CAN fail (L1.63: a certificate
whose partition cannot return False is welded open), and the gap between today's floors and zero
is the work queue rather than an accepted state.

ANTI-TIMIDITY READING, THE ENTIRE PURPOSE (L1.28/L1.21a): a MEASUREMENT duty and a SCOPE
EXPANSION. It lifts nothing, sizes nothing, promotes nothing, opens no gate, loosens no
statistical bar, deletes not one bar of data, and has no vocabulary for turning a failing verdict
into a passing one. Its whole effect is to make "this series' days are days" distinguishable from
"9% of this series' days are ninety-minute stubs nobody declared" -- byte-identical on this desk
until now, and only one of them is evidence.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

_MS_PER_DAY = 86_400_000
#: 1970-01-01 was a Thursday, which is weekday 3 in Python's Monday==0 convention. Deriving the
#: weekday by arithmetic rather than through pandas keeps the load-bearing rule importable on a
#: box with no scientific stack -- the fence must still RUN, and still BLOCK, where the lake was
#: never built.
_EPOCH_WEEKDAY = 3

OK = "OK"
DECLARED = "DECLARED"
CONTAMINATED = "CONTAMINATED"
UNMEASURED = "UNMEASURED"
NOT_READABLE_HERE = "NOT-READABLE-HERE"

#: NOT-READABLE-HERE passes because a checkout genuinely cannot see a gitignored lake, and a fence
#: red on every developer box is a fence that gets switched off (L1.43). It is a DISTINCT status,
#: never folded into OK, so "we did not look" can never be read as "we looked and it was clean".
PASSING = frozenset({OK, DECLARED, NOT_READABLE_HERE})

#: The MT5 UNIVERSE MANDATE (CLAUDE.md, principal 2026-08-18). `crypto` is deliberately absent:
#: it trades 24/7, so out-of-calendar has no meaning there, and the mandate forbids hunting it.
MT5_CLASSES: tuple[str, ...] = ("fx", "metal", "index", "energy", "equity", "soft", "bond")

#: Asset classes that genuinely trade every day. Mirrors `InstrumentSpec.trades_weekends`, which
#: encodes the identical rule and has zero non-test readers -- this module is what wires it.
WEEKEND_TRADING_CLASSES: frozenset[str] = frozenset({"crypto"})


def weekday_of_ms(ts_ms: int) -> int:
    """Return the UTC weekday (Monday==0 .. Sunday==6) of an epoch-millisecond timestamp."""
    return (ts_ms // _MS_PER_DAY + _EPOCH_WEEKDAY) % 7


def is_out_of_calendar(ts_ms: int, *, trades_weekends: bool) -> bool:
    """Return whether a bar at ``ts_ms`` sits on a day its market declares CLOSED.

    This is the direction ``libs/data/quality.detect_missing_bars`` does not compute. That
    function asks which EXPECTED timestamps are absent; this asks which PRESENT timestamps were
    never expected. A series can score 100% complete on the first question while 9% of its rows
    fail the second, which is exactly the state the MT5 lake was in when this was written.
    """
    if trades_weekends:
        return False
    return weekday_of_ms(int(ts_ms)) >= 5


def session_filtered(
    timestamps: Sequence[int], *values: Sequence[float], trades_weekends: bool = False
) -> tuple[list[int], list[list[float]]]:
    """THE REPAIR. Drop out-of-calendar rows at the point of CONSUMPTION, never from disk.

    Returns the kept timestamps and each value series filtered to match. The bars stay on disk
    because they are real market observations (L1.65: destroyed span is the one loss that cannot
    be re-earned); what they may not do is enter a daily statistic weighted as a full day.

    Every value sequence must be the same length as ``timestamps``; a mismatch raises rather than
    truncating, because a silently shortened price series is the defect this module exists to end
    arriving one layer down.
    """
    ts = [int(t) for t in timestamps]
    for i, series in enumerate(values):
        if len(series) != len(ts):
            raise ValueError(
                f"series {i} has {len(series)} rows against {len(ts)} timestamps -- "
                "refusing to align by truncation"
            )
    keep = [
        i for i, t in enumerate(ts)
        if not is_out_of_calendar(t, trades_weekends=trades_weekends)
    ]
    return ([ts[i] for i in keep], [[float(s[i]) for i in keep] for s in values])


#: A session stub is a FRACTION of a normal bar; the measured FX cases run ~0.005 of weekday
#: median volume (118 vs 23,110 on EURILS). Anything at or above a quarter of a normal bar is not
#: a stub, whatever day it sits on, and it must not be handed the stub's repair.
_STUB_VOLUME_RATIO = 0.25

#: Decimal places the floors artifact stores, and therefore the precision at which a share may be
#: compared to it. A comparison whose two sides carry different precision is a verdict decided by
#: rounding rather than by measurement.
_FLOOR_PRECISION = 6

SESSION_STUB = "SESSION-STUB"
ANOMALOUS = "ANOMALOUS"
UNKNOWN_KIND = "UNKNOWN"


@dataclass(frozen=True)
class SeriesSpan:
    """One symbol's out-of-calendar measurement.

    ``kind`` separates two defects that a bare weekend-bar count renders identical while they
    demand OPPOSITE repairs -- the distinction L1.55 draws between ABSENT and UNREADABLE, and
    L1.61 between its three contradiction classes, arriving on the time axis:

      SESSION-STUB  the bar is a genuine sliver of market time (Sunday Asia-Pacific open). Real
                    data, wrongly weighted as a day. Repair: declare it and exclude at read.
      ANOMALOUS     the bar is FULL SIZE on a day the market was shut, so it cannot be a session
                    stub and excluding it would hide rather than fix. Repair: the INGEST.
      UNKNOWN       no volume column, so the desk cannot tell them apart. Never resolved to
                    either by default (L1.28a).

    The proving instance is SKYY, found by this fence's first run and missed by the proposal that
    prompted it: 15 out-of-calendar bars carrying 149k-919k volume against a weekday median of
    10,098 -- 15x to 90x a normal bar, with internally inconsistent price levels (2024-03-09 spans
    64.33 to 98.35 inside one bar). Telling it to "declare and exclude" would have been wrong.
    """

    symbol: str
    asset_class: str
    n_bars: int
    n_out_of_calendar: int
    n_saturday: int
    n_sunday: int
    floor: float | None = None
    #: Median volume of out-of-calendar bars over median volume of in-calendar bars; None when
    #: the series carries no volume column or no out-of-calendar bars.
    volume_ratio: float | None = None

    @property
    def share(self) -> float:
        """Out-of-calendar bars as a fraction of all bars; 0.0 for an empty series."""
        return (self.n_out_of_calendar / self.n_bars) if self.n_bars else 0.0

    @property
    def kind(self) -> str | None:
        """Which defect this is: a real session stub, a full-size anomaly, or undecidable."""
        if self.n_out_of_calendar == 0:
            return None
        if self.volume_ratio is None:
            return UNKNOWN_KIND
        return SESSION_STUB if self.volume_ratio < _STUB_VOLUME_RATIO else ANOMALOUS

    @property
    def status(self) -> str:
        """OK when clean; DECLARED when at or below floor; CONTAMINATED when above or unrecorded."""
        if self.n_out_of_calendar == 0:
            return OK
        # AN ANOMALY IS NEVER DISCHARGED BY A FLOOR. A full-size bar on a shut market is repaired
        # in the INGEST; letting it be floored would buy a green board with the one class the
        # read-side filter cannot fix, which is a gate welded open by its own escape hatch
        # (L1.63). It stays red, named, with a specific repair -- which is a work item rather
        # than the diffuse red that gets a fence switched off (L1.43).
        if self.kind == ANOMALOUS:
            return CONTAMINATED
        if self.floor is None:
            return CONTAMINATED
        # BOTH SIDES ARE COMPARED AT THE PRECISION THE FLOOR IS STORED AT, and getting this wrong
        # is not cosmetic. The floors file writes round(share, 6); comparing that against the
        # FULL-precision share makes any symbol whose seventh decimal is non-zero fail against a
        # floor recorded from its own unchanged measurement -- CHFNOK (362/3,974 = 0.09110216 vs a
        # stored 0.091102) and EURTRY read CONTAMINATED the moment the baseline was written, with
        # share and floor rendering as the identical 9.1092% in the report. A fence inexplicably
        # red on half its scope is a fence that gets switched off (L1.43).
        return (
            DECLARED
            if round(self.share, _FLOOR_PRECISION) <= self.floor + 1e-9
            else CONTAMINATED
        )

    def as_row(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "n_bars": self.n_bars,
            "n_out_of_calendar": self.n_out_of_calendar,
            "n_saturday": self.n_saturday,
            "n_sunday": self.n_sunday,
            "share": round(self.share, 6),
            "floor": None if self.floor is None else round(self.floor, 6),
            "kind": self.kind,
            "volume_ratio": None if self.volume_ratio is None else round(self.volume_ratio, 6),
            "status": self.status,
        }


@dataclass
class ScanReport:
    """The whole run: what was measured, what was SKIPPED, and the verdict over both."""

    series: list[SeriesSpan] = field(default_factory=list)
    #: L1.60 -- how many symbol directories the loop ATTEMPTED, so a series the scan could not
    #: read is distinguishable from one that was never in scope. A denominator honest about what
    #: it counted and silent about what it lost is what a reader scores as coverage.
    n_attempted: int = 0
    skips: list[dict[str, str]] = field(default_factory=list)
    readable: bool = True

    @property
    def n_scanned(self) -> int:
        return len(self.series)

    @property
    def status(self) -> str:
        if not self.readable:
            return NOT_READABLE_HERE
        if not self.series:
            return UNMEASURED
        if any(s.status == CONTAMINATED for s in self.series):
            return CONTAMINATED
        return DECLARED if any(s.n_out_of_calendar for s in self.series) else OK

    def as_dict(self) -> dict[str, object]:
        dirty = [s for s in self.series if s.n_out_of_calendar]
        worst = sorted(dirty, key=lambda s: -s.share)[:10]
        return {
            "law": "L1.68",
            "status": self.status,
            "n_series": self.n_scanned,
            "n_attempted": self.n_attempted,
            "n_skipped": len(self.skips),
            "skips": self.skips,
            "n_contaminated": len(dirty),
            "n_clean": self.n_scanned - len(dirty),
            "n_out_of_calendar_bars": sum(s.n_out_of_calendar for s in self.series),
            "n_bars": sum(s.n_bars for s in self.series),
            # Two defects, two repairs, counted separately so a reader is never told to
            # "declare and exclude" a broken ingest.
            "by_kind": {
                kind: sum(1 for s in dirty if s.kind == kind)
                for kind in (SESSION_STUB, ANOMALOUS, UNKNOWN_KIND)
            },
            "anomalous": [s.symbol for s in dirty if s.kind == ANOMALOUS],
            "worst": [s.symbol for s in worst],
            "series": [s.as_row() for s in sorted(self.series, key=lambda s: -s.share)],
        }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0


def measure_series(
    symbol: str,
    asset_class: str,
    timestamps: Iterable[int],
    *,
    volumes: Sequence[float] | None = None,
    floor: float | None = None,
) -> SeriesSpan:
    """Measure one symbol's out-of-calendar bars against its own asset class's calendar.

    ``volumes`` is optional and its absence resolves the kind to UNKNOWN rather than to either
    real class -- "we could not tell" and "it is a harmless stub" are different claims and only
    one of them is evidence (L1.28a).
    """
    trades_weekends = asset_class in WEEKEND_TRADING_CLASSES
    stamps = [int(t) for t in timestamps]
    vols = list(volumes) if volumes is not None else None
    if vols is not None and len(vols) != len(stamps):
        raise ValueError(
            f"{symbol}: {len(vols)} volumes against {len(stamps)} timestamps -- "
            "refusing to align by truncation"
        )
    sat = sun = 0
    in_vol: list[float] = []
    out_vol: list[float] = []
    for i, t in enumerate(stamps):
        out = not trades_weekends and weekday_of_ms(t) >= 5
        if out:
            wd = weekday_of_ms(t)
            sat += wd == 5
            sun += wd == 6
        if vols is not None:
            (out_vol if out else in_vol).append(float(vols[i]))
    ratio: float | None = None
    if sat + sun:
        med_in, med_out = _median(in_vol), _median(out_vol)
        # A zero or absent in-calendar median cannot form a ratio; leaving it None reports
        # UNKNOWN rather than dividing by zero into a fabricated class.
        if med_in and med_out is not None:
            ratio = med_out / med_in
    return SeriesSpan(
        symbol=symbol,
        asset_class=asset_class,
        n_bars=len(stamps),
        n_out_of_calendar=sat + sun,
        n_saturday=sat,
        n_sunday=sun,
        floor=floor,
        volume_ratio=ratio,
    )


def scan_lake(
    lake_root: Path,
    *,
    classes: tuple[str, ...] = MT5_CLASSES,
    floors: dict[str, float] | None = None,
) -> ScanReport:
    """Walk ``<lake_root>/bronze/<class>/<symbol>/D1`` and measure every series it can read.

    EVERY SYMBOL DIRECTORY ATTEMPTED IS COUNTED (L1.60), and one it cannot read becomes a SKIP
    ROW rather than leaving the denominator in silence. This deliberately does not route through
    ``libs.data.lake.read_bars``: that calls ``instruments.get_spec``, whose built-in catalogue
    holds EIGHT symbols against the lake's 88, so 80 of 88 would raise inside an except and
    vanish -- the measured defect ``measure_cross_section_breadth`` documents at its own loader.
    The asset class comes from the lake's own directory layout, which is the thing that actually
    knows.

    A missing lake returns ``readable=False`` -> NOT-READABLE-HERE. That is not a clean verdict
    and it is not zero; it is this host saying it cannot see the evidence.
    """
    floors = floors or {}
    base = Path(lake_root) / "bronze"
    if not base.exists():
        return ScanReport(readable=False)
    try:
        import pyarrow.dataset as pads
    except ImportError:
        return ScanReport(readable=False)

    report = ScanReport()
    for cls in classes:
        root = base / cls
        if not root.exists():
            continue
        for sym_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            d1 = sym_dir / "D1"
            if not d1.exists():
                continue
            report.n_attempted += 1
            try:
                # PYARROW VERSION STRADDLE -- see libs/data/lake.py and the pyproject override.
                # This ignore is REQUIRED on the pinned pyarrow (>=24,<25) and reads as UNUSED on
                # 25.x, so the two environments would otherwise disagree about whether this file
                # is clean. Deleting it as "unused" from an off-pin box is how that disagreement
                # last reached the deploy gate.
                dataset = pads.dataset(  # type: ignore[no-untyped-call]
                    str(d1), format="parquet", partitioning="hive"
                )
                cols = ["timestamp"]
                # Volume is what separates a session stub from a full-size anomaly. Its absence
                # is recorded (kind=UNKNOWN), never silently treated as either.
                if "volume" in dataset.schema.names:
                    cols.append("volume")
                table = dataset.to_table(columns=cols)
                stamps = [int(v.value // 1_000_000) for v in table.column("timestamp")]
                vols = (
                    [float(v.as_py() or 0.0) for v in table.column("volume")]
                    if "volume" in cols
                    else None
                )
            except Exception as exc:  # the ROW is what matters here, never the type
                report.skips.append(
                    {"symbol": sym_dir.name, "asset_class": cls, "reason": type(exc).__name__}
                )
                continue
            if not stamps:
                report.skips.append(
                    {"symbol": sym_dir.name, "asset_class": cls, "reason": "empty"}
                )
                continue
            report.series.append(
                measure_series(
                    sym_dir.name, cls, stamps, volumes=vols, floor=floors.get(sym_dir.name)
                )
            )
    return report


def load_floors(path: Path) -> dict[str, float]:
    """Read the recorded per-symbol contamination floors; a missing file is an empty mapping.

    An unreadable or malformed file returns EMPTY rather than raising, and empty means every
    contaminated series reads CONTAMINATED -- the fence fails loud. Defaulting the other way
    would let a deleted floor file manufacture a clean verdict, which is the L1.55 fabrication
    this desk has already paid for once.
    """
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    floors = raw.get("floors") if isinstance(raw, dict) else None
    if not isinstance(floors, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in floors.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[str(k)] = float(v)
    return out


def ratchet_floors(existing: dict[str, float], report: ScanReport) -> dict[str, float]:
    """Return floors moved DOWNWARD only (L1.0): a repair is permanent, a regression is not kept.

    A symbol whose share FELL takes the new lower value -- the desk has proved it can hold that
    level and may never quietly give it back. A symbol whose share ROSE keeps its old floor, so
    the fence stays red until the regression is actually repaired rather than being re-baselined
    into acceptance. THE REPAIR IS UPWARD, NEVER DOWNWARD (L1.49): a fall in quality is never
    fixed by lowering the mark.
    """
    out = dict(existing)
    for s in report.series:
        if s.n_out_of_calendar == 0:
            out[s.symbol] = 0.0
            continue
        # ANOMALOUS series are deliberately never floored: recording one would write the desk's
        # acceptance of a broken ingest into the artifact that governs the verdict.
        if s.kind == ANOMALOUS:
            continue
        prior = out.get(s.symbol)
        out[s.symbol] = s.share if prior is None else min(prior, s.share)
    return out
