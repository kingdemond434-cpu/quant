"""Upbit daily candles keyed by their UTC date -- the ONE copy of the alignment policy.

WHY THIS MODULE EXISTS (2026-07-29). Several scripts each carried their own Upbit keying, and when
the join was "fixed" in one, the others silently kept measuring the old one and printed the same
numbers as if nothing had changed. Two copies of one policy is the flat-$100k-floor failure class
(§42) arriving in the data layer: fixing one copy MOVES the bug, it does not remove it. Every
consumer imports from here; a second copy anywhere fails tests/governance/test_upbit_single_source.

THE BOUNDARY, MEASURED FROM PRIMARY DATA (prospector 2026-07-30, re-derived 2026-08-01).
Upbit day candles are UTC-MIDNIGHT-boundary. The candle labelled `candle_date_time_utc = D` opens
00:00 UTC D and closes 24:00 UTC D, so its label is simultaneously its open date and its close
date, and NO SHIFT IS CORRECT. Two independent confirmations, both from Upbit's own data:

  * The two stamps are one instant in two zones: `candle_date_time_utc=2026-07-31T00:00:00` carries
    `candle_date_time_kst=2026-07-31T09:00:00` (00:00 UTC == 09:00 KST). A KST-DAY candle would
    read utc=2026-07-30T15:00:00 / kst=2026-07-31T00:00:00. It does not.
  * `trade_price` matches Upbit's OWN hourly close at 24:00 UTC D to the won -- checked on
    2026-07-30, 2026-07-31 (this module's test) and 2026-07-28, 2021-05-19 (prospector, two eras)
    -- and differs from the 15:00 UTC price on every one of them.

Reproduce in ~5s, no key:  .venv/bin/python -m pytest tests/research/test_upbit_boundary.py

THE 2026-07-29 REGRESSION, RECORDED SO IT CANNOT RETURN. This module originally shipped a
`+ 1 day` shift, on the belief that `candle_date_time_utc` was a KST-day OPEN stamp labelling
closes ~15h early. That belief was imported from bithumb_kr_premium_lookahead -- a REAL kill, on a
DIFFERENT venue whose 24h candle genuinely IS KST-day-open. UPBIT IS NOT BITHUMB, and the premise
was never measured before it became canon. The shift removed no leak; it paired a 24:00-UTC-D
Upbit leg against a 24:00-UTC-(D+1) Binance leg, and the resulting "premium" was 24h-mispaired:
corr(premium, -r_binance) = +0.813 at 2.98% std and a +-17% range, against +0.122 / 1.40% / +-4%
for the same-instant join. data/kimchi_premium.jsonl rows dated 2026-07-29..2026-08-01 were
collected under it and are quarantined to data/kimchi_premium.quarantined.jsonl.

LIVE forward-clock rows were never affected by the ORIGINAL (pre-07-29) keying: at collection time
only completed candles exist. The 07-29..08-01 window is the exception -- reality stays the arbiter
only when the legs it is built from are the same instant.
"""
from __future__ import annotations

import json
import time as _time
import urllib.error
import urllib.request
from typing import Any

_UPBIT = "https://api.upbit.com/v1/candles/days"
_UA = {"User-Agent": "Mozilla/5.0 (quant-desk kimchi)"}


def _key(row: dict[str, Any]) -> str:
    """THE alignment policy, in one place: the candle's label IS its UTC date. No shift."""
    return str(row["candle_date_time_utc"])[:10]


def _fetch(market: str, count: int, to: str, timeout: int) -> list[dict[str, Any]]:
    url = f"{_UPBIT}?market={market}&count={count}"
    if to:
        url += f"&to={to}"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rows = json.loads(r.read())
    return rows if isinstance(rows, list) else []


def upbit_daily_utc_keyed(market: str = "KRW-BTC", count: int = 200,
                          timeout: int = 35) -> dict[str, float]:
    """{UTC date: trade_price} for the most recent `count` Upbit day candles.

    Same-instant with a Binance UTC daily close: both legs are the 24:00 UTC print of that date.
    See the module docstring for the primary-data boundary proof.
    """
    return {_key(r): float(r["trade_price"]) for r in _fetch(market, count, "", timeout)}


def upbit_daily_history(market: str = "KRW-BTC", pages: int = 40, timeout: int = 35,
                        pause: float = 0.15) -> dict[str, float]:
    """{UTC date: trade_price} walked back via the `to=` cursor -- the deep-history form.

    Same keying as upbit_daily_utc_keyed(), because it is literally the same `_key`: the deep
    backfill re-deriving its own join is how a keying fix reaches the live collector and misses
    the history it is compared against. A partial walk is announced and returned, never silently
    truncated -- pagination truncation is the failure mode that never throws.
    """
    out: dict[str, float] = {}
    cursor = ""
    for _ in range(pages):
        try:
            rows = _fetch(market, 200, cursor, timeout)
        except Exception as e:                       # loud, never silent: partial history is usable
            print(f"  upbit page failed ({e!r}) -- stopping at {len(out)} rows")
            break
        if not rows:
            break
        for r in rows:
            out[_key(r)] = float(r["trade_price"])
        cursor = str(rows[-1]["candle_date_time_utc"])
        _time.sleep(pause)                           # courtesy: Upbit allows ~10 req/s
    return out


