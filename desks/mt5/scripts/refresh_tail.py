"""Incremental tail refresh for cached MT5 universe parquets.

Fetches only recent bars per symbol, appends new CLOSED bars to the
existing parquet, dedupes by timestamp, saves in-place.
Also records the MT5 server name so the VPS can verify promotion_authority.
Run on the Windows box where MetaTrader5 is available.

AND DERIVES THE SERIES NOBODY DOWNLOADS. `<SYM>_D1.parquet` is built here from the symbol's own
H1 file, because the daily clock is a clock this desk declares and has never had a file for --
see `DERIVED` below for what its absence cost. Derivation needs no terminal, so it runs on the
VPS pass too, where the terminal is absent and the honest return code is 2.
"""

import json
import sys
from pathlib import Path

try:
    import MetaTrader5 as mt5
except ImportError:
    # NOT THE WINDOWS BOX. This used to be a bare top-level import, so the module could not even
    # be LOADED anywhere else -- and `daily_cycle._refresh_bars` does `import refresh_tail`
    # before calling it, so the VPS's step died on the import rather than on the terminal check
    # it was written to survive. `main()` returns 2 for that, which the cycle already tolerates;
    # everything in here that needs no terminal (the D1 derivation) still runs first.
    mt5 = None                                                   # type: ignore[assignment]
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
#: Every timeframe this desk stores, with its bar length in seconds. The seconds are what let the
#: fetch SIZE ITSELF against the gap instead of assuming one: 200 bars is eight days at H1 and
#: sixteen HOURS at M5, so the single constant that worked for hourly bars silently could not
#: reach back far enough for anything faster.
TIMEFRAMES: dict[str, int] = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "D1": 86400,
}
#: Ceiling on one fetch. The box has 8GB and this runs beside the gauntlet; a year of M1 is 525k
#: bars and would be a memory event, not a refresh. When the gap exceeds this the run says so
#: rather than writing a file with a hole in it.
MAX_FETCH = 50_000

#: Series this desk BUILDS from a finer one it already holds, rather than fetching: `{derived:
#: source}`. Only D1 so far, and it exists because of a hole with a price on it.
#:
#: MEASURED 2026-09-09 in this tree. `state_vector_build.ASSET_CLOCKS` declares six clocks
#: including `daily` and `weekly`, and `BAR_SUFFIXES` searched `M5, M15, H1` finest-first and
#: returned ONE series for every clock. `XAUUSD_M5.parquet` holds 20,000 bars over 73 days while
#: `XAUUSD_H1.parquet` holds 49,964 over 2,181 -- so once gold acquired M5 bars, `XAUUSD@daily`
#: saw 73 observations against a floor of 250 and `XAUUSD@weekly` saw 15 against 120. Both
#: refused. `XAUUSD@daily` IS the state vector's `global` state, the book-wide regime the
#: allocator's world draw reads: downloading finer bars for gold silently turned it off.
#:
#: A file of the daily clock's own is what stops that class of accident: the daily tier stops
#: depending on which intraday file happens to exist for a symbol this week.
DERIVED: dict[str, str] = {"D1": "H1"}
#: What was derived, from what, and when. Read by `refresh_symbol` so a derived series is never
#: FETCHED -- see the refusal there.
DERIVED_MANIFEST = OUT / "derived_series.json"
#: Aggregating a bar from finer bars. `spread` is a level and averages; the volumes are flows and
#: sum. Anything the source lacks is simply not carried, never invented.
BAR_AGG: dict[str, str] = {"open": "first", "high": "max", "low": "min", "close": "last",
                           "tick_volume": "sum", "spread": "mean", "real_volume": "sum"}


def _mt5_timeframe(tf: str) -> int | None:
    return getattr(mt5, f"TIMEFRAME_{tf}", None)


def _rule(tf: str) -> str:
    """The pandas offset for one bar of `tf`, from the sweep's own timeframe table.

    Reused rather than re-tabulated: `orthogonal_sweep` already resamples every chart the desk
    hunts on, and two tables of bar lengths is how a D1 file ends up with H4 bars in it.
    """
    try:
        from research.orthogonal_sweep import _resample_rule
        return _resample_rule(tf)
    except ImportError:                                          # bare-script path, no package
        from mt5desk.universe_registry import timeframe_minutes
        return f"{timeframe_minutes(tf)}min"


