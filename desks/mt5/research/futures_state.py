"""FUTURES-STATE FACTORY -- global futures positioning, curves and FX state as MT5 cells.

THE PRINCIPAL, 2026-10-19: futures prices, curves, volume, OI, COT, options on futures and dealer
state go through a futures-state feature factory (level, change, acceleration, percentile, curve
deformation, flow-price disagreement, cross-contract and cross-asset transmission), then into the
strategy labs, exact MT5/Fusion cells, the canonical gauntlet, forward clocks, the allocator and
execution. Maximised every hour and never exhausted.

WHAT THIS ORGAN DOES, end to end, and every stage publishes a number:

  1. COLLECTS from the rows in `research/futures_state_sources.json` -- rows, never code. The OPEN
     sources are the CFTC public reporting API (legacy, disaggregated and TFF, each futures-only
     AND futures+options combined, so the difference is the delta-adjusted OPTIONS-ON-FUTURES
     book), FRED's curves, rate differentials and reserves, and Japan's MoF intervention record
     (every intervention day since 1991, signed, stamped at its quarterly disclosure; monthly
     totals stamped at their release). Every other
     venue is a row with its terms state (TO_CONFIRM / HELD / IDEAS_ONLY / OWNED_ELSEWHERE /
     DISCONTINUED: EIA's NYMEX contracts 1-4 stopped after 2024-04-05) and is COUNTED as a named
     gap, never fetched. CFTC is read incrementally, past the newest held week, and only once the
     next report is out; every request goes through `libs.data.polite_fetch` with retries off.

  2. HONEST ACCESS. One User-Agent that says who we are, no retries, and 401/403/429/451 is a
     HARD STOP for that source written to state; it is not fetched again until
     `source_fixer --release` clears it. Nothing here routes around a refusal.

  3. POINT IN TIME. Every row carries `available_time` in UTC: a CFTC report is stamped 21:00 UTC
     on the day CFTC published it (after the 15:30 ET release in both DST regimes): the Friday
     after its as-of day, the next business day when a federal holiday or closure falls in
     between, and the dates of CFTC's own catch-up notices after a shutdown
     (`cftc_release_calendar` in the registry). Daily FRED closes are stamped the next business
     day 23:00 UTC; monthly sets after their own publication lag. A series silent past three
     times its own cadence is STALE and mints nothing. `family_exogenous_conditioner` then holds
     every value back a further publication day before it can touch a bar.

  4. FEATURES. Each base column becomes level / change / acceleration / rolling percentile; a
     curve becomes slope, roll yield, curvature and contango flag (their changes are the curve's
     deformation); positioning becomes net and net/OI per participant class, the options book
     (combined minus futures-only), and flow-price disagreement (positioning change z minus price
     change z, plus the OI/price quadrant). Transmission rows join two markets' columns into a
     spread or z-gap (copper vs gold managed money, crude curve vs speculative length, ...).

  5. CELLS. Each feature series lands in `data/lake/series/<id>.parquet`, the id prefixed by
     its source (`cot_`, `fred_`, `mof_`, `xfer_`, `eia_`), and every
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
import gzip
import hashlib
import json
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
    _replace(tmp, p)


class FetchError(Exception):
    """A non-refusal failure, with the status when there was one (a 404 robots.txt allows)."""

    def __init__(self, code: int | None, url: str, why: str):
        super().__init__(why)
        self.code, self.url = code, url


#: Spacing, retries and stats come from the desk's one polite fetcher. Retries are OFF: a 429
#: here is the server asking us to stop, and it becomes a hard stop, never a retry.
def _polite(url: str, accept: str, timeout: float) -> str:
    from libs.data import polite_fetch
    r = polite_fetch.get(url, headers={"User-Agent": UA, "Accept": accept}, timeout=timeout,
                         retries=0, leg="futures_state")
    if r.status in HARD_STOP:
        raise HardStop(int(r.status or 0), url)
    if not r.ok:
        raise FetchError(r.status, url, r.error or f"HTTP {r.status}")
    return r.text


def fetch_json(url: str, timeout: float = 40.0) -> Any:
    """One honest GET. No retry: a 429 is the server asking us to stop, so we stop."""
    return json.loads(_polite(url, "application/json", timeout))


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
    exact for dated contracts). Their changes, taken by `dynamics`, ARE the curve's deformation:
    a slope change is a twist, a curvature change a butterfly.
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


# ----------------------------------------------------------------------------- PIT stamps

def _us_holidays(closures: Sequence[str] = ()) -> frozenset[pd.Timestamp]:
    from pandas.tseries.holiday import USFederalHolidayCalendar
    h = USFederalHolidayCalendar().holidays("1986-01-01", "2040-12-31")
    return frozenset({pd.Timestamp(x).normalize() for x in h} |
                     {pd.Timestamp(x).normalize() for x in closures})


def cftc_release_day(report_day: pd.Timestamp, calendar: Mapping[str, Any] | None = None,
                     holidays: frozenset[pd.Timestamp] | None = None) -> pd.Timestamp:
    """The day a report dated `report_day` was PUBLIC. Normally the Friday after (15:30 ET).
    A federal holiday or a CFTC closure between the report day and that Friday moves it to the
    next business day after the Friday, which is the rule every 2026 delayed release follows
    (CFTC release schedule). A shutdown is never inferred: `calendar["releases"]` maps an
    as-of day to the date CFTC published it, and `calendar["windows"]` holds a not-before date
    for every report dated inside a window whose exact catch-up dates are not on record."""
    cal = calendar or {}
    d = pd.Timestamp(report_day).tz_localize(None).normalize()
    exact = (cal.get("releases") or {}).get(d.date().isoformat())
    if exact:
        return pd.Timestamp(exact)
    hol = holidays if holidays is not None else _us_holidays(cal.get("closures") or ())
    friday = d + pd.Timedelta(days=(4 - d.weekday()) % 7 or 7)
    rel = friday
    if any(d < h <= friday for h in hol):
        rel = friday + pd.Timedelta(days=1)
        while rel.weekday() >= 5 or rel in hol:
            rel += pd.Timedelta(days=1)
    for w in cal.get("windows") or []:
        if pd.Timestamp(w["from"]) <= d <= pd.Timestamp(w["to"]):
            rel = max(rel, pd.Timestamp(w["not_before"]))
    return rel


def cftc_available(report_date: pd.Series, calendar: Mapping[str, Any] | None = None
                   ) -> pd.Series:
    """Report day -> its release day at 21:00 UTC (after 15:30 ET in both DST regimes)."""
    hol = _us_holidays((calendar or {}).get("closures") or ())
    d = pd.to_datetime(report_date, utc=True, errors="coerce")
    out = [pd.NaT if pd.isna(x) else
           (cftc_release_day(x, calendar, hol) + pd.Timedelta(hours=21)).tz_localize("UTC")
           for x in d]
    return pd.Series(pd.to_datetime(out, utc=True), index=report_date.index)


def daily_available(day: pd.Series) -> pd.Series:
    """A daily close is public the next BUSINESS day (FRED posts Friday's H.15 on Monday)."""
    d = pd.to_datetime(day, utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    return (d + pd.offsets.BDay(1) + pd.Timedelta(hours=23)).dt.tz_localize("UTC")


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

def _socrata(url: str, market: Mapping[str, Any], get: Callable[[str], Any],
             after: str | None = None) -> pd.DataFrame:
    """A market is EITHER an exact-name rename chain (`names`, preferred: a substring or LIKE can
    swallow a cross contract, which is how cot_tff/eur.parquet came to be one third EUR/JPY) or a
    `like` pattern whose every hit is reported."""
    names = [str(n).upper().replace("'", "''") for n in market.get("names") or []]
    if names:
        where = "upper(market_and_exchange_names) in (" + ",".join(f"'{n}'" for n in names) + ")"
    else:
        where = f"upper(market_and_exchange_names) like '{str(market['like']).upper()}'"
    if after:
        # Incremental: only weeks past the newest one already held.
        where += f" AND report_date_as_yyyy_mm_dd > '{after}'"
    q = urllib.parse.urlencode({"$where": where, "$order": "report_date_as_yyyy_mm_dd ASC",
                                "$limit": str(CFTC_LIMIT)})
    rows = get(f"{url}?{q}")
    return pd.DataFrame(rows or [])


def _read_rows(p: Path) -> pd.DataFrame:
    try:
        return pd.DataFrame(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return pd.DataFrame()


def _replace(tmp: Path, p: Path) -> None:
    """os.replace, with the Windows fallback: a destination another process holds open raises
    PermissionError there, so it is removed and the rename retried once."""
    try:
        os.replace(tmp, p)
    except PermissionError:
        p.unlink(missing_ok=True)
        os.replace(tmp, p)


def _atomic_json_rows(p: Path, df: pd.DataFrame) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    df.to_json(tmp, orient="records")
    _replace(tmp, p)


def _atomic_parquet(p: Path, df: pd.DataFrame, *, index: bool = True) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    df.to_parquet(tmp, index=index)
    _replace(tmp, p)


def _cftc_due(last: str | None, calendar: Mapping[str, Any] | None,
              now: datetime | None) -> bool:
    """Fetch only when the report after the newest held one has been released: weekly data is
    asked for once a week, never every hour."""
    if not last:
        return True
    nxt = pd.Timestamp(last) + pd.Timedelta(days=7)
    out = (cftc_release_day(nxt, calendar) + pd.Timedelta(hours=21)).tz_localize("UTC")
    return bool(pd.Timestamp(now or datetime.now(UTC)) >= out)


def cftc_market(market: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]],
                get: Callable[[str], Any], state: dict[str, Any],
                calendar: Mapping[str, Any] | None = None, now: datetime | None = None,
                budget: float | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
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
            held = _read_rows(raw_path)
            last = (str(held["report_date_as_yyyy_mm_dd"].max())[:10]
                    if "report_date_as_yyyy_mm_dd" in held.columns and len(held) else None)
            df = held
            if not _cftc_due(last, calendar, now):
                info["sets"][sid] = "HELD (next release not out yet)"
            elif budget is not None and time.monotonic() > budget:
                info["sets"][sid] = "HELD (pass budget spent)"
            else:
                try:
                    new = _socrata(str(src["url"]), market, get,
                                   after=f"{last}T00:00:00.000" if last else None)
                    if len(new):
                        df = pd.concat([held, new], ignore_index=True)
                        _atomic_json_rows(raw_path, df)
                except HardStop as hs:
                    state.setdefault("hard_stops", {})[sid] = {"code": hs.code, "at": _now()}
                    info["sets"][sid] = f"HARD_STOP {hs.code}"
                    continue
                except Exception as exc:
                    info["sets"][sid] = f"ERROR {type(exc).__name__}"
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
            # Deterministic across a rename chain: the NEWEST declared name wins a shared week
            # (chains are listed oldest first), never whichever row the API returned last.
            order = [str(n).upper() for n in market.get("names") or []]
            rank = (df["market_and_exchange_names"].astype(str).str.upper().map(
                {n: i for i, n in enumerate(order)}).fillna(-1)
                if "market_and_exchange_names" in df.columns and order
                else pd.Series(0, index=df.index))
            df = (df.assign(_rank=rank.to_numpy())
                  .sort_values(["report_date_as_yyyy_mm_dd", "_rank"], kind="stable")
                  .drop_duplicates("report_date_as_yyyy_mm_dd", keep="last")
                  .drop(columns="_rank"))
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
    reaction  each central bank's distance from a Taylor rule (`reaction_residual`), monthly.
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
    elif mode == "reaction":
        for bk in cv.get("banks") or []:
            if bk.get("rate") not in yc.columns or bk.get("inflation") not in yc.columns:
                continue
            u = yc[bk["unemployment"]] if bk.get("unemployment") in yc.columns else None
            f = reaction_residual(yc[bk["rate"]], yc[bk["inflation"]], u,
                                  target=float(bk.get("target", 2.0)))
            if len(f) < MIN_ROWS:
                continue
            out.append((f"fred_{cv['id']}_{str(bk['id']).lower()}",
                        dynamics(f, list(f.columns), window=int(cv.get("window", 60))),
                        pd.DatetimeIndex(f.index), list(bk.get("targets") or []),
                        "fred_cb_reaction"))
    return out


#: Months of history the neutral real rate and the unemployment norm are averaged over, and the
#: fewest months each needs. Both averages stop the month BEFORE the one they are used in.
RSTAR_MONTHS, RSTAR_MIN = 120, 36
UNORM_MONTHS, UNORM_MIN = 60, 24


def reaction_residual(rate: pd.Series, price_index: pd.Series,
                      unemployment: pd.Series | None = None, *, target: float = 2.0
                      ) -> pd.DataFrame:
    """A central bank's distance from a Taylor (1993) rule, monthly, strictly causal.

        inflation  12-month % change of the price index
        r*         the bank's own average real policy rate over the prior RSTAR_MONTHS
        gap        -2 * (unemployment - its prior UNORM_MONTHS average)   (Okun; 0 when absent)
        rule       r* + inflation + 0.5 * (inflation - target) + 0.5 * gap
        resid      policy rate - rule: above zero the bank is TIGHTER than its own rule implies,
                   below zero it is behind it

    The coefficients are Taylor's, fixed, so nothing is fitted and nothing can be fitted to the
    future. The residual is a QUESTION for the gauntlet (does a bank far behind its rule see
    its currency weaken, or catch up?), not a forecast. Indexed by the month's first day; the
    caller stamps availability after that month's releases.
    """
    r = pd.to_numeric(rate, errors="coerce").dropna().resample("MS").mean()
    px = pd.to_numeric(price_index, errors="coerce").dropna().resample("MS").last()
    infl = 100.0 * (px / px.shift(12) - 1.0)
    f = pd.DataFrame({"rate": r, "infl": infl}).dropna()
    real = f["rate"] - f["infl"]
    rstar = real.rolling(RSTAR_MONTHS, min_periods=RSTAR_MIN).mean().shift(1)
    gap = pd.Series(0.0, index=f.index)
    if unemployment is not None:
        u = pd.to_numeric(unemployment, errors="coerce").dropna().resample("MS").last()
        norm = u.rolling(UNORM_MONTHS, min_periods=UNORM_MIN).mean().shift(1)
        gap = (-2.0 * (u - norm)).reindex(f.index)
    rule = rstar + f["infl"] + 0.5 * (f["infl"] - target) + 0.5 * gap
    out = pd.DataFrame({"resid": f["rate"] - rule, "real_rate": real,
                        "infl_gap": f["infl"] - target}, index=f.index)
    return out.dropna(subset=["resid"])


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


# ------------------------------------------------------------- scheduled-release first prints

#: ALFRED's "initial release only" view: one row per observation period, stamped with the day it
#: was FIRST published (realtime_start). That is the number a trader saw at the release, never a
#: later revision, which is what makes a jobs or CPI print usable on the bar clock at all.
ALFRED_INITIAL = "4"
#: Releases come out at a fixed wall-clock time in New York; the bar may use the print only after
#: it. The default is 08:30, the slot of payrolls, CPI, claims, retail sales and PCE.
RELEASE_TZ = "America/New_York"
RELEASE_GRACE = pd.Timedelta(minutes=5)
#: Prior first-print changes a shock is scored against. Strictly earlier releases only.
SHOCK_WINDOW = 36


def alfred_first_prints(series: str, key: str, get: Callable[[str], Any],
                        weekdays: Sequence[int] | None = None,
                        counts: dict[str, int] | None = None) -> pd.DataFrame:
    """[period, released, value]: each period's FIRST published value and the day it came out.

    A realtime_start shared by several periods is an archive bulk-load (ALFRED's vintages begin
    where its archive begins), not a release, so those rows are dropped: stamping thirty years of
    payrolls with the archive's first day would put them all on one fictitious date.

    realtime_start is the day ALFRED recorded the value, which can trail the real release by a day
    (late stamping is safe). It must never fall on a day the series cannot be released: a weekend,
    or outside `weekdays` when the series has a fixed schedule (payrolls on Friday, claims on
    Thursday, each with the holiday-shifted day before). Such rows are dropped and counted.
    """
    q = urllib.parse.urlencode({"series_id": series, "api_key": key, "file_type": "json",
                                "realtime_start": "1776-07-04", "realtime_end": "9999-12-31",
                                "output_type": ALFRED_INITIAL})
    doc = get(f"https://api.stlouisfed.org/fred/series/observations?{q}") or {}
    rows = doc.get("observations") or []
    tally = counts if counts is not None else {}
    if not rows:
        return pd.DataFrame(columns=["period", "released", "value"])
    d = pd.DataFrame(rows)
    out = pd.DataFrame({
        "period": pd.to_datetime(d.get("date"), errors="coerce"),
        "released": pd.to_datetime(d.get("realtime_start"), errors="coerce"),
        "value": pd.to_numeric(d.get("value"), errors="coerce"),
    }).dropna()
    bulk = out["released"].map(out["released"].value_counts()) > 1
    tally["dropped_bulk_load"] = int(bulk.sum())
    out = out[~bulk].sort_values("period").drop_duplicates("period", keep="first")
    # a first print released before its own period ended is impossible; one released before
    # the previous period's print is an archive artefact -- either would reorder history
    n0 = len(out)
    out = out[out["released"] >= out["period"]]
    out = out[out["released"].cummax() == out["released"]]
    tally["dropped_out_of_order"] = n0 - len(out)
    allowed = set(weekdays) if weekdays else {0, 1, 2, 3, 4}
    ok = out["released"].dt.weekday.isin(allowed)
    tally["dropped_off_schedule"] = int((~ok).sum())
    return out[ok].reset_index(drop=True)


def release_shock(prints: pd.DataFrame, transform: str = "diff",
                  window: int = SHOCK_WINDOW) -> pd.DataFrame:
    """Per release: the first-print change and how unusual it was against EARLIER releases.

    `first_chg` compares this period's first print with the PREVIOUS period's first print, both
    as published at the time; across a missing period it is NaN, never a two-period change scored
    as one. `shock_z` scores it against the trailing `window` releases, shifted so a release
    never sees itself. This is a shock against the series' own history, not against a consensus
    forecast: the free calendar's consensus exists only forward from when the desk began
    capturing it, and is joined separately where it does.

    Two columns only, on purpose: every column mints cells and every cell is charged to the
    program's family-wise budget, so near-duplicates (|z|, a rank of the same change) are not
    added. `first_chg` is a change and so is asked only as level_z by the cell plan.
    """
    v = prints["value"].astype(float).reset_index(drop=True)
    per = pd.to_datetime(prints["period"]).reset_index(drop=True)
    if transform == "logdiff":
        chg = np.log(v.where(v > 0)).diff() * 100.0
    else:
        chg = v.diff()
    step = per.diff()
    typical = step.median() if step.notna().any() else pd.NaT
    if pd.notna(typical):
        chg = chg.where(step <= typical * 1.5)
    past = chg.shift(1)
    mu = past.rolling(window, min_periods=MIN_ROWS // 2).mean()
    sd = past.rolling(window, min_periods=MIN_ROWS // 2).std(ddof=0)
    return pd.DataFrame({"first_chg": chg.to_numpy(),
                         "shock_z": ((chg - mu) / sd.replace(0.0, np.nan)).to_numpy()})


def release_available(released: pd.Series, at: str = "08:30") -> pd.Series:
    """The UTC instant a release became public: its New York release time plus a short grace."""
    hh, mm = (int(x) for x in str(at).split(":"))
    local = (pd.to_datetime(released).dt.normalize()
             + pd.Timedelta(hours=hh, minutes=mm)).dt.tz_localize(
        RELEASE_TZ, nonexistent="shift_forward", ambiguous=False)
    return local.dt.tz_convert("UTC") + RELEASE_GRACE


#: Scheduled-release instants recovered from the first prints, for the event families. Kept OUT
#: of `data/intelligence/`: the candidate compiler reads every row there as a donation and would
#: mint a cell per historical release.
CALENDAR_BACKFILL = DESK / "data" / "calendar_backfill"


def write_release_calendar(oid: str, rel: Mapping[str, Any], prints: pd.DataFrame) -> Path | None:
    """One JSON-lines file of this series' release instants (UTC), newest state replacing old.

    The instant is the New York release time on the day ALFRED first recorded the value, with no
    grace added: it is the event, not when a bar may use the number. `instant_basis` says so,
    because ALFRED can record a release a day late for a series it loads late.
    """
    if prints.empty:
        return None
    hh, mm = (int(x) for x in str(rel.get("at") or "08:30").split(":"))
    when = (pd.to_datetime(prints["released"]).dt.normalize()
            + pd.Timedelta(hours=hh, minutes=mm)).dt.tz_localize(
        RELEASE_TZ, nonexistent="shift_forward", ambiguous=False).dt.tz_convert("UTC")
    lines = [json.dumps({"event_date": t.isoformat(), "currency": "USD", "country": "USD",
                         "title": str(rel.get("title") or rel["series"]), "impact": "High",
                         "series": str(rel["series"]), "source": "alfred_first_release",
                         "instant_basis": "alfred_realtime_start", "backfill": True},
                        sort_keys=True) for t in when]
    CALENDAR_BACKFILL.mkdir(parents=True, exist_ok=True)
    p = CALENDAR_BACKFILL / f"backfill_{oid}.jsonl.gz"
    tmp = p.with_suffix(p.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    _replace(tmp, p)
    return p


def first_release_outputs(cv: Mapping[str, Any], key: str, get: Callable[[str], Any] | None,
                          raw_dir: Path, notes: list[dict[str, Any]]
                          ) -> list[tuple[str, pd.DataFrame, dict[str, Any]]]:
    """Each configured release -> one stamped frame, keyed on its release instant."""
    out: list[tuple[str, pd.DataFrame, dict[str, Any]]] = []
    for rel in cv.get("releases") or []:
        ser = str(rel["series"])
        oid = f"fred_{cv['id']}_{ser.lower()}"
        raw = raw_dir / f"{oid}.parquet"
        prints = pd.DataFrame()
        counts: dict[str, int] = {}
        if get is not None and key:
            try:
                prints = alfred_first_prints(ser, key, get, rel.get("weekdays"), counts)
                if not prints.empty:
                    _atomic_parquet(raw, prints, index=False)
            except HardStop:
                raise
            except Exception as exc:
                notes.append({"source": oid, "error": f"{type(exc).__name__}"})
        if prints.empty and raw.exists():
            prints = pd.read_parquet(raw)
        if len(prints) < MIN_ROWS:
            continue
        try:
            write_release_calendar(oid, rel, prints)
        except OSError as exc:
            notes.append({"source": oid, "calendar_backfill": f"{type(exc).__name__}"})
        feat = release_shock(prints, str(rel.get("transform") or "diff"),
                             int(cv.get("window", SHOCK_WINDOW)))
        at = release_available(prints["released"], str(rel.get("at") or "08:30"))
        frame = stamped(feat, at, oid, pd.to_datetime(prints["released"], utc=True))
        out.append((oid, frame, {"targets": list(rel.get("targets") or cv.get("targets") or []),
                                 "kind": "release_first_print", "rows": len(frame),
                                 "last_event": str(prints["released"].max()),
                                 "why": str(rel.get("why") or ""), "dropped": counts}))
    return out


# ----------------------------------------------------------------------- Japan MoF intervention

#: MoF publishes intervention two ways. The historical CSV holds every intervention DAY since
#: April 1991 with its amount and direction, but a quarter's days are disclosed only after the
#: quarter ends (the CSV read 2026-10-29 ended at June 2026). The monthly release gives the
#: period's TOTAL, undirected, at the month's last business day. The intervention date is never
#: the availability time: a day is stamped when its quarter was disclosed, a monthly total when
#: its page was published.
MOF_QUARTER_LAG_DAYS = 62     # quarter end -> disclosure; the Q2 2026 rows were not out at +29
MOF_PAGES_PER_PASS = 12       # monthly pages are immutable and cached; a few per pass is polite
_MOF_MON = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                                        "Sep", "Oct", "Nov", "Dec"), start=1)}


def fetch_text(url: str, timeout: float = 40.0) -> str:
    """One honest GET of a page or file. Same rules as `fetch_json`: no retry, hard stop.
    The body is decoded by the polite fetcher (header charset, then the page's own meta)."""
    return _polite(url, "text/html,text/csv,*/*;q=0.8", timeout)


def robots_allow(url: str, get_text: Callable[[str], str]) -> bool:
    """robots.txt for the URL's host, read with our own UA. A missing file (404) allows, as the
    standard says; any other failure to read it does NOT allow, so an unread policy is never
    treated as a yes."""
    import urllib.robotparser
    p = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(get_text(f"{p.scheme}://{p.netloc}/robots.txt").splitlines())
    except (urllib.error.HTTPError, FetchError) as exc:
        return getattr(exc, "code", None) == 404
    return rp.can_fetch(UA, url)


def mof_sign(pair: str) -> float:
    """+1 when the yen was BOUGHT (support), -1 when sold, 0 for an operation not against yen."""
    p = pair.lower()
    if "japanese yen (bought)" in p:
        return 1.0
    if "japanese yen (sold)" in p:
        return -1.0
    return 0.0


def mof_days(text: str) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    """The historical CSV -> one row per intervention day (amount in 100 million yen, signed by
    direction) and the list of quarters it covers, read from its own quarter-total rows so a
    quarter with no intervention is a measured zero, never a missing row."""
    import csv
    import io
    days, quarters, year = [], [], None
    for row in csv.reader(io.StringIO(text)):
        row = [c.strip() for c in row] + [""] * 9
        if row[3] and " - " in row[3] and not row[4]:
            try:
                q_end = pd.Timestamp(row[3].split(" - ")[1].strip()) + pd.offsets.MonthEnd(0)
            except ValueError:
                continue
            quarters.append(q_end)
            continue
        if row[3].isdigit():
            year = int(row[3])
        if year is None or row[4] not in _MOF_MON or not row[5].isdigit():
            continue
        try:
            amt = float(row[6].replace(",", ""))
        except ValueError:
            continue
        days.append({"day": pd.Timestamp(year, _MOF_MON[row[4]], int(row[5])),
                     "amount": amt, "sign": mof_sign(row[8])})
    return pd.DataFrame(days, columns=["day", "amount", "sign"]), sorted(set(quarters))


def mof_quarterly(days: pd.DataFrame, quarters: Sequence[pd.Timestamp]) -> pd.DataFrame:
    """Per disclosed quarter: signed net, gross, days, trailing-year net, quarters since the
    last intervention. Indexed by quarter end."""
    idx = pd.DatetimeIndex(sorted(quarters))
    if days.empty or not len(idx):
        return pd.DataFrame()
    d = days.assign(q=days["day"] + pd.offsets.QuarterEnd(0),
                    net=days["amount"] * days["sign"])
    g = d.groupby("q")
    out = pd.DataFrame({"mof_q_net": g["net"].sum(), "mof_q_gross": g["amount"].sum(),
                        "mof_q_days": g.size()}).reindex(idx).fillna(0.0)
    out["mof_net_4q"] = out["mof_q_net"].rolling(4, min_periods=1).sum()
    active = out["mof_q_gross"] > 0
    out["mof_q_since_last"] = (~active).groupby(active.cumsum()).cumsum().astype(float)
    return out


_MOF_PERIOD = r"through\s+([A-Z][a-z]+\.?\s+\d{1,2},\s+\d{4})"
_MOF_AMOUNT = r"[¥￥]\s*([\d,]+(?:\.\d+)?)\s*(trillion|billion|million)?"


def mof_monthly_page(html: str) -> tuple[pd.Timestamp, float] | None:
    """A monthly release -> (period end, total in 100 million yen). None when unparseable."""
    import re
    txt = re.sub(r"<[^>]+>", " ", html).replace("　", " ").replace("&nbsp;", " ")
    pe, am = re.search(_MOF_PERIOD, txt), re.search(_MOF_AMOUNT, txt)
    if not pe or not am:
        return None
    scale = {"trillion": 1e4, "billion": 10.0, "million": 0.01, None: 1e-8}[am.group(2)]
    try:
        amount = float(am.group(1).replace(",", "")) * scale
        return pd.Timestamp(pe.group(1).replace(".", "")), amount
    except ValueError:
        return None


def mof_monthly(pages: Mapping[str, Mapping[str, Any]], days: pd.DataFrame,
                quarters: Sequence[pd.Timestamp]) -> pd.DataFrame:
    """Monthly gross intervention as it was known. A month with a fetched release is stamped at
    its publication; a month before the first release this organ can read comes from the CSV,
    stamped when its quarter was disclosed. Columns: event_time, available, mof_m_gross,
    mof_m_since_last."""
    rows = [{"event_time": pd.Timestamp(v["period_end"]), "mof_m_gross": float(v["total"]),
             "available": pd.Timestamp(k, tz="UTC").normalize() + pd.Timedelta(hours=23)}
            for k, v in pages.items()]
    first = min((r["event_time"] for r in rows), default=None)
    if not days.empty and quarters:
        months = pd.date_range(pd.Timestamp(min(quarters)) - pd.offsets.MonthEnd(2),
                               max(quarters), freq="ME")
        g = (days.assign(m=days["day"] + pd.offsets.MonthEnd(0)).groupby("m")["amount"].sum()
             .reindex(months).fillna(0.0))
        for m, v in g.items():
            if first is not None and m >= first:
                break
            q_end = m + pd.offsets.QuarterEnd(0)
            rows.append({"event_time": m, "mof_m_gross": float(v),
                         "available": pd.Timestamp(q_end, tz="UTC").normalize()
                         + pd.Timedelta(days=MOF_QUARTER_LAG_DAYS, hours=23)})
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values("event_time").drop_duplicates("event_time", keep="first")
    active = out["mof_m_gross"] > 0
    out["mof_m_since_last"] = (~active).groupby(active.cumsum()).cumsum().astype(float)
    return out.reset_index(drop=True)


def mof_collect(src: Mapping[str, Any], get_text: Callable[[str], str] | None,
                state: dict[str, Any], notes: list[dict[str, Any]]
                ) -> tuple[pd.DataFrame, list[pd.Timestamp], dict[str, Any]]:
    """Fetch (when allowed) and cache the CSV and new monthly pages; return what is held."""
    import re
    sid = str(src["id"])
    csv_path, pages_path = RAW / "mof_intervention.csv", RAW / "mof_monthly_pages.json"
    pages: dict[str, Any] = _read(pages_path, {}) or {}
    if get_text is not None and src.get("terms") == "OPEN" and \
            sid not in state.get("hard_stops", {}):
        try:
            if not robots_allow(str(src["csv_url"]), get_text):
                notes.append({"source": sid, "status": "UNMEASURED", "why": "robots disallows"})
            else:
                text = get_text(str(src["csv_url"]))
                if mof_days(text)[1]:
                    csv_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = csv_path.with_suffix(".csv.tmp")
                    tmp.write_text(text, encoding="utf-8")
                    _replace(tmp, csv_path)
                index = get_text(str(src["monthly_index_url"]))
                base = str(src["monthly_index_url"]).rsplit("/", 1)[0]
                links = sorted(set(re.findall(r"monthly/(\d{8}e?)\.html", index)) |
                               set(re.findall(r'href="(\d{8}e?)\.html"', index)))
                todo = [ln for ln in links if ln[:8] not in pages][-MOF_PAGES_PER_PASS:]
                for ln in todo:
                    got = mof_monthly_page(get_text(f"{base}/{ln}.html"))
                    if got is None:
                        notes.append({"source": sid, "page": ln, "status": "UNPARSED"})
                        continue
                    pages[ln[:8]] = {"period_end": str(got[0].date()), "total": got[1]}
                _write(pages_path, pages)
        except HardStop as hs:
            state.setdefault("hard_stops", {})[sid] = {"code": hs.code, "at": _now()}
        except Exception as exc:
            notes.append({"source": sid, "error": f"{type(exc).__name__}"})
    text = csv_path.read_text(encoding="utf-8") if csv_path.exists() else ""
    days, quarters = mof_days(text) if text else (pd.DataFrame(), [])
    return days, quarters, pages


# ----------------------------------------------------------------------------- build

def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _universe() -> frozenset[str]:
    doc = _read(UNIVERSE, {}) or {}
    return frozenset(str(k) for k in doc) if isinstance(doc, dict) else frozenset()


def _write_series(sid: str, frame: pd.DataFrame) -> Path:
    p = SERIES / f"{sid}.parquet"
    _atomic_parquet(p, frame, index=False)
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


# --------------------------------------------------------------- BIS policy rates and prices

#: A reply this close to the polite fetcher's 2 MB cap may have been cut, and a cut reply loses
#: its NEWEST rows: it is refused rather than stored.
BIS_MAX_CHARS = 1_900_000
#: BIS refreshes these monthly tables every few days; one read a day is plenty.
BIS_REFETCH_H = 20


def parse_bis_csv(text: str, unit: str | None = None) -> pd.DataFrame:
    """BIS SDMX CSV -> one column per REF_AREA, indexed by period (a month is its first day).

    Columns are read by NAME (FREQ, REF_AREA, TIME_PERIOD, OBS_VALUE, and UNIT_MEASURE when
    `unit` filters on it), because the policy-rate table carries long quoted notes with commas.
    Anything else, a page of HTML included, parses to nothing."""
    import csv
    import io
    cols: dict[str, dict[pd.Timestamp, float]] = {}
    try:
        rows = csv.DictReader(io.StringIO(text))
        if not {"REF_AREA", "TIME_PERIOD", "OBS_VALUE"} <= set(rows.fieldnames or []):
            return pd.DataFrame()
        for r in rows:
            if unit is not None and str(r.get("UNIT_MEASURE")) != unit:
                continue
            t = pd.to_datetime(str(r.get("TIME_PERIOD")), utc=True, errors="coerce")
            v = pd.to_numeric(r.get("OBS_VALUE"), errors="coerce")
            if pd.notna(t) and pd.notna(v):
                cols.setdefault(str(r["REF_AREA"]), {})[t] = float(v)
    except csv.Error:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index()


def drop_carried_tail(df: pd.DataFrame) -> pd.DataFrame:
    """Blank a series' LAST value when it repeats the one before it exactly. A price index
    printing the same six decimals two months running is the publisher carrying the old value
    forward until the real one arrives (seen for Japan, 2026-09, on the box read of
    2026-11-11); the month is re-read on a later pass. Earlier repeats are left alone."""
    out = df.copy()
    for c in out.columns:
        v = out[c].dropna()
        if len(v) >= 2 and v.iloc[-1] == v.iloc[-2]:
            out.loc[v.index[-1], c] = np.nan
    return out


def bis_collect(src: Mapping[str, Any], get_text: Callable[[str], str] | None,
                state: dict[str, Any], notes: list[dict[str, Any]],
                now: datetime | None = None) -> pd.DataFrame:
    """Monthly policy rates (WS_CBPOL) and consumer price indices (WS_LONG_CPI, unit 628) for
    the row's areas -> columns BIS_CBPOL_<area> and BIS_CPI_<area>.

    One request per area for rates (each row repeats a long note, so areas are never batched)
    and one for all the price indices. The first read asks for history from `history_start`,
    later reads for the last two years, and what is held is kept under what is newly read.
    Fetches at most every BIS_REFETCH_H hours, and only what the host's robots.txt allows;
    offline, stopped or disallowed, it returns what is held."""
    sid = str(src.get("id") or "bis_stats")
    now = now or datetime.now(UTC)
    paths = {"CBPOL": RAW / "bis_cbpol.parquet", "CPI": RAW / "bis_cpi.parquet"}
    held = {k: (pd.read_parquet(p) if p.exists() else pd.DataFrame()) for k, p in paths.items()}
    areas = [str(a) for a in src.get("areas") or []]
    last = pd.to_datetime(state.get("bis_last_fetch"), utc=True, errors="coerce")
    due = pd.isna(last) or (pd.Timestamp(now) - last) >= pd.Timedelta(hours=BIS_REFETCH_H)
    if get_text is not None and src.get("terms") == "OPEN" and areas and due and \
            sid not in state.get("hard_stops", {}):
        def start(key: str) -> str:
            return (str(src.get("history_start", "2000-01")) if held[key].empty
                    else f"{now.year - 2}-{now.month:02d}")
        try:
            got: dict[str, list[pd.DataFrame]] = {"CBPOL": [], "CPI": []}
            jobs: list[tuple[str, str, str | None]] = [
                ("CBPOL", str(src["rate_url"]).format(area=a, start=start("CBPOL")), None)
                for a in areas]
            jobs.append(("CPI", str(src["cpi_url"]).format(areas="+".join(areas),
                                                           start=start("CPI")), "628"))
            # Open terms are not a robots yes: the host's robots.txt is read once per pass and
            # every URL is asked of it before the first data request.
            seen: dict[str, str | Exception] = {}

            def robots_text(u: str) -> str:
                if u not in seen:
                    try:
                        seen[u] = get_text(u)
                    except (urllib.error.HTTPError, FetchError) as exc:
                        seen[u] = exc
                got_ = seen[u]
                if isinstance(got_, Exception):
                    raise got_
                return got_

            if not all(robots_allow(url, robots_text) for _k, url, _u in jobs):
                notes.append({"source": sid, "status": "UNMEASURED", "why": "robots disallows"})
                jobs = []
            for key, url, unit in jobs:
                text = get_text(url)
                if len(text) >= BIS_MAX_CHARS:
                    notes.append({"source": sid, "status": "TRUNCATED", "table": key})
                    continue
                df = parse_bis_csv(text, unit)
                if df.empty:
                    notes.append({"source": sid, "status": "UNPARSED", "table": key})
                    continue
                got[key].append(df)
            for key, parts in got.items():
                if parts:
                    new = pd.concat(parts, axis=1)
                    new = new.loc[:, ~new.columns.duplicated()]
                    held[key] = new.combine_first(held[key]).sort_index()
                    _atomic_parquet(paths[key], held[key])
            state["bis_last_fetch"] = now.isoformat(timespec="seconds")
        except HardStop as hs:
            state.setdefault("hard_stops", {})[sid] = {"code": hs.code, "at": _now()}
        except Exception as exc:
            notes.append({"source": sid, "error": f"{type(exc).__name__}"})
    out = [held["CBPOL"].add_prefix("BIS_CBPOL_"),
           drop_carried_tail(held["CPI"]).add_prefix("BIS_CPI_")]
    out = [f for f in out if not f.empty]
    return pd.concat(out, axis=1).sort_index() if out else pd.DataFrame()


def build_market_series(registry: Mapping[str, Any], *, get: Callable[[str], Any] | None,
                        state: dict[str, Any], bars: Callable[[str], pd.DataFrame | None],
                        get_text: Callable[[str], str] | None = None,
                        now: datetime | None = None, budget: float | None = None
                        ) -> tuple[dict[str, dict[str, Any]], dict[str, pd.DataFrame],
                                    list[dict[str, Any]]]:
    """Every OPEN source -> stamped feature frames. `get=None` means offline (held raw only)."""
    sources = {str(s["id"]): s for s in registry.get("sources") or []}
    built: dict[str, dict[str, Any]] = {}
    frames: dict[str, pd.DataFrame] = {}
    notes: list[dict[str, Any]] = []
    offline_get = _offline_get
    calendar = registry.get("cftc_release_calendar") or {}

    for m in registry.get("cftc_markets") or []:
        pos, info = cftc_market(m, sources, get or offline_get, state, calendar, now, budget)
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
        frames[sid] = stamped(feat.reset_index(drop=True),
                              cftc_available(pd.Series(pos.index), calendar),
                              sid, pd.Series(pos.index))
        built[sid] = {"targets": list(m.get("targets") or []), "kind": "cftc",
                      "rows": len(pos), "last_event": str(pos.index.max())}

    eia = sources.get("eia_futures") or {}
    key = next((os.environ.get(k) for k in eia.get("key_env") or [] if os.environ.get(k)), "")
    if eia.get("terms") != "OPEN":
        notes.append({"source": "eia_futures", "status": "UNMEASURED",
                      "why": str(eia.get("terms")), "note": eia.get("note", "")})
    for cv in (registry.get("eia_curves") or []) if eia.get("terms") == "OPEN" else []:
        sid = f"eia_{cv['id']}"
        raw_path = RAW / f"{sid}.parquet"
        px = pd.DataFrame()
        if get is not None and eia.get("terms") == "OPEN" and key and \
                "eia_futures" not in state.get("hard_stops", {}):
            try:
                px = eia_curve(cv, key, get)
                if not px.empty:
                    _atomic_parquet(raw_path, px)
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
    bis: pd.DataFrame | None = None
    for cv in [*(registry.get("fred_curves") or []), *(registry.get("fred_sets") or [])]:
        if cv.get("mode") == "first_release":
            live = (get if fred.get("terms") == "OPEN" and
                    "fred_rates" not in state.get("hard_stops", {}) else None)
            if not fkey:
                notes.append({"source": f"fred_{cv['id']}", "status": "NEEDS_KEY",
                              "key_env": fred.get("key_env")})
            try:
                for oid, frame, meta in first_release_outputs(cv, fkey, live, RAW, notes):
                    frames[oid] = frame
                    built[oid] = meta
            except HardStop as hs:
                state.setdefault("hard_stops", {})["fred_rates"] = {"code": hs.code, "at": _now()}
            continue
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
                    _atomic_parquet(raw_path, yc)
            except HardStop as hs:
                state.setdefault("hard_stops", {})["fred_rates"] = {"code": hs.code, "at": _now()}
            except Exception as exc:
                notes.append({"source": sid, "error": f"{type(exc).__name__}"})
        elif not fkey:
            notes.append({"source": sid, "status": "NEEDS_KEY", "key_env": fred.get("key_env")})
        if yc.empty and raw_path.exists():
            yc = pd.read_parquet(raw_path)
        yc = yc[[c for c in cv["series"] if c in yc.columns]].dropna(how="all") if len(yc) else yc
        if cv.get("bis"):
            # This set's rates and prices come from the BIS; FRED adds unemployment where held.
            if bis is None:
                bis = bis_collect(sources.get("bis_stats") or {}, get_text, state, notes, now)
            if not bis.empty:
                yc = bis.join(yc, how="outer") if len(yc) else bis
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

    mof = sources.get("mof_japan_intervention") or {}
    if mof.get("adapter") == "mof_feio":
        days, quarters, pages = mof_collect(mof, get_text, state, notes)
        targets = list(mof.get("targets") or [])
        q = mof_quarterly(days, quarters)
        if len(q) >= MIN_ROWS:
            feat = dynamics(q, ["mof_q_net", "mof_net_4q"], window=40)
            feat[["mof_q_gross", "mof_q_days", "mof_q_since_last"]] = \
                q[["mof_q_gross", "mof_q_days", "mof_q_since_last"]]
            at = (pd.to_datetime(pd.Series(q.index), utc=True).dt.normalize()
                  + pd.Timedelta(days=MOF_QUARTER_LAG_DAYS, hours=23))
            frames["mof_jpy_q"] = stamped(feat.reset_index(drop=True), at, "mof_jpy_q",
                                          pd.Series(q.index))
            built["mof_jpy_q"] = {"targets": targets, "kind": "mof_intervention_quarterly",
                                  "rows": len(q), "last_event": str(q.index.max())}
        mm = mof_monthly(pages, days, quarters)
        if len(mm) >= MIN_ROWS:
            feat = dynamics(mm[["mof_m_gross"]], ["mof_m_gross"], window=60)
            feat["mof_m_since_last"] = mm["mof_m_since_last"]
            frames["mof_jpy_m"] = stamped(feat, mm["available"], "mof_jpy_m", mm["event_time"])
            built["mof_jpy_m"] = {"targets": targets, "kind": "mof_intervention_monthly",
                                  "rows": len(mm), "release_pages": len(pages),
                                  "last_event": str(mm["event_time"].max())}
        if "mof_jpy_q" not in built:
            notes.append({"source": "mof_japan_intervention", "status": "UNMEASURED",
                          "why": "no historical CSV held yet"})

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
             "roll_yield", "curvature", "shock_z", "mof_q_net", "mof_net_4q", "mof_m_gross", "x")
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


#: Wall-clock budget for one pass's network reads; past it every source serves what it holds.
#: The leg is killed at its planned 720s, and the series writes, the mint and the report come
#: after the reads: at 600s the only pass in the ledger was killed at 778s with no report written
#: (2026-11-05). 420s leaves the rest of the pass room to finish.
FETCH_BUDGET_S = 420.0


def stale_series(built: Mapping[str, Any], frames: Mapping[str, pd.DataFrame],
                 registry: Mapping[str, Any], now: datetime) -> dict[str, str]:
    """A series whose newest row is far older than its own cadence is STALE: the conditioner
    would carry its last value forward for ever. Stale means silent past 3x the series' median
    publication gap and at least 30 days. A transmission with a stale leg is stale too."""
    out: dict[str, str] = {}
    t = pd.Timestamp(now)
    for sid in built:
        at = pd.to_datetime(frames[sid]["available_time"], utc=True).sort_values()
        gap = at.diff().median()
        bound = max(pd.Timedelta(days=30), 3 * gap if pd.notna(gap) else pd.Timedelta(days=30))
        if len(at) and t - at.iloc[-1] > bound:
            out[sid] = f"last published {at.iloc[-1].date()}, silent beyond {bound.days}d"
    for tr in registry.get("transmissions") or []:
        sid = f"xfer_{tr['id']}"
        legs = [str(tr["a"]), str(tr["b"])]
        if sid in built and any(leg in out for leg in legs):
            out[sid] = "a leg is stale: " + ", ".join(leg for leg in legs if leg in out)
    return out


def build(*, dry_run: bool = False, offline: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    registry = _read(REGISTRY, {}) or {}
    state = _read(STATE, {}) or {}
    try:
        from research.proposer_common import bars
    except Exception:
        def bars(sym: str) -> pd.DataFrame | None:
            return None
    now = datetime.now(UTC)
    built, frames, notes = build_market_series(
        registry, get=None if offline else fetch_json, state=state, bars=bars,
        get_text=None if offline else fetch_text, now=now,
        budget=time.monotonic() + FETCH_BUDGET_S)
    for sid, why in stale_series(built, frames, registry, now).items():
        built.pop(sid, None)
        frames.pop(sid, None)
        notes.append({"series": sid, "status": "UNMEASURED", "why": f"STALE: {why}"})
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
        "rule": ("Every futures, commodity and FX state series reaches cells or is named "
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