_MARKETS_URL = "https://api.upbit.com/v1/market/all?isDetails=true"


def candle_key(row: dict[str, Any]) -> str:
    """The venue's FULL candle stamp (ISO, lexicographically ordered) -- the raw-row key.

    Raw-row consumers (the R0303 snapshot) compare and store this string; joins slice it to a
    date via `_key`. Kept here so the alignment policy and the storage key are one field read
    in one module -- the single-source fence pins every executable use of the field name here.
    """
    return str(row["candle_date_time_utc"])


def fetch_markets(timeout: int = 35) -> list[dict[str, Any]]:
    """All Upbit markets with venue flags (/v1/market/all?isDetails=true). Raises on failure:
    an unreachable universe must never read as an empty universe (L1.28a)."""
    req = urllib.request.Request(_MARKETS_URL, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rows = json.loads(r.read())
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"upbit market list malformed/empty ({type(rows).__name__})")
    return rows


def _fetch_raw(path: str, market: str, count: int, to: str, timeout: int) -> list[dict[str, Any]]:
    """One raw candle page from /v1/candles/{path}, with a bounded 429 backoff."""
    url = f"https://api.upbit.com/v1/candles/{path}?market={market}&count={count}"
    if to:
        url += f"&to={to}"
    req = urllib.request.Request(url, headers=_UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                rows = json.loads(r.read())
            return rows if isinstance(rows, list) else []
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:          # venue backpressure: honour it, bounded
                _time.sleep(1.5 * (attempt + 1))
                continue
            raise
    return []                                          # unreachable; keeps mypy honest


def walk_candles_raw(market: str, *, path: str = "days", stop_before_key: str = "",
                     exclude_from_key: str = "", max_pages: int = 400, timeout: int = 35,
                     pause: float = 0.12) -> tuple[list[dict[str, Any]], bool]:
    """FULL raw candle rows for `market`, walked back via the `to=` cursor.

    Returns (rows ASCENDING by venue stamp, complete). Rows with key <= `stop_before_key`
    (already stored) and >= `exclude_from_key` (the in-progress candle: storing a partial row
    as final is the L1.46 class) are dropped. `complete=False` means a page failed or
    `max_pages` was hit -- the partial is returned LOUDLY, never silently truncated: pagination
    truncation is the failure mode that never throws.
    """
    out: dict[str, dict[str, Any]] = {}
    cursor = ""
    complete = True
    for page in range(max_pages):
        try:
            rows = _fetch_raw(path, market, 200, cursor, timeout)
        except Exception as e:
            print(f"  upbit {path} walk {market} page {page} failed ({e!r}) -- "
                  f"partial at {len(out)} rows")
            complete = False
            break
        if not rows:
            break                                      # history exhausted: a genuine end
        oldest = min(candle_key(r) for r in rows)
        for r in rows:
            k = candle_key(r)
            if (not stop_before_key or k > stop_before_key) \
                    and (not exclude_from_key or k < exclude_from_key):
                out[k] = r
        if stop_before_key and oldest <= stop_before_key:
            break                                      # reached what is already stored
        if cursor == oldest:
            break                                      # cursor stalled: history exhausted
        cursor = oldest
        _time.sleep(pause)                             # courtesy: Upbit allows ~10 req/s
    else:
        complete = False
        print(f"  upbit {path} walk {market}: max_pages={max_pages} hit -- partial, "
              f"no silent cap (L1.57)")
    return [out[k] for k in sorted(out)], complete


def upbit_hourly_utc(market: str = "KRW-BTC", count: int = 200, to: str = "",
                     timeout: int = 35) -> dict[str, float]:
    """{`YYYY-MM-DDTHH:00:00` UTC bar-open: trade_price} for 60m candles.

    Exists so the daily boundary is checkable from Upbit's OWN primary data rather than asserted:
    the bar opening 23:00 UTC on D closes at 24:00 UTC D and must equal the D daily close.
    """
    url = f"https://api.upbit.com/v1/candles/minutes/60?market={market}&count={count}"
    if to:
        url += f"&to={to}"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rows = json.loads(r.read())
    if not isinstance(rows, list):
        return {}
    return {str(x["candle_date_time_utc"]): float(x["trade_price"]) for x in rows}
