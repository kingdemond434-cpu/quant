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

TERMINALS are the desk's own bars (price, return, range, body, tick activity, the broker's
spread, ATR) and the economic driver roles of `economic_drivers` (USD, RATES, RISK, GOLD, OIL,
GROWTH) when a caller supplies them. Nothing cross-sectional: the desk trades one instrument per
cell, so cross-sectional rank is a different family, not an operator here.

REPRESENTATION is plain JSON so an expression IS its recipe: a terminal is a string, a node is
a list `[op, child, ...args]`. `to_str` renders it for a human; the recipe the gauntlet keeps is
the list. Two expressions with the same list are the same hypothesis and hash the same.
"""
from __future__ import annotations

import json
import warnings
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

Expr = Any                                      # str | list[Any]; JSON-shaped

BAR_TERMINALS = ("close", "open", "high", "low", "ret", "range", "body", "activity", "spread",
                 "atr")
DRIVER_TERMINALS = ("usd", "rates", "risk", "gold", "oil", "growth")
TERMINALS = BAR_TERMINALS + DRIVER_TERMINALS

UNARY = ("neg", "abs", "sign")
WINDOWED = ("delay", "delta", "mean", "std", "min", "max", "ts_rank", "zscore", "decay", "sum",
            "bars_since_max", "bars_since_min", "atr_norm")
BINARY = ("add", "sub", "mul", "div", "max2", "min2")
BINARY_WINDOWED = ("corr", "residual", "cov")
OPERATORS = UNARY + WINDOWED + BINARY + BINARY_WINDOWED
WINDOWS = (2, 3, 5, 8, 12, 24, 48, 120, 240)
MAX_DEPTH = 5

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
                    atr_n: int = 20) -> dict[str, pd.Series]:
    """Every terminal as a float series on `bars.index`. Missing ones are simply absent.

    `bars` is the resampled OHLC frame; `raw` is the original frame carrying the broker's
    `spread` and `tick_volume` (the resampler drops them -- see `family_spread_state`).
    Drivers are aligned to the bar index and forward-filled, which is the only causal join:
    the driver's last known close at each bar.
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
    src = raw if raw is not None else bars
    for col, name in (("spread", "spread"), ("tick_volume", "activity")):
        if col in src.columns:
            s = src[col].astype(float)
            if src is not bars:
                s.index = pd.DatetimeIndex(pd.to_datetime(s.index, utc=True, errors="coerce"))
                s = s.reindex(idx).ffill()
            out[name] = s
    for role, frame in (drivers or {}).items():
        key = str(role).lower()
        if key not in DRIVER_TERMINALS or frame is None or "close" not in frame.columns:
            continue
        s = frame["close"].astype(float)
        s.index = pd.DatetimeIndex(pd.to_datetime(s.index, utc=True, errors="coerce"))
        s = s[~s.index.duplicated(keep="last")].sort_index()
        out[key] = s.reindex(idx, method="ffill")
    return out


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


def _decay(s: pd.Series, w: int) -> pd.Series:
    weights = np.arange(w, 0, -1, dtype=float)
    acc = pd.Series(0.0, index=s.index)
    for k in range(w):
        acc = acc + s.shift(k) * weights[k]
    return acc / weights.sum()


def evaluate(expr: Expr, frames: dict[str, pd.Series],
             _memo: dict[str, pd.Series] | None = None) -> pd.Series:
    """The expression as a float series on the frames' index. NaN where undefined. Never raises."""
    idx = next(iter(frames.values())).index if frames else pd.Index([])
    memo = _memo if _memo is not None else {}
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
          memo: dict[str, pd.Series]) -> pd.Series:
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
    if op in BINARY:
        a, b = evaluate(expr[1], frames, memo), evaluate(expr[2], frames, memo)
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
    return _nan(idx)


# --------------------------------------------------------------------------- the type system
#: Every terminal carries a DTYPE and every operator a signature. `type_of` refuses a tree that
#: adds a price to a volatility or correlates a spread with itself; `is_valid` requires a type.
#: This is alpha-foundry's strongly typed AST, reduced to what an MT5 desk needs.
DTYPES: dict[str, str] = {
    "close": "PRICE", "open": "PRICE", "high": "PRICE", "low": "PRICE",
    "ret": "RETURN", "range": "RATIO", "body": "RATIO", "activity": "ACTIVITY",
    "spread": "SPREAD", "atr": "PRICE",
    "usd": "PRICE", "rates": "PRICE", "risk": "PRICE", "gold": "PRICE", "oil": "PRICE",
    "growth": "PRICE",
}
#: Windowed operators: output dtype as a function of the input dtype.
_WINDOWED_OUT: dict[str, str] = {
    "delay": "same", "delta": "diff", "mean": "same", "std": "SCALE", "min": "same",
    "max": "same", "ts_rank": "RANK", "zscore": "Z", "decay": "same", "sum": "same",
    "bars_since_max": "COUNT", "bars_since_min": "COUNT", "atr_norm": "Z",
}
_DIFF_OF: dict[str, str] = {"PRICE": "PRICE_DIFF", "RETURN": "RETURN", "RATIO": "RATIO",
                            "ACTIVITY": "ACTIVITY", "SPREAD": "SPREAD", "Z": "Z",
                            "RANK": "RANK", "COUNT": "COUNT", "PRICE_DIFF": "PRICE_DIFF",
                            "SCALE": "SCALE"}
