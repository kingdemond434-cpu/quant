"""OPERATOR-EXACT FORMULA ENGINE: the published GTJA-191 and Qlib operator sets, on a panel.

WHY A SECOND EVALUATOR, AND WHY IT IS NOT A SECOND GRAMMAR. `alpha_grammar` is the desk's search
language: a closed, typed, unit-checked operator set the generators sample and mutate. Its
operators are deliberately the desk's own (a `decay`, a `ts_rank` on a fixed window vocabulary,
`rank` translated to time), and `alpha_dsl` transpiles the 101 published alphas INTO it by
semantic type, approximating where the desk has no analogue. That is right for search and wrong
for a LIBRARY: a GTJA formula re-said in the grammar is a different formula. This module
evaluates a published formula with the published operators, exactly as the publication defines
them, and nothing else. It is reached from the grammar through ONE node, `["lib", key]`
(`alpha_grammar.LIBRARY`), which is never sampled and never mutated: the search stays the
search, and a library cell is the publication's own recipe.

TWO DIALECTS, ONE PARSER. The publications spell operators differently and DEFINE them
differently, and the definition is the part that must not drift:

  gtja   Guotai Junan Securities, "基于短周期价量特征的多因子选股体系 -- 数量化专题之九十三"
         (2017-06-15), operator appendix. RANK is CROSS-SECTIONAL (within the panel on the same
         bar); TSRANK is the rank of the current value in its own last n; SMA(A,n,m) is the
         RECURSIVE Y' = (A*m + Y*(n-m))/n; WMA weights 0.9^i (i = bars before now); DECAYLINEAR
         weights d..1 summing to one; MAX/MIN of two arguments are ELEMENTWISE and TSMAX/TSMIN
         are the windows; HIGHDAY/LOWDAY count bars from the window's extreme to now (0 when it
         is the current bar); REGBETA/REGRESI regress on a series or on SEQUENCE(n) = 1..n;
         SUMIF/COUNT/PROD/FILTER/SUMAC as defined there. Windows require a FULL window: a value
         is NaN until n finite observations exist, and a NaN condition propagates NaN.
  qlib   Microsoft Qlib (MIT licence), `qlib/data/ops.py` and `qlib/data/_libs/rolling.pyx`,
         read from the published wheel pyqlib 0.9.7. Every Rolling operator uses
         `min_periods=1` (a partial window is a value, as Qlib computes it); Rank is the ROLLING
         percentile of the current value in its own window (not cross-sectional); Slope / Rsquare
         / Resi are OLS on the window position 1..N with NaN observations dropped; Corr and
         Rsquare are NaN where a rolling std is within 2e-5 of zero; IdxMax/IdxMin are
         `argmax + 1`; comparisons follow numpy (a NaN operand compares False).

THE PANEL. Every field is a DataFrame [bar x instrument]. Time-series operators act down each
column; the GTJA cross-sectional RANK acts across the row (the peer class on the same bar, NaN
members ignored). A single instrument is a one-column panel, so a formula with no RANK gives the
same series whether it is evaluated alone or among peers -- which `needs_panel` reports, and
which the producer and the judge's executor rely on.

THE FIELDS A BROKER FEED HAS, AND THE ONES IT DOES NOT. open/high/low/close and the broker's
TICK volume. `VOLUME`/`$volume` read tick counts, never exchange volume, and every formula that
reads them is marked `volume_proxy = "tick"` by the catalogue. VWAP, AMOUNT (turnover), a
benchmark index and the Fama-French factor returns do not exist on an MT5 feed: a formula that
needs one is NONTESTABLE with the field named, and the engine refuses to invent it (an absent
field raises `MissingField`, it never evaluates to a proxy).

Nothing here has authority: it computes series. Pure numpy/pandas, no I/O.
"""
from __future__ import annotations

import math
import re
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

import numpy as np
import pandas as pd

Panel: TypeAlias = pd.DataFrame
_DIALECTS: tuple[str, ...] = ("gtja", "qlib")


class FormulaError(ValueError):
    """The text is not a formula this engine can evaluate."""


class MissingField(FormulaError):
    """The formula reads a field the caller does not have (VWAP, AMOUNT, a benchmark...)."""


# ============================================================================ the parser
_TOKEN = re.compile(r"\s*(?:(\d+\.\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?|\d+(?:[eE][-+]?\d+)?)"
                    r"|(\$?[A-Za-z_][A-Za-z0-9_]*)|(&&|\|\||<=|>=|==|!=|[-+*/^(),?:<>=&|]))")


