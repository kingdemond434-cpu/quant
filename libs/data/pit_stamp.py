"""Point-in-time stamps for collected SERIES (frames): when could the desk have KNOWN a row?

The row-level stamp already exists (`libs.data.pit.stamp` / `usable_at`, wired into every
proposer donation). This is the same doctrine applied to a parsed TABLE from a collected source,
where the availability of each row is not the fetch time but the row's own period plus the
source's declared publication lag. The column names are the row stamp's (`STAMP_FIELDS`), so a
frame row and a donation row answer `usable_at` the same way.

THE DEFECT THIS PREVENTS. A monthly customs figure describes July and is published on the 20th
of August. Join it to price data by the month it DESCRIBES and every backtest that conditions on
it sees July's number in July -- three weeks before anyone could have. The conditioner looks
brilliant and is unreproducible live. The collector vaults bytes with a FETCH timestamp, which is
an honest bound going forward; backfilled history fetched today carries today's fetch time, so
without a publication-lag model there is no honest way to backtest it at all.

THREE FIELDS PER ROW, ALWAYS TOGETHER:

    event_time      the last instant the row DESCRIBES (the reference month's last day, the
                    week's Friday, the print's own date)
    available_time  the first instant the desk could have read it: event_time + the source's
                    declared `publication_lag_days` (registry `pit.publication_lag_days`, else
                    a conservative default by cadence)
    ingested_time   when THIS box actually fetched the bytes (the vault's `fetched_utc`) -- the
                    vintage; revisions are a new vault blob with a new ingested_time, never an
                    overwrite

A consumer joins on `available_time`, never on `event_time`. A frame with no recognisable date
column is stamped UNSTAMPED with the reason, which is a real answer -- it means the series may
not be used point-in-time until someone names its period column.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

#: Conservative publication lag by declared cadence, used only when the registry row declares
#: none. Monthly official statistics arrive two to three weeks after the month; weekly a few
#: days after the week; a daily print is the same evening, usable next day.
DEFAULT_LAG_DAYS: dict[str, int] = {
    "hourly": 0, "daily": 1, "weekly": 3, "10-daily": 5, "monthly": 20, "quarterly": 45,
    "on demand": 1, "on change": 1, "monthly announcement, daily execution": 1,
}
FALLBACK_LAG_DAYS = 20

#: Column names that name a period, in preference order, matched case-insensitively.
PERIOD_COLUMNS: tuple[str, ...] = (
    "period_end", "period", "date", "time", "datetime", "timestamp", "month", "week", "day",
    "as_of", "asof", "reference_period", "ref_month", "trade_date", "settlement_date", "日期",
    "月份", "时间", "统计日期",
)


def lag_for(source: dict[str, Any] | None) -> tuple[int, str]:
    """(publication lag in days, how it was decided) for a registry row."""
    if not isinstance(source, dict):
        return FALLBACK_LAG_DAYS, f"no registry row: fallback {FALLBACK_LAG_DAYS}d"
    pit = source.get("pit")
    if isinstance(pit, dict):
        raw = pit.get("publication_lag_days")
        if raw is not None:
            try:
                return max(0, int(raw)), "declared in the registry's pit block"
            except (TypeError, ValueError):
                pass
    cadence = str(source.get("cadence") or "").strip().lower()
    if cadence in DEFAULT_LAG_DAYS:
        return DEFAULT_LAG_DAYS[cadence], f"default for cadence {cadence!r}"
    return FALLBACK_LAG_DAYS, f"no pit block and unknown cadence {cadence!r}: fallback"


def available_at(period_end: datetime | date, lag_days: int) -> datetime:
    """The first UTC instant a row describing `period_end` could have been read."""
    if isinstance(period_end, datetime):
        base = period_end if period_end.tzinfo else period_end.replace(tzinfo=UTC)
    else:
        base = datetime(period_end.year, period_end.month, period_end.day, tzinfo=UTC)
    return base + timedelta(days=int(lag_days))


def find_period_column(columns: Any) -> str | None:
    """The column that names the row's period, or None."""
    names = [str(c) for c in columns]
    lower = {n.lower().strip(): n for n in names}
    for want in PERIOD_COLUMNS:
        if want in lower:
            return lower[want]
    for n in names:
        low = n.lower()
        if "date" in low or "period" in low or low.endswith("time"):
            return n
    return None


