"""Bulk MT5 history ingester -- maximize data breadth and depth into the Parquet lake.

Connects to MT5 READ-ONLY, enumerates the live broker universe (FX, metals, energy, crypto,
indices incl. the dollar index, single-name equities, soft commodities), and pulls the maximum
available history per (symbol, timeframe) into the Bronze layer of the existing ``ParquetLake``.

MT5 quirk handled here (the hard part): ``copy_rates_*`` returns nothing on first touch of a
symbol/timeframe until the terminal finishes an async history download, and ``copy_rates_range``
fails for deep intraday ranges. So we (1) bulk-select every symbol and let the terminal sync once,
then (2) pull with ``copy_rates_from_pos`` (which works once warm) under a real retry budget,
falling back to ``copy_rates_range`` for daily history. ``from_pos(0, maxbars)`` returns the full
available history (D1 reaches ~2000; H1 the most recent ~100k bars).

This is one-time infrastructure (the committee's "data breadth" lever). Storing breadth on disk is
cheap and reusable; it does NOT mean every symbol is tested -- research stays niche-focused.

Usage:
    python scripts/ingest_history.py                      # D1 full universe + H1 liquid core
    python scripts/ingest_history.py --groups Indices,Forex --timeframes D1
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.data.instruments import InstrumentSpec, asset_class_for_group, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.mt5_research import research_session_verdict, resolve_liquid_intraday_core
from libs.data.schema import BAR_COLUMNS
from libs.data.timeframe import Timeframe

# Liquid, research-relevant core that also gets intraday (H1) history. Everything else is D1 only.
_OUT = Path("reports/data_coverage.json")
# Keep one native MT5 request below the terminal's crash-prone 100k ceiling. 30k still gives
# roughly 114y D1 / 19y H4 / 4.8y H1 / 1.2y M15 and matches the deepest discovery consumer.
_MAXBARS = 30_000


def _connect(
    expected_server: str = "",
    *,
    terminal_path: str = "",
    portable: bool = False,
    allow_readonly_live: bool = False,
):  # type: ignore[no-untyped-def]
    import MetaTrader5 as mt5

    initialized = (
        mt5.initialize(terminal_path, portable=portable) if terminal_path else mt5.initialize()
    )
    if not initialized:
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    acct = mt5.account_info()
    term = mt5.terminal_info()
    verdict = research_session_verdict(
        acct, term, expected_server=expected_server, allow_readonly_live=allow_readonly_live
    )
    if not verdict.allowed:
        mt5.shutdown()
        raise SystemExit(f"refusing MT5 research session: {verdict.mode}: {verdict.reason}")
    print(f"connected: server={acct.server} mode={verdict.mode} maxbars={term.maxbars}")
    return mt5


def _fetch(  # type: ignore[no-untyped-def]
    mt5, symbol: str, tf_const, count: int, tries: int, start, *, prefer_range: bool = False
):
    """Pull history, retrying while the async download completes.

    Tries ``copy_rates_range`` first (more reliable at triggering a cold-cache download) and falls
    back to ``copy_rates_from_pos``. NOTE: a terminal with no cached history (fresh install / no
    charts opened / weekend) may return nothing no matter what -- that is an environment limit, not
    a code bug. Open the symbol's chart once, or run on a trading day, to seed the cache.
    """
    now = datetime.now(tz=UTC)
    for _ in range(tries):
        methods = (
            (
                (mt5.copy_rates_range, (symbol, tf_const, start, now)),
                (mt5.copy_rates_from_pos, (symbol, tf_const, 0, count)),
            )
            if prefer_range
            else (
                (mt5.copy_rates_from_pos, (symbol, tf_const, 0, count)),
                (mt5.copy_rates_range, (symbol, tf_const, start, now)),
            )
        )
        for method, call_args in methods:
            rates = method(*call_args)
            if rates is not None and len(rates) > 0:
                return rates
        time.sleep(0.5)
    return None


def _to_canonical(rates) -> pd.DataFrame:  # type: ignore[no-untyped-def]
    """Build the canonical UTC bar frame from an MT5 rates array.

    MT5 bar ``time`` is an epoch second; we label it UTC. (Sub-day session offsets vs the broker
    server clock are immaterial at D1/H1 breadth scope; intraday strategies must re-confirm tz.)
    """
    df = pd.DataFrame(rates)
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df["time"], unit="s", utc=True),
            "open": df["open"].astype("float64"),
            "high": df["high"].astype("float64"),
            "low": df["low"].astype("float64"),
            "close": df["close"].astype("float64"),
            "volume": df["tick_volume"].astype("float64"),
        }
    )[list(BAR_COLUMNS)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="data/lake")
    parser.add_argument("--timeframes", default="D1,H1")
    parser.add_argument("--groups", default="", help="comma-separated group filter; empty = all")
    parser.add_argument("--max-symbols", type=int, default=0, help="0 = no cap")
    parser.add_argument(
        "--universe",
        choices=("all", "mt5-liquid-core"),
        default="all",
        help="full broker D1 breadth or the resolved liquid cross-asset core",
    )
    parser.add_argument(
        "--warmup-sleep",
        type=float,
        default=25.0,
        help="seconds to let the terminal bulk-download after selecting symbols",
    )
    parser.add_argument("--tries", type=int, default=15, help="per-symbol fetch retries")
    parser.add_argument("--start", default="2000-01-01", help="earliest bar date to request")
    parser.add_argument(
        "--expected-server",
        default="",
        help="assert MT5 connected to this server (reproducibility guard)",
    )
    parser.add_argument("--terminal", default="", help="exact MT5 terminal executable")
    parser.add_argument(
        "--portable", action="store_true", help="start terminal in isolated portable mode"
    )
    parser.add_argument(
        "--allow-readonly-live",
        action="store_true",
        help="permit a server-pinned investor login only when account+terminal trading are disabled",
    )
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    want_tf = [Timeframe(t.strip()) for t in args.timeframes.split(",") if t.strip()]
    group_filter = {g.strip() for g in args.groups.split(",") if g.strip()}

    mt5 = _connect(
        args.expected_server,
        terminal_path=args.terminal,
        portable=args.portable,
        allow_readonly_live=args.allow_readonly_live,
    )
    lake = ParquetLake(args.base)
    tf_map = {
        Timeframe.D1: mt5.TIMEFRAME_D1,
        Timeframe.H4: mt5.TIMEFRAME_H4,
        Timeframe.H1: mt5.TIMEFRAME_H1,
        Timeframe.M15: mt5.TIMEFRAME_M15,
        Timeframe.M5: mt5.TIMEFRAME_M5,
    }

    symbols = list(mt5.symbols_get())
    if group_filter:
        symbols = [s for s in symbols if s.path.split("\\", 1)[0] in group_filter]
    if args.max_symbols:
        symbols = symbols[: args.max_symbols]
    liquid_intraday = set(resolve_liquid_intraday_core([s.name for s in symbols]))
    if args.universe == "mt5-liquid-core":
        symbols = [s for s in symbols if s.name in liquid_intraday]
    print(f"universe: {len(symbols)} symbols; timeframes={[t.value for t in want_tf]}")
    print(f"resolved liquid intraday core: {len(liquid_intraday)} broker symbols")

    # Phase 1: bulk-select + nudge every symbol so the terminal starts downloading history, then
    # wait ONCE for the bulk sync (far faster than paying a long retry budget per cold symbol).
    for s in symbols:
        mt5.symbol_select(s.name, True)
        mt5.symbol_info_tick(s.name)
    print(f"selected {len(symbols)} symbols; waiting {args.warmup_sleep:.0f}s for bulk sync...")
    time.sleep(args.warmup_sleep)

    coverage: list[dict[str, object]] = []
    try:
        for i, sym in enumerate(symbols, 1):
            name = sym.name
            ac = asset_class_for_group(sym.path)
            register_instrument(
                InstrumentSpec(symbol=name, asset_class=ac, description=sym.description or name)
            )
            for tf in want_tf:
                if tf is not Timeframe.D1 and name not in liquid_intraday:
                    continue
                rates = _fetch(
                    mt5,
                    name,
                    tf_map[tf],
                    _MAXBARS,
                    args.tries,
                    start,
                    prefer_range=tf is Timeframe.D1,
                )
                if rates is None:
                    coverage.append(
                        {"symbol": name, "asset_class": ac.value, "timeframe": tf.value, "bars": 0}
                    )
                    continue
                frame = _to_canonical(rates)
                lake.write_bars(Layer.BRONZE, name, tf, frame)
                coverage.append(
                    {
                        "symbol": name,
                        "asset_class": ac.value,
                        "timeframe": tf.value,
                        "bars": len(frame),
                        "first": str(frame["timestamp"].iloc[0].date()),
                        "last": str(frame["timestamp"].iloc[-1].date()),
                    }
                )
            if i % 25 == 0:
                print(f"  [{i}/{len(symbols)}] {name} done")
    finally:
        mt5.shutdown()

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(coverage, indent=2), "utf-8")

    d1 = [c for c in coverage if c["timeframe"] == "D1" and c["bars"]]
    by_class: dict[str, int] = {}
    for c in d1:
        by_class[str(c["asset_class"])] = by_class.get(str(c["asset_class"]), 0) + 1
    deepest = sorted(d1, key=lambda c: int(c["bars"]), reverse=True)[:5]  # type: ignore[arg-type]
    print(f"\nINGEST COMPLETE -> {_OUT}")
    print(f"D1 datasets with data: {len(d1)} | by class: {by_class}")
    for tf in want_tf:
        measured = [c for c in coverage if c["timeframe"] == tf.value and c["bars"]]
        print(f"{tf.value} datasets with data: {len(measured)}")
    if deepest:
        print("deepest D1 history:")
        for c in deepest:
            print(f"  {c['symbol']:10} {c['bars']} bars  {c['first']} -> {c['last']}")


if __name__ == "__main__":
    main()
