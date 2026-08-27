"""Fetch H1 history for the MT5 research universe (2018 -> now) and cache it.

Per-symbol cost model recorded (contract size, tick value, median spread).
Run with the VIG terminal logged in.

IT USED TO TRUNCATE THE REGISTRY, AND THAT COST THE DESK ITS FORWARD BOOK (fixed 2026-08-27).
`summary` started empty and was written whole over `universe.json`, so every run REPLACED the
registry with whatever this hardcoded list happened to fetch. On contabo-mt5 -- the only box with
a terminal, and therefore the box that computes every forward observation -- the result was a
23-row cost map beside 299 downloaded H1 parquets. `shadow_forward` then raised
`KeyError: 'EURZAR'` on a certified symbol the map did not contain and the entire forward pass
was discarded, every 15 minutes, for 5.5 hours.

Two rules now hold here, and both are the anti-hardcode law (LAWS §1) rather than style:

  * `SEED_CANDIDATES` is a BOOTSTRAP SEED, never a limit. The refresh set is the seed UNION every
    symbol the registry already knows, so this collector can only ever widen the desk's ground.
    Whole-broker enumeration from the terminal is `expand_universe.py`'s job -- it asks
    `mt5.symbols_get()` and records what it cannot test rather than dropping it -- and this file
    must never silently undo that organ's work.
  * The write MERGES. A symbol this run did not fetch keeps the metadata it already had. A
    partial or failed pass may leave the registry stale; it may never leave it SMALLER, because
    a missing row is not "no data", it is an uncostable symbol that kills a pass.
"""

import json
import sys
from datetime import datetime, timezone
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
OUT.mkdir(parents=True, exist_ok=True)

#: BOOTSTRAP SEED, NOT A UNIVERSE (LAWS §1 anti-hardcode). These are the symbols this collector
#: starts from on an empty box; the actual refresh set is this union whatever `universe.json`
#: already holds, and the whole-broker enumerator is `expand_universe.py`.
SEED_CANDIDATES = [
    "XAUUSD", "XAGUSD", "WTI", "BRENT", "USOIL",
    "US500", "US30", "USTEC", "NAS100", "SPX500",
    "EURUSD", "GBPUSD", "USDJPY", "EURJPY", "GBPJPY",
    "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
    "EURCHF", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY",
    "AUDNZD", "NZDCAD", "EURAUD", "GBPAUD", "JP225",
    "BTCUSD", "ETHUSD",
]

START = datetime(2018, 1, 1, tzinfo=timezone.utc)


def main() -> None:
    if mt5.terminal_info() is None:
        if not mt5.initialize(path=TERMINAL):
            print(f"initialize failed: {mt5.last_error()}")
            return
    print(f"terminal: {mt5.terminal_info().name} | account {mt5.account_info().login}")

    # THE REGISTRY IS THE BASE, NOT THE OUTPUT. Read first, refresh into it, write the union.
    registry: dict = {}
    if (OUT / "universe.json").exists():
        try:
            loaded = json.loads((OUT / "universe.json").read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                registry = loaded
        except (OSError, ValueError) as exc:
            # A FAILED READ IS NOT AN EMPTY REGISTRY. Rebuilding from this list would be exactly
            # the truncation this file was fixed to stop, so refuse the run instead.
            print(f"REFUSING to run: {OUT / 'universe.json'} exists but cannot be read ({exc}); "
                  f"retry later rather than rebuilding the registry from the seed list")
            return
    prior_n = len(registry)
    candidates = list(dict.fromkeys([*SEED_CANDIDATES, *registry]))
    print(f"refreshing {len(candidates)} symbol(s): {len(SEED_CANDIDATES)} seeded, "
          f"{prior_n} already in the registry")

    summary = {}
    for sym in candidates:
        info = mt5.symbol_info(sym)
        if info is None:
            print(f"{sym:8s} not offered")
            continue
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, START, datetime.now(timezone.utc))
        if rates is None or len(rates) < 1000:
            print(f"{sym:8s} insufficient history ({0 if rates is None else len(rates)} bars)")
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
    registry.update(summary)
    if len(registry) < prior_n:
        # Unreachable by construction (update never removes keys); asserted anyway because the
        # whole point of this fix is that this file can never shrink the registry again.
        print(f"REFUSING to write: registry would shrink {prior_n} -> {len(registry)}")
        return
    (OUT / "universe.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(f"\n{len(summary)} symbol(s) refreshed this run, merged into {len(registry)} "
          f"registry row(s) -> {OUT}")


if __name__ == "__main__":
    main()