#: A period written the way the source's own country writes it. MEASURED 2026-09-23: all 23
#: sources the parser had turned into frames were UNSTAMPED -- 'no column names a period' on the
#: frames whose header row pandas read as data, and "only 0% of 'Date' parses" on the Chinese and
#: compact-integer ones. Neither is a missing period; both are a period this function had never
#: been taught to read. Coercion is tried in this order and the first that parses >= the share
#: threshold wins. It only ever STAMPS MORE FRAMES -- a frame that stamped before still stamps.
def _coerce_periods(col: Any) -> Any:
    """Parse a column of periods written in any shape this desk's sources actually publish.

    Plain ISO first (the common case, and pandas already handles it), then: CJK dates
    (2026年9月15日 / 2026年9月 / 令和-free), compact integers (20260915, 202609), ISO months
    (2026-09), quarters (2026Q3 / 2026年第3季度) and Excel day serials. Never raises; a column
    that parses as nothing comes back all-NaT and the caller reports UNSTAMPED.
    """
    import re

    import pandas as pd
    s = col.astype("string").str.strip()
    out = pd.to_datetime(s, errors="coerce", utc=True, format="mixed")
    miss = out.isna()
    if not bool(miss.any()):
        return out

    def _try(conv: Any, fmt: str | None = None) -> None:
        nonlocal out, miss
        if not bool(miss.any()):
            return
        try:
            got = conv(s[miss])
        except Exception:
            return
        # An explicit format on every fallback: pandas emits a UserWarning when it has to infer
        # per element, and this desk runs its suite with `filterwarnings = error`, so an inferred
        # parse here is a test failure rather than a note.
        got = (pd.to_datetime(got, errors="coerce", utc=True, format=fmt) if fmt
               else pd.to_datetime(got, errors="coerce", utc=True))
        out = out.where(~miss, got)
        miss = out.isna()

    # CJK y/m/d, with or without the day: 2026年9月15日, 2026年9月, 2026年09月15日
    cjk = re.compile(r"(\d{4})\s*[年/.-]\s*(\d{1,2})(?:\s*[月/.-]\s*(\d{1,2}))?")
    def _cjk(v: Any) -> Any:
        ex = v.str.extract(cjk)
        return (ex[0] + "-" + ex[1].str.zfill(2) + "-" + ex[2].fillna("01").str.zfill(2))
    _try(_cjk, "%Y-%m-%d")
    # Quarters: 2026Q3, 2026年第3季度, 2026-Q3
    quart = re.compile(r"(\d{4})\D{0,3}[Qq季]\D{0,2}(\d)")
    def _q(v: Any) -> Any:
        ex = v.str.extract(quart)
        mon = (ex[1].astype("Float64") * 3).astype("Int64").astype("string").str.zfill(2)
        return ex[0] + "-" + mon + "-01"
    _try(_q, "%Y-%m-%d")
    # Compact integers: 20260915, 202609, 2026
    def _compact(v: Any) -> Any:
        d = v.str.replace(r"\D", "", regex=True)
        return (d.where(d.str.len() == 8).pipe(pd.to_datetime, format="%Y%m%d", errors="coerce")
                .fillna(d.where(d.str.len() == 6)
                        .pipe(pd.to_datetime, format="%Y%m", errors="coerce"))
                .fillna(d.where(d.str.len() == 4)
                        .pipe(pd.to_datetime, format="%Y", errors="coerce")))
    _try(_compact)
    # Excel day serials (1900 epoch): a plain number between 20000 (1954) and 60000 (2064).
    def _excel(v: Any) -> Any:
        n = pd.to_numeric(v, errors="coerce")
        n = n.where((n > 20_000) & (n < 60_000))
        return pd.to_datetime(n, unit="D", origin="1899-12-30", errors="coerce")
    _try(_excel)
    return out


def period_column_by_value(df: Any, *, min_share: float = 0.8) -> tuple[str | None, Any]:
    """The column whose VALUES are periods, when no column NAME says so.

    A table scraped out of an HTML page names its columns 0, 1, 2 or repeats the header text in
    every cell; the dates are still there. This scans every column, coerces it, and returns the
    one with the highest parse share at or above `min_share`, preferring the leftmost on a tie
    because a period column is conventionally first. Returns (name, parsed) or (None, None).
    """
    best: tuple[float, str, Any] | None = None
    for i, name in enumerate(list(df.columns)):
        try:
            parsed = _coerce_periods(df[name])
        except Exception:
            continue
        if parsed is None or not len(parsed):
            continue
        share = float(parsed.notna().mean())
        if share >= min_share and (best is None or share > best[0] + 1e-9):
            best = (share, str(name), parsed)
        elif best is not None and share >= min_share and abs(share - best[0]) <= 1e-9:
            _ = i  # leftmost already held; nothing to do
    if best is None:
        return None, None
    return best[1], best[2]


