#!/usr/bin/env python3
"""DAILY PERP FUNDING, AS A SIDECAR -- the input `funding_stress_reversal` never had.

WHY THE SLEEVE READ FLAT. `crypto_adapter` attaches `MarketSeries.funding` only when the LAKE
frame carries a `funding` column, and `data/lake` holds OHLCV. So the generator degraded to zeros
on every symbol, every run -- honestly, and to no effect: `positioning_crowding_unwind` is one of
the two mechanism sleeves the principal put live, and it has never been able to produce a signal.

`libs/data/crypto_source.daily_with_funding` already fetches this correctly, pagination and all.
Nothing on a schedule called it. A sidecar rather than a lake rebuild: the lake is shared by every
research path and rebuilding it to add one column would re-date artifacts that have nothing to do
with funding, on the day a sleeve needed a series.

**FUNDING IS SIGNED AND THE SIGN IS THE MECHANISM.** Positive funding means LONGS PAY SHORTS --
crowded leverage on the long side, which is the inventory that unwinds on the venue's schedule
rather than the holder's. Flipping it inverts the sleeve into buying exactly what is being forced
out, and it would look like a working strategy with the sign reversed.

**A SYMBOL THAT FAILS IS NAMED, NOT SKIPPED.** A partial collection published as a complete one
gives the sleeve a universe that depends on which requests happened to succeed.

    python scripts/collect_perp_funding.py [--days 400] [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data/perp_funding.json"
_STATUS = _ROOT / "web/perp_funding.json"

#: The sleeve universe. Same symbols the mechanism sleeves trade -- a funding series collected for
#: a different set would leave the sleeve reading zeros on exactly the names it sizes.
SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "LINKUSDT", "ADAUSDT")

#: History depth. `funding_stress_reversal` z-scores over a 30-bar window, so a year gives the
#: estimator many independent windows rather than one long one.
DEFAULT_DAYS = 400


def collect(symbols: tuple[str, ...] = SYMBOLS, days: int = DEFAULT_DAYS) -> dict[str, Any]:
    from libs.data import crypto_source as cs

    start = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    series: dict[str, dict[str, float]] = {}
    failed: dict[str, str] = {}
    for sym in symbols:
        try:
            df = cs.daily_with_funding(sym, start=start)
        except Exception as exc:
            failed[sym] = f"{type(exc).__name__}: {exc}"
            continue
        if df is None or len(df) == 0 or "funding" not in getattr(df, "columns", []):
            failed[sym] = ("returned no funding column -- UNMEASURED, not zero funding. A perp "
                           "with genuinely zero funding still publishes rows")
            continue
        rows: dict[str, float] = {}
        for ts, val in zip(df.index, df["funding"].tolist(), strict=False):
            try:
                rows[str(ts.date() if hasattr(ts, "date") else ts)[:10]] = float(val)
            except (TypeError, ValueError):
                continue
        if rows:
            series[sym] = rows
        else:
            failed[sym] = "funding column present but empty after parsing"

    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "start": start, "days": days,
        "n_symbols": len(series), "n_failed": len(failed),
        "symbols": sorted(series),
        # NAMED, NOT COUNTED. A partial collection published as a complete one gives the sleeve a
        # universe that depends on which requests happened to succeed.
        "failed": failed,
        "sign_convention": ("POSITIVE funding = longs pay shorts = crowded LONG leverage. The "
                            "sleeve fades it. Flipping this sign inverts the sleeve into buying "
                            "what is being forced out, and it would look like a working strategy"),
        "series": series,
    }


def load(symbol: str) -> dict[str, float]:
    """Date -> funding for one symbol. Empty when absent; the CALLER reports that as UNMEASURED,
    because a sleeve that treated missing funding as zero funding would trade a flat signal as a
    real one."""
    try:
        doc = json.loads(_OUT.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    row = (doc.get("series") or {}).get(str(symbol).upper())
    return {str(k): float(v) for k, v in row.items()} if isinstance(row, dict) else {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = collect(days=args.days)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep), "utf-8")
    _STATUS.parent.mkdir(parents=True, exist_ok=True)
    _STATUS.write_text(json.dumps({k: v for k, v in rep.items() if k != "series"}, indent=1),
                       "utf-8")

    if args.json:
        print(json.dumps({k: v for k, v in rep.items() if k != "series"}, indent=1))
        return 0
    print(f"perp funding: {rep['n_symbols']} symbol(s) collected, {rep['n_failed']} failed, "
          f"from {rep['start']}")
    for sym, why in rep["failed"].items():
        print(f"  FAILED {sym:<10} {why[:110]}")
    if rep["symbols"]:
        one = rep["series"][rep["symbols"][0]]
        print(f"  {rep['symbols'][0]}: {len(one)} daily row(s)")
    print(f"-> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
