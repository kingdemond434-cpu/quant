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
import time
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

#: A walk-forward split needs enough history to have an out-of-sample half worth
#: measuring; below this a symbol is not testable yet rather than broken. Recorded on
#: every skip so a symbol that is merely YOUNG is never mistaken for one the broker
#: refuses to quote.
MIN_BARS = 1000

START = datetime(2018, 1, 1, tzinfo=timezone.utc)


def _clocked_symbols() -> set[str]:
    """Symbols carrying an ACTIVE forward clock. Their bars are load-bearing; others' are not."""
    try:
        state = json.loads((desk_root() / "reports" / "shadow" / "shadow_state.json")
                           .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(k).split(".")[0] for k, v in state.items()
            if isinstance(v, dict) and str(v.get("status") or "") == "ACTIVE"}


def _refresh_order(candidates: list[str]) -> list[str]:
    """Order the refresh by what most needs it: clocked first, then stalest first.

    A LIST ORDER STARVES ITS OWN TAIL. This walked `SEED_CANDIDATES` then registry order, so a
    run that does not finish -- and with 251 symbols of 2018-to-now H1 through one terminal, many
    do not -- always refreshes the same head and never reaches the same tail. MEASURED
    2026-09-02: seven symbols carrying ACTIVE forward clocks (AUDCHF, CHFDKK, CHFNOK, EURZAR,
    GBPCHF, USDMXN, USDZAR) held H1 parquets 168.7 HOURS old -- a full week -- while symbols
    earlier in the list were 8.8 hours old. Those clocks were accruing forward evidence against
    week-old bars, which is not forward evidence.

    Staleness order makes truncation self-correcting: whatever a short run misses is first in
    line next time, so no symbol can be starved by its position. Clocked symbols outrank
    unclocked ones at equal staleness because a stale bar under a running clock corrupts
    evidence, while a stale bar under no clock merely delays research.
    """
    clocked = _clocked_symbols()

    def age(sym: str) -> float:
        pq = OUT / f"{sym}_H1.parquet"
        try:
            return time.time() - pq.stat().st_mtime
        except OSError:
            return float("inf")         # never fetched: the stalest thing there is

    ordered = sorted(candidates, key=lambda s: (0 if s in clocked else 1, -age(s)))
    if clocked:
        worst = ordered[0]
        print(f"{len(clocked)} clocked symbol(s); refreshing {worst} first "
              f"({age(worst) / 3600:.1f}h old)")
    return ordered


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
    # THE UNIVERSE IS DERIVED FROM THE BROKER, not from a seed list plus whatever accreted.
    # Measured 2026-09-03, the registry was wrong in BOTH directions: three symbols it still
    # carried are no longer offered (BeyondMeat, BlockInc, Walgreens), and two the broker DOES
    # offer were absent from it entirely (Palantir, SpaceX) -- so the desk had never hunted them
    # and nothing in the system could notice, because absence of a symbol looks exactly like a
    # symbol with no edge (L1.28a). Unioning the broker's own list means a new listing is hunted
    # the next time this runs, with no edit anywhere.
    offered: list[str] = []
    try:
        offered = [s.name for s in (mt5.symbols_get() or ())]
        print(f"broker offers {len(offered)} symbol(s); "
              f"{sum(1 for s in mt5.symbols_get() if s.trade_mode == 4)} fully tradeable")
    except Exception as exc:                                    # noqa: BLE001
        print(f"broker symbol list unavailable ({type(exc).__name__}); "
              f"refreshing the seed and registry only")
    delisted = [s for s in registry if offered and s not in offered]
    if delisted:
        # NAMED, NEVER DELETED. A row that vanishes reads exactly like a row resolved, and the
        # registry is the desk's memory of what it has ever been able to price.
        print(f"{len(delisted)} registry symbol(s) no longer offered: {sorted(delisted)[:10]}")
        for s in delisted:
            if isinstance(registry.get(s), dict):
                registry[s]["tradeable"] = False
                registry[s]["delisted_seen_at"] = datetime.now(timezone.utc).isoformat()
    candidates = _refresh_order(
        list(dict.fromkeys([*SEED_CANDIDATES, *registry, *offered])))
    print(f"refreshing {len(candidates)} symbol(s): {len(SEED_CANDIDATES)} seeded, "
          f"{prior_n} already in the registry; clocked and stalest first")

    summary = {}
    # WHY A SYMBOL HAS NO BARS IS ITSELF DATA. Both skips below used to print a line and vanish,
    # so 54 symbols in the registry had no H1 parquet and NOTHING recorded whether the broker
    # refuses to quote them, they are too young to test, or the fetch was simply never attempted.
    # Those three need completely different responses -- retire the symbol, wait, or re-run --
    # and with no artifact they were indistinguishable from each other and from a silent bug.
    # "UNMEASURED is a real answer" (LAWS L1.28a): record it as one.
    skipped: dict[str, dict] = {}
    for sym in candidates:
        info = mt5.symbol_info(sym)
        if info is None:
            print(f"{sym:8s} not offered")
            skipped[sym] = {"reason": "NOT_OFFERED",
                            "detail": "the broker does not quote this symbol on this account"}
            continue
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, START, datetime.now(timezone.utc))
        n_bars = 0 if rates is None else len(rates)
        if rates is None or n_bars < MIN_BARS:
            print(f"{sym:8s} insufficient history ({n_bars} bars)")
            skipped[sym] = {"reason": "INSUFFICIENT_HISTORY", "bars": n_bars,
                            "min_bars": MIN_BARS,
                            "detail": f"{n_bars} H1 bars is below the {MIN_BARS} a walk-forward "
                                      f"split needs; retry as the symbol ages"}
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
            # WHAT THE BROKER WILL ACTUALLY LET US DO. Measured 2026-09-03: Fusion offers 250
            # symbols of which only 237 are SYMBOL_TRADE_MODE_FULL; the other 13 (DocuSign,
            # EOSUSD, EURRUB, EURTRY, GBPTRY, OJ, SUGAR, UKCOCOA, UKGILT, USDRUB, USDTRY,
            # UST05Y, UST10Y) are CLOSE_ONLY -- no new position can be opened on them at all.
            # The registry carried no trade_mode, so nothing downstream could tell a hunt-able
            # symbol from one the desk can only exit, and the sweep spent budget on both.
            "trade_mode": int(getattr(info, "trade_mode", -1)),
            "tradeable": bool(int(getattr(info, "trade_mode", -1)) == 4),
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
    # The skip ledger is written EVERY run, including an empty one, because "nothing was skipped
    # this pass" and "this pass never reported" are different facts and a stale file would make
    # them look identical to the coverage watchdog.
    (OUT / "bar_coverage_skips.json").write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "attempted": len(candidates), "written": len(summary), "skipped": len(skipped),
        "reasons": skipped}, indent=1), encoding="utf-8")
    print(f"skip ledger: {len(skipped)} symbol(s) recorded with a reason")
    print(f"\n{len(summary)} symbol(s) refreshed this run, merged into {len(registry)} "
          f"registry row(s) -> {OUT}")


if __name__ == "__main__":
    main()