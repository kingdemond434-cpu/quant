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

# EVERY CHART, NOT ONE (principal, 2026-09-05: "m1 m5 m15 m30 h1 h4 d1 all possible every type
# of mechanism n chart for all always").
#
# This fetched H1 alone, for every symbol, and wrote `<SYM>_H1.parquet`. Gold was the only
# instrument with anything finer, and only because `fetch_gold_scalp.py` was hand-written for
# it. The consequence was structural rather than cosmetic: no family could express an intraday
# mechanism on anything but gold, the scalp lane existed on XAUUSD alone because it was the
# only symbol with M5/M15, and every sub-hour question -- including "was this event already
# priced?" -- resolved to UNMEASURABLE for want of bars fine enough to see the answer in.
#
# WHY THE FULL LADDER IS AFFORDABLE, measured rather than assumed. The tick recorder captures
# 251 symbols at ~24 MB/day compacted (~8.9 GB/year), and a tick is strictly finer than an M1
# bar -- so bars are cheap beside an asset the desk already pays for. The real cost is the
# GAUNTLET.
#
# AND IT IS A DAILY COST, NOT A ONE-TIME BUILD. This said the opposite -- "a ONE-TIME build,
# because the cell cache is content-addressed and every later sweep is a cache hit" -- and that
# is not what the cache is addressed BY. `external_gauntlet._cache_key` hashes
# (cell, params, chart, LAST COMPLETE DATA-DAY), and it must: the gate matrix aligns columns by
# length from the end, so every column has to end on the same complete day or PBO and SPA compare
# yesterday's row of one cell against today's of another. So every cell recomputes once per
# TRADING DAY, and the module's own budget note says as much ("the cache key rolls over and every
# cell goes cold again").
#
# What that means for the ladder, measured on this tree (build_cell + daily_series on AUDCAD):
# 0.4-2.0 s per sweep-family cell at H1, scaling roughly linearly with bar count, so ~1-2 s at
# M15 and tens of seconds at M1. The docket is 23,465 rows of which 20,341 are `discovered` --
# an H1-only searcher this ladder does not multiply -- so the ~3,100 sweep cells grow ~4x (the
# residual and peer families are declared H1-and-slower) and the whole docket grows ~1.4x.
# Against `FRESH_BUILD_BUDGET_SEC` (20 minutes an hour) the desk ALREADY cannot rebuild its
# docket inside a day; `gauntlet_build_cursor` rotates it instead and `trial_allocator` orders
# that rotation by measured certification yield. The ladder lengthens that rotation; it does not
# introduce the constraint, and no cell is dropped -- a cell the budget did not reach is recorded
# UNMEASURED with its reason and is at the front of the next sweep.
#
# AND WIDENING THE SWEEP DOES NOT RAISE THE BAR. I wrote the opposite here first and it was
# wrong: this desk pins `fixed_trial_count` and `fixed_variance_of_sharpes` in
# `policy/gate_spec.yaml` precisely so that "a candidate must not face a higher bar for having
# been scheduled into a wider sweep" (gate_policy.py). The spec records the measurement that
# forced it -- sr0 ran 0.3786 at 597 charged trials and 1.3593 at 5,963 for the SAME cell,
# purely because the sweep around it grew. The deflated Sharpe still corrects for multiple
# testing; it just no longer punishes a candidate for the company it keeps.
#
# So the ten gates are fixed and permanent, and every cell from every chart faces exactly the
# bar it would have faced alone. More timeframes is therefore strictly more candidates judged
# at an unchanged bar -- more certificates, not fewer. There is no tradeoff here to manage.
#
# Brokers keep far less M1 than H1, so many symbols will fail MIN_BARS on the fast end and
# record why. That self-selection is the feature: the ladder asks for everything and keeps what
# can actually support a ten-gate verdict.
# ONE LADDER, IMPORTED. A second literal spelling of the charts here is how a producer and a
# consumer quietly stop agreeing about which charts exist; `universe_registry` owns what the
# registry means, and `min_bars` below reads the same module for the floor.
from mt5desk.universe_registry import TIMEFRAMES

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
REPORT = BASE / "data" / "universe_expansion.json"

#: Years of history to request. Enough for the gauntlet's walk-forward and CPCV folds.
YEARS = 6
#: An HOURLY chart with fewer bars than this cannot support the ten gates. It is the ADMISSION
#: floor and it has not moved.
MIN_BARS = 3000


