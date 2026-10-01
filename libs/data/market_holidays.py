"""Thirty-one national settlement calendars: every MT5 instrument knows when its home is shut.

Source: github.com/avhz/RustQuant, crate `RustQuant_time` (MIT OR Apache-2.0, Copyright 2023
avhz; notice in `desks/mt5/data/market_holidays/LICENSE_RustQuant`). The crate was COMPILED and
every weekday 2000-2030 its `Calendar::is_holiday` marks was dumped into
`desks/mt5/data/market_holidays/weekday_holidays.csv`; `meta.json` beside it records the
overrides (Japan 2018-2026 is the desk's own Cabinet Office list, which RustQuant gets wrong on 15
days; EUR is TARGET2 by the ECB's rule) and where each hand-written lunar or Islamic table ends.

WHY IT IS A MECHANISM. On a home-market holiday the local banks, corporates and fixings that
supply a currency's flow are absent: the Tokyo fix does not print, CNH loses its onshore anchor,
a T+2 value date that lands on a holiday rolls. The desk had one calendar (Japan). Every FX leg,
index and commodity on the box now gets one, as a CONDITIONER and a FALSIFIER: a session edge
blamed on a local flow must weaken on that locale's holidays, or the story is wrong.

THREE-VALUED, ON PURPOSE. `is_holiday` answers True, False or None. A listed day is a holiday.
An unlisted day is a business day only inside the calendar's verified span; past the end of a
lunar table (China after 2023, Hong Kong after 2020, ...), or in Turkey (whose religious bayrams
RustQuant never lists) or for a currency with no calendar, an unlisted day is None: UNMEASURED,
never "open".
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "desks" / "mt5" / "data" / "market_holidays"

#: The calendar a currency settles on.
CURRENCY_COUNTRY: dict[str, str] = {
    "USD": "US", "EUR": "EU", "GBP": "GB", "JPY": "JP", "CHF": "CH", "CAD": "CA", "AUD": "AU",
    "NZD": "NZ", "NOK": "NO", "DKK": "DK", "HUF": "HU", "CZK": "CZ", "TRY": "TR", "MXN": "MX",
    "CNH": "CN", "CNY": "CN", "HKD": "HK", "SGD": "SG", "INR": "IN", "IDR": "ID", "ILS": "IL",
    "BRL": "BR", "CLP": "CL", "ARS": "AR", "ISK": "IS", "BWP": "BW",
}
#: Currencies an MT5 pair can carry that no calendar here covers: their leg reads UNMEASURED.
UNCOVERED_CURRENCIES = frozenset({"SEK", "PLN", "ZAR", "RUB", "THB", "KRW", "TWD", "RON", "PHP",
                                  "MYR", "AED", "SAR", "KWD", "QAR", "COP", "PEN", "KES", "NGN"})
#: Index CFDs by the exchange whose holidays shut their cash market (prefix match, upper case).
INDEX_COUNTRY: tuple[tuple[str, str], ...] = (
    ("US", "US"), ("SPX", "US"), ("NAS", "US"), ("NDX", "US"), ("DJ", "US"), ("USTEC", "US"),
    ("UK", "GB"), ("FTSE", "GB"), ("GER", "DE"), ("DE40", "DE"), ("DAX", "DE"), ("FRA", "FR"),
    ("F40", "FR"), ("EU50", "EU"), ("STOXX", "EU"), ("ITA", "IT"), ("NETH", "NL"), ("SWI", "CH"),
    ("JP", "JP"), ("JPN", "JP"), ("NIK", "JP"), ("AUS", "AU"), ("HK", "HK"), ("CHINA", "CN"),
    ("CN50", "CN"), ("CHI", "CN"), ("SING", "SG"), ("SG", "SG"), ("IND", "IN"), ("NIFTY", "IN"),
    ("CA60", "CA"), ("MEX", "MX"), ("BRA", "BR"),
)
#: Metals and energy settle in USD and fix in London.
DOLLAR_COMMODITY = ("XAU", "XAG", "XPT", "XPD", "XTI", "XBR", "XNG", "WTI", "BRENT", "USO",
                    "UKO", "NGAS", "COPPER", "XCU")


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, frozenset[_dt.date]], dict[str, int], frozenset[str], int]:
    days: dict[str, set[_dt.date]] = {}
    with (DATA / "weekday_holidays.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            days.setdefault(r["country"], set()).add(_dt.date.fromisoformat(r["date"]))
    meta = json.loads((DATA / "meta.json").read_text("utf-8"))
    return ({k: frozenset(v) for k, v in days.items()},
            {k: int(v) for k, v in meta["valid_through"].items()},
            frozenset(meta.get("partial", {})), int(meta["generated_through"]))


def countries() -> tuple[str, ...]:
    return tuple(sorted(_load()[0]))


def is_holiday(country: str, d: _dt.date) -> bool | None:
    """True on a listed holiday, False on a verified business weekday, None when unmeasured."""
    days, valid, partial, through = _load()
    if country not in days:
        return None
    if d in days[country]:
        return True
    if d.weekday() >= 5:
        return None                                   # weekends are not this calendar's question
    if country in partial or d.year > valid.get(country, through) or d.year < 2000:
        return None
    return False


def instrument_countries(symbol: str) -> tuple[str | None, ...]:
    """The calendars an MT5 symbol depends on: an FX pair's base and quote (None for a currency
    no calendar covers), an index's exchange, a dollar commodity's US and GB; () when the symbol
    is unclassified."""
    s = symbol.upper().split(".")[0].replace("_", "")
    known = CURRENCY_COUNTRY.keys() | UNCOVERED_CURRENCIES
    if len(s) >= 6 and s[:3] in known and s[3:6] in known:
        return CURRENCY_COUNTRY.get(s[:3]), CURRENCY_COUNTRY.get(s[3:6])
    if s.startswith(DOLLAR_COMMODITY):
        return "US", "GB"
    for prefix, country in INDEX_COUNTRY:
        if s.startswith(prefix):
            return (country,)
    return ()


def _flag(country: str | None, dates: list[_dt.date]) -> np.ndarray:
    if country is None:
        return np.full(len(dates), np.nan)
    out = []
    for d in dates:
        v = is_holiday(country, d)
        out.append(np.nan if v is None else float(v))
    return np.asarray(out, dtype=float)


def _either(legs: tuple[str | None, ...], dates: list[_dt.date]) -> np.ndarray:
    """1 when any leg is shut, 0 when every leg is verifiably open, NaN otherwise."""
    if not legs:
        return np.full(len(dates), np.nan)
    m = np.column_stack([_flag(c, dates) for c in legs])
    out = np.where(np.isnan(m).any(axis=1), np.nan, 0.0)
    return np.where((m == 1.0).any(axis=1), 1.0, out)


def features(index: pd.DatetimeIndex, symbol: str) -> pd.DataFrame:
    """Per bar: is the home / second calendar shut today, will any leg be shut on the next
    weekday (positioning ahead of a holiday), and was any leg shut on the previous weekday (the
    catch-up). Every column is known in advance -- holidays are legislated -- and NaN where the
    calendar cannot say."""
    legs = instrument_countries(symbol)
    idx = pd.DatetimeIndex(index)
    days = sorted({t.date() for t in idx})
    nxt = [d + _dt.timedelta(days=3 if d.weekday() == 4 else 1) for d in days]
    prv = [d - _dt.timedelta(days=3 if d.weekday() == 0 else 1) for d in days]
    daily = pd.DataFrame({
        "hol_home": _flag(legs[0] if legs else None, days),
        "hol_second": _flag(legs[1] if len(legs) > 1 else None, days),
        "hol_next": _either(legs, nxt), "hol_prev": _either(legs, prv)}, index=pd.Index(days))
    return daily.reindex([t.date() for t in idx]).set_axis(idx)
