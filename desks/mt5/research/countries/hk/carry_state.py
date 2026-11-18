"""HONG KONG CARRY STATE -- HIBOR minus SOFR, the carry of the USDHKD peg, as a USDHKD state.

WHY THIS IS THE STATE THAT MATTERS FOR USDHKD. Under the Linked Exchange Rate System the HKD rate
does not float; the carry does. When HIBOR sits far below SOFR the carry trade sells HKD for USD
and drives USDHKD to the 7.85 weak-side undertaking, where the HKMA buys HKD, the Aggregate Balance
shrinks and HIBOR is pushed back up (`pack.CENTRAL_BANK`). `ABSENT_INSTRUMENTS` recorded the
HIBOR-SOFR spread as UNMEASURED by name; this measures it from two free primary publishers.

WHAT IT PUBLISHES. `data/lake/series/hk_hibor_sofr_carry.parquet` with two signal columns, in
percentage points: `hibor_on_sofr` (overnight HIBOR minus SOFR, both overnight) and
`hibor_1m_sofr` (the HKAB one-month fixing minus SOFR). The `exogenous_conditioner` family reads it
through the culture-gap recipe `hk_hibor_sofr_carry_state` (USDHKD).

SOURCES AND THEIR TERMS (read 2026-11-18; `countries/asia_rv_sources.json` carries the clauses):
  * HKMA Open API, daily figures of interbank liquidity (`hibor_overnight`, `hibor_fixing_1m`).
    HKMA terms clause 17 allows the APIs to be used "whether for commercial or non-commercial
    purposes" to build a system that analyses the Information, on the clause-12 conditions
    (accurate, attributed, not redistributed as our own). HKD HIBOR is owned by HKAB and is NOT in
    the TMA's data-licensing regime (TMA notice, June 2024).
  * New York Fed Markets API, SOFR. The NY Fed terms licence Content "for your personal or
    business purposes", including automated access that does not interfere with the site.

NO LOOKAHEAD. Each value is stamped by a rule that is LATE by construction, and a value first seen
live is stamped at max(rule, first fetch that held it) (`merge_first`):
  * SOFR for business day D is published at 08:00 New York time on the next SIFMA business day;
    it is stamped 09:00 New York on that day. SIFMA, not the Federal Reserve, sets the calendar:
    federal holidays, Good Friday and SIFMA's listed mourning closes are all skipped (mirrors
    `usd_liquidity_primary._next_sifma_day`, #1330). Good Friday is sometimes only an early close,
    when SOFR is published; treating it as closed then stamps a day late, never early.
  * HKMA's figures for D are stamped 09:00 Hong Kong time on the next Hong Kong BUSINESS day:
    weekends and Hong Kong general holidays skipped, from the `holidays` package when it is
    installed and otherwise from the pack's declared table (`pack._HK_HOLIDAYS`). For a year the
    table does not cover the rule takes the fifth weekday after D instead, which is later than any
    Hong Kong holiday run, so an unknown calendar costs freshness and never looks ahead.
A row's `available_time` is the later of its two legs. The FIRST value seen for a date is kept;
a later revision is counted and never back-dated. History read on a backfill pass (rule instant
more than `BACKFILL_AGE` old) is stamped by its rule, which the two calendars above make late.
"""
from __future__ import annotations

import functools
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import pandas as pd

SERIES_ID = "hk_hibor_sofr_carry"
HKMA_URL = ("https://api.hkma.gov.hk/public/market-data-and-statistics/daily-monetary-statistics/"
            "daily-figures-interbank-liquidity")
SOFR_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
SOFR_FIRST = "2018-04-02"          # SOFR's first publication date
HKMA_PAGE = 1000
MIN_ROWS = 30
#: A rule instant older than this is history read on a backfill pass, stamped by its rule.
BACKFILL_AGE = pd.Timedelta(days=3)


# ------------------------------------------------------------------------------ parsers (pure)