#: The full point-in-time envelope every stamped observation carries (blueprint item 2,
#: 2026-09-16). The three original fields are measured; the four added ones are either aliases
#: of measured fields (published_time = the modelled publication instant, retrieval_time = the
#: fetch instant) or DECLARED by the caller (source_id, vintage_id) -- an undeclared one is None,
#: never invented, and `meta["undeclared"]` names it.
PIT_FIELDS: tuple[str, ...] = ("event_time", "published_time", "available_time", "revision_time",
                               "retrieval_time", "ingested_time", "source_id", "vintage_id")


def vintage_id_for(source_id: str | None, ingested_time: str | None,
                   payload: Any = None) -> str | None:
    """One id per (source, fetch) blob: sha1 of source|fetch|payload-size, 16 hex. None when the
    fetch instant is unknown -- a vintage without a fetch time is not a vintage."""
    if not ingested_time:
        return None
    import hashlib
    size = ""
    try:
        size = str(len(payload)) if payload is not None else ""
    except TypeError:
        size = ""
    raw = f"{source_id or ''}|{ingested_time}|{size}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


def stamp_frame(df: Any, *, lag_days: int, observed_at: str | datetime | None,
                source_id: str | None = None, vintage_id: str | None = None,
                revision_time: str | datetime | None = None,
                vintage_fallback: bool = False,
                ) -> tuple[Any, dict[str, Any]]:
    """Add the point-in-time envelope to a DataFrame when a period column exists.

    event_time / available_time / ingested_time as before, plus published_time (= the modelled
    publication instant, event_time + lag), retrieval_time (= ingested_time), revision_time (the
    caller's, or None), source_id and vintage_id (declared or derived from source + fetch).
    Returns (frame, meta). Never raises; an unstampable frame comes back unchanged with
    `meta["status"] == "UNSTAMPED"` and the reason.
    """
    import pandas as pd

    meta: dict[str, Any] = {"lag_days": int(lag_days), "ingested_time": None}
    if observed_at is not None:
        meta["ingested_time"] = (observed_at.isoformat() if isinstance(observed_at, datetime)
                                 else str(observed_at))
    meta["source_id"] = source_id
    meta["vintage_id"] = vintage_id or vintage_id_for(source_id, meta["ingested_time"], df)
    meta["revision_time"] = (revision_time.isoformat() if isinstance(revision_time, datetime)
                             else (str(revision_time) if revision_time else None))
    meta["undeclared"] = [k for k in ("source_id", "vintage_id", "revision_time")
                          if meta.get(k) is None]
    # THE NAME FIRST, THEN THE VALUES. A named column that parses is the cheapest and most
    # honest answer; when there is no such name, or the named one does not parse, the periods are
    # still in the table and `period_column_by_value` finds them. MEASURED 2026-09-23: this is
    # the whole difference between 0 and N stamped frames on the collected source lake -- every
    # one of the 23 parsed sources failed here, none of them for want of a date.
    col = find_period_column(df.columns)
    parsed = None
    share = 0.0
    basis = "column name"
    if col is not None:
        try:
            parsed = _coerce_periods(df[col])
            share = float(parsed.notna().mean()) if len(parsed) else 0.0
        except Exception:
            parsed, share = None, 0.0
    if share < 0.8:
        alt, alt_parsed = period_column_by_value(df)
        if alt is not None and alt_parsed is not None:
            col, parsed, basis = alt, alt_parsed, "column values"
            share = float(parsed.notna().mean()) if len(parsed) else 0.0
    if col is None or parsed is None:
        meta.update({"status": "UNSTAMPED", "why": "no column names a period (date/period/...) "
                     "and no column's values parse as periods", "period_column": None})
        return df, meta
    if share < 0.8:
        meta.update({"status": "UNSTAMPED", "period_column": col,
                     "why": f"only {share:.0%} of {col!r} parses as a date"})
        return df, meta
    meta["period_basis"] = basis
    out = df.copy()
    out["event_time"] = parsed
    out["available_time"] = parsed + pd.Timedelta(days=lag_days)
    out["ingested_time"] = meta["ingested_time"]
    out["published_time"] = out["available_time"]
    out["retrieval_time"] = meta["ingested_time"]
    out["revision_time"] = meta["revision_time"]
    out["source_id"] = meta["source_id"]
    out["vintage_id"] = meta["vintage_id"]
    meta.update({"status": "STAMPED", "period_column": col, "n": len(out),
                 "fields": list(PIT_FIELDS),
                 "parsed_share": round(share, 3),
                 "first_period": str(parsed.min())[:19] if len(parsed) else None,
                 "last_period": str(parsed.max())[:19] if len(parsed) else None})
    return out, meta