def tokens(text: str) -> list[tuple[str, str]]:
    """(kind, text) tokens: num / name / op. Raises FormulaError on a stray character."""
    out: list[tuple[str, str]] = []
    pos, s = 0, str(text)
    while pos < len(s):
        if s[pos:].strip() == "":
            break
        m = _TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise FormulaError(f"unexpected character {s[pos:pos + 10]!r} in {text!r}")
        pos = m.end()
        num, name, op = m.groups()
        if num is not None:
            out.append(("num", num))
        elif name is not None:
            out.append(("name", name))
        else:
            out.append(("op", op))
    return out


#: Binary operator precedence (higher binds tighter). `^` is right associative; a single `=`
#: is the publication's equality (GTJA writes CLOSE=DELAY(CLOSE,1)).
_BINARY: dict[str, int] = {"||": 1, "|": 1, "&&": 2, "&": 2,
                           "<": 3, ">": 3, "<=": 3, ">=": 3, "==": 3, "=": 3, "!=": 3,
                           "+": 4, "-": 4, "*": 5, "/": 5, "^": 7}


class _Parser:
    """Pratt parser -> nested tuples: ("num", v) | ("field", NAME) | ("call", NAME, args) |
    ("bin", op, a, b) | ("neg", a) | ("if", cond, a, b)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.toks = tokens(text)
        self.i = 0

    def peek(self) -> tuple[str, str] | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want: str | None) -> tuple[str, str]:
        t = self.peek()
        if t is None or (want is not None and t[1] != want):
            raise FormulaError(f"expected {want or 'a token'} at token {self.i} in {self.text!r}")
        self.i += 1
        return t

    def parse(self) -> Any:
        node = self.expr(0)
        if self.peek() is not None:
            raise FormulaError(f"trailing tokens from {self.i} in {self.text!r}")
        return node

    def expr(self, min_prec: int) -> Any:
        left = self.unary()
        while True:
            t = self.peek()
            if t is None or t[0] != "op":
                break
            op = t[1]
            if op == "?":
                if min_prec > 0:
                    break
                self.take("?")
                a = self.expr(0)
                self.take(":")
                b = self.expr(0)
                left = ("if", left, a, b)
                continue
            prec = _BINARY.get(op)
            if prec is None or prec < min_prec:
                break
            self.take(op)
            right = self.expr(prec if op == "^" else prec + 1)
            left = ("bin", "==" if op == "=" else op, left, right)
        return left

    def unary(self) -> Any:
        t = self.peek()
        if t is None:
            raise FormulaError(f"unexpected end of {self.text!r}")
        if t == ("op", "-"):
            self.take("-")
            return ("neg", self.expr(6))
        if t == ("op", "+"):
            self.take("+")
            return self.expr(6)
        return self.primary()

    def primary(self) -> Any:
        kind, text = self.take(None)
        if kind == "num":
            return ("num", float(text))
        if kind == "op" and text == "(":
            node = self.expr(0)
            self.take(")")
            return node
        if kind == "name":
            nxt = self.peek()
            if nxt == ("op", "("):
                self.take("(")
                args: list[Any] = []
                if self.peek() != ("op", ")"):
                    while True:
                        args.append(self.expr(0))
                        if self.peek() == ("op", ","):
                            self.take(",")
                            continue
                        break
                self.take(")")
                return ("call", text, tuple(args))
            return ("field", text)
        raise FormulaError(f"unexpected {text!r} in {self.text!r}")


def parse(text: str) -> Any:
    """The formula as a tree. Raises FormulaError on text that is not a well-formed formula."""
    return _Parser(text).parse()


def fields_in(tree: Any) -> set[str]:
    """Every field (bare name, `$name`) the tree reads -- the input requirement."""
    out: set[str] = set()

    def walk(n: Any) -> None:
        if not isinstance(n, tuple):
            return
        if n[0] == "field":
            out.add(str(n[1]))
        elif n[0] == "call":
            for a in n[2]:
                walk(a)
        else:
            for a in n[1:]:
                walk(a)
    walk(tree)
    return out


def calls_in(tree: Any) -> set[str]:
    out: set[str] = set()

    def walk(n: Any) -> None:
        if not isinstance(n, tuple):
            return
        if n[0] == "call":
            out.add(str(n[1]).upper())
            for a in n[2]:
                walk(a)
        elif n[0] in ("bin", "neg", "if"):
            for a in n[1:]:
                walk(a)
    walk(tree)
    return out


# ============================================================================ numeric helpers
def _f(x: Any) -> Panel:
    return x.astype(float) if isinstance(x, pd.DataFrame) else x


def _w(n: Any) -> int:
    """A window argument: a positive integer literal (the publications only use those)."""
    if isinstance(n, pd.DataFrame):
        raise FormulaError("a window must be a number, not a series")
    v = float(n)
    if not math.isfinite(v) or v < 0 or abs(v - round(v)) > 1e-9:
        raise FormulaError(f"window {n!r} is not a non-negative integer")
    return round(v)


def _like(template: Panel, values: np.ndarray) -> Panel:
    return pd.DataFrame(values, index=template.index, columns=template.columns)


def _windows(a: np.ndarray, n: int) -> np.ndarray:
    """[rows, cols, n] views of each column's trailing window, NaN-padded at the start."""
    pad = np.full((n - 1, a.shape[1]), np.nan)
    full = np.vstack([pad, a]) if n > 1 else a
    return np.lib.stride_tricks.sliding_window_view(full, n, axis=0)


