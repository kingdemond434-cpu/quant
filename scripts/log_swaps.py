"""Daily broker SWAP-rate logger -- seeds the MT5-native carry sleeve (forward dataset).

MT5 exposes only the CURRENT swap per symbol (no history), so a carry backtest is impossible; the
honest path is to snapshot swaps daily, accumulate our own history, then validate the carry sleeve
forward in shadow. Connects READ-ONLY, snapshots swap_long/swap_short for the cross-asset universe,
converts them to a fractional daily carry (points * point / price), and appends one row per symbol
to data/swap_log.parquet. Schedule daily (e.g. alongside QuantShadow).

    python scripts/log_swaps.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.data.cot_source import COT_MAP

_LOG = Path("data/swap_log.parquet")
# Cross-asset universe to log (carry is meaningful per instrument; reuse the liquid set).
_UNIVERSE = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
    "EURJPY", "GBPJPY", "EURGBP", "AUDJPY",
    "XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XTIUSD", "XBRUSD", "XNGUSD",
    "US500", "US30", "US2000", "UK100", "BTCUSD", "ETHUSD", *COT_MAP,
)


def main() -> None:
    import MetaTrader5 as mt5

    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    acct = mt5.account_info()
    if acct is None or int(acct.trade_mode) != 0:
        mt5.shutdown()
        raise SystemExit("refusing to run: not connected to a DEMO account")

    ts = datetime.now(tz=UTC)
    rows: list[dict[str, object]] = []
    for sym in sorted(set(_UNIVERSE)):
        mt5.symbol_select(sym, True)
        info = mt5.symbol_info(sym)
        tick = mt5.symbol_info_tick(sym)
        if info is None or tick is None or not tick.bid:
            continue
        price = float(tick.bid)
        point = float(info.point) or 1.0
        # Fractional daily carry of holding 1 unit long / short (points * point / price).
        carry_long = float(info.swap_long) * point / price
        carry_short = float(info.swap_short) * point / price
        rows.append({
            "ts": ts, "symbol": sym, "price": price,
            "swap_long": float(info.swap_long), "swap_short": float(info.swap_short),
            "point": point, "swap_mode": int(info.swap_mode),
            "carry_long": carry_long, "carry_short": carry_short,
        })
    mt5.shutdown()
    if not rows:
        raise SystemExit("no swap data captured (terminal cold?)")

    snap = pd.DataFrame(rows)
    if _LOG.exists():
        snap = pd.concat([pd.read_parquet(_LOG), snap], ignore_index=True)
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    snap.to_parquet(_LOG)
    days = snap["ts"].dt.date.nunique()
    print(f"logged {len(rows)} symbols @ {ts.date()} -> {_LOG} "
          f"({len(snap)} rows, {days} distinct days)")
    top = snap[snap["ts"] == snap["ts"].max()].nlargest(6, "carry_long")
    print("highest current long-carry:")
    for _, r in top.iterrows():
        print(f"  {r['symbol']:8} carry_long={r['carry_long']*1e4:+.2f}bps/day "
              f"carry_short={r['carry_short']*1e4:+.2f}bps/day")


if __name__ == "__main__":
    main()
