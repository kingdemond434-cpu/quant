"""EXPAND THE HUNTED UNIVERSE TO EVERY TRADABLE FUSION SYMBOL.

THE GAP (measured 2026-08-26, principal: "maximum classes assets symbols indices stocks
everything possible on mt5"). Fusion exposes 250 tradable symbols across nine asset classes. The
desk hunts 24. Everything below has never been looked at:

    Equities          105     entirely unhunted
    Forex Exotics      57     entirely unhunted
    Indices            16     entirely unhunted
    Commodities        12     entirely unhunted
    Soft Commodity     11     entirely unhunted
    Bonds               3     entirely unhunted
    Energy              3     entirely unhunted

This is the single largest breadth constraint on the desk, and it is upstream of everything else.
N_eff cannot rise while 95% of certificates are one mechanism on five FX pairs -- but the fix is
not only more mechanisms, it is more GROUND. An equity CFD, a bond and a soft commodity fail in
different regimes from a JPY cross by construction: they respond to earnings, to rate
expectations and to weather. That is diversification the desk cannot manufacture by adding
another parameterisation of a session breakout.

WHY THIS IS SAFE FOR THE 4GB BOX. Bars are fetched and stored on the DESK box, which has 71GB
free and the terminal connection; the research box pulls only what it searches. ~460MB of H1
across 250 symbols is nothing on the desk box and would be a real cost on the research box, so
the split follows the data rather than the code.

WHAT IT REFUSES. A symbol whose history is too short to test is recorded as SHORT_HISTORY, not
silently dropped -- otherwise the universe registry would claim coverage it does not have, which
is the WS-005 class (absence read as a clean verdict). Symbols are never hardcoded: the list
comes from the terminal every run, so a symbol Fusion adds is hunted without a code change.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
REPORT = BASE / "data" / "universe_expansion.json"

#: Years of H1 history to request. Enough for the gauntlet's walk-forward and CPCV folds.
YEARS = 6
#: A symbol with fewer bars than this cannot support the ten gates and is recorded as such.
MIN_BARS = 3000


def main() -> int:
    import MetaTrader5 as mt5
    import pandas as pd
    from mt5desk.universe_registry import cost_fields_from_symbol_info

    now = datetime.now(tz=UTC)
    if not mt5.initialize():
        print(f"MT5 initialize failed: {mt5.last_error()}")
        return 1

    symbols = mt5.symbols_get() or ()
    tradable = [s for s in symbols if getattr(s, "trade_mode", 0) != 0]
    print(f"Fusion exposes {len(symbols)} symbols, {len(tradable)} tradable")

    registry = {}
    if REGISTRY.exists():
        try:
            registry = json.loads(REGISTRY.read_text("utf-8"))
        except (OSError, ValueError):
            # A FAILED READ OF A FULL REGISTRY MUST NEVER BECOME A FRESH EMPTY BASE. Measured
            # 2026-08-27: a read race (the hourly sync mid-copy) yielded {} here, the terminal's
            # MarketWatch offered 23 selected symbols, and the whole-broker registry of 197 was
            # overwritten with 23 -- then synced to the repo. Absence of a readable registry is
            # a reason to STOP, not a blank slate.
            print(f"REFUSING to run: {REGISTRY} exists but cannot be read -- retry later "
                  f"rather than rebuilding the registry from whatever this terminal shows")
            return 1
    prior_n = len(registry)

    start = now - timedelta(days=365 * YEARS)
    added, refreshed, short, failed = [], [], [], []
    by_class: dict[str, int] = {}

    for s in tradable:
        name = s.name
        asset_class = str(getattr(s, "path", "")).split("\\")[0] or "Unknown"
        # SELECT BEFORE COPY. An unselected symbol returns no rates and would look like a dead
        # instrument rather than one nobody had asked for.
        if not mt5.symbol_select(name, True):
            failed.append({"symbol": name, "why": "symbol_select refused"})
            continue
        rates = mt5.copy_rates_range(name, mt5.TIMEFRAME_H1, start, now)
        if rates is None or len(rates) < MIN_BARS:
            short.append({"symbol": name, "class": asset_class,
                          "bars": 0 if rates is None else len(rates),
                          "why": f"fewer than {MIN_BARS} H1 bars -- cannot support the ten gates; "
                                 f"recorded rather than silently dropped"})
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").sort_index()
        out = UNIVERSE / f"{name}_H1.parquet"
        existed = out.exists()
        try:
            df.to_parquet(out)
        except Exception as exc:
            failed.append({"symbol": name, "why": f"{type(exc).__name__}: {exc}"})
            continue
        (refreshed if existed else added).append(name)
        by_class[asset_class] = by_class.get(asset_class, 0) + 1

        info = mt5.symbol_info(name)
        if info is not None:
            # MERGE THE ROW, NEVER REPLACE IT. A bare assignment drops every field a
            # different producer wrote (`min_volume`, `first`, `last`, repaired
            # `tick_value`), which is the row-level twin of the file-level clobber
            # that once left 0/197 instruments costable. Whatever this run measured
            # wins; whatever it did not measure survives.
            registry[name] = {**registry.get(name, {}), **{
                "symbol": name, "asset_class": asset_class,
                "tick_size": float(getattr(info, "trade_tick_size", 0) or 0),
                # WITHOUT tick_value THERE IS NO CURRENCY CONVERSION: Costs.from_symbol and every
                # sizing path need one tick's worth IN ACCOUNT CURRENCY, and this collector never
                # asked MT5 for it -- so all 82 equity/index rows of the whole-broker expansion
                # arrived uncostable and sat outside the hunt while looking "present".
                # The cost fields come from cost_fields_from_symbol_info (below) rather than
                # being read inline: `or 0` wrote 0.0 for a symbol with no fresh tick, and
                # because this is a MERGE that 0.0 overwrote a good prior reading -- the exact
                # row-level clobber the comment above warns about, committed by the line that
                # was meant to fix it. A degenerate reading must be OMITTED so the prior value
                # survives; 0.0 tick_value is unmeasured, not free, and it makes
                # spread_cost_per_lot 0.0 so gate 8 (stress_costs) cannot judge the candidate
                # at all -- which is how a symbol sits in the registry and never certifies.
                "contract_size": float(getattr(info, "trade_contract_size", 0) or 0),
                "digits": int(getattr(info, "digits", 5) or 5),
                # ONE FIELD, ONE MEASUREMENT (fixed 2026-08-27). This wrote `info.spread` -- the
                # spread AT THE INSTANT THE COLLECTOR RAN -- into the same key that
                # `fetch_universe` fills with the MEDIAN of the H1 spread column, and
                # `Costs.from_symbol` prices every candidate off it. Two producers writing two
                # different measurements into one name meant a symbol's cost basis depended on
                # which collector touched it last, and a run at a thin hour would have re-priced
                # the desk's whole live book off one tick. The bars are already downloaded here,
                # so the median is free and identical in meaning to the other producer's.
                # The point-in-time reading is KEPT, under its own name, because it is real data
                # about the moment -- it just is not a median.
                "median_spread_pts": float(df["spread"].median())
                if "spread" in df.columns else float(getattr(info, "spread", 0) or 0),
                "spread_pts_at_collection": float(getattr(info, "spread", 0) or 0),
                "swap_long": float(getattr(info, "swap_long", 0) or 0),
                "swap_short": float(getattr(info, "swap_short", 0) or 0),
                **cost_fields_from_symbol_info(info),
                "volume_min": float(getattr(info, "volume_min", 0.01) or 0.01),
                "volume_step": float(getattr(info, "volume_step", 0.01) or 0.01),
                "bars": len(df),
                "updated_at": now.isoformat(timespec="seconds"),
            }}

    if len(registry) < prior_n:
        print(f"REFUSING to write: registry would shrink {prior_n} -> {len(registry)}; "
              f"a smaller broker offering is announced by retirement, never by overwrite")
        return 1
    REGISTRY.write_text(json.dumps(registry, indent=1, default=str), "utf-8")
    REPORT.write_text(json.dumps({
        "expanded_at": now.isoformat(timespec="seconds"),
        "fusion_symbols": len(symbols), "tradable": len(tradable),
        "added": added, "refreshed": len(refreshed),
        "short_history": short, "failed": failed,
        "by_class": by_class,
        "note": ("symbol list comes from the terminal every run -- a symbol Fusion adds is hunted "
                 "without a code change (LAWS anti-hardcode). SHORT_HISTORY entries are recorded, "
                 "never silently dropped."),
    }, indent=1, default=str), "utf-8")

    mt5.shutdown()
    print(f"universe: +{len(added)} new, {len(refreshed)} refreshed, "
          f"{len(short)} short-history, {len(failed)} failed")
    for k, v in sorted(by_class.items(), key=lambda kv: -kv[1]):
        print(f"   {k:24} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
