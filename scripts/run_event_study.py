#!/usr/bin/env python3
"""Run the pre-registered listing event study -- the §39 promotion path, end to end.

    python3 scripts/run_event_study.py

Reads what `run_listing_watch.py` has been collecting, computes each listing's benchmark-adjusted
short-side return over the pre-registered holding window, and puts the panel through the
cross-sectional event-study gate. Writes `data/event_study_listings.json` and prints the verdict.

Freeze-safe and read-only against the market: public klines endpoints, no keys, no orders, no
capital. A verdict of PASS is EVIDENCE, not an allocation -- promotion past that point is the
normal gate's business and real capital is never allocated automatically.

Degrades rather than fails: no log, no network, or an incomplete panel all print an honest
"not yet" and exit 0, because "we do not have the evidence yet" is the correct answer for most of
this study's life and must not read as a broken job.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_FAPI = "https://fapi.binance.com"
_BENCH = "BTCUSDT"
_OUT = ROOT / "data/event_study_listings.json"


def _klines(symbol: str, start_ms: int, end_ms: int) -> list[list[object]]:
    url = (f"{_FAPI}/fapi/v1/klines?symbol={symbol}&interval=1h"
           f"&startTime={start_ms}&endTime={end_ms}&limit=1000")
    req = urllib.request.Request(url, headers={"User-Agent": "quant-event-study"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    return data if isinstance(data, list) else []


def _window_return(symbol: str, t_start: float, hold_h: float) -> float | None:
    """Close-to-close return over the holding window, or None if the window is not complete."""
    start_ms, end_ms = int(t_start * 1000), int((t_start + hold_h * 3600.0) * 1000)
    if end_ms > int(datetime.now(tz=UTC).timestamp() * 1000):
        return None                       # window still open -- not evidence yet
    try:
        bars = _klines(symbol, start_ms, end_ms)
    except Exception:
        return None
    if len(bars) < 2:
        return None
    try:
        first, last = float(str(bars[0][4])), float(str(bars[-1][4]))   # index 4 = close
    except (ValueError, IndexError, TypeError):
        return None                       # a malformed bar is a missing observation, not a zero
    return (last - first) / first if first > 0 else None


def main() -> int:
    from libs.research.listing_events import (
        HOLD_HOURS,
        VARIANTS_TRIED,
        build_events,
        listing_rows,
        qualifying,
        study_listings,
    )

    rows = listing_rows(ROOT / "data/listings.jsonl")
    if not rows:
        print("[event-study] no listings collected yet -- run_listing_watch needs to run first. "
              "The clock has not started; this is not a failure.")
        return 0
    quals = qualifying(rows)
    print(f"[event-study] {len(rows)} listings logged, {len(quals)} in the extreme-funding regime")

    cache: dict[float, float | None] = {}

    def _bench(t_start: float) -> float | None:
        if t_start not in cache:
            cache[t_start] = _window_return(_BENCH, t_start, HOLD_HOURS)
        return cache[t_start]

    events = build_events(rows, lambda s, t: _window_return(s, t, HOLD_HOURS), _bench)
    res = study_listings(events)
    _OUT.write_text(json.dumps({
        "as_of": datetime.now(tz=UTC).isoformat(),
        "hypothesis": ("SHORT a new USDT perp whose day-1 funding >= threshold, held "
                       f"{HOLD_HOURS:.0f}h, benchmark-adjusted vs {_BENCH}"),
        "variants_tried": VARIANTS_TRIED,
        "n_logged": len(rows), "n_qualifying": len(quals),
        **res.model_dump(),
    }, indent=2), "utf-8")
    print(f"[event-study] {res.verdict}")
    print(f"[event-study] wrote {_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