#: Dimensionless families that may be combined freely.
_FREE: frozenset[str] = frozenset({"Z", "RANK", "RATIO", "RETURN", "COUNT"})
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
        if op == "residual":
            return a
    return INVALID


def well_typed(expr: Expr) -> bool:
    return type_of(expr) != INVALID


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


def is_valid(expr: Expr, allow_drivers: bool = True) -> bool:
    return _structurally_valid(expr, allow_drivers) and well_typed(expr)


def _structurally_valid(expr: Expr, allow_drivers: bool = True) -> bool:
    if isinstance(expr, str):
        return expr in TERMINALS and (allow_drivers or expr not in DRIVER_TERMINALS)
    if not isinstance(expr, (list, tuple)) or not expr or depth(expr) > MAX_DEPTH:
        return False
    op = expr[0]
    if op in UNARY:
        return len(expr) == 2 and _structurally_valid(expr[1], allow_drivers)
    if op in WINDOWED:
        return (len(expr) == 3 and _structurally_valid(expr[1], allow_drivers)
                and isinstance(expr[2], int) and expr[2] in WINDOWS)
    if op in BINARY:
        return len(expr) == 3 and all(_structurally_valid(e, allow_drivers) for e in expr[1:3])
    if op in BINARY_WINDOWED:
        return (len(expr) == 4 and all(_structurally_valid(e, allow_drivers) for e in expr[1:3])
                and isinstance(expr[3], int) and expr[3] in WINDOWS)
    return False


# --------------------------------------------------------------------------- search moves
def random_expr(rng: np.random.Generator, max_depth: int = 3,
                allow_drivers: bool = True, tries: int = 24) -> Expr:
    """A random WELL-TYPED tree: the raw generator is sampled until the type system accepts it,
    and falls back to a bare terminal (always typed) when it does not within `tries`."""
    for _ in range(tries):
        e = _random_expr_raw(rng, max_depth, allow_drivers)
        if is_valid(e, allow_drivers):
            return e
    return str(rng.choice(TERMINALS if allow_drivers else BAR_TERMINALS))


def _random_expr_raw(rng: np.random.Generator, max_depth: int = 3,
                     allow_drivers: bool = True, _d: int = 0) -> Expr:
    terms = TERMINALS if allow_drivers else BAR_TERMINALS
    if _d >= max_depth or (_d > 0 and rng.random() < 0.3):
        return str(rng.choice(terms))
    kind = rng.choice(["unary", "windowed", "binary", "binary_windowed"],
                      p=[0.1, 0.5, 0.25, 0.15])
    w = int(rng.choice(WINDOWS))
    if kind == "unary":
        return [str(rng.choice(UNARY)), _random_expr_raw(rng, max_depth, allow_drivers, _d + 1)]
    if kind == "windowed":
        return [str(rng.choice(WINDOWED)),
                _random_expr_raw(rng, max_depth, allow_drivers, _d + 1), w]
    if kind == "binary":
        return [str(rng.choice(BINARY)), _random_expr_raw(rng, max_depth, allow_drivers, _d + 1),
                _random_expr_raw(rng, max_depth, allow_drivers, _d + 1)]
    return [str(rng.choice(BINARY_WINDOWED)),
            _random_expr_raw(rng, max_depth, allow_drivers, _d + 1),
            _random_expr_raw(rng, max_depth, allow_drivers, _d + 1), w]


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


def mutate(expr: Expr, rng: np.random.Generator, allow_drivers: bool = True) -> Expr:
    """One structural move: window change, operator swap within class, terminal swap, or a
    subtree replaced by a fresh random one. Always returns a valid expression."""
    e = _clone(expr)
    for _ in range(8):
        paths = _paths(e)
        path = paths[int(rng.integers(len(paths)))]
        node = _get(e, path)
        move = rng.random()
        if isinstance(node, str):
            terms = TERMINALS if allow_drivers else BAR_TERMINALS
            new: Expr = (str(rng.choice(terms)) if move < 0.6
                         else random_expr(rng, 2, allow_drivers))
        elif move < 0.35 and node[0] in WINDOWED + BINARY_WINDOWED:
            new = list(node)
            new[-1] = int(rng.choice(WINDOWS))
        elif move < 0.65:
            cls = next(c for c in (UNARY, WINDOWED, BINARY, BINARY_WINDOWED) if node[0] in c)
            new = list(node)
            new[0] = str(rng.choice(cls))
        else:
            new = random_expr(rng, 2, allow_drivers)
        cand = _set(e, path, new)
        if is_valid(cand, allow_drivers):
            return cand
    return e


def crossover(a: Expr, b: Expr, rng: np.random.Generator,
              allow_drivers: bool = True) -> Expr:
    """Swap a random subtree of `a` for a random subtree of `b`."""
    for _ in range(8):
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
    if ops & {"delta", "decay", "sum"} and "zscore" not in ops:
        shape = "a momentum-type measure"
    elif ops & {"zscore", "ts_rank"}:
        shape = "a normalised extremeness measure"
    elif ops & {"corr", "residual", "cov"}:
        shape = "a co-movement / residual measure"
    elif ops & {"bars_since_max", "bars_since_min", "max", "min"}:
        shape = "a distance-from-extreme measure"
    else:
        shape = "a level measure"
    use = ("followed in its own direction" if side_mode == "follow"
           else "faded against its direction")
    return (f"{to_str(expr)}: {shape} of {', '.join(terms)}, z-scored on its own history and "
            f"{use} when it is extreme")
