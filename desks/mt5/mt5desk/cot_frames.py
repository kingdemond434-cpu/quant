"""Per-symbol CFTC positioning columns, point-in-time, oriented to the MT5 symbol.

WHY THIS EXISTS (2026-10-06). The `positioning_flow` alpha cluster held no certificate while
three CFTC report families sat in git under `desks/mt5/data/`: legacy (`cot/`, non-commercial and
commercial), Traders in Financial Futures (`cot_tff/`, leveraged money, asset managers, dealers)
and disaggregated (`cot_disagg/`, managed money and swap dealers). The sealed gauntlet's one COT
door, `orthogonal_sweep._cot_frame`, read only `data/cot_zcache.parquet` -- a gitignored z-score
cache of ONE column ("net", legacy non-commercial) that exists on the trading box alone -- so
every positioning-change hypothesis about any other trader class was unbuildable, and on a tree
without the cache even the level hypothesis built with `cot=None`.

This module turns the in-git parquets into the columns the family reads. It is a READER: it
fetches nothing and writes nothing.

THE CLOCK. A report is as of TUESDAY (Monday when Tuesday is a holiday) and normally published
the same week's FRIDAY at 15:30 ET. Its label is the LATER of two instants: the Monday 00:00 UTC
after that Friday (`orthogonal_sweep.COT_RELEASE_LAG_DAYS`, the label the cache has always used,
so a normal week is labelled exactly as before), and the first whole hour after the report's TRUE
release (`release_schedule`). The second only binds when the CFTC published late:

  * a federal holiday or office closure on the Wednesday, Thursday or Friday between the as-of
    date and the release moves the release to the next business day (CFTC 2026 schedule: Jun 19,
    Jul 3, Nov 11, Thanksgiving and Dec 25 weeks all release on the Monday; a MONDAY holiday
    before the as-of Tuesday moves nothing, and a Tuesday holiday moves the as-of date to Monday
    with the Friday release kept -- CFTC announcement of 2018-12-21);
  * the 2013, 2018-19 and 2025 appropriation lapses, whose catch-up releases are tabled in
    `SHUTDOWN_RELEASES` from the CFTC's own announcements.

Before 2026-10-07 every report was labelled the Monday after its NOMINAL Friday, which read a
holiday-week report about 20 hours early and a shutdown report weeks early (the audit measured
692 h and 1,076 h; 746 signals across all 82 positioning-change cells). The parquets carry no
release date, so the schedule is DERIVED; where an announcement gives only a window, the END of
the window is used, so a derived release is never earlier than the real one.

EVERY ROW CARRIES ITS REPORT WEEK (`report_week`, an integer week ordinal). A change is a
difference between two ADJACENT report weeks or it is nothing: `families_orthogonal` reads this
column and leaves the change NaN across any missing week, so a 12-week move is never traded as a
"weekly" one (the TFF files lost 55-86 outright weeks to a cross-rate dedup before 2026-10-07).

THE SIGN. CFTC currency futures are quoted USD per foreign unit, so a long JPY future is a SHORT
USDJPY position. Every column is oriented so POSITIVE means the trader class is long the MT5
symbol; the reciprocal symbols are negated (the rule `scripts/refresh_cot_zcache.INVERT` applies).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
LEGACY = DATA / "cot"
TFF = DATA / "cot_tff"
DISAGG = DATA / "cot_disagg"

#: The z window of the cache's "net" column (`scripts/refresh_cot_zcache.ZWIN`), reproduced when
#: the cache is absent so the default family construction means the same thing on either tree.
ZWIN = 52
ZMIN = 12

#: symbols quoted USD per foreign unit: a long foreign-currency future is a SHORT position here.
INVERT = frozenset({"USDJPY", "USDCHF", "USDCAD"})

#: MT5 symbol -> (legacy slug, TFF slug + market-name prefixes, disaggregated slug). Explicit and
#: exact: a TFF file holds cross-rate contracts too (EURO FX/BRITISH POUND XRATE sits in both the
#: EUR and GBP files), so a market is admitted only on its own name's prefix.
SOURCES: dict[str, tuple[str | None, tuple[str, tuple[str, ...]] | None, str | None]] = {
    "EURUSD": (None, ("eur", ("EURO FX - ",)), None),
    "GBPUSD": ("gbp", ("gbp", ("BRITISH POUND - ", "BRITISH POUND STERLING - ")), None),
    "AUDUSD": ("aud", ("aud", ("AUSTRALIAN DOLLAR - ",)), None),
    "NZDUSD": ("nzd", ("nzd", ("NEW ZEALAND DOLLAR - ", "NZ DOLLAR - ")), None),
    "USDJPY": ("jpy", ("jpy", ("JAPANESE YEN - ",)), None),
    "USDCAD": ("cad", ("cad", ("CANADIAN DOLLAR - ",)), None),
    "USDCHF": ("chf", ("chf", ("SWISS FRANC - ",)), None),
    "XAUUSD": ("gold", None, "gold"),
    "XAGUSD": ("silver", None, "silver"),
}

#: column -> (report family, trader class). The positioning-change cells name these.
COLUMNS: dict[str, tuple[str, str]] = {
    "noncomm_net": ("legacy", "non-commercial (large speculators)"),
    "comm_net": ("legacy", "commercial (hedgers)"),
    "lev_net": ("tff", "leveraged money (hedge funds, CTAs)"),
    "am_net": ("tff", "asset managers (institutional)"),
    "dealer_net": ("tff", "dealers (sell side)"),
    "mm_net": ("disaggregated", "managed money"),
    "swap_net": ("disaggregated", "swap dealers"),
}


#: The column every frame carries: the report's week as an integer ordinal (adjacent reports
#: differ by exactly 1). Never a positioning series.
REPORT_WEEK = "report_week"

#: The CFTC's normal release instant, US Eastern.
RELEASE_ET = "15:30"
ET = "America/New_York"

#: Office closures beyond the federal calendar (pandas `USFederalHolidayCalendar` carries the
#: statutory holidays and their observed days, Juneteenth from 2021). National days of mourning
#: and the executive-order Christmas Eve / Boxing Day closures. A closure listed here that did not
#: in fact delay a report only labels that report LATER, never earlier.
EXTRA_CLOSURES: tuple[str, ...] = (
    "2004-06-11",                # President Reagan, day of mourning
    "2007-01-02",                # President Ford, day of mourning
    "2012-12-24", "2014-12-26", "2015-12-24",
    "2018-12-05",                # President G.H.W. Bush (CFTC announcement 2018-12-04)
    "2018-12-24", "2019-12-24", "2020-12-24",   # 2020: CFTC announcement 2020-12-28
    "2024-12-24",
    "2025-01-09",                # President Carter (CFTC announcement 2025-01-07: release Mon 13th)
    "2025-12-24", "2025-12-26",
)

#: Appropriation lapses: as-of date -> the date the CFTC actually published it (released at an
#: unannounced hour, so labelled at the END of that US day).
#:   2013 (lapse Oct 1-16): CFTC PR 6745-13 -- the Oct 1 report published Oct 25, two more in the
#:     week of Oct 28, at least two more in the week of Nov 4, schedule resumed by Nov 8; the Oct 29
#:     report was published Nov 6 (CFTC "reports update", 2013-11-06). The Oct 8/15 and Oct 22
#:     dates are the END of their announced windows, so never earlier than the truth.
#:   2018-19 (lapse Dec 22 - Jan 25): CFTC PR 7864-19 -- the Dec 24 report published Fri Feb 1,
#:     then one report every Tuesday and Friday until current (the Mar 5 report on Fri Mar 8).
#:   2025 (lapse Oct 1 - Nov 12): CFTC PR 9147-25 table. The Dec 23 report is labelled Dec 31,
#:     the later of the table's Dec 29 and the CFTC's "now available" notice of Dec 31.
SHUTDOWN_RELEASES: dict[str, str] = {
    "2013-10-01": "2013-10-25", "2013-10-08": "2013-11-01", "2013-10-15": "2013-11-01",
    "2013-10-22": "2013-11-06", "2013-10-29": "2013-11-06",
    "2018-12-24": "2019-02-01", "2018-12-31": "2019-02-05", "2019-01-08": "2019-02-08",
    "2019-01-15": "2019-02-12", "2019-01-22": "2019-02-15", "2019-01-29": "2019-02-19",
    "2019-02-05": "2019-02-22", "2019-02-12": "2019-02-26", "2019-02-19": "2019-03-01",
    "2019-02-26": "2019-03-05",
    "2025-09-30": "2025-11-19", "2025-10-07": "2025-11-21", "2025-10-14": "2025-11-25",
    "2025-10-21": "2025-12-02", "2025-10-28": "2025-12-05", "2025-11-04": "2025-12-09",
    "2025-11-10": "2025-12-10", "2025-11-18": "2025-12-12", "2025-11-25": "2025-12-15",
    "2025-12-02": "2025-12-17", "2025-12-09": "2025-12-19", "2025-12-16": "2025-12-23",
    "2025-12-23": "2025-12-31",
}

#: The span the schedule is built over (the legacy history starts 1986).
_SCHEDULE_START = "1985-12-27"


def release_lag_days() -> int:
    """The one lag the desk applies to a COT label. Read from the sweep so the two cannot drift."""
    try:
        from research.orthogonal_sweep import COT_RELEASE_LAG_DAYS
        return int(COT_RELEASE_LAG_DAYS)
    except Exception:
        return 3


def _week_friday(ts: pd.Timestamp) -> pd.Timestamp:
    """The Friday (00:00 UTC) closing the W-FRI week that holds `ts`."""
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    t = t.normalize()
    return t + pd.Timedelta(days=(4 - t.dayofweek) % 7)


def week_ordinal(friday: pd.Timestamp) -> int:
    """Integer week number of a W-FRI Friday; adjacent report weeks differ by exactly 1."""
    return int((_week_friday(friday) - pd.Timestamp("1970-01-02", tz="UTC")).days // 7)


@lru_cache(maxsize=1)
def _closures() -> frozenset:
    from pandas.tseries.holiday import USFederalHolidayCalendar
    days = USFederalHolidayCalendar().holidays(_SCHEDULE_START, "2100-01-01")
    out = {pd.Timestamp(d).date() for d in days}
    out.update(pd.Timestamp(d).date() for d in EXTRA_CLOSURES)
    return frozenset(out)


def _business_day(day) -> bool:
    return day.weekday() < 5 and day not in _closures()


def release_date(friday: pd.Timestamp):
    """(US calendar date of release, from_shutdown_table) for the report of the week ending
    `friday`. Normal: that Friday. A closure on the Wednesday-Friday moves it to the next business
    day after the Friday. A tabled lapse release overrides both."""
    fri = _week_friday(friday)
    for asof, rel in SHUTDOWN_RELEASES.items():
        if _week_friday(pd.Timestamp(asof)) == fri:
            return pd.Timestamp(rel).date(), True
    d = fri.date()
    closures = _closures()
    if any((d - pd.Timedelta(days=k).to_pytimedelta()) in closures for k in (0, 1, 2)):
        nxt = d + pd.Timedelta(days=1).to_pytimedelta()
        while not _business_day(nxt):
            nxt = nxt + pd.Timedelta(days=1).to_pytimedelta()
        return nxt, False
    return d, False


def _label_for(friday: pd.Timestamp) -> pd.Timestamp:
    fri = _week_friday(friday)
    nominal = fri + pd.Timedelta(days=release_lag_days())
    day, tabled = release_date(fri)
    clock = "23:59" if tabled else RELEASE_ET
    released = pd.Timestamp(f"{day} {clock}").tz_localize(ET).tz_convert("UTC")
    return max(nominal, released.ceil("h"))


@lru_cache(maxsize=1)
def release_schedule() -> pd.Series:
    """{W-FRI Friday: label} for every report week from 1986 to two years ahead.

    Labels are made STRICTLY increasing in report order (a report that shares a release instant
    with the one before it is labelled an hour later), so one label is one report week and a
    later report can never be labelled before an earlier one."""
    end = pd.Timestamp.now(tz="UTC").tz_localize(None) + pd.Timedelta(days=730)
    fridays = pd.date_range(pd.Timestamp(_SCHEDULE_START), end, freq="W-FRI", tz="UTC")
    labels: list[pd.Timestamp] = []
    prev: pd.Timestamp | None = None
    for f in fridays:
        lab = _label_for(f)
        if prev is not None and lab <= prev:
            lab = prev + pd.Timedelta(hours=1)
        labels.append(lab)
        prev = lab
    return pd.Series(labels, index=fridays)


def release_label(friday: pd.Timestamp) -> pd.Timestamp:
    """The first instant the report of the week ending `friday` may be read."""
    fri = _week_friday(friday)
    sched = release_schedule()
    if fri in sched.index:
        return sched[fri]
    return _label_for(fri)


def relabel_weeks(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """A W-FRI-resampled index (report-week Fridays) mapped to release labels."""
    return pd.DatetimeIndex([release_label(f) for f in index])


def to_weekly(series: pd.Series) -> pd.Series:
    """A Tuesday(or Monday)-dated weekly series on its report-week Friday, one row per week."""
    s = series.astype(float).dropna().sort_index()
    if s.empty:
        return s
    s = s[~s.index.duplicated(keep="last")]
    return s.resample("W-FRI").last().dropna()


def to_release_clock(series: pd.Series) -> pd.Series:
    """A Tuesday-dated weekly series, re-labelled at the first instant it was public."""
    s = to_weekly(series)
    if s.empty:
        return s
    s.index = relabel_weeks(s.index)
    return s


def _read(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if df.empty or "report_date" not in df.columns:
        return None
    df = df.copy()
    df["report_date"] = pd.to_datetime(df["report_date"], utc=True, errors="coerce")
    return df.dropna(subset=["report_date"])


def _net(df: pd.DataFrame, long_col: str, short_col: str) -> pd.Series | None:
    if long_col not in df.columns or short_col not in df.columns:
        return None
    net = (pd.to_numeric(df[long_col], errors="coerce")
           - pd.to_numeric(df[short_col], errors="coerce"))
    return net.groupby(df["report_date"]).sum(min_count=1).dropna()


def raw_columns(symbol: str) -> dict[str, pd.Series]:
    """{column: Tuesday-dated weekly net, oriented to `symbol`} for every source on disk."""
    spec = SOURCES.get(str(symbol or "").upper())
    if spec is None:
        return {}
    legacy, tff, disagg = spec
    out: dict[str, pd.Series] = {}
    if legacy:
        df = _read(LEGACY / f"{legacy}.parquet")
        if df is not None:
            for col, (lo, sh) in {
                    "noncomm_net": ("noncomm_positions_long_all", "noncomm_positions_short_all"),
                    "comm_net": ("comm_positions_long_all", "comm_positions_short_all")}.items():
                s = _net(df, lo, sh)
                if s is not None and len(s):
                    out[col] = s
    if tff:
        slug, prefixes = tff
        df = _read(TFF / f"{slug}.parquet")
        if df is not None and "market" in df.columns:
            mk = df["market"].astype(str).str.upper()
            df = df[mk.map(lambda m: any(m.startswith(p) for p in prefixes))]
            for col, (lo, sh) in {"lev_net": ("lm_l", "lm_s"), "am_net": ("am_l", "am_s"),
                                  "dealer_net": ("dealer_l", "dealer_s")}.items():
                s = _net(df, lo, sh)
                if s is not None and len(s):
                    out[col] = s
    if disagg:
        df = _read(DISAGG / f"{disagg}.parquet")
        if df is not None:
            for col, (lo, sh) in {
                    "mm_net": ("m_money_positions_long_all", "m_money_positions_short_all"),
                    "swap_net": ("swap_positions_long_all", "swap__positions_short_all")}.items():
                s = _net(df, lo, sh)
                if s is not None and len(s):
                    out[col] = s
    if symbol.upper() in INVERT:
        out = {k: -v for k, v in out.items()}
    return out


def zscore(net: pd.Series) -> pd.Series:
    """The cache's "net" semantics: a 52-week rolling z of the weekly net."""
    mu = net.rolling(ZWIN, min_periods=ZMIN).mean()
    sd = net.rolling(ZWIN, min_periods=ZMIN).std(ddof=0)
    return ((net - mu) / sd.where(sd > 0)).dropna()


