"""THE MACRO STATE ENGINE: one state block per country/region, and edge CHANGES as hunted objects.

WHY THIS EXISTS (Tier-1 row W7, measured gap). The desk already describes the world twice, and
both descriptions stop one step short of what the row asks for:

  `libs/portfolio/macro_state.py` collapses the FRED archive into five point-in-time states --
  dollar, risk, rates, real_rates, curve, liquidity -- and every one of them is a state OF THE
  UNITED STATES. A book that trades GER40, JPN225, AUDUSD and UKGILT was being solved in a
  single country's regime, and nothing in the artifact said so: `rates` reads DGS10 whether the
  sleeve is a Bund or a gilt.

  `research/world_causal_graph.py` discovers a cross-asset graph and publishes EDGES -- src, dst,
  lag, strength, an admission verdict. An edge is a STATE of the world, not an event, and the
  graph republishes it each pass with a fresh strength. Nothing anywhere published the DERIVATIVE:
  the moment a link turned on, flipped sign or died. That moment is the tradable object -- a
  regime break is where the desk's priors are wrong and everyone else's are too -- and it was
  being averaged away inside a rolling correlation that only ever reported its level.

So this organ does exactly two things neither of those does, and rewrites neither of them:

  (1) COUNTRY / REGION STATE BLOCKS. The same six named states, computed per region from the PIT
      series this desk actually holds: the FRED archive (US), and the universe bars for that
      region's index, rates and FX proxies. A state the data cannot support is UNMEASURED WITH A
      REASON, never a substituted global number -- a Japanese liquidity state quietly reading
      WALCL would be worse than a gap, because nobody downstream could tell.

      THE BLOCK SET IS DERIVED, NOT LISTED. Every instrument the broker's own registry classifies
      (`data/universe/universe.json`, the same file `research/universe_policy` routes lanes with)
      is walked, and a block exists only where classified instruments landed in it. The seed maps
      below are the ONLY hand-written part: a currency code -> region map and an index/bond
      ticker -> region map, both small, both documented. A new pair or a new index joins its
      block the day the registry carries it, with no edit here.

  (2) THE EDGE-CHANGE HUNTER. For every (x, y) pair the causal graph names, a rolling OLS beta of
      y_t on x_{t-lag} over two ADJACENT windows, a standardized difference between them, and a
      permutation p-value for the maximum such difference over the whole scan. A link that turned
      on, flipped sign, strengthened, weakened or died becomes a ROW with a timestamp, a pre/post
      statistic and a p-value. The strongest rows that map to a registered price-only family and
      pass the two-lane door are DONATED as hypotheses through `research.proposer_common.donate`.

POINT-IN-TIME BY CONSTRUCTION, AND IT IS THE WHOLE POINT. A change point DETECTED at time t uses
the window ending at t and the window before it -- never a window that extends past t. The naive
formulation (pre = [t-w, t), post = [t, t+w)) centres the break and is the reason so many
published break dates cannot be traded: at time t nobody has the post window. Here the detection
time IS the first bar at which the desk could have made the claim, `_rolling_ols` reads a
trailing window only, and `_pit_rank` ranks each print among the prints that preceded it.
`test_macro_state_engine.py::test_changepoint_scores_are_point_in_time` proves it by truncating
the series at t and asserting the score at t is unchanged.

NOTHING HERE SIZES, CAPS, VETOES OR SHRINKS ANYTHING. It measures and it donates hypotheses; the
gauntlet judges them and the allocator decides capital. The only bound is `--max-donations`,
which spends the shared family-wise trial budget deliberately rather than flooding it.

    python research/macro_state_engine.py --once --budget-s 600
    python research/macro_state_engine.py --dry-run          # measures, writes nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "macro_state_engine"
UNI = BASE / "data" / "universe"
REGISTRY_PATH = UNI / "universe.json"
REPORT = BASE / "reports" / "MACRO_STATE_ENGINE.json"
#: The causal graph, read in the same order `state_vector_build` reads it: the REPORT first
#: because it is the graph organ's own answer, the tracked `data/` copy second because `reports/`
#: is gitignored and a box that only ever received the synced graph still gets its edges.
WORLD_REPORT = BASE / "reports" / "WORLD_CAUSAL_GRAPH.json"
WORLD_GRAPH = BASE / "data" / "world_causal_graph.json"
#: The cross-asset screen's artifact. Read and REPORTED rather than used: measured 2026-09-22 it
#: publishes counts (`edges: 26`) and an empty `proposals`, never an edge list, so it can seed no
#: pair. That is a verdict about an input, and it belongs in the artifact where the next session
#: can see it instead of rediscovering it.
CROSS_ASSET = BASE / "reports" / "CROSS_ASSET_GRAPH.json"

#: THE SEED MAP, PART ONE: currency code -> region key. Hand-written and small on purpose; it is
#: the only place a country name appears. Which currencies actually form blocks is decided by the
#: registry, not by this map -- a code here with no classified instrument forms no block.
CCY_REGION: dict[str, str] = {
    "USD": "US", "EUR": "EZ", "JPY": "JP", "GBP": "GB", "AUD": "AU", "NZD": "NZ",
    "CAD": "CA", "CHF": "CH", "SEK": "SE", "NOK": "NO", "DKK": "DK", "PLN": "PL",
    "HUF": "HU", "CZK": "CZ", "TRY": "TR", "ZAR": "ZA", "MXN": "MX", "SGD": "SG",
    "HKD": "HK", "CNH": "CN", "CNY": "CN", "INR": "IN", "KRW": "KR", "BRL": "BR",
    "ILS": "IL", "THB": "TH", "RUB": "RU", "TWD": "TW", "PHP": "PH", "IDR": "ID",
}
#: THE SEED MAP, PART TWO: index and bond tickers -> region key. A ticker carries no currency to
#: parse, so the broker's name is mapped once. Euro-area national indices keep their OWN country
#: block and EUSTX50 is the bloc's, because a German growth state and an Italian one are not the
#: same state even when the policy rate is.
SYMBOL_REGION: dict[str, str] = {
    "US500": "US", "US30": "US", "NAS100": "US", "US2000": "US", "USDX": "US",
    "UST05Y": "US", "UST10Y": "US", "GER40": "DE", "FRA40": "FR", "NETH25": "NL",
    "E35": "ES", "EUSTX50": "EZ", "UK100": "GB", "UKGILT": "GB", "JPN225": "JP",
    "AUS200": "AU", "CA60": "CA", "HK50": "HK", "CHINAH": "CN",
}
#: The six states every block publishes, in report order. A block publishes all six ALWAYS: the
#: ones its data cannot support are published UNMEASURED with the reason, because a state that is
#: simply absent from the artifact reads as a state nobody asked for.
STATES: tuple[str, ...] = ("growth", "inflation", "policy_rates", "liquidity",
                           "risk_appetite", "external_tot")
#: Lookbacks in TRADING DAYS for the price-derived states. 126 ~ six months (a growth trend that
#: survives a quarter), 63 ~ one quarter (a policy and terms-of-trade impulse), 21 ~ one month
#: (realised volatility). They are lookbacks, not fitted parameters: nothing here is searched.
MOM_DAYS, IMPULSE_DAYS, VOL_DAYS = 126, 63, 21
#: The commodity basket the terms-of-trade beta is measured against, restricted to instruments
#: this desk holds bars for. Gold, oil and copper are the three the desk trades and the three that
#: price most of the world's terms of trade; a missing one simply drops out of the basket.
TOT_BASKET: tuple[str, ...] = ("XAUUSD", "XTIUSD", "XCUUSD")
#: Default permutations for the change-point p-value. 199 gives a resolution of 0.005, which is
#: finer than any threshold this organ uses, at a cost of 199 O(n) passes per pair.
N_PERM = 199
#: Donations per pass, and the p-value a row must beat to be one. Neither is a cap on research:
#: EVERY measured edge change is published in the artifact regardless. This bounds only what is
#: pushed into the DOCKET, because trial count is a shared cost -- a row the permutation null
#: already explains would raise the bar every other hypothesis on the docket has to clear.
MAX_DONATIONS, P_MAX = 15, 0.10
#: Change kind -> the registered price-only family that expresses it. Each name is checked at
#: runtime against the family registries AND the compiler's price-only vocabulary; a kind whose
#: family is missing or banned is refused and counted, never donated under an invented name.
FAMILY_BY_KIND: dict[str, str] = {
    "turned_on": "momentum_volgate",     # the driver transmits again: the responder trends
    "strengthened": "momentum_volgate",
    "sign_flip": "spread_state",         # the pair's spread is the object that changed state
    "weakened": "spread_state",
    "died": "mean_reversion_rsi",        # nothing pushes it now: its own moves revert
}
RULE = ("a change point at t uses the two windows ending at t and never a bar after it; the "
        "p-value permutes the pairing over the whole scan, so the scan's own multiplicity is "
        "priced in; every state a region's data cannot support is UNMEASURED with its reason")


# ------------------------------------------------------------------------------- small helpers
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _f(x: Any) -> float | None:
    """A finite float or None. `None` is a real answer everywhere in this organ."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _r(x: float | None, nd: int = 6) -> float | None:
    return None if x is None else round(float(x), nd)


def _read_json(path: Path) -> Any:
    """Tolerant: a BOM, a missing file and a half-written one are all 'that source is absent'."""
    try:
        return json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def max_rows() -> int:
    """Observations kept per series, DERIVED from this machine's measured free memory.

    Never sized off a claim about a box (the build host has 8 GB and the trading host 98 GB, and
    a constant chosen for either one is wrong on the other). Two float64 arrays per series and
    about five working copies inside the change-point scan is ~80 bytes per observation; spending
    2% of free memory on that, floored at 20,000 observations (~80 years of daily bars) so an
    unreadable counter changes nothing.
    """
    floor = 20_000
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        avail = int(psutil.virtual_memory().available)
    except Exception:                                                   # pragma: no cover - env
        return floor
    return max(floor, int(avail * 0.02 / 80.0))


# --------------------------------------------------------------------------------- PIT series
@lru_cache(maxsize=1)
def _registry() -> dict[str, dict[str, Any]]:
    """The broker's own instrument registry, KEYED AS THE BROKER SPELLS IT.

    Not uppercased: the parquet on disk is `Apple_D1.parquet`, so a block that published `APPLE`
    would name a symbol that reads right and resolves to nothing. Matching against the seed maps
    uppercases at the point of comparison instead. Empty when absent -- a verdict the report
    carries, never an excuse to guess an asset class.
    """
    doc = _read_json(REGISTRY_PATH)
    if not isinstance(doc, dict):
        return {}
    return {str(k): v for k, v in doc.items() if isinstance(v, dict)}


def _bars_close(symbol: str, suffix: str) -> Any:
    """One (symbol, timeframe) close series, through `state_vector_build._bars` where it imports.

    REUSED RATHER THAN REWRITTEN: that reader already decides what a readable parquet is, and it
    takes its universe directory as a PARAMETER precisely so a caller (or a test) can point it
    somewhere else. The local fallback exists because importing it drags in the regime engine,
    and an organ that cannot read a bar because a neighbour's import failed is a worse organ.
    """
    try:
        from research.state_vector_build import _bars
        return _bars(symbol, suffix, UNI)
    except Exception:                                                   # pragma: no cover - env
        pass
    try:
        import pandas as pd
        path = UNI / f"{symbol}_{suffix}.parquet"
        if not path.exists():
            return None
        df = pd.read_parquet(path, columns=["close"])
        if df.empty:
            return None
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        s = pd.Series(df["close"].to_numpy(dtype=float), index=idx).dropna()
        return s if s.size else None
    except Exception:                                                   # pragma: no cover - env
        return None


def closes(symbol: str, clock: str = "D") -> tuple[list[str], NDArray[np.float64]]:
    """(dates, closes) for `symbol` on the daily or weekly grid. Empty when the desk holds none.

    The finest file that can serve the clock wins, resampled with LAST -- the close of the period
    is the only price the desk could have acted on at its end, so no bar here is ever a price
    from inside a period that had not finished.
    """
    rule = "W-FRI" if clock.upper().startswith("W") else "1D"
    best_n: int = -1
    best: Any = None
    for suffix in ("D1", "H1", "M15", "M5"):
        s = _bars_close(symbol, suffix)
        if s is None or len(s) == 0:
            continue
        try:
            r = s.resample(rule).last().dropna()
        except Exception:                                               # pragma: no cover - env
            continue
        if len(r) > best_n:
            best_n, best = len(r), r
    if best is None or best_n <= 0:
        return [], np.zeros(0, dtype=float)
    cap = max_rows()
    if best_n > cap:
        best = best.iloc[-cap:]
    dates = [str(t)[:10] for t in best.index]
    return dates, np.asarray(best.to_numpy(dtype=float), dtype=float)


@lru_cache(maxsize=1)
def fred_levels() -> dict[str, tuple[tuple[str, ...], tuple[float, ...]]]:
    """The FRED archive as {series id: (dates, levels)}, read from `macro_state.resolve_archive`.

    The PATH is the reuse that matters: one archive, one collector, one answer about which file
    is current. Levels rather than `macro_state.daily_states()`' ranks because two of the states
    here are DIFFERENCES of levels (the 10y breakeven is DGS10 - DFII10) and a difference of
    percentile ranks is not a spread.
    """
    out: dict[str, tuple[tuple[str, ...], tuple[float, ...]]] = {}
    # ALFRED FIRST (2026-09-30): the same point-in-time overlay `macro_state` reads, so a series
    # with a vintage file is its first-release path dated by publication, and the rest are the
    # current vintage -- `fred_vintages()` says which is which.
    try:
        from libs.portfolio.macro_state import load_pit
        series, _newest, _v = load_pit()
        for sid, rows in series.items():
            if rows:
                out[str(sid)] = (tuple(r[0] for r in rows), tuple(r[1] for r in rows))
        return out
    except Exception:                                                   # pragma: no cover - env
        pass
    try:
        from libs.portfolio.macro_state import resolve_archive
        doc = _read_json(resolve_archive())
    except Exception:                                                   # pragma: no cover - env
        doc = None
    if not isinstance(doc, dict):
        return out
    for sid, pts in (doc.get("series") or {}).items():
        rows: list[tuple[str, float]] = []
        if not isinstance(pts, list):
            continue
        for p in pts:
            try:
                d, v = str(p[0])[:10], float(p[1])
            except (TypeError, ValueError, IndexError):
                continue
            if len(d) == 10 and np.isfinite(v):
                rows.append((d, v))
        rows.sort()
        if rows:
            out[str(sid)] = (tuple(r[0] for r in rows), tuple(r[1] for r in rows))
    return out


def fred_vintages() -> dict[str, Any]:
    """Which vintage each FRED series in `fred_levels` is: ALFRED point-in-time, or the current
    vintage stamped 'current (look-ahead risk)'. The report carries it so no reader treats a
    revised series as point-in-time."""
    try:
        from libs.portfolio.macro_state import VINTAGE_ALFRED, VINTAGE_CURRENT, load_pit
        _s, _n, by_sid = load_pit()
    except Exception as exc:                                            # pragma: no cover - env
        return {"vintage": "current (look-ahead risk)", "by_series": {},
                "why": f"{type(exc).__name__}: {exc}"}
    overall = (VINTAGE_ALFRED if by_sid and all(v == VINTAGE_ALFRED for v in by_sid.values())
               else VINTAGE_CURRENT)
    return {"vintage": overall, "by_series": by_sid}


def rank_window() -> int:
    """The trailing rank window, taken from `macro_state` so both organs mean the same thing by
    'the top of its year'."""
    try:
        from libs.portfolio.macro_state import RANK_WINDOW
        return int(RANK_WINDOW)
    except Exception:                                                   # pragma: no cover - env
        return 250


