"""Download bars for ALL broker-enabled MT5 symbols at EVERY timeframe, and build
universe.json. Runs on Windows where MetaTrader5 is installed. Then SCP to VPS.

Was H1-only, and not by choice -- see the TIMEFRAME_DEPTH block below.
"""
import json
import os
import re
import sys
import time
import atexit
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk.config import desk_root, terminal_path
from mt5desk.universe_registry import TIMEFRAMES as CANONICAL_TIMEFRAMES
from mt5desk.universe_registry import cost_fields_from_symbol_info, merge

# PATHS COME FROM `desk_root()`, NEVER A USERNAME (LAWS §1 anti-hardcode; the helper's own
# docstring records that twenty-one files hardcoded `C:\\Users\\dell\\...`, "which meant the desk
# could only ever run on one machine under one username"). This one never adopted it, so on the
# trading box it targeted a directory that does not exist -- which is why NOTHING on that box
# refreshes its bars and most of its 295 parquets were ~28h stale on 2026-08-27. `MT5_DESK_ROOT`
# still overrides, so a machine keeping its store elsewhere sets one env var.
#
# THE CALL SAT FOUR LINES ABOVE ITS OWN IMPORT until 2026-09-06, so this module raised
# `NameError: name 'desk_root' is not defined` at import and could not run AT ALL -- the fix that
# adopted desk_root() introduced the ordering fault in the same edit, and the two cancelled into
# a script that looks correct and has never once executed.
OUT_DIR = desk_root() / "data" / "universe"
OUT_DIR.mkdir(parents=True, exist_ok=True)

UNIVERSE_OUT = OUT_DIR / "universe.json"
VERDICTS_OUT = desk_root() / "data" / "bar_coverage_verdicts.json"


# ONE LAYOUT. The desk keeps bars as `data/universe/<SYM>_<TF>.parquet` -- that is where
# `refresh_tail` reads them and where all 295 on the desk box actually live. A `parquets/`
# subdirectory would make this writer's `existing` check see an empty store and
# re-download the entire universe into a directory nothing else reads. The `<TF>` suffix is
# load-bearing, not decoration: it is how `refresh_tail` knows which timeframe to request from
# the terminal, so a file named without one cannot be kept current.
PARQUET_DIR = OUT_DIR
PARQUET_DIR.mkdir(parents=True, exist_ok=True)


#: MetaTrader5's own IPC failures (-10001 send, -10002 receive, -10003 init, -10004 no connection,
#: -10005 timeout). They say the TERMINAL LINK was down, never that the broker has no chart.
#: Measured 2026-09-29: 1,437 of 1,439 BROKER_SERVES_NOTHING rows carried `(-10004, 'No IPC
#: connection')`, all re-stamped in one outage at 10:00 UTC. Each read as a fresh venue refusal,
#: so the hourly pass skipped every missing chart for a day, and the next outage restamped them.
#: 296 of the 602 FX charts were absent while the terminal served the same bars live.
TERMINAL_ERROR_MAX = -10000


def _is_terminal_error(err: object) -> bool:
    """True for an MT5 IPC failure code, given `mt5.last_error()` or a verdict's `why` text."""
    code = err[0] if isinstance(err, tuple) and err else None
    if code is None:
        m = re.search(r"last_error \((-?\d+)", str(err or ""))
        code = int(m.group(1)) if m else None
    try:
        return code is not None and int(code) <= TERMINAL_ERROR_MAX
    except (TypeError, ValueError):
        return False


def _is_refusal(row: dict) -> bool:
    """A BROKER_SERVES_NOTHING verdict the broker actually gave, not a dropped terminal link."""
    return (row.get("verdict") == "BROKER_SERVES_NOTHING"
            and not _is_terminal_error(row.get("why")))