_CHUNK = 4096


def _apply_windows(a: Panel, n: int, fn: Callable[[np.ndarray], np.ndarray]) -> Panel:
    """fn(windows[rows, cols, n]) -> [rows, cols], evaluated in row chunks (bounded memory)."""
    arr = a.to_numpy(dtype=float)
    out = np.full(arr.shape, np.nan)
    if n < 1 or arr.shape[0] == 0:
        return _like(a, out)
    view = _windows(arr, n)
    for s in range(0, arr.shape[0], _CHUNK):
        out[s:s + _CHUNK] = fn(view[s:s + _CHUNK])
    return _like(a, out)


def _full(win: np.ndarray) -> np.ndarray:
    return np.asarray(np.isfinite(win).all(axis=-1), dtype=bool)


def _linear_weights(weights: np.ndarray, a: Panel) -> Panel:
    """Weighted mean over a FULL finite window; weights ordered oldest -> newest."""
    w = np.asarray(weights, dtype=float)
    tot = w.sum()

    def fn(win: np.ndarray) -> np.ndarray:
        ok = _full(win)
        val = np.einsum("rcn,n->rc", np.nan_to_num(win), w) / tot
        return np.where(ok, val, np.nan)
    return _apply_windows(a, len(w), fn)


def _ts_rank_count(a: Panel, n: int) -> Panel:
    """1-based rank of the current value in its full window, ties averaged."""
    def fn(win: np.ndarray) -> np.ndarray:
        last = win[..., -1:]
        less = (win < last).sum(axis=-1)
        eq = (win == last).sum(axis=-1)
        val = 1.0 + less + (eq - 1) / 2.0
        return np.where(_full(win), val, np.nan)
    return _apply_windows(a, n, fn)


def _days_since(a: Panel, n: int, which: str) -> Panel:
    """Bars from the window's extreme to now; 0 when the extreme is the current bar. The first
    occurrence wins a tie (numpy's argmax/argmin), i.e. the OLDEST equal extreme."""
    def fn(win: np.ndarray) -> np.ndarray:
        ok = _full(win)
        safe = np.where(np.isfinite(win), win, 0.0)
        pos = safe.argmax(axis=-1) if which == "max" else safe.argmin(axis=-1)
        return np.where(ok, (n - 1) - pos, np.nan).astype(float)
    return _apply_windows(a, n, fn)


def _seq_slope(a: Panel, n: int) -> Panel:
    """OLS slope of the full window on x = 1..n."""
    x = np.arange(1, n + 1, dtype=float)
    xc = x - x.mean()
    den = float((xc ** 2).sum())
    if n < 2 or den == 0:
        return _like(a, np.full(a.shape, np.nan))

    def fn(win: np.ndarray) -> np.ndarray:
        ok = _full(win)
        val = np.einsum("rcn,n->rc", np.nan_to_num(win), xc) / den
        return np.where(ok, val, np.nan)
    return _apply_windows(a, n, fn)


def _seq_resi(a: Panel, n: int) -> Panel:
    """Residual of the CURRENT bar from the full-window OLS fit on x = 1..n."""
    slope = _seq_slope(a, n)
    mean = a.rolling(n, min_periods=n).mean()
    xbar = (n + 1) / 2.0
    return a - (mean + slope * (n - xbar))


