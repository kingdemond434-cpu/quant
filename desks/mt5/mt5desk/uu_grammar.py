"""THE UNKNOWN-UNKNOWN GRAMMAR: a typed expression language over bar primitives, and the family
the sealed gauntlet rebuilds every expression-rule cell with.

WHY (principal 2026-09-30: "maximise them all fr breadth and unknown unknown minings all"). Every
family the desk holds was NAMED by somebody first -- a book, a forum, a video, a mechanism -- and
the mass screen (`mt5desk.mass_screen_rules`) widened that to a fixed feature set (returns,
z-scores, range position, vol ratio, range/ATR, clock, leader, carry). Neither can find a
relationship nobody thought to write down. This module is the language for one: expressions built
from primitives by transforms and combinators, evaluated causally on a symbol's own bars (and on
any cross-asset reference the expression itself names), so an open-ended search can enumerate or
evolve features no family names and the judge can rebuild each one from its text alone.

THE LANGUAGE (prefix, parenthesised, whitespace-free; the text IS the identity):

    leaf       r1 rng body uwick lwick gap lvol clv          price / volume primitives
               hod dow dom mend                             calendar primitives
               xr1@SYM xrng@SYM                             a cross-asset reference's r1 / rng
    unary      lagK sumK zK rankK emaK diffK volK  (K = a window in bars)   abs sign neg
    binary     sub ratio mul max min  corrK
    e.g.       z120(sum24(r1))     corr24(r1,lvol)     sub(rank120(rng),rank120(xrng@XAUUSD))

EVERY OPERATOR IS CAUSAL: bar i reads bars <= i only (rolling windows look back, lags are
positive, a cross-asset leaf is re-indexed onto this symbol's clock by the last reference bar
stamped at or before this bar -- the rule `mass_screen_rules.lead_features` already uses). The
test suite pins this by truncating the frame and comparing.

THE RULE the family trades is the mass screen's, with `feat` replaced by an expression: at the
close of bar i, when `expr op thr` (and the optional conditioner `cond_lo <= cond_expr < cond_hi`,
where `cond_expr` may be another expression or `hour`, and the optional clock), enter `direction`
at the next open with a `stop_atr` ATR stop and a `hold`-bar time exit, thinned by the one
law (`mass_screen_rules.thin`). The screen and the judge call the same `evaluate` on the same
bars and the same `signals_from_mask`, so what the screen measured is what the judge replays.

GRAMMARS (the family name is the grammar; the params are the whole identity), kept distinct so
the multiplicity ledger charges each grammar its own screened width:

    uu_unary    one primitive through one or two transforms
    uu_binary   a combinator over two transformed primitives
    uu_cross    an expression that names a cross-asset reference
    uu_cond     an expression conditioned on a second expression's tercile or a clock bucket
    uu_gp       a random / genetically mutated tree of depth <= 4

Mechanism: UNKNOWN by construction and counted as such (`axis_registry`), never guessed.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from mt5desk import mass_screen_rules as MR
from mt5desk.families import Signal, _h1

#: Carried in every cell's params, so a later language change is a new identity.
GRAMMAR_VERSION = 1
GRAMMARS = ("unary", "binary", "cross", "cond", "gp")

PRICE_LEAVES = ("r1", "rng", "body", "uwick", "lwick", "gap", "lvol", "clv")
CALENDAR_LEAVES = ("hod", "dow", "dom", "mend")
CROSS_LEAVES = ("xr1", "xrng")
_LEAVES = frozenset(PRICE_LEAVES + CALENDAR_LEAVES + CROSS_LEAVES)
#: Unary operators and the windows each may take (an empty tuple: the operator takes none).
UNARY: dict[str, tuple[int, ...]] = {
    "lag": (1, 2, 4, 8, 24), "sum": (4, 24, 120), "z": (24, 120, 480), "rank": (24, 120),
    "ema": (8, 48), "diff": (1, 24), "vol": (24, 120), "abs": (), "sign": (), "neg": (),
}
#: Binary combinators and their windows.
BINARY: dict[str, tuple[int, ...]] = {
    "sub": (), "ratio": (), "mul": (), "max": (), "min": (), "corr": (24, 120),
}
#: The largest window any operator takes -- the warm-up a caller must allow for.
MAX_WINDOW = 480
_EPS = 1e-12

_TOKEN = re.compile(r"\s*([A-Za-z_]+)(\d*)(@[A-Za-z0-9_.&-]+)?\s*")


class GrammarError(ValueError):
    """An expression the language does not define. Raised, never approximated."""


# ------------------------------------------------------------------------------ parsing
def parse(text: str) -> tuple:
    """`text` -> an AST of tuples: ("leaf", name, ref) | ("op", name, k, (children...))."""
    s = str(text or "").strip()
    node, pos = _parse(s, 0)
    if pos != len(s):
        raise GrammarError(f"trailing text at {pos} in {s!r}")
    return node


def _parse(s: str, pos: int) -> tuple[tuple, int]:
    m = _TOKEN.match(s, pos)
    if not m:
        raise GrammarError(f"expected a name at {pos} in {s!r}")
    name, digits, ref = m.group(1), m.group(2), m.group(3)
    pos = m.end()
    if digits and f"{name}{digits}" in _LEAVES and not (pos < len(s) and s[pos] == "("):
        name, digits = f"{name}{digits}", ""          # `r1`, `xr1@SYM`: a leaf, not a window
    if pos < len(s) and s[pos] == "(":
        if ref:
            raise GrammarError(f"an operator takes no @reference: {name}{ref}")
        args: list[tuple] = []
        pos += 1
        while True:
            child, pos = _parse(s, pos)
            args.append(child)
            if pos < len(s) and s[pos] == ",":
                pos += 1
                continue
            if pos < len(s) and s[pos] == ")":
                pos += 1
                break
            raise GrammarError(f"expected ',' or ')' at {pos} in {s!r}")
        k = int(digits) if digits else 0
        if name in UNARY:
            if len(args) != 1:
                raise GrammarError(f"{name} takes one argument")
            if UNARY[name] and k not in UNARY[name]:
                raise GrammarError(f"{name}{k}: window must be one of {UNARY[name]}")
            if not UNARY[name] and digits:
                raise GrammarError(f"{name} takes no window")
        elif name in BINARY:
            if len(args) != 2:
                raise GrammarError(f"{name} takes two arguments")
            if BINARY[name] and k not in BINARY[name]:
                raise GrammarError(f"{name}{k}: window must be one of {BINARY[name]}")
            if not BINARY[name] and digits:
                raise GrammarError(f"{name} takes no window")
        else:
            raise GrammarError(f"unknown operator {name!r}")
        return ("op", name, k, tuple(args)), pos
    if digits:
        raise GrammarError(f"a leaf takes no window: {name}{digits}")
    if name in CROSS_LEAVES:
        if not ref:
            raise GrammarError(f"{name} needs an @reference symbol")
        return ("leaf", name, ref[1:]), pos
    if ref:
        raise GrammarError(f"{name} takes no @reference")
    if name not in PRICE_LEAVES and name not in CALENDAR_LEAVES:
        raise GrammarError(f"unknown leaf {name!r}")
    return ("leaf", name, ""), pos


def render(node: tuple) -> str:
    """The canonical text of an AST (parse(render(x)) == x)."""
    if node[0] == "leaf":
        return f"{node[1]}@{node[2]}" if node[2] else str(node[1])
    _kind, name, k, args = node
    return f"{name}{k if k else ''}({','.join(render(a) for a in args)})"


def references(text: str) -> tuple[str, ...]:
    """Every cross-asset symbol an expression names, sorted."""
    out: set[str] = set()

    def walk(n: tuple) -> None:
        if n[0] == "leaf":
            if n[2]:
                out.add(str(n[2]))
            return
        for a in n[3]:
            walk(a)
    walk(parse(text))
    return tuple(sorted(out))


def depth(node: tuple) -> int:
    if node[0] == "leaf":
        return 0
    return 1 + max(depth(a) for a in node[3])


# ------------------------------------------------------------------------------ evaluation
def _leaf(df: pd.DataFrame, name: str) -> pd.Series:
    o = df["open"].astype("float64")
    h = df["high"].astype("float64")
    lo = df["low"].astype("float64")
    c = df["close"].astype("float64")
    span = (h - lo).where((h - lo) > 0)
    if name == "r1":
        return np.log(c.where(c > 0)).diff()
    if name == "rng":
        return np.log(h.where(h > 0) / lo.where(lo > 0))
    if name == "body":
        return (c - o) / span
    if name == "uwick":
        return (h - np.maximum(o, c)) / span
    if name == "lwick":
        return (np.minimum(o, c) - lo) / span
    if name == "gap":
        return np.log(o.where(o > 0) / c.shift(1).where(c.shift(1) > 0))
    if name == "clv":
        return (c - lo) / span
    if name == "lvol":
        vol = df["tick_volume"] if "tick_volume" in df.columns else (
            df["volume"] if "volume" in df.columns else None)
        if vol is None:
            return pd.Series(np.nan, index=df.index)
        return np.log1p(vol.astype("float64").clip(lower=0))
    idx = pd.DatetimeIndex(df.index)
    if name == "hod":
        return pd.Series(idx.hour.astype("float64"), index=df.index)
    if name == "dow":
        return pd.Series(idx.weekday.astype("float64"), index=df.index)
    if name == "dom":
        return pd.Series(idx.day.astype("float64"), index=df.index)
    if name == "mend":
        return pd.Series((idx.days_in_month - idx.day).astype("float64"), index=df.index)
    raise GrammarError(f"unknown leaf {name!r}")


#: Replaceable in tests: symbol -> H1 frame (or None). None means `mass_screen_rules.load_bars`.
REF_LOADER = None


def _ref_leaf(df: pd.DataFrame, name: str, ref: str) -> pd.Series:
    loader = REF_LOADER or MR.load_bars
    other = loader(str(ref))
    if other is None or len(other) == 0:
        return pd.Series(np.nan, index=df.index)
    other = _h1(other)
    s = _leaf(other, "r1" if name == "xr1" else "rng")
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.reindex(df.index, method="ffill")


def _rank(s: pd.Series, w: int) -> pd.Series:
    return s.rolling(w, min_periods=w).rank(pct=True)


def _eval(node: tuple, df: pd.DataFrame) -> pd.Series:
    if node[0] == "leaf":
        _k, name, ref = node
        return _ref_leaf(df, name, ref) if ref else _leaf(df, name)
    _kind, name, k, args = node
    a = _eval(args[0], df)
    if name == "lag":
        return a.shift(k)
    if name == "sum":
        return a.rolling(k, min_periods=k).sum()
    if name == "z":
        m = a.rolling(k, min_periods=k).mean()
        sd = a.rolling(k, min_periods=k).std()
        return (a - m) / sd.where(sd > _EPS)
    if name == "rank":
        return _rank(a, k)
    if name == "ema":
        return a.ewm(span=k, adjust=False, min_periods=k).mean()
    if name == "diff":
        return a.diff(k)
    if name == "vol":
        return a.rolling(k, min_periods=k).std()
    if name == "abs":
        return a.abs()
    if name == "sign":
        return np.sign(a)
    if name == "neg":
        return -a
    b = _eval(args[1], df)
    if name == "sub":
        return a - b
    if name == "ratio":
        return a / b.where(b.abs() > _EPS)
    if name == "mul":
        return a * b
    if name == "max":
        return np.maximum(a, b)
    if name == "min":
        return np.minimum(a, b)
    if name == "corr":
        return a.rolling(k, min_periods=k).corr(b)
    raise GrammarError(f"unknown operator {name!r}")


def evaluate(text: str, df: pd.DataFrame) -> np.ndarray:
    """The expression's value at every bar of `df` (already on its own clock), float64, NaN where
    undefined. Deterministic: the screen and the judge get the same numbers from the same bars."""
    node = _parsed(str(text))
    with np.errstate(all="ignore"):
        out = _eval(node, df)
    a = np.array(pd.to_numeric(out, errors="coerce"), dtype="float64", copy=True)
    a[~np.isfinite(a)] = np.nan
    return a


@lru_cache(maxsize=4096)
def _parsed(text: str) -> tuple:
    return parse(text)


# ------------------------------------------------------------------------------ the family
def rule_mask(h1: pd.DataFrame, *, expr: str, op: str, thr: float, cond_expr: str = "",
              cond_lo: float = -MR.OPEN_BOUND, cond_hi: float = MR.OPEN_BOUND, hour: int = -1,
              weekday: int = -1) -> np.ndarray:
    """The bars at whose close the rule fires, before thinning."""
    feats: dict[str, np.ndarray] = {expr: evaluate(expr, h1)}
    if cond_expr and cond_expr != "hour":
        feats[cond_expr] = evaluate(cond_expr, h1)
    hr, wd = MR.clock_arrays(h1)
    return MR.condition_mask(feats, hr, wd, feat=expr, op=op, thr=thr, cond_feat=cond_expr,
                             cond_lo=cond_lo, cond_hi=cond_hi, hour=hour, weekday=weekday)


def family_uu_rule(df: pd.DataFrame, side: int = 1, *, expr: str, op: str, thr: float,
                   direction: int, hold: int, stop_atr: float, cond_expr: str = "",
                   cond_lo: float = -MR.OPEN_BOUND, cond_hi: float = MR.OPEN_BOUND,
                   hour: int = -1, weekday: int = -1, atr_n: int = 20,
                   gv: int = GRAMMAR_VERSION) -> list[Signal]:
    """The one constructor every unknown-unknown grammar rebuilds through.

    `side` is accepted and IGNORED (the gauntlet passes side=1; the traded side is `direction`,
    part of the identity). `expr`, `op`, `thr`, `direction`, `hold` and `stop_atr` have no
    defaults on purpose, so a default-parameter sweep sets these families aside instead of
    minting an unscreened rule. A cross-asset reference is loaded by the family itself from the
    bar store, so the sealed `build_cell`'s ordinary `fn(h1, **params)` call needs no branch.
    """
    del side, gv
    h1 = _h1(df)
    if len(h1) < MR.VOL_MIN_PERIODS + 2:
        return []
    try:
        m = rule_mask(h1, expr=expr, op=op, thr=thr, cond_expr=cond_expr, cond_lo=cond_lo,
                      cond_hi=cond_hi, hour=hour, weekday=weekday)
    except GrammarError:
        return []
    return MR.signals_from_mask(h1, m, direction=direction, hold=hold, stop_atr=stop_atr,
                                atr_n=atr_n, tag="unknown_unknown")


UU_FAMILIES: dict[str, Any] = {f"uu_{g}": family_uu_rule for g in GRAMMARS}