def _num(v: Any) -> float | None:
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def parse_hkma(doc: Any) -> tuple[dict[str, dict[str, float]], int | None]:
    """({date: {hibor_on, hibor_1m}}, datasize) from one HKMA API page. Empty on any shape miss."""
    if not isinstance(doc, Mapping):
        return {}, None
    header = doc.get("header") or {}
    if isinstance(header, Mapping) and header.get("success") is False:
        return {}, None
    result = doc.get("result") or {}
    recs = result.get("records") if isinstance(result, Mapping) else None
    out: dict[str, dict[str, float]] = {}
    for r in recs if isinstance(recs, list) else []:
        if not isinstance(r, Mapping):
            continue
        try:
            day = pd.Timestamp(str(r.get("end_of_date"))).date().isoformat()
        except (ValueError, TypeError):
            continue
        row = {k: v for k, v in (("hibor_on", _num(r.get("hibor_overnight"))),
                                 ("hibor_1m", _num(r.get("hibor_fixing_1m"))))
               if v is not None}
        if row:
            out[day] = row
    size = result.get("datasize") if isinstance(result, Mapping) else None
    return out, int(size) if isinstance(size, (int, float)) else None


def parse_sofr(doc: Any) -> dict[str, dict[str, float]]:
    """{date: {sofr}} from the NY Fed reference-rates JSON."""
    rows = doc.get("refRates") if isinstance(doc, Mapping) else None
    out: dict[str, dict[str, float]] = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, Mapping) or str(r.get("type", "SOFR")).upper() != "SOFR":
            continue
        v = _num(r.get("percentRate"))
        try:
            day = pd.Timestamp(str(r.get("effectiveDate"))).date().isoformat()
        except (ValueError, TypeError):
            continue
        if v is not None:
            out[day] = {"sofr": v}
    return out


# ------------------------------------------------------------------------------ stamping rules

#: SIFMA's recommended full closes that are not federal holidays and have no rule (national days
#: of mourning). Good Friday is added by rule. Mirrors #1330's `SIFMA_EXTRA_CLOSES`.
SIFMA_EXTRA_CLOSES: frozenset[str] = frozenset({"2018-12-05", "2025-01-09"})


@functools.lru_cache(maxsize=1)
def _sifma_offset() -> pd.offsets.CustomBusinessDay:
    from pandas.tseries.holiday import GoodFriday, USFederalHolidayCalendar
    lo, hi = pd.Timestamp("2000-01-01"), pd.Timestamp("2100-12-31")
    hol = list(USFederalHolidayCalendar().holidays(start=lo, end=hi))
    hol += list(GoodFriday.dates(lo, hi))
    hol += [pd.Timestamp(x) for x in SIFMA_EXTRA_CLOSES]
    return pd.offsets.CustomBusinessDay(holidays=hol)


def next_sifma_day(day: str) -> pd.Timestamp:
    """The next SIFMA business day after `day` (SOFR is published on SIFMA business days)."""
    return (pd.Timestamp(day) + _sifma_offset()).normalize()


def sofr_available(day: str) -> pd.Timestamp:
    """09:00 New York on the next SIFMA business day after `day`."""
    return (next_sifma_day(day) + pd.Timedelta(hours=9)).tz_localize(
        "America/New_York", nonexistent="shift_forward", ambiguous=False).tz_convert("UTC")


#: Weekdays the rule waits when the year's Hong Kong holidays are not known: longer than any
#: Hong Kong general-holiday run (Lunar New Year or Easter plus a substituted day).
HK_UNKNOWN_YEAR_WEEKDAYS = 5


@functools.lru_cache(maxsize=64)
def hk_holidays(year: int) -> frozenset[str] | None:
    """Hong Kong general holidays for `year` (ISO dates), or None when no calendar covers it."""
    try:
        import holidays as _hol  # optional dependency
        return frozenset(d.isoformat() for d in _hol.country_holidays("HK", years=year))
    except Exception:
        pass
    from research.countries.hk import pack as HKP
    table = HKP._HK_HOLIDAYS.get(int(year))
    return frozenset(table) if table else None