# ---- the qlib rolling regression family, NaN-aware partial windows exactly as rolling.pyx
def _qlib_ols(a: Panel, n: int) -> tuple[np.ndarray, ...]:
    arr = a.to_numpy(dtype=float)
    view = _windows(arr, n)
    x = np.arange(1, n + 1, dtype=float)
    out = [np.full(arr.shape, np.nan) for _ in range(3)]
    for s in range(0, arr.shape[0], _CHUNK):
        win = view[s:s + _CHUNK]
        m = np.isfinite(win)
        y = np.where(m, win, 0.0)
        cnt = m.sum(axis=-1).astype(float)
        xs = (m * x).sum(axis=-1)
        x2 = (m * x * x).sum(axis=-1)
        ys = y.sum(axis=-1)
        y2 = (y * y).sum(axis=-1)
        xy = (y * x).sum(axis=-1)
        with np.errstate(all="ignore"):
            den = cnt * x2 - xs * xs
            slope = (cnt * xy - xs * ys) / den
            interp = ys / cnt - slope * xs / cnt
            resi = win[..., -1] - (slope * n + interp)
            r = (cnt * xy - xs * ys) / np.sqrt(den * (cnt * y2 - ys * ys))
        out[0][s:s + _CHUNK] = slope
        out[1][s:s + _CHUNK] = r * r
        out[2][s:s + _CHUNK] = resi
    return tuple(out)


def _isclose0(p: Panel) -> np.ndarray:
    return np.asarray(np.isclose(p.to_numpy(dtype=float), 0, atol=2e-05), dtype=bool)


# ============================================================================ operator tables
def _cmp(op: str, a: Any, b: Any, nan_false: bool) -> Any:
    fn = {"<": np.less, ">": np.greater, "<=": np.less_equal, ">=": np.greater_equal,
          "==": np.equal, "!=": np.not_equal}[op]
    with np.errstate(invalid="ignore"):
        r = fn(a, b)
    r = r.astype(float) if isinstance(r, pd.DataFrame) else float(r)
    if nan_false:
        return r
    nan = _nanmask(a) | _nanmask(b)
    if isinstance(r, pd.DataFrame) and nan is not False:
        r = r.mask(nan)
    return r


def _nanmask(x: Any) -> Any:
    if isinstance(x, pd.DataFrame):
        return x.isna()
    return isinstance(x, float) and math.isnan(x)


def _logic(op: str, a: Any, b: Any, nan_false: bool) -> Any:
    with np.errstate(invalid="ignore"):
        r = (a != 0) & (b != 0) if op in ("&&", "&") else (a != 0) | (b != 0)
    r = r.astype(float) if isinstance(r, pd.DataFrame) else float(r)
    if not nan_false and isinstance(r, pd.DataFrame):
        r = r.mask(_nanmask(a) | _nanmask(b)) if (isinstance(a, pd.DataFrame)
                                                  or isinstance(b, pd.DataFrame)) else r
    return r


def _gtja_rank(a: Panel) -> Panel:
    """Cross-sectional percentile rank within the panel on the same bar (ties averaged; NaN
    members ignored, a NaN member stays NaN). A bar with fewer than two finite members has no
    cross-section: the lone member ranks NaN, never 1.0 (a rank against itself is no signal)."""
    x = _f(a)
    r = x.rank(axis=1, pct=True, method="average")
    if isinstance(r, pd.DataFrame):
        lone = np.isfinite(x.to_numpy(dtype=float)).sum(axis=1) < 2
        r = r.mask(np.repeat(lone[:, None], r.shape[1], axis=1))
    return r


def _sma(a: Panel, n: Any, m: Any) -> Panel:
    nn, mm = float(n), float(m)
    if not (0 < mm <= nn):
        raise FormulaError(f"SMA needs 0 < m <= n, got n={n}, m={m}")
    return _f(a).ewm(alpha=mm / nn, adjust=False).mean()


def _regbeta(a: Panel, b: Any, n: int) -> Panel:
    if isinstance(b, tuple) and b and b[0] == "SEQUENCE":
        return _seq_slope(a, int(b[1] or n))
    cov = a.rolling(n, min_periods=n).cov(b)
    var = b.rolling(n, min_periods=n).var()
    return cov / var.where(var > 0)


def _regresi(a: Panel, b: Any, n: int) -> Panel:
    if isinstance(b, tuple) and b and b[0] == "SEQUENCE":
        return _seq_resi(a, int(b[1] or n))
    beta = _regbeta(a, b, n)
    alpha = a.rolling(n, min_periods=n).mean() - beta * b.rolling(n, min_periods=n).mean()
    return a - (alpha + beta * b)


