"""FUTURES-STATE FACTORY -- global futures positioning, curves and crypto derivatives as MT5 cells.

THE PRINCIPAL, 2026-10-19: futures prices, curves, volume, OI, COT, options on futures and dealer
state go through a futures-state feature factory (level, change, acceleration, percentile, curve
deformation, flow-price disagreement, cross-contract and cross-asset transmission), then into the
strategy labs, exact MT5/Fusion cells, the canonical gauntlet, forward clocks, the allocator and
execution. Maximised every hour and never exhausted.

WHAT THIS ORGAN DOES, end to end, and every stage publishes a number:

  1. COLLECTS from the rows in `research/futures_state_sources.json` -- rows, never code. The OPEN
     sources are the CFTC public reporting API (legacy, disaggregated and TFF, each futures-only
     AND futures+options combined, so the difference is the delta-adjusted OPTIONS-ON-FUTURES
     book), EIA's republished NYMEX contracts 1-4 (WTI, Henry Hub: a dated curve from a
     public-domain source now that Yahoo is IDEAS_ONLY), and Deribit's public read-only API (BTC
     and ETH futures term structure, perpetual funding, option OI, implied vol, a dealer-gamma
     proxy). Every other venue is a row with its terms state (TO_CONFIRM / HELD / IDEAS_ONLY /
     OWNED_ELSEWHERE) and is COUNTED as a named gap, never fetched.

  2. HONEST ACCESS. One User-Agent that says who we are, no retries, and 401/403/429/451 is a
     HARD STOP for that source written to state; it is not fetched again until
     `source_fixer --release` clears it. Nothing here routes around a refusal.

  3. POINT IN TIME. Every row carries `available_time` in UTC: CFTC data is available the Friday
     after its Tuesday report date (stamped Friday 21:00 UTC, after the 15:30 ET release in both
     DST regimes); EIA closes are stamped the next day 23:00 UTC; Deribit snapshots at their
     retrieval time. `family_exogenous_conditioner` then holds every value back a further
     publication day before it can touch a bar.

  4. FEATURES. Each base column becomes level / change / acceleration / rolling percentile; a
     curve becomes slope, roll yield, curvature and contango flag (their changes are the curve's
     deformation); positioning becomes net and net/OI per participant class, the options book
     (combined minus futures-only), and flow-price disagreement (positioning change z minus price
     change z, plus the OI/price quadrant). Transmission rows join two markets' columns into a
     spread or z-gap (copper vs gold managed money, crude curve vs speculative length, ...).

  5. CELLS. Each feature series lands in `data/lake/series/futstate_<id>.parquet` and every
     (column x transform x target x chart) becomes ONE `exogenous_conditioner` candidate through
     `libs.moat.registry.enqueue_candidate`, the same door `pack_cells` uses. A cell is enqueued
     ONCE in its life (state keeps the hash), so a pass never bumps another search_count: trials
     are counted when the rule is minted, never inflated by re-minting it.

  6. NEVER EXHAUSTED. The report lists every CFTC market the catalogue carries that has no row
     yet, every target the account does not quote, every held venue, and every column not yet
     minted -- the hourly pass reads `gaps` and works the queue.

    python desks/mt5/research/futures_state.py --once
    python desks/mt5/research/futures_state.py --once --dry-run      # build, mint nothing
    python desks/mt5/research/futures_state.py --once --offline      # features from held raw only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: The source rows live beside the code, not under data/: data/ is the box's state (and money
#: path to the release gates), and these rows are reviewed configuration, not state.
REGISTRY = DESK / "research" / "futures_state_sources.json"
RAW = DESK / "data" / "futures_state" / "raw"
STATE = DESK / "data" / "futures_state" / "state.json"
SERIES = DESK / "data" / "lake" / "series"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
OUT = DESK / "reports" / "FUTURES_STATE.json"
LAB_INPUTS = DESK / "data" / "intelligence" / "futures_state" / "lab_inputs.json"

UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; futures_state)"
HARD_STOP = frozenset({401, 403, 429, 451})
TRANSFORMS: tuple[str, ...] = ("level_z", "delta", "delta_z")
CHARTS: tuple[str, ...] = ("H1", "H4", "D1")
PCT_WINDOW = 156          # three years of weekly reports; 156 trading days for daily series
MIN_ROWS = 30             # below this a series is UNMEASURED and mints nothing
CFTC_LIMIT = 50000
DERIBIT = "https://www.deribit.com/api/v2/public/"


class HardStop(Exception):
    """A source said no. Recorded and never retried this pass, nor any pass until released."""

    def __init__(self, code: int, url: str):
        super().__init__(f"HTTP {code}")
        self.code, self.url = code, url


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


def fetch_json(url: str, timeout: float = 40.0) -> Any:
    """One honest GET. No retry: a 429 is the server asking us to stop, so we stop."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in HARD_STOP:
            raise HardStop(exc.code, url) from exc
        raise


# ----------------------------------------------------------------------------- features (pure)

def rolling_pct(s: pd.Series, window: int = PCT_WINDOW) -> pd.Series:
    """Causal percentile rank of the latest value inside its trailing window, in [0, 1]."""
    def _rank(a: np.ndarray) -> float:
        last = a[-1]
        if not np.isfinite(last):
            return np.nan
        ok = a[np.isfinite(a)]
        return float((ok <= last).sum() - 1) / max(len(ok) - 1, 1)
    return s.rolling(window, min_periods=min(MIN_ROWS, window)).apply(_rank, raw=True)


def dynamics(df: pd.DataFrame, cols: Sequence[str], window: int = PCT_WINDOW) -> pd.DataFrame:
    """level / change / acceleration / percentile for each column, all strictly causal."""
    out = pd.DataFrame(index=df.index)
    for c in cols:
        s = pd.to_numeric(df[c], errors="coerce")
        chg = s.diff()
        out[c] = s
        out[f"{c}_chg"] = chg
        out[f"{c}_acc"] = chg.diff()
        out[f"{c}_pct"] = rolling_pct(s, window)
        out[f"{c}_chg_pct"] = rolling_pct(chg, window)
    return out