def min_bars(timeframe: str) -> int:
    """`MIN_BARS` re-expressed as the SAME MARKET TIME on `timeframe`.

    ONE NUMBER APPLIED TO SEVEN CHARTS IS SEVEN DIFFERENT RULES, and the flat version of this
    would have emptied a whole lane in silence. 3,000 bars is four months of H1 and TWELVE YEARS
    of D1; six years of daily bars is ~1,560, so every symbol on the desk would have recorded
    `D1:1560` as a thin chart and the DAILY lane -- the swing lane, the one the principal named
    in the same breath as the scalp lane -- would have been empty on all 250 symbols with nothing
    anywhere saying why. That is absence read as a clean verdict (WS-005), on a whole timeframe.

    Deriving from the span makes the rule the same rule everywhere: "at least as much market time
    as 3,000 hourly bars", i.e. ~125 trading days. It is the identity at H1, so the admission
    decision -- which symbols are in the universe at all -- is byte-identical to before.
    """
    from mt5desk.universe_registry import min_bars_for
    return min_bars_for(timeframe, h1_floor=MIN_BARS)




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
    tf_written: dict[str, list[str]] = {}
    tf_thin: dict[str, list[str]] = {}
    by_class: dict[str, int] = {}

    for s in tradable:
        name = s.name
        asset_class = str(getattr(s, "path", "")).split("\\")[0] or "Unknown"
        # SELECT BEFORE COPY. An unselected symbol returns no rates and would look like a dead
        # instrument rather than one nobody had asked for.
        if not mt5.symbol_select(name, True):
            failed.append({"symbol": name, "why": "symbol_select refused"})
            continue
        # EVERY CHART THE BROKER WILL GIVE. H1 remains the ADMISSION timeframe: a symbol that
        # cannot support the ten gates hourly is not in the universe at all, so the registry's
        # meaning is unchanged and nothing downstream that assumes an H1 file breaks. The finer
        # and slower charts are then fetched beside it, each judged on its own bar count.
        wrote: list[str] = []
        thin: list[str] = []
        h1_rates = None
        for tf in TIMEFRAMES:
            code = getattr(mt5, f"TIMEFRAME_{tf}", None)
            if code is None:                      # a broker/terminal without this chart
                thin.append(f"{tf}:unsupported")
                continue
            rates = mt5.copy_rates_range(name, code, start, now)
            n = 0 if rates is None else len(rates)
            if tf == "H1":
                h1_rates = rates
            if n < min_bars(tf):
                # NOT A FAILURE. Brokers keep far less M1 than H1; a chart too short for the
                # gates is recorded with its count so the gap is visible rather than inferred.
                # The floor is the SAME MARKET TIME on every chart -- see min_bars().
                thin.append(f"{tf}:{n}/{min_bars(tf)}")
                continue
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.set_index("time").sort_index()
            try:
                df.to_parquet(UNIVERSE / f"{name}_{tf}.parquet")
            except Exception as exc:
                failed.append({"symbol": name, "tf": tf, "why": f"{type(exc).__name__}: {exc}"})
                continue
            wrote.append(tf)

        # ADMISSION IS STILL H1. Without it there is no walk-forward the ten gates can run.
        if h1_rates is None or len(h1_rates) < min_bars("H1") or "H1" not in wrote:
            short.append({"symbol": name, "class": asset_class,
                          "bars": 0 if h1_rates is None else len(h1_rates),
                          "timeframes_written": wrote, "timeframes_thin": thin,
                          "why": f"fewer than {MIN_BARS} H1 bars -- cannot support the ten gates; "
                                 f"recorded rather than silently dropped"})
            continue
        out = UNIVERSE / f"{name}_H1.parquet"
        existed = out.exists()
        (refreshed if existed else added).append(name)
        by_class[asset_class] = by_class.get(asset_class, 0) + 1
        tf_written[name] = wrote
        if thin:
            tf_thin[name] = thin

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
                # WHICH CHARTS THIS SYMBOL ACTUALLY HAS. A family that needs M5 can now ask
                # rather than assume, and a thin chart is named with its bar count instead of
                # being discovered as a missing file at gauntlet time.
                "timeframes": tf_written.get(name, ["H1"]),
                "timeframes_thin": tf_thin.get(name, []),
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
        "timeframes_requested": list(TIMEFRAMES),
        "min_bars_by_timeframe": {tf: min_bars(tf) for tf in TIMEFRAMES},
        "timeframe_coverage": {tf: sum(1 for w in tf_written.values() if tf in w)
                               for tf in TIMEFRAMES},
        "timeframes_thin": tf_thin,
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