def _prod(a: Panel, n: int) -> Panel:
    if n == 1:
        return _f(a)

    def fn(win: np.ndarray) -> np.ndarray:
        return np.where(_full(win), np.prod(np.nan_to_num(win), axis=-1), np.nan)
    return _apply_windows(a, n, fn)


def _qlib_rolling(name: str, a: Panel, n: int) -> Panel:
    r = _f(a).rolling(n, min_periods=1)
    return getattr(r, name)()


def _qlib_idx(a: Panel, n: int, which: str) -> Panel:
    fn = np.argmax if which == "max" else np.argmin
    return _f(a).rolling(n, min_periods=1).apply(lambda x: fn(x) + 1, raw=True)


def _qlib_corr(a: Panel, b: Panel, n: int) -> Panel:
    res = _f(a).rolling(n, min_periods=1).corr(_f(b))
    bad = (_isclose0(_f(a).rolling(n, min_periods=1).std())
           | _isclose0(_f(b).rolling(n, min_periods=1).std()))
    return res.mask(bad)


def _qlib_rsquare(a: Panel, n: int) -> Panel:
    _, r2, _ = _qlib_ols(_f(a), n)
    out = _like(a, r2)
    return out.mask(_isclose0(_f(a).rolling(n, min_periods=1).std()))


@dataclass(frozen=True)
class Op:
    """One published operator: arity (min, max), how windows are read, the implementation."""

    name: str
    arity: tuple[int, int]
    fn: Callable[..., Any]
    doc: str


def _need_df(x: Any, like: Panel) -> Panel:
    if isinstance(x, pd.DataFrame):
        return _f(x)
    return pd.DataFrame(float(x), index=like.index, columns=like.columns)


