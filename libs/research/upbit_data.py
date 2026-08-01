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
import urllib.request

_UPBIT = "https://api.upbit.com/v1/candles/days"
_UA = {"User-Agent": "Mozilla/5.0 (quant-desk kimchi)"}


def _key(row: dict) -> str:
    """THE alignment policy, in one place: the candle's label IS its UTC date. No shift."""
    return str(row["candle_date_time_utc"])[:10]


def _fetch(market: str, count: int, to: str, timeout: int) -> list:
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