def _fresh(row: dict, seconds: int) -> bool:
    try:
        stamp = datetime.fromisoformat(str(row.get("at") or "").replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return False
    return (datetime.now(UTC) - stamp).total_seconds() < seconds


def _all_cells_accounted_for() -> tuple[bool, int, int]:
    """Fast path: physical chart or still-fresh explicit venue refusal for every registry cell."""
    try:
        registry = json.loads(UNIVERSE_OUT.read_text("utf-8-sig"))
        verdict_doc = json.loads(VERDICTS_OUT.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return False, 0, 0
    if not isinstance(registry, dict) or not isinstance(verdict_doc, dict):
        return False, 0, 0
    cells = verdict_doc.get("cells") or {}
    if not isinstance(cells, dict):
        return False, 0, 0
    wanted = [x.strip().upper() for x in os.environ.get(
        "MT5_TIMEFRAMES", ",".join(CANONICAL_TIMEFRAMES)).split(",") if x.strip()]
    physical = refused = 0
    for symbol in registry:
        wildcard = cells.get(f"{symbol}_*") or {}
        for tf in wanted:
            if (PARQUET_DIR / f"{symbol}_{tf}.parquet").exists():
                physical += 1
                continue
            row = cells.get(f"{symbol}_{tf}") or {}
            if _is_refusal(row) and _fresh(row, 24 * 3600):
                refused += 1
                continue
            if (wildcard.get("verdict") == "NOT_OFFERED" and _fresh(wildcard, 7 * 24 * 3600)):
                refused += 1
                continue
            return False, physical, refused
    return True, physical, refused


_accounted, _physical_count, _refused_count = _all_cells_accounted_for()
if _accounted:
    print(f"Universe current: {_physical_count} physical chart(s), {_refused_count} fresh explicit "
          "venue refusal(s); no Fusion request is due")
    raise SystemExit(0)

# Heavy imports and Fusion ownership happen ONLY when a cell is genuinely due. MetaTrader5 can
# block while resolving IPC and Arrow/NumPy reserve substantial commit; importing either before
# the current-ledger fast path made a no-op hourly task consume resources and sometimes hang.
import MetaTrader5 as mt5  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from research.expand_universe import _pull_bars  # noqa: E402
from research.job_lock import exclusive_job  # noqa: E402
from research.mt5_session import attach_or_initialize  # noqa: E402

# The canonical gauntlet samples Fusion-native costs while this collector walks the complete
# broker chart ladder. Both opening the terminal at once interrupted the 2026-09-28 rebuild.
_terminal_lane = exclusive_job("fusion_terminal_research_lane", need_mb=0)
if not _terminal_lane.__enter__():
    print("download_all_symbols: DEFERRED -- Fusion research terminal lane is busy")
    raise SystemExit(0)
atexit.register(lambda: _terminal_lane.__exit__(None, None, None))

if not attach_or_initialize(mt5, path=terminal_path(), timeout=30_000):
    print(f"UNMEASURED: authenticated Fusion terminal is unavailable ({mt5.last_error()}); "
          "no broker chart was relabelled as missing")
    raise SystemExit(2)
info = mt5.terminal_info()
if info is None:
    print(f"UNMEASURED: Fusion attach returned no terminal info ({mt5.last_error()}); "
          "no broker chart was relabelled as missing")
    raise SystemExit(2)
print(f"Terminal: {info.name}, connected={info.connected}")

syms = mt5.symbols_get()
# `visible` is a TERMINAL UI state, not a broker-universe property.  Filtering on it left a
# hidden-but-tradable pair (measured: EURCAD M15) permanently absent even though every hourly
# pass claimed to cover the full broker.  Select every enabled instrument below; MT5 will make
# it visible before the request.  A failed select/request is recorded as a cell verdict rather
# than silently shrinking the denominator.
tradable = [s for s in syms if s.trade_mode > 0]
print(f"Tradable symbols: {len(tradable)}")

# Build universe.json + download bars at every eligible timeframe
universe = {}
failed = []
cell_verdicts = {}
# EVERY TIMEFRAME IS ELIGIBLE, AND `existing` IS KEYED BY (SYMBOL, TIMEFRAME).
#
# It used to be keyed by SYMBOL alone, computed from `*_H1.parquet`. So the moment a symbol had
# an H1 file this downloader considered it finished and would never fetch a second timeframe for
# it -- not once, not ever. That is why the store held 82 symbols at H1 and exactly six non-H1
# files in total, all placed by hand: XAUUSD at M1/M5/M15 and three FX crosses at M15. The desk
# was structurally hourly-only and nothing said so; it looked like a choice.
#
# Depths are per timeframe so each covers a comparable SPAN rather than a comparable bar count:
# 50k bars is six years of H1 and thirty-five days of M1, and a scalp mechanism judged on
# thirty-five days of history is not judged at all.
TIMEFRAME_DEPTH: dict[str, int] = {
    "M1": 200_000, "M5": 120_000, "M15": 80_000, "M30": 60_000,
    "H1": 50_000, "H4": 30_000, "D1": 10_000,
}
_WANTED = [tf.strip().upper() for tf in
           os.environ.get("MT5_TIMEFRAMES", ",".join(TIMEFRAME_DEPTH)).split(",") if tf.strip()]
TIMEFRAMES = [tf for tf in _WANTED if tf in TIMEFRAME_DEPTH]
if not TIMEFRAMES:
    raise SystemExit(f"MT5_TIMEFRAMES={_WANTED} names no timeframe this desk stores "
                     f"({', '.join(TIMEFRAME_DEPTH)}) -- refusing to download nothing quietly")

existing = {(f.stem.rpartition("_")[0], f.stem.rpartition("_")[2])
            for f in PARQUET_DIR.glob("*.parquet") if "_" in f.stem}
print(f"Already downloaded: {len(existing)} (symbol, timeframe) series "
      f"across {len({s for s, _ in existing})} symbols")

_prior = {}
if UNIVERSE_OUT.exists():
    try:
        _prior = json.loads(UNIVERSE_OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"  WARN: prior universe.json unreadable ({exc}); rebuilding from Parquet metadata")
        _prior = {}

_verdict_doc = {}
if VERDICTS_OUT.exists():
    try:
        _verdict_doc = json.loads(VERDICTS_OUT.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        _verdict_doc = {}
_prior_cells = _verdict_doc.get("cells") if isinstance(_verdict_doc, dict) else {}
if not isinstance(_prior_cells, dict):
    _prior_cells = {}


def _recent_no_data(symbol: str, timeframe: str) -> bool:
    """Do not re-spend the whole hour on a venue refusal measured less than a day ago."""
    row = _prior_cells.get(f"{symbol}_{timeframe}") or {}
    if not _is_refusal(row):
        return False
    try:
        stamp = datetime.fromisoformat(str(row.get("at") or "").replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
    except ValueError:
        return False
    return (datetime.now(UTC) - stamp).total_seconds() < 24 * 3600


jobs = [(s, tf) for s in tradable for tf in TIMEFRAMES
        if (s.name, tf) not in existing and not _recent_no_data(s.name, tf)]
deferred_no_data = sum(1 for s in tradable for tf in TIMEFRAMES
                       if (s.name, tf) not in existing and _recent_no_data(s.name, tf))
print(f"To download: {len(jobs)} series over timeframes {', '.join(TIMEFRAMES)}")
print(f"Fresh broker no-data verdicts deferred until daily retry: {deferred_no_data}")

_warmed_symbols: set[str] = set()
_hydration_retried: set[str] = set()
_history_start = datetime(2015, 1, 1, tzinfo=UTC)

for i, (sym_info, tf) in enumerate(jobs):
    name = sym_info.name
    period = getattr(mt5, f"TIMEFRAME_{tf}", None)
    if period is None:
        print(f"  [{i+1}/{len(jobs)}] {name:25s} {tf:4s} NO SUCH TIMEFRAME IN MT5")
        failed.append(f"{name}_{tf}")
        cell_verdicts[f"{name}_{tf}"] = {
            "verdict": "NO_SUCH_TIMEFRAME", "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "bars": 0, "why": f"this terminal has no TIMEFRAME_{tf} constant",
        }
        continue
    point = sym_info.point
    digits = sym_info.digits
    spread_pts = sym_info.spread
    contract_size = getattr(sym_info, "trade_contract_size", 1.0)
    volume_min = sym_info.volume_min
    path = sym_info.path.replace("\\", "/")
    category = path.split("/")[0] if "/" in path else "Root"
    spread_price = spread_pts * point

    selected = bool(mt5.symbol_select(name, True))
    # Selecting a hidden broker symbol starts an asynchronous terminal history subscription.
    # Asking in the same instruction frequently returns an empty first read and used to stamp
    # every chart on that instrument BROKER_SERVES_NOTHING. Warm once per symbol, then reuse the
    # canonical chunked puller (position request to hydrate, range fallback, older chunks). If
    # the first cell is still empty, one bounded retry gives the subscription time to settle;
    # subsequent charts reuse the already-warm symbol and never pay another delay.
    if selected and name not in _warmed_symbols:
        time.sleep(1.0)
        _warmed_symbols.add(name)
    rates = _pull_bars(mt5, name, period, TIMEFRAME_DEPTH[tf], _history_start,
                       datetime.now(UTC))
    if (rates is None or len(rates) == 0) and selected and name not in _hydration_retried:
        time.sleep(2.0)
        _hydration_retried.add(name)
        rates = _pull_bars(mt5, name, period, TIMEFRAME_DEPTH[tf], _history_start,
                           datetime.now(UTC))

    if rates is None or len(rates) == 0:
        _err = mt5.last_error()
        if _is_terminal_error(_err):
            # THE LINK IS DOWN, NOT THE CHART. Recorded as such (never a refusal, so the next
            # hourly pass asks again) and the pass stops: every remaining request would fail the
            # same way and, before this, was stamped as a venue refusal one by one.
            print(f"  [{i+1}/{len(jobs)}] {name:25s} {tf:4s} TERMINAL UNAVAILABLE {_err}: "
                  f"stopping; {len(jobs) - i - 1} chart(s) left for the next pass")
            failed.append(f"{name}_{tf}")
            cell_verdicts[f"{name}_{tf}"] = {
                "verdict": "TERMINAL_UNAVAILABLE",
                "at": datetime.now(UTC).isoformat(timespec="seconds"), "bars": 0,
                "why": f"terminal IPC failure, not a broker answer (last_error {_err})",
            }
            break
        print(f"  [{i+1}/{len(jobs)}] {name:25s} {tf:4s} NO DATA")
        failed.append(f"{name}_{tf}")
        cell_verdicts[f"{name}_{tf}"] = {
            "verdict": "BROKER_SERVES_NOTHING",
            "at": datetime.now(UTC).isoformat(timespec="seconds"), "bars": 0,
            "why": (f"broker-enabled symbol; symbol_select={selected}; {tf} request returned "
                    f"no bars (last_error {_err})"),
        }
        continue

    df = pd.DataFrame(rates)
    # utc=True IS LOAD-BEARING: MT5 `rates["time"]` is Unix EPOCH SECONDS, so the instants
    # are unambiguous, but pandas drops the tz label without it and `h1_source._normalise`
    # then REFUSES the file ("bar index is timezone-naive"). Five bulk downloaders omitted
    # it while every other producer passed it, so 173 of 197 H1 parquets were unreadable by
    # the shadow/forward chain -- a 197-symbol universe that was effectively 24 symbols.
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.set_index("time", inplace=True)
    df.sort_index(inplace=True)

    pq_path = PARQUET_DIR / f"{name}_{tf}.parquet"
    df.to_parquet(pq_path, engine="pyarrow")
    # A prior negative verdict must not survive after the chart has been filled.
    cell_verdicts[f"{name}_{tf}"] = {
        "verdict": "FILLED", "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "bars": len(df), "span_start": str(df.index[0]), "span_end": str(df.index[-1]),
        "why": "bulk broker-universe collector selected the symbol and wrote the chart",
    }

    # THE REGISTRY ROW IS PER SYMBOL, NOT PER SERIES. point/digits/spread/contract_size are
    # properties of the instrument and identical at every timeframe, so the first series to
    # arrive writes them. Only the bar census below is timeframe-specific, and it is keyed as
    # such -- overwriting `bars`/`first_bar`/`last_bar` on each pass would leave the registry
    # describing whichever timeframe happened to be downloaded last.
    universe.setdefault(name, {}).setdefault("series", {})[tf] = {
        "bars": len(df), "first_bar": str(df.index[0]), "last_bar": str(df.index[-1]),
    }
    universe[name] |= {
        "point": point,
        "digits": digits,
        "tick_size": point,
        "median_spread_pts": spread_pts,
        "spread_price": round(spread_price, 6),
        "contract_size": contract_size,
        "volume_min": volume_min,
        "category": category,
        # THE FIELD WHOSE ABSENCE MAKES 42% OF THE UNIVERSE UNPRICEABLE. `tick_value` is the only
        # field carrying a price in ACCOUNT currency, so without it `spread_cost_per_lot` returns
        # 0.0 and gate 8 (stress_costs) cannot judge the candidate at all. Measured 2026-08-27:
        # 82 of 197 registry rows had none -- 67 Equities, 15 Indices, 23 uncategorised -- because
        # the ONLY producer that ever wrote it (`fetch_universe.py`) carries a hardcoded 32-symbol
        # list. The terminal has had the answer in hand on every one of these iterations and this
        # writer was dropping it. `currency_profit` rides along because it is MT5's OWN answer to
        # the denomination question, and it is the only correct route for a share or index CFD
        # whose name ("3M", "AUS200") carries no code to parse -- see universe_registry.
        **cost_fields_from_symbol_info(sym_info),
        # Kept for every reader that predates `series` and asks for the flat fields. They now
        # describe the LONGEST series held, which is the honest answer to "how much history is
        # there for this symbol" -- not whichever timeframe finished last.
        **max((s for s in universe[name]["series"].values()), key=lambda s: s["bars"]),
    }

    print(f"  [{i+1}/{len(jobs)}] {name:25s} {tf:4s} {len(df):7d} bars ({category})")

# Also load already-existing series into the universe, at every timeframe on disk.
for sym_name, sym_tf in sorted(existing):
    pq_path = PARQUET_DIR / f"{sym_name}_{sym_tf}.parquet"
    if not pq_path.exists():
        continue
    sym_info_list = [s for s in tradable if s.name == sym_name]
    if not sym_info_list:
        continue
    si = sym_info_list[0]
    path = si.path.replace("\\", "/")
    cat = path.split("/")[0] if "/" in path else "Root"
    row = universe.setdefault(sym_name, {})
    # Rebuilding the registry used to materialise all 285 complete DataFrames after the broker
    # sweep. Arrow retains allocation pools, so the pass exhausted Windows commit and died even
    # though it needed only three scalars. Row count is Parquet metadata; existing span stamps
    # are authoritative for unchanged files. A missing historical stamp stays explicit instead
    # of spending gigabytes to rediscover it.
    meta = pq.ParquetFile(pq_path).metadata
    prior_series = (((_prior.get(sym_name) or {}).get("series") or {}).get(sym_tf) or {})
    first_bar = prior_series.get("first_bar")
    last_bar = prior_series.get("last_bar")
    row.setdefault("series", {})[sym_tf] = {
        "bars": int(meta.num_rows),
        "first_bar": first_bar if first_bar is not None else "UNMEASURED",
        "last_bar": last_bar if last_bar is not None else "UNMEASURED",
    }
    row |= {
        "point": si.point, "digits": si.digits, "tick_size": si.point,
        "median_spread_pts": si.spread,
        "spread_price": round(si.spread * si.point, 6),
        "contract_size": getattr(si, "trade_contract_size", 1.0),
        "volume_min": si.volume_min, "category": cat,
        **cost_fields_from_symbol_info(si),
        **max((s for s in row["series"].values()), key=lambda s: s["bars"]),
    }

mt5.shutdown()

# Save universe.json -- MERGED, never clobbered, and it now actually writes.
# TWO DEFECTS IN ONE LINE (measured 2026-08-27):
#   1. `json.dumps(..., encoding="utf-8")` raises `TypeError: JSONEncoder.__init__() got an
#      unexpected keyword argument 'encoding'` on every Python 3. This script did the ENTIRE
#      download -- hundreds of symbols, minutes of terminal I/O -- and then died on the write, so
#      nobody who ran it ever got a universe.json out of it. `encoding` belongs to write_text.
#   2. It CLOBBERED. `universe_registry` exists because three producers each wrote their own
#      field set over the others, and this script is named in its docstring as one of the three;
#      the merge it prescribes was never adopted here. A producer that does not know a field must
#      not be able to delete it.
_merged = merge(_prior, universe, source="download_all_symbols")
UNIVERSE_OUT.write_text(json.dumps(_merged, indent=2), encoding="utf-8")
print(f"universe.json: {len(universe)} row(s) this run merged into {len(_merged)} total")

# SAME VERDICT LEDGER AS `fill_bar_gaps.py`.  Preserve rows from the bounded gap filler and
# replace only cells this full-universe pass actually measured.  This closes the conservation
# hole where a failed request appeared only in stdout and vanished when the process exited.
_cells = _verdict_doc.get("cells") if isinstance(_verdict_doc, dict) else {}
if not isinstance(_cells, dict):
    _cells = {}
_cells.update(cell_verdicts)
_verdict_doc = {
    "at": datetime.now(UTC).isoformat(timespec="seconds"),
    "host": os.environ.get("COMPUTERNAME") or "unknown",
    "rule": ("one durable row per broker chart measured by either full-universe collection or "
             "bounded gap filling; a missing chart is never silently dropped"),
    "cells": _cells,
}
_tmp = VERDICTS_OUT.with_suffix(VERDICTS_OUT.suffix + ".tmp")
_tmp.write_text(json.dumps(_verdict_doc, indent=1), encoding="utf-8")
os.replace(_tmp, VERDICTS_OUT)

# Summary
cats = {}
for k, v in universe.items():
    c = v.get("category", "Root")
    cats.setdefault(c, []).append(k)

print(f"\n{'='*60}")
print(f"UNIVERSE BUILT: {len(universe)} symbols")
for c in sorted(cats):
    print(f"  {c:20s}: {len(cats[c])} symbols")
print(f"Failed: {len(failed)}: {failed[:10]}")
print(f"\nSaved to: {UNIVERSE_OUT}")
print(f"Parquets: {PARQUET_DIR}")
