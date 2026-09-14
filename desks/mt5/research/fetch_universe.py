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
from datetime import UTC, datetime, timedelta
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

START = datetime(2018, 1, 1, tzinfo=UTC)

#: INTRADAY BARS, AND WHY THE DESK HAD NONE (added 2026-09-14).
#:
#: This collector made exactly one call per symbol -- TIMEFRAME_H1 -- and the whole research
#: system inherited that as a ceiling it never chose. Measured on the box: 299 H1 parquets, 250
#: D1, 248 H4, and FOUR M15 plus a single M5 (XAUUSD). Nothing was wrong with the machinery:
#: `external_gauntlet.timeframe_of()` already reads `params["timeframe"]` per cell, and
#: `lvc_asia_london` is explicitly PINNED to M5. The bars simply did not exist.
#:
#: THREE SEPARATE SYMPTOMS, ONE LINE OF CODE:
#:   * No intraday mechanism could ever be hunted, on any symbol, at any timeframe below H1.
#:   * Every scalp sleeve on the desk is `xau_*` -- not a research preference, XAUUSD was the
#:     only instrument with M5/M1 coverage, so it was the only one the scalp lane COULD hunt.
#:   * `lvc_asia_london` produced cells the gauntlet built and never judged, because an M5-pinned
#:     family cannot reach the 60 trading days the gates need on symbols with no M5 bars. Those
#:     cells were routed to the deepening queue and surfaced in the conservation report as 13
#:     LOST candidates. The family was not lost; it was starving.
#:
#: WINDOWS ARE PER TIMEFRAME, AND SHORTER GOING DOWN. H1 keeps its full 2018 history unchanged --
#: nothing here reduces what already works. Intraday needs recency, not depth: the gates want 60
#: trading days, which is ~17k M5 bars, so one year of M5 (~74k bars) and two of M15 clear the
#: bar with room for a walk-forward split while keeping the pull to single-digit GB. Measured
#: from the existing files, M15 across all 299 symbols is ~0.6 GB against 58 GB free.
#:
#: TRADEABLE ONLY. Intraday is fetched for symbols the broker lets us OPEN (trade_mode 4); the
#: 13 CLOSE_ONLY instruments already cost the sweep budget once and there is no reason to buy
#: them a second, finer-grained dataset the desk can never act on.
#: (label, terminal constant, days of history). THE WHOLE LADDER BELOW H1, because a chart the
#: desk does not collect is a chart it can never hunt, and the sweep reads the files.
#:
#: WINDOWS SHORTEN AS THE CHART DOES, and the reason is bar COUNT rather than taste. The gates
#: need 60 trading days; a walk-forward split needs several multiples of that. Every window here
#: clears it by a wide margin -- M30 730d is ~35k bars, M15 730d ~70k, M5 365d ~105k, M1 180d
#: ~259k -- while keeping the whole pull near 2 GB against 58 GB free on the box. Taking M1 back
#: to 2018 would buy no statistical power the gates can spend and would cost tens of GB.
INTRADAY_TIMEFRAMES: tuple[tuple[str, str, int], ...] = (
    ("M30", "TIMEFRAME_M30", 730),
    ("M15", "TIMEFRAME_M15", 730),
    ("M5", "TIMEFRAME_M5", 365),
    ("M1", "TIMEFRAME_M1", 180),
)

#: An intraday series below this is not worth writing: it cannot carry the 60 trading days the
#: gates need, and a short file is worse than none because it looks like coverage.
MIN_INTRADAY_BARS = 5000


