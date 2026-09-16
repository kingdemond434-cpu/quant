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


def stamp_frame(df: Any, *, lag_days: int, observed_at: str | datetime | None,
                ) -> tuple[Any, dict[str, Any]]:
    """Add event_time / available_time / ingested_time to a DataFrame when a period column exists.

    Returns (frame, meta). Never raises; an unstampable frame comes back unchanged with
    `meta["status"] == "UNSTAMPED"` and the reason.
    """
    import pandas as pd

    meta: dict[str, Any] = {"lag_days": int(lag_days), "ingested_time": None}
    if observed_at is not None:
        meta["ingested_time"] = (observed_at.isoformat() if isinstance(observed_at, datetime)
                                 else str(observed_at))
    col = find_period_column(df.columns)
    if col is None:
        meta.update({"status": "UNSTAMPED", "why": "no column names a period (date/period/...)",
                     "period_column": None})
        return df, meta
    try:
        parsed = pd.to_datetime(df[col], errors="coerce", utc=True)
    except Exception as exc:
        meta.update({"status": "UNSTAMPED", "why": f"{col!r} does not parse as dates: "
                     f"{type(exc).__name__}", "period_column": col})
        return df, meta
    share = float(parsed.notna().mean()) if len(parsed) else 0.0
    if share < 0.8:
        meta.update({"status": "UNSTAMPED", "period_column": col,
                     "why": f"only {share:.0%} of {col!r} parses as a date"})
        return df, meta
    out = df.copy()
    out["event_time"] = parsed
    out["available_time"] = parsed + pd.Timedelta(days=lag_days)
    out["ingested_time"] = meta["ingested_time"]
    meta.update({"status": "STAMPED", "period_column": col, "n": len(out),
                 "parsed_share": round(share, 3),
                 "first_period": str(parsed.min())[:19] if len(parsed) else None,
                 "last_period": str(parsed.max())[:19] if len(parsed) else None})
    return out, meta
