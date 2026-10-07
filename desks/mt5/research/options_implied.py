"""OPTIONS-IMPLIED FEATURES AND CELLS -- the options market's state, on the underlyings this
account can trade, point-in-time, and handed to the one gauntlet.

WHAT WAS MISSING (completion audit 2026-10-06, repair rank 2). `recorders/vol_archive.py` has
archived CBOE implied vol for the desk's own underlyings hourly since 2026-09-05, and nothing
read it: no feature reached `representation_forge`, no cell reached the docket, and the
`options_implied` alpha cluster stayed empty while `empty_cluster_forcer` called it unreachable
by venue. This organ is the missing consumer. Per mapped MT5 symbol it publishes:

    iv_level          the CBOE index close (percent, the index's own units)
    iv_pct_1y         its percentile within its own trailing 252 observations (min 126)
    iv_chg_1d/5d      change over 1 and 5 observations, in vol points
    iv_chg_5d_z       the 5-observation change z-scored on its own trailing year
    slope_9d_30d      VIX 9D->30D slope, vol points per log-tenor   (US500 only; each slope is a
    slope_30d_3m      VIX 30D->3M slope                              NAMED pair -- a missing
    slope_3m_6m       VIX 3M->6M slope                               tenor leaves it UNMEASURED)
    term_inverted     1 when VIX 30D > VIX 3M on the same as-of date, else 0
    rv_21d            THIS BROKER's 21-day close-to-close realised vol from its own H1 bars
    vrp               iv_level - rv_21d: the variance risk premium this account faces
    vrp_pct_1y        vrp's percentile within its own trailing year

and does three things with them, all on the box's hourly clock:

  1. WRITES `data/lake/series/oi_<SYMBOL>.parquet` in the lake's PIT envelope -- the series the
     `implied_vol_state` / `implied_vol_conditioned` families (mt5desk/family_implied_vol.py)
     load when the sealed gauntlet, the forward clock or the gateway rebuilds a cell.
  2. FEEDS THE REPRESENTATION FACTORY: `data/lake/axes/options_implied.json`, an axis file
     `world_model.load_inputs` reads beside `data/axes/`, so `representation_forge` mints
     z/rank/surprise/interaction representations of IV and VRP and the world model credits them.
  3. MINTS options-implied cells -- DIRECT (enter when the implied state begins) and INDIRECT (a
     price-only base family kept only inside the state) -- on every mapped instrument the
     two-lane order hunts, and donates each identity ONCE through `proposer_common.donate`, which
     stamps, lane-filters, pre-registers and charges `tests_run` to the experiment ledger. Every
     family it mints under classifies into `options_implied` (libs/research/alpha_clusters).

POINT-IN-TIME, STATED ONCE. A CBOE index close for US date D is published after 16:15 ET (20:15
or 21:15 UTC). It is stamped knowable at D+1 00:00 UTC (`libs/data/pit_stamp.available_at` with
the daily lag) plus `world_model.CLOCK_PAD_H` -- D+1 04:00 UTC, about seven hours after the
print. Realised vol for D uses this broker's bars up to broker-date D, which closes at 21:00 or
22:00 UTC on D. The families then hold the stamp back a further `MAX_BROKER_OFFSET_H` before
aligning it to a broker-labelled bar. Every expanding or rolling statistic uses only values at or
before its own date. `tests/research/test_options_implied.py` corrupts the future and checks.

HISTORY, LABELLED HONESTLY. The desk's own vintages (what each index READ when vol_archive looked)
start 2026-09-05 and override the public series on every date they cover; behind them sits the
public, restated CBOE reference history as FRED republishes it. Research cells may be
judged on that reference history; each row's `vintage` column says which one it is, and the
report keeps vol_archive's own `backtestable` line -- false until MIN_VINTAGES desk observations
exist. NOTHING HERE PROMOTES, SIZES OR CONDITIONS CAPITAL. The gauntlet decides.

SOURCES: HELD AS OF 2026-10-06. History comes only through `vol_archive.FredVolSource`, which
sends no request while `vol_archive.TERMS_EVIDENCE` holds FRED (and CBOE, and refuses Yahoo):
the terms read that day contain no clause clearly permitting this use. A source that is not
admitted is never asked; a reference cache is used only if it was written by an admitted source;
a desk vintage counts only if its row was served by an admitted route. So until a permitting
clause is quoted there, every symbol is UNMEASURED and nothing is minted. Every series row, the
reference cache, the forge feed and the report carry `terms_note`.

    python desks/mt5/research/options_implied.py --once [--offline] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import UTC, date, datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders import vol_archive as va  # noqa: E402

from libs.data.pit_stamp import DEFAULT_LAG_DAYS, available_at  # noqa: E402

SEAT = "options_implied"
UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE_JSON = UNIVERSE_DIR / "universe.json"
SERIES_DIR = DESK / "data" / "lake" / "series"
STATE_DIR = DESK / "data" / "lake" / "options_implied"
REFERENCE_DIR = STATE_DIR / "reference"
DONATED = STATE_DIR / "donated.json"
FORGE_FEED = DESK / "data" / "lake" / "axes" / "options_implied.json"
REPORT = DESK / "reports" / "OPTIONS_IMPLIED.json"

#: `world_model.CLOCK_PAD_H`, restated rather than imported so this organ does not load the
#: world model's whole module to read one integer; `test_options_implied` pins the two equal.
CLOCK_PAD_H = 4
#: Trailing observations a percentile or z is measured over, and the fewest it needs.
YEAR = 252
MIN_YEAR = 126
#: Reference history older than this is refetched; a failed fetch falls back to the cache.
REFERENCE_MAX_AGE_H = 6.0
#: Points per series handed to the representation factory. The world model keeps at most 4,000;
#: four years is enough for the forge's 260-observation windows and keeps the feed small.
FORGE_POINTS = 1040
#: The features the forge is fed. The forge mints z, rank, diff and interactions itself, so the
#: derived columns above would only be the forge's own transforms computed twice.
FORGE_FEATURES: tuple[str, ...] = ("iv_level", "vrp", "slope_9d_30d", "slope_30d_3m")

#: (label, feature, op, threshold) -- the implied STATES a cell conditions on. Fixed and declared,
#: so the grid is the same every hour and the multiplicity charge is the grid's real width.
CONDITIONS: tuple[tuple[str, str, str, float], ...] = (
    ("iv_high", "iv_pct_1y", "ge", 0.8),
    ("iv_low", "iv_pct_1y", "le", 0.2),
    ("iv_spike", "iv_chg_5d_z", "ge", 1.5),
    ("iv_crush", "iv_chg_5d_z", "le", -1.5),
    ("vrp_rich", "vrp", "gt", 0.0),
    ("vrp_cheap", "vrp", "lt", 0.0),
    ("term_inverted", "term_inverted", "ge", 1.0),
)
#: DIRECT arm: chart -> the holds (in that chart's bars) a state-onset entry is tested at.
DIRECT_HOLDS: dict[str, tuple[int, ...]] = {"H1": (24, 120), "H4": (6, 30)}
DIRECTIONS: tuple[int, ...] = (1, -1)
#: INDIRECT arm: price-only base families at their registered defaults, on H1. The same six
#: `free_stack_proposer` conditions, so an implied-state gate and an alt-series gate on the same
#: base are directly comparable in the docket.
BASES: tuple[str, ...] = ("session_range_breakout", "trend_ma_cross", "mean_reversion_rsi",
                          "momentum_volgate", "overnight_drift", "volatility_squeeze")

#: Why each condition's payer pays. Carried onto every cell as its mechanism.
PAYER: dict[str, str] = {
    "iv_high": "implied vol in the top of its year: dealers short gamma hedge INTO moves and "
               "realised follows implied up, or the premium is rich and sold",
    "iv_low": "implied vol in the bottom of its year: dealers long gamma pin the underlying and "
              "breakouts are faded until the compression ends",
    "iv_spike": "a five-day implied-vol spike: a hedging rush whose unwind is the forced flow",
    "iv_crush": "a five-day implied-vol crush: protection sold off, hedges unwound into the "
                "underlying",
    "vrp_rich": "implied above THIS broker's realised: option sellers are paid to carry risk, "
                "the underlying drifts in the direction their hedges lean",
    "vrp_cheap": "implied below THIS broker's realised: hedgers are under-protected for the "
                 "move the bars already show",
    "term_inverted": "the VIX curve inverted (30D above 3M): near-dated stress priced above "
                     "the medium term, the crisis-state hedge demand",
}


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        # `os.replace` onto a read-only destination is legal on POSIX and WinError 5 on the box.
        path.chmod(0o644)
        os.replace(tmp, path)


# ----------------------------------------------------------------------------- the clock
def knowable_at(value_date: str) -> tuple[str, str]:
    """(published_time, available_time) for a CBOE close dated `value_date`, both UTC.

    Published is bounded at D+1 00:00 UTC by the daily lag (the print lands 20:15-21:15 UTC on
    D); available adds the world model's clock pad on top, so a feature is never usable before
    D+1 04:00 UTC.
    """
    d = date.fromisoformat(value_date[:10])
    pub = available_at(d, DEFAULT_LAG_DAYS["daily"])
    return pub.isoformat(), (pub + timedelta(hours=CLOCK_PAD_H)).isoformat()


# ----------------------------------------------------------------------------- the inputs
def grounds(registry: dict[str, Any]) -> list[tuple[va.Ground, str]]:
    """(ground, mapped MT5 symbol) for every vol series whose underlying this account lists."""
    out: list[tuple[va.Ground, str]] = []
    for g in va.GROUND:
        sym = va.resolve_symbol(g.mt5_candidates, registry)
        if sym:
            out.append((g, sym))
    return out


def tickers_for(g: va.Ground) -> tuple[str, ...]:
    return tuple(dict.fromkeys((g.vol_ticker, *g.term)))


def _safe(ticker: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in ticker).strip("_")


def reference_history(ticker: str, source: va.VolSource | None, *, cache_dir: Path | None = None,
                      max_age_h: float = REFERENCE_MAX_AGE_H, now: datetime | None = None
                      ) -> tuple[dict[str, float], dict[str, Any]]:
    """The public CBOE history for `ticker`: a fresh cache, else a fetch, else a stale cache.

    Returns (series, provenance). An empty series is UNMEASURED and the provenance says why --
    an unreachable source and an index with no history are different facts.
    """
    now = now or datetime.now(tz=UTC)
    path = (cache_dir or REFERENCE_DIR) / f"{_safe(ticker)}.json"
    cached = _read(path, {})
    # A CACHE COUNTS ONLY IF AN ADMITTED SOURCE WROTE IT. A file fetched under a route the terms
    # now hold (or written before the terms were read) is never served as reference history.
    if cached.get("admitted") is not True:
        cached = {}
    series = {str(k): float(v) for k, v in (cached.get("series") or {}).items()
              if isinstance(v, (int, float)) and math.isfinite(float(v))}
    fetched_at = str(cached.get("fetched_at") or "")
    age_h = None
    if fetched_at:
        try:
            age_h = (now - datetime.fromisoformat(fetched_at)).total_seconds() / 3600.0
        except ValueError:
            age_h = None
    if series and age_h is not None and age_h <= max_age_h:
        return series, {"status": "CACHE_FRESH", "fetched_at": fetched_at, "n": len(series)}
    got = None
    admitted = bool(getattr(source, "admitted", False))
    if source is not None and admitted:
        try:
            got = source.series(ticker)
        except Exception:
            got = None
    if got:
        series = {str(k)[:10]: float(v) for k, v in got.items()
                  if v is not None and math.isfinite(float(v))}
        stamp = now.isoformat(timespec="seconds")
        _atomic(path, json.dumps({"ticker": ticker, "fetched_at": stamp, "series": series,
                                  "terms_note": va.TERMS_NOTE, "admitted": True,
                                  "source": type(source).__name__,
                                  "what": "public CBOE close history -- REFERENCE, restated "
                                          "by the source, never the desk's own vintage"}))
        return series, {"status": "FETCHED", "fetched_at": stamp, "n": len(series),
                        "terms_note": va.TERMS_NOTE}
    if series:
        return series, {"status": "CACHE_STALE", "fetched_at": fetched_at, "n": len(series),
                        "why": "source did not answer this pass; the last fetch is used"}
    if source is not None and not admitted:
        return {}, {"status": "HELD_PENDING_TERMS", "n": 0, "requested": False,
                    "why": (f"{type(source).__name__} is not admitted by vol_archive."
                            f"TERMS_EVIDENCE; no request sent and no unadmitted cache used")}
    return {}, {"status": "UNMEASURED", "n": 0,
                "why": ("no cache and the source did not answer (offline, or no egress from this "
                        "host)"),
                "measured_by": "a pass on a host that can reach the CBOE history source"}


def desk_vintages(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """{ticker: {value_date: value}} -- what each index READ when vol_archive observed it.

    The newest observation of a date wins: the archive is append-only, and a later row for the
    same value date is the source restating itself, which is what the desk would have seen then.
    """
    out: dict[str, dict[str, float]] = {}
    for r in sorted(rows, key=lambda x: str(x.get("observed_at") or "")):
        vdate = str(r.get("value_date") or "")[:10]
        # ONLY ROWS AN ADMITTED ROUTE SERVED. Rows before the route stamp (2026-10-06) came
        # through a source now refused by its terms and are not served as vintages.
        if not vdate or r.get("source_admitted") is not True:
            continue
        iv = r.get("implied_vol")
        if isinstance(iv, (int, float)) and math.isfinite(float(iv)):
            out.setdefault(str(r.get("vol_ticker")), {})[vdate] = float(iv)
        for t, v in (r.get("term") or {}).items():
            if isinstance(v, (int, float)) and math.isfinite(float(v)):
                out.setdefault(str(t), {})[vdate] = float(v)
    return out


def realised_daily(symbol: str, universe_dir: Path | None = None,
                   window_d: int = va.RV_WINDOW_D) -> pd.Series | None:
    """THIS broker's annualised close-to-close realised vol in PERCENT, per broker date.

    Each date's value uses that date's close and the `window_d` before it -- nothing later.
    Percent, to match the CBOE indices' own units (vol_archive.realised_vol's rule).
    """
    path = (universe_dir or UNIVERSE_DIR) / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path, columns=["close"])
    except (OSError, ValueError, KeyError):
        return None
    if df.empty:
        return None
    idx = pd.DatetimeIndex(df.index)
    close = df["close"].astype(float).groupby(idx.date).last()
    close = close[close > 0]
    if len(close) < window_d + 1:
        return None
    ret = np.log(close).diff()
    rv = ret.rolling(window_d, min_periods=max(5, (2 * window_d) // 3)).std(ddof=1)
    rv = (rv * va.ANNUALISE * 100.0).dropna()
    rv.index = [d.isoformat() for d in rv.index]
    return rv


def trailing_percentile(s: pd.Series, window: int = YEAR, min_obs: int = MIN_YEAR) -> pd.Series:
    """Share of the trailing `window` values (this one included) at or below this one."""
    v = s.to_numpy(dtype=float)
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        if not math.isfinite(v[i]):
            continue
        lo = max(0, i - window + 1)
        w = v[lo:i + 1]
        w = w[np.isfinite(w)]
        if len(w) >= min_obs:
            out[i] = float(np.mean(w <= v[i]))
    return pd.Series(out, index=s.index)


def trailing_z(s: pd.Series, window: int = YEAR, min_obs: int = MIN_YEAR) -> pd.Series:
    mu = s.rolling(window, min_periods=min_obs).mean()
    sd = s.rolling(window, min_periods=min_obs).std(ddof=0)
    return ((s - mu) / sd.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)


def build_features(iv: dict[str, float], *, term: dict[str, dict[str, float]] | None = None,
                   rv: pd.Series | None = None, desk_dates: set[str] | None = None,
                   ticker: str = "", symbol: str = "") -> pd.DataFrame:
    """One row per IV value date, every column computed from that date and earlier only."""
    if not iv:
        return pd.DataFrame()
    dates = sorted(iv)
    s = pd.Series([iv[d] for d in dates], index=dates, dtype=float)
    f = pd.DataFrame(index=dates)
    f["iv_level"] = s
    f["iv_pct_1y"] = trailing_percentile(s)
    f["iv_chg_1d"] = s.diff(1)
    f["iv_chg_5d"] = s.diff(5)
    f["iv_chg_5d_z"] = trailing_z(f["iv_chg_5d"])
    slopes: dict[str, list[float]] = {name: [] for name, _a, _b in va.TERM_PAIRS}
    inverted: list[float] = []
    for d in dates:
        curve = {t: vals[d] for t, vals in (term or {}).items() if d in vals}
        named, _missing = va.term_slopes(curve)
        for name, v in named.items():
            slopes[name].append(float(v) if v is not None else np.nan)
        thirty, three_m = curve.get("^VIX"), curve.get("^VIX3M")
        inverted.append(float(thirty > three_m) if thirty is not None and three_m is not None
                        else np.nan)
    for name, vals in slopes.items():
        f[name] = vals
    f["term_inverted"] = inverted
    if rv is not None and len(rv):
        f["rv_21d"] = pd.Series(rv).reindex(dates)
    else:
        f["rv_21d"] = np.nan
    f["vrp"] = f["iv_level"] - f["rv_21d"]
    f["vrp_pct_1y"] = trailing_percentile(f["vrp"])
    stamps = [knowable_at(d) for d in dates]
    f["value_date"] = dates
    f["event_time"] = [f"{d}T00:00:00+00:00" for d in dates]
    f["published_time"] = [p for p, _a in stamps]
    f["available_time"] = [a for _p, a in stamps]
    desk = desk_dates or set()
    f["vintage"] = ["desk" if d in desk else "reference" for d in dates]
    f["source_id"] = f"cboe:{ticker}" if ticker else "cboe"
    f["terms_note"] = va.TERMS_NOTE
    f["symbol"] = symbol
    return f.reset_index(drop=True)


def write_series(symbol: str, frame: pd.DataFrame, series_dir: Path | None = None) -> Path:
    series_dir = series_dir or SERIES_DIR
    series_dir.mkdir(parents=True, exist_ok=True)
    path = series_dir / f"oi_{symbol}.parquet"
    tmp = path.with_suffix(".parquet.tmp")
    frame.to_parquet(tmp, index=False)
    try:
        os.replace(tmp, path)
    except PermissionError:
        path.chmod(0o644)
        os.replace(tmp, path)
    return path


def forge_feed(frames: dict[str, pd.DataFrame], path: Path | None = None) -> dict[str, Any]:
    """An axis file in the `series[name].points` shape `world_model.load_inputs` reads.

    `available_time` here is the PUBLICATION bound (D+1 00:00 UTC): the world model adds its own
    CLOCK_PAD_H to every axis point, so the forge sees the same instant the families do.
    """
    series: dict[str, Any] = {}
    for sym, f in sorted(frames.items()):
        for col in FORGE_FEATURES:
            if col not in f.columns:
                continue
            sub = f[["published_time", "value_date", col]].dropna().tail(FORGE_POINTS)
            if len(sub) < 24:
                continue
            series[f"{sym}.{col}"] = {
                "what": f"{col} for {sym} (options-implied state, research/options_implied.py)",
                "points": [{"available_time": str(r.published_time), "d": str(r.value_date),
                            "v": round(float(getattr(r, col)), 6)}
                           for r in sub.itertuples(index=False)]}
    doc = {"id": "options_implied", "axis": "options_implied", "at": now_iso(),
           "source": "research/options_implied.py over recorders/vol_archive.py",
           "shape": "series[name].points of available_time (publication bound), d, v",
           "terms_note": va.TERMS_NOTE,
           "series": series}
    out = path or FORGE_FEED
    _atomic(out, json.dumps(doc, separators=(",", ":")))
    return {"path": str(out), "series": len(series)}


# ----------------------------------------------------------------------------- the cells
def _cell(symbol: str, chart: str, family: str, params: dict[str, Any], cond: str, arm: str,
          *, desk_n: int) -> dict[str, Any]:
    from proposer_common import candidate
    mech = f"options-implied state {cond} on {symbol}: {PAYER[cond]}"
    c = candidate(SEAT, symbol, family, {**params, "timeframe": chart}, mech,
                  f"{family} {cond} -> {symbol} {chart} [{arm}]",
                  {"arm": arm, "condition": cond, "series": params["source"],
                   "history": ("public CBOE reference history (restated) overlaid by the desk's "
                               "own vol_archive vintages on every date they cover"),
                   "desk_vintages": desk_n,
                   "backtestable_on_desk_vintages": desk_n >= va.MIN_VINTAGES})
    c["chart"] = chart
    c["alpha_cluster"] = "options_implied"
    c["required_data"] = [f"desks/mt5/data/lake/series/{params['source']}.parquet"]
    c["falsifier"] = (f"{cond} ({params['feature']} {params['op']} {params['threshold']}) has "
                      f"no measurable relation to {symbol} returns at {chart} out of sample, "
                      "net of this broker's round trip")
    return c


def build_cells(frames: dict[str, pd.DataFrame], *, desk_n: dict[str, int] | None = None
                ) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """The full grid over every symbol whose frame can measure each condition."""
    from mt5desk.family_implied_vol import MIN_OBSERVATIONS
    desk_n = desk_n or {}
    out: list[dict[str, Any]] = []
    skipped: dict[str, list[str]] = {}
    for sym in sorted(frames):
        f = frames[sym]
        src = f"oi_{sym}"
        for cond, feature, op, thr in CONDITIONS:
            n = int(f[feature].notna().sum()) if feature in f.columns else 0
            if n < MIN_OBSERVATIONS:
                skipped.setdefault(sym, []).append(f"{cond}: {feature} has {n} observations")
                continue
            base = {"source": src, "feature": feature, "op": op, "threshold": thr}
            for chart, holds in DIRECT_HOLDS.items():
                for direction, ttl in product(DIRECTIONS, holds):
                    out.append(_cell(sym, chart, "implied_vol_state",
                                     {**base, "direction": direction, "ttl_bars": ttl},
                                     cond, f"direct:{cond}", desk_n=desk_n.get(sym, 0)))
            for fam in BASES:
                out.append(_cell(sym, "H1", "implied_vol_conditioned",
                                 {**base, "base_family": fam, "base_params": {}},
                                 cond, f"indirect:{fam}|{cond}", desk_n=desk_n.get(sym, 0)))
    return out, skipped


# ----------------------------------------------------------------------------- the pass
def run(*, source: va.VolSource | None, dry_run: bool = False,
        registry: dict[str, Any] | None = None, universe_dir: Path | None = None,
        archive: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    if registry is None:
        registry = _read(UNIVERSE_JSON, {}) or {}
    mapped = grounds(registry)
    desk = desk_vintages(va.read_archive(archive or va.ARCHIVE))
    provenance: dict[str, Any] = {}
    histories: dict[str, dict[str, float]] = {}
    for g, _sym in mapped:
        for t in tickers_for(g):
            if t in histories:
                continue
            ref, prov = reference_history(t, source, now=now)
            merged = {**ref, **desk.get(t, {})}
            prov["desk_vintages"] = len(desk.get(t, {}))
            provenance[t] = prov
            histories[t] = merged

    frames: dict[str, pd.DataFrame] = {}
    per_symbol: dict[str, Any] = {}
    desk_n: dict[str, int] = {}
    for g, sym in mapped:
        iv = histories.get(g.vol_ticker) or {}
        if not iv:
            per_symbol[sym] = {"vol_ticker": g.vol_ticker, "status": "UNMEASURED",
                               "why": provenance.get(g.vol_ticker, {}).get("why",
                                                                         "no history")}
            continue
        term = {t: histories.get(t) or {} for t in g.term} if g.term else None
        rv = realised_daily(sym, universe_dir)
        dates = set(desk.get(g.vol_ticker, {}))
        f = build_features(iv, term=term, rv=rv, desk_dates=dates, ticker=g.vol_ticker,
                           symbol=sym)
        frames[sym] = f
        desk_n[sym] = len(dates)
        last = f.iloc[-1]
        per_symbol[sym] = {
            "vol_ticker": g.vol_ticker, "status": "OBSERVED", "rows": len(f),
            "first": str(f["value_date"].iloc[0]), "last": str(last["value_date"]),
            "last_available_time": str(last["available_time"]),
            "desk_vintages": len(dates),
            "rv": ("MEASURED" if rv is not None else
                   f"UNMEASURED: no {sym}_H1.parquet on this host, so vrp is absent"),
            "latest": {k: (None if pd.isna(last[k]) else round(float(last[k]), 4))
                       for k in ("iv_level", "iv_pct_1y", "iv_chg_5d", "slope_9d_30d",
                                 "slope_30d_3m", "term_inverted", "rv_21d", "vrp")},
        }

    cells, skipped = build_cells(frames, desk_n=desk_n)
    from proposer_common import identity
    done = set(_read(DONATED, {}).get("identities") or [])
    fresh = [c for c in cells if identity(c["symbol"], c["family"], c["params"]) not in done]
    feed: dict[str, Any] = {"status": "SKIPPED_DRY_RUN"}
    written: list[str] = []
    path = None
    counts: dict[str, Any] = {}
    if not dry_run:
        for sym, f in frames.items():
            written.append(str(write_series(sym, f)))
        feed = forge_feed(frames) if frames else {"status": "NO_FRAMES"}
        if fresh:
            from proposer_common import donate, donation_counts
            path = donate(source=SEAT, candidates=fresh, tests_run=len(fresh))
            counts = donation_counts()
            if path is not None:
                done |= {identity(c["symbol"], c["family"], c["params"]) for c in fresh}
                _atomic(DONATED, json.dumps({"at": now_iso(), "n": len(done),
                                             "identities": sorted(done)}))
    by_family: dict[str, int] = {}
    by_symbol: dict[str, int] = {}
    for c in cells:
        by_family[c["family"]] = by_family.get(c["family"], 0) + 1
        by_symbol[c["symbol"]] = by_symbol.get(c["symbol"], 0) + 1
    least = min(desk_n.values()) if desk_n else 0
    unmapped = [g.vol_ticker for g in va.GROUND
                if va.resolve_symbol(g.mt5_candidates, registry) is None]
    doc = {
        "at": now_iso(), "writer": "research/options_implied.py", "seat": SEAT,
        "status": ("DRY_RUN" if dry_run else "RAN") if frames else "UNMEASURED",
        "alpha_cluster": "options_implied",
        "rule": ("implied-vol state on the underlying, point-in-time, judged by the one "
                 "gauntlet; nothing here promotes, sizes or conditions capital"),
        "clock": {"published": "value_date + 1 day 00:00 UTC (libs/data/pit_stamp daily lag)",
                  "available": f"published + {CLOCK_PAD_H}h (world_model.CLOCK_PAD_H)",
                  "family_lag": "a further MAX_BROKER_OFFSET_H before a broker-labelled bar"},
        "symbols": per_symbol,
        "not_tradeable_here": unmapped,
        "reference": provenance,
        "terms_note": va.TERMS_NOTE,
        "sources": va.source_record(source),
        "desk_vintages_min": least,
        "min_vintages_for_backtestable": va.MIN_VINTAGES,
        "backtestable_on_desk_vintages": bool(desk_n) and least >= va.MIN_VINTAGES,
        "promotion_authority": False,
        "series_written": written,
        "forge_feed": feed,
        "grid": {"total": len(cells), "by_family": by_family, "by_symbol": by_symbol,
                 "conditions": [c[0] for c in CONDITIONS], "skipped": skipped},
        "donated": {"fresh": len(fresh), "contract": str(path) if path else None,
                    "minted": counts.get("donated", 0),
                    "refused_wrong_lane": counts.get("refused_wrong_lane", 0),
                    "refused_unstamped": counts.get("refused_unstamped", 0),
                    "trials_charged": len(fresh) if path else 0,
                    "rule": "each cell identity is donated once; the docket keeps it"},
        "seconds": round(time.monotonic() - t0, 2),
    }
    if not dry_run:
        _atomic(REPORT, json.dumps(doc, indent=1, default=str))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly cycle is the clock)")
    ap.add_argument("--dry-run", action="store_true", help="compute and print; write nothing")
    ap.add_argument("--offline", action="store_true",
                    help="never fetch; use the reference cache and the desk's own vintages")
    a = ap.parse_args(argv)
    doc = run(source=None if a.offline else va.FredVolSource(), dry_run=a.dry_run)
    print(f"options_implied: {doc['status']} -- {len(doc['symbols'])} mapped symbol(s), "
          f"grid {doc['grid']['total']}, fresh {doc['donated']['fresh']}, minted "
          f"{doc['donated']['minted']}, desk vintages min {doc['desk_vintages_min']}")
    for sym, row in sorted(doc["symbols"].items()):
        if row.get("status") != "OBSERVED":
            print(f"  {sym:<8} {row.get('vol_ticker')}: {row.get('status')} {row.get('why', '')}")
            continue
        print(f"  {sym:<8} {row['vol_ticker']:<6} rows={row['rows']:<5} "
              f"last={row['last']} latest={row['latest']}")
    print(f"YIELD cells={doc['grid']['total']} minted={doc['donated']['minted']} "
          f"symbols={sum(1 for r in doc['symbols'].values() if r.get('status') == 'OBSERVED')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
