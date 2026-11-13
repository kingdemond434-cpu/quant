"""JAPANESE RETAIL FX POSITIONING, FROM THE INDUSTRY'S OWN MONTHLY STATISTICS (FFAJ).

The Financial Futures Association of Japan publishes, every month, the aggregate open long and
short positions that Japanese retail OTC FX customers hold per currency pair, reported by its
member brokers ("店頭FX月次速報", file trading_vol_and_position.xls). Japanese retail is the
largest retail FX crowd in the world, so this is a free, official stand-in for the paid retail
sentiment feeds (IG, OANDA, Myfxbook) the desk could not use under their terms. History runs
from November 2008, one sheet per pair.

TERMS (read on the box 2026-11-13, reports/free_terminal_alternatives/asia/): robots.txt allows
the pages and files; FFAJ's disclaimer holds copyright and asks users to comply with copyright
law, with no bar on automated access or analysis (Japan's Copyright Act art. 30-4 permits
information analysis). The raw file is therefore read and reduced to positioning ratios on the
box and is never committed (the repository is public).

POINT IN TIME. Month m is published around the 15th of month m+1 (September 2026 carried an
update stamp of 2026-10-15), so a month's row is only usable from AVAILABLE_LAG_D days after its
month end.

Sign: `net` is (long - short) / (long + short) in base-currency units, so a positive value means
retail is LONG the pair as quoted (USDJPY > 0: retail long dollars, short yen).
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from typing import Any

import pandas as pd

INDEX = "https://www.ffaj.or.jp/library/performance/fx_flash/"
FILE_RE = re.compile(r'href="([^"]*/wp-content/uploads/[^"]*trading_vol_and_position\.xls)"', re.I)
UA = "quant-desk-research/1.0 (research; robots-respecting)"
AVAILABLE_LAG_D = 20
#: Sheets that are a pair the MT5 universe trades under the same name.
PAIRS = ("USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CHFJPY", "CADJPY", "NZDJPY", "ZARJPY",
         "EURUSD", "GBPUSD")


def _month_end(year: int, month: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def parse_sheet(pair: str, rows: Iterable[list[Any]]) -> list[dict[str, Any]]:
    """One pair's sheet: rows of month, year, then JPY-converted volume/short/long/total and
    the same four in base currency. The base-currency short/long (columns 7, 8) are used when
    present, the JPY ones (3, 4) otherwise; the ratio is the same either way."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if len(r) < 6 or not all(isinstance(r[i], (int, float)) for i in (0, 1, 3, 4)):
            continue
        month, year = int(r[0]), int(r[1])
        if not (1 <= month <= 12 and 2000 <= year <= 2100):
            continue
        short, long_ = float(r[3]), float(r[4])
        if len(r) >= 9 and isinstance(r[7], (int, float)) and isinstance(r[8], (int, float)):
            short, long_ = float(r[7]), float(r[8])
        tot = short + long_
        if tot <= 0:
            continue
        me = _month_end(year, month)
        out.append({"pair": pair, "month_end": me.isoformat(),
                    "available_at": (me + timedelta(days=AVAILABLE_LAG_D)).isoformat(),
                    "long": long_, "short": short, "net": (long_ - short) / tot})
    return out


def parse_workbook(sheets: Iterable[Any]) -> pd.DataFrame:
    """Every PAIRS sheet of a parsed workbook (objects with .name and .rows)."""
    rows: list[dict[str, Any]] = []
    for s in sheets:
        if s.name not in PAIRS:
            continue
        body = s.rows() if callable(s.rows) else s.rows
        rows.extend(parse_sheet(s.name, body))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["pair", "month_end"]).drop_duplicates(["pair", "month_end"],
                                                                 keep="last")


def net_series(df: pd.DataFrame, pair: str) -> pd.Series:
    """The pair's net share indexed by the date it became AVAILABLE (UTC)."""
    if df.empty:
        return pd.Series(dtype="float64")
    sub = df[df["pair"] == pair]
    idx = pd.to_datetime(sub["available_at"], utc=True)
    return pd.Series(sub["net"].to_numpy(dtype=float), index=idx).sort_index()


def fetch(get: Callable[[str], tuple[int | None, bytes]],
          refusal: Callable[[str], str | None]) -> tuple[pd.DataFrame, str]:
    """Find the newest workbook on the index page and parse it. (frame, why-not or "")."""
    why = refusal(INDEX)
    if why:
        return pd.DataFrame(), f"ROBOTS_REFUSED: {why}"
    code, page = get(INDEX)
    if code != 200 or not page:
        return pd.DataFrame(), f"index HTTP {code}"
    links = FILE_RE.findall(page.decode("utf-8", "replace"))
    if not links:
        return pd.DataFrame(), "index carries no trading_vol_and_position.xls link"
    url = links[0] if links[0].startswith("http") else "https://www.ffaj.or.jp" + links[0]
    why = refusal(url)
    if why:
        return pd.DataFrame(), f"ROBOTS_REFUSED: {why}"
    code, blob = get(url)
    if code != 200 or not blob:
        return pd.DataFrame(), f"workbook HTTP {code}"
    from libs.data.xls_reader import read_xls
    try:
        df = parse_workbook(read_xls(blob))
    except Exception as exc:
        return pd.DataFrame(), f"workbook unreadable ({type(exc).__name__})"
    return df, "" if not df.empty else "workbook parsed to 0 rows"


def http_get(url: str) -> tuple[int | None, bytes]:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.status), r.read(20_000_000)
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return None, b""
