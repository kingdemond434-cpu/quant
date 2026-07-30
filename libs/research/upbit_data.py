"""Upbit daily candles, keyed by CLOSE date -- the ONE copy of the alignment policy.

WHY THIS MODULE EXISTS (2026-07-29). Two scripts each carried their own Upbit keying --
collect_kimchi_premium.py and revalidate_clocks.py -- and when the alignment leak was found and
fixed in the collector, the revalidator silently kept measuring the leaky join and printed the
same inflated IC as if nothing had changed. Two copies of one policy is the flat-$100k-floor
failure class (§42) arriving in the data layer: fixing one copy MOVES the bug, it does not remove
it. Both scripts now import this function; a third copy anywhere is a defect.

THE ALIGNMENT LEAK ITSELF. Upbit's `candle_date_time_utc` is the OPEN timestamp of a KST-day
candle. A KST day opens 15:00 UTC the previous calendar day, so keying by open-date labels every
close ~15h EARLY: key D carried a close taken at 15:00 UTC on D+1, and a "forward" screen of
signal[D] against the UTC-day D+1 return was ~62% contemporaneous overlap, not prediction. The
shift test exposed it (+1d cell 0.823 vs 0d 0.225; the honest no-overlap cell +0.018). Keying by
CLOSE date -- open + 1 day -- gives signal[K] information only up to 15:00 UTC on K, and a screen
against the K+1 UTC-day return has a 9h standoff instead of a 15h leak.

LIVE forward-clock rows were never affected: at collection time only completed candles exist, so
appended z-scores are honest by construction. The leak lived solely in HISTORICAL reconstruction,
which is exactly where celebrated backtest ICs come from -- reality (the accruing clock) stays
the arbiter, per constitution.
"""
from __future__ import annotations

import datetime as _dt
import json
import urllib.request

_UPBIT = "https://api.upbit.com/v1/candles/days"
_UA = {"User-Agent": "Mozilla/5.0 (quant-desk kimchi)"}


def upbit_daily_close_keyed(market: str = "KRW-BTC", count: int = 200,
                            timeout: int = 35) -> dict[str, float]:
    """{UTC close-date: trade_price} for Upbit KST-day candles. See module docstring."""
    req = urllib.request.Request(f"{_UPBIT}?market={market}&count={count}", headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        rows = json.loads(r.read())
    if not isinstance(rows, list):
        return {}
    out: dict[str, float] = {}
    for r_ in rows:
        d = _dt.date.fromisoformat(str(r_["candle_date_time_utc"])[:10]) + _dt.timedelta(days=1)
        out[d.isoformat()] = float(r_["trade_price"])
    return out
