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
from datetime import UTC, datetime
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
    try:
        from libs.portfolio.macro_state import resolve_archive
        doc = _read_json(resolve_archive())
    except Exception:                                                   # pragma: no cover - env
        doc = None
    out: dict[str, tuple[tuple[str, ...], tuple[float, ...]]] = {}
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


# -------------------------------------------------------------------------------------- build
def build(*, budget_s: float = 600.0, max_donations: int = MAX_DONATIONS, p_max: float = P_MAX,
          n_perm: int = N_PERM, apply: bool = True) -> dict[str, Any]:
    """Measure both halves and return the report. `apply=False` measures and donates nothing."""
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
        "budget_s": float(budget_s), "spent_s": round(time.monotonic() - start, 2),
        "rule": RULE,
        "inputs": {**inputs,
                   "instrument_registry": {"status": "present" if _registry() else "absent",
                                           "path": str(REGISTRY_PATH), "n": len(_registry()),
                                           "why": "" if _registry() else "no broker registry: "
                                                  "no instrument can be routed to a region"},
                   "fred_archive": {"status": "present" if fred_levels() else "absent",
                                    "n_series": len(fred_levels()),
                                    "why": "" if fred_levels() else "no FRED archive on this box"}},
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
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write no report and donate nothing")
    ap.add_argument("--max-donations", type=int, default=MAX_DONATIONS)
    ap.add_argument("--p-max", type=float, default=P_MAX)
    ap.add_argument("--n-perm", type=int, default=N_PERM)
    a = ap.parse_args(argv)
    rep = build(budget_s=a.budget_s, max_donations=a.max_donations, p_max=a.p_max,
                n_perm=a.n_perm, apply=not a.dry_run)
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