def frame(symbol: str) -> pd.DataFrame | None:
    """Every positioning column for `symbol` on the release clock, or None when it has none.

    Includes "net" (the z of legacy non-commercial net) so a tree without the box's cache builds
    the family's default construction instead of refusing it."""
    cols = raw_columns(symbol)
    if not cols:
        return None
    weekly = {k: to_weekly(v) for k, v in cols.items()}
    if "noncomm_net" in cols:
        weekly["net"] = to_weekly(zscore(cols["noncomm_net"]))
    df = pd.DataFrame(weekly).sort_index()
    if df.empty:
        return None
    df[REPORT_WEEK] = [week_ordinal(f) for f in df.index]
    df.index = relabel_weeks(df.index)
    return df


def enrich(base: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """`base` (the cache's one-column frame) with every in-git column joined on the SAME label.

    The base's "net" is never replaced: the cache is the box's authority for that column."""
    extra = frame(symbol)
    if extra is None:
        return base
    extra = extra.drop(columns=[c for c in extra.columns if c in base.columns])
    if extra.empty:
        return base
    # LEFT, so the cache's own rows -- and therefore every default-construction cell already
    # judged on the box -- are byte-identical; a column is only ever ADDED beside them.
    return base.join(extra, how="left")


def available(symbol: str) -> list[str]:
    """Columns `frame(symbol)` will carry (positioning-change columns only, not "net" and not
    the `report_week` key)."""
    return sorted(raw_columns(symbol))