def _derived_names() -> set[str]:
    """`{"XAUUSD_D1", ...}` -- the (symbol, timeframe) files this desk builds rather than fetches.

    Read off the manifest so it names the files that were ACTUALLY derived on this box, not the
    ones that would be if the source existed.
    """
    try:
        doc = json.loads(DERIVED_MANIFEST.read_text("utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(k) for k in (doc.get("series") or {})}


def resample_bars(bars: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Aggregate finer bars into `tf` bars, dropping the one still forming.

    THE LAST BAR IS DROPPED UNCONDITIONALLY, the same rule `refresh_symbol` applies to a fetch.
    The source's tail is by construction the last CLOSED finer bar, so the calendar day it falls
    in is almost always still open -- and a daily bar whose close is really 14:00's close is not
    a late bar, it is a WRONG one, and it would be silently corrected tomorrow with no reader
    able to tell it had ever been wrong. One day of latency on a 250-day clock is the cheap side.
    """
    agg = {c: how for c, how in BAR_AGG.items() if c in bars.columns}
    if "close" not in agg:
        return bars.iloc[0:0]
    out = bars.resample(_rule(tf)).agg(agg).dropna(subset=["close"])
    return out.iloc[:-1]


def derive_series(sym: str, tf: str = "D1") -> str:
    """Build `<sym>_<tf>.parquet` from its finer source. Returns a status line, never raises."""
    src_tf = DERIVED.get(tf)
    if src_tf is None:
        return f"not-a-derived-timeframe({tf})"
    src = OUT / f"{sym}_{src_tf}.parquet"
    if not src.exists():
        # ABSENCE IS NEVER A PASS: a symbol with no source is REPORTED, not counted as derived.
        return f"no-{src_tf}-source"
    try:
        bars = pd.read_parquet(src)
    except Exception as e:
        return f"unreadable-source({type(e).__name__})"
    if bars.empty or not isinstance(bars.index, pd.DatetimeIndex):
        return "source-carries-no-bar-index"
    bars = bars.sort_index()
    if bars.index.tz is None:
        # Same restoration `refresh_symbol` performs, and for the same reason: these stamps come
        # from MT5 `rates["time"]`, UNIX EPOCH SECONDS, so the instants are unambiguous.
        bars = bars.copy()
        bars.index = bars.index.tz_localize("UTC")
    out = resample_bars(bars, tf)
    if out.empty:
        return f"source-too-short({len(bars)} {src_tf} bars)"
    out.to_parquet(OUT / f"{sym}_{tf}.parquet")
    return f"{len(out)} bars (last {out.index.max().date()}) from {src.name}"


def book_symbols() -> tuple[list[str], str]:
    """Symbols to derive for, and where the list came from.

    The BOOK, read through the same `state_vector_build.book_symbols` the state vector uses, so
    the two can never disagree about what the book holds. When that import is unavailable the
    fallback is every symbol with a source file -- wider, never narrower, because a derived file
    that silently stops being produced is the failure this whole module exists to prevent.
    """
    try:
        from research.state_vector_build import book_symbols as _book
        syms = [s for s in _book() if (OUT / f"{s}_H1.parquet").exists()]
        if syms:
            return syms, "book (UNIVERSAL_SURVIVORS.canon.json)"
    except ImportError:
        pass
    # THE PATTERN COMES FROM `DERIVED`, NEVER A LITERAL. Not only because the source timeframe
    # must be able to change in one place: a literal one-timeframe glob in this file is exactly
    # the defect `test_every_timeframe_is_eligible` fences, and that fence reads raw text.
    src_tf = next(iter(DERIVED.values()))
    return (sorted({p.stem.rpartition("_")[0] for p in OUT.glob(f"*_{src_tf}.parquet")}),
            f"every symbol holding a {src_tf} file (book unreadable here)")


def derive_all(symbols: list[str] | None = None) -> dict:
    """Rebuild every derived series and write the manifest. Needs no terminal."""
    scope = "caller-supplied"
    if symbols is None:
        symbols, scope = book_symbols()
    series: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    for tf, src_tf in DERIVED.items():
        for sym in sorted(symbols):
            status = derive_series(sym, tf)
            name = f"{sym}_{tf}"
            if status[0].isdigit():
                series[name] = {"derived_from": f"{sym}_{src_tf}", "status": status}
            else:
                skipped[name] = status
    doc = {"scope": scope, "n_symbols": len(symbols),
           "series": series, "skipped": skipped,
           "why_not_fetched": ("A derived daily bar is stamped at 00:00 UTC; the broker's own D1 "
                               "bar is stamped at ITS day start. Concatenating the two would put "
                               "two bars in every day at two different instants, so a series "
                               "listed here is rebuilt from its source and never fetched.")}
    DERIVED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    DERIVED_MANIFEST.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    return doc


def refresh_symbol(sym: str, tf: str = "H1") -> str:
    """Refresh one (symbol, timeframe) parquet.

    THE TIMEFRAME WAS HARDCODED HERE AND IN THE CALLER'S GLOB, and that is the whole reason the
    gold scalp sleeves could never mature. MEASURED 2026-09-06: XAUUSD_M5, _M15 and _M1 held no
    bar after 2026-08-21 23:55, and the three gold scalp sleeves went on their forward clock on
    2026-08-22. They have therefore had ZERO bars for the entire life of that clock -- which is
    why all three sat at forward n=0 with 39/65/69 observations tagged historical, and why the
    answer to "are the two gold sleeves ready" kept being assembled from selection-era rows.

    It was not a quiet market and it was not a state file failing to persist. The instruments
    they trade had not been updated since the day before they started.
    """
    pq = OUT / f"{sym}_{tf}.parquet"
    if not pq.exists():
        return "no-cache"
    # A DERIVED SERIES IS REBUILT, NEVER FETCHED. Our D1 bars are stamped 00:00 UTC because they
    # are an aggregate of UTC-stamped H1 bars; the terminal's own D1 bar is stamped at the
    # BROKER's day start, which is 21:00 or 22:00 UTC. Fetching into this file would therefore
    # append a second bar for every day at a different instant, and the dedupe -- which keys on
    # the timestamp -- would keep both. `derive_all` refreshes it from the source instead, after
    # the source itself has been extended.
    if f"{sym}_{tf}" in _derived_names():
        return f"derived from {DERIVED.get(tf, '?')} -- rebuilt, not fetched"
    seconds = TIMEFRAMES.get(tf)
    period = _mt5_timeframe(tf)
    if seconds is None or period is None:
        # ABSENCE IS NEVER A PASS. An unknown timeframe is reported, never silently skipped as if
        # it had been refreshed -- a skip that reads as success is how this failure lasted weeks.
        return f"unknown-timeframe({tf})"
    old = pd.read_parquet(pq)
    # SELECT BEFORE YOU READ. A symbol absent from Market Watch is not subscribed, so
    # `copy_rates_from_pos` serves whatever history happens to be cached and reports no error --
    # the terminal answers, just not with current bars. MEASURED 2026-08-27 on the desk box: with
    # no select, USDCAD (a Market Watch symbol) refreshed to 08-27 10:00 while US500 stopped at
    # 08-26 07:00 and USCOCOA at 08-25 20:00, all in the SAME run. That is the whole reason most
    # of the 295-symbol store sat days stale: not a broken refresher, a subscription nobody asked
    # for. `symbol_select` costs one call and makes the terminal fetch the real tail.
    mt5.symbol_select(sym, True)
    # SIZE THE FETCH TO THE GAP, NEVER TO A CONSTANT. A fixed 200 bars is eight days at H1 and
    # sixteen hours at M5, so on a file that had gone sixteen days stale a fixed fetch cannot
    # reach back to where the history stops -- and `concat` would then write a parquet with a
    # HOLE in it, which is worse than the stale file it replaced: a gap in bars is invisible to
    # every reader downstream and silently becomes a gap in a forward record.
    want = N_BARS
    if isinstance(old.index, pd.DatetimeIndex) and len(old):
        last = old.index.max()
        if last.tz is None:
            last = last.tz_localize("UTC")
        gap = (pd.Timestamp.now(tz="UTC") - last).total_seconds()
        want = max(N_BARS, int(gap // seconds) + N_BARS)
    capped = min(want, MAX_FETCH)
    rates = mt5.copy_rates_from_pos(sym, period, 0, capped)
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
    # A HOLE MUST NAME ITSELF. If the fetch still could not reach back to where the cache ends,
    # the file is about to gain a discontinuity. It is still better to hold the new bars than to
    # stay frozen, so the write proceeds -- but it says GAP, because a silent hole in a bar series
    # becomes a silent hole in a forward record and nothing downstream can tell the difference
    # between "no trade fired" and "no bar existed to fire on". That confusion is exactly what
    # cost the gold scalp sleeves sixteen days.
    hole = ""
    if len(old) and isinstance(old.index, pd.DatetimeIndex) and len(new):
        last_old = old.index.max()
        if last_old.tz is None:
            last_old = last_old.tz_localize("UTC")
        missing = (new.index.min() - last_old).total_seconds()
        if missing > 2 * seconds:
            hole = f" GAP {missing / 86400:.1f}d unfetched before {new.index.min()}"
    combined = pd.concat([old, new])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    added = len(combined) - len(old)
    combined.to_parquet(pq)
    return f"+{added} bars (last {combined.index.max()}){hole}"


def _report_derivation(doc: dict) -> None:
    n, skipped = len(doc.get("series") or {}), doc.get("skipped") or {}
    print(f"\nderived {n} series from finer bars ({doc.get('scope')})")
    if skipped:
        # Listed, not counted. A symbol that stops being derivable is exactly how the daily
        # clock went dark the first time, and a number nobody reads would hide it again.
        print(f"  {len(skipped)} not derived:")
        for name, why in sorted(skipped.items())[:12]:
            print(f"   {name:20s} {why}")


def main() -> int:
    """0 = refreshed, 2 = no terminal on this box (an honest answer, not a failure).

    RETURNS, NEVER `sys.exit`. This is called as a daily-cycle step, and `SystemExit` is a
    BaseException: a bare exit here would tear down the entire cycle -- promotion chain included
    -- because a terminal was shut, rather than skipping one step.
    """
    if mt5 is None or (mt5.terminal_info() is None and not mt5.initialize(path=TERMINAL)):
        # NO TERMINAL, BUT STILL WORK TO DO. The derived series are an aggregate of files this
        # box already holds, so they rebuild here as well as on the trading box -- which is what
        # keeps the daily clock alive on the VPS, where the terminal never exists.
        print("no MT5 terminal here"
              if mt5 is None else f"initialize failed: {mt5.last_error()}")
        _report_derivation(derive_all())
        return 2

    # Record broker server for promotion_authority on VPS
    account = mt5.account_info()
    server_name = getattr(account, "server", "unknown") if account else "unknown"
    is_fusion = "fusion" in server_name.lower()
    print(f"Broker server: {server_name} (Fusion={is_fusion})")

    # EVERY PARQUET IN THE LAKE, AT WHATEVER TIMEFRAME ITS NAME DECLARES. The glob was
    # `*_H1.parquet`, so the six non-H1 files in the store -- XAUUSD at M1/M5/M15 and three FX
    # crosses at M15 -- were never refreshed by anything, ever. They are not a rounding error:
    # they are the entire sub-hourly universe, and the gold scalp lane trades on them.
    #
    # The timeframe now comes from the FILENAME rather than a constant, so adding a symbol at a
    # new timeframe makes it eligible immediately, with nothing here to edit. A file whose suffix
    # this desk does not recognise is REPORTED, never skipped in silence.
    results = []
    broker_info: dict[str, dict] = {}
    for pq in sorted(OUT.glob("*.parquet")):
        sym, _, tf = pq.stem.rpartition("_")
        if not sym:
            results.append(f"{pq.stem:16s} unparseable-name")
            print(results[-1], flush=True)
            continue
        try:
            status = refresh_symbol(sym, tf)
        except Exception as e:
            status = f"error:{e}"
        results.append(f"{sym}_{tf:<16s} {status}")
        print(results[-1], flush=True)
        # Record server for this symbol (once; the broker is a property of the symbol, not of
        # the timeframe we happen to be holding for it).
        if sym not in broker_info and mt5.symbol_info(sym):
            broker_info[sym] = {
                "server": server_name,
                "is_fusion": is_fusion,
                "account": getattr(account, "login", 0) if account else 0,
            }
    ok = sum(1 for r in results if " +" in r)
    holes = [r for r in results if "GAP" in r]
    print(f"\n{ok}/{len(results)} (symbol, timeframe) series refreshed "
          f"across {len(broker_info)} symbol(s)")
    if holes:
        # Loud, and listed. A gap that only appears as a suffix on one line of a 300-line log is
        # a gap nobody reads.
        print(f"\n{len(holes)} series could not be bridged and now carry a hole:")
        for row in holes:
            print(f"   {row}")

    # AFTER the fetch loop, never before: a derived series is only as fresh as the source it was
    # built from, and building it first would leave the daily clock a full pass behind the hourly.
    _report_derivation(derive_all())

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
