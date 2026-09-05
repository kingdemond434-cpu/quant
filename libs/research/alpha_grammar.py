"""An alpha language for MT5 bars: the grammar behind formulaic alpha search, not any one alpha.

WorldQuant's 101 published formulas, AlphaGen's RL-generated expressions and the LLM-assisted
HARLA variants share one thing that transfers to a gold/FX/index desk when the individual
formulas do not: a small closed set of causal operators over a small set of market terminals,
composed into trees, searched by mutation, crossover and generation, and scored by what they do
for a PORTFOLIO rather than by standalone correlation. This module is that closed set.

EVERY OPERATOR IS CAUSAL BY CONSTRUCTION. Windows look back only; there is no operator that
can reach a later bar, so an expression cannot leak whatever its shape. `evaluate` is pure
arithmetic on aligned series and raises nothing: an expression that cannot be computed on the
frames it is given (a driver terminal with no driver, a window longer than the history) returns
a series of NaN, which every consumer treats as "no signal".

INVALID ARITHMETIC IS NOT CONSTRUCTIBLE (2026-09-05). `is_valid` -- the one screen every
generator, mutation, crossover and the `formula` family itself run -- is now structural validity
AND `well_typed` AND `well_formed`, so a tree that adds a price to a tick count or a lot count to
a return cannot be built, sampled, mutated into, or traded. It is not screened out afterwards:
`random_expr` redraws until the composition is legal and the typed samplers in
`libs.research.generators` intersect their action mask with the unit algebra, so the illegal
action is never offered. `well_typed` is UNCHANGED by that promotion -- the second check is the
unit algebra below, and nothing already certified changes its verdict.

TERMINALS are the desk's own bars (price, return, range, body, tick activity, realised
volatility, signed tick flow, the broker's spread, ATR), the economic driver roles of
`economic_drivers` (USD, RATES, RISK, GOLD, OIL, GROWTH), and the EXTERNAL roles a caller
supplies through `extra` (positioning, event, macro, fundamental, state probability,
cross-sectional rank, execution state). The externals are never SAMPLED unless the caller says
it has them -- `terminal_pool` and `available_terminals` decide that from the frames -- because
a terminal with no series evaluates to NaN and spends search budget on nothing. Cross-section
enters as a TERMINAL (a percentile the caller computed against the peers it has), never as an
operator: the desk trades one instrument per cell and the grammar has no panel to rank within.

REPRESENTATION is plain JSON so an expression IS its recipe: a terminal is a string, a node is
a list `[op, child, ...args]`. `to_str` renders it for a human; the recipe the gauntlet keeps is
the list. Two expressions with the same list are the same hypothesis and hash the same.
"""
from __future__ import annotations

import hashlib
import json
import warnings
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import pandas as pd

Expr = Any                                      # str | list[Any]; JSON-shaped

#: Terminals the desk computes from its OWN bars, so they are always available.
BAR_TERMINALS = ("close", "open", "high", "low", "ret", "range", "body", "activity", "spread",
                 "atr", "vol", "flow")
DRIVER_TERMINALS = ("usd", "rates", "risk", "gold", "oil", "growth")
#: Terminals only a caller can supply (`terminal_frames(extra=...)`): positioning surveys, an
#: event calendar, macro surprises, fundamentals, a regime posterior, a peer-group percentile,
#: the desk's own execution state. Declared here so a claim, an LLM or a literature template CAN
#: name one and be type-checked; never sampled unless the frames actually carry it.
EXTERNAL_TERMINALS = ("positioning", "event", "macro", "fundamental", "state_prob", "xsec",
                      "fill_state")
TERMINALS = BAR_TERMINALS + DRIVER_TERMINALS + EXTERNAL_TERMINALS

UNARY = ("neg", "abs", "sign")
WINDOWED = ("delay", "delta", "mean", "std", "min", "max", "ts_rank", "zscore", "decay", "sum",
            "bars_since_max", "bars_since_min", "atr_norm", "ts_backfill", "scale")
BINARY = ("add", "sub", "mul", "div", "max2", "min2", "trade_when")
BINARY_WINDOWED = ("corr", "residual", "cov", "group_rank", "group_zscore")
OPERATORS = UNARY + WINDOWED + BINARY + BINARY_WINDOWED
WINDOWS = (2, 3, 5, 8, 12, 24, 48, 120, 240)
MAX_DEPTH = 5
#: Bars of log return that `vol` is measured over. One trading day on H1, so the terminal means
#: "how volatile has the last day been" rather than a number nobody can name.
VOL_N = 24

#: Named reference alphas the search measures novelty against: what the desk already knows how
#: to say. A new expression that is 0.95 correlated with one of these is not new.
CANON: dict[str, Expr] = {
    "trend_24": ["delta", "close", 24],
    "trend_120": ["delta", "close", 120],
    "reversal_5": ["neg", ["delta", "close", 5]],
    "breakout_dist_48": ["sub", "close", ["max", "high", 48]],
    "range_z_24": ["zscore", "range", 24],
    "activity_z_48": ["zscore", "activity", 48],
    "spread_rank_240": ["ts_rank", "spread", 240],
}


