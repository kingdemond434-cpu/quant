"""Fetch H1 history for the MT5 research universe (2018 -> now) and cache it.

Per-symbol cost model recorded (contract size, tick value, median spread).
Run with the VIG terminal logged in.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# THE PATH INSERT MUST PRECEDE THE IMPORT IT ENABLES. This module imported mt5desk.config on the
# line ABOVE the sys.path.insert that makes mt5desk importable, so it only ever worked when the
# process happened to start with desks/mt5 already on the path -- i.e. when the cwd was right.
# Run as `python research/fetch_universe.py` from desks/mt5 it dies with ModuleNotFoundError, and
# that is the documented way to run it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import MetaTrader5 as mt5
import pandas as pd
from mt5desk.config import DATA, REPORTS, desk_root, terminal_path  # noqa: E402

TERMINAL = terminal_path()
OUT = DATA / "universe"
OUT.mkdir(parents=True, exist_ok=True)

#: Names to try when the broker will not enumerate (permissions, or an empty symbol tree).
#: A FALLBACK, never the definition of the universe -- see `candidates()`.
FALLBACK_CANDIDATES = [
    "XAUUSD", "XAGUSD", "WTI", "BRENT", "USOIL",
    "US500", "US30", "USTEC", "NAS100", "SPX500",
    "EURUSD", "GBPUSD", "USDJPY", "EURJPY", "GBPJPY",
    "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
    "EURCHF", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY",
    "AUDNZD", "NZDCAD", "EURAUD", "GBPAUD", "JP225",
    "BTCUSD", "ETHUSD",
]


def candidates() -> tuple[list[str], str]:
    """Every symbol the broker offers, or the hand-written list if the terminal will not say.

    THE HARDCODED LIST WAS THE UNIVERSE FOR THE LIFE OF THIS DESK, and nine of its entries --
    WTI, BRENT, USOIL, US500, US30, USTEC, NAS100, SPX500, JP225 -- are not offered on the
    Vantage account. The fetcher printed "not offered" and moved on, so the energy and index
    complexes were never tested, and nothing downstream recorded that an entire asset class was
    MISSING rather than REJECTED. Those are different facts and only one of them is evidence.

    A fixed list is also broker-specific in a way that fails quietly: the same index trades as
    US500, SPX500 or USA500 depending on the venue, so a Vantage -> Fusion move would shrink the
    universe at precisely the moment the desk was told to widen it.

    `mt5.symbols_get()` asks the terminal what it actually has. Everything it returns is a
    candidate; whether an instrument is worth TRADING is decided downstream by measured cost and
    the battery, never by omitting it here.
    """
    try:
        syms = mt5.symbols_get()
    except Exception as exc:                      # noqa: BLE001 - any failure means fall back
        return list(FALLBACK_CANDIDATES), f"enumeration failed ({type(exc).__name__}); using list"
    if not syms:
        return list(FALLBACK_CANDIDATES), "broker returned no symbols; using list"
    return sorted({s.name for s in syms}), f"enumerated {len(syms)} symbols from the terminal"

START = datetime(2018, 1, 1, tzinfo=timezone.utc)


def main() -> None:
    if mt5.terminal_info() is None:
        if not mt5.initialize(path=TERMINAL):
            print(f"initialize failed: {mt5.last_error()}")
            return
    print(f"terminal: {mt5.terminal_info().name} | account {mt5.account_info().login}")

    cands, how = candidates()
    print(f"universe discovery: {how}")

    summary = {}
    skipped: dict[str, str] = {}
    for sym in cands:
        info = mt5.symbol_info(sym)
        if info is None:
            skipped[sym] = "not offered"
            continue
        # A symbol must be visible in MarketWatch before copy_rates_range returns anything.
        # Enumerating the full offering means most symbols are hidden by default, so the fetch
        # would return zero bars for nearly everything and look like "no history" rather than
        # "never selected" -- the same missing-vs-rejected confusion this rewrite exists to end.
        if not info.visible:
            mt5.symbol_select(sym, True)
            info = mt5.symbol_info(sym) or info
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, START, datetime.now(timezone.utc))
        if rates is None or len(rates) < 1000:
            skipped[sym] = f"insufficient history ({0 if rates is None else len(rates)} bars)"
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").sort_index()
        df = df[["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
        df.to_parquet(OUT / f"{sym}_H1.parquet")
        med_spread = float(df["spread"].median())
        summary[sym] = {
            "bars": len(df),
            "first": str(df.index.min()),
            "last": str(df.index.max()),
            "contract_size": float(info.trade_contract_size),
            "tick_size": float(info.trade_tick_size),
            "tick_value": float(info.trade_tick_value),
            "min_volume": float(info.volume_min),
            "volume_step": float(info.volume_step),
            "median_spread_pts": med_spread,
        }
        print(f"{sym:8s} {len(df):6d} bars {df.index.min().date()} -> {df.index.max().date()} "
              f"contract={info.trade_contract_size} spread_med={med_spread:.1f}pts")
    (OUT / "universe.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    # WHAT WAS EXCLUDED IS RECORDED, NOT PRINTED AND FORGOTTEN. An asset class that is absent
    # because the broker does not offer it is a different fact from one the desk tested and
    # rejected, and only the second is evidence about markets.
    (OUT / "universe_skipped.json").write_text(json.dumps(skipped, indent=2), encoding="utf-8")

    from mt5desk.universe import classify_all, coverage
    cov = coverage(classify_all(summary))
    print(f"\n{len(summary)} symbols cached, {len(skipped)} skipped -> {OUT}")
    print(f"{'asset class':<14}{'usable':>8}{'unusable':>10}")
    for klass, row in cov.items():
        print(f"{klass:<14}{row['usable']:>8}{row['unusable']:>10}")
    absent = [k for k in ("energy", "index", "crypto", "metal", "fx_major", "fx_cross")
              if k not in cov]
    if absent:
        print(f"\nNO INSTRUMENTS AT ALL in: {', '.join(absent)} -- these classes are untested "
              f"by this desk because the broker does not offer them, NOT because they failed.")


if __name__ == "__main__":
    main()