"""THE MOAT, WRITTEN DOWN: every series only this desk has, registered, measured, and mined.

Ledger items C20/W13 (principal 2026-09-16). The desk's edge in data is not the bars -- anybody
can buy an H1 candle for XAUUSD. It is the series that exist because THIS desk stood in front of
THIS broker and recorded them: Fusion's own ticks, the point-in-time financing terms, the cost
surface fitted on the venue's stamped spread, a triangle's executability at a measured quote skew,
the fills the desk paid for, the verdicts its own gauntlet returned. Each is unbuyable after the
fact at any price, and nothing enumerated them -- so nothing could say how deep they ran, which
instruments they covered, or where they had holes, and `mined_ground.scan_moat` awarded the whole
tape 0.7% of one symbol's docket score because a ranking nudge was all it could reach.

1. A REGISTRY. Per series: owner organ, path pattern, cadence, first and last stamp, day depth,
   instrument coverage, rows, and MOAT SCORE = declared class weight x measured depth in days.
   The CLASS is declared, never inferred: this broker's ticks, its financing tape and this desk's
   own fills are `high` because no public source reproduces them after the fact; what is derived
   from them, and the gauntlet's verdicts, are `medium` -- anyone holding the same raw series
   recomputes those, so the moat is the raw series, not the arithmetic on top. The DEPTH is
   measured every run from the artifacts, and a series whose depth cannot be measured scores
   NOTHING and is named in `unmeasured`: absence is a verdict, not a zero (L1.28a, WS-005).

2. A BUILDER -- five series derived from the tape per instrument-day, vectorised over numpy with
   no python loop over ticks (the per-minute groupby is `bincount` over `unique(..., inverse)`):

     realised_spread_session  the quoted spread observed tick by tick, per session. "Realised"
                              means MEASURED FROM THE TAPE, not read off the broker's stamped bar
                              field, and it is NOT the trade-based realised spread of the
                              literature, which needs signed trades a CFD venue does not publish.
                              Carries `zero_spread_frac`: some symbols' tape repeats one side of a
                              one-sided update, and a 0.0 median must never read as free.
     quote_intensity          quotes per active minute (mean/median/p95), burstiness = sd/mean of
                              the per-minute count, longest silence. Two identical H1 candles from
                              80 and 4,000 quotes are different events; the bar cannot say so.
     ofi_proxy                the only order-flow imbalance a venue with no depth supports --
                              sign(mid - mid.shift(1)) summed per minute: upticks minus downticks.
     spread_vol_beta          OLS slope of the minute's mean spread_bps on its absolute log-return
                              variation in bps. Positive beta = the venue widens into movement,
                              the cost every breakout family pays and no bar reports.
     daily_quote_count        the census: quotes total and per session, distinct minutes and hours,
                              first and last stamp, quotes thrown out as unusable.

   Written to `data/moat/<series>/<SYM>.parquet`, one file per instrument, appended by day and
   deduplicated on `date`, so the store ACCUMULATES while one run stays cheap (`--max-days`,
   `--budget-s`). Families and the axis proposer read them via `series_frame(series, symbol)`.

3. COVERAGE WITH ITS GAPS NAMED. A universe instrument with no tape day in the last seven days is
   a NAMED GAP carrying its last-seen day, never a silent zero. The tick tape's 7-day instrument
   coverage is READ FROM `data/moat_coverage.json`: that organ measures it every five minutes, and
   a second number here would only be a second number to disagree with.

It does not recompute `recorders/tape_features.py` -- it REGISTERS that leg's outputs and reports
them UNMEASURED where this box has not run it. It proposes no hypothesis and judges nothing.

    python desks/mt5/research/moat_series.py                # measure, build, write
    python desks/mt5/research/moat_series.py --dry-run      # measure, build nothing, write nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA, REPORTS = _DESK / "data", _DESK / "reports"
TICKS, TERMS = DATA / "tape" / "ticks", DATA / "tape" / "contract_terms"
INTRABAR, STORE = DATA / "tape" / "intrabar", DATA / "moat"
UNIVERSE, MOAT_COVERAGE = DATA / "universe" / "universe.json", DATA / "moat_coverage.json"
COST_SURFACE, COST_SURFACE_TICK = DATA / "cost_surface.json", DATA / "cost_surface_tick.json"
SLIPPAGE_SURFACE, TRIANGLE = DATA / "tape" / "slippage_surface.json", (
    DATA / "tape" / "triangle_executable.json")
LIVE_LEDGER = DATA / "live_ledger.jsonl"
VERDICT_LEDGER = DATA / "hypotheses" / "gate_verdict_ledger.jsonl"
REPORT = REPORTS / "MOAT_SERIES.json"

RULE = ("the moat is the series only this desk has; every one is registered, measured for depth "
        "and coverage, and its gaps are named")

#: DECLARED. Changing either number re-prices every row in the artifact, so it is a decision, not
#: a constant: `high` = no public source reproduces it after the fact; `medium` = a competitor
#: holding the same raw series could recompute it.
MOAT_CLASS = {"high": 3.0, "medium": 1.5}
#: A universe instrument with no day inside this window is a GAP with a name and a last-seen date
#: -- the same window `moat_coverage.json` uses, so the two organs cannot disagree about it.
GAP_WINDOW_DAYS, GAP_CAP = 7, 40
#: Footers cost ~4 ms each and the tick tape is ~2,800 files. Row counts are worth that, never at
#: the derive phase's expense, so the scan carries its own stopwatch and reports PARTIAL.
FOOTER_BUDGET_S = 30.0
#: A regression on four minutes is not a measurement. Below this the day's beta is NaN.
MIN_REG_MINUTES = 20

try:  # the desk's ONE session vocabulary; a private copy here would become a second one
    from mt5desk.family_call import SESSIONS as _FAMILY_SESSIONS
except ImportError:  # pragma: no cover -- the desk package is importable on both boxes
    _FAMILY_SESSIONS = {}

#: `family_call.SESSIONS` states its windows in SERVER hours and the tape is stamped UTC; the two
#: differ by the venue's offset (+2 winter, +3 summer). The boundaries are kept IDENTICAL on
#: purpose, so a spread measured in "london" here means the window a cell certified in "london"
#: traded. Correcting the offset here would put this organ on a clock no certificate uses.
SESSIONS: dict[str, tuple[int, int]] = {
    k: v for k, v in (_FAMILY_SESSIONS or {}).items() if isinstance(v, tuple)
} or {"asia": (0, 8), "london": (8, 16), "ny": (14, 22)}

DERIVED_SERIES = ("realised_spread_session", "quote_intensity", "ofi_proxy", "spread_vol_beta",
                  "daily_quote_count")
_FIELDS = ("name", "owner", "kind", "path_pattern", "cadence", "moat_class", "why")
_REGISTERED: tuple[tuple[str, ...], ...] = (
    ("tick_tape", "moat/moat_recorder.py -> moat/moat_silver.py (MT5-MoatSilver)", "raw",
     "data/tape/ticks/<SYM>/<YYYY-MM-DD>.parquet", "hourly", "high",
     "Fusion's own quote updates; no vendor sells this broker's bid/ask at this timestamp."),
    ("financing_tape", "mt5desk/tape.py:record_contract_terms (MT5-MoatRecorder --terms-only)",
     "raw", "data/tape/contract_terms/<YYYY-MM-DD>.parquet", "daily", "high",
     "Point-in-time swap/margin/stops-level/trade-mode. symbol_info reports TODAY's values, so an "
     "unrecorded night is re-priced by tomorrow's registry forever."),
    ("live_fill_ledger", "mt5desk/gateway.py", "raw", "data/live_ledger.jsonl", "per fill", "high",
     "The desk's own fills against the quote it acted on: slippage at this broker, on this "
     "account, at this size. Nobody else holds one row of it."),
    ("gate_verdict_ledger", "scripts/external_gauntlet.py", "raw",
     "data/hypotheses/gate_verdict_ledger.jsonl", "hourly", "medium",
     "Every cell the gauntlet judged and where it died. Medium: spending the compute recomputes."),
    ("cost_surface_bar", "research/cost_surface.py", "derived", "data/cost_surface.json", "daily",
     "high", "Spread as a symbol x hour STATE from the venue's own stamped bar field."),
    ("cost_surface_tick", "recorders/tape_features.py (MT5-TapeFeatures)", "derived",
     "data/cost_surface_tick.json", "hourly", "high",
     "What a market order would ACTUALLY have crossed at seven latencies -- the live-tick "
     "confirmation research/cost_surface.py records that it is owed."),
    ("slippage_surface", "recorders/tape_features.py (MT5-TapeFeatures)", "derived",
     "data/tape/slippage_surface.json", "hourly", "high",
     "The latency-slippage curve from ticks not fills, so fill_surface has a day-one prior."),
    ("intrabar_bars", "recorders/tape_features.py (MT5-TapeFeatures)", "derived",
     "data/tape/intrabar/<SYM>/<FREQ>/<YYYY-MM-DD>.parquet", "hourly", "medium",
     "M1..D1 bars with the true path, excursions and the realised/bipower split."),
    ("triangle_executable", "mt5desk/triangle_tape.py", "derived",
     "data/tape/triangle_executable.json", "hourly", "medium",
     "Quoted, spread-inclusive FX loops at a measured quote skew. Evidence, not a signal."),
)


def registry() -> list[dict[str, Any]]:
    """Declarations only -- owner, path, cadence, class. Every number arrives by measurement."""
    rows = [dict(zip(_FIELDS, r, strict=True)) for r in _REGISTERED]
    rows += [dict(zip(_FIELDS, (n, "research/moat_series.py (this organ)", "derived",
                                f"data/moat/{n}/<SYM>.parquet", "hourly", "medium",
                                "Built here from the tick tape; medium because the moat is the "
                                "tape underneath, not the arithmetic on top."), strict=True))
             for n in DERIVED_SERIES]
    return rows


# ------------------------------------------------------------------------ reading the tape --

def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _day_key(stem: str) -> str | None:
    """`2026-09-15` and `20260915` are one day written by two writers. Normalise, or None."""
    s = stem.replace("-", "")
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()
    except ValueError:
        return None


def tape_index() -> dict[str, dict[str, Path]]:
    """{SYMBOL: {YYYY-MM-DD: path}} from one directory walk. Where both naming conventions hold
    the same day, the larger file wins -- it is the one with more ticks in it."""
    out: dict[str, dict[str, Path]] = {}
    for d in sorted(TICKS.iterdir()) if TICKS.is_dir() else []:
        if not d.is_dir():
            continue
        days: dict[str, Path] = {}
        for f in d.glob("*.parquet"):
            key = _day_key(f.stem)
            try:
                if key is None or (key in days and f.stat().st_size <= days[key].stat().st_size):
                    continue
            except OSError:
                continue
            days[key] = f
        if days:
            out[d.name] = days
    return out


def _read_day(path: Path) -> dict[str, np.ndarray] | None:
    """time_msc/bid/ask only, sorted, unusable quotes dropped and counted. Nothing depends on
    `ts`, which one tape writer derives and the other does not (mt5desk/tape.merge_day)."""
    try:
        df = pd.read_parquet(path, columns=["time_msc", "bid", "ask"])
    except Exception:  # a corrupt or foreign day file must never take the leg down
        return None
    num = {c: pd.to_numeric(df[c], errors="coerce").to_numpy(dtype="float64") for c in df.columns}
    ms, bid, ask = num["time_msc"], num["bid"], num["ask"]
    ok = np.isfinite(ms) & (bid > 0) & (ask > 0) & (ask >= bid)
    bad = int((~ok).sum())
    ms, bid, ask = ms[ok].astype("int64"), bid[ok], ask[ok]
    if ms.size < 2:
        return None
    order = np.argsort(ms, kind="stable")
    ms, bid, ask = ms[order], bid[order], ask[order]
    mid = (bid + ask) / 2.0
    return {"ms": ms, "mid": mid, "spread": ask - bid, "spread_bps": (ask - bid) / mid * 1e4,
            "hour": ((ms // 3_600_000) % 24).astype("int64"),
            "minute": (ms // 60_000).astype("int64"), "bad": np.array([bad], dtype="int64")}


def _masks(hour: np.ndarray) -> dict[str, np.ndarray]:
    """Sessions OVERLAP by the desk's own definition (london 8-16, ny 14-22); a tick inside both
    is counted in both, because that is what a cell certified in either session traded."""
    m = {"all": np.ones(hour.shape, dtype=bool)}
    for name, (lo, hi) in SESSIONS.items():
        m[name] = (hour >= lo) & (hour < hi)
    return m


def _med(x: np.ndarray) -> float:
    return float(np.median(x)) if x.size else float("nan")


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """(beta, intercept, r2) of y on x, NaNs when there is not enough of it to mean anything."""
    nan = float("nan")
    if x.size < MIN_REG_MINUTES:
        return nan, nan, nan
    dx, dy = x - x.mean(), y - y.mean()
    vx, vy, cxy = float(dx @ dx), float(dy @ dy), float(dx @ dy)
    if vx <= 0.0:
        return nan, nan, nan
    beta = cxy / vx
    return beta, float(y.mean() - beta * x.mean()), (0.0 if vy <= 0 else cxy * cxy / (vx * vy))


# -------------------------------------------------------------------------- derived series --

def derive_day(sym: str, day: str, path: Path) -> dict[str, dict[str, Any]] | None:
    """One instrument-day -> one row for each of the five derived series."""
    d = _read_day(path)
    if d is None:
        return None
    ms, mid, sp = d["ms"], d["mid"], d["spread_bps"]
    masks = _masks(d["hour"])
    stamp = {"date": day, "symbol": sym,
             "built_at": datetime.now(UTC).isoformat(timespec="seconds")}

    # ZERO-SPREAD ROWS ARE PUBLISHED, NOT FILTERED (measured 2026-09-17). 41,604 of EURUSD's
    # 42,460 tape rows for 2026-09-15 carry ask == bid, while XAUUSD's carry none: on some symbols
    # this tape records a one-sided update by repeating the other side. Dropping those rows would
    # silently discard 98% of a day and corrupt every count built from it; keeping them without
    # saying so would let a consumer read a 0.0 median as "free to cross". So the fraction is a
    # COLUMN, and a spread series is only usable where it is small.
    spread_row: dict[str, Any] = dict(stamp, spread_price_med_all=_med(d["spread"]),
                                      zero_spread_frac=float((d["spread"] == 0).mean()))
    for n, m in masks.items():
        spread_row[f"spread_bps_med_{n}"] = _med(sp[m])
        spread_row[f"spread_bps_mean_{n}"] = float(sp[m].mean()) if m.any() else float("nan")
        spread_row[f"spread_bps_p90_{n}"] = (float(np.quantile(sp[m], 0.90)) if m.any()
                                             else float("nan"))
        spread_row[f"n_{n}"] = int(m.sum())

    keys, inv = np.unique(d["minute"], return_inverse=True)
    per_min = np.bincount(inv, minlength=keys.size).astype("float64")
    gaps_s = np.diff(ms) / 1000.0
    intensity_row = dict(stamp, quotes=int(ms.size), active_minutes=int(keys.size),
                         quotes_per_min_mean=float(per_min.mean()),
                         quotes_per_min_med=_med(per_min),
                         quotes_per_min_p95=float(np.quantile(per_min, 0.95)),
                         burstiness=(float(per_min.std() / per_min.mean()) if per_min.mean()
                                     else float("nan")),
                         max_gap_s=float(gaps_s.max()), med_gap_s=_med(gaps_s))

    # UPTICKS MINUS DOWNTICKS per minute. sign() of the mid change is the only order-flow signal a
    # venue with no depth supports -- probe_depth says this one has none, and a book-based OFI here
    # would be a model of the synthesis (mt5desk/tape.py:probe_depth).
    dirn = np.sign(np.diff(mid))
    ofi_min = np.bincount(inv[1:], weights=dirn, minlength=keys.size)
    ofi_row = dict(stamp, ofi_sum=float(dirn.sum()), ofi_mean_per_min=float(ofi_min.mean()),
                   ofi_abs_mean_per_min=float(np.abs(ofi_min).mean()),
                   ofi_frac_min_positive=float((ofi_min > 0).mean()),
                   upticks=int((dirn > 0).sum()), downticks=int((dirn < 0).sum()),
                   **{f"ofi_sum_{n}": float(dirn[m[1:]].sum())
                      for n, m in masks.items() if n != "all"})

    # THE SPREAD'S RESPONSE TO VOLATILITY, per day. Minutes holding a single quote carry no
    # variation and are EXCLUDED rather than entered as a zero that would flatten the slope.
    vol_min = np.bincount(inv[1:], weights=np.abs(np.diff(np.log(mid))) * 1e4, minlength=keys.size)
    sp_min = np.bincount(inv, weights=sp, minlength=keys.size) / np.maximum(per_min, 1.0)
    usable = per_min >= 2
    beta, alpha, r2 = _ols(vol_min[usable], sp_min[usable])
    beta_row = dict(stamp, beta=beta, intercept=alpha, r2=r2, n_minutes=int(usable.sum()),
                    vol_bps_med=_med(vol_min[usable]), spread_bps_med=_med(sp_min[usable]))

    count_row = dict(stamp, quotes=int(ms.size), distinct_minutes=int(keys.size),
                     distinct_hours=int(np.unique(d["hour"]).size), bad_quotes=int(d["bad"][0]),
                     first_ts=str(pd.Timestamp(int(ms[0]), unit="ms", tz="UTC")),
                     last_ts=str(pd.Timestamp(int(ms[-1]), unit="ms", tz="UTC")),
                     **{f"quotes_{n}": int(m.sum()) for n, m in masks.items() if n != "all"})

    return {"realised_spread_session": spread_row, "quote_intensity": intensity_row,
            "ofi_proxy": ofi_row, "spread_vol_beta": beta_row, "daily_quote_count": count_row}


# ------------------------------------------------------------------------------- the store --

def store_path(series: str, symbol: str) -> Path:
    return STORE / series / f"{symbol}.parquet"


def series_frame(series: str, symbol: str) -> pd.DataFrame:
    """The reader every consumer imports: sorted by `date`, with `ts` added as a UTC timestamp.

    AN EMPTY FRAME MEANS UNMEASURED, NEVER ZERO. A caller treating `.empty` as "no edge here" is
    reading an absent file as evidence; check it and defer.
    """
    path, empty = store_path(series, symbol), pd.DataFrame(columns=["date", "symbol", "ts"])
    if not path.exists():
        return empty
    try:
        df = pd.read_parquet(path)
    except Exception:
        return empty
    if df.empty or "date" not in df.columns:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    df["ts"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    return df


def _replace(tmp: Path, path: Path) -> None:
    """`os.replace` onto a read-only destination is legal on POSIX and WinError 5 here -- the way
    a VPS-tested fix once broke the box that trades."""
    try:
        os.replace(tmp, path)
        return
    except PermissionError:
        try:
            os.chmod(path, 0o666)
            os.replace(tmp, path)
            return
        except OSError:
            pass
    except OSError:
        pass
    path.write_bytes(tmp.read_bytes())
    tmp.unlink(missing_ok=True)


def append_rows(series: str, symbol: str, rows: list[dict[str, Any]]) -> int:
    """Append and deduplicate on `date`, the newest write winning. Returns rows on disk."""
    if not rows:
        return 0
    path, frame = store_path(series, symbol), pd.DataFrame(rows)
    if path.exists():
        try:
            prev = pd.read_parquet(path)
        except Exception:
            prev = pd.DataFrame()
        if not prev.empty:
            frame = pd.concat([prev, frame], ignore_index=True)
    frame = frame.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    frame = frame.reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    frame.to_parquet(tmp, index=False, compression="zstd")
    _replace(tmp, path)
    return len(frame)


def _dates_in(path: Path) -> set[str]:
    try:
        return {str(v) for v in pd.read_parquet(path, columns=["date"])["date"]} if path.exists() \
            else set()
    except Exception:
        return set()


def build(index: dict[str, dict[str, Path]], *, max_days: int, deadline: float,
          rebuild: bool = False, symbols: list[str] | None = None) -> dict[str, Any]:
    """Derive the last `max_days` tape days per instrument, least-covered instrument first, until
    the clock says stop. A run that cannot reach the whole universe still advances its thinnest
    corner every hour, and the store keeps what earlier runs already paid for."""
    wanted = set(symbols or [])
    todo = [s for s in index if not wanted or s in wanted]
    built = dict.fromkeys(DERIVED_SERIES, 0)
    held = {s: {k: _dates_in(store_path(k, s)) for k in DERIVED_SERIES} for s in todo}
    todo.sort(key=lambda s: (min((len(v) for v in held[s].values()), default=0), s))
    stopped, touched = False, 0
    for sym in todo:
        if time.monotonic() >= deadline:
            stopped = True
            break
        days = sorted(index[sym])[-max_days:] if max_days > 0 else sorted(index[sym])
        pending = [d for d in days
                   if rebuild or any(d not in held[sym][s] for s in DERIVED_SERIES)]
        if not pending:
            continue
        rows: dict[str, list[dict[str, Any]]] = {s: [] for s in DERIVED_SERIES}
        for day in pending:
            if time.monotonic() >= deadline:
                stopped = True
                break
            out = derive_day(sym, day, index[sym][day])
            for s, row in (out or {}).items():
                rows[s].append(row)
        for s, batch in rows.items():
            if batch:
                append_rows(s, sym, batch)
                built[s] += len(batch)
        touched += 1
        if stopped:
            break
    return {"built": built, "budget_stopped": stopped, "instruments_touched": touched}


# ------------------------------------------------------------------------- the measurement --

def _universe() -> list[str]:
    uni = _load_json(UNIVERSE)
    return sorted(uni) if isinstance(uni, dict | list) else []


def _gaps(universe: list[str], last_seen: dict[str, str],
          why: str) -> tuple[list[dict[str, Any]], int]:
    cut = (datetime.now(UTC) - timedelta(days=GAP_WINDOW_DAYS)).date().isoformat()
    rows = [{"instrument": s, "last": last_seen.get(s.upper()), "why": why}
            for s in universe if last_seen.get(s.upper(), "") < cut]
    return rows[:GAP_CAP], len(rows)


def _count_rows(paths: list[Path], deadline: float) -> tuple[int | None, str]:
    import pyarrow.parquet as pq
    rows, seen = 0, 0
    for p in paths:
        if time.monotonic() >= deadline:
            break
        try:
            rows += int(pq.read_metadata(p).num_rows)
        except Exception:
            continue
        seen += 1
    if not seen:
        return None, "no parquet footer could be read"
    return rows, (f"{seen} parquet footers" if seen == len(paths) else
                  f"PARTIAL: {seen} of {len(paths)} parquet footers read before the stopwatch")


def _measure_tick_tape(index: dict[str, dict[str, Path]], universe: list[str]) -> dict[str, Any]:
    if not index:
        return {"unmeasured": f"no tape at {TICKS}"}
    days = sorted({d for v in index.values() for d in v})
    gaps, n = _gaps(universe, {s.upper(): max(v) for s, v in index.items()},
                    f"no tape day in the last {GAP_WINDOW_DAYS} days")
    files = [p for v in index.values() for p in v.values()]
    rows, basis = _count_rows(files, time.monotonic() + FOOTER_BUDGET_S)
    # The 7-day instrument coverage is the EXISTING organ's number, never a second one.
    cov = _load_json(MOAT_COVERAGE)
    cov_map = cov.get("coverage") if isinstance(cov, dict) else None
    return {"first": days[0], "last": days[-1], "days": len(days), "instruments": len(index),
            "rows": rows, "rows_basis": basis, "files": len(files), "gaps": gaps, "n_gaps": n,
            "coverage_source": (f"data/moat_coverage.json: {len(cov_map)} instruments, "
                                f"newest_tape_write={cov.get('newest_tape_write')}"
                                if isinstance(cov_map, dict) else "data/moat_coverage.json absent")}


def _measure_day_parquet_dir(root: Path) -> dict[str, Any]:
    files = {k: p for p in (root.glob("*.parquet") if root.is_dir() else [])
             if (k := _day_key(p.stem)) is not None}
    if not files:
        return {"unmeasured": f"{root} absent or holds no dated parquet"}
    days = sorted(files)
    rows, basis = _count_rows(list(files.values()), time.monotonic() + FOOTER_BUDGET_S)
    try:
        instruments: int | None = int(
            pd.read_parquet(files[days[-1]], columns=["symbol"])["symbol"].nunique())
    except Exception:
        instruments = None
    return {"first": days[0], "last": days[-1], "days": len(days), "instruments": instruments,
            "rows": rows, "rows_basis": basis}


def _measure_jsonl(path: Path, time_key: str, sym_key: str) -> dict[str, Any]:
    if not path.exists():
        return {"unmeasured": f"{path} absent"}
    stamps, syms, rows = set(), set(), 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rows += 1
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec.get(time_key), str) and len(rec[time_key]) >= 10:
                    stamps.add(rec[time_key][:10])
                if rec.get(sym_key):
                    syms.add(str(rec[sym_key]))
    except OSError as exc:
        return {"unmeasured": f"{path}: {type(exc).__name__}"}
    days = sorted(stamps)
    if not rows:
        return {"unmeasured": f"{path} is empty"}
    return {"first": days[0] if days else None, "last": days[-1] if days else None,
            "days": len(days), "instruments": len(syms) or None, "rows": rows,
            "rows_basis": "jsonl lines"}


def _measure_cost_surface(path: Path) -> dict[str, Any]:
    doc = _load_json(path)
    syms = doc.get("symbols") if isinstance(doc, dict) else None
    if not isinstance(syms, dict) or not syms:
        return {"unmeasured": f"{path} absent or carries no symbols block"}
    vals = [v for v in syms.values() if isinstance(v, dict)]
    depths = [int(v["days_total"]) for v in vals if isinstance(v.get("days_total"), int)]
    firsts = sorted(str(v["first"])[:10] for v in vals if v.get("first"))
    # THE MEDIAN, not the best symbol: depth the book actually has, not depth one instrument has.
    days = int(np.median(depths)) if depths else None
    return {"first": firsts[0] if firsts else None,
            "last": str(doc.get("built_at") or "")[:10] or None, "days": days,
            "instruments": len(syms), "rows": sum(len(v.get("hours") or {}) for v in vals),
            "rows_basis": "symbol x hour cells",
            "unmeasured": None if days else "no symbol publishes days_total"}


def _measure_json_rows(path: Path, key: str, at_key: str = "at") -> dict[str, Any]:
    doc = _load_json(path)
    rows = doc.get(key) if isinstance(doc, dict) else None
    if not isinstance(rows, list | dict) or not rows:
        return {"unmeasured": f"{path} absent or carries no '{key}'"}
    at = str(doc.get(at_key) or "")[:10] or None
    return {"first": at, "last": at, "days": 1 if at else None, "instruments": len(rows),
            "rows": len(rows), "rows_basis": f"'{key}' entries",
            "unmeasured": None if at else "the artifact carries no timestamp, so it has no depth"}


def _measure_intrabar(root: Path) -> dict[str, Any]:
    dirs = [d for d in (root.iterdir() if root.is_dir() else []) if d.is_dir()]
    days = {k for d in dirs for p in d.rglob("*.parquet") if (k := _day_key(p.stem)) is not None}
    if not days:
        return {"unmeasured": f"{root} absent or empty -- MT5-TapeFeatures has not run here"}
    o = sorted(days)
    return {"first": o[0], "last": o[-1], "days": len(o), "instruments": len(dirs), "rows": None,
            "rows_basis": "row count not scanned (one tree per frequency)"}


def _measure_store(series: str, universe: list[str]) -> dict[str, Any]:
    root = STORE / series
    days: set[str] = set()
    last_seen: dict[str, str] = {}
    rows = 0
    for p in sorted(root.glob("*.parquet")) if root.is_dir() else []:
        got = _dates_in(p)
        if got:
            days |= got
            rows += len(got)
            last_seen[p.stem.upper()] = max(got)
    if not days:
        return {"unmeasured": f"{root} absent or holds no dated rows -- nothing derived yet"}
    o = sorted(days)
    gaps, n = _gaps(universe, last_seen, f"no derived row in the last {GAP_WINDOW_DAYS} days")
    return {"first": o[0], "last": o[-1], "days": len(o), "instruments": len(last_seen),
            "rows": rows, "rows_basis": "instrument-days in the store", "gaps": gaps, "n_gaps": n}


def measure(index: dict[str, dict[str, Path]], universe: list[str]) -> list[dict[str, Any]]:
    """Every registered series, measured against the artifacts on THIS box."""
    how = {"tick_tape": lambda: _measure_tick_tape(index, universe),
           "financing_tape": lambda: _measure_day_parquet_dir(TERMS),
           "live_fill_ledger": lambda: _measure_jsonl(LIVE_LEDGER, "time", "symbol"),
           "gate_verdict_ledger": lambda: _measure_jsonl(VERDICT_LEDGER, "at", "sym"),
           "cost_surface_bar": lambda: _measure_cost_surface(COST_SURFACE),
           "cost_surface_tick": lambda: _measure_cost_surface(COST_SURFACE_TICK),
           "slippage_surface": lambda: _measure_json_rows(SLIPPAGE_SURFACE, "symbols", "built_at"),
           "intrabar_bars": lambda: _measure_intrabar(INTRABAR),
           "triangle_executable": lambda: _measure_json_rows(TRIANGLE, "rows")}
    out = []
    for row in registry():
        fn = how.get(row["name"])
        got = fn() if fn else _measure_store(row["name"], universe)
        row.update({k: v for k, v in got.items() if k != "unmeasured"})
        row.setdefault("gaps", [])
        row.setdefault("n_gaps", 0)
        for k in ("first", "last", "days", "instruments", "rows"):
            row.setdefault(k, None)
        weight = MOAT_CLASS[row["moat_class"]]
        row["moat_weight_per_day"] = weight
        row["moat_score"] = (round(weight * row["days"], 2)
                             if isinstance(row["days"], int) and row["days"] > 0 else None)
        row["unmeasured"] = got.get("unmeasured") or (
            None if row["moat_score"] is not None else "no measurable depth in days")
        out.append(row)
    return out


# ------------------------------------------------------------------------------------ the leg --

def run(*, budget_s: float = 240.0, max_days: int = 3, dry_run: bool = False,
        rebuild: bool = False, symbols: list[str] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    universe, index = _universe(), tape_index()
    built = ({"built": dict.fromkeys(DERIVED_SERIES, 0), "budget_stopped": budget_s <= 0,
              "instruments_touched": 0} if dry_run else
             build(index, max_days=max_days, deadline=t0 + budget_s, rebuild=rebuild,
                   symbols=symbols))
    rows = measure(index, universe)
    scored = [r["moat_score"] for r in rows if r["moat_score"] is not None]
    return {"at": datetime.now(UTC).isoformat(timespec="seconds"), "n_series": len(rows),
            "series": rows, "built_this_run": built["built"],
            "instruments_touched": built["instruments_touched"],
            "total_moat_score": round(sum(scored), 2),
            "unmeasured": [{"series": r["name"], "why": r["unmeasured"]}
                           for r in rows if r["unmeasured"]],
            "universe": len(universe), "budget_s": budget_s,
            "budget_stopped": built["budget_stopped"], "max_days": max_days, "dry_run": dry_run,
            "elapsed_s": round(time.monotonic() - t0, 2), "rule": RULE}


def write_report(report: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    _replace(tmp, out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Register, measure and build the desk's moat series")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--max-days", type=int, default=3)
    ap.add_argument("--symbols", type=str, default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    rep = run(budget_s=args.budget_s, max_days=args.max_days, dry_run=args.dry_run,
              rebuild=args.rebuild,
              symbols=[s.strip() for s in args.symbols.split(",") if s.strip()] or None)
    for r in rep["series"]:
        score = "UNMEASURED" if r["moat_score"] is None else f"{r['moat_score']:>9.1f}"
        print(f"  {r['name']:<24}{r['kind']:<9}{r['moat_class']:<8}days={r['days']!s:>6} "
              f"inst={r['instruments']!s:>5} rows={r['rows']!s:>10} score={score} "
              f"gaps={r['n_gaps']}")
    print(f"\n{rep['n_series']} series, total moat score {rep['total_moat_score']}, "
          f"{len(rep['unmeasured'])} unmeasured, built this run "
          f"{sum(rep['built_this_run'].values())} instrument-days in {rep['elapsed_s']}s"
          + (" (BUDGET STOPPED)" if rep["budget_stopped"] else ""))
    if args.dry_run:
        print("--dry-run: nothing derived, nothing written")
        return 0
    write_report(rep, args.out or REPORT)
    print(f"  -> {args.out or REPORT}\nYIELD series={rep['n_series']} "
          f"built={sum(rep['built_this_run'].values())} moat_score={rep['total_moat_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