def next_hk_business_day(day: str) -> pd.Timestamp:
    """The next Hong Kong business day after `day`; for a year with no known holiday calendar,
    the fifth weekday after it (later than any holiday run, so never early)."""
    d = pd.Timestamp(day).normalize()
    cand = d + pd.offsets.BDay(1)
    for _ in range(40):
        hol = hk_holidays(cand.year)
        if hol is None:
            return d + pd.offsets.BDay(HK_UNKNOWN_YEAR_WEEKDAYS)
        if cand.date().isoformat() not in hol:
            return cand
        cand = cand + pd.offsets.BDay(1)
    return d + pd.offsets.BDay(HK_UNKNOWN_YEAR_WEEKDAYS)


def hkma_available(day: str) -> pd.Timestamp:
    """09:00 Hong Kong time on the next Hong Kong business day after `day`."""
    return (next_hk_business_day(day) + pd.Timedelta(hours=9)).tz_localize(
        "Asia/Hong_Kong").tz_convert("UTC")


RULES = {"hkma": hkma_available, "sofr": sofr_available}


# ------------------------------------------------------------------------------ the PIT store

def merge_first(store: dict[str, Any], fresh: Mapping[str, Mapping[str, float]], rule: str,
                now: datetime) -> dict[str, int]:
    """Keep the FIRST value per date and field; count revisions; stamp at max(rule, first seen).

    A date whose rule instant is more than `BACKFILL_AGE` before `now` is history (the backfill
    pass) and is stamped by its rule: it was public then. Anything newer is stamped at
    max(rule, now), so a value read early is never stamped before its rule and a value read late
    is never stamped before it was seen. Neither publisher revises these fixings in practice;
    a revision would be counted, and the backfill carries the value as published today."""
    added = revised = 0
    t = pd.Timestamp(now)
    now_ts = t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")
    for day, fields in fresh.items():
        held = store.get(day)
        if held is None:
            ruled = RULES[rule](day)
            at = ruled if ruled < now_ts - BACKFILL_AGE else max(ruled, now_ts)
            store[day] = {"v": dict(fields), "available_time": at.isoformat(),
                          "first_seen": now_ts.isoformat(), "revisions": 0}
            added += 1
            continue
        changed = False
        for k, v in fields.items():
            old = held["v"].get(k)
            if old is None:
                held["v"][k] = v           # a field that was absent is added, not a revision
            elif abs(float(old) - float(v)) > 1e-12:
                changed = True
        if changed:
            held["revisions"] = int(held.get("revisions", 0)) + 1
            revised += 1
    return {"added": added, "revised": revised}


def store_frame(store: Mapping[str, Any]) -> pd.DataFrame:
    rows = [{"day": pd.Timestamp(d), **rec["v"],
             "available_time": pd.Timestamp(rec["available_time"])}
            for d, rec in store.items() if isinstance(rec, Mapping) and "v" in rec]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("day").sort_index()


def carry_frame(hkma: Mapping[str, Any], sofr: Mapping[str, Any]) -> pd.DataFrame:
    """The stamped carry series: dates where both legs exist, stamped at the later leg."""
    h, s = store_frame(hkma), store_frame(sofr)
    if h.empty or s.empty or "sofr" not in s.columns:
        return pd.DataFrame()
    j = h.join(s, how="inner", lsuffix="_h", rsuffix="_s")
    if j.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=j.index)
    if "hibor_on" in j.columns:
        out["hibor_on_sofr"] = j["hibor_on"] - j["sofr"]
    if "hibor_1m" in j.columns:
        out["hibor_1m_sofr"] = j["hibor_1m"] - j["sofr"]
    out = out.dropna(how="all")
    at = pd.concat([pd.to_datetime(j["available_time_h"], utc=True),
                    pd.to_datetime(j["available_time_s"], utc=True)], axis=1).max(axis=1)
    out["event_time"] = pd.to_datetime(out.index).tz_localize("UTC")
    out["available_time"] = at.reindex(out.index)
    return out.reset_index(drop=True)