# --------------------------------------------------------------------------- frames
def terminal_frames(bars: pd.DataFrame, raw: pd.DataFrame | None = None,
                    drivers: dict[str, pd.DataFrame] | None = None,
                    atr_n: int = 20, extra: dict[str, Any] | None = None,
                    vol_n: int = VOL_N) -> dict[str, pd.Series]:
    """Every terminal as a float series on `bars.index`. Missing ones are simply absent.

    `bars` is the resampled OHLC frame; `raw` is the original frame carrying the broker's
    `spread` and `tick_volume` (the resampler drops them -- see `family_spread_state`).
    Drivers are aligned to the bar index and forward-filled, which is the only causal join:
    the driver's last known close at each bar.

    `extra` supplies the EXTERNAL terminals -- positioning, event, macro, fundamental,
    state_prob, xsec, fill_state -- as a series or a one-column frame each, joined by the same
    forward-fill: whatever was last KNOWN at the bar. A caller with none of them passes none and
    the search never proposes one (`available_terminals`), which is the difference between a
    terminal the desk cannot measure and a terminal it measures as NaN.
    """
    idx = bars.index
    close = bars["close"].astype(float)
    out: dict[str, pd.Series] = {
        "close": close, "open": bars["open"].astype(float), "high": bars["high"].astype(float),
        "low": bars["low"].astype(float),
    }
    with np.errstate(all="ignore"):
        out["ret"] = np.log(close).diff()
        out["range"] = (out["high"] - out["low"]) / close
        out["body"] = (close - out["open"]) / close
        h, lo, pc = out["high"], out["low"], close.shift(1)
        tr = pd.concat([(h - lo), (h - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)
        out["atr"] = tr.rolling(atr_n, min_periods=atr_n).mean()
        out["vol"] = out["ret"].rolling(int(max(2, vol_n)), min_periods=int(max(2, vol_n))).std()
    src = raw if raw is not None else bars
    for col, name in (("spread", "spread"), ("tick_volume", "activity")):
        if col in src.columns:
            s = src[col].astype(float)
            if src is not bars:
                s.index = pd.DatetimeIndex(pd.to_datetime(s.index, utc=True, errors="coerce"))
                s = s.reindex(idx).ffill()
            out[name] = s
    if "activity" in out:
        # SIGNED TICK FLOW, the only order-flow proxy a retail MT5 feed can carry: Fusion
        # publishes tick counts, not traded contracts, so the direction has to come from the
        # bar that produced them. Ticks into an up-bar are buying pressure by construction of
        # the bar, which is a proxy and is typed as one (FLOW, in ticks), not as volume.
        out["flow"] = np.sign(out["body"]).fillna(0.0) * out["activity"]
    for role, frame in (drivers or {}).items():
        key = str(role).lower()
        if key not in DRIVER_TERMINALS or frame is None or "close" not in frame.columns:
            continue
        s = frame["close"].astype(float)
        s.index = pd.DatetimeIndex(pd.to_datetime(s.index, utc=True, errors="coerce"))
        s = s[~s.index.duplicated(keep="last")].sort_index()
        out[key] = s.reindex(idx, method="ffill")
    for role, obj in (extra or {}).items():
        key = str(role).lower()
        if key not in EXTERNAL_TERMINALS or obj is None:
            continue
        s = obj.iloc[:, 0] if isinstance(obj, pd.DataFrame) and obj.shape[1] else obj
        if not isinstance(s, pd.Series) or s.empty:
            continue
        s = s.astype(float)
        s.index = pd.DatetimeIndex(pd.to_datetime(s.index, utc=True, errors="coerce"))
        s = s[~s.index.isna()]
        s = s[~s.index.duplicated(keep="last")].sort_index()
        out[key] = s.reindex(idx, method="ffill")
    return out


def available_terminals(frames: dict[str, pd.Series],
                        allow_drivers: bool = True) -> tuple[str, ...]:
    """The terminals a search may actually SAMPLE given these frames.

    A terminal absent from the frames -- or present and entirely NaN -- evaluates to NaN
    everywhere, so every tree containing it is a wasted trial. Empty frames mean "the caller
    is not telling", and the answer is then the ordinary pool rather than nothing.
    """
    if not frames:
        return terminal_pool(allow_drivers)
    # An EXTERNAL the caller supplied is available by that fact alone -- supplying the series is
    # how a caller declares it has one, and there is nothing else to ask.
    pool = terminal_pool(allow_drivers, extra=[t for t in EXTERNAL_TERMINALS if t in frames])
    out = tuple(t for t in pool
                if isinstance(frames.get(t), pd.Series) and bool(frames[t].notna().any()))
    return out or (BAR_TERMINALS[:1] if "close" in frames else pool)


def terminal_pool(allow_drivers: bool = True, extra: Iterable[str] = ()) -> tuple[str, ...]:
    """The terminals a generator may draw from: the bars, the drivers when allowed, and the
    external roles the caller DECLARES it has. Externals are opt-in for the reason above."""
    named = tuple(t for t in EXTERNAL_TERMINALS if t in set(extra))
    return BAR_TERMINALS + (DRIVER_TERMINALS if allow_drivers else ()) + named


# --------------------------------------------------------------------------- evaluation
def _nan(idx: pd.Index) -> pd.Series:
    return pd.Series(np.nan, index=idx, dtype=float)


def _ts_rank(v: np.ndarray, w: int) -> np.ndarray:
    out = np.full(v.size, np.nan)
    if v.size <= w:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(v, w + 1)
    prev, cur = win[:, :-1], win[:, -1:]
    with np.errstate(invalid="ignore"):
        out[w:] = (prev <= cur).mean(axis=1)
    return out


def _bars_since(v: np.ndarray, w: int, fn: Callable[..., Any]) -> np.ndarray:
    out = np.full(v.size, np.nan)
    if v.size < w:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(v, w)
    with np.errstate(invalid="ignore"):
        pos = fn(np.nan_to_num(win, nan=-np.inf if fn is np.argmax else np.inf), axis=1)
    out[w - 1:] = (w - 1) - pos
    return out


def _peer_mask(x: np.ndarray, g: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sliding windows of `x` and the boolean mask of the bars that are the CURRENT bar's peers.

    WorldQuant's `group_rank` asks "is this name extreme against its PEERS?" rather than against
    the whole universe, and the desk has no universe to rank within -- it trades one instrument
    per cell. The transferable half of the idea survives the translation intact if the peer group
    is a STATE rather than a sector: the past `w` bars on the same side of `g`'s own window mean
    as the current bar. "Extreme for a bar like this one" is the question; the sector was only
    ever one way of saying which bars are alike.
    """
    from numpy.lib.stride_tricks import sliding_window_view
    xw = sliding_window_view(x, w)
    gw = sliding_window_view(g, w)
    with np.errstate(invalid="ignore"):
        centred = gw - np.nanmean(gw, axis=1, keepdims=True)
    side = np.sign(centred)
    peers = (side == side[:, -1:]) & np.isfinite(xw) & np.isfinite(gw)
    return xw, gw, peers


def _group_stat(x: np.ndarray, g: np.ndarray, w: int, how: str) -> np.ndarray:
    out = np.full(x.size, np.nan)
    if x.size < w or w < 2:
        return out
    xw, _gw, peers = _peer_mask(x, g, w)
    cur = xw[:, -1:]
    n = peers.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        if how == "rank":
            val = np.where(n > 1, (np.where(peers, xw <= cur, False)).sum(axis=1) / np.maximum(
                n, 1), np.nan)
        else:
            xs = np.where(peers, xw, np.nan)
            mu = np.nanmean(xs, axis=1)
            sd = np.nanstd(xs, axis=1)
            val = np.where((n > 2) & (sd > 1e-12), (cur[:, 0] - mu) / np.where(sd > 1e-12, sd,
                                                                              np.nan), np.nan)
    out[w - 1:] = val
    return out


def _decay(s: pd.Series, w: int) -> pd.Series:
    weights = np.arange(w, 0, -1, dtype=float)
    acc = pd.Series(0.0, index=s.index)
    for k in range(w):
        acc = acc + s.shift(k) * weights[k]
    return acc / weights.sum()


class Memo(Protocol):
    """What `evaluate` needs of a memo: a plain dict, or a `SubtreeCache` scope shared by every
    population. Structural, so neither side has to know about the other."""

    def __contains__(self, key: str) -> bool: ...
    def __getitem__(self, key: str) -> pd.Series: ...
    def __setitem__(self, key: str, value: pd.Series) -> None: ...


def evaluate(expr: Expr, frames: dict[str, pd.Series],
             _memo: Memo | None = None) -> pd.Series:
    """The expression as a float series on the frames' index. NaN where undefined. Never raises.

    `_memo` caches EVERY SUBTREE, not just the root: pass one `SubtreeCache.scope` and the whole
    search shares its work (see `SubtreeCache`).
    """
    idx = next(iter(frames.values())).index if frames else pd.Index([])
    memo: Memo = _memo if _memo is not None else {}
    key = json.dumps(expr, default=str)
    if key in memo:
        return memo[key]
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        try:
            out = _eval(expr, frames, idx, memo)
        except Exception:
            out = _nan(idx)
    out = out.astype(float).replace([np.inf, -np.inf], np.nan)
    memo[key] = out
    return out


def _eval(expr: Expr, frames: dict[str, pd.Series], idx: pd.Index,
          memo: Memo) -> pd.Series:
    if isinstance(expr, str):
        return frames[expr] if expr in frames else _nan(idx)
    if not isinstance(expr, (list, tuple)) or not expr:
        return _nan(idx)
    op = str(expr[0])
    if op in UNARY:
        a = evaluate(expr[1], frames, memo)
        return {"neg": lambda: -a, "abs": lambda: a.abs(), "sign": lambda: np.sign(a)}[op]()
    if op in WINDOWED:
        a = evaluate(expr[1], frames, memo)
        w = int(expr[2])
        if w < 1 or w > len(idx):
            return _nan(idx)
        if op == "delay":
            return a.shift(w)
        if op == "delta":
            return a - a.shift(w)
        if op in ("mean", "std", "min", "max", "sum"):
            r = a.rolling(w, min_periods=w)
            return getattr(r, op)()
        if op == "ts_rank":
            return pd.Series(_ts_rank(a.to_numpy(dtype=float), w), index=idx)
        if op == "zscore":
            r = a.rolling(w, min_periods=w)
            return (a - r.mean()) / r.std()
        if op == "decay":
            return _decay(a, w)
        if op == "bars_since_max":
            return pd.Series(_bars_since(a.to_numpy(dtype=float), w, np.argmax), index=idx)
        if op == "bars_since_min":
            return pd.Series(_bars_since(a.to_numpy(dtype=float), w, np.argmin), index=idx)
        if op == "atr_norm":
            atr = frames.get("atr")
            return _nan(idx) if atr is None else a / atr.rolling(w, min_periods=1).mean()
        if op == "ts_backfill":
            # BOUNDED forward fill, `wq_operators.ts_backfill`'s leakage guard reimplemented on
            # the grammar's own window vocabulary: a gap is covered, a dead series is not
            # invented. Forward only -- there is no backward fill anywhere in this grammar.
            return a.ffill(limit=w)
        if op == "scale":
            den = a.abs().rolling(w, min_periods=w).sum()
            return a / den.where(den > 1e-12)
    if op in BINARY:
        a, b = evaluate(expr[1], frames, memo), evaluate(expr[2], frames, memo)
        if op == "trade_when":
            # `wq_operators.trade_when`: take the signal where the gate holds, otherwise HOLD
            # THE PREVIOUS VALUE rather than going flat. The whole difference from a
            # multiplicative gate is turnover, and turnover is what the desk's costliest
            # measured signal died of. The gate is `a > 0` because a NaN cast to bool is True,
            # and a gate that is true where it was never measured is not a gate.
            return b.where(a > 0).ffill()
        if op == "add":
            return a + b
        if op == "sub":
            return a - b
        if op == "mul":
            return a * b
        if op == "div":
            return a / b.where(b.abs() > 1e-12)
        if op == "max2":
            return pd.concat([a, b], axis=1).max(axis=1)
        if op == "min2":
            return pd.concat([a, b], axis=1).min(axis=1)
    if op in BINARY_WINDOWED:
        a, b = evaluate(expr[1], frames, memo), evaluate(expr[2], frames, memo)
        w = int(expr[3])
        if w < 3 or w > len(idx):
            return _nan(idx)
        if op == "corr":
            return a.rolling(w, min_periods=w).corr(b)
        if op == "cov":
            return a.rolling(w, min_periods=w).cov(b)
        if op == "residual":
            cov = a.rolling(w, min_periods=w).cov(b)
            var = b.rolling(w, min_periods=w).var()
            beta = cov / var.where(var > 1e-18)
            return a - beta * b
        if op in ("group_rank", "group_zscore"):
            return pd.Series(_group_stat(a.to_numpy(dtype=float), b.to_numpy(dtype=float), w,
                                         "rank" if op == "group_rank" else "z"), index=idx)
    return _nan(idx)


# --------------------------------------------------------------------------- subtree cache
#: How much of a shared cache is worth holding. A series is one float per bar, so on ten years
#: of H1 bars an entry is ~60k floats: 20M cells is roughly 160 MB, which is what a swapless
#: 4 GB box can lend a search without racing the terminal it also runs. Both bounds evict
#: least-recently-used, so the cache degrades by forgetting rather than by dying.
CACHE_MAX_ENTRIES = 4096
CACHE_MAX_CELLS = 20_000_000


def frames_fingerprint(symbol: str, frames: dict[str, pd.Series]) -> str:
    """What makes two `frames` the SAME bars: the symbol, the index, and the terminals present.

    A cache shared by every population is only safe if a key cannot collide across symbols or
    across an appended hour of bars, and only useful if re-reading the same parquet gives the
    same key. The index endpoints and length pin the sample; the terminal names pin which
    series exist (drivers and externals come and go); the close checksum catches a revision
    that kept the shape -- a corrected bar, a re-resampled frame -- which is exactly the case
    a length-only key would serve stale.
    """
    idx = next(iter(frames.values())).index if frames else pd.Index([])
    close = frames.get("close")
    checksum = 0.0
    if isinstance(close, pd.Series) and close.size:
        arr = close.to_numpy(dtype=float)
        finite = arr[np.isfinite(arr)]
        checksum = float(finite.sum()) if finite.size else 0.0
    parts = (str(symbol), str(len(idx)), str(idx[0]) if len(idx) else "",
             str(idx[-1]) if len(idx) else "", ",".join(sorted(frames)), f"{checksum:.6e}")
    return hashlib.blake2b("|".join(parts).encode("utf-8"), digest_size=12).hexdigest()


class SubtreeCache:
    """Structural hash of a SUBTREE -> its evaluated series, keyed by (symbol, bars).

    WHY THE CACHE IS PER SUBTREE. The evolution memoised per CELL and the feature store per
    FEATURE, so `zscore(delta(close, 24), 240)` and `ts_rank(delta(close, 24), 48)` each
    recomputed `delta(close, 24)` from scratch, in every population, in every generation. Trees
    drawn from one grammar share their lower halves overwhelmingly -- that is what a grammar is
    -- so the shared unit of work is the subtree, not the expression. `evaluate` already
    recurses through a memo dict; a scope of this cache IS that memo, so every population that
    evaluates through it fills the same table and reads the others' work, and a subtree computed
    by the GP is free for the GFlowNet, the enumerator and the zoo mutation.

    NOTHING HERE IS AN APPROXIMATION. A hit is returned only for the identical tree on the
    identical bars; `frames_fingerprint` is what "identical bars" means.
    """

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES,
                 max_cells: int = CACHE_MAX_CELLS) -> None:
        self.max_entries = int(max_entries)
        self.max_cells = int(max_cells)
        self._store: dict[tuple[str, str], pd.Series] = {}
        self._cells = 0
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def scope(self, symbol: str, frames: dict[str, pd.Series]) -> _CacheScope:
        """The memo to hand `evaluate` for these bars. Cheap: it holds a key, not a copy."""
        return _CacheScope(self, frames_fingerprint(symbol, frames))

    def get(self, scope: str, tree_key: str) -> pd.Series | None:
        hit = self._store.pop((scope, tree_key), None)
        if hit is None:
            self.misses += 1
            return None
        self._store[(scope, tree_key)] = hit                     # touch: most recently used
        self.hits += 1
        return hit

    def put(self, scope: str, tree_key: str, series: pd.Series) -> None:
        k = (scope, tree_key)
        if k in self._store:
            self._cells -= int(self._store.pop(k).size)
        self._store[k] = series
        self._cells += int(series.size)
        while self._store and (len(self._store) > self.max_entries
                               or self._cells > self.max_cells):
            oldest = next(iter(self._store))
            self._cells -= int(self._store.pop(oldest).size)
            self.evictions += 1

    def stats(self) -> dict[str, int | float]:
        total = self.hits + self.misses
        return {"entries": len(self._store), "cells": self._cells, "hits": self.hits,
                "misses": self.misses, "evictions": self.evictions,
                "hit_rate": round(self.hits / total, 4) if total else 0.0}


class _CacheScope:
    """One `SubtreeCache` bound to one (symbol, bars), shaped like the memo `evaluate` wants."""

    def __init__(self, cache: SubtreeCache, scope: str) -> None:
        self.cache = cache
        self.scope = scope
        # `evaluate` asks `key in memo` and then `memo[key]`, so the lookup would happen twice
        # and be counted twice. One pending answer, remembered WITH the key it answers, makes
        # the pair one hit -- and a `__getitem__` for any other key still goes to the store.
        self._pending: tuple[str, pd.Series] | None = None

    @staticmethod
    def _digest(tree_key: str) -> str:
        return hashlib.blake2b(tree_key.encode("utf-8"), digest_size=12).hexdigest()

    def __contains__(self, tree_key: str) -> bool:
        hit = self.cache.get(self.scope, self._digest(tree_key))
        self._pending = None if hit is None else (tree_key, hit)
        return hit is not None

    def __getitem__(self, tree_key: str) -> pd.Series:
        if self._pending is not None and self._pending[0] == tree_key:
            return self._pending[1]
        hit = self.cache.get(self.scope, self._digest(tree_key))
        if hit is None:
            raise KeyError(tree_key)
        return hit

    def __setitem__(self, tree_key: str, series: pd.Series) -> None:
        self.cache.put(self.scope, self._digest(tree_key), series)


# --------------------------------------------------------------------------- the type system
#: Every terminal carries a DTYPE and every operator a signature. `type_of` refuses a tree that
#: adds a price to a volatility or correlates a spread with itself; `is_valid` requires a type.
#: This is alpha-foundry's strongly typed AST, reduced to what an MT5 desk needs.
#: THE FOURTEEN DECLARED TYPES. Five were here before (PRICE, RETURN, RATIO, ACTIVITY, SPREAD);
#: the nine added 2026-09-05 are the kinds of evidence an MT5 book actually trades on and could
#: not name -- so a claim, an LLM or a literature template that says "positioning" or "macro
#: surprise" now lands on a TYPE the algebra can check instead of on an untyped float. A type
#: exists here whether or not this hour's frames carry a series for it: the vocabulary is what
#: makes an unmeasured thing sayable, and `available_terminals` is what stops it being searched.
DECLARED_TYPES: tuple[str, ...] = (
    "PRICE", "RETURN", "RATIO", "ACTIVITY", "SPREAD",
    "VOLATILITY",            # realised dispersion of returns -- the risk the desk sizes against
    "FLOW",                  # signed order flow (here: ticks signed by their bar)
    "POSITIONING",           # who is already long: surveys, broker books, COT
    "EVENT",                 # scheduled-event proximity / intensity
    "MACRO",                 # macro surprise relative to expectation
    "FUNDAMENTAL",           # the instrument's own fundamentals (carry, earnings, inventory)
    "STATE_PROBABILITY",     # a regime posterior in [0, 1]
    "CROSS_SECTION",         # the instrument's percentile among the peers a CALLER supplied
    "EXECUTION_STATE",       # the desk's own fills: slippage, queue, rejects
)
DTYPES: dict[str, str] = {
    "close": "PRICE", "open": "PRICE", "high": "PRICE", "low": "PRICE",
    "ret": "RETURN", "range": "RATIO", "body": "RATIO", "activity": "ACTIVITY",
    "spread": "SPREAD", "atr": "PRICE", "vol": "VOLATILITY", "flow": "FLOW",
    "usd": "PRICE", "rates": "PRICE", "risk": "PRICE", "gold": "PRICE", "oil": "PRICE",
    "growth": "PRICE",
    "positioning": "POSITIONING", "event": "EVENT", "macro": "MACRO",
    "fundamental": "FUNDAMENTAL", "state_prob": "STATE_PROBABILITY", "xsec": "CROSS_SECTION",
    "fill_state": "EXECUTION_STATE",
}
#: Windowed operators: output dtype as a function of the input dtype.
_WINDOWED_OUT: dict[str, str] = {
    "delay": "same", "delta": "diff", "mean": "same", "std": "SCALE", "min": "same",
    "max": "same", "ts_rank": "RANK", "zscore": "Z", "decay": "same", "sum": "same",
    "bars_since_max": "COUNT", "bars_since_min": "COUNT", "atr_norm": "Z",
    "ts_backfill": "same", "scale": "Z",
}
_DIFF_OF: dict[str, str] = {"PRICE": "PRICE_DIFF", "RETURN": "RETURN", "RATIO": "RATIO",
                            "ACTIVITY": "ACTIVITY", "SPREAD": "SPREAD", "Z": "Z",
                            "RANK": "RANK", "COUNT": "COUNT", "PRICE_DIFF": "PRICE_DIFF",
                            "SCALE": "SCALE",
                            # A change in each new type is a quantity of the same kind: the
                            # change in positioning is still positioning, in lots.
                            **{t: t for t in DECLARED_TYPES[5:]}}
#: Dimensionless families that may be combined freely. The new SCORE types join it and the new
#: DIMENSIONED ones (FLOW in ticks, POSITIONING in lots, EXECUTION_STATE in pips) do NOT: a free
#: type is one whose values are pure numbers, and calling a lot count free is how a book ends up
#: adding lots to returns.
_FREE: frozenset[str] = frozenset({"Z", "RANK", "RATIO", "RETURN", "COUNT", "VOLATILITY",
                                   "STATE_PROBABILITY", "CROSS_SECTION", "MACRO",
                                   "FUNDAMENTAL", "EVENT"})
INVALID = "INVALID"


def type_of(expr: Expr) -> str:
    """The dtype of a tree, or INVALID when the composition is not meaningful."""
    if isinstance(expr, str):
        return DTYPES.get(expr, INVALID)
    if not isinstance(expr, (list, tuple)) or not expr:
        return INVALID
    op = str(expr[0])
    if op in UNARY:
        t = type_of(expr[1])
        return INVALID if t == INVALID else ("Z" if op == "sign" else t)
    if op in WINDOWED:
        t = type_of(expr[1])
        if t == INVALID:
            return INVALID
        rule = _WINDOWED_OUT[op]
        if op == "atr_norm":
            return "Z" if t in ("PRICE", "PRICE_DIFF") else INVALID
        if rule == "same":
            return t
        if rule == "diff":
            return _DIFF_OF.get(t, INVALID)
        return rule
    if op in BINARY:
        a, b = type_of(expr[1]), type_of(expr[2])
        if INVALID in (a, b):
            return INVALID
        if op == "trade_when":
            # The GATE must be a pure number -- something whose sign means "on" or "off". A
            # price is positive on every bar the desk has ever seen, so gating on one is a gate
            # that never fires, which reads in a report exactly like a gate that always does.
            return b if a in _FREE else INVALID
        if op in ("add", "sub", "max2", "min2"):
            if a == b:
                return a
            if a in _FREE and b in _FREE:
                return "Z"
            return INVALID                           # PRICE + VOLATILITY is not a claim
        if op == "mul":
            if a in _FREE and b in _FREE:
                return "Z"
            if a in _FREE or b in _FREE:
                return b if a in _FREE else a        # scaling by a dimensionless quantity
            return INVALID
        if op == "div":
            if a == b:
                return "RATIO"
            if b in _FREE:
                return a
            if a in _FREE:
                return "Z"
            return INVALID
    if op in BINARY_WINDOWED:
        a, b = type_of(expr[1]), type_of(expr[2])
        if INVALID in (a, b):
            return INVALID
        if op == "corr":
            return "Z"
        if op == "cov":
            return "SCALE"
        if op == "group_rank":
            return "RANK"
        if op == "group_zscore":
            return "Z"
        if op == "residual":
            return a
    return INVALID


def well_typed(expr: Expr) -> bool:
    return type_of(expr) != INVALID


# --------------------------------------------------------------------------- dimensional algebra
#: The type system says which COMPOSITIONS are meaningful; it does not say what a value is made
#: of. SCALE is one dtype whether it is std(close) in price units or std(ret) in none, so
#: `add(std(close, 24), std(ret, 24))` is well typed and still adds a price to a pure number.
#: Dimensions are the second check: every terminal carries integer exponents over three base
#: quantities and every operator keeps, combines or cancels them. `dimension_of` is None where
#: the exponents cannot be reconciled; `well_formed` demands both checks and `well_typed` is
#: left exactly as it was, so nothing already certified changes its verdict.
#:
#: The bases are price, count and time. Nothing in the closed operator set produces a time
#: exponent today: the bar is the grammar's clock, so a bar count (`bars_since_*`) is a pure
#: number, exactly as the type system's COUNT is a free type. The base is carried for the
#: terminal that will need it (a holding period, a funding interval), not for anything here.
BASE_DIMENSIONS = ("price", "count", "time")


@dataclass(frozen=True)
class Dimension:
    """Integer exponents over (price, count, time). `Dimension()` is dimensionless.

    `a + b` is the dimension of a product and `a - b` of a quotient -- exponents add and
    subtract -- which is the whole algebra; equality is the dataclass's own."""
    price: int = 0
    count: int = 0
    time: int = 0

    def __add__(self, other: Dimension) -> Dimension:
        return Dimension(self.price + other.price, self.count + other.count,
                         self.time + other.time)

    def __sub__(self, other: Dimension) -> Dimension:
        return Dimension(self.price - other.price, self.count - other.count,
                         self.time - other.time)

    @property
    def is_dimensionless(self) -> bool:
        return self.price == 0 and self.count == 0 and self.time == 0

    def __str__(self) -> str:
        parts = [f"{b}^{e}" for b, e in zip(BASE_DIMENSIONS, (self.price, self.count, self.time),
                                            strict=True) if e]
        return " ".join(parts) if parts else "1"


DIMENSIONLESS = Dimension()
PRICE_DIM = Dimension(price=1)
COUNT_DIM = Dimension(count=1)
#: `range` and `body` are (high - low) / close and (close - open) / close in `terminal_frames`:
#: divided by the close, so a pure number, like the RATIO dtype they carry. Were they a price,
#: `add(ret, range)` -- well typed, both free -- would have no dimension, and the type system and
#: this check would disagree on trees `random_expr` produces routinely. `spread` is the broker's
#: quote in points, a price difference. A driver is the other instrument's close: a price of
#: THAT instrument, which the algebra treats as price -- one base, not one per instrument --
#: so it does not claim that `add(close, gold)` mixes quantities; the type system does not
#: either, and the gauntlet is the judge of whether the sum means anything.
TERMINAL_DIMENSIONS: dict[str, Dimension] = {
    "close": PRICE_DIM, "open": PRICE_DIM, "high": PRICE_DIM, "low": PRICE_DIM,
    "ret": DIMENSIONLESS, "range": DIMENSIONLESS, "body": DIMENSIONLESS,
    "activity": COUNT_DIM, "spread": PRICE_DIM, "atr": PRICE_DIM,
    "vol": DIMENSIONLESS, "flow": COUNT_DIM,
    "positioning": COUNT_DIM, "event": DIMENSIONLESS, "macro": DIMENSIONLESS,
    "fundamental": DIMENSIONLESS, "state_prob": DIMENSIONLESS, "xsec": DIMENSIONLESS,
    "fill_state": PRICE_DIM,
    **dict.fromkeys(DRIVER_TERMINALS, PRICE_DIM),
}
#: Windowed operators that keep their input's dimension: a shifted, averaged, extreme, decayed,
#: summed, differenced, dispersed or gap-filled price is still a price.
_DIM_PRESERVING = frozenset({"delay", "delta", "mean", "std", "min", "max", "decay", "sum",
                             "ts_backfill"})
#: Windowed operators whose output is a pure number whatever went in: a rank, a z-score, a
#: bar count, a share of the window's own total.
_DIM_FREE = frozenset({"ts_rank", "zscore", "bars_since_max", "bars_since_min", "scale"})


def dimension_of(expr: Expr) -> Dimension | None:
    """The dimension of a tree, or None when its exponents cannot be reconciled.

    add / sub / max2 / min2 require equal dimensions; mul adds exponents and div subtracts;
    corr is a pure number and cov a product; residual keeps the first argument's (it is that
    argument minus a scaled copy of the other); atr_norm divides by the ATR, a price; sign is
    a pure number; neg and abs keep. Unknown tokens and malformed nodes are None, like INVALID.
    """
    if isinstance(expr, str):
        return TERMINAL_DIMENSIONS.get(expr)
    if not isinstance(expr, (list, tuple)) or not expr:
        return None
    op = str(expr[0])
    if op in UNARY:
        a = dimension_of(expr[1]) if len(expr) > 1 else None
        return None if a is None else (DIMENSIONLESS if op == "sign" else a)
    if op in WINDOWED:
        a = dimension_of(expr[1]) if len(expr) > 1 else None
        if a is None:
            return None
        if op in _DIM_PRESERVING:
            return a
        if op in _DIM_FREE:
            return DIMENSIONLESS
        return a - PRICE_DIM                                    # atr_norm
    if op in BINARY or op in BINARY_WINDOWED:
        if len(expr) < 3:
            return None
        a, b = dimension_of(expr[1]), dimension_of(expr[2])
        if a is None or b is None:
            return None
        if op in ("add", "sub", "max2", "min2"):
            return a if a == b else None
        if op in ("mul", "cov"):
            return a + b
        if op == "div":
            return a - b
        if op in ("corr", "group_rank", "group_zscore"):
            return DIMENSIONLESS
        if op == "trade_when":
            return b                                            # the signal's, held or taken
        return a                                                # residual
    return None


def dimensionless(expr: Expr) -> bool:
    return dimension_of(expr) == DIMENSIONLESS


# --------------------------------------------------------------------------- the unit algebra
#: DIMENSIONS ARE NOT UNITS, and the gap between them is where the last invalid alphas lived.
#: `spread` and `close` are both price^1, so the dimensional check passes `add(close, spread)` --
#: a quote in the account's price units plus a broker spread in POINTS. Same dimension, different
#: unit, and the sum is a number with no referent. So every terminal carries a NAMED unit, every
#: operator keeps, cancels or combines them, and `well_formed` demands the units reconcile.
#:
#: A unit here is a vector of integer exponents over the base units below, exactly as a dimension
#: is over (price, count, time) -- so quote/quote cancels to a pure number, quote x ticks is a
#: legal compound, and quote + ticks is nothing at all. Two units of the SAME dimension never add
#: even when a constant would convert them (percent and bps, lots and contracts): the grammar's
#: `evaluate` does arithmetic on the series it is handed and applies no conversion factor, so
#: adding a percent series to a bps series really is wrong by a factor of a hundred. Refusing is
#: the honest verdict; a silent conversion would be a fabricated one.
#:
#: ONE `quote` FOR EVERY INSTRUMENT, deliberately, and for the same reason the dimensional
#: algebra carries one price base: a driver terminal is another instrument's close, and the
#: grammar has no FX rate with which to say what adding it to this one means. `add(close, gold)`
#: is left to the gauntlet to judge as economics, not refused here as arithmetic.
BASE_UNITS: tuple[str, ...] = ("quote", "pips", "usd_per_oz", "ticks", "contracts", "lots",
                               "seconds", "bars", "percent", "bps")
#: What each base unit is a unit OF, so the unit algebra can never disagree with the dimensional
#: one. `bars`, `percent` and `bps` are pure numbers with a scale, not dimensions: the bar is the
#: grammar's clock (see `BASE_DIMENSIONS`) and a percentage is a number wearing a factor.
UNIT_DIMENSION: dict[str, Dimension] = {
    "quote": PRICE_DIM, "pips": PRICE_DIM, "usd_per_oz": PRICE_DIM,
    "ticks": COUNT_DIM, "contracts": COUNT_DIM, "lots": COUNT_DIM,
    "seconds": Dimension(time=1),
    "bars": DIMENSIONLESS, "percent": DIMENSIONLESS, "bps": DIMENSIONLESS,
}


@dataclass(frozen=True)
class Unit:
    """Integer exponents over `BASE_UNITS`, held sorted so equality is structural.

    `a + b` is the unit of a product and `a - b` of a quotient. `Unit()` is dimensionless: the
    unit of a return, a rank, a z-score and every other pure number.
    """

    exponents: tuple[tuple[str, int], ...] = ()

    @classmethod
    def of(cls, name: str, power: int = 1) -> Unit:
        return cls(((name, power),)) if power else cls()

    def _map(self) -> dict[str, int]:
        return dict(self.exponents)

    @staticmethod
    def _pack(m: dict[str, int]) -> Unit:
        return Unit(tuple(sorted((k, v) for k, v in m.items() if v)))

    def __add__(self, other: Unit) -> Unit:
        m = self._map()
        for k, v in other.exponents:
            m[k] = m.get(k, 0) + v
        return Unit._pack(m)

    def __sub__(self, other: Unit) -> Unit:
        m = self._map()
        for k, v in other.exponents:
            m[k] = m.get(k, 0) - v
        return Unit._pack(m)

    @property
    def is_dimensionless(self) -> bool:
        return not self.exponents

    @property
    def dimension(self) -> Dimension:
        """The dimension this unit is one of. Every unit HAS one, so the two checks agree."""
        out = DIMENSIONLESS
        for name, power in self.exponents:
            base = UNIT_DIMENSION.get(name, DIMENSIONLESS)
            step = base if power > 0 else Dimension() - base
            for _ in range(abs(power)):
                out = out + step
        return out

    def __str__(self) -> str:
        return " ".join(f"{n}^{p}" for n, p in self.exponents) if self.exponents else "1"


NO_UNIT = Unit()
#: The named units of the desk. `quote` is the instrument's own price unit; `pips` is what the
#: broker quotes a spread in; `usd_per_oz` is what gold is priced in and is NOT `quote` for any
#: other instrument; `ticks` is what an MT5 feed counts (it does not publish traded contracts);
#: `contracts` and `lots` are what a position is written in and never convert into one another
#: here, because the factor is the instrument's contract size and the grammar does not know it;
#: `seconds` is carried for the terminal that will be denominated in wall clock (a holding
#: period, a funding interval) rather than in bars.
UNITS: dict[str, Unit] = {n: Unit.of(n) for n in BASE_UNITS} | {"dimensionless": NO_UNIT}
QUOTE, PIPS, TICKS, LOTS, BARS = (UNITS["quote"], UNITS["pips"], UNITS["ticks"], UNITS["lots"],
                                  UNITS["bars"])
#: Every terminal's unit. `range` and `body` are divided by the close in `terminal_frames`, so
#: they are pure numbers; `ret` is a log return, also pure; `vol` is its dispersion, also pure.
#: `activity` and `flow` are TICK counts and say so, because calling them contracts would claim
#: a volume this broker does not publish. `positioning` is a net book in lots, `fill_state` a
#: realised slippage in pips, `state_prob` / `xsec` probabilities and percentiles.
TERMINAL_UNITS: dict[str, Unit] = {
    "close": QUOTE, "open": QUOTE, "high": QUOTE, "low": QUOTE, "atr": QUOTE,
    "ret": NO_UNIT, "range": NO_UNIT, "body": NO_UNIT, "vol": NO_UNIT,
    "activity": TICKS, "flow": TICKS, "spread": PIPS,
    "positioning": LOTS, "event": NO_UNIT, "macro": NO_UNIT, "fundamental": NO_UNIT,
    "state_prob": NO_UNIT, "xsec": NO_UNIT, "fill_state": PIPS,
    **dict.fromkeys(DRIVER_TERMINALS, QUOTE),
}


def unit_of(expr: Expr) -> Unit | None:
    """The unit of a tree, or None when its units cannot be reconciled.

    The rules are the dimensional ones read one level finer: add / sub / max2 / min2 demand
    EQUAL units, mul and cov add exponents, div subtracts, corr and the group operators are pure
    numbers, residual and trade_when carry the unit of the series they return, atr_norm divides
    by the ATR (a quote). `bars_since_*` is a bar count and says so, so it cannot be added to a
    return that happens to share its (empty) dimension.

    `unit_of(e) is not None` IMPLIES `dimension_of(e) is not None` -- every rule here is at
    least as strict as its dimensional twin -- which is why `well_formed` needs only this one.
    """
    if isinstance(expr, str):
        return TERMINAL_UNITS.get(expr)
    if not isinstance(expr, (list, tuple)) or not expr:
        return None
    op = str(expr[0])
    if op in UNARY:
        a = unit_of(expr[1]) if len(expr) > 1 else None
        return None if a is None else (NO_UNIT if op == "sign" else a)
    if op in WINDOWED:
        a = unit_of(expr[1]) if len(expr) > 1 else None
        if a is None:
            return None
        if op in _DIM_PRESERVING:
            return a
        if op in ("bars_since_max", "bars_since_min"):
            return BARS
        if op in _DIM_FREE:
            return NO_UNIT
        return a - QUOTE                                        # atr_norm
    if op in BINARY or op in BINARY_WINDOWED:
        if len(expr) < 3:
            return None
        a, b = unit_of(expr[1]), unit_of(expr[2])
        if a is None or b is None:
            return None
        if op in ("add", "sub", "max2", "min2"):
            return a if a == b else None
        if op in ("mul", "cov"):
            return a + b
        if op == "div":
            return a - b
        if op in ("corr", "group_rank", "group_zscore"):
            return NO_UNIT
        if op == "trade_when":
            return b if a.is_dimensionless else None            # a gate is a pure number
        return a                                                # residual
    return None


def well_formed(expr: Expr) -> bool:
    """Well typed AND unit-consistent: the stricter gate, and the one production runs.

    `well_typed` is UNCHANGED by this and by the promotion of `is_valid` -- the type system
    still says which compositions are meaningful and the unit algebra still says what the
    values are made of. Nothing already certified changes its verdict; what changes is that a
    tree failing either check can no longer be BUILT (see `is_valid`).
    """
    return well_typed(expr) and unit_of(expr) is not None


# --------------------------------------------------------------------------- structure
def terminals_in(expr: Expr) -> set[str]:
    if isinstance(expr, str):
        return {expr}
    out: set[str] = set()
    for c in (expr[1:] if isinstance(expr, (list, tuple)) else []):
        if isinstance(c, (str, list, tuple)):
            out |= terminals_in(c)
    return {t for t in out if t in TERMINALS}


def complexity(expr: Expr) -> int:
    if isinstance(expr, str):
        return 1
    return 1 + sum(complexity(c) for c in expr[1:] if isinstance(c, (str, list, tuple)))


def depth(expr: Expr) -> int:
    if isinstance(expr, str):
        return 0
    kids = [c for c in expr[1:] if isinstance(c, (str, list, tuple))]
    return 1 + (max(depth(c) for c in kids) if kids else 0)


def to_str(expr: Expr) -> str:
    if isinstance(expr, str):
        return expr
    op, args = expr[0], expr[1:]
    inner = ", ".join(to_str(a) if isinstance(a, (str, list, tuple)) else str(a) for a in args)
    return f"{op}({inner})"


def key(expr: Expr) -> str:
    return json.dumps(expr, separators=(",", ":"), default=str)


def kind_of(expr: Expr) -> str:
    """The tree's SEMANTIC kind, `"<DTYPE>@<unit>"`, or INVALID -- the two checks in one token.

    The typed samplers plan over kinds rather than dtypes, which is what makes an illegal action
    unofferable rather than merely rejectable: a slot that needs a PRICE in quote units will not
    be offered a SPREAD in pips, so `add(std(close, 24), std(ret, 24))` is not a tree the search
    can even reach. A string keeps every table in `generators` hashable and printable.
    """
    t = type_of(expr)
    if t == INVALID:
        return INVALID
    u = unit_of(expr)
    return INVALID if u is None else f"{t}@{u}"


#: Each terminal's kind, for the samplers' leaf tables.
TERMINAL_KINDS: dict[str, str] = {t: f"{DTYPES[t]}@{TERMINAL_UNITS[t]}" for t in TERMINALS}


def subtree_hash(expr: Expr) -> str:
    """A stable structural hash of a subtree: the same tree in any process hashes the same.

    `key` is already canonical JSON, so this is only its digest -- short enough to be a dict key
    in a cache shared by every population, stable across processes (unlike `hash`), and equal
    for two trees exactly when they are the same recipe.
    """
    return hashlib.blake2b(key(expr).encode("utf-8"), digest_size=12).hexdigest()


def is_valid(expr: Expr, allow_drivers: bool = True,
             terminals: Sequence[str] | None = None) -> bool:
    """THE PRODUCTION SCREEN: structurally valid AND well typed AND well formed.

    Promoted 2026-09-05. `well_formed` had no production caller: the screen was `well_typed`
    alone, so `add(std(close, 24), std(ret, 24))` -- a price dispersion plus a pure number --
    was constructible, sampleable, mutable-into and tradeable by `family_formula`. Every one of
    those paths runs this function, so promoting it here closes all of them at once, and the
    generators' action masks (`libs.research.generators`) close the door earlier still by never
    offering the action. `terminals` narrows the legal leaf set for a caller that knows which
    series it actually has; None means the whole declared vocabulary.
    """
    return _structurally_valid(expr, allow_drivers, terminals) and well_formed(expr)


def _structurally_valid(expr: Expr, allow_drivers: bool = True,
                        terminals: Sequence[str] | None = None) -> bool:
    if isinstance(expr, str):
        if terminals is not None:
            return expr in set(terminals)
        return expr in TERMINALS and (allow_drivers or expr not in DRIVER_TERMINALS)
    if not isinstance(expr, (list, tuple)) or not expr or depth(expr) > MAX_DEPTH:
        return False
    op = expr[0]
    if op in UNARY:
        return len(expr) == 2 and _structurally_valid(expr[1], allow_drivers, terminals)
    if op in WINDOWED:
        return (len(expr) == 3 and _structurally_valid(expr[1], allow_drivers, terminals)
                and isinstance(expr[2], int) and expr[2] in WINDOWS)
    if op in BINARY:
        return len(expr) == 3 and all(_structurally_valid(e, allow_drivers, terminals)
                                      for e in expr[1:3])
    if op in BINARY_WINDOWED:
        return (len(expr) == 4 and all(_structurally_valid(e, allow_drivers, terminals)
                                       for e in expr[1:3])
                and isinstance(expr[3], int) and expr[3] in WINDOWS)
    return False


# --------------------------------------------------------------------------- search moves
def random_expr(rng: np.random.Generator, max_depth: int = 3, allow_drivers: bool = True,
                tries: int = 40, terminals: Sequence[str] | None = None) -> Expr:
    """A random tree the production screen accepts: sampled until `is_valid` -- structure, type
    AND units -- says yes, with a bare terminal (always valid) as the floor after `tries`.

    `tries` rose from 24 to 40 when the screen gained the unit algebra: the raw draw is
    uniform over the operator set and now has to clear a stricter check, and the floor is a
    LEVEL rather than an alpha, so paying a few more draws to avoid it is the cheaper mistake.
    """
    pool = tuple(terminals) if terminals is not None else terminal_pool(allow_drivers)
    for _ in range(tries):
        e = _random_expr_raw(rng, max_depth, allow_drivers, terminals=pool)
        # `pool` is not re-asserted here: the raw draw took its leaves FROM it, so the default
        # screen is the same verdict, and passing it would make `is_valid` unmockable for the
        # sampler tests that stub the screen out.
        if is_valid(e, allow_drivers):
            return e
    return str(rng.choice(pool))


def _random_expr_raw(rng: np.random.Generator, max_depth: int = 3,
                     allow_drivers: bool = True, _d: int = 0,
                     terminals: Sequence[str] | None = None) -> Expr:
    terms = tuple(terminals) if terminals is not None else terminal_pool(allow_drivers)
    if _d >= max_depth or (_d > 0 and rng.random() < 0.3):
        return str(rng.choice(terms))
    kind = rng.choice(["unary", "windowed", "binary", "binary_windowed"],
                      p=[0.1, 0.5, 0.25, 0.15])
    w = int(rng.choice(WINDOWS))

    def _child() -> Expr:
        return _random_expr_raw(rng, max_depth, allow_drivers, _d + 1, terms)
    if kind == "unary":
        return [str(rng.choice(UNARY)), _child()]
    if kind == "windowed":
        return [str(rng.choice(WINDOWED)), _child(), w]
    if kind == "binary":
        return [str(rng.choice(BINARY)), _child(), _child()]
    return [str(rng.choice(BINARY_WINDOWED)), _child(), _child(), w]


def _paths(expr: Expr, prefix: tuple[int, ...] = ()) -> list[tuple[int, ...]]:
    out = [prefix]
    if isinstance(expr, (list, tuple)):
        for i, c in enumerate(expr[1:], start=1):
            if isinstance(c, (str, list, tuple)):
                out.extend(_paths(c, (*prefix, i)))
    return out


def _get(expr: Expr, path: tuple[int, ...]) -> Expr:
    for i in path:
        expr = expr[i]
    return expr


def _set(expr: Expr, path: tuple[int, ...], sub: Expr) -> Expr:
    if not path:
        return sub
    out = list(expr)
    out[path[0]] = _set(out[path[0]], path[1:], sub)
    return out


def _clone(expr: Expr) -> Expr:
    return json.loads(json.dumps(expr))


def mutate(expr: Expr, rng: np.random.Generator, allow_drivers: bool = True,
           terminals: Sequence[str] | None = None, tries: int = 12) -> Expr:
    """One structural move: window change, operator swap within class, terminal swap, or a
    subtree replaced by a fresh random one. Always returns a valid expression."""
    pool = tuple(terminals) if terminals is not None else terminal_pool(allow_drivers)
    e = _clone(expr)
    for _ in range(tries):
        paths = _paths(e)
        path = paths[int(rng.integers(len(paths)))]
        node = _get(e, path)
        move = rng.random()
        if isinstance(node, str):
            new: Expr = (str(rng.choice(pool)) if move < 0.6
                         else random_expr(rng, 2, allow_drivers, terminals=pool))
        elif move < 0.35 and node[0] in WINDOWED + BINARY_WINDOWED:
            new = list(node)
            new[-1] = int(rng.choice(WINDOWS))
        elif move < 0.65:
            cls = next(c for c in (UNARY, WINDOWED, BINARY, BINARY_WINDOWED) if node[0] in c)
            new = list(node)
            new[0] = str(rng.choice(cls))
        else:
            new = random_expr(rng, 2, allow_drivers, terminals=pool)
        cand = _set(e, path, new)
        if is_valid(cand, allow_drivers):
            return cand
    return e


def crossover(a: Expr, b: Expr, rng: np.random.Generator, allow_drivers: bool = True,
              tries: int = 12) -> Expr:
    """Swap a random subtree of `a` for a random subtree of `b`. No terminal pool: crossover
    moves subtrees that already exist rather than drawing new leaves."""
    for _ in range(tries):
        pa = _paths(a)
        pb = _paths(b)
        path_a = pa[int(rng.integers(len(pa)))]
        path_b = pb[int(rng.integers(len(pb)))]
        cand = _set(_clone(a), path_a, _clone(_get(b, path_b)))
        if is_valid(cand, allow_drivers):
            return cand
    return _clone(a)


def describe(expr: Expr, side_mode: str = "follow") -> str:
    """A mechanism sentence from the structure: what the expression measures and how it is used.

    Written AFTER the search, from the tree, exactly as the AI-explains-afterward step is meant
    to work: the description can be wrong about why it pays, never about what it computes.
    """
    ops = set()

    def _walk(x: Expr) -> None:
        if isinstance(x, (list, tuple)):
            ops.add(str(x[0]))
            for c in x[1:]:
                _walk(c)
    _walk(expr)
    terms = sorted(terminals_in(expr))
    if ops & {"group_rank", "group_zscore"}:
        shape = "an extremeness measure AGAINST BARS IN THE SAME STATE"
    elif ops & {"delta", "decay", "sum"} and "zscore" not in ops:
        shape = "a momentum-type measure"
    elif ops & {"zscore", "ts_rank", "scale"}:
        shape = "a normalised extremeness measure"
    elif ops & {"corr", "residual", "cov"}:
        shape = "a co-movement / residual measure"
    elif ops & {"bars_since_max", "bars_since_min", "max", "min"}:
        shape = "a distance-from-extreme measure"
    else:
        shape = "a level measure"
    # `trade_when` HOLDS the previous value where its gate fails, so the sentence has to say
    # so: a reader who takes it for the multiplicative gate reads the turnover backwards.
    held = ", held through the bars its gate does not admit" if "trade_when" in ops else ""
    use = ("followed in its own direction" if side_mode == "follow"
           else "faded against its direction")
    return (f"{to_str(expr)}: {shape} of {', '.join(terms)}{held}, z-scored on its own history "
            f"and {use} when it is extreme")