def _fetch_intraday(mt5, sym: str, info) -> dict[str, dict]:
    """Write the intraday parquets for one symbol. Returns per-timeframe coverage, always.

    A timeframe that produced nothing is REPORTED with its reason rather than omitted: "the
    broker served no M5 for this symbol" and "nobody asked for M5" are different facts, and an
    absent key makes them identical (L1.28a).
    """
    out: dict[str, dict] = {}
    if int(getattr(info, "trade_mode", -1)) != 4:
        return {tf: {"bars": 0, "reason": "NOT_TRADEABLE"} for tf, _, _ in INTRADAY_TIMEFRAMES}
    now = datetime.now(UTC)
    for label, attr, days in INTRADAY_TIMEFRAMES:
        tf_const = getattr(mt5, attr, None)
        if tf_const is None:
            out[label] = {"bars": 0, "reason": "TIMEFRAME_UNKNOWN_TO_TERMINAL"}
            continue
        start = now - timedelta(days=days)
        try:
            rates = mt5.copy_rates_range(sym, tf_const, start, now)
        except Exception as exc:
            out[label] = {"bars": 0, "reason": f"FETCH_FAILED: {type(exc).__name__}"}
            continue
        n = 0 if rates is None else len(rates)
        if n < MIN_INTRADAY_BARS:
            out[label] = {"bars": n, "reason": "INSUFFICIENT_HISTORY",
                          "min_bars": MIN_INTRADAY_BARS}
            continue
        d = pd.DataFrame(rates)
        d["time"] = pd.to_datetime(d["time"], unit="s", utc=True)
        d = d.set_index("time").sort_index()
        d = d[["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
        d.to_parquet(OUT / f"{sym}_{label}.parquet")
        out[label] = {"bars": len(d), "first": str(d.index.min()),
                      "last": str(d.index.max()),
                      "median_spread_pts": float(d["spread"].median())}
    return out



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
    except Exception as exc:
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
                registry[s]["delisted_seen_at"] = datetime.now(UTC).isoformat()
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
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, START, datetime.now(UTC))
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
        # INTRADAY, on the same pass. Failures here never abort the H1 write above: an M5 gap is
        # a coverage fact to record, not a reason to lose the hourly series the whole desk runs on.
        try:
            intraday = _fetch_intraday(mt5, sym, info)
        except Exception as exc:
            intraday = {"error": {"reason": f"{type(exc).__name__}: {exc}"}}
        summary[sym]["bars_by_timeframe"] = {"H1": len(df), **{
            k: int(v.get("bars", 0)) for k, v in intraday.items()}}
        summary[sym]["intraday_coverage"] = intraday
        # THE REGISTRY MUST CLAIM WHAT WAS ACTUALLY WRITTEN. `orthogonal_sweep.timeframes_of`
        # reads `timeframes` to decide which charts a symbol may be hunted on, and falls back to
        # H1 alone for a row carrying neither field. `timeframes_thin` records charts that WERE
        # fetched and came back too short for the gates, with their bar counts -- a coverage
        # measurement, not an absence, so a family that needs M5 can ask rather than discovering
        # the gap at gauntlet time.
        summary[sym]["timeframes"] = ["H1"] + [
            k for k, v in intraday.items() if int(v.get("bars", 0)) >= MIN_INTRADAY_BARS]
        summary[sym]["timeframes_thin"] = {
            k: int(v.get("bars", 0)) for k, v in intraday.items()
            if 0 < int(v.get("bars", 0)) < MIN_INTRADAY_BARS}
        _tf = " ".join(f"{k}={v.get('bars', 0)}" for k, v in intraday.items())
        print(f"{sym:8s} {len(df):6d} bars {df.index.min().date()} -> {df.index.max().date()} "
              f"contract={info.trade_contract_size} spread_med={med_spread:.1f}pts  {_tf}")
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
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "attempted": len(candidates), "written": len(summary), "skipped": len(skipped),
        "reasons": skipped}, indent=1), encoding="utf-8")
    print(f"skip ledger: {len(skipped)} symbol(s) recorded with a reason")
    print(f"\n{len(summary)} symbol(s) refreshed this run, merged into {len(registry)} "
          f"registry row(s) -> {OUT}")


if __name__ == "__main__":
    main()