def _gtja_ops() -> dict[str, Op]:
    def mx(a: Any, b: Any) -> Any:
        return _elementwise(np.maximum, a, b)

    def mn(a: Any, b: Any) -> Any:
        return _elementwise(np.minimum, a, b)

    ops = [
        Op("DELAY", (1, 2), lambda a, n=1: _f(a).shift(_w(n)),
           "DELAY(A,n): A n bars ago (one-argument form = 1, as the report writes DELAY(CLOSE))"),
        Op("DELTA", (2, 2), lambda a, n: _f(a) - _f(a).shift(_w(n)), "DELTA(A,n) = A - DELAY(A,n)"),
        Op("SUM", (2, 2), lambda a, n: _f(a).rolling(_w(n), min_periods=_w(n)).sum(),
           "SUM(A,n): sum of the last n"),
        Op("MEAN", (2, 2), lambda a, n: _f(a).rolling(_w(n), min_periods=_w(n)).mean(),
           "MEAN(A,n): mean of the last n"),
        Op("MA", (2, 2), lambda a, n: _f(a).rolling(_w(n), min_periods=_w(n)).mean(),
           "MA(A,n): the report's alias of MEAN"),
        Op("STD", (2, 2), lambda a, n: _f(a).rolling(_w(n), min_periods=_w(n)).std(),
           "STD(A,n): sample standard deviation of the last n"),
        Op("TSMAX", (2, 2), lambda a, n: _f(a).rolling(_w(n), min_periods=_w(n)).max(),
           "TSMAX(A,n): max of the last n"),
        Op("TSMIN", (2, 2), lambda a, n: _f(a).rolling(_w(n), min_periods=_w(n)).min(),
           "TSMIN(A,n): min of the last n"),
        Op("MAX", (2, 2), mx, "MAX(A,B): elementwise maximum"),
        Op("MIN", (2, 2), mn, "MIN(A,B): elementwise minimum"),
        Op("CORR", (3, 3), lambda a, b, n: _f(a).rolling(_w(n), min_periods=_w(n)).corr(_f(b)),
           "CORR(A,B,n): correlation over the last n"),
        Op("COVIANCE", (3, 3),
           lambda a, b, n: _f(a).rolling(_w(n), min_periods=_w(n)).cov(_f(b)),
           "COVIANCE(A,B,n): covariance over the last n (the report's spelling)"),
        Op("RANK", (1, 1), _gtja_rank, "RANK(A): cross-sectional percentile rank on the bar"),
        Op("TSRANK", (2, 2), lambda a, n: _ts_rank_count(_f(a), _w(n)),
           "TSRANK(A,n): rank (1..n, ties averaged) of the current value in its last n"),
        Op("SMA", (3, 3), _sma, "SMA(A,n,m): Y' = (A*m + Y*(n-m))/n, recursive"),
        Op("WMA", (2, 2), lambda a, n: _linear_weights(0.9 ** np.arange(_w(n) - 1, -1, -1), _f(a)),
           "WMA(A,n): weights 0.9^i, i = bars before now, normalised"),
        Op("DECAYLINEAR", (2, 2),
           lambda a, d: _linear_weights(np.arange(1, _w(d) + 1, dtype=float), _f(a)),
           "DECAYLINEAR(A,d): weights d (now) .. 1 (oldest), normalised to one"),
        Op("REGBETA", (2, 3), lambda a, b, n=None: _regbeta(
            _f(a), b, _w(n) if n is not None else int(b[1]) if isinstance(b, tuple) else 0),
           "REGBETA(A,B,n): OLS slope of A on B (B = SEQUENCE(n) is 1..n)"),
        Op("REGRESI", (2, 3), lambda a, b, n=None: _regresi(
            _f(a), b, _w(n) if n is not None else int(b[1]) if isinstance(b, tuple) else 0),
           "REGRESI(A,B,n): residual of the current bar from that regression"),
        Op("SUMIF", (3, 3), lambda a, n, c: _f(a).where(_need_df(c, _f(a)) != 0, 0.0)
           .mask(_need_df(c, _f(a)).isna()).rolling(_w(n), min_periods=_w(n)).sum(),
           "SUMIF(A,n,cond): sum of A over the last n bars where cond holds"),
        Op("COUNT", (2, 2), lambda c, n: _f(c).rolling(_w(n), min_periods=_w(n)).sum(),
           "COUNT(cond,n): bars in the last n where cond holds"),
        Op("HIGHDAY", (2, 2), lambda a, n: _days_since(_f(a), _w(n), "max"),
           "HIGHDAY(A,n): bars from the last-n maximum to now"),
        Op("LOWDAY", (2, 2), lambda a, n: _days_since(_f(a), _w(n), "min"),
           "LOWDAY(A,n): bars from the last-n minimum to now"),
        Op("PROD", (2, 2), lambda a, n: _prod(_f(a), _w(n)), "PROD(A,n): product of the last n"),
        Op("LOG", (1, 1), lambda a: np.log(_f(a).where(_f(a) > 0))
           if isinstance(a, pd.DataFrame) else (math.log(a) if a > 0 else math.nan),
           "LOG(A): natural log (NaN where A <= 0)"),
        Op("ABS", (1, 1), lambda a: abs(a), "ABS(A)"),
        Op("SIGN", (1, 1), lambda a: np.sign(a), "SIGN(A)"),
        Op("FILTER", (2, 2), lambda a, c: _f(a).where(_need_df(c, _f(a)) != 0),
           "FILTER(A,cond): A where cond holds, else absent"),
        Op("SUMAC", (1, 1), lambda a: _f(a).cumsum(), "SUMAC(A): cumulative sum"),
    ]
    return {o.name: o for o in ops}


def _elementwise(fn: Callable[..., Any], a: Any, b: Any) -> Any:
    if isinstance(a, pd.DataFrame) or isinstance(b, pd.DataFrame):
        like = a if isinstance(a, pd.DataFrame) else b
        return _like(like, fn(_need_df(a, like).to_numpy(float), _need_df(b, like).to_numpy(float)))
    return float(fn(a, b))


