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
live is stamped at max(rule, first seen):
  * SOFR for business day D is published at 08:00 New York time on the next Federal Reserve
    business day; it is stamped 09:00 New York on that day (federal holidays skipped).
  * HKMA's figures for D are stamped 09:00 Hong Kong time on the next weekday. On a Hong Kong
    holiday the true release is earlier than that, never later, so the error is on the safe side.
A row's `available_time` is the later of its two legs. The FIRST value seen for a date is kept;
a later revision is counted and never back-dated.
"""
from __future__ import annotations

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

def _fed_bday() -> pd.offsets.CustomBusinessDay:
    from pandas.tseries.holiday import USFederalHolidayCalendar
    return pd.offsets.CustomBusinessDay(calendar=USFederalHolidayCalendar())


def sofr_available(day: str) -> pd.Timestamp:
    """09:00 New York on the next Federal Reserve business day after `day`."""
    nxt = pd.Timestamp(day) + _fed_bday()
    return (nxt.normalize() + pd.Timedelta(hours=9)).tz_localize(
        "America/New_York", nonexistent="shift_forward", ambiguous=False).tz_convert("UTC")


def hkma_available(day: str) -> pd.Timestamp:
    """09:00 Hong Kong time on the next weekday after `day`."""
    nxt = pd.Timestamp(day) + pd.offsets.BDay(1)
    return (nxt.normalize() + pd.Timedelta(hours=9)).tz_localize("Asia/Hong_Kong"
                                                                 ).tz_convert("UTC")


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
