"""Incremental tail refresh for cached MT5 universe parquets.

Fetches only recent bars per symbol, appends new CLOSED bars to the
existing parquet, dedupes by timestamp, saves in-place.
Also records the MT5 server name so the VPS can verify promotion_authority.
Run on the Windows box where MetaTrader5 is available.
"""

import json
import sys
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk.config import desk_root, terminal_path

TERMINAL = terminal_path()
# PATHS COME FROM `desk_root()`, NEVER A USERNAME (LAWS §1 anti-hardcode; the helper's own
# docstring records that twenty-one files hardcoded `C:\\Users\\dell\\...`, "which meant the desk
# could only ever run on one machine under one username"). This one never adopted it, so on the
# trading box it targeted a directory that does not exist -- which is why NOTHING on that box
# refreshes its bars and most of its 295 parquets were ~28h stale on 2026-08-27. `MT5_DESK_ROOT`
# still overrides, so a machine keeping its store elsewhere sets one env var.
OUT = desk_root() / "data" / "universe"
N_BARS = 200


def refresh_symbol(sym: str) -> str:
    pq = OUT / f"{sym}_H1.parquet"
    if not pq.exists():
        return "no-cache"
    old = pd.read_parquet(pq)
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, N_BARS)
    if rates is None or len(rates) < 2:
        return f"fetch-fail({mt5.last_error()})"
    new = pd.DataFrame(rates)
    new["time"] = pd.to_datetime(new["time"], unit="s", utc=True)
    new = new.set_index("time").sort_index()
    # drop the still-forming bar
    new = new.iloc[:-1]
    new = new[["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
    # A TZ-NAIVE CACHE FILE WOULD BE CORRUPTED BY THIS CONCAT, NOT MERELY REFUSED. Joining a
    # naive DatetimeIndex to an aware one yields an object-dtype index, and `to_parquet` would
    # then write a file no reader can use -- destroying the history it was called to extend.
    # Measured 2026-08-27: 173 of 197 parquets in this desk's tree were tz-naive, because five
    # bulk downloaders called `to_datetime(..., unit="s")` without `utc=True`. The label is
    # RESTORED, not assumed: every file here comes from MT5 `rates["time"]`, which is UNIX EPOCH
    # SECONDS, so the instants are unambiguous and no server offset can apply -- the same
    # provenance argument `h1_source` already relies on.
    if isinstance(old.index, pd.DatetimeIndex) and old.index.tz is None:
        old = old.copy()
        old.index = old.index.tz_localize("UTC")
    combined = pd.concat([old, new])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    added = len(combined) - len(old)
    combined.to_parquet(pq)
    return f"+{added} bars (last {combined.index.max()})"


def main() -> int:
    """0 = refreshed, 2 = no terminal on this box (an honest answer, not a failure).

    RETURNS, NEVER `sys.exit`. This is called as a daily-cycle step, and `SystemExit` is a
    BaseException: a bare exit here would tear down the entire cycle -- promotion chain included
    -- because a terminal was shut, rather than skipping one step.
    """
    if mt5.terminal_info() is None and not mt5.initialize(path=TERMINAL):
        print(f"initialize failed: {mt5.last_error()}")
        return 2

    # Record broker server for promotion_authority on VPS
    account = mt5.account_info()
    server_name = getattr(account, "server", "unknown") if account else "unknown"
    is_fusion = "fusion" in server_name.lower()
    print(f"Broker server: {server_name} (Fusion={is_fusion})")

    results = []
    broker_info = {}
    for pq in sorted(OUT.glob("*_H1.parquet")):
        sym = pq.stem.replace("_H1", "")
        try:
            status = refresh_symbol(sym)
        except Exception as e:
            status = f"error:{e}"
        results.append(f"{sym:8s} {status}")
        print(results[-1], flush=True)
        # Record server for this symbol
        info = mt5.symbol_info(sym)
        if info:
            broker_info[sym] = {
                "server": server_name,
                "is_fusion": is_fusion,
                "account": getattr(account, "login", 0) if account else 0,
            }
    ok = sum(1 for r in results if r.split(None, 1)[1].startswith("+"))
    print(f"\n{ok}/{len(results)} symbols refreshed")

    # Save broker info for VPS promotion_authority
    broker_info_path = OUT / "broker_info.json"
    broker_info_path.write_text(json.dumps({
        "server": server_name,
        "is_fusion": is_fusion,
        "account": getattr(account, "login", 0) if account else 0,
        "symbols": broker_info,
    }, indent=2), encoding="utf-8")
    print(f"Broker info saved: {server_name}")

    mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
