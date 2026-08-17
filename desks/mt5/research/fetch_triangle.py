"""Fetch AUDCAD/AUDNZD/NZDCAD M15+H1 for the relative-value triangle study.

Chunked per-year M15 requests (single 2018->now requests return empty).
Extends data/universe/* and universe.json (keeps existing symbols).
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd
from mt5desk.config import DATA, REPORTS, desk_root  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk.config import terminal_path

TERMINAL = terminal_path()
OUT = DATA / "universe"
OUT.mkdir(parents=True, exist_ok=True)

TRIANGLE = ["AUDCAD", "AUDNZD", "NZDCAD"]
YEARS = range(2018, 2027)


def fetch_range(sym: str, tf, start, end, tries: int = 4) -> pd.DataFrame | None:
    for _ in range(tries):
        rates = mt5.copy_rates_range(sym, tf, start, end)
        if rates is not None and len(rates):
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            return df.set_index("time").sort_index()
        time.sleep(2)
    return None


def main() -> None:
    if mt5.terminal_info() is None:
        if not mt5.initialize(path=TERMINAL):
            print(f"initialize failed: {mt5.last_error()}")
            return
    print(f"terminal: {mt5.terminal_info().name} | account {mt5.account_info().login}")

    meta_path = OUT / "universe.json"
    summary = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    for sym in TRIANGLE:
        info = mt5.symbol_info(sym)
        if info is None:
            print(f"{sym:8s} not offered")
            continue
        mt5.symbol_select(sym, True)
        time.sleep(0.5)
        for tf, label in ((mt5.TIMEFRAME_H1, "H1"), (mt5.TIMEFRAME_M15, "M15")):
            if (OUT / f"{sym}_{label}.parquet").exists() and label == "H1":
                print(f"{sym:8s} {label} cached, skip")
                continue
            frames = []
            for y in YEARS:
                s = datetime(y, 1, 1, tzinfo=timezone.utc)
                e = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
                if e > datetime.now(timezone.utc):
                    e = datetime.now(timezone.utc)
                df = fetch_range(sym, tf, s, e)
                if df is not None and len(df):
                    frames.append(df)
                else:
                    print(f"  {label} {y}: empty")
            if not frames:
                print(f"{sym:8s} {label} NO DATA")
                continue
            df = pd.concat(frames)
            df = df[~df.index.duplicated(keep="first")].sort_index()
            df = df[["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
            df.to_parquet(OUT / f"{sym}_{label}.parquet")
            print(f"{sym:8s} {label} {len(df):6d} bars "
                  f"{df.index.min().date()} -> {df.index.max().date()}")
            time.sleep(1)
        summary[sym] = {
            "contract_size": float(info.trade_contract_size),
            "tick_size": float(info.trade_tick_size),
            "tick_value": float(info.trade_tick_value),
            "min_volume": float(info.volume_min),
            "volume_step": float(info.volume_step),
            "median_spread_pts": float(summary.get(sym, {}).get("median_spread_pts")
                                       or (mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1,
                                                                datetime(2026, 7, 1, tzinfo=timezone.utc),
                                                                datetime.now(timezone.utc)) or [None])[0]),
            "fx_pair": True,
        }
        info2 = mt5.symbol_info(sym)
        print(f"{sym:8s} contract={info2.trade_contract_size} tick={info2.trade_tick_size} "
              f"spread_med={summary[sym]['median_spread_pts']}pts")

    meta_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{len(summary)} symbols in universe.json")


if __name__ == "__main__":
    main()