def _qlib_ops() -> dict[str, Op]:
    ops = [
        Op("Ref", (2, 2), lambda a, n: _f(a).shift(_w(n)), "Ref(x,d): x d bars ago"),
        Op("Mean", (2, 2), lambda a, n: _qlib_rolling("mean", a, _w(n)), "rolling mean, min 1"),
        Op("Sum", (2, 2), lambda a, n: _qlib_rolling("sum", a, _w(n)), "rolling sum, min 1"),
        Op("Std", (2, 2), lambda a, n: _qlib_rolling("std", a, _w(n)), "rolling std, min 1"),
        Op("Max", (2, 2), lambda a, n: _qlib_rolling("max", a, _w(n)), "rolling max, min 1"),
        Op("Min", (2, 2), lambda a, n: _qlib_rolling("min", a, _w(n)), "rolling min, min 1"),
        Op("Quantile", (3, 3),
           lambda a, n, q: _f(a).rolling(_w(n), min_periods=1).quantile(float(q)),
           "rolling quantile (linear), min 1"),
        Op("Rank", (2, 2), lambda a, n: _f(a).rolling(_w(n), min_periods=1).rank(pct=True),
           "rolling percentile rank of the current value, min 1"),
        Op("IdxMax", (2, 2), lambda a, n: _qlib_idx(a, _w(n), "max"), "rolling argmax + 1"),
        Op("IdxMin", (2, 2), lambda a, n: _qlib_idx(a, _w(n), "min"), "rolling argmin + 1"),
        Op("Slope", (2, 2), lambda a, n: _like(a, _qlib_ols(_f(a), _w(n))[0]),
           "OLS slope on window position, NaN-aware"),
        Op("Rsquare", (2, 2), lambda a, n: _qlib_rsquare(a, _w(n)),
           "OLS r^2 on window position; NaN where rolling std ~ 0"),
        Op("Resi", (2, 2), lambda a, n: _like(a, _qlib_ols(_f(a), _w(n))[2]),
           "residual of the current value from that fit"),
        Op("Corr", (3, 3), lambda a, b, n: _qlib_corr(a, b, _w(n)),
           "rolling correlation, min 1; NaN where either rolling std ~ 0"),
        Op("Log", (1, 1), lambda a: np.log(_f(a)) if isinstance(a, pd.DataFrame) else math.log(a),
           "natural log"),
        Op("Abs", (1, 1), lambda a: abs(a), "absolute value"),
        Op("Greater", (2, 2), lambda a, b: _elementwise(np.maximum, a, b), "elementwise max"),
        Op("Less", (2, 2), lambda a, b: _elementwise(np.minimum, a, b), "elementwise min"),
    ]
    return {o.name: o for o in ops}


_OPERATORS: dict[str, dict[str, Op]] = {"gtja": _gtja_ops(), "qlib": _qlib_ops()}

#: The GTJA shorthand fields, defined in the report's own appendix and expanded in place.
_GTJA_MACROS: dict[str, str] = {
    "RET": "CLOSE/DELAY(CLOSE,1)-1",
    "DTM": "(OPEN<=DELAY(OPEN,1)?0:MAX((HIGH-OPEN),(OPEN-DELAY(OPEN,1))))",
    "DBM": "(OPEN>=DELAY(OPEN,1)?0:MAX((OPEN-LOW),(OPEN-DELAY(OPEN,1))))",
    "TR": "MAX(MAX(HIGH-LOW,ABS(HIGH-DELAY(CLOSE,1))),ABS(LOW-DELAY(CLOSE,1)))",
    "HD": "HIGH-DELAY(HIGH,1)",
    "LD": "DELAY(LOW,1)-LOW",
}

#: Field name -> the panel key a caller supplies. VOLUME is the broker's tick count.
_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "gtja": {"OPEN": "open", "HIGH": "high", "LOW": "low", "CLOSE": "close",
             "VOLUME": "volume", "VWAP": "vwap", "AMOUNT": "amount",
             "BANCHMARKINDEXCLOSE": "benchmark_close", "BANCHMARKINDEXOPEN": "benchmark_open",
             "MKT": "mkt", "SMB": "smb", "HML": "hml"},
    "qlib": {"$open": "open", "$high": "high", "$low": "low", "$close": "close",
             "$volume": "volume", "$vwap": "vwap"},
}


def required_fields(text: str, dialect: str) -> set[str]:
    """The panel keys a formula reads, macros expanded. Raises FormulaError if unparseable."""
    tree = parse(text)
    out: set[str] = set()
    for name in fields_in(tree):
        if dialect == "gtja" and name.upper() in _GTJA_MACROS:
            out |= required_fields(_GTJA_MACROS[name.upper()], dialect)
        elif name == "SEQUENCE":
            continue
        else:
            key = _FIELD_ALIASES[dialect].get(name if dialect == "qlib" else name.upper())
            if key is None:
                raise FormulaError(f"unknown field {name!r}")
            out.add(key)
    return out


def needs_panel(text: str, dialect: str) -> bool:
    """True when the formula ranks ACROSS instruments (GTJA RANK). Qlib's Rank is temporal."""
    return dialect == "gtja" and "RANK" in calls_in(parse(text))