def curve_features(prices: pd.DataFrame, tenors_years: Sequence[float]) -> pd.DataFrame:
    """Slope, roll yield, curvature and contango flag from contract columns ordered near->far.

    `tenors_years` are the contracts' times to expiry (approximate for EIA's rolling C1..C4,
    exact for Deribit). Their changes, taken by `dynamics`, ARE the curve's deformation: a slope
    change is a twist, a curvature change a butterfly.
    """
    p = prices.astype(float).where(prices.astype(float) > 0)
    lp = np.log(p)
    cols = list(p.columns)
    t = list(tenors_years)
    out = pd.DataFrame(index=p.index)
    span = (t[-1] - t[0]) or np.nan
    out["slope"] = (lp[cols[-1]] - lp[cols[0]]) / span
    if len(cols) >= 2:
        out["roll_yield_12"] = (lp[cols[0]] - lp[cols[1]]) / ((t[1] - t[0]) or np.nan)
        out["contango"] = (p[cols[1]] > p[cols[0]]).astype(float).where(p[cols[1]].notna())
    if len(cols) >= 3:
        out["curvature"] = lp[cols[0]] - 2.0 * lp[cols[1]] + lp[cols[2]]
    out["front"] = p[cols[0]]
    return out


def yield_curve_features(y: pd.DataFrame, tenors_years: Sequence[float]) -> pd.DataFrame:
    """Yields in percent, near->far: level per tenor, slope (far - near), curvature
    (2*mid - near - far)."""
    y = y.astype(float)
    cols = list(y.columns)
    out = pd.DataFrame(index=y.index)
    for c in cols:
        out[f"y_{c}"] = y[c]
    if len(cols) >= 2:
        out["slope"] = y[cols[-1]] - y[cols[0]]
    if len(cols) >= 3:
        mid = cols[len(cols) // 2]
        out["curvature"] = 2.0 * y[mid] - y[cols[0]] - y[cols[-1]]
    return out


def positioning(df: pd.DataFrame) -> pd.DataFrame:
    """Net and net/OI for every participant class the report carries, found by column shape.

    Schema-robust on purpose: legacy, disaggregated and TFF name their classes differently and
    CFTC has renamed columns before (`swap__positions_short_all`). Any `<x>_long<...>` with a
    matching `<x>_short<...>` is a class.
    """
    cols = [c for c in df.columns if "_long" in c]
    oi_col = next((c for c in ("open_interest_all", "oi") if c in df.columns), None)
    oi = pd.to_numeric(df[oi_col], errors="coerce") if oi_col else None
    out = pd.DataFrame(index=df.index)
    for lc in cols:
        if "pct_of" in lc or "change_in" in lc or "traders" in lc or "conc_" in lc:
            continue
        stem, _, tail = lc.partition("_long")
        sc = next((c for c in (f"{stem}_short{tail}", f"{stem}__short{tail}")
                   if c in df.columns), None)
        if sc is None and stem.endswith("_positions"):
            alt = stem[: -len("_positions")] + "__positions_short" + tail
            sc = alt if alt in df.columns else None
        if sc is None:
            continue
        name = stem.replace("_positions", "")
        net = pd.to_numeric(df[lc], errors="coerce") - pd.to_numeric(df[sc], errors="coerce")
        out[f"{name}_net"] = net
        if oi is not None:
            out[f"{name}_net_oi"] = net / oi.replace(0, np.nan)
    if oi is not None:
        out["oi"] = oi
    return out


def zscore(s: pd.Series, window: int = PCT_WINDOW) -> pd.Series:
    mu = s.rolling(window, min_periods=MIN_ROWS // 2).mean()
    sd = s.rolling(window, min_periods=MIN_ROWS // 2).std(ddof=0)
    return (s - mu) / sd.replace(0.0, np.nan)


def flow_price(net_chg: pd.Series, oi_chg: pd.Series | None, px_chg: pd.Series,
               window: int = PCT_WINDOW) -> pd.DataFrame:
    """Flow-price disagreement and the OI/price quadrant, aligned on the flow series' index.

    disagree  = z(positioning change) - z(price change): positive when the crowd added length
                the price did not reward (or shed it while price rose).
    quadrant  = +2 long build (OI up, price up), -2 short build (OI up, price down),
                +1 short cover (OI down, price up), -1 long liquidation (OI down, price down).
    """
    px = px_chg.reindex(net_chg.index)
    out = pd.DataFrame(index=net_chg.index)
    out["flow_price_disagree"] = zscore(net_chg, window) - zscore(px, window)
    if oi_chg is not None:
        o, p = np.sign(oi_chg.reindex(net_chg.index)), np.sign(px)
        q = np.where((o > 0) & (p > 0), 2.0, np.where((o > 0) & (p < 0), -2.0,
                     np.where((o < 0) & (p > 0), 1.0, np.where((o < 0) & (p < 0), -1.0, np.nan))))
        out["oi_price_quadrant"] = q
    return out


def bs_gamma(spot: float, strike: float, iv: float, t_years: float) -> float:
    """Black-Scholes gamma (rate 0, which is Deribit's own convention for inverse options)."""
    if spot <= 0 or strike <= 0 or iv <= 0 or t_years <= 0:
        return 0.0
    vs = iv * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + 0.5 * vs * vs) / vs
    return math.exp(-0.5 * d1 * d1) / (math.sqrt(2.0 * math.pi) * spot * vs)


# ----------------------------------------------------------------------------- PIT stamps

def cftc_available(report_date: pd.Series) -> pd.Series:
    """Tuesday report -> Friday 21:00 UTC. A holiday-delayed release is later still, and the
    conditioner's own 24h hold absorbs a one-day slip; a longer one is caught by the release
    calendar lane, not guessed here."""
    d = pd.to_datetime(report_date, utc=True, errors="coerce").dt.normalize()
    return d + pd.Timedelta(days=3, hours=21)


def daily_available(day: pd.Series) -> pd.Series:
    d = pd.to_datetime(day, utc=True, errors="coerce").dt.normalize()
    return d + pd.Timedelta(days=1, hours=23)


def stamped(feat: pd.DataFrame, available: pd.Series, source_id: str,
            event_time: pd.Series | None = None) -> pd.DataFrame:
    out = feat.copy()
    out["available_time"] = pd.to_datetime(available, utc=True).to_numpy()
    if event_time is not None:
        out["event_time"] = pd.to_datetime(event_time, utc=True).to_numpy()
    out["source_id"] = source_id
    out["retrieval_time"] = datetime.now(UTC).isoformat(timespec="seconds")
    return out.dropna(subset=["available_time"]).reset_index(drop=True)


# ----------------------------------------------------------------------------- collectors

def _socrata(url: str, market: Mapping[str, Any], get: Callable[[str], Any]) -> pd.DataFrame:
    """A market is EITHER an exact-name rename chain (`names`, preferred: a substring or LIKE can
    swallow a cross contract, which is how cot_tff/eur.parquet came to be one third EUR/JPY) or a
    `like` pattern whose every hit is reported."""
    names = [str(n).upper().replace("'", "''") for n in market.get("names") or []]
    if names:
        where = "upper(market_and_exchange_names) in (" + ",".join(f"'{n}'" for n in names) + ")"
    else:
        where = f"upper(market_and_exchange_names) like '{str(market['like']).upper()}'"
    q = urllib.parse.urlencode({"$where": where, "$order": "report_date_as_yyyy_mm_dd ASC",
                                "$limit": str(CFTC_LIMIT)})
    rows = get(f"{url}?{q}")
    return pd.DataFrame(rows or [])


def cftc_market(market: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]],
                get: Callable[[str], Any], state: dict[str, Any]
                ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """One market across every OPEN CFTC set. Futures-only and combined both kept, so the
    options book is their difference; each set's classes are prefixed by its family."""
    info: dict[str, Any] = {"market": market["id"], "sets": {}}
    frames: list[pd.DataFrame] = []
    names: set[str] = set()
    for fam in ("legacy", "disagg", "tff"):
        per: dict[str, pd.DataFrame] = {}
        for kind in ("futonly", "combined"):
            sid = f"cftc_{fam}_{kind}"
            src = sources.get(sid) or {}
            if src.get("terms") != "OPEN" or sid in state.get("hard_stops", {}):
                info["sets"][sid] = "NOT_FETCHED"
                continue
            raw_path = RAW / f"{sid}__{market['id']}.json"
            try:
                df = _socrata(str(src["url"]), market, get)
                if not df.empty:
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    df.to_json(raw_path, orient="records")
            except HardStop as hs:
                state.setdefault("hard_stops", {})[sid] = {"code": hs.code, "at": _now()}
                info["sets"][sid] = f"HARD_STOP {hs.code}"
                continue
            except Exception as exc:
                info["sets"][sid] = f"ERROR {type(exc).__name__}"
                df = pd.read_json(raw_path) if raw_path.exists() else pd.DataFrame()
            if df.empty or "report_date_as_yyyy_mm_dd" not in df.columns:
                info["sets"].setdefault(sid, "NO_ROWS")
                continue
            if "market_and_exchange_names" in df.columns:
                hit = sorted(set(df["market_and_exchange_names"].astype(str)))
                names.update(hit)
                if len(hit) > 1 and not market.get("names"):
                    # Two markets matched one pattern. Never merge them: keep the largest by rows
                    # and name the rest so the row can be tightened.
                    top = df["market_and_exchange_names"].value_counts().index[0]
                    df = df[df["market_and_exchange_names"] == top]
                    info.setdefault("ambiguous", hit)
            dup = int(df.duplicated("report_date_as_yyyy_mm_dd").sum())
            if dup:
                info.setdefault("overlap_weeks", {})[sid] = dup
            df = df.drop_duplicates("report_date_as_yyyy_mm_dd", keep="last")
            df.index = pd.to_datetime(df["report_date_as_yyyy_mm_dd"], utc=True)
            per[kind] = positioning(df).add_prefix(f"{fam}_")
            info["sets"].setdefault(sid, f"OK {len(df)}")
        if "futonly" in per:
            frames.append(per["futonly"])
            if "combined" in per:
                opt = per["combined"].sub(per["futonly"].reindex(per["combined"].index))
                opt = opt[[c for c in opt.columns if c.endswith("_net") or c.endswith("_net_oi")]]
                frames.append(opt.add_suffix("_opt"))
        elif "combined" in per:
            frames.append(per["combined"])
    info["matched_names"] = sorted(names)
    if not frames:
        return pd.DataFrame(), info
    pos = pd.concat(frames, axis=1).sort_index()
    pos = pos.loc[:, pos.notna().mean() >= 0.6]
    # ONE open-interest column. Every family's futures-only report carries the same OI for the
    # same market, and three copies would be three trials for one piece of information.
    oi_cols = [c for c in pos.columns if c.endswith("_oi") and not c.endswith("_net_oi")]
    if oi_cols:
        pos["oi"] = pos[oi_cols[0]]
        pos = pos.drop(columns=oi_cols)
    return pos, info


def eia_curve(curve: Mapping[str, Any], key: str, get: Callable[[str], Any]) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    for s in curve["series"]:
        q = urllib.parse.urlencode({"api_key": key, "frequency": "daily", "data[0]": "value",
                                    "facets[series][]": s, "sort[0][column]": "period",
                                    "sort[0][direction]": "asc", "length": "5000"})
        doc = get(f"https://api.eia.gov/v2/{curve['route']}/data/?{q}") or {}
        rows = ((doc.get("response") or {}).get("data")) or []
        if rows:
            d = pd.DataFrame(rows)
            cols[s] = pd.Series(pd.to_numeric(d["value"], errors="coerce").to_numpy(),
                                index=pd.to_datetime(d["period"], utc=True))
    return pd.DataFrame(cols).sort_index()


def fred_outputs(cv: Mapping[str, Any], yc: pd.DataFrame
                 ) -> list[tuple[str, pd.DataFrame, pd.DatetimeIndex, list[str], str]]:
    """One FRED set -> its feature frames, by mode.

    curve   the set is one term structure (level per tenor, slope, curvature).
    pairs   each pair is base minus quote, e.g. euro-area minus US 3M rate for EURUSD: the
            interest-rate differential a forward prices, compared against the swap the broker
            charges elsewhere (GAP_MAP row 64). One series per pair, with that pair's targets.
    levels  each series alone, level and log change (reserves: the change is the intervention
            proxy), with the targets named for that series.
    """
    mode = str(cv.get("mode") or "curve")
    out: list[tuple[str, pd.DataFrame, pd.DatetimeIndex, list[str], str]] = []
    if mode == "curve":
        curve = yield_curve_features(yc, cv.get("tenors") or [])
        out.append((f"fred_{cv['id']}", dynamics(curve, list(curve.columns), window=252),
                    pd.DatetimeIndex(yc.index), list(cv.get("targets") or []), "fred_yield_curve"))
    elif mode == "pairs":
        for pr in cv.get("pairs") or []:
            b, q = str(pr["base"]), str(pr["quote"])
            if b not in yc.columns or q not in yc.columns:
                continue
            both = yc[[b, q]].ffill().dropna()
            if len(both) < MIN_ROWS:
                continue
            diff = pd.DataFrame({"diff": both[b] - both[q]}, index=both.index)
            out.append((f"fred_{cv['id']}_{str(pr['id']).lower()}",
                        dynamics(diff, ["diff"], window=int(cv.get("window", 252))),
                        pd.DatetimeIndex(both.index), list(pr.get("targets") or []),
                        "fred_rate_differential"))
    elif mode == "levels":
        for ser, targets in (cv.get("targets_by_series") or {}).items():
            if ser not in yc.columns:
                continue
            v = yc[ser].dropna()
            v = v[v > 0]
            if len(v) < MIN_ROWS:
                continue
            f = pd.DataFrame({"level": v, "log_chg": np.log(v).diff()}, index=v.index)
            out.append((f"fred_{cv['id']}_{ser.lower()}",
                        dynamics(f, ["level", "log_chg"], window=int(cv.get("window", 60))),
                        pd.DatetimeIndex(v.index), list(targets), "fred_level"))
    return out


def fred_curve(curve: Mapping[str, Any], key: str, get: Callable[[str], Any]) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    for s in curve["series"]:
        q = urllib.parse.urlencode({"series_id": s, "api_key": key, "file_type": "json"})
        doc = get(f"https://api.stlouisfed.org/fred/series/observations?{q}") or {}
        rows = doc.get("observations") or []
        if rows:
            d = pd.DataFrame(rows)
            cols[s] = pd.Series(pd.to_numeric(d["value"], errors="coerce").to_numpy(),
                                index=pd.to_datetime(d["date"], utc=True))
    return pd.DataFrame(cols).sort_index()


def deribit_snapshot(currency: str, get: Callable[[str], Any], now: datetime) -> dict[str, float]:
    """One PIT snapshot: futures basis curve, perpetual funding, option OI/IV, gamma proxy."""
    snap: dict[str, float] = {}
    fut = (get(f"{DERIBIT}get_book_summary_by_currency?currency={currency}&kind=future")
           or {}).get("result") or []
    curve: list[tuple[float, float, float]] = []
    tot_oi = 0.0
    for r in fut:
        name = str(r.get("instrument_name") or "")
        mark, idx = float(r.get("mark_price") or 0), float(r.get("estimated_delivery_price") or 0)
        tot_oi += float(r.get("open_interest") or 0)
        if name.endswith("PERPETUAL"):
            snap["funding_8h"] = float(r.get("funding_8h") or np.nan)
            snap["perp_premium"] = (mark / idx - 1.0) if idx else np.nan
            continue
        exp = _deribit_expiry(name)
        if exp is None or not idx or not mark:
            continue
        t = (exp - now).total_seconds() / (365.25 * 86400)
        if t > 1 / 365:
            curve.append((t, math.log(mark / idx) / t, mark))
    snap["fut_oi"] = tot_oi
    if curve:
        curve.sort()
        ts, bs = np.array([c[0] for c in curve]), np.array([c[1] for c in curve])
        for days in (7, 30, 90):
            snap[f"basis_ann_{days}d"] = float(np.interp(days / 365.25, ts, bs))
        snap["basis_slope"] = float(bs[-1] - bs[0]) if len(bs) > 1 else np.nan
    opt = (get(f"{DERIBIT}get_book_summary_by_currency?currency={currency}&kind=option")
           or {}).get("result") or []
    put_oi = call_oi = iv_w = gex = 0.0
    walls: dict[float, float] = {}
    skew_p: list[float] = []
    skew_c: list[float] = []
    spot = float(next((o.get("underlying_price") for o in opt
                       if o.get("underlying_price")), 0) or 0)
    for o in opt:
        parts = str(o.get("instrument_name") or "").split("-")
        if len(parts) != 4:
            continue
        oi, iv = float(o.get("open_interest") or 0), float(o.get("mark_iv") or 0) / 100.0
        exp = _deribit_expiry("-".join(parts[:2]))
        strike = float(parts[2]) if parts[2].replace(".", "").isdigit() else 0.0
        if exp is None or not strike:
            continue
        t = (exp - now).total_seconds() / (365.25 * 86400)
        g = bs_gamma(spot, strike, iv, t) * oi * spot * spot * 0.01
        # ASSUMPTION, labelled: customers net long puts and short calls, so dealers are long call
        # gamma and short put gamma. It is a proxy for the sign, not a measured dealer book.
        if parts[3] == "C":
            call_oi += oi
            gex += g
            if 1.0 < strike / spot <= 1.10 and 7 / 365 < t < 60 / 365:
                skew_c.append(iv)
        else:
            put_oi += oi
            gex -= g
            if 0.90 <= strike / spot < 1.0 and 7 / 365 < t < 60 / 365:
                skew_p.append(iv)
        iv_w += iv * oi
        walls[strike] = walls.get(strike, 0.0) + abs(g)
    if put_oi + call_oi > 0 and spot:
        snap["opt_oi"] = put_oi + call_oi
        snap["put_call_oi"] = put_oi / call_oi if call_oi else np.nan
        snap["iv_oi_weighted"] = iv_w / (put_oi + call_oi)
        snap["gex_proxy"] = gex
        wall = max(walls, key=lambda k: walls[k]) if walls else np.nan
        snap["gamma_wall_dist"] = (wall / spot - 1.0) if walls else np.nan
        if skew_p and skew_c:
            snap["skew_10pct"] = float(np.mean(skew_p) - np.mean(skew_c))
    snap["spot"] = spot
    return snap


_MONTHS = {m: i for i, m in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}


def _deribit_expiry(name: str) -> datetime | None:
    """`BTC-27DEC26` -> 2026-12-27 08:00 UTC (Deribit's expiry hour)."""
    try:
        tag = name.split("-")[1]
        day, mon, yr = int(tag[:-5]), _MONTHS[tag[-5:-2]], 2000 + int(tag[-2:])
        return datetime(yr, mon, day, 8, tzinfo=UTC)
    except Exception:
        return None


def deribit_dvol_history(currency: str, get: Callable[[str], Any], now: datetime) -> pd.Series:
    """Daily DVOL closes back as far as the API serves, for an immediately judgeable history."""
    end = int(now.timestamp() * 1000)
    start = end - 5 * 365 * 86400 * 1000
    url = (f"{DERIBIT}get_volatility_index_data?currency={currency}&start_timestamp={start}"
           f"&end_timestamp={end}&resolution=1D")
    rows = ((get(url) or {}).get("result") or {}).get("data") or []
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series([float(r[4]) for r in rows],
                     index=pd.to_datetime([int(r[0]) for r in rows], unit="ms", utc=True))


# ----------------------------------------------------------------------------- build

def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _universe() -> frozenset[str]:
    doc = _read(UNIVERSE, {}) or {}
    return frozenset(str(k) for k in doc) if isinstance(doc, dict) else frozenset()


def _write_series(sid: str, frame: pd.DataFrame) -> Path:
    SERIES.mkdir(parents=True, exist_ok=True)
    p = SERIES / f"{sid}.parquet"
    frame.to_parquet(p, index=False)
    return p


def _feature_cols(frame: pd.DataFrame) -> list[str]:
    stamp = {"available_time", "event_time", "source_id", "retrieval_time"}
    cols = []
    for c in frame.columns:
        if c in stamp:
            continue
        s = pd.to_numeric(frame[c], errors="coerce")
        if s.notna().sum() >= MIN_ROWS and s.nunique(dropna=True) >= 4:
            cols.append(str(c))
    return cols


def build_market_series(registry: Mapping[str, Any], *, get: Callable[[str], Any] | None,
                        state: dict[str, Any], bars: Callable[[str], pd.DataFrame | None]
                        ) -> tuple[dict[str, dict[str, Any]], dict[str, pd.DataFrame],
                                    list[dict[str, Any]]]:
    """Every OPEN source -> stamped feature frames. `get=None` means offline (held raw only)."""
    sources = {str(s["id"]): s for s in registry.get("sources") or []}
    built: dict[str, dict[str, Any]] = {}
    frames: dict[str, pd.DataFrame] = {}
    notes: list[dict[str, Any]] = []
    offline_get = _offline_get

    for m in registry.get("cftc_markets") or []:
        pos, info = cftc_market(m, sources, get or offline_get, state)
        notes.append(info)
        if pos.empty or len(pos) < MIN_ROWS:
            continue
        sign = float(m.get("sign", 1))
        # Net/OI per class, the options book per class, and OI. Raw contract counts are left
        # out: net/OI carries the same information scaled, and both would be charged twice.
        base = [c for c in pos.columns if c.endswith("_net_oi") or c.endswith("_net_oi_opt")
                or c == "oi"]
        feat = dynamics(pos * np.where([c != "oi" for c in pos.columns], sign, 1.0), base)
        # FLOW-PRICE DISAGREEMENT against the first quoted target's own close at the report date.
        tgt = next((t for t in m.get("targets") or [] if bars(t) is not None), None)
        head = next((c for c in ("disagg_m_money_net_oi", "tff_lev_money_net_oi",
                                 "legacy_noncomm_net_oi")
                     if c in pos.columns), None)
        if tgt and head:
            b = bars(tgt)
            close = (b["close"].astype(float).resample("1D").last().dropna()
                     if b is not None else None)
            if close is not None and len(close):
                px = np.log(close).reindex(pos.index, method="ffill").diff()
                oi_chg = pos["oi"].diff() if "oi" in pos.columns else None
                feat = feat.join(flow_price(pos[head].diff() * sign, oi_chg, px))
        sid = f"cot_{m['id']}"
        frames[sid] = stamped(feat.reset_index(drop=True), cftc_available(pd.Series(pos.index)),
                              sid, pd.Series(pos.index))
        built[sid] = {"targets": list(m.get("targets") or []), "kind": "cftc",
                      "rows": len(pos), "last_event": str(pos.index.max())}

    eia = sources.get("eia_futures") or {}
    key = next((os.environ.get(k) for k in eia.get("key_env") or [] if os.environ.get(k)), "")
    for cv in registry.get("eia_curves") or []:
        sid = f"eia_{cv['id']}"
        raw_path = RAW / f"{sid}.parquet"
        px = pd.DataFrame()
        if get is not None and eia.get("terms") == "OPEN" and key and \
                "eia_futures" not in state.get("hard_stops", {}):
            try:
                px = eia_curve(cv, key, get)
                if not px.empty:
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    px.to_parquet(raw_path)
            except HardStop as hs:
                state.setdefault("hard_stops", {})["eia_futures"] = {"code": hs.code, "at": _now()}
            except Exception as exc:
                notes.append({"source": sid, "error": f"{type(exc).__name__}"})
        elif not key:
            notes.append({"source": sid, "status": "NEEDS_KEY", "key_env": eia.get("key_env")})
        if px.empty and raw_path.exists():
            px = pd.read_parquet(raw_path)
        if px.empty or len(px) < MIN_ROWS:
            continue
        px = px[[c for c in cv["series"] if c in px.columns]].dropna(how="all")
        curve = curve_features(px, [i / 12.0 for i in range(1, px.shape[1] + 1)])
        feat = dynamics(curve, [c for c in curve.columns if c != "contango"], window=252)
        feat["contango"] = curve["contango"]
        frames[sid] = stamped(feat.reset_index(drop=True), daily_available(pd.Series(px.index)),
                              sid, pd.Series(px.index))
        built[sid] = {"targets": list(cv.get("targets") or []), "kind": "eia_curve",
                      "rows": len(px), "last_event": str(px.index.max())}

    fred = sources.get("fred_rates") or {}
    fkey = next((os.environ.get(k) for k in fred.get("key_env") or [] if os.environ.get(k)), "")
    for cv in [*(registry.get("fred_curves") or []), *(registry.get("fred_sets") or [])]:
        cv = {**cv, "series": cv.get("series") or sorted(
            {str(p[k]) for p in cv.get("pairs") or [] for k in ("base", "quote")})}
        sid = f"fred_{cv['id']}"
        raw_path = RAW / f"{sid}.parquet"
        yc = pd.DataFrame()
        if get is not None and fred.get("terms") == "OPEN" and fkey and \
                "fred_rates" not in state.get("hard_stops", {}):
            try:
                yc = fred_curve(cv, fkey, get)
                if not yc.empty:
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    yc.to_parquet(raw_path)
            except HardStop as hs:
                state.setdefault("hard_stops", {})["fred_rates"] = {"code": hs.code, "at": _now()}
            except Exception as exc:
                notes.append({"source": sid, "error": f"{type(exc).__name__}"})
        elif not fkey:
            notes.append({"source": sid, "status": "NEEDS_KEY", "key_env": fred.get("key_env")})
        if yc.empty and raw_path.exists():
            yc = pd.read_parquet(raw_path)
        yc = yc[[c for c in cv["series"] if c in yc.columns]].dropna(how="all") if len(yc) else yc
        if yc.empty or len(yc) < MIN_ROWS:
            continue
        lag = cv.get("avail_lag_days")
        for oid, feat, idx, targets, kind in fred_outputs(cv, yc):
            at = (daily_available(pd.Series(idx)) if lag is None else
                  pd.to_datetime(pd.Series(idx), utc=True).dt.normalize()
                  + pd.Timedelta(days=int(lag), hours=23))
            frames[oid] = stamped(feat.reset_index(drop=True), at, oid, pd.Series(idx))
            built[oid] = {"targets": targets, "kind": kind, "rows": len(feat),
                          "last_event": str(idx.max())}

    der = sources.get("deribit_public") or {}
    now = datetime.now(UTC)
    for d in registry.get("deribit") or []:
        sid = f"deribit_{d['id']}"
        snap_path = RAW / f"{sid}_snapshots.parquet"
        snaps = pd.read_parquet(snap_path) if snap_path.exists() else pd.DataFrame()
        dvol_path = RAW / f"{sid}_dvol.parquet"
        if get is not None and der.get("terms") == "OPEN" and \
                "deribit_public" not in state.get("hard_stops", {}):
            try:
                row: dict[str, Any] = deribit_snapshot(str(d["currency"]), get, now)
                row["available_time"] = now.isoformat()
                snaps = pd.concat([snaps, pd.DataFrame([row])], ignore_index=True)
                snap_path.parent.mkdir(parents=True, exist_ok=True)
                snaps.to_parquet(snap_path, index=False)
                today = now.date().isoformat()
                if not dvol_path.exists() or state.get("dvol_day", {}).get(sid) != today:
                    dv = deribit_dvol_history(str(d["currency"]), get, now)
                    if len(dv):
                        dv.rename("dvol").to_frame().to_parquet(dvol_path)
                        state.setdefault("dvol_day", {})[sid] = today
            except HardStop as hs:
                state.setdefault("hard_stops", {})["deribit_public"] = {"code": hs.code,
                                                                        "at": _now()}
            except Exception as exc:
                notes.append({"source": sid, "error": f"{type(exc).__name__}"})
        if dvol_path.exists():
            dv = pd.read_parquet(dvol_path)
            feat = dynamics(dv, ["dvol"], window=252)
            vid = f"{sid}_dvol"
            frames[vid] = stamped(feat.reset_index(drop=True), daily_available(pd.Series(dv.index)),
                                  vid, pd.Series(dv.index))
            built[vid] = {"targets": list(d.get("targets") or []), "kind": "deribit_dvol",
                          "rows": len(dv), "last_event": str(dv.index.max())}
        if len(snaps) >= MIN_ROWS:
            snaps = snaps.sort_values("available_time")
            at = pd.to_datetime(snaps["available_time"], utc=True)
            cols = [c for c in snaps.columns if c not in ("available_time", "spot")]
            feat = dynamics(snaps.reset_index(drop=True), cols, window=24 * 30)
            frames[sid] = stamped(feat, at.reset_index(drop=True), sid)
            built[sid] = {"targets": list(d.get("targets") or []), "kind": "deribit_snapshot",
                          "rows": len(snaps), "last_event": str(at.max())}
        else:
            notes.append({"source": sid, "status": "ACCRUING", "snapshots": len(snaps),
                          "need": MIN_ROWS})

    for tr in registry.get("transmissions") or []:
        a, b = frames.get(str(tr["a"])), frames.get(str(tr["b"]))
        ca = str(tr.get("column_a") or tr.get("column"))
        cb = str(tr.get("column_b") or tr.get("column"))
        if a is None or b is None or ca not in a.columns or cb not in b.columns:
            notes.append({"transmission": tr["id"], "status": "UNMEASURED",
                          "why": "a leg is missing this pass"})
            continue
        sa = pd.Series(pd.to_numeric(a[ca], errors="coerce").to_numpy(),
                       index=pd.to_datetime(a["available_time"], utc=True)).sort_index()
        sb = pd.Series(pd.to_numeric(b[cb], errors="coerce").to_numpy(),
                       index=pd.to_datetime(b["available_time"], utc=True)).sort_index()
        sa, sb = sa[~sa.index.duplicated(keep="last")], sb[~sb.index.duplicated(keep="last")]
        # As-of join: each row of the later-publishing leg sees only what the other had published.
        idx = sa.index.union(sb.index)
        ja, jb = sa.reindex(idx).ffill(), sb.reindex(idx).ffill()
        val = (zscore(ja) - zscore(jb)) if tr.get("op") == "zgap" else (ja - jb)
        f = dynamics(pd.DataFrame({"x": val}), ["x"]).dropna(subset=["x"])
        sid = f"xfer_{tr['id']}"
        frames[sid] = stamped(f.reset_index(drop=True), pd.Series(f.index), sid)
        built[sid] = {"targets": list(tr.get("targets") or []), "kind": "transmission",
                      "rows": len(f), "why": tr.get("why", "")}
    return built, frames, notes


def _offline_get(url: str) -> Any:
    raise ConnectionError("offline")


def cell_hash(sid: str, col: str, tf: str, sym: str, chart: str) -> str:
    return hashlib.sha1(f"{sid}|{col}|{tf}|{sym}|{chart}".encode()).hexdigest()[:16]


#: Cells minted per pass. The judge's clock, not ours, decides how fast cells are tested, and a
#: flood minted at once would sit unjudged while charging the program for every one. The queue
#: is ordered so the headline state goes first; nothing is dropped, the rest leads next pass.
MAX_MINT_PER_PASS = 3000
_HEADLINE = ("m_money", "lev_money", "noncomm", "_opt", "flow_price", "oi_price", "slope",
             "roll_yield", "curvature", "basis", "funding", "perp_premium", "dvol", "gex",
             "gamma_wall", "skew", "put_call", "iv_", "x")
_DERIVED = ("_chg", "_acc", "_pct")


def _col_rank(col: str) -> tuple[int, int]:
    derived = any(col.endswith(d) or f"{d}_" in col for d in _DERIVED)
    headline = col == "x" or any(h in col for h in _HEADLINE if h != "x")
    return (0 if headline else 1, 1 if derived else 0)


def cell_plan(built: Mapping[str, Mapping[str, Any]], frames: Mapping[str, pd.DataFrame],
              universe: frozenset[str]) -> list[tuple[str, str, str, str, str]]:
    """Every (series, column, transform, target, chart), headline-first, series round robin.

    A column `dynamics` already differenced or ranked (`_chg`, `_acc`, `_pct`) is asked only as
    `level_z`: `delta` of a change is the acceleration column, which is already in the set, so
    asking it again would be the same hypothesis charged twice.
    """
    per: dict[str, list[tuple[tuple[int, int], str, str, str, str, str]]] = {}
    for sid, meta in built.items():
        targets = [t for t in meta.get("targets") or [] if t in universe]
        for col in _feature_cols(frames[sid]):
            rank = _col_rank(col)
            tfs = ("level_z",) if rank[1] else TRANSFORMS
            for tf in tfs:
                for sym in targets:
                    for chart in CHARTS:
                        per.setdefault(sid, []).append((rank, sid, col, tf, sym, chart))
    for rows in per.values():
        rows.sort(key=lambda r: r[0])
    plan: list[tuple[str, str, str, str, str]] = []
    queues = [list(v) for _k, v in sorted(per.items())]
    for tier in ((0, 0), (0, 1), (1, 0), (1, 1)):
        live = [[r for r in q if r[0] == tier] for q in queues]
        while any(live):
            for q in live:
                if q:
                    plan.append(q.pop(0)[1:])
    return plan


def mint(built: Mapping[str, Mapping[str, Any]], frames: Mapping[str, pd.DataFrame],
         universe: frozenset[str], state: dict[str, Any], *, dry_run: bool,
         enqueue: Callable[..., tuple[str, bool]] | None = None,
         limit: int = MAX_MINT_PER_PASS) -> dict[str, Any]:
    """The next `limit` unminted cells of the plan, each minted once in its life."""
    minted = set(state.get("minted") or [])
    plan = cell_plan(built, frames, universe)
    new = 0
    errors: list[str] = []
    per_series: dict[str, int] = {}
    mechs = {sid: (f"futures state {sid} ({meta.get('kind')}) conditions "
                   f"{', '.join(t for t in meta.get('targets') or [] if t in universe)}: "
                   f"positioning, curve and derivatives state carry information the CFD's own "
                   f"price has not yet absorbed. {meta.get('why', '')}").strip()
             for sid, meta in built.items()}
    for sid, col, tf, sym, chart in plan:
        h = cell_hash(sid, col, tf, sym, chart)
        if h in minted or dry_run or enqueue is None or new >= limit:
            continue
        mech = mechs[sid]
        try:
            enqueue(family="exogenous_conditioner", symbol=sym,
                    params={"source": sid, "signal": col, "transform": tf},
                    origin="futures_state", mechanism=mech, chart=chart,
                    horizon=chart, source_id=sid, generator="futures_state",
                    department="information", asset_class="",
                    transformation="futures_state_feature",
                    required_data=[f"desks/mt5/data/lake/series/{sid}.parquet"],
                    pit_status="STAMPED", causal_rationale=mech,
                    falsifier=(f"the {tf} of {sid}.{col} has no measurable "
                               f"relation to {sym} at {chart} out of sample"))
            minted.add(h)
            new += 1
            per_series[sid] = per_series.get(sid, 0) + 1
        except Exception as exc:
            errors.append(f"{sid}/{col}/{sym}: {type(exc).__name__}: {str(exc)[:50]}")
    state["minted"] = sorted(minted)
    planned = {cell_hash(*r) for r in plan}
    unquoted = {sid: [t for t in meta.get("targets") or [] if t not in universe]
                for sid, meta in built.items()}
    return {"cells_planned": len(plan), "cells_minted_this_pass": new,
            "cells_minted_total": len(minted), "cells_queued": len(planned - minted),
            "minted_by_series": per_series,
            "unquoted_targets": {k: v for k, v in unquoted.items() if v}, "errors": errors[:10]}


def gaps(registry: Mapping[str, Any], built: Mapping[str, Any],
         notes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """What is NOT covered yet, by name. The hourly pass works this list; it never empties."""
    held = [{"id": s["id"], "terms": s.get("terms"), "note": s.get("note", "")}
            for s in registry.get("sources") or []
            if s.get("terms") != "OPEN" or s.get("adapter") == "none"]
    missed = [s["id"] for s in registry.get("sources") or [] if s.get("missed_growth")]
    missing = [n.get("market") for n in notes if n.get("market") and
               f"cot_{n['market']}" not in built]
    ambiguous = [{"market": n["market"], "names": n["ambiguous"]} for n in notes
                 if n.get("ambiguous")]
    return {"held_or_unconfirmed_venues": held, "missed_growth_unmeasured": missed,
            "markets_without_series": missing,
            "ambiguous_market_patterns": ambiguous,
            "unmeasured": [n for n in notes if n.get("status") in ("UNMEASURED", "NEEDS_KEY",
                                                                     "ACCRUING")]}


def lab_inputs(built: Mapping[str, Any], frames: Mapping[str, pd.DataFrame]
               ) -> list[dict[str, Any]]:
    """The strategy labs' brief: each series' latest state as percentiles, nothing to fit on."""
    rows = []
    for sid, meta in built.items():
        f = frames[sid]
        last = f.iloc[-1]
        extremes = {c: round(float(last[c]), 3) for c in f.columns if c.endswith("_pct")
                    and pd.notna(last[c]) and (last[c] >= 0.9 or last[c] <= 0.1)}
        rows.append({"series": sid, "kind": meta.get("kind"), "targets": meta.get("targets"),
                     "as_of": str(last.get("available_time")), "extreme_percentiles": extremes,
                     "columns": _feature_cols(f),
                     "family": "exogenous_conditioner",
                     "params_template": {"source": sid, "signal": "<column>",
                                         "transform": "level_z|delta|delta_z"}})
    return rows


def build(*, dry_run: bool = False, offline: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    registry = _read(REGISTRY, {}) or {}
    state = _read(STATE, {}) or {}
    try:
        from research.proposer_common import bars
    except Exception:
        def bars(sym: str) -> pd.DataFrame | None:
            return None
    built, frames, notes = build_market_series(
        registry, get=None if offline else fetch_json, state=state, bars=bars)
    if not dry_run:
        for sid, f in frames.items():
            _write_series(sid, f)
    enqueue: Callable[..., tuple[str, bool]] | None = None
    if not dry_run:
        try:
            from libs.moat.registry import enqueue_candidate
            enqueue = enqueue_candidate
        except Exception as exc:
            notes.append({"registry": "UNAVAILABLE", "why": f"{type(exc).__name__}"})
    cells = mint(built, frames, _universe(), state, dry_run=dry_run, enqueue=enqueue)
    doc = {
        "generated_utc": _now(),
        "rule": ("Every futures, commodity and crypto-derivative series reaches cells or is named "
                 "below with its reason. 401/403/429/451 is a hard stop; held venues are never "
                 "fetched; a cell is minted once in its life so trials are never inflated."),
        "series": built,
        "n_series": len(built),
        "cells": cells,
        "hard_stops": state.get("hard_stops", {}),
        "gaps": gaps(registry, built, notes),
        "notes": notes,
        "seconds": round(time.monotonic() - t0, 1),
    }
    if not dry_run:
        _write(STATE, state)
        _write(LAB_INPUTS, {"generated_utc": doc["generated_utc"],
                            "rows": lab_inputs(built, frames)})
        _write(OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    doc = build(dry_run=a.dry_run, offline=a.offline)
    c = doc["cells"]
    print(f"futures state: {doc['n_series']} series, {c['cells_planned']} cells planned, "
          f"{c['cells_minted_this_pass']} minted this pass ({c['cells_minted_total']} total, "
          f"{c['cells_queued']} queued), "
          f"{len(doc['hard_stops'])} hard stop(s), {doc['seconds']}s")
    g = doc["gaps"]
    print(f"  gaps: {len(g['markets_without_series'])} market(s) without series, "
          f"{len(g['held_or_unconfirmed_venues'])} held venue(s), "
          f"{len(g['unmeasured'])} unmeasured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