def pit_rank(values: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """Trailing-window percentile rank of each print among the `window` prints ending AT it.

    Identical in definition to `libs.portfolio.macro_state._rank` (a test asserts the two agree
    print for print), restated here rather than reaching into another module's private. NaN until
    the window is full: a rank computed over four prints is not a regime, it is a coin.
    """
    n = int(values.size)
    out = np.full(n, np.nan, dtype=float)
    if n < window or window < 2:
        return out
    for i in range(window - 1, n):
        tail = values[i - window + 1: i + 1]
        out[i] = float((tail < values[i]).sum()) / float(window - 1)
    return out


def _bucket(rank: float | None) -> str:
    try:
        from libs.portfolio.macro_state import bucket
        return str(bucket(rank))
    except Exception:                                                   # pragma: no cover - env
        return "UNMEASURED" if rank is None else ("low" if rank < 1 / 3 else
                                                  "high" if rank > 2 / 3 else "mid")


# ------------------------------------------------------------------------------ region blocks
def _pair_ccys(symbol: str) -> tuple[str, str] | None:
    s = str(symbol).strip().upper()
    if len(s) != 6 or not s.isalpha():
        return None
    return s[:3], s[3:]


def region_blocks() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Walk the broker's registry once and group every classified instrument into its region.

    Returns (blocks, census). A block is created only when an instrument lands in it, so the set
    of countries is the set the desk can actually measure. Single-name equities land in
    `event_lane`: they are MEASURED here (a region with fifty share CFDs and no index says
    something true about this desk's coverage) and they are never hunted -- the two-lane mandate
    is enforced again at the donation door, where it decides something.
    """
    blocks: dict[str, dict[str, Any]] = {}
    census: dict[str, Any] = {"registry_rows": 0, "classified": 0, "unclassified": [],
                              "unmapped_currencies": [], "global": []}

    def _slot(region: str, role: str, symbol: str) -> None:
        b = blocks.setdefault(region, {"region": region, "fx": [], "index": [], "rates": [],
                                       "commodity": [], "event_lane": []})
        if symbol not in b[role]:
            b[role].append(symbol)

    reg = _registry()
    census["registry_rows"] = len(reg)
    unmapped: set[str] = set()
    for sym, row in sorted(reg.items()):
        # The seed maps are written in upper case and the registry is not, so matching happens on
        # `key` while everything PUBLISHED keeps `sym`, the broker's own spelling -- the only one
        # that finds `Apple_D1.parquet`.
        key = sym.upper()
        klass = " ".join(str(row.get("asset_class") or "").strip().lower().split())
        if not klass:
            census["unclassified"].append(sym)
            continue
        census["classified"] = int(census["classified"]) + 1
        if klass.startswith("forex") or klass in ("fx",):
            pair = _pair_ccys(key)
            if pair is None:
                census["unclassified"].append(sym)
                continue
            for ccy in pair:
                region = CCY_REGION.get(ccy)
                if region is None:
                    unmapped.add(ccy)
                    continue
                _slot(region, "fx", sym)
        elif klass.startswith("indices") or klass.startswith("index"):
            region = SYMBOL_REGION.get(key)
            if region is None:
                census["unclassified"].append(sym)
                continue
            _slot(region, "rates" if key.startswith("UST") else "index", sym)
        elif klass.startswith("bond"):
            region = SYMBOL_REGION.get(key)
            if region is None:
                census["unclassified"].append(sym)
                continue
            _slot(region, "rates", sym)
        elif klass.startswith("equit") or klass in ("shares", "share", "stock", "stocks"):
            # MEASURED, NEVER HUNTED. A share CFD's ticker carries no country, but the registry
            # names the currency it settles in, so the instrument is routed to that region's
            # EVENT lane -- counted in the block, never in a state and never in a donation. A
            # region with fifty share CFDs and no index is a true and useful fact about this
            # desk's coverage; inventing a growth state out of them would not be.
            region = CCY_REGION.get(str(row.get("currency_profit") or "").strip().upper(), "")
            if region:
                _slot(region, "event_lane", sym)
            else:
                census["global"].append(sym)
        else:
            census["global"].append(sym)
    census["unmapped_currencies"] = sorted(unmapped)
    census["unclassified"] = sorted(set(census["unclassified"]))[:60]
    census["global"] = sorted(set(census["global"]))[:80]
    return blocks, census


# ------------------------------------------------------------------------------- state builders
def _state(name: str, *, value: float | None, basis: str, as_of: str | None,
           n_obs: int, why: str = "", **extra: Any) -> dict[str, Any]:
    measured = value is not None
    row: dict[str, Any] = {"state": name, "status": "measured" if measured else "UNMEASURED",
                           "value": _r(value), "bucket": _bucket(value) if measured else None,
                           "basis": basis, "as_of": as_of, "n_obs": int(n_obs),
                           "why": why if not measured else ""}
    row.update(extra)
    return row


def _rank_of_last(dates: list[str], values: NDArray[np.float64], window: int,
                  ) -> tuple[float | None, str | None]:
    """The trailing rank of the most recent print, and its date. None when the window is short."""
    if values.size == 0 or values.size < window:
        return None, (dates[-1] if dates else None)
    ranks = pit_rank(values, window)
    v = _f(ranks[-1])
    return v, (dates[-1] if dates else None)


def _pick(symbols: list[str], clock: str = "D") -> tuple[str, list[str], NDArray[np.float64]]:
    """The listed instrument with the most usable bars, and its series. ('', [], empty) if none."""
    best_sym, best_dates, best_vals = "", [], np.zeros(0, dtype=float)
    for sym in symbols:
        d, v = closes(sym, clock)
        if v.size > best_vals.size:
            best_sym, best_dates, best_vals = sym, d, v
    return best_sym, best_dates, best_vals


def _change(values: NDArray[np.float64], days: int) -> NDArray[np.float64]:
    """Log change over `days` observations, NaN where the lookback is not yet available."""
    out = np.full(values.size, np.nan, dtype=float)
    if values.size <= days:
        return out
    v = np.where(values > 0, values, np.nan)
    out[days:] = np.log(v[days:]) - np.log(v[:-days])
    return out


def _growth(block: dict[str, Any], window: int) -> dict[str, Any]:
    sym, dates, vals = _pick(list(block["index"]))
    if not sym:
        return _state("growth", value=None, basis="", as_of=None, n_obs=0,
                      why="no equity index classified to this region in the broker's registry")
    mom = _change(vals, MOM_DAYS)
    ok = np.isfinite(mom)
    value, as_of = _rank_of_last([d for d, k in zip(dates, ok, strict=True) if k], mom[ok], window)
    return _state("growth", value=value, basis=f"{sym} {MOM_DAYS}d log return, trailing rank",
                  as_of=as_of, n_obs=int(ok.sum()), instrument=sym,
                  why=f"{int(ok.sum())} usable prints, fewer than the {window}-print rank window")


def _risk(block: dict[str, Any], window: int) -> dict[str, Any]:
    sym, dates, vals = _pick(list(block["index"]) or list(block["fx"]))
    if not sym:
        return _state("risk_appetite", value=None, basis="", as_of=None, n_obs=0,
                      why="no index or FX instrument classified to this region")
    ret = np.diff(np.log(np.where(vals > 0, vals, np.nan)), prepend=np.nan)
    vol = np.full(ret.size, np.nan, dtype=float)
    for i in range(VOL_DAYS, ret.size):
        w = ret[i - VOL_DAYS + 1: i + 1]
        if np.isfinite(w).sum() >= VOL_DAYS - 2:
            vol[i] = float(np.nanstd(w, ddof=1))
    ok = np.isfinite(vol)
    rank, as_of = _rank_of_last([d for d, k in zip(dates, ok, strict=True) if k], vol[ok], window)
    # INVERTED ON PURPOSE: high realised volatility is risk OFF, and the state is named for the
    # appetite, so a 0.9 here means the region's own market is as calm as it gets in its year.
    value = None if rank is None else 1.0 - rank
    return _state("risk_appetite", value=value, as_of=as_of, n_obs=int(ok.sum()), instrument=sym,
                  basis=f"{sym} {VOL_DAYS}d realised vol, trailing rank, inverted",
                  why=f"{int(ok.sum())} usable prints, fewer than the {window}-print rank window")


def _inflation(region: str, window: int) -> dict[str, Any]:
    fred = fred_levels()
    if region == "US" and "DGS10" in fred and "DFII10" in fred:
        nom, real = fred["DGS10"], fred["DFII10"]
        real_by_date = dict(zip(real[0], real[1], strict=True))
        dates = [d for d in nom[0] if d in real_by_date]
        vals = np.array([nom[1][nom[0].index(d)] - real_by_date[d] for d in dates], dtype=float)
        value, as_of = _rank_of_last(dates, vals, window)
        return _state("inflation", value=value, as_of=as_of, n_obs=len(dates),
                      basis="FRED DGS10 - DFII10 (10y breakeven), trailing rank",
                      why=f"{len(dates)} joint prints, fewer than the {window}-print window")
    return _state("inflation", value=None, basis="", as_of=None, n_obs=0,
                  why=(f"no point-in-time inflation or breakeven series for {region} on this "
                       f"box: the FRED archive holds {len(fred)} series and all of them are US "
                       "(DGS10, DFII10, T10Y2Y, VIXCLS, DTWEXBGS, WALCL, M2SL)"))


def _policy(region: str, block: dict[str, Any], window: int) -> dict[str, Any]:
    fred = fred_levels()
    if region == "US" and "DGS10" in fred:
        d, v = fred["DGS10"]
        value, as_of = _rank_of_last(list(d), np.asarray(v, dtype=float), window)
        return _state("policy_rates", value=value, as_of=as_of, n_obs=len(d),
                      basis="FRED DGS10 level, trailing rank",
                      why=f"{len(d)} prints, fewer than the {window}-print rank window")
    sym, dates, vals = _pick(list(block["rates"]))
    if not sym:
        return _state("policy_rates", value=None, basis="", as_of=None, n_obs=0,
                      why=(f"no yield series and no bond instrument classified to {region}; the "
                           "FRED archive is US-only and the registry lists no rates proxy here"))
    imp = _change(vals, IMPULSE_DAYS)
    ok = np.isfinite(imp)
    # A bond PRICE falling is a yield rising, which is the tightening the state is named for, so
    # the rank of the price impulse is inverted to read as policy tightness.
    rank, as_of = _rank_of_last([d for d, k in zip(dates, ok, strict=True) if k], imp[ok], window)
    value = None if rank is None else 1.0 - rank
    return _state("policy_rates", value=value, as_of=as_of, n_obs=int(ok.sum()), instrument=sym,
                  basis=f"{sym} {IMPULSE_DAYS}d log price change, trailing rank, inverted",
                  why=f"{int(ok.sum())} usable prints, fewer than the {window}-print window")


def _liquidity(region: str, window: int) -> dict[str, Any]:
    fred = fred_levels()
    if region == "US" and "WALCL" in fred:
        d, v = fred["WALCL"]
        # WALCL prints weekly: a year of it is 52 prints, not 250, so the window follows the
        # series' own clock exactly as `macro_state._WINDOW_BY_SERIES` does.
        value, as_of = _rank_of_last(list(d), np.asarray(v, dtype=float), min(52, window))
        return _state("liquidity", value=value, as_of=as_of, n_obs=len(d),
                      basis="FRED WALCL level, trailing 52-print rank",
                      why=f"{len(d)} prints, fewer than the 52-print window")
    return _state("liquidity", value=None, basis="", as_of=None, n_obs=0,
                  why=(f"no central-bank balance sheet or monetary aggregate for {region} in the "
                       "FRED archive (US-only), and no price series is a liquidity measurement"))


def _effective_ccy(region: str, block: dict[str, Any]) -> tuple[list[str], NDArray[np.float64]]:
    """The region's currency as a log effective index across every universe pair that holds it.

    Signed by side (+1 where the region's currency is the base, -1 where it is the quote) and
    averaged over the pairs that have a print on the day, so the index means 'this currency
    against what this desk can actually see'. Not a trade-weighted index and it does not pretend
    to be one -- the weights are the desk's coverage, and `basis` says so.
    """
    ccys = {c for c, r in CCY_REGION.items() if r == region}
    grids: list[dict[str, float]] = []
    for sym in sorted(block["fx"]):
        pair = _pair_ccys(sym)
        if pair is None:
            continue
        sign = 1.0 if pair[0] in ccys else (-1.0 if pair[1] in ccys else 0.0)
        if sign == 0.0:
            continue
        d, v = closes(sym)
        if v.size == 0:
            continue
        lv = np.where(v > 0, v, np.nan)
        grids.append({dt: sign * float(np.log(x)) for dt, x in zip(d, lv, strict=True)
                      if np.isfinite(x)})
    if not grids:
        return [], np.zeros(0, dtype=float)
    dates = sorted(set().union(*[set(g) for g in grids]))
    vals: list[float] = []
    keep: list[str] = []
    for dt in dates:
        xs = [g[dt] for g in grids if dt in g]
        if xs:
            keep.append(dt)
            vals.append(float(np.mean(xs)))
    return keep, np.asarray(vals, dtype=float)


def _basket() -> tuple[list[str], NDArray[np.float64]]:
    grids: list[dict[str, float]] = []
    for sym in TOT_BASKET:
        d, v = closes(sym)
        if v.size == 0:
            continue
        lv = np.where(v > 0, v, np.nan)
        grids.append({dt: float(np.log(x)) for dt, x in zip(d, lv, strict=True)
                      if np.isfinite(x)})
    if not grids:
        return [], np.zeros(0, dtype=float)
    dates = sorted(set().union(*[set(g) for g in grids]))
    keep, vals = [], []
    for dt in dates:
        xs = [g[dt] for g in grids if dt in g]
        if xs:
            keep.append(dt)
            vals.append(float(np.mean(xs)))
    return keep, np.asarray(vals, dtype=float)


def _external(region: str, block: dict[str, Any], window: int) -> dict[str, Any]:
    dates, idx = _effective_ccy(region, block)
    if idx.size == 0:
        return _state("external_tot", value=None, basis="", as_of=None, n_obs=0,
                      why=f"no FX pair in the registry carries {region}'s currency")
    imp = _change(np.exp(idx), IMPULSE_DAYS)
    ok = np.isfinite(imp)
    ok_dates = [d for d, k in zip(dates, ok, strict=True) if k]
    value, as_of = _rank_of_last(ok_dates, imp[ok], window)
    # TERMS OF TRADE WITHOUT AN EXPORTER LIST. The sign of a currency's commodity exposure is
    # MEASURED, not declared: the trailing beta of its effective-index impulse on the commodity
    # basket's impulse, fitted only on data up to the last print. A country map would be right
    # the day it was written and silently wrong afterwards -- exactly the failure the two-lane
    # router exists to avoid.
    b_dates, b_vals = _basket()
    tot_beta: float | None = None
    tot_signal: float | None = None
    if b_vals.size:
        b_imp = _change(np.exp(b_vals), IMPULSE_DAYS)
        b_by_date = {d: x for d, x in zip(b_dates, b_imp, strict=True) if np.isfinite(x)}
        joint = [(imp[i], b_by_date[d]) for i, d in enumerate(dates)
                 if np.isfinite(imp[i]) and d in b_by_date]
        if len(joint) >= 60:
            x = np.array([p[1] for p in joint], dtype=float)
            y = np.array([p[0] for p in joint], dtype=float)
            sxx = float(((x - x.mean()) ** 2).sum())
            if sxx > 0:
                tot_beta = float(((x - x.mean()) * (y - y.mean())).sum() / sxx)
                tot_signal = float(tot_beta * x[-1])
    return _state("external_tot", value=value, as_of=as_of, n_obs=int(ok.sum()),
                  basis=(f"log effective {region} currency index over {len(block['fx'])} "
                         f"universe pairs, {IMPULSE_DAYS}d impulse, trailing rank"),
                  tot_beta=_r(tot_beta), tot_signal=_r(tot_signal),
                  tot_basis=("measured trailing beta of the effective index's impulse on the "
                             f"{'/'.join(TOT_BASKET)} basket impulse; no exporter list"),
                  why=f"{int(ok.sum())} usable prints, fewer than the {window}-print window")


def build_blocks() -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Every region block with its six states, plus the census and a coverage summary."""
    blocks, census = region_blocks()
    window = rank_window()
    out: dict[str, dict[str, Any]] = {}
    measured = 0
    for region in sorted(blocks):
        block = blocks[region]
        states = {
            "growth": _growth(block, window),
            "inflation": _inflation(region, window),
            "policy_rates": _policy(region, block, window),
            "liquidity": _liquidity(region, window),
            "risk_appetite": _risk(block, window),
            "external_tot": _external(region, block, window),
        }
        n_ok = sum(1 for s in states.values() if s["status"] == "measured")
        measured += n_ok
        out[region] = {
            "region": region,
            "instruments": {k: block[k] for k in ("fx", "index", "rates", "event_lane")},
            "n_instruments": sum(len(block[k]) for k in ("fx", "index", "rates")),
            "states": {name: states[name] for name in STATES},
            "coverage": round(n_ok / float(len(STATES)), 4),
            "measured_states": n_ok, "unmeasured_states": len(STATES) - n_ok,
        }
    total = len(out) * len(STATES)
    summary = {"n_blocks": len(out), "states_per_block": len(STATES),
               "measured": measured, "unmeasured": total - measured,
               "coverage": round(measured / float(total), 4) if total else 0.0,
               "rank_window": window,
               "rule": ("a state a region's PIT data cannot support is UNMEASURED with its "
                        "reason; no global number is ever substituted for a missing local one")}
    return out, summary, census


def global_factors(blocks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The world's own state: the FRED dims, plus the CROSS-SECTION of the region blocks.

    The dispersion rows are the part that only exists once there are blocks: how far apart the
    regions' growth states are, and what share of them is risk-on, are facts about the world that
    no single-country vector can express.
    """
    out: dict[str, Any] = {"fred": {"status": "absent", "why": "", "states": {}}}
    try:
        from libs.portfolio.macro_state import now as macro_now
        snap = macro_now()
        out["fred"] = {"status": str(snap.get("status") or "present"),
                       "as_of": snap.get("as_of"), "states": snap.get("states") or {},
                       "buckets": snap.get("buckets") or {},
                       "freshness": snap.get("freshness"),
                       "why": "libs/portfolio/macro_state.now(): the US dims, unchanged"}
    except Exception as exc:                                            # pragma: no cover - env
        out["fred"] = {"status": "absent", "states": {},
                       "why": f"macro_state.now() unavailable ({type(exc).__name__}: {exc})"}
    for name in STATES:
        vals = [b["states"][name]["value"] for b in blocks.values()
                if b["states"][name]["status"] == "measured"]
        clean = [float(v) for v in vals if v is not None]
        out[f"dispersion_{name}"] = {
            "n_blocks_measured": len(clean),
            "mean": _r(float(np.mean(clean))) if clean else None,
            "stdev": _r(float(np.std(clean, ddof=1))) if len(clean) > 1 else None,
            "share_high": _r(float(np.mean([1.0 if v > 2 / 3 else 0.0 for v in clean]))
                             ) if clean else None,
            "status": "measured" if clean else "UNMEASURED",
            "why": "" if clean else f"no region publishes a measured {name}",
        }
    out["scalars"] = _global_scalars(out)
    return out


def _global_scalars(factors: dict[str, Any]) -> dict[str, Any]:
    """THE SAME CROSS-SECTION AS ONE NUMBER PER FACT, because a reader needs a number.

    Every value above is a dict -- the honest shape, because each carries its own status and its
    own reason. But a reader that wants THE global factor finds no scalar anywhere in the block
    and can only render UNMEASURED, which was the desk dashboard's verdict on this organ while
    the organ was measuring six dispersions perfectly well. A structure nothing can read is a
    measurement nobody has.

    So the scalars are DERIVED FROM THE BLOCK ABOVE and never recomputed: each dispersion's mean,
    stdev and high-share flattened to `<state>_mean` etc., plus the two facts about the world the
    six of them make -- how many states the regions agree on at all (`n_states_measured`), and
    the mean dispersion across the states that ARE measured (`cross_state_dispersion`), which is
    the one number that says whether the world is moving together or apart.

    A state no region measures contributes NOTHING here -- not a zero. An absent scalar is absent
    with the same reason the dict above carries (L1.28a).
    """
    flat: dict[str, Any] = {}
    stdevs: list[float] = []
    measured_states: list[str] = []
    unmeasured: dict[str, str] = {}
    for name in STATES:
        row = factors.get(f"dispersion_{name}")
        if not isinstance(row, dict):
            continue
        if str(row.get("status")) != "measured":
            unmeasured[name] = str(row.get("why") or "")
            continue
        measured_states.append(name)
        for field in ("mean", "stdev", "share_high"):
            value = row.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                flat[f"{name}_{field}"] = float(value)
        flat[f"{name}_n_blocks"] = int(row.get("n_blocks_measured") or 0)
        if isinstance(row.get("stdev"), (int, float)):
            stdevs.append(float(row["stdev"]))
    raw_fred = factors.get("fred")
    fred: dict[str, Any] = raw_fred if isinstance(raw_fred, dict) else {}
    fresh = fred.get("freshness")
    if isinstance(fresh, (int, float)) and not isinstance(fresh, bool):
        flat["fred_freshness"] = float(fresh)
    flat["fred_status"] = str(fred.get("status") or "absent")
    flat["fred_as_of"] = fred.get("as_of")
    flat["n_states_measured"] = len(measured_states)
    flat["states_measured"] = measured_states
    # A DISPERSION OF ONE BLOCK HAS NO SPREAD, AND THAT IS NOT A SPREAD OF ZERO. `stdev` is None
    # at n=1 by construction above, so this mean is taken over the states that HAVE a spread and
    # says how many they were; with none, it is UNMEASURED with its reason.
    flat["cross_state_dispersion"] = (_r(float(np.mean(stdevs))) if stdevs else None)
    flat["cross_state_dispersion_n"] = len(stdevs)
    flat["cross_state_dispersion_why"] = (
        "" if stdevs else
        "no state has two or more regions measured, so no cross-region spread exists to average; "
        "this is UNMEASURED and never a dispersion of zero")
    flat["status"] = "measured" if measured_states else "UNMEASURED"
    flat["why"] = ("" if measured_states else
                   "no region publishes a measured state, so the world has no scalar factor on "
                   "this host: " + "; ".join(f"{k}: {v}" for k, v in unmeasured.items())[:400])
    flat["unmeasured_states"] = unmeasured
    flat["basis"] = ("derived from the dispersion_* rows above and the FRED snapshot; nothing is "
                     "recomputed here, so a scalar can never disagree with the block it came from")
    return flat


# --------------------------------------------------------------------------- the edge hunter
def _rolling_ols(x: NDArray[np.float64], y: NDArray[np.float64], w: int,
                 ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Rolling OLS of y on x over the TRAILING window of length `w` ending at each index.

    Returns (beta, se, corr), each NaN before the first full window. Computed from cumulative
    sums so one pass is O(n) -- which is what makes a 199-permutation null affordable per pair.
    Index i reads x[i-w+1 .. i] and y[i-w+1 .. i] and NOTHING after i; that is the anti-lookahead
    guarantee the whole change-point scan rests on.
    """
    n = int(x.size)
    beta = np.full(n, np.nan, dtype=float)
    se = np.full(n, np.nan, dtype=float)
    corr = np.full(n, np.nan, dtype=float)
    if n < w or w < 8:
        return beta, se, corr

    def _win(v: NDArray[np.float64]) -> NDArray[np.float64]:
        cs = np.concatenate(([0.0], np.cumsum(v)))
        return np.asarray(cs[w:] - cs[:-w], dtype=float)

    sx, sy = _win(x), _win(y)
    sxx, syy, sxy = _win(x * x), _win(y * y), _win(x * y)
    cxx = sxx - sx * sx / w
    cyy = syy - sy * sy / w
    cxy = sxy - sx * sy / w
    with np.errstate(divide="ignore", invalid="ignore"):
        b = np.where(cxx > 0, cxy / cxx, np.nan)
        resid = cyy - b * cxy
        s2 = np.where(resid > 0, resid, 0.0) / float(w - 2)
        s = np.sqrt(np.where(cxx > 0, s2 / cxx, np.nan))
        c = np.where((cxx > 0) & (cyy > 0), cxy / np.sqrt(cxx * cyy), np.nan)
    beta[w - 1:] = b
    se[w - 1:] = s
    corr[w - 1:] = c
    return beta, se, corr


def _scan(x: NDArray[np.float64], y: NDArray[np.float64], w: int,
          ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64],
                     NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """(z, beta_pre, beta_post, se_pre, se_post, corr_post) indexed by DETECTION time.

    The two windows both END at or before the detection index: post is [i-w+1, i], pre is the w
    observations before it. z is their standardized difference. Everything is NaN until 2w
    observations exist, because a break needs a before as well as an after.
    """
    beta, se, corr = _rolling_ols(x, y, w)
    n = int(x.size)
    z = np.full(n, np.nan, dtype=float)
    b_pre = np.full(n, np.nan, dtype=float)
    s_pre = np.full(n, np.nan, dtype=float)
    if n >= 2 * w:
        b_pre[2 * w - 1:] = beta[w - 1: n - w]
        s_pre[2 * w - 1:] = se[w - 1: n - w]
        denom = np.sqrt(s_pre ** 2 + se ** 2)
        with np.errstate(divide="ignore", invalid="ignore"):
            z = np.where(denom > 0, (beta - b_pre) / denom, np.nan)
    return z, b_pre, beta, s_pre, se, corr


def _kind(b_pre: float, s_pre: float, b_post: float, s_post: float) -> str:
    """What the link DID, from the two windows' own t-statistics. Names, not adjectives."""
    t_pre = abs(b_pre / s_pre) if s_pre > 0 else 0.0
    t_post = abs(b_post / s_post) if s_post > 0 else 0.0
    live_pre, live_post = t_pre >= 2.0, t_post >= 2.0
    if live_pre and live_post and np.sign(b_pre) != np.sign(b_post):
        return "sign_flip"
    if not live_pre and live_post:
        return "turned_on"
    if live_pre and not live_post:
        return "died"
    return "strengthened" if abs(b_post) >= abs(b_pre) else "weakened"


def changepoint(x: NDArray[np.float64], y: NDArray[np.float64], *, window: int,
                n_perm: int = N_PERM, seed: int = 0) -> dict[str, Any]:
    """The strongest PIT change point in beta(y | x), with a permutation p-value for the scan.

    THE NULL IS 'ONE CONSTANT BETA'. Permuting the ORDER of the aligned (x, y) pairs keeps the
    joint distribution exactly and destroys any time structure, so the permuted maximum |z| is
    what this scan produces on a series with no break at all. Comparing the observed MAXIMUM to
    the permuted MAXIMUM prices the scan's own multiplicity: a break found by looking in 900
    places is charged for the 900 places.
    """
    n = int(min(x.size, y.size))
    if n < 2 * window + 2 or window < 8:
        return {"status": "UNMEASURED", "why": f"{n} aligned observations, fewer than the "
                                               f"{2 * window + 2} a {window}-bar double window "
                                               f"needs", "n": n}
    z, b_pre, b_post, s_pre, s_post, corr = _scan(x[:n], y[:n], window)
    finite = np.isfinite(z)
    if not finite.any():
        return {"status": "UNMEASURED", "why": "no window pair had a finite standard error "
                                               "(a constant series carries no regression)",
                "n": n}
    absz = np.where(finite, np.abs(z), -np.inf)
    i = int(np.argmax(absz))
    obs = float(absz[i])
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(max(int(n_perm), 0)):
        order = rng.permutation(n)
        pz, _, _, _, _, _ = _scan(x[:n][order], y[:n][order], window)
        pm = np.nanmax(np.abs(pz)) if np.isfinite(pz).any() else 0.0
        if float(pm) >= obs:
            ge += 1
    p = (1.0 + ge) / (1.0 + max(int(n_perm), 0))
    pre_c, post_c = _rolling_ols(x[:n], y[:n], window)[2][i - window], corr[i]
    return {"status": "measured", "n": n, "index": i, "window": window,
            "z": _r(float(z[i])), "abs_z": _r(obs), "p_perm": round(float(p), 6),
            "n_perm": int(n_perm),
            "beta_pre": _r(float(b_pre[i])), "beta_post": _r(float(b_post[i])),
            "se_pre": _r(float(s_pre[i])), "se_post": _r(float(s_post[i])),
            "corr_pre": _r(_f(pre_c)), "corr_post": _r(_f(post_c)),
            "kind": _kind(float(b_pre[i]), float(s_pre[i]),
                          float(b_post[i]), float(s_post[i]))}


def graph_pairs() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Every (src, dst, lag, clock) the causal graph names, plus a status row per input read.

    NO GRAPH IS A VERDICT, NOT A CRASH. With every source absent this returns no pairs and the
    caller publishes UNMEASURED rows saying which file it wanted -- an organ that raised here
    would take the region blocks down with it for want of a neighbour's artifact.
    """
    inputs: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for name, path, keys in (("world_causal_graph_report", WORLD_REPORT,
                              ("admitted_edges", "recorded_not_admitted")),
                             ("world_causal_graph_data", WORLD_GRAPH, ("edges",))):
        doc = _read_json(path)
        if not isinstance(doc, dict):
            inputs[name] = {"status": "absent", "path": str(path),
                            "why": "file missing or unreadable"}
            continue
        found: list[dict[str, Any]] = []
        for key in keys:
            v = doc.get(key)
            if isinstance(v, list):
                found.extend([e for e in v if isinstance(e, dict)])
        inputs[name] = {"status": "present", "path": str(path), "n_edges": len(found),
                        "generated_at": doc.get("generated_at") or doc.get("generated_utc"),
                        "why": "" if found else f"no edge list under {keys}"}
        if found and not rows:
            rows = found
    doc = _read_json(CROSS_ASSET)
    if isinstance(doc, dict):
        edges = doc.get("edges")
        inputs["cross_asset_graph"] = {
            "status": "present", "path": str(CROSS_ASSET), "n_edges": None,
            "why": ("publishes counts, not an edge list (edges="
                    f"{edges if isinstance(edges, int) else 'n/a'}); it can seed no pair until "
                    "the screen publishes its pairs")}
    else:
        inputs["cross_asset_graph"] = {"status": "absent", "path": str(CROSS_ASSET),
                                       "why": "file missing or unreadable"}
    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for e in rows:
        src, dst = str(e.get("src") or ""), str(e.get("dst") or "")
        if not src or not dst or src == dst:
            continue
        # `or 1` WOULD BE A BUG HERE: a contemporaneous edge carries lag 0, which is falsy, and
        # would silently become a 1-bar lead -- measuring a relationship the graph never claimed.
        lag_v = _f(e.get("lag"))
        lag = int(lag_v) if lag_v is not None else 1
        clock = str(e.get("clock") or "").upper()
        if not clock:
            clock = str(e.get("decay_cls") or "").upper().replace("BAR_", "")
        ident = (src.upper(), dst.upper(), lag)
        if ident in seen:
            continue
        seen.add(ident)
        pairs.append({"src": src, "dst": dst, "lag": max(lag, 0),
                      "clock": clock or "D1", "graph_strength": _f(e.get("strength")),
                      "graph_status": str(e.get("status") or "").upper() or "RECORDED",
                      "graph_n": _f(e.get("n"))})
    return pairs, inputs


def _aligned(src: str, dst: str, lag: int, clock: str,
             ) -> tuple[list[str], NDArray[np.float64], NDArray[np.float64], str]:
    """Lagged returns of (src, dst) on their common grid: x = src return at t-lag, y = dst at t."""
    grid = "W" if clock.startswith("W") else "D"
    ds, vs = closes(src, grid)
    dd, vd = closes(dst, grid)
    if vs.size < 4 or vd.size < 4:
        missing = src if vs.size < 4 else dst
        return [], np.zeros(0), np.zeros(0), f"no usable series on this box for {missing}"
    rs = {d: r for d, r in zip(ds[1:], np.diff(np.log(np.where(vs > 0, vs, np.nan))), strict=True)
          if np.isfinite(r)}
    rd = {d: r for d, r in zip(dd[1:], np.diff(np.log(np.where(vd > 0, vd, np.nan))), strict=True)
          if np.isfinite(r)}
    common = sorted(set(rs) & set(rd))
    if len(common) < 4:
        return [], np.zeros(0), np.zeros(0), (f"{len(common)} common {grid} bars between "
                                              f"{src} and {dst}")
    x_all = np.array([rs[d] for d in common], dtype=float)
    y_all = np.array([rd[d] for d in common], dtype=float)
    if lag > 0:
        if len(common) <= lag + 4:
            return [], np.zeros(0), np.zeros(0), f"fewer bars than the {lag}-bar lag needs"
        return common[lag:], x_all[:-lag], y_all[lag:], ""
    return common, x_all, y_all, ""


def hunt_edges(pairs: list[dict[str, Any]], *, deadline: float, n_perm: int,
               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Measure every pair the graph named. Returns (rows, unmeasured, counts)."""
    rows: list[dict[str, Any]] = []
    unmeasured: list[dict[str, Any]] = []
    tests = 0
    skipped_budget = 0
    for k, pair in enumerate(pairs):
        if time.monotonic() > deadline:
            skipped_budget = len(pairs) - k
            break
        src, dst, lag = str(pair["src"]), str(pair["dst"]), int(pair["lag"])
        dates, x, y, why = _aligned(src, dst, lag, str(pair["clock"]))
        if why:
            unmeasured.append({**pair, "status": "UNMEASURED", "why": why})
            continue
        # THE WINDOW IS DERIVED FROM THE SERIES, not chosen: a sixth of the sample, so the scan
        # always has at least three window-pairs to compare, bounded to a month at the short end
        # and a year at the long end. Nothing here is searched over, so nothing is charged for.
        window = int(np.clip(x.size // 6, 20, 250))
        seed = int(hashlib.sha1(f"{src}|{dst}|{lag}".encode()).hexdigest()[:8], 16)
        res = changepoint(x, y, window=window, n_perm=n_perm, seed=seed)
        tests += 1
        if res.get("status") != "measured":
            unmeasured.append({**pair, "status": "UNMEASURED", "why": str(res.get("why") or "")})
            continue
        i = int(res["index"])
        rows.append({**pair, **{k2: v for k2, v in res.items() if k2 != "index"},
                     "t_change": dates[i] if i < len(dates) else None,
                     "t_window_start": dates[max(i - 2 * int(res["window"]) + 1, 0)],
                     "grid": "W" if str(pair["clock"]).startswith("W") else "D"})
    rows.sort(key=lambda r: (float(r.get("p_perm") or 1.0), -float(r.get("abs_z") or 0.0)))
    counts = {"pairs": len(pairs), "measured": len(rows), "unmeasured": len(unmeasured),
              "tests_run": tests, "skipped_budget": skipped_budget, "n_perm": n_perm}
    return rows, unmeasured, counts


# ------------------------------------------------------------------------------- the donation
@lru_cache(maxsize=1)
def registered_families() -> frozenset[str]:
    """Every family the desk can call, minus the banned -- read off the registries the way
    `residual_queue.registered_families` reads them, never from a list kept here."""
    names: set[str] = set()
    try:
        from mt5desk import families as fam_mod
        from mt5desk import families_orthogonal as fo
        names |= {str(k) for k in getattr(fam_mod, "FAMILY_REGISTRY", {})}
        names |= {str(k) for k in getattr(fo, "ORTHOGONAL_FAMILIES", {})}
    except Exception:                                                   # pragma: no cover - env
        return frozenset()
    try:
        from research.family_policy import family_banned
        names = {n for n in names if not family_banned(n)}
    except Exception:                                                   # pragma: no cover - env
        pass
    return frozenset(names)


@lru_cache(maxsize=1)
def price_only_families() -> frozenset[str]:
    """The compiler's price-only vocabulary, so a donated family actually compiles as a
    STRUCTURED_HYPOTHESIS instead of falling through to prose and losing its instrument.
    Empty when the compiler will not import, which the report records rather than assumes."""
    try:
        from research.miner_candidate_compiler import _FAMILY_VOCAB
        return frozenset(str(k) for k in _FAMILY_VOCAB)
    except Exception:                                                   # pragma: no cover - env
        return frozenset()


def _may(symbol: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
        return bool(may_hypothesise(symbol))
    except Exception:                                                   # pragma: no cover - env
        return False


def donation_candidates(rows: list[dict[str, Any]], limit: int, p_max: float,
                        ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(candidates, refusals) for the strongest edge changes. Every refusal is counted.

    THE TWO-LANE DOOR IS APPLIED TO BOTH ENDS. A hypothesis of the form 'y responds to x, and the
    response just changed' conditions on x as much as it trades y, so a single-name equity at
    EITHER end is measured, published, and never donated: its cells would spend the shared
    family-wise budget that every FX and metals hypothesis then has to clear.
    """
    known, price_only = registered_families(), price_only_families()
    out: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for row in rows:
        src, dst = str(row["src"]), str(row["dst"])
        kind = str(row.get("kind") or "")
        fam = FAMILY_BY_KIND.get(kind, "")
        p = float(row.get("p_perm") or 1.0)
        if len(out) >= max(int(limit), 0):
            break
        # THE MANDATE IS THE FIRST DOOR, and the order matters: refusing an equity edge for its
        # p-value would record a statistical verdict where a categorical one belongs, and the
        # census of what the two-lane rule actually turned away would read as zero.
        if not _may(dst) or not _may(src):
            refused.append({"src": src, "dst": dst,
                            "why": "the two-lane mandate: one end of this edge is traded on news "
                                   "and earnings reaction, never hunted for statistical "
                                   "hypotheses. Measured and published here; never donated"})
            continue
        if p > p_max:
            refused.append({"src": src, "dst": dst, "p_perm": p,
                            "why": f"p_perm {p:.4g} above {p_max}: the permutation null already "
                                   "explains this scan, and donating it would charge every other "
                                   "cell on the docket for it"})
            continue
        if not fam:
            refused.append({"src": src, "dst": dst, "kind": kind,
                            "why": "no registered family expresses this change kind; it stays a "
                                   "measured row rather than take an invented one"})
            continue
        if fam not in known or (price_only and fam not in price_only):
            refused.append({"src": src, "dst": dst, "family": fam,
                            "why": "not in the family registry, banned, or outside the "
                                   "compiler's price-only vocabulary"})
            continue
        out.append({
            "source": SOURCE, "kind": "hypothesis", "symbol": dst, "symbols": [dst],
            "family": fam, "params": {}, "url": "",
            "title": f"edge change {src}->{dst} lag {row['lag']} {kind} at {row['t_change']}"[:120],
            "mechanism": (f"{src} led {dst} by {row['lag']} {row.get('grid', 'D')} bar(s) with "
                          f"beta {row.get('beta_pre')}; over the window ending "
                          f"{row.get('t_change')} that beta became {row.get('beta_post')} "
                          f"({kind}). The link itself is the object that changed, so the "
                          f"hypothesis is about {dst}'s behaviour in the new regime, not about "
                          f"the level of the correlation.")[:400],
            "evidence": {"edge": f"{src}->{dst}", "src": src, "dst": dst, "lag": row["lag"],
                         "clock": row.get("clock"), "grid": row.get("grid"),
                         "change_kind": kind, "t_change": row.get("t_change"),
                         "t_window_start": row.get("t_window_start"),
                         "window_bars": row.get("window"),
                         "beta_pre": row.get("beta_pre"), "beta_post": row.get("beta_post"),
                         "se_pre": row.get("se_pre"), "se_post": row.get("se_post"),
                         "corr_pre": row.get("corr_pre"), "corr_post": row.get("corr_post"),
                         "z": row.get("z"), "p_perm": row.get("p_perm"),
                         "n_perm": row.get("n_perm"), "n_obs": row.get("n"),
                         "graph_strength": row.get("graph_strength"),
                         "graph_status": row.get("graph_status"),
                         "screen": RULE}})
    return out, refused


def _donate(candidates: list[dict[str, Any]], tests_run: int) -> Any:
    """The seam. One import, one call, so a test can watch what leaves without a live intake."""
    from research.proposer_common import donate
    return donate(SOURCE, candidates, tests_run)


def _effective_trials(candidates: list[dict[str, Any]], tests_run: int) -> dict[str, Any]:
    """What this pass costs the SHARED family-wise budget, through the desk's own ledger."""
    row: dict[str, Any] = {"n_raw": len(candidates), "tests_run": tests_run,
                           "n_effective": None, "status": "UNMEASURED",
                           "why": "libs.research.trial_ledger unavailable"}
    try:
        from libs.research.trial_ledger import effective_count_of_records
        row["n_effective"] = round(float(effective_count_of_records(candidates)), 4)
        row["status"] = "measured"
        row["why"] = ""
    except Exception as exc:                                            # pragma: no cover - env
        row["why"] = f"{type(exc).__name__}: {exc}"
    return row


# =============================================================================================
# THE PROPRIETARY LATENT DATASETS (directive PART XVII A-D; audit 2026-10-06 rows 38-41, P5)
# =============================================================================================
#
# WHAT THEY ARE. Four datasets that exist in no feed: a CHINA INDUSTRIAL ACTIVITY state, a CHINA
# PHYSICAL GOLD DEMAND state, an ASIA INDUSTRIAL EXPORT state and an ASIA FUNDING / CARRY state.
# Each is a one-factor DYNAMIC FACTOR NOWCAST over the hard series the desk holds or will hold,
# estimated as a STATE-SPACE model and run through a KALMAN FILTER, published beside two simple
# baselines (an equal-weight z average and the first principal component) so the complex model
# has to beat something before anyone believes it.
#
# HOW IT STAYS POINT-IN-TIME, AND WHY THAT IS THE WHOLE DESIGN. Every input observation is
# placed at the instant it became KNOWABLE (its `available_time`, or its `revision_time` when it
# is a revision), never at the period it describes. Each input is z-scored against ITS OWN PRIOR
# observations only. The model is then re-estimated FROM SCRATCH at every release date on the
# data knowable at that date -- loadings, persistence and all -- so the state published for a
# date is exactly what the desk could have computed on that date. Those per-release-date VINTAGES
# are appended to `data/latent/<dataset>.vintages.jsonl` and never rewritten: a later vintage that
# re-describes the same week carries `revision_of` / `revision_delta`; it does not overwrite.
#
# RAGGED EDGES ARE THE NORMAL CASE. A weekly grid holds daily, 10-daily, weekly and monthly
# inputs; an input contributes a measurement only in the week it arrived, and the filter simply
# skips what is missing. Every vintage records, per input, whether it contributed, its loading,
# its precision weight, its age and its news contribution to the level.
#
# NOTHING IS SUBSTITUTED. An input the desk does not collect yet is listed with status
# NOT_YET_COLLECTED and the package that will deliver it; one whose terms are unconfirmed is
# BLOCKED_ON_TERMS; one whose key is missing is BLOCKED_ON_KEY. No price series is fused into any
# of the four states (`price_inputs` is empty on every dataset and says so); a dataset with fewer
# than two live hard inputs is published with that fact on it, not padded with a price proxy.
#
# WHERE IT GOES. Through the axis door (`data/axes/latent_<id>.json`, read unchanged by
# `alpha_dsl.FieldCatalogue` and `representation_forge`), into the lake envelope
# (`data/lake/series/latent_<id>.csv`, which `exogenous_conditioner` and the `alt:` regime
# modifier read), into `reports/LATENT_ALLOCATION_INTEL.json` (which `state_vector_build`
# merges onto the state vector's conditioning block), and as conditioner and regime CELLS donated
# through `proposer_common` with every look charged as a trial.

AXES_DIR = BASE / "data" / "axes"
LAKE_SERIES = BASE / "data" / "lake" / "series"
LATENT_DIR = BASE / "data" / "latent"
LATENT_INTEL = BASE / "reports" / "LATENT_ALLOCATION_INTEL.json"
ASIA_EVENTS = LATENT_DIR / "asia_events.json"
ASIA_EVENTS_LEDGER = LATENT_DIR / "asia_events.jsonl"
NULL_TRIALS = BASE / "data" / "null_pass_trials.jsonl"
SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
LATENT_SOURCE = "macro_state_latent"
SENSOR_ID = "macro_state_engine.latent"
#: The grid. Weekly, anchored on a Monday: fine enough for the 10-daily Korean prints and the
#: daily satellite/AIS series, coarse enough that a monthly print is not one point in thirty.
STEP_DAYS = 7
GRID_EPOCH = datetime(2000, 1, 3, tzinfo=UTC)
#: Prior observations an input needs before its z-score exists, and the window it is taken over.
Z_MIN_PRIOR, Z_WINDOW = 8, 104
#: Weeks the model is estimated over at each vintage (five years), and the history the first
#: pass reconstructs vintages for. Older vintages are not owed: the inputs barely reach back.
EST_STEPS, HISTORY_DAYS = 260, 730
#: Weeks an input's last measurement stays current, by cadence, for the baselines and the
#: published weights. The filter itself needs no such bound -- it decays the state by phi.
STALE_STEPS = {"daily": 2, "weekly": 3, "10-daily": 4, "monthly": 7, "policy": 9}
#: The prior loading a sign-declared input starts from, and the pseudo-count of weekly rows the
#: estimated loading must outweigh to move away from it (shrinkage toward the declared sign).
PRIOR_LOADING, SHRINK_ROWS = 0.5, 52
#: Vintages a dataset needs before its cells are screened, and regime children per pass.
MIN_CELL_VINTAGES, LATENT_CHILDREN_PER_PASS = 60, 12
#: Days a latent state stays current in the allocation intel.
INTEL_STALE_DAYS = 21
#: The latent build's OWN wall-clock budget (seconds), spent BEFORE the edge scan and never taken
#: out of the scan's `--budget-s`. The hourly leg's timeout carries both on top of each other.
LATENT_BUDGET_S = 150.0
#: THE DATASET RULE: every declared input must be consumed by the latent build within this
#: window, or it is published as UNFED (CRO D18, target 0).
FED_WINDOW_H = 24
#: The consumer name under which the latent build records its reads for the dataset-use census.
FED_CONSUMER = "macro_state_engine.latent"


@dataclass(frozen=True)
class LatentInput:
    """One declared input of a latent dataset, and where its observations come from."""

    id: str
    label: str
    #: `<axis doc stem>` under data/axes, or "" when nothing collects it yet.
    axis: str
    #: `series[<key>]` of the axis doc, or `row:<SYMBOL>:<column>` for a rows-shaped doc.
    series: str
    sign: int
    cadence: str
    #: The alt_proxies source whose TERMS gate binds this input ("" = not an alt_proxies row).
    terms_source: str = ""
    key_env: str = ""
    #: Who delivers it when it is absent: the package / organ named in the 2026-10-06 audit.
    pending: str = ""
    kind: str = "hard"


@dataclass(frozen=True)
class LatentSpec:
    id: str
    name: str
    directive: str
    entity: str
    geography: str
    meaning: str
    inputs: tuple[LatentInput, ...]
    #: MT5 instruments the state bears on, and the declared sign of the bearing.
    instruments: dict[str, int]

    @property
    def dataset_id(self) -> str:
        return f"latent_{self.id}"


def _pending(i: str, label: str, sign: int, cadence: str, who: str) -> LatentInput:
    return LatentInput(i, label, "", "", sign, cadence, pending=who)


LATENT_SPECS: tuple[LatentSpec, ...] = (
    LatentSpec(
        "cn_industrial", "China industrial activity state", "XVII.A", "China industry", "CN",
        "positive = Chinese heavy-industry activity running above its own recent history",
        (
            LatentInput("firms_thermal", "NASA FIRMS thermal detections over steel/coke/smelter "
                        "clusters", "alt_cn_firms_industrial", "total_count.value", 1, "daily",
                        terms_source="cn_firms_industrial", key_env="FIRMS_MAP_KEY"),
            LatentInput("portwatch_shanghai", "IMF PortWatch Shanghai port calls",
                        "alt_imf_portwatch_ports", "shanghai_portcalls.value", 1, "daily",
                        terms_source="imf_portwatch_ports"),
            LatentInput("portwatch_ningbo", "IMF PortWatch Ningbo-Zhoushan port calls",
                        "alt_imf_portwatch_ports", "ningbo_zhoushan_portcalls.value", 1, "daily",
                        terms_source="imf_portwatch_ports"),
            LatentInput("mot_port_teu", "MOT port container throughput", "alt_cn_mot_port_weekly",
                        "container_10k_teu.value", 1, "weekly", terms_source="cn_mot_port_weekly"),
            _pending("nbs_pmi_internals", "NBS PMI internals (new orders, production, "
                     "inventories)", 1, "monthly", "package P3: asia_parser + cn_official_tables "
                     "(NBS easyquery)"),
            _pending("nbs_industrial_production", "NBS industrial production", 1, "monthly",
                     "package P3: cn_official_tables"),
            _pending("shfe_inventory", "SHFE warehouse stocks (copper/aluminium/zinc)", -1,
                     "weekly", "package P2: free_stack SHFE weekly warehouse parser"),
            _pending("shfe_positioning", "SHFE member long/short concentration", 1, "daily",
                     "package P2: free_stack pm<date>.dat member ranks"),
            _pending("shfe_curve", "SHFE copper backwardation", 1, "daily",
                     "package P2: free_stack kx<date>.dat curves"),
            _pending("customs_quantities", "China customs import quantities (ore, copper "
                     "concentrate)", 1, "monthly", "package P3: customs query tool"),
            _pending("freight_scfi", "SCFI/CCFI route indices", 1, "weekly",
                     "package P4: alt_proxies SSE freight"),
            _pending("rail_freight", "China rail freight", 1, "monthly",
                     "package P4: NBS rail freight"),
            _pending("power_output", "China power generation", 1, "monthly",
                     "package P4: NBS energy output"),
            _pending("procurement_orders", "CCGP procurement order index", 1, "weekly",
                     "package P4: CCGP award aggregation"),
            _pending("s5p_no2", "Sentinel-5P NO2 over industrial clusters", 1, "daily",
                     "package P4: S5P parser (BLOCKED_ON_KEY CDSE_TOKEN)"),
            _pending("corporate_supply_chain", "corporate supply-chain activity", 1, "monthly",
                     "package P4: CNINFO/CCGP Tianyancha substitute"),
        ),
        {"XCUUSD": 1, "AUDUSD": 1, "NZDUSD": 1, "AUS200": 1, "CHINAH": 1, "HK50": 1,
         "USDCNH": -1}),
    LatentSpec(
        "cn_physical_gold", "China physical gold demand state", "XVII.B", "China gold demand",
        "CN", "positive = Asian physical gold offtake running above its own recent history",
        (
            LatentInput("sge_premium", "Shanghai Gold Exchange premium over loco London",
                        "alt_cn_sge_premium", "premium_pct.value", 1, "daily",
                        terms_source="cn_sge_premium"),
            LatentInput("india_gold_imports", "India monthly gold imports (regional neighbour "
                        "demand, not China; labelled)", "alt_in_gold_imports",
                        "gold_imports_usd_bn.value", 1, "monthly",
                        terms_source="in_gold_imports"),
            _pending("sge_benchmark", "Shanghai Gold Benchmark AM/PM and SGE volume", 1, "daily",
                     "package P1: fetch_sge_premium benchmark backfill"),
            _pending("china_gold_imports", "China / Hong Kong gold imports (C&SD, customs)", 1,
                     "monthly", "package P3: customs query tool; HK C&SD not collected"),
            _pending("swiss_gold_exports", "Swiss gold exports to China/HK/India", 1, "monthly",
                     "registry row swiss_customs_gold only (no parser)"),
            _pending("lbma_vaults", "LBMA London vault holdings", -1, "monthly",
                     "registry row lbma_vault only (no parser)"),
            _pending("asia_etf_flows", "Asian gold ETF flows", 1, "monthly",
                     "registry row wgc_etf_flows only (no parser)"),
            _pending("pboc_gold_reserves", "PBOC reported gold reserves", 1, "monthly",
                     "package P3: SAFE reserves table"),
            _pending("comex_inventory", "COMEX gold inventories", -1, "daily",
                     "not collected (CME public warehouse report)"),
            _pending("shfe_gold_basis", "SHFE gold futures basis", 1, "daily",
                     "package P2: free_stack kx<date>.dat"),
        ),
        {"XAUUSD": 1, "XAGUSD": 1}),
    LatentSpec(
        "asia_export", "Asia industrial export state", "XVII.C", "Asian manufacturing exports",
        "ASIA", "positive = Asian export volumes running above their own recent history",
        (
            LatentInput("kr_exports_daily_avg", "Korea 1-10/1-20 day exports, daily average y/y",
                        "alt_kr_exports_early", "daily_avg_yoy.value", 1, "10-daily",
                        terms_source="kr_exports_early"),
            LatentInput("kr_semis_exports", "Korea semiconductor exports y/y",
                        "alt_kr_exports_early", "semis_yoy.value", 1, "10-daily",
                        terms_source="kr_exports_early"),
            LatentInput("busan_teu", "Busan Port Authority container throughput y/y",
                        "alt_kr_busan_port", "container_yoy.value", 1, "monthly",
                        terms_source="kr_busan_port"),
            LatentInput("kr_mof_teu", "Korea MOF container TEU", "alt_kr_mof_container_teu",
                        "container_teu.value", 1, "monthly", terms_source="kr_mof_container_teu",
                        key_env="DATA_GO_KR_KEY"),
            LatentInput("sg_port_teu", "Singapore container throughput (SingStat)",
                        "alt_sg_port_throughput", "container_throughput_k_teu.value", 1,
                        "monthly", terms_source="sg_port_throughput"),
            LatentInput("portwatch_busan", "IMF PortWatch Busan port calls",
                        "alt_imf_portwatch_ports", "busan_portcalls.value", 1, "daily",
                        terms_source="imf_portwatch_ports"),
            LatentInput("portwatch_singapore", "IMF PortWatch Singapore port calls",
                        "alt_imf_portwatch_ports", "singapore_portcalls.value", 1, "daily",
                        terms_source="imf_portwatch_ports"),
            _pending("tw_export_orders", "Taiwan export orders (MOEA)", 1, "monthly",
                     "not collected (MOEA statistics; no registry parser)"),
            _pending("sg_nodx", "Singapore NODX (Enterprise Singapore)", 1, "monthly",
                     "not collected"),
            _pending("cn_exports", "China customs exports", 1, "monthly",
                     "package P3: customs query tool"),
            _pending("jp_trade", "Japan MOF trade statistics", 1, "monthly",
                     "package P6: countries/jp data plane"),
            _pending("semis_measures", "semiconductor billings / memory prices", 1, "monthly",
                     "not collected (SIA/WSTS)"),
        ),
        {"USDKRW": -1, "AUDUSD": 1, "JPN225": 1, "NAS100": 1, "XCUUSD": 1}),
    LatentSpec(
        "asia_funding", "Asia funding / carry state", "XVII.D", "Asian funding and carry",
        "ASIA", "positive = Asian funding cheap relative to USD: the JPY-funded carry trade "
                "is paid more than its own recent history",
        (
            LatentInput("usdjpy_policy_differential", "BIS policy-rate differential USD-JPY",
                        "bis", "row:USDJPY:carry_differential", 1, "policy",
                        terms_source="bis_policy_rates"),
            LatentInput("audjpy_policy_differential", "BIS policy-rate differential AUD-JPY",
                        "bis", "row:AUDJPY:carry_differential", 1, "policy",
                        terms_source="bis_policy_rates"),
            _pending("shibor_dr007", "SHIBOR / DR007 onshore funding", -1, "daily",
                     "package P3: chinamoney SHIBOR / DR007 JSON"),
            _pending("cfets_fix_surprise", "CFETS fix surprise vs model-implied fix", -1, "daily",
                     "package P3: CFETS fix-surprise model"),
            _pending("cnh_hibor", "CNH HIBOR / offshore funding", -1, "daily",
                     "package P6: HKMA open API semantics"),
            _pending("hkma_aggregate_balance", "HKMA aggregate balance / HIBOR spread", 1,
                     "daily", "package P6: HKMA open API semantics"),
            _pending("boj_jgb", "BOJ balance sheet / JGB yields", -1, "daily",
                     "package P6: BOJ stat-search flat files"),
            _pending("tfx_swap_points", "TFX JPY swap points", 1, "daily",
                     "package P6: TFX swap points"),
            _pending("krw_carry", "KRW policy-rate differential", 1, "policy",
                     "BIS carries KRW but the axis doc has no USDKRW row (bis ingest)"),
            _pending("broker_swaps", "broker swap rates as a PIT history", 1, "daily",
                     "not recorded as a history (universe.json holds a snapshot only)"),
        ),
        {"USDJPY": 1, "AUDJPY": 1, "NZDJPY": 1}),
)
LATENT_BY_ID: dict[str, LatentSpec] = {s.id: s for s in LATENT_SPECS}


# ---------------------------------------------------------------------------- input loading
def _step(t: datetime) -> int:
    return int((t - GRID_EPOCH).total_seconds() // (STEP_DAYS * 86400))


def _step_start(step: int) -> datetime:
    return GRID_EPOCH + timedelta(days=STEP_DAYS * step)


def _iso_t(v: Any) -> datetime | None:
    if v is None or v == "":
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _terms(source_id: str) -> str:
    """The alt_proxies TERMS verdict for a source; anything unreadable is NOT confirmed. A source
    that alt_proxies does not fetch itself (BIS, read from the axis door) is judged by its row in
    the same TERMS table; a source in neither is `unknown_source`, i.e. blocked."""
    try:
        from research import alt_proxies
        src = alt_proxies.BY_ID.get(source_id)
        if src is not None:
            return str(src.terms)
        row = alt_proxies.TERMS.get(source_id)
        return str(row[0]) if row is not None else "unknown_source"
    except Exception as exc:                                            # pragma: no cover - env
        return f"unreadable:{type(exc).__name__}"


def _scan_rows(text: str, series: str) -> list[dict[str, Any]]:
    """The flat `rows` objects of one symbol, found by scanning the doc's text."""
    import re
    _, sym, col = series.split(":", 2)
    out: list[dict[str, Any]] = []
    pat = re.compile(r'\{[^{}]*?"symbol":\s*"' + re.escape(sym) + r'"[^{}]*\}')
    num = re.compile(r'"' + re.escape(col) + r'":\s*(-?[0-9][0-9.eE+-]*)')
    kpat = re.compile(r'"knowable_at":\s*"([0-9-]+)"')
    for m in pat.finditer(text):
        body = m.group(0)
        k, v = kpat.search(body), num.search(body)
        if k and v:
            out.append({"symbol": sym, "knowable_at": k.group(1), col: _f(v.group(1))})
    return out


def _obs_from_doc(doc: dict[str, Any], series: str) -> list[dict[str, Any]] | None:
    """Observations of one input from an axis doc, or None when the doc lacks the series."""
    out: list[dict[str, Any]] = []
    if series.startswith("row:"):
        _, sym, col = series.split(":", 2)
        rows = doc.get("rows")
        if not isinstance(rows, list):
            return None
        for r in rows:
            if not isinstance(r, dict) or str(r.get("symbol")) != sym:
                continue
            k = str(r.get("knowable_at") or "")
            v = _f(r.get(col))
            if len(k) != 10 or v is None:
                continue          # a month-only stamp cannot be placed honestly on a day
            t = _iso_t(k)
            if t is None:
                continue
            # A policy-rate row dated D is acted on from the next day: no same-day join.
            out.append({"arrival": t + timedelta(days=1), "value": v, "period": k,
                        "vintage": f"{sym}:{k}", "revision": False,
                        "pit_quality": "bulk_current_vintage"})
        return out if out else None
    s = (doc.get("series") or {}).get(series) if isinstance(doc.get("series"), dict) else None
    if not isinstance(s, dict):
        return None
    seen: set[str] = set()
    for p in s.get("points") or []:
        if not isinstance(p, dict):
            continue
        v = _f(p.get("v", p.get("value")))
        a, r = _iso_t(p.get("available_time")), _iso_t(p.get("revision_time"))
        if v is None or a is None:
            continue          # no availability stamp: never joined
        period = str(p.get("d") or "")
        rev = period in seen
        seen.add(period)
        arrival = max(a, r) if (r is not None and rev) else a
        out.append({"arrival": arrival, "value": v, "period": period,
                    "vintage": str(p.get("vintage_id") or f"{period}:{arrival.isoformat()}"),
                    "revision": rev, "pit_quality": str(p.get("pit_quality") or "pit")})
    return out


def load_input(inp: LatentInput, axes_dir: Path, docs: dict[str, Any],
               environ: dict[str, str] | None = None,
               ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(observations, availability record) for one input. Every refusal is named."""
    env = os.environ if environ is None else environ
    rec: dict[str, Any] = {"input": inp.id, "label": inp.label, "kind": inp.kind,
                           "sign": inp.sign, "cadence": inp.cadence,
                           "axis": inp.axis or None, "series": inp.series or None}
    if not inp.axis:
        rec.update({"status": "NOT_YET_COLLECTED", "why": inp.pending})
        return [], rec
    if inp.terms_source:
        terms = _terms(inp.terms_source)
        rec["terms"] = terms
        if terms != "confirmed":
            rec.update({"status": f"BLOCKED_ON_TERMS:{terms}",
                        "why": (f"alt_proxies TERMS[{inp.terms_source}] is {terms}; the input "
                                "is not fused until a human confirms the source's terms")})
            return [], rec
    if inp.series.startswith("row:"):
        # A rows-shaped doc (BIS is 81 MB, 465k rows) is SCANNED for the one symbol rather than
        # parsed whole: a full json.load peaks near 400 MB, which the 8 GB build host cannot
        # spare beside the live terminal. The regex reads the same flat row objects.
        key = f"text:{inp.axis}"
        if key not in docs:
            try:
                docs[key] = (axes_dir / f"{inp.axis}.json").read_text("utf-8-sig")
            except OSError:
                docs[key] = None
        doc = ({"rows": _scan_rows(docs[key], inp.series)} if isinstance(docs[key], str)
               else None)
    else:
        if inp.axis not in docs:
            docs[inp.axis] = _read_json(axes_dir / f"{inp.axis}.json")
        doc = docs[inp.axis]
    if not isinstance(doc, dict):
        if inp.key_env and not env.get(inp.key_env):
            rec.update({"status": f"BLOCKED_ON_KEY:{inp.key_env}",
                        "why": f"{inp.key_env} is not set on this host and no axis doc exists"})
        else:
            rec.update({"status": "UNMEASURED",
                        "why": f"data/axes/{inp.axis}.json absent on this host: its producer has "
                               "not published it here"})
        return [], rec
    obs = _obs_from_doc(doc, inp.series)
    if obs is None:
        rec.update({"status": "UNMEASURED",
                    "why": f"data/axes/{inp.axis}.json carries no `{inp.series}`"})
        return [], rec
    obs.sort(key=lambda o: o["arrival"])
    rec.update({"status": "COLLECTED", "n_obs": len(obs),
                "first_arrival": obs[0]["arrival"].isoformat(),
                "last_arrival": obs[-1]["arrival"].isoformat(),
                "n_revisions": sum(1 for o in obs if o["revision"]),
                "backfill_share": round(sum(1 for o in obs if o["pit_quality"] == "backfill")
                                        / len(obs), 4)})
    return obs, rec


# ---------------------------------------------------------------------------- the nowcast
class _Prepared:
    """One input's observations bucketed by arrival week, with each week's PIT z-score stats."""

    def __init__(self, inp: LatentInput, obs: list[dict[str, Any]]) -> None:
        self.inp = inp
        self.by_step: dict[int, list[dict[str, Any]]] = {}
        for o in obs:
            self.by_step.setdefault(_step(o["arrival"]), []).append(o)
        self.steps = sorted(self.by_step)
        # Each week's prior distribution comes from the FULL aggregates of earlier weeks only,
        # which are final by the time this week begins.
        self.stats: dict[int, tuple[float, float, int]] = {}
        hist: list[float] = []
        for s in self.steps:
            prior = hist[-Z_WINDOW:]
            if prior:
                mu = float(np.mean(prior))
                sd = float(np.std(prior, ddof=1)) if len(prior) > 1 else 0.0
                self.stats[s] = (mu, sd, len(prior))
            hist.append(float(np.mean([o["value"] for o in self.by_step[s]])))

    def z_at(self, step: int, cutoff: datetime) -> tuple[float | None, list[dict[str, Any]]]:
        """This week's z on what had arrived by `cutoff`, and the observations it used."""
        got = [o for o in self.by_step.get(step, ()) if o["arrival"] <= cutoff]
        st = self.stats.get(step)
        if not got or st is None or st[2] < Z_MIN_PRIOR:
            return None, got
        x = float(np.mean([o["value"] for o in got]))
        mu, sd, _n = st
        if sd <= 1e-12:
            z = 0.0 if abs(x - mu) <= 1e-12 else float(np.sign(x - mu)) * 3.0
        else:
            z = (x - mu) / sd
        return float(np.clip(z, -4.0, 4.0)), got


def _panel(prep: list[_Prepared], cutoff: datetime, s0: int, s1: int,
           ) -> tuple[NDArray[np.float64], dict[int, list[list[dict[str, Any]]]]]:
    T, N = s1 - s0 + 1, len(prep)
    Y = np.full((T, N), np.nan)
    used: dict[int, list[list[dict[str, Any]]]] = {}
    for j, p in enumerate(prep):
        lo, hi = bisect_left(p.steps, s0), bisect_right(p.steps, s1)
        for s in p.steps[lo:hi]:
            z, got = p.z_at(s, cutoff)
            if z is not None:
                Y[s - s0, j] = z
                if s == s1:
                    used.setdefault(j, []).append(got)
    return Y, used


def _ffill(Y: NDArray[np.float64], limits: list[int]) -> NDArray[np.float64]:
    F = Y.copy()
    for j in range(F.shape[1]):
        last, age = np.nan, 10 ** 9
        for t in range(F.shape[0]):
            if np.isfinite(Y[t, j]):
                last, age = Y[t, j], 0
            else:
                age += 1
                F[t, j] = last if age <= limits[j] else np.nan
    return F


def _pca(F: NDArray[np.float64], signs: NDArray[np.float64],
         ) -> tuple[NDArray[np.float64] | None, float, int, NDArray[np.float64] | None]:
    """First principal component of the forward-filled panel: (vector, eigenvalue, rows, scores).

    Rows need two live inputs; a missing cell is read as the input's own mean (0 in z units).
    The sign is aligned with the declared signs so 'up' means what the dataset says it means.
    """
    live = np.isfinite(F)
    rows = live.sum(axis=1) >= 2
    cols = live[rows].any(axis=0) if rows.any() else np.zeros(F.shape[1], bool)
    if int(rows.sum()) < 20 or int(cols.sum()) < 2:
        return None, 0.0, int(rows.sum()), None
    X = np.where(live, F, 0.0)[rows][:, cols]
    C = (X.T @ X) / X.shape[0]
    w, V = np.linalg.eigh(C)
    v = np.zeros(F.shape[1])
    v[cols] = V[:, -1]
    ev = float(w[-1])
    if float(np.dot(v, signs)) < 0:
        v = -v
    if ev <= 1e-12:
        return None, 0.0, int(rows.sum()), None
    scores = np.where(live, F, 0.0) @ v / np.sqrt(ev)
    scores[~(live.sum(axis=1) >= 1)] = np.nan
    return v, ev, int(rows.sum()), scores


def nowcast(prep: list[_Prepared], cutoff: datetime) -> dict[str, Any] | None:
    """The state AS KNOWABLE AT `cutoff`: re-estimated, filtered, decomposed. None if empty."""
    s1 = _step(cutoff)
    s0 = s1 - EST_STEPS + 1
    Y, used = _panel(prep, cutoff, s0, s1)
    if not np.isfinite(Y).any():
        return None
    signs = np.array([float(p.inp.sign) for p in prep])
    limits = [STALE_STEPS.get(p.inp.cadence, 4) for p in prep]
    F = _ffill(Y, limits)
    v, ev, n_rows, scores = _pca(F, signs)
    prior = signs * PRIOR_LOADING
    if v is not None:
        est = np.clip(v * np.sqrt(ev), -0.95, 0.95)
        wgt = n_rows / (n_rows + SHRINK_ROWS)
        lam = np.where(np.isfinite(F).any(axis=0), wgt * est + (1.0 - wgt) * prior, prior)
        method = "kalman_dfm_pca_loadings_shrunk"
    else:
        lam = prior
        method = "kalman_dfm_prior_loadings"
    lam = np.clip(lam, -0.95, 0.95)
    r = np.maximum(1.0 - lam ** 2, 0.1)
    phi = 0.9
    if scores is not None:
        a, b = scores[:-1], scores[1:]
        ok = np.isfinite(a) & np.isfinite(b)
        if int(ok.sum()) >= 20 and float(np.std(a[ok])) > 0 and float(np.std(b[ok])) > 0:
            phi = float(np.clip(np.corrcoef(a[ok], b[ok])[0, 1], 0.5, 0.98))
    q = 1.0 - phi ** 2
    f, P = 0.0, 1.0
    path: list[float] = []
    contrib = np.zeros(len(prep))
    carry = f_pred = P_pred = 0.0
    for t in range(Y.shape[0]):
        f, P = phi * f, phi * phi * P + q
        if t == Y.shape[0] - 1:
            carry, f_pred, P_pred = f, f, P
        for jj in np.flatnonzero(np.isfinite(Y[t])):
            S = lam[jj] * lam[jj] * P + r[jj]
            K = P * lam[jj] / S
            inc = K * (Y[t, jj] - lam[jj] * f)
            f += inc
            P -= K * lam[jj] * P
            if t == Y.shape[0] - 1:
                contrib[jj] += inc
        path.append(f)
    T = len(path)
    level = path[-1]
    delta = (path[-1] - path[-5]) if T >= 5 else None
    accel = ((path[-1] - path[-5]) - (path[-5] - path[-9])) if T >= 9 else None
    fresh = np.isfinite(F[-1])
    ew = (float(np.mean(signs[fresh] * F[-1][fresh])) if fresh.any() else None)
    pca_level = (float(scores[-1]) if scores is not None and np.isfinite(scores[-1]) else None)
    prec = np.where(fresh, lam ** 2 / r, 0.0)
    wsum = float(prec.sum())
    comps: list[dict[str, Any]] = []
    revised: list[str] = []
    for j, p in enumerate(prep):
        got = [o for grp in used.get(j, []) for o in grp]
        last = None
        for s in reversed(p.steps):
            if s <= s1:
                cand = [o for o in p.by_step[s] if o["arrival"] <= cutoff]
                if cand:
                    last = cand[-1]
                    break
        if any(o["revision"] for o in got):
            revised.append(p.inp.id)
        comps.append({
            "input": p.inp.id, "loading": round(float(lam[j]), 4),
            "z": None if not np.isfinite(Y[-1, j]) else round(float(Y[-1, j]), 4),
            "weight": round(float(prec[j] / wsum), 4) if wsum > 0 else 0.0,
            "contribution": round(float(contrib[j]), 6),
            "last_arrival": None if last is None else last["arrival"].isoformat(),
            "age_days": (None if last is None else
                         round((cutoff - last["arrival"]).total_seconds() / 86400.0, 2)),
            "fresh": bool(fresh[j]), "n_this_week": len(got),
            "contradicts_declared_sign": bool(v is not None and lam[j] * signs[j] < 0)})
    n_used = int(sum(1 for c in comps if c["fresh"]))
    return {"level": float(level), "uncertainty": float(np.sqrt(max(P, 0.0))),
            "carry": float(carry), "f_pred": float(f_pred), "P_pred": float(P_pred),
            "delta": None if delta is None else float(delta),
            "acceleration": None if accel is None else float(accel),
            "baseline_level": ew, "pca_level": pca_level, "components": comps,
            "inputs_revised": revised, "n_inputs_used": n_used,
            "model": {"method": method, "phi": round(phi, 4), "q": round(q, 6),
                      "pca_rows": n_rows, "pca_eigenvalue": round(ev, 4),
                      "estimation_weeks": EST_STEPS, "shrink_rows": SHRINK_ROWS},
            "step": s1}


def _ledger_path(spec: LatentSpec, root: Path) -> Path:
    return root / f"{spec.dataset_id}.vintages.jsonl"


def read_ledger(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text("utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        if line.strip():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _hit(sign_obs: float, level: float | None) -> int | None:
    if level is None or level == 0 or sign_obs == 0:
        return None
    return int(np.sign(sign_obs) == np.sign(level))


def build_vintages(spec: LatentSpec, prep: list[_Prepared], ledger: list[dict[str, Any]],
                   now: datetime, deadline: float) -> tuple[list[dict[str, Any]], int]:
    """New vintages after the ledger's last, chronologically, until the deadline. Returns
    (records, release dates still owed)."""
    last_k = _iso_t(ledger[-1]["knowable_at"]) if ledger else None
    floor = now - timedelta(days=HISTORY_DAYS)
    dates: set[str] = set()
    for p in prep:
        for s, obs in p.by_step.items():
            if p.stats.get(s, (0, 0, 0))[2] < Z_MIN_PRIOR:
                continue
            for o in obs:
                a = o["arrival"]
                if a <= now and a >= floor and (last_k is None or a > last_k):
                    dates.add(a.date().isoformat())
    todo = sorted(dates)
    prev = ledger[-1] if ledger else None
    by_week: dict[str, dict[str, Any]] = {}
    for r in ledger[-60:]:
        by_week[str(r.get("event_time"))] = r
    hist_levels = [float(r["level"]) for r in ledger[-EST_STEPS:] if _f(r.get("level")) is not None]
    comparison = dict((prev or {}).get("comparison") or {
        "kalman": [0, 0], "baseline": [0, 0], "pca": [0, 0]})
    out: list[dict[str, Any]] = []
    merged = sorted(((o["arrival"], j, o) for j, p in enumerate(prep) for s in p.steps
                     for o in p.by_step[s]), key=lambda m: m[0])
    arrivals = [m[0] for m in merged]
    ptr = bisect_right(arrivals, last_k) if last_k is not None else 0
    done = 0
    for day in todo:
        if time.monotonic() > deadline:
            break
        end = datetime.fromisoformat(day).replace(tzinfo=UTC) + timedelta(days=1, seconds=-1)
        cutoff = min(end, now)
        hi = bisect_right(arrivals, cutoff)
        new_obs = [(prep[j], o) for _a, j, o in merged[ptr:hi]]
        ptr = max(ptr, hi)
        done += 1
        if not new_obs:
            continue
        knowable = max(o["arrival"] for _p, o in new_obs)
        nc = nowcast(prep, cutoff)
        if nc is None:
            last_k = knowable
            continue
        # OUT-OF-SAMPLE SCORE, before this vintage's update: did each method's previous level
        # point the way each arriving observation went? Same question for all three methods.
        if prev is not None:
            for p, o in new_obs:
                z, _ = p.z_at(_step(o["arrival"]), o["arrival"])
                if z is None:
                    continue
                for m, key in (("kalman", "level"), ("baseline", "baseline_level"),
                               ("pca", "pca_level")):
                    h = _hit(p.inp.sign * z, _f(prev.get(key)))
                    if h is not None:
                        comparison[m] = [comparison[m][0] + h, comparison[m][1] + 1]
        week = (_step_start(nc["step"]) + timedelta(days=STEP_DAYS - 1)).date().isoformat()
        expected = nc["f_pred"]
        sd_pred = float(np.sqrt(max(nc["P_pred"], 1e-12)))
        raw = nc["level"] - expected
        pct = (float(np.mean(np.asarray(hist_levels[-EST_STEPS:]) <= nc["level"]))
               if len(hist_levels) >= 20 else None)
        same = by_week.get(week)
        provenance = hashlib.sha256(json.dumps(
            [spec.dataset_id, knowable.isoformat(),
             sorted(o["vintage"] for _p, o in new_obs), nc["model"]],
            sort_keys=True, default=str).encode()).hexdigest()
        obs_id = provenance[:24]
        pit = ("backfill_input" if any(o["pit_quality"] == "backfill" for _p, o in new_obs)
               else "realtime" if (now - knowable) <= timedelta(days=2) else
               "reconstructed_pit")
        rec = {
            "dataset_id": spec.dataset_id, "observation_id": obs_id, "sensor_id": SENSOR_ID,
            "source_id": SOURCE, "entity": spec.entity, "geography": spec.geography,
            "asset_domain": "macro_latent", "metric": f"{spec.id}_level",
            "unit": "z (unit-variance latent factor)",
            "value": round(nc["level"], 6), "level": round(nc["level"], 6),
            "event_time": week, "scheduled_time": None,
            "publication_time": knowable.isoformat(), "knowable_at": knowable.isoformat(),
            "received_at": now.isoformat(timespec="seconds"),
            "parse_complete_at": now.isoformat(timespec="seconds"),
            "expected_value": round(expected, 6), "consensus": None,
            "consensus_status": "UNMEASURED: a proprietary latent has no consensus",
            "seasonal_expected": None,
            "raw_surprise": round(raw, 6), "surprise_z": round(raw / sd_pred, 4),
            "percentile": None if pct is None else round(pct, 4),
            "delta": None if nc["delta"] is None else round(nc["delta"], 6),
            "acceleration": None if nc["acceleration"] is None else round(nc["acceleration"], 6),
            "revision_of": None if same is None else same.get("observation_id"),
            "revision_delta": (None if same is None or _f(same.get("level")) is None
                               else round(nc["level"] - float(same["level"]), 6)),
            "measurement_uncertainty": round(nc["uncertainty"], 6),
            "uncertainty": round(nc["uncertainty"], 6),
            "source_confidence": round(nc["n_inputs_used"] / max(1, len(spec.inputs)), 4),
            "commercial_rights": "derived dataset; inherits each input's licence",
            "licence": "internal derived; see inputs[].terms in the dataset metadata",
            "provenance_hash": provenance,
            "raw_pointer": f"desks/mt5/data/latent/{spec.dataset_id}.vintages.jsonl",
            "baseline_level": None if nc["baseline_level"] is None
            else round(nc["baseline_level"], 6),
            "pca_level": None if nc["pca_level"] is None else round(nc["pca_level"], 6),
            "carry": round(nc["carry"], 6), "n_inputs_used": nc["n_inputs_used"],
            "components": nc["components"], "model": nc["model"],
            "revision_state": ("revises_same_week" if same is not None else
                               "input_revised" if nc["inputs_revised"] else "first_estimate"),
            "inputs_revised": nc["inputs_revised"], "pit_quality": pit,
            "comparison": {k: list(v) for k, v in comparison.items()},
        }
        out.append(rec)
        by_week[week] = rec
        hist_levels.append(nc["level"])
        prev = rec
        last_k = knowable
    return out, len(todo) - done


def _comparison_verdict(rec: dict[str, Any] | None) -> dict[str, Any]:
    comp = (rec or {}).get("comparison") or {}
    rates = {m: (round(h / n, 4) if n else None, n) for m, (h, n) in comp.items()}
    k, b = rates.get("kalman", (None, 0)), rates.get("baseline", (None, 0))
    if k[0] is None or b[0] is None or min(k[1], b[1]) < 30:
        verdict = "UNMEASURED: fewer than 30 scored arrivals for one of the methods"
    else:
        verdict = ("kalman_beats_baseline" if k[0] > b[0] else
                   "baseline_holds: the complex model has not beaten equal-weight z")
    return {"oos_sign_hit_rate": {m: {"rate": r, "n": n} for m, (r, n) in rates.items()},
            "verdict": verdict,
            "rule": ("before each vintage's update, each method's previous level is scored on "
                     "whether it pointed the way each arriving input observation went (sign of "
                     "declared-sign x z); the same question for all three methods")}


def axis_doc_latent(spec: LatentSpec, ledger: list[dict[str, Any]], inputs: list[dict[str, Any]],
                    now: datetime) -> dict[str, Any]:
    """The axis door's shape: `series[<col>].points` with `available_time` on every point."""
    cols = ("level", "surprise_z", "raw_surprise", "uncertainty", "acceleration", "delta",
            "baseline_level", "pca_level")
    series: dict[str, Any] = {}
    tail = ledger[-1500:]
    for col in cols:
        pts = [{"d": r["event_time"], "v": r[col], "available_time": r["knowable_at"],
                "published_time": r["publication_time"], "event_time": r["event_time"],
                "first_seen_at": r.get("received_at"),
                "revision_time": r["knowable_at"] if r.get("revision_of") else None,
                "vintage_id": r["observation_id"], "pit_quality": r.get("pit_quality")}
               for r in tail if _f(r.get(col)) is not None]
        if pts:
            series[col] = {"what": f"{spec.name}: {col}", "n": len(pts), "first": pts[0]["d"],
                           "last": pts[-1]["d"], "points": pts}
    return {"axis": "latent_state", "id": spec.dataset_id, "source": SOURCE,
            "at": now.isoformat(timespec="seconds"), "directive": spec.directive,
            "name": spec.name, "meaning": spec.meaning, "entity": spec.entity,
            "geography": spec.geography, "n_series": len(series),
            "pit_fields": ["event_time", "published_time", "available_time", "first_seen_at",
                           "revision_time", "vintage_id"],
            "shape": "series[<column>].points, joined on available_time (= knowable_at)",
            "vintage_note": ("one point per release date, computed on the inputs knowable at "
                             "that date and appended; a later vintage of the same week carries "
                             "revision_of and never overwrites"),
            "inputs": inputs, "price_inputs": [],
            "price_proxy_policy": ("no price series is fused into this state; a dataset short "
                                   "of hard inputs says so in `inputs` instead"),
            "instruments": spec.instruments, "series": series}


LAKE_COLUMNS = ("event_time", "available_time", "published_time", "retrieval_time",
                "revision_time", "source_id", "vintage_id", "value", "level", "surprise_z",
                "raw_surprise", "acceleration", "delta", "uncertainty", "baseline_level",
                "pca_level", "pace", "pit_quality")


def write_lake(spec: LatentSpec, ledger: list[dict[str, Any]], root: Path) -> Path:
    """`data/lake/series/latent_<id>.csv` in the PIT envelope `exogenous_conditioner` reads."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(LAKE_COLUMNS)
    for r in ledger:
        w.writerow([r.get("event_time"), r.get("knowable_at"), r.get("publication_time"),
                    r.get("received_at"), r.get("knowable_at") if r.get("revision_of") else "",
                    SOURCE, r.get("observation_id"), r.get("level"), r.get("level"),
                    r.get("surprise_z"), r.get("raw_surprise"), r.get("acceleration"),
                    r.get("delta"), r.get("uncertainty"), r.get("baseline_level"),
                    r.get("pca_level"), r.get("delta"), r.get("pit_quality")])
    path = root / f"{spec.dataset_id}.csv"
    _atomic(path, buf.getvalue())
    return path


def allocation_intel_latent(ledgers: dict[str, list[dict[str, Any]]], now: datetime,
                            days: int = 30) -> dict[str, Any]:
    """Per instrument: every latent state bearing on it, as knowable now and over 30 days.

    tilt = mean(sign * clip(level, +-3)) over the states that are not stale. Read-only context:
    it sizes nothing, and its authority is none until a dimension admission says otherwise."""
    inst: dict[str, dict[str, Any]] = {}
    day_list = [(now - timedelta(days=k)).date() for k in range(days - 1, -1, -1)]
    for sid, ledger in ledgers.items():
        spec = LATENT_BY_ID[sid]
        stamps: list[tuple[datetime, dict[str, Any]]] = []
        for r in ledger:
            tk = _iso_t(r.get("knowable_at"))
            if tk is not None:
                stamps.append((tk, r))
        for sym, sign in spec.instruments.items():
            e = inst.setdefault(sym, {"components": [], "daily": {}})
            for day in day_list:
                cut = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=UTC)
                known = [r for t, r in stamps if t <= cut]
                if not known:
                    continue
                r = known[-1]
                t = _iso_t(r["knowable_at"])
                if t is None or (cut - t).days > INTEL_STALE_DAYS:
                    continue
                e["daily"].setdefault(day.isoformat(), []).append(
                    sign * float(np.clip(float(r["level"]), -3.0, 3.0)))
            if stamps:
                r = stamps[-1][1]
                age = (now - stamps[-1][0]).total_seconds() / 86400.0
                e["components"].append({
                    "dataset_id": spec.dataset_id, "level": r.get("level"),
                    "surprise_z": r.get("surprise_z"), "acceleration": r.get("acceleration"),
                    "uncertainty": r.get("uncertainty"), "knowable_at": r.get("knowable_at"),
                    "event_time": r.get("event_time"), "sign": sign, "sign_basis": "declared",
                    "n_inputs_used": r.get("n_inputs_used"), "age_days": round(age, 2),
                    "stale": age > INTEL_STALE_DAYS, "pit_quality": r.get("pit_quality")})
    out: dict[str, Any] = {}
    for sym, e in sorted(inst.items()):
        daily = [{"date": d, "tilt": round(sum(v) / len(v), 4), "n": len(v)}
                 for d, v in sorted(e["daily"].items())]
        out[sym] = {"tilt": daily[-1]["tilt"] if daily else None,
                    "as_of": daily[-1]["date"] if daily else None,
                    "components": e["components"], "daily": daily}
    return {"generated_at": now.isoformat(timespec="seconds"), "use": "allocation_intel",
            "producer": "desks/mt5/research/macro_state_engine.py (latent datasets)",
            "consumer": ("desks/mt5/research/state_vector_build.py world_conditioning -> "
                         "data/state_vector.json conditioning rows (information, never authority)"),
            "authority": "none -- advisory state context, sizes nothing",
            "rule": ("tilt = mean(declared sign * clip(level, +-3)) over the latent states "
                     f"knowable that day and not older than {INTEL_STALE_DAYS} days"),
            "instruments": out}


def latent_hints_for(symbols: list[str], path: Path | None = None,
                     ) -> dict[str, list[dict[str, Any]]]:
    """THE CONSUMER'S DOOR for `state_vector_build.world_conditioning`: per book instrument, one
    row per latent state bearing on it, read from the allocation-intel artifact. An absent or
    unreadable artifact returns {} -- absence is UNMEASURED, never a demotion."""
    doc = _read_json(path or LATENT_INTEL)
    rows = (doc or {}).get("instruments") if isinstance(doc, dict) else None
    if not isinstance(rows, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for sym in symbols:
        e = rows.get(sym)
        if not isinstance(e, dict):
            continue
        hints = []
        for c in e.get("components") or []:
            if not isinstance(c, dict) or _f(c.get("level")) is None:
                continue
            age = _f(c.get("age_days"))
            weight = (0.0 if age is None else
                      round(max(0.0, 1.0 - age / float(INTEL_STALE_DAYS)), 4))
            hints.append({"src": c.get("dataset_id"), "kind": "latent_state", "lag": 0,
                          "clock": "release", "level": c.get("level"),
                          "surprise_z": c.get("surprise_z"),
                          "uncertainty": c.get("uncertainty"),
                          "knowable_at": c.get("knowable_at"), "sign": c.get("sign"),
                          "weight": weight, "stale": bool(c.get("stale")) or weight <= 0.0,
                          "authority": "none"})
        if hints:
            out[sym] = hints
    return out


# ---------------------------------------------------------------------------- latent cells
def _may_mint(sym: str, family: str) -> bool:
    try:
        from research import universe_policy
        return bool(universe_policy.may_hypothesise(sym, family))
    except Exception:                                                   # pragma: no cover - env
        return False


def direct_latent_cells(spec: LatentSpec, series_root: Path, now: datetime,
                        ) -> tuple[list[dict[str, Any]], int]:
    """Screen `exogenous_conditioner` on the latent's level and surprise for every mapped
    instrument the two-lane order allows. Returns (screen rows, looks charged)."""
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner

    from research import proposer_common as pc
    meta = pc.universe_meta()
    rows: list[dict[str, Any]] = []
    looks = 0
    for sym, sign in sorted(spec.instruments.items()):
        if not _may_mint(sym, "exogenous_conditioner"):
            continue
        bars = pc.bars(sym)
        if bars is None:
            continue
        cost = pc.cost_frac(sym, meta, bars["close"])
        if cost is None:
            continue
        unf = pc.artifact_hours(bars)
        for signal in ("level", "surprise_z"):
            params: dict[str, Any] = {"source": spec.dataset_id, "signal": signal,
                                      "transform": "level_z",
                      "threshold": 1.0, "side_when_high": int(sign), "lag_hours": 24,
                      "ttl_bars": 96}
            sigs = family_exogenous_conditioner(bars, **params, series_root=series_root)
            looks += 1
            sc = pc.screen(bars, sigs, cost, unf)
            if sc is None:
                continue
            rows.append({"cell": f"{sym}.exogenous_conditioner.{spec.dataset_id}.{signal}",
                         "symbol": sym, "params": params, "dataset": spec.id, **sc})
    return rows, looks


def regime_children(specs: list[LatentSpec], series_root: Path, state: dict[str, Any],
                    survivors: Path | None = None, limit: int = LATENT_CHILDREN_PER_PASS,
                    replay: Any = None) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]],
                                                 dict[str, int]]:
    """Certified parents on each mapped instrument, traded only while a latent level is above
    (or below) zero -- the `alt:` regime modifier the gauntlet already applies -- gated by the
    placebo-conditioned test (random regimes of the same duty cycle), Bonferroni-charged.

    Returns (passing candidates, looks charged, one gate row per child, looks by family)."""
    from mt5desk import cell_modifiers as cm
    from mt5desk.family_exogenous_conditioner import conditioner

    from libs.research.release_gain import regime_placebo
    from research import alt_proxies
    paths = alt_proxies.Paths(desk=BASE)
    doc = _read_json(survivors or SURVIVORS)
    parents: dict[str, list[dict[str, Any]]] = {}
    for name, v in sorted(((doc or {}).get("survivors") or {}).items()) \
            if isinstance(doc, dict) else []:
        sp = (v or {}).get("shadow_spec") if isinstance(v, dict) else None
        if isinstance(sp, dict) and sp.get("family") and sp.get("symbol"):
            parents.setdefault(str(sp["symbol"]), []).append({"name": name, **sp})
    pairs: list[tuple[LatentSpec, dict[str, Any]]] = []
    for spec in specs:
        for sym in sorted(spec.instruments):
            for par in parents.get(sym, [])[:3]:
                if _may_mint(sym, str(par.get("family") or "")):
                    pairs.append((spec, par))
    if not pairs:
        return [], 0, [], {}
    start = int(state.get("children_cursor") or 0) % len(pairs)
    take = (pairs[start:] + pairs[:start])[: max(0, limit // 2)]
    state["children_cursor"] = (start + len(take)) % len(pairs)
    replay = replay or alt_proxies._parent_signal_returns
    replays: dict[str, Any] = {}
    inputs: list[tuple[dict[str, Any], Any]] = []
    for spec, par in take:
        name = str(par["name"])
        if name not in replays:
            replays[name] = replay(paths, par)
        got = replays[name]
        series = conditioner(spec.dataset_id, "level", "raw", root=series_root)
        for op in ("gt", "lt"):
            params = dict(par.get("params") or {})
            if par.get("selector") and "session" not in params:
                params["session"] = str(par["selector"])
            params["conditioner"] = f"alt:{spec.dataset_id}:level:{op}:0"
            sym = str(par["symbol"])
            cand: dict[str, Any] = {"source": LATENT_SOURCE, "kind": "hypothesis", "symbol": sym,
                    "symbols": [sym], "family": str(par["family"]), "params": params, "url": "",
                    "cell": f"{name}|{params['conditioner']}", "parent": name,
                    "title": (f"{par['family']} on {sym} only while {spec.name} "
                              f"{'>' if op == 'gt' else '<'} 0")[:120],
                    "mechanism": (f"{spec.name} ({spec.meaning}) is a regime the certified "
                                  f"parent {name} may pay differently in"),
                    "falsifier": ("the conditioned child's gauntlet verdict is no better than "
                                  "its certified parent's on the same window"),
                    "provenance": {"organ": "macro_state_engine", "use": "latent_regime_child",
                                   "dataset_id": spec.dataset_id}}
            if isinstance(got, str):
                inputs.append((cand, got))
                continue
            if series is None or len(series) == 0:
                inputs.append((cand, "no latent lake series on this box"))
                continue
            idx, pos, ret = got
            known = series.reindex(series.index.union(idx)).ffill().reindex(idx)
            mask = cm.ALT_OPS[op](known.astype(float), 0.0).to_numpy(dtype=bool)
            inputs.append((cand, (pos, ret, mask)))
    n_trials = max(1, sum(1 for _c, x in inputs if not isinstance(x, str)))
    passed: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    by_family: dict[str, int] = {}
    for cand, x in inputs:
        if isinstance(x, str):
            res: dict[str, Any] = {"verdict": "UNMEASURED", "why": x}
        else:
            fam = str(cand["family"])
            by_family[fam] = by_family.get(fam, 0) + 1
            seed = int(hashlib.sha256(str(cand["cell"]).encode()).hexdigest()[:8], 16)
            res = regime_placebo(x[0], x[1], x[2], n_trials=n_trials, seed=seed)
        gates.append({"cell": cand["cell"], "family": cand["family"], **res})
        if res.get("verdict") == "PASS":
            cand["evidence"] = {k: res.get(k) for k in (
                "n_in", "n_signals", "duty_cycle", "mean_in", "placebo_mean", "p_placebo",
                "p_charged", "n_trials", "why")}
            passed.append(cand)
    return passed, sum(by_family.values()), gates, by_family


def _charge_null(tests_run: int, by_family: dict[str, int], now: datetime,
                 path: Path | None = None) -> dict[str, Any]:
    """A pass that looked and donated nothing still spent its trials: same side ledger
    `alt_proxies` uses, read by `libs.research.experiment_ledger`."""
    row = {"at": now.isoformat(timespec="seconds"), "source": LATENT_SOURCE,
           "tests_run": int(tests_run),
           "by_family": {k: int(v) for k, v in sorted(by_family.items()) if v},
           "why": "tested latent cells charged; no discovery file carried them this pass"}
    path = path or NULL_TRIALS
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        return {"null_trials_charged": int(tests_run)}
    except OSError as exc:
        return {"null_trials_error": f"{type(exc).__name__}: {str(exc)[:160]}"}


def latent_cells(specs: list[LatentSpec], ledgers: dict[str, list[dict[str, Any]]],
                 series_root: Path, state: dict[str, Any], now: datetime, apply: bool,
                 deadline: float | None = None) -> dict[str, Any]:
    """Screen -> deflate -> donate, with every look charged whether or not anything passes.
    Past `deadline` no further spec is screened (named in `skipped`): the latent build stops
    inside its own budget and the looks it DID take are still charged."""
    from research import proposer_common as pc
    rows: list[dict[str, Any]] = []
    looks = 0
    skipped: dict[str, str] = {}
    ready = [s for s in specs if len(ledgers.get(s.id) or []) >= MIN_CELL_VINTAGES]
    for spec in specs:
        if spec not in ready:
            skipped[spec.id] = (f"{len(ledgers.get(spec.id) or [])} vintages < "
                                f"{MIN_CELL_VINTAGES}: the conditioner cannot measure yet")
            continue
        if deadline is not None and time.monotonic() > deadline:
            skipped[spec.id] = "latent budget spent: not screened this pass"
            continue
        try:
            got_rows, n = direct_latent_cells(spec, series_root, now)
        except Exception as exc:
            skipped[spec.id] = f"direct cells raised {type(exc).__name__}: {str(exc)[:120]}"
            continue
        rows.extend(got_rows)
        looks += n
    rows = pc.deflate(rows) if rows else []
    best = pc.best_per_cell(rows) if rows else []
    cands: list[dict[str, Any]] = []
    for b in best:
        r = dict(b)
        spec = LATENT_BY_ID[str(r["dataset"])]
        cands.append({
            "source": LATENT_SOURCE, "kind": "hypothesis", "symbol": r["symbol"],
            "symbols": [r["symbol"]], "family": "exogenous_conditioner",
            "params": r["params"], "url": "", "cell": r["cell"],
            "title": f"{spec.name} {r['params']['signal']} extreme -> {r['symbol']}"[:120],
            "available_time": now.isoformat(timespec="seconds"),
            "event_time": now.isoformat(timespec="seconds"),
            "mechanism": (f"{spec.name}: {spec.meaning}. A state fused from hard Asian series "
                          f"the price-only families cannot see, bearing on {r['symbol']} with "
                          f"declared sign {r['params']['side_when_high']:+d}")[:400],
            "falsifier": (f"{r['symbol']} returns after a |z|>=1 {spec.dataset_id} "
                          f"{r['params']['signal']} reading no longer clear cost at the "
                          "deflated bar"),
            "evidence": {k: r.get(k) for k in ("n_independent", "gross_per_trade",
                                               "net_per_trade", "t_gross", "t_deflated_sweep",
                                               "n_tests_sweep", "t_deflated_lifetime")},
            "provenance": {"organ": "macro_state_engine", "use": "latent_direct_cell",
                           "dataset_id": spec.dataset_id, "directive": spec.directive}})
    children: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    child_looks = 0
    child_fam: dict[str, int] = {}
    if deadline is not None and time.monotonic() > deadline:
        skipped["regime_children"] = "latent budget spent: not screened this pass"
    else:
        try:
            children, child_looks, gates, child_fam = regime_children(ready, series_root, state)
        except Exception as exc:
            skipped["regime_children"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    tests_run = looks + child_looks
    by_family = {"exogenous_conditioner": looks, **child_fam}
    out: dict[str, Any] = {"screened": len(rows), "looks": looks, "child_looks": child_looks,
                           "tests_run": tests_run, "proposed_direct": len(cands),
                           "passed_children": len(children), "skipped": skipped,
                           "child_gates": gates[:40], "path": None, "donated": 0}
    allc = cands + children
    if apply and allc:
        try:
            path = pc.donate(LATENT_SOURCE, allc, max(1, tests_run))
            out.update({**pc.donation_counts(), "path": str(path) if path else None})
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    if apply and tests_run > 0 and not out.get("path"):
        out.update(_charge_null(tests_run, by_family, now))
    out["trials_by_family"] = by_family
    return out


# ---------------------------------------------------------------------------- asia events
def asia_calendars() -> dict[str, Any]:
    """The desk's own closure tables for `event_state.asia_schedule`: the mainland pack's
    closures, the Korean pack's holidays and the flow calendar's effective gotobi. Any that
    will not import is simply absent, and the schedule then says `weekends_only`."""
    out: dict[str, Any] = {}
    try:
        from countries.cn import pack as cn
        out["cn_closed"] = cn._is_closed
    except Exception:                                                   # pragma: no cover - env
        pass
    try:
        from countries.kr import pack as kr

        def _kr_closed(d: Any) -> bool:
            return d.weekday() >= 5 or d.isoformat() in kr.holidays(d.year)
        out["kr_closed"] = _kr_closed
    except Exception:                                                   # pragma: no cover - env
        pass
    try:
        from mt5desk.flowcal import effective_gotobi
        out["jp_gotobi"] = effective_gotobi
    except Exception:                                                   # pragma: no cover - env
        pass
    return out


def build_asia_events(now: datetime, axes_dir: Path, apply: bool,
                      out_path: Path | None = None, ledger_path: Path | None = None,
                      ) -> dict[str, Any]:
    """Every rule-derived Asian release from 35 days back to 14 ahead, as lifecycle objects
    read against the hard sensors the axis door holds. Stage changes are appended to a ledger
    (history kept); the current set is the file `state_vector_build` reads."""
    from libs.regime.event_state import ASIA_EVENT_RULES, asia_event_objects, asia_schedule
    out_path = out_path or ASIA_EVENTS
    ledger_path = ledger_path or ASIA_EVENTS_LEDGER
    rows = asia_schedule(now.date() - timedelta(days=35), now.date() + timedelta(days=14),
                         calendars=asia_calendars())
    docs: dict[str, Any] = {}
    sensors: dict[str, list[dict[str, Any]]] = {}
    sensor_state: dict[str, str] = {}
    for rule in ASIA_EVENT_RULES:
        if not rule.sensor or rule.sensor in sensors:
            continue
        stem, _, key = rule.sensor.partition(":")
        if stem not in docs:
            docs[stem] = _read_json(axes_dir / f"{stem}.json")
        doc = docs[stem]
        pts = (((doc or {}).get("series") or {}).get(key) or {}).get("points") \
            if isinstance(doc, dict) else None
        sensors[rule.sensor] = [p for p in (pts or []) if isinstance(p, dict)]
        sensor_state[rule.sensor] = (f"{len(sensors[rule.sensor])} points" if pts else
                                     f"UNMEASURED: data/axes/{stem}.json has no `{key}` here")
    objs = asia_event_objects(now, rows, sensors)
    stages: dict[str, int] = {}
    for o in objs:
        stages[o["stage"]] = stages.get(o["stage"], 0) + 1
    doc_out = {"generated_at": now.isoformat(timespec="seconds"),
               "dataset_id": "asia_events", "producer": "desks/mt5/research/macro_state_engine.py",
               "consumer": ("desks/mt5/research/state_vector_build.py event_state -> "
                            "data/state_vector.json event.per_symbol[*].asia_events"),
               "rules": [{"rule": r.rule, "kind": r.kind, "title": r.title,
                          "sensor": r.sensor or None, "sensor_status": r.sensor_status,
                          "schedule": r.schedule_note} for r in ASIA_EVENT_RULES],
               "sensors": sensor_state, "n_events": len(objs), "by_stage": stages,
               "events": objs}
    appended = 0
    if apply:
        _atomic(out_path, json.dumps(doc_out, indent=1, default=str))
        seen = {str(r.get("observation_id")) for r in read_ledger(ledger_path)[-20000:]}
        new = [o for o in objs if o["observation_id"] not in seen
               and o["stage"] not in ("ANNOUNCED",)]
        if new:
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with ledger_path.open("a", encoding="utf-8") as fh:
                for o in new:
                    fh.write(json.dumps({**o, "recorded_at": now.isoformat(timespec="seconds")},
                                        sort_keys=True, default=str) + "\n")
            appended = len(new)
    return {"n_events": len(objs), "by_stage": stages, "sensors": sensor_state,
            "appended_to_ledger": appended, "path": str(out_path) if apply else None}


# ---------------------------------------------------------------------------- the dataset rule
def fed_block(consumed: dict[str, dict[str, Any]], prior: dict[str, Any], now: datetime,
              ) -> dict[str, Any]:
    """THE DATASET RULE (CRO D18): every declared input is consumed within FED_WINDOW_H or it is
    UNFED, and the count is published (`unfed_count`, target 0).

    An input is FED this pass when the latent build actually loaded its observations and handed
    them to the estimator. `last_fed_at` is carried in `data/latent/state.json` so an input
    that stops arriving keeps its last real consumption time and turns STALE after the window,
    never silently FED. Field names follow the desk's D18 publishers (`dataset_exploitation`:
    `unfed_count` + `unfed_datasets`; `dataset_use_census`: `unfed[{dataset, kind, status}]`)."""
    at = now.isoformat(timespec="seconds")
    window = timedelta(hours=FED_WINDOW_H)
    rows: dict[str, dict[str, Any]] = {}
    unfed: list[dict[str, Any]] = []
    for key, c in sorted(consumed.items()):
        inp: LatentInput = c["inp"]
        rec: dict[str, Any] = c["rec"]
        last = at if c["fed"] else (prior.get(key) if isinstance(prior.get(key), str) else None)
        try:
            age_ok = last is not None and now - datetime.fromisoformat(last) <= window
        except ValueError:
            age_ok, last = False, None
        # Consumed inside the window (this pass or an earlier one) is FED; consumed once but
        # not inside the window is STALE; never consumed is UNFED. Both of the last count.
        status = "FED" if (c["fed"] or age_ok) else ("UNFED" if last is None else "STALE")
        rows[key] = {"dataset_id": f"latent_{key.split('.', 1)[0]}", "input": inp.id,
                     "axis": inp.axis or None,
                     "census_id": f"axis:{inp.axis}" if inp.axis else None,
                     "status": status, "last_fed_at": last, "consumed_this_pass": c["fed"],
                     "input_status": rec.get("status")}
        if status != "FED":
            unfed.append({"dataset": key, "kind": "latent_input", "status": status,
                          "last_fed_at": last,
                          "why": str(rec.get("why") or rec.get("status") or "")[:200]})
    return {"measured_at": at, "duty": "CRO D18 -- no unfed datasets", "window_h": FED_WINDOW_H,
            "datasets": rows, "datasets_held": len(rows), "fed": len(rows) - len(unfed),
            "unfed": unfed, "unfed_count": len(unfed), "unfed_datasets": len(unfed),
            "target": 0,
            "evidence": ("an input is fed when the latent build loaded its observations and "
                         f"handed them to the estimator inside {FED_WINDOW_H}h; declared, "
                         "pending, blocked or absent inputs are UNFED")}


def record_fed_reads(consumed: dict[str, dict[str, Any]], now: datetime) -> str:
    """Record this pass's real reads with the desk's dataset-use recorder (`libs.data.dataset_use`,
    read by `dataset_use_census`) under the census's own ids (`axis:<stem>`). Never raises: a
    recorder that is not on this branch reads UNMEASURED, never 'recorded'."""
    reads: dict[str, str | None] = {}
    for c in consumed.values():
        if c["fed"] and c["inp"].axis:
            reads[f"axis:{c['inp'].axis}"] = c["rec"].get("last_arrival")
    if not reads:
        return "nothing consumed this pass: no read to record"
    try:
        import importlib
        dataset_use = importlib.import_module("libs.data.dataset_use")
    except Exception as exc:
        return f"UNMEASURED: dataset-use recorder not importable ({type(exc).__name__})"
    try:
        ok = dataset_use.record_reads(FED_CONSUMER, reads, use="regime_state", now=now)
    except Exception as exc:                                            # pragma: no cover - env
        return f"UNMEASURED: {type(exc).__name__}: {str(exc)[:120]}"
    return f"recorded {len(reads)} read(s)" if ok else "UNMEASURED: recorder refused the write"


# ---------------------------------------------------------------------------- the latent pass
def build_latent(now: datetime, *, budget_s: float = 120.0, apply: bool = True,
                 axes_dir: Path | None = None, latent_dir: Path | None = None,
                 series_root: Path | None = None, intel_path: Path | None = None,
                 specs: tuple[LatentSpec, ...] = LATENT_SPECS, cells: bool = True,
                 environ: dict[str, str] | None = None) -> dict[str, Any]:
    """Load, nowcast new vintages, append, publish (axis door, lake, intel), then cells.

    Paths default to the module's globals AT CALL TIME, so a test that redirects them redirects
    every write this pass makes."""
    axes_dir = axes_dir or AXES_DIR
    latent_dir = latent_dir or LATENT_DIR
    series_root = series_root or LAKE_SERIES
    intel_path = intel_path or LATENT_INTEL
    deadline = time.monotonic() + max(1.0, float(budget_s))
    docs: dict[str, Any] = {}
    report: dict[str, Any] = {}
    ledgers: dict[str, list[dict[str, Any]]] = {}
    consumed: dict[str, dict[str, Any]] = {}
    for spec in specs:
        recs: list[dict[str, Any]] = []
        prep: list[_Prepared] = []
        for inp in spec.inputs:
            obs, rec = load_input(inp, axes_dir, docs, environ)
            recs.append(rec)
            consumed[f"{spec.id}.{inp.id}"] = {"inp": inp, "rec": rec, "fed": bool(obs)}
            if obs:
                prep.append(_Prepared(inp, obs))
        lpath = _ledger_path(spec, latent_dir)
        ledger = read_ledger(lpath)
        new, owed = (build_vintages(spec, prep, ledger, now, deadline) if prep else ([], 0))
        full = ledger + new
        ledgers[spec.id] = full
        last = full[-1] if full else None
        weights = {c["input"]: c["weight"] for c in (last or {}).get("components") or []}
        for rec in recs:
            if rec["input"] in weights:
                rec["weight_last_vintage"] = weights[rec["input"]]
                rec["status_last_vintage"] = ("USED" if any(
                    c["input"] == rec["input"] and c["fresh"]
                    for c in last.get("components") or []) else "STALE")  # type: ignore[union-attr]
        if apply and new:
            lpath.parent.mkdir(parents=True, exist_ok=True)
            with lpath.open("a", encoding="utf-8") as fh:
                for r in new:
                    fh.write(json.dumps(r, sort_keys=True, default=str) + "\n")
        if apply and full:
            _atomic(axes_dir / f"{spec.dataset_id}.json",
                    json.dumps(axis_doc_latent(spec, full, recs, now), indent=1, default=str))
            write_lake(spec, full, series_root)
        n_hard = sum(1 for r in recs if r["status"] == "COLLECTED")
        report[spec.id] = {
            "dataset_id": spec.dataset_id, "name": spec.name, "directive": spec.directive,
            "meaning": spec.meaning,
            "status": ("OK" if full else
                       "UNMEASURED: no declared input is collected on this host"),
            "n_vintages": len(full), "new_vintages": len(new), "release_dates_owed": owed,
            "n_inputs_declared": len(spec.inputs), "n_inputs_collected": n_hard,
            "n_inputs_not_yet_collected": sum(1 for r in recs
                                              if r["status"] == "NOT_YET_COLLECTED"),
            "thin": n_hard < 2,
            "latest": None if last is None else {
                k: last.get(k) for k in ("knowable_at", "event_time", "level", "uncertainty",
                                         "surprise_z", "acceleration", "baseline_level",
                                         "pca_level", "revision_state", "n_inputs_used",
                                         "pit_quality")},
            "model_comparison": _comparison_verdict(last), "inputs": recs,
            "price_inputs": [],
            "axis_doc": f"desks/mt5/data/axes/{spec.dataset_id}.json" if full else None,
            "lake_series": f"desks/mt5/data/lake/series/{spec.dataset_id}.csv" if full else None,
            "ledger": f"desks/mt5/data/latent/{spec.dataset_id}.vintages.jsonl"}
    state_path = latent_dir / "state.json"
    state = _read_json(state_path)
    state = state if isinstance(state, dict) else {}
    prior_fed = state.get("fed")
    fed = fed_block(consumed, prior_fed if isinstance(prior_fed, dict) else {}, now)
    state["fed"] = {k: v["last_fed_at"] for k, v in fed["datasets"].items()
                    if v["last_fed_at"] is not None}
    fed["census_record"] = (record_fed_reads(consumed, now) if apply
                            else "dry run: no read recorded")
    intel = allocation_intel_latent({k: v for k, v in ledgers.items() if v}, now)
    intel["fed"] = fed
    if apply:
        _atomic(intel_path, json.dumps(intel, indent=1, default=str))
    cell_rep: dict[str, Any] = {"status": "skipped (cells=False)"}
    if cells:
        try:
            cell_rep = latent_cells(list(specs), ledgers, series_root, state, now, apply,
                                    deadline=deadline)
        except Exception as exc:
            cell_rep = {"status": f"UNMEASURED: {type(exc).__name__}: {str(exc)[:160]}"}
    if apply:
        _atomic(state_path, json.dumps(state, indent=1))
    return {"datasets": report, "allocation_intel": {
                "path": str(intel_path) if apply else None,
                "n_instruments": len(intel["instruments"])},
            "fed": fed, "cells": cell_rep,
            "rule": ("one vintage per release date, re-estimated on the data knowable at that "
                     "date and appended; no price series fused; not-yet-collected inputs are "
                     "named with the package that delivers them")}


# -------------------------------------------------------------------------------------- build
def build(*, budget_s: float = 600.0, max_donations: int = MAX_DONATIONS, p_max: float = P_MAX,
          n_perm: int = N_PERM, apply: bool = True,
          latent_budget_s: float = LATENT_BUDGET_S) -> dict[str, Any]:
    """Measure both halves and return the report. `apply=False` measures and donates nothing."""
    t0 = time.monotonic()
    # THE LATENT DATASETS AND THE ASIA EVENTS GO FIRST, ON THEIR OWN BUDGET (`latent_budget_s`),
    # never on the edge scan's: mining is never reduced to make room for a new organ. The edge
    # scan below keeps the WHOLE `budget_s` from the moment it starts, exactly as before the
    # latent build existed, and the leg's timeout sits above latent + scan so neither is killed.
    now = _now()
    try:
        latent = build_latent(now, budget_s=max(1.0, float(latent_budget_s)), apply=apply)
    except Exception as exc:                                            # pragma: no cover - env
        latent = {"status": f"UNMEASURED: {type(exc).__name__}: {str(exc)[:200]}"}
    try:
        asia_events = build_asia_events(now, AXES_DIR, apply)
    except Exception as exc:                                            # pragma: no cover - env
        asia_events = {"status": f"UNMEASURED: {type(exc).__name__}: {str(exc)[:200]}"}
    latent_spent = time.monotonic() - t0
    start = time.monotonic()
    deadline = start + max(float(budget_s), 1.0)
    blocks, summary, census = build_blocks()
    pairs, inputs = graph_pairs()
    if pairs:
        rows, unmeasured, counts = hunt_edges(pairs, deadline=deadline, n_perm=n_perm)
    else:
        rows, counts = [], {"pairs": 0, "measured": 0, "unmeasured": 1, "tests_run": 0,
                            "skipped_budget": 0, "n_perm": n_perm}
        unmeasured = [{"status": "UNMEASURED", "src": None, "dst": None,
                       "why": ("no causal-graph artifact published an edge list: wanted "
                               f"{WORLD_REPORT.name} (admitted_edges / recorded_not_admitted) "
                               f"or {WORLD_GRAPH.name} (edges). Edge changes are UNMEASURED "
                               "this pass; the region blocks above are unaffected")}]
    cands, refusals = donation_candidates(rows, max_donations, p_max)
    path = _donate(cands, int(counts["tests_run"])) if (apply and cands) else None
    counts_from_intake: dict[str, Any] = {}
    if path is not None:
        try:
            from research.proposer_common import donation_counts
            counts_from_intake = dict(donation_counts())
        except Exception:                                               # pragma: no cover - env
            counts_from_intake = {}
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[str(r.get("kind"))] = by_kind.get(str(r.get("kind")), 0) + 1
    return {
        "source": SOURCE,
        "generated_at": _now().isoformat(),
        "status": "OK" if (blocks or rows) else "UNMEASURED",
        "why": "" if (blocks or rows) else ("no classified instrument and no graph edge: both "
                                            "halves are UNMEASURED and named below"),
        "budget_s": float(budget_s), "spent_s": round(time.monotonic() - t0, 2),
        "edge_scan_spent_s": round(time.monotonic() - start, 2),
        "latent_budget_s": float(latent_budget_s), "latent_spent_s": round(latent_spent, 2),
        "rule": RULE,
        "inputs": {**inputs,
                   "instrument_registry": {"status": "present" if _registry() else "absent",
                                           "path": str(REGISTRY_PATH), "n": len(_registry()),
                                           "why": "" if _registry() else "no broker registry: "
                                                  "no instrument can be routed to a region"},
                   "fred_archive": {"status": "present" if fred_levels() else "absent",
                                    "n_series": len(fred_levels()),
                                    "why": "" if fred_levels() else "no FRED archive on this box",
                                    **fred_vintages()}},
        "blocks": blocks, "blocks_summary": summary, "registry_census": census,
        "global_factors": global_factors(blocks),
        "edge_changes": {**counts, "by_kind": by_kind, "rows": rows[:200],
                         "unmeasured_rows": unmeasured[:200],
                         "window_rule": ("window = clip(n/6, 20, 250) bars, two adjacent "
                                         "trailing windows, permutation null over the scan")},
        "donations": {"eligible": len(cands), "donated": 0 if path is None else len(cands),
                      "max_donations": int(max_donations), "p_max": float(p_max),
                      "refused": refusals[:40], "n_refused": len(refusals),
                      "path": None if path is None else str(path),
                      "intake": counts_from_intake,
                      "trials": _effective_trials(cands, int(counts["tests_run"])),
                      "families": dict(FAMILY_BY_KIND),
                      "price_only_vocab": ("measured" if price_only_families()
                                           else "UNMEASURED: the compiler would not import")},
        "latent_datasets": latent,
        "asia_events": asia_events,
        "consumer": ("donated rows land in data/intelligence/macro_state_engine/ and are read by "
                     "research/miner_candidate_compiler.py (STRUCTURED_HYPOTHESIS, family "
                     "defaults, declared instrument) on the same hourly cycle; the blocks and "
                     "their UNMEASURED verdicts are this desk's per-country state, published for "
                     "the state vector and the allocator's macro conditioning to read"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="per-country macro state blocks, and the "
                                             "cross-asset graph's edge CHANGES as hunted objects")
    ap.add_argument("--once", action="store_true",
                    help="one pass (this organ has no loop; the flag keeps the leg uniform)")
    ap.add_argument("--budget-s", type=float, default=600.0,
                    help="wall-clock bound; the edge scan stops on it and says how many pairs "
                         "it did not reach")
    ap.add_argument("--latent-budget-s", type=float, default=LATENT_BUDGET_S,
                    help="the latent build's OWN wall-clock bound, spent before the edge scan "
                         "and never taken out of --budget-s")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no report and donate nothing")
    ap.add_argument("--max-donations", type=int, default=MAX_DONATIONS)
    ap.add_argument("--p-max", type=float, default=P_MAX)
    ap.add_argument("--n-perm", type=int, default=N_PERM)
    a = ap.parse_args(argv)
    rep = build(budget_s=a.budget_s, max_donations=a.max_donations, p_max=a.p_max,
                n_perm=a.n_perm, apply=not a.dry_run, latent_budget_s=a.latent_budget_s)
    s, e = rep["blocks_summary"], rep["edge_changes"]
    print(f"macro-state-engine: {s['n_blocks']} region block(s), {s['measured']}/"
          f"{s['n_blocks'] * s['states_per_block']} states measured "
          f"(coverage {s['coverage']:.2f}); rank window {s['rank_window']}")
    worst = sorted(rep["blocks"].values(), key=lambda b: float(b["coverage"]))[:3]
    if worst:
        print("  thinnest  " + "  ".join(f"{b['region']}:{b['coverage']:.2f}" for b in worst))
    print(f"  edges     {e['measured']} measured of {e['pairs']} pair(s); "
          f"{e['unmeasured']} UNMEASURED; {e['skipped_budget']} left on the budget; "
          f"kinds {e['by_kind'] or '{}'}")
    top = (e["rows"] or [{}])[0]
    if top:
        print(f"  top       {top.get('src')}->{top.get('dst')} lag {top.get('lag')} "
              f"{top.get('kind')} at {top.get('t_change')} p={top.get('p_perm')}")
    for sid, ds in sorted(((rep.get("latent_datasets") or {}).get("datasets") or {}).items()):
        lt = ds.get("latest") or {}
        print(f"  latent    {sid:17s} {ds['n_vintages']:5d} vintage(s) (+{ds['new_vintages']}, "
              f"{ds['release_dates_owed']} owed), {ds['n_inputs_collected']}/"
              f"{ds['n_inputs_declared']} inputs collected; level {lt.get('level')} "
              f"+-{lt.get('uncertainty')}")
    ev = rep.get("asia_events") or {}
    print(f"  asia ev   {ev.get('n_events')} event object(s) {ev.get('by_stage')}")
    d = rep["donations"]
    verb = "would donate" if a.dry_run else "donated"
    print(f"  {verb:<9} {d['eligible']} of {d['max_donations']} allowed; {d['n_refused']} "
          f"refused (p, lane or family); effective trials {d['trials']['n_effective']}")
    if a.dry_run:
        print("  --dry-run: nothing written, nothing donated")
        print(f"  would have written {REPORT}")
        return 0
    _atomic(REPORT, json.dumps(rep, indent=1, default=str))
    print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