class Evaluator:
    """Evaluate formulas of one dialect on one panel of fields, with a shared subtree memo."""

    def __init__(self, fields: Mapping[str, Panel], dialect: str) -> None:
        if dialect not in _DIALECTS:
            raise FormulaError(f"unknown dialect {dialect!r}")
        self.dialect = dialect
        self.fields = {k: _f(v) for k, v in fields.items()}
        self.ops = _OPERATORS[dialect]
        self.nan_false = dialect == "qlib"
        self.memo: dict[Any, Any] = {}
        any_panel = next(iter(self.fields.values()), None)
        if any_panel is None:
            raise FormulaError("no fields supplied")
        self.template: Panel = any_panel

    def field(self, name: str) -> Panel:
        if self.dialect == "gtja" and name.upper() in _GTJA_MACROS:
            return self.node(parse(_GTJA_MACROS[name.upper()]))
        key = _FIELD_ALIASES[self.dialect].get(name if self.dialect == "qlib" else name.upper())
        if key is None:
            raise FormulaError(f"unknown field {name!r}")
        if key not in self.fields:
            raise MissingField(f"{name} ({key}) is not on this feed")
        return self.fields[key]

    def evaluate(self, text: str) -> Panel:
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore")
            out = self.node(parse(text))
        if not isinstance(out, pd.DataFrame):
            out = pd.DataFrame(float(out), index=self.template.index,
                               columns=self.template.columns)
        return out.astype(float).replace([np.inf, -np.inf], np.nan)

    def node(self, n: Any) -> Any:
        if n in self.memo:
            return self.memo[n]
        out = self._node(n)
        self.memo[n] = out
        return out

    def _node(self, n: Any) -> Any:
        kind = n[0]
        if kind == "num":
            return float(n[1])
        if kind == "field":
            if n[1] == "SEQUENCE":
                return ("SEQUENCE", 0)
            return self.field(str(n[1]))
        if kind == "neg":
            return -self.node(n[1])
        if kind == "if":
            c, a, b = self.node(n[1]), self.node(n[2]), self.node(n[3])
            like = next((x for x in (c, a, b) if isinstance(x, pd.DataFrame)), self.template)
            cd, ad, bd = _need_df(c, like), _need_df(a, like), _need_df(b, like)
            out = ad.where(cd != 0, bd)
            return out.mask(cd.isna())
        if kind == "bin":
            op = n[1]
            a, b = self.node(n[2]), self.node(n[3])
            if op in ("<", ">", "<=", ">=", "==", "!="):
                return _cmp(op, a, b, self.nan_false)
            if op in ("&&", "&", "||", "|"):
                return _logic(op, a, b, self.nan_false)
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if isinstance(b, pd.DataFrame):
                    return a / b.where(b != 0)
                return a / b if b != 0 else a * math.nan
            if op == "^":
                return a ** b
            raise FormulaError(f"unknown operator {op!r}")
        if kind == "call":
            name = str(n[1])
            if self.dialect == "gtja" and name.upper() == "SEQUENCE":
                if len(n[2]) != 1:
                    raise FormulaError("SEQUENCE takes one argument")
                return ("SEQUENCE", _w(self.node(n[2][0])))
            op = self.ops.get(name.upper() if self.dialect == "gtja" else name)
            if op is None:
                raise FormulaError(f"unknown {self.dialect} operator {name!r}")
            lo, hi = op.arity
            if not lo <= len(n[2]) <= hi:
                raise FormulaError(f"{name} takes {lo}..{hi} arguments, got {len(n[2])}")
            args = [self.node(a) for a in n[2]]
            return op.fn(*args)
        raise FormulaError(f"unknown node {kind!r}")


def panel_from_bars(bars: Mapping[str, pd.DataFrame], index: pd.Index | None
                    ) -> dict[str, Panel]:
    """{symbol: OHLC(+tick_volume) frame} -> {field: panel}, aligned on `index` (None: the
    union). Members are REINDEXED, never forward-filled: a peer with no bar at a time is absent
    from that bar's cross-section, which is what "the peer class on the same date" means.
    `volume` is the broker's `tick_volume` and is absent when no member carries it."""
    syms = list(bars)
    if index is None:
        idx = pd.DatetimeIndex([])
        for s in syms:
            idx = idx.union(pd.DatetimeIndex(bars[s].index))
        index = idx
    out: dict[str, Panel] = {}
    for col, key in (("open", "open"), ("high", "high"), ("low", "low"), ("close", "close"),
                     ("tick_volume", "volume")):
        cols = {}
        for s in syms:
            df = bars[s]
            if col in df.columns:
                ser = df[col].astype(float)
                ser = ser[~ser.index.duplicated(keep="last")]
                cols[s] = ser.reindex(index)
        if cols and (key != "volume" or len(cols) == len(syms)):
            out[key] = pd.DataFrame(cols, index=index)[[s for s in syms if s in cols]]
    return out
