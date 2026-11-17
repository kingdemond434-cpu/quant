"""THE 101 FORMULAIC ALPHAS AS A CROSS-SECTIONAL PANEL -- the desk's own numpy operators.

WHAT THIS IS. Kakushadze, "101 Formulaic Alphas" (Wilmott 2016, arXiv:1601.00991, a public
paper) defines a small operator algebra -- rank, delay, delta, correlation, covariance, scale,
signedpower, decay_linear, ts_min / ts_max / ts_argmin / ts_argmax / ts_rank, sum, product,
stddev, indneutralize -- and 101 alphas written in it. This module implements that algebra FROM
THE PAPER'S OPERATOR DEFINITIONS in the desk's own numpy, and writes each alpha as desk code over
it. No formula text is carried here (`libs/research/alpha_dsl.py` keeps the transcription the
expression factory parses; this module is the evaluator the federation adapter runs). No third
party implementation is imported or copied: the graveyard marks one popular lineage DEAD because
its decay_linear back-filled -- a look-ahead -- and every operator below is strictly causal and
pinned so by a test that perturbs the future and checks the past did not move.

THE PANEL. A bundle is several symbols' bars. The panel is the UNION of their bar times (T rows)
by the symbols (N columns), with a PRESENCE mask: a symbol that did not print a bar at a time is
absent there, not zero. Two kinds of operator, exactly as the paper separates them:

  * CROSS-SECTIONAL (`rank`, `scale`, `indneutralize`): at each bar, across the symbols present.
  * TIME-SERIES (everything windowed): per symbol, over THAT SYMBOL'S OWN bars -- a window of
    d is the last d bars the symbol printed, never d rows of a grid it was absent from.

The paper's "day" is this panel's bar. A non-integer window is floored, as the paper says.

THE FIELDS AND THEIR DECLARED PROXIES. A CFD has no consolidated volume, no exchange VWAP, no
market capitalisation and no GICS industry. Each is named, never silently approximated:

  volume  -> TICK VOLUME (the count of quote changes Fusion publishes per bar)
  adv{d}  -> TICK-VOLUME ADV: the trailing d-bar mean of tick volume (a count, not dollars)
  vwap    -> TYPICAL PRICE (high + low + close) / 3 of the bar
  IndClass.{sector,industry,subindustry}
          -> the instrument's PEER CLASS from MetaTrader's own registry
             (`desks/mt5/research/universe_policy.peer_class`, falling back to the registry's
             `asset_class`), one level for all three: the broker has no finer tree
  cap     -> NO HONEST PROXY. An alpha that reads market capitalisation is UNMEASURED, by name.

An alpha that reads only open/high/low/close/returns is EXACT; one that reads any proxied field
is PROXIED (its proxies listed); one that reads `cap` is UNMEASURED. The status is MEASURED by
running the alpha on an instrumented panel (`census()`), never typed by hand.

WHAT THIS IS NOT. Nothing here ranks alphas, sizes, or approves. An alpha is a hypothesis; the
adapter charges it as a trial and the ten gates judge it.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

#: Declared proxies, field -> what stands in for it on a CFD. `cap` has none.
PROXIES: dict[str, str] = {
    "volume": "tick volume (quote-change count per bar; Fusion publishes no contract volume)",
    "adv": "tick-volume ADV: trailing mean of tick volume over the window (a count, not dollars)",
    "vwap": "typical price (high + low + close) / 3 of the bar (no exchange VWAP on a CFD)",
    "indclass": "peer class from MetaTrader's registry via universe_policy (one level for "
                "sector, industry and subindustry)",
}
#: Fields with NO honest proxy on a CFD: an alpha reading one is UNMEASURED.
NO_PROXY: dict[str, str] = {
    "cap": "market capitalisation does not exist for a CFD; no honest proxy",
}
STATUSES: tuple[str, ...] = ("EXACT", "PROXIED", "UNMEASURED")
#: Fewer symbols than this present at a bar and a cross-sectional rank there is NaN: a rank of
#: one is not a rank.
MIN_XS = 2


class Unmeasured(Exception):
    """Raised by a field that has no honest proxy; the alpha is UNMEASURED with the field named."""


def _win(d: float) -> int:
    """The paper's window rule: a non-integer d is floored; a window is at least one bar."""
    return max(1, math.floor(float(d)))


# ============================================================================ 1-D causal kernels
# Each takes ONE symbol's own series (its present bars, oldest first) and returns a series of the
# same length whose value at i reads only positions <= i. The first d-1 positions are NaN, and a
# window holding any NaN yields NaN: a value the window could not see is not filled from anywhere.

def _windows(x: np.ndarray, d: int) -> np.ndarray | None:
    if x.shape[0] < d:
        return None
    return np.lib.stride_tricks.sliding_window_view(x, d)


def _pad(x: np.ndarray, d: int, body: np.ndarray) -> np.ndarray:
    out = np.full(x.shape[0], np.nan)
    if body.shape[0]:
        out[d - 1:] = body
    return out


def _bad(w: np.ndarray) -> Any:
    return ~np.isfinite(w).all(axis=-1)


def k_delay(x: np.ndarray, d: int) -> np.ndarray:
    out = np.full(x.shape[0], np.nan)
    if d == 0:
        return x.astype(float).copy()
    if x.shape[0] > d:
        out[d:] = x[:-d]
    return out


def k_sum(x: np.ndarray, d: int) -> np.ndarray:
    w = _windows(x, d)
    return np.full(x.shape[0], np.nan) if w is None else _pad(x, d, w.sum(axis=-1))


def k_product(x: np.ndarray, d: int) -> np.ndarray:
    w = _windows(x, d)
    return np.full(x.shape[0], np.nan) if w is None else _pad(x, d, w.prod(axis=-1))


def k_min(x: np.ndarray, d: int) -> np.ndarray:
    w = _windows(x, d)
    return np.full(x.shape[0], np.nan) if w is None else _pad(x, d, w.min(axis=-1))


def k_max(x: np.ndarray, d: int) -> np.ndarray:
    w = _windows(x, d)
    return np.full(x.shape[0], np.nan) if w is None else _pad(x, d, w.max(axis=-1))


def k_stddev(x: np.ndarray, d: int) -> np.ndarray:
    w = _windows(x, d)
    if w is None:
        return np.full(x.shape[0], np.nan)
    m = w.mean(axis=-1, keepdims=True)
    return _pad(x, d, np.sqrt(((w - m) ** 2).mean(axis=-1)))


def k_argmax(x: np.ndarray, d: int) -> np.ndarray:
    """Position of the window's maximum, 0 = the oldest bar of the window, d-1 = this bar."""
    w = _windows(x, d)
    if w is None:
        return np.full(x.shape[0], np.nan)
    body = np.argmax(np.where(np.isfinite(w), w, -np.inf), axis=-1).astype(float)
    body[_bad(w)] = np.nan
    return _pad(x, d, body)


def k_argmin(x: np.ndarray, d: int) -> np.ndarray:
    w = _windows(x, d)
    if w is None:
        return np.full(x.shape[0], np.nan)
    body = np.argmin(np.where(np.isfinite(w), w, np.inf), axis=-1).astype(float)
    body[_bad(w)] = np.nan
    return _pad(x, d, body)


def k_tsrank(x: np.ndarray, d: int) -> np.ndarray:
    """This bar's rank within its own last d values, in [0, 1] (ties take the average)."""
    w = _windows(x, d)
    if w is None:
        return np.full(x.shape[0], np.nan)
    last = w[:, -1:]
    below = (w < last).sum(axis=-1)
    ties = (w == last).sum(axis=-1) - 1
    body = (below + 0.5 * ties) / max(d - 1, 1)
    body = body.astype(float)
    body[_bad(w)] = np.nan
    return _pad(x, d, body)


def k_decay_linear(x: np.ndarray, d: int) -> np.ndarray:
    """Weighted mean with weights d, d-1, ..., 1 -- d on THIS bar -- normalised to sum to one.
    A NaN anywhere in the window is NaN: nothing is back-filled (the defect of the DEAD lineage)."""
    w = _windows(x, d)
    if w is None:
        return np.full(x.shape[0], np.nan)
    wt = np.arange(1, d + 1, dtype=float)
    return _pad(x, d, w @ (wt / wt.sum()))


def _k_moments(x: np.ndarray, y: np.ndarray, d: int
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    wx, wy = _windows(x, d), _windows(y, d)
    if wx is None or wy is None:
        return None
    xc = wx - wx.mean(axis=-1, keepdims=True)
    yc = wy - wy.mean(axis=-1, keepdims=True)
    return (xc * yc).mean(axis=-1), (xc * xc).mean(axis=-1), (yc * yc).mean(axis=-1)


def k_covariance(x: np.ndarray, y: np.ndarray, d: int) -> np.ndarray:
    mom = _k_moments(x, y, d)
    return np.full(x.shape[0], np.nan) if mom is None else _pad(x, d, mom[0])


def k_correlation(x: np.ndarray, y: np.ndarray, d: int) -> np.ndarray:
    """Pearson correlation over the last d bars; NaN where either side does not vary (a flat
    window has no correlation, and inventing 0 or 1 there would be a number nobody measured)."""
    if d < 2:
        return np.full(x.shape[0], np.nan)
    mom = _k_moments(x, y, d)
    if mom is None:
        return np.full(x.shape[0], np.nan)
    cxy, vx, vy = mom
    den = np.sqrt(vx * vy)
    tiny = 1e-14 * (1.0 + np.abs(den))
    body = np.where(den > tiny, cxy / np.where(den > tiny, den, 1.0), np.nan)
    return _pad(x, d, np.clip(body, -1.0, 1.0))


# ============================================================================ the panel
@dataclass
class Panel:
    """T bars x N symbols, oldest first, with a presence mask and each symbol's peer class."""

    symbols: tuple[str, ...]
    times: tuple[str, ...]
    o: np.ndarray
    h: np.ndarray
    lo: np.ndarray
    c: np.ndarray
    v: np.ndarray
    present: np.ndarray
    groups: tuple[str, ...]

    def __post_init__(self) -> None:
        self._idx = [np.flatnonzero(self.present[:, j]) for j in range(self.present.shape[1])]
        self.touched: set[str] = set()
        self.windows: list[int] = []
        self._adv: dict[int, np.ndarray] = {}

    @property
    def shape(self) -> tuple[int, int]:
        return (int(self.present.shape[0]), int(self.present.shape[1]))

    # ------------------------------------------------------------------- fields
    @property
    def open(self) -> np.ndarray:
        return self.o

    @property
    def high(self) -> np.ndarray:
        return self.h

    @property
    def low(self) -> np.ndarray:
        return self.lo

    @property
    def close(self) -> np.ndarray:
        return self.c

    @property
    def returns(self) -> np.ndarray:
        return self.ts(self.c, lambda s: s / k_delay(s, 1) - 1.0)

    @property
    def volume(self) -> np.ndarray:
        self.touched.add("volume")
        return self.v

    @property
    def vwap(self) -> Any:
        self.touched.add("vwap")
        return (self.h + self.lo + self.c) / 3.0

    @property
    def cap(self) -> np.ndarray:
        self.touched.add("cap")
        raise Unmeasured("cap")

    def adv(self, d: float) -> np.ndarray:
        self.touched.add("adv")
        n = _win(d)
        if n not in self._adv:
            self._adv[n] = self.ts(self.v, lambda s: k_sum(s, n) / n)
        return self._adv[n]

    # ------------------------------------------------------------------- plumbing
    def ts(self, x: np.ndarray, fn: Callable[[np.ndarray], np.ndarray]) -> np.ndarray:
        """Apply a 1-D causal kernel to each symbol over ITS OWN present bars."""
        out = np.full(self.shape, np.nan)
        for j, idx in enumerate(self._idx):
            if idx.size:
                out[idx, j] = fn(x[idx, j])
        return out

    def ts2(self, x: np.ndarray, y: np.ndarray,
            fn: Callable[[np.ndarray, np.ndarray], np.ndarray]) -> np.ndarray:
        out = np.full(self.shape, np.nan)
        for j, idx in enumerate(self._idx):
            if idx.size:
                out[idx, j] = fn(x[idx, j], y[idx, j])
        return out

    def _d(self, d: float) -> int:
        n = _win(d)
        self.windows.append(n)
        return n

    # ------------------------------------------------------------------- time-series operators
    def delay(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_delay(s, n))

    def delta(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: s - k_delay(s, n))

    def sum(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_sum(s, n))

    def product(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_product(s, n))

    def stddev(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_stddev(s, n))

    def ts_min(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_min(s, n))

    def ts_max(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_max(s, n))

    def ts_argmax(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_argmax(s, n))

    def ts_argmin(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_argmin(s, n))

    def ts_rank(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_tsrank(s, n))

    def decay_linear(self, x: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts(x, lambda s: k_decay_linear(s, n))

    def correlation(self, x: np.ndarray, y: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts2(x, y, lambda a, b: k_correlation(a, b, n))

    def covariance(self, x: np.ndarray, y: np.ndarray, d: float) -> np.ndarray:
        n = self._d(d)
        return self.ts2(x, y, lambda a, b: k_covariance(a, b, n))

    # ------------------------------------------------------------------- cross-sectional
    def rank(self, x: np.ndarray) -> np.ndarray:
        """At each bar, the symbol's rank among the symbols present, in [0, 1], ties averaged."""
        return xs_rank(np.where(self.present, x, np.nan))

    def scale(self, x: np.ndarray, a: float = 1.0) -> np.ndarray:
        """Rescale each bar's cross-section so its absolute values sum to `a`."""
        x = np.where(self.present & np.isfinite(x), x, np.nan)
        tot = np.nansum(np.abs(x), axis=1, keepdims=True)
        return np.where(tot > 0, x * a / np.where(tot > 0, tot, 1.0), np.nan)

    def indneutralize(self, x: np.ndarray) -> np.ndarray:
        """Demean each bar's cross-section within each peer class (MetaTrader's registry). A
        class with fewer than two members present at a bar has nothing to be neutral against."""
        self.touched.add("indclass")
        x = np.where(self.present & np.isfinite(x), x, np.nan)
        out = np.full(self.shape, np.nan)
        for g in sorted(set(self.groups)):
            if not g:
                continue
            cols = [j for j, gg in enumerate(self.groups) if gg == g]
            sub = x[:, cols]
            ok = np.isfinite(sub)
            cnt = ok.sum(axis=1, keepdims=True)
            mean = np.where(ok, sub, 0.0).sum(axis=1, keepdims=True) / np.maximum(cnt, 1)
            out[:, cols] = np.where(ok & (cnt >= 2), sub - mean, np.nan)
        return out


def row_ranks(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Row-wise 1-based average-tie ranks of the finite entries (NaN elsewhere) and the count of
    finite entries per row -- by comparison, vectorised (T x N x N, N is a bundle's width)."""
    ok = np.isfinite(x)
    v = np.where(ok, x, 0.0)
    both = ok[:, :, None] & ok[:, None, :]
    less = ((v[:, None, :] < v[:, :, None]) & both).sum(axis=2)
    equal = ((v[:, None, :] == v[:, :, None]) & both).sum(axis=2)
    r = less + (equal + 1) / 2.0
    return np.where(ok, r, np.nan), ok.sum(axis=1)


def xs_rank(x: np.ndarray) -> np.ndarray:
    """Row-wise average-tie rank of the finite entries, scaled to [0, 1]; NaN where a row has
    fewer than MIN_XS finite entries."""
    r, cnt = row_ranks(x)
    den = np.where(cnt >= MIN_XS, cnt - 1, 1)[:, None]
    return np.where((cnt >= MIN_XS)[:, None], (r - 1.0) / den, np.nan)


def avg_rank(v: np.ndarray) -> np.ndarray:
    """1-based ranks with ties averaged (numpy only)."""
    _uniq, inv, counts = np.unique(v, return_inverse=True, return_counts=True)
    upper = np.cumsum(counts)
    return (upper - (counts - 1) / 2.0)[inv].astype(float)


# ============================================================================ element-wise
def sign(x: np.ndarray) -> Any:
    return np.sign(x)


def signedpower(x: np.ndarray, a: Any) -> Any:
    return np.sign(x) * np.power(np.abs(x), a)


def lt(a: Any, b: Any) -> np.ndarray:
    """a < b as 1.0 / 0.0, NaN where either side is not finite."""
    a_, b_ = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ok = np.isfinite(a_) & np.isfinite(b_)
    return np.where(ok, (a_ < b_).astype(float), np.nan)


def iff(cond: np.ndarray, a: Any, b: Any) -> np.ndarray:
    """The paper's ternary `cond ? a : b`; NaN where the condition itself is unknown."""
    a_ = np.broadcast_to(np.asarray(a, dtype=float), cond.shape)
    b_ = np.broadcast_to(np.asarray(b, dtype=float), cond.shape)
    return np.where(np.isnan(cond), np.nan, np.where(cond > 0.5, a_, b_))


def emax(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.where(np.isfinite(a) & np.isfinite(b), np.maximum(a, b), np.nan)


def emin(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.where(np.isfinite(a) & np.isfinite(b), np.minimum(a, b), np.nan)


def _mix(a: np.ndarray, b: np.ndarray, w: float) -> np.ndarray:
    """w * a + (1 - w) * b -- the paper's weighted field blends."""
    return a * w + b * (1.0 - w)


# ============================================================================ the 101 alphas
# Each is desk code over the operators above, written from the paper's definitions. `p` is the
# panel. Field blends whose two legs are the SAME field (e.g. a vwap-with-vwap mix) reduce to that
# field and are written as it.

def _t46(p: Panel) -> Any:
    c = p.close
    return (p.delay(c, 20) - p.delay(c, 10)) / 10.0 - (p.delay(c, 10) - c) / 10.0


def _a001(p: Panel) -> Any:
    r = p.returns
    base = iff(lt(r, 0.0), p.stddev(r, 20), p.close)
    return p.rank(p.ts_argmax(signedpower(base, 2.0), 5)) - 0.5


def _a002(p: Panel) -> Any:
    return -p.correlation(p.rank(p.delta(np.log(p.volume), 2)),
                          p.rank((p.close - p.open) / p.open), 6)


def _a003(p: Panel) -> Any:
    return -p.correlation(p.rank(p.open), p.rank(p.volume), 10)


def _a004(p: Panel) -> Any:
    return -p.ts_rank(p.rank(p.low), 9)


def _a005(p: Panel) -> Any:
    vw = p.vwap
    return p.rank(p.open - p.sum(vw, 10) / 10.0) * -np.abs(p.rank(p.close - vw))


def _a006(p: Panel) -> Any:
    return -p.correlation(p.open, p.volume, 10)


def _a007(p: Panel) -> Any:
    d7 = p.delta(p.close, 7)
    return iff(lt(p.adv(20), p.volume), -p.ts_rank(np.abs(d7), 60) * np.sign(d7), -1.0)


def _a008(p: Panel) -> Any:
    x = p.sum(p.open, 5) * p.sum(p.returns, 5)
    return -p.rank(x - p.delay(x, 10))


def _ab009(p: Panel, d: int) -> Any:
    d1 = p.delta(p.close, 1)
    return iff(lt(0.0, p.ts_min(d1, d)), d1, iff(lt(p.ts_max(d1, d), 0.0), d1, -d1))


def _a009(p: Panel) -> Any:
    return _ab009(p, 5)


def _a010(p: Panel) -> Any:
    return p.rank(_ab009(p, 4))


def _a011(p: Panel) -> Any:
    g = p.vwap - p.close
    return (p.rank(p.ts_max(g, 3)) + p.rank(p.ts_min(g, 3))) * p.rank(p.delta(p.volume, 3))


def _a012(p: Panel) -> Any:
    return np.sign(p.delta(p.volume, 1)) * -p.delta(p.close, 1)


def _a013(p: Panel) -> Any:
    return -p.rank(p.covariance(p.rank(p.close), p.rank(p.volume), 5))


def _a014(p: Panel) -> Any:
    return -p.rank(p.delta(p.returns, 3)) * p.correlation(p.open, p.volume, 10)


def _a015(p: Panel) -> Any:
    return -p.sum(p.rank(p.correlation(p.rank(p.high), p.rank(p.volume), 3)), 3)


def _a016(p: Panel) -> Any:
    return -p.rank(p.covariance(p.rank(p.high), p.rank(p.volume), 5))


def _a017(p: Panel) -> Any:
    c = p.close
    return (-p.rank(p.ts_rank(c, 10)) * p.rank(p.delta(p.delta(c, 1), 1))
            * p.rank(p.ts_rank(p.volume / p.adv(20), 5)))


def _a018(p: Panel) -> Any:
    body = p.close - p.open
    return -p.rank(p.stddev(np.abs(body), 5) + body + p.correlation(p.close, p.open, 10))


def _a019(p: Panel) -> Any:
    c = p.close
    return (-np.sign((c - p.delay(c, 7)) + p.delta(c, 7))
            * (1.0 + p.rank(1.0 + p.sum(p.returns, 250))))


def _a020(p: Panel) -> Any:
    o = p.open
    return (-p.rank(o - p.delay(p.high, 1)) * p.rank(o - p.delay(p.close, 1))
            * p.rank(o - p.delay(p.low, 1)))


def _a021(p: Panel) -> Any:
    c = p.close
    m8, s8, m2 = p.sum(c, 8) / 8.0, p.stddev(c, 8), p.sum(c, 2) / 2.0
    vr = p.volume / p.adv(20)
    inner = iff(1.0 - lt(vr, 1.0), 1.0, -1.0)          # vr >= 1 -> long
    return iff(lt(m8 + s8, m2), -1.0, iff(lt(m2, m8 - s8), 1.0, inner))


def _a022(p: Panel) -> Any:
    return -(p.delta(p.correlation(p.high, p.volume, 5), 5) * p.rank(p.stddev(p.close, 20)))


def _a023(p: Panel) -> Any:
    h = p.high
    return iff(lt(p.sum(h, 20) / 20.0, h), -p.delta(h, 2), 0.0)


def _a024(p: Panel) -> Any:
    c = p.close
    q = p.delta(p.sum(c, 100) / 100.0, 100) / p.delay(c, 100)
    return iff(1.0 - lt(0.05, q), -(c - p.ts_min(c, 100)), -p.delta(c, 3))   # q <= 0.05


def _a025(p: Panel) -> Any:
    return p.rank(-p.returns * p.adv(20) * p.vwap * (p.high - p.close))


def _a026(p: Panel) -> Any:
    return -p.ts_max(p.correlation(p.ts_rank(p.volume, 5), p.ts_rank(p.high, 5), 5), 3)


def _a027(p: Panel) -> Any:
    m = p.sum(p.correlation(p.rank(p.volume), p.rank(p.vwap), 6), 2) / 2.0
    return iff(lt(0.5, p.rank(m)), -1.0, 1.0)


def _a028(p: Panel) -> Any:
    return p.scale(p.correlation(p.adv(20), p.low, 5) + (p.high + p.low) / 2.0 - p.close)


def _a029(p: Panel) -> Any:
    inner = p.rank(p.rank(-p.rank(p.delta(p.close - 1.0, 5))))
    core = p.rank(p.rank(p.scale(np.log(p.sum(p.ts_min(inner, 2), 1)))))
    return p.ts_min(p.product(core, 1), 5) + p.ts_rank(p.delay(-p.returns, 6), 5)


def _a030(p: Panel) -> Any:
    c = p.close
    s = (np.sign(c - p.delay(c, 1)) + np.sign(p.delay(c, 1) - p.delay(c, 2))
         + np.sign(p.delay(c, 2) - p.delay(c, 3)))
    v = p.volume
    return (1.0 - p.rank(s)) * p.sum(v, 5) / p.sum(v, 20)


def _a031(p: Panel) -> Any:
    c = p.close
    a = p.rank(p.rank(p.rank(p.decay_linear(-p.rank(p.rank(p.delta(c, 10))), 10))))
    return a + p.rank(-p.delta(c, 3)) + np.sign(p.scale(p.correlation(p.adv(20), p.low, 12)))


def _a032(p: Panel) -> Any:
    c = p.close
    return (p.scale(p.sum(c, 7) / 7.0 - c)
            + 20.0 * p.scale(p.correlation(p.vwap, p.delay(c, 5), 230)))


def _a033(p: Panel) -> Any:
    return p.rank(-(1.0 - p.open / p.close))


def _a034(p: Panel) -> Any:
    r = p.returns
    return p.rank((1.0 - p.rank(p.stddev(r, 2) / p.stddev(r, 5)))
                  + (1.0 - p.rank(p.delta(p.close, 1))))


def _a035(p: Panel) -> Any:
    return (p.ts_rank(p.volume, 32) * (1.0 - p.ts_rank(p.close + p.high - p.low, 16))
            * (1.0 - p.ts_rank(p.returns, 32)))


def _a036(p: Panel) -> Any:
    c, o = p.close, p.open
    return (2.21 * p.rank(p.correlation(c - o, p.delay(p.volume, 1), 15))
            + 0.7 * p.rank(o - c)
            + 0.73 * p.rank(p.ts_rank(p.delay(-p.returns, 6), 5))
            + p.rank(np.abs(p.correlation(p.vwap, p.adv(20), 6)))
            + 0.6 * p.rank((p.sum(c, 200) / 200.0 - o) * (c - o)))


def _a037(p: Panel) -> Any:
    oc = p.open - p.close
    return p.rank(p.correlation(p.delay(oc, 1), p.close, 200)) + p.rank(oc)


def _a038(p: Panel) -> Any:
    return -p.rank(p.ts_rank(p.close, 10)) * p.rank(p.close / p.open)


def _a039(p: Panel) -> Any:
    dl = p.decay_linear(p.volume / p.adv(20), 9)
    return (-p.rank(p.delta(p.close, 7) * (1.0 - p.rank(dl)))
            * (1.0 + p.rank(p.sum(p.returns, 250))))


def _a040(p: Panel) -> Any:
    return -p.rank(p.stddev(p.high, 10)) * p.correlation(p.high, p.volume, 10)


def _a041(p: Panel) -> Any:
    return np.sqrt(p.high * p.low) - p.vwap


def _a042(p: Panel) -> Any:
    vw = p.vwap
    return p.rank(vw - p.close) / p.rank(vw + p.close)


def _a043(p: Panel) -> Any:
    return p.ts_rank(p.volume / p.adv(20), 20) * p.ts_rank(-p.delta(p.close, 7), 8)


def _a044(p: Panel) -> Any:
    return -p.correlation(p.high, p.rank(p.volume), 5)


def _a045(p: Panel) -> Any:
    c = p.close
    return -(p.rank(p.sum(p.delay(c, 5), 20) / 20.0) * p.correlation(c, p.volume, 2)
             * p.rank(p.correlation(p.sum(c, 5), p.sum(c, 20), 2)))


def _a046(p: Panel) -> Any:
    t = _t46(p)
    c = p.close
    return iff(lt(0.25, t), -1.0, iff(lt(t, 0.0), 1.0, -(c - p.delay(c, 1))))


def _a047(p: Panel) -> Any:
    c, h, vw = p.close, p.high, p.vwap
    return ((p.rank(1.0 / c) * p.volume / p.adv(20))
            * (h * p.rank(h - c) / (p.sum(h, 5) / 5.0)) - p.rank(vw - p.delay(vw, 5)))


def _a048(p: Panel) -> Any:
    c = p.close
    d1 = p.delta(c, 1)
    num = p.indneutralize(p.correlation(d1, p.delta(p.delay(c, 1), 1), 250) * d1 / c)
    return num / p.sum((d1 / p.delay(c, 1)) ** 2, 250)


def _a049(p: Panel) -> Any:
    c = p.close
    return iff(lt(_t46(p), -0.1), 1.0, -(c - p.delay(c, 1)))


def _a050(p: Panel) -> Any:
    return -p.ts_max(p.rank(p.correlation(p.rank(p.volume), p.rank(p.vwap), 5)), 5)


def _a051(p: Panel) -> Any:
    c = p.close
    return iff(lt(_t46(p), -0.05), 1.0, -(c - p.delay(c, 1)))


def _a052(p: Panel) -> Any:
    r = p.returns
    m5 = p.ts_min(p.low, 5)
    return ((-m5 + p.delay(m5, 5)) * p.rank((p.sum(r, 240) - p.sum(r, 20)) / 220.0)
            * p.ts_rank(p.volume, 5))


def _a053(p: Panel) -> Any:
    c, h, lo = p.close, p.high, p.low
    return -p.delta(((c - lo) - (h - c)) / (c - lo), 9)


def _a054(p: Panel) -> Any:
    c, lo = p.close, p.low
    return -((lo - c) * p.open ** 5) / ((lo - p.high) * c ** 5)


def _a055(p: Panel) -> Any:
    lo12, hi12 = p.ts_min(p.low, 12), p.ts_max(p.high, 12)
    return -p.correlation(p.rank((p.close - lo12) / (hi12 - lo12)), p.rank(p.volume), 6)


def _a056(p: Panel) -> Any:
    r = p.returns
    return -(p.rank(p.sum(r, 10) / p.sum(p.sum(r, 2), 3)) * p.rank(r * p.cap))


def _a057(p: Panel) -> Any:
    return -((p.close - p.vwap) / p.decay_linear(p.rank(p.ts_argmax(p.close, 30)), 2))


def _a058(p: Panel) -> Any:
    return -p.ts_rank(p.decay_linear(p.correlation(p.indneutralize(p.vwap), p.volume, 3.92795),
                                     7.89291), 5.50322)


def _a059(p: Panel) -> Any:
    return -p.ts_rank(p.decay_linear(p.correlation(p.indneutralize(p.vwap), p.volume, 4.25197),
                                     16.2289), 8.19648)


def _a060(p: Panel) -> Any:
    c, h, lo = p.close, p.high, p.low
    a = p.scale(p.rank(((c - lo) - (h - c)) / (h - lo) * p.volume))
    return -(2.0 * a - p.scale(p.rank(p.ts_argmax(c, 10))))


def _a061(p: Panel) -> Any:
    vw = p.vwap
    return lt(p.rank(vw - p.ts_min(vw, 16.1219)), p.rank(p.correlation(vw, p.adv(180), 17.9282)))


def _a062(p: Panel) -> Any:
    o, h, lo = p.open, p.high, p.low
    a = p.rank(p.correlation(p.vwap, p.sum(p.adv(20), 22.4101), 9.91009))
    b = p.rank(lt(p.rank(o) + p.rank(o), p.rank((h + lo) / 2.0) + p.rank(h)))
    return -lt(a, b)


def _a063(p: Panel) -> Any:
    a = p.rank(p.decay_linear(p.delta(p.indneutralize(p.close), 2.25164), 8.22237))
    b = p.rank(p.decay_linear(p.correlation(_mix(p.vwap, p.open, 0.318108),
                                            p.sum(p.adv(180), 37.2467), 13.557), 12.2883))
    return -(a - b)


def _a064(p: Panel) -> Any:
    w = 0.178404
    a = p.rank(p.correlation(p.sum(_mix(p.open, p.low, w), 12.7054),
                             p.sum(p.adv(120), 12.7054), 16.6208))
    b = p.rank(p.delta(_mix((p.high + p.low) / 2.0, p.vwap, w), 3.69741))
    return -lt(a, b)


def _a065(p: Panel) -> Any:
    a = p.rank(p.correlation(_mix(p.open, p.vwap, 0.00817205), p.sum(p.adv(60), 8.6911),
                             6.40374))
    return -lt(a, p.rank(p.open - p.ts_min(p.open, 13.635)))


def _a066(p: Panel) -> Any:
    vw = p.vwap
    a = p.rank(p.decay_linear(p.delta(vw, 3.51013), 7.23052))
    b = p.ts_rank(p.decay_linear((p.low - vw) / (p.open - (p.high + p.low) / 2.0), 11.4157),
                  6.72611)
    return -(a + b)


def _a067(p: Panel) -> Any:
    a = p.rank(p.high - p.ts_min(p.high, 2.14593))
    b = p.rank(p.correlation(p.indneutralize(p.vwap), p.indneutralize(p.adv(20)), 6.02936))
    return -np.power(a, b)


def _a068(p: Panel) -> Any:
    a = p.ts_rank(p.correlation(p.rank(p.high), p.rank(p.adv(15)), 8.91644), 13.9333)
    b = p.rank(p.delta(_mix(p.close, p.low, 0.518371), 1.06157))
    return -lt(a, b)


def _a069(p: Panel) -> Any:
    a = p.rank(p.ts_max(p.delta(p.indneutralize(p.vwap), 2.72412), 4.79344))
    b = p.ts_rank(p.correlation(_mix(p.close, p.vwap, 0.490655), p.adv(20), 4.92416), 9.0615)
    return -np.power(a, b)


def _a070(p: Panel) -> Any:
    a = p.rank(p.delta(p.vwap, 1.29456))
    b = p.ts_rank(p.correlation(p.indneutralize(p.close), p.adv(50), 17.8256), 17.9171)
    return -np.power(a, b)


def _a071(p: Panel) -> Any:
    a = p.ts_rank(p.decay_linear(p.correlation(p.ts_rank(p.close, 3.43976),
                                               p.ts_rank(p.adv(180), 12.0647), 18.0175),
                                 4.20501), 15.6948)
    b = p.ts_rank(p.decay_linear(p.rank((p.low + p.open) - 2.0 * p.vwap) ** 2, 16.4662),
                  4.4388)
    return emax(a, b)


def _a072(p: Panel) -> Any:
    a = p.rank(p.decay_linear(p.correlation((p.high + p.low) / 2.0, p.adv(40), 8.93345),
                              10.1519))
    b = p.rank(p.decay_linear(p.correlation(p.ts_rank(p.vwap, 3.72469),
                                            p.ts_rank(p.volume, 18.5188), 6.86671), 2.95011))
    return a / b


def _a073(p: Panel) -> Any:
    blend = _mix(p.open, p.low, 0.147155)
    a = p.rank(p.decay_linear(p.delta(p.vwap, 4.72775), 2.91864))
    b = p.ts_rank(p.decay_linear(-(p.delta(blend, 2.03608) / blend), 3.33829), 16.7411)
    return -emax(a, b)


def _a074(p: Panel) -> Any:
    a = p.rank(p.correlation(p.close, p.sum(p.adv(30), 37.4843), 15.1365))
    b = p.rank(p.correlation(p.rank(_mix(p.high, p.vwap, 0.0261661)), p.rank(p.volume),
                             11.4791))
    return -lt(a, b)


def _a075(p: Panel) -> Any:
    return lt(p.rank(p.correlation(p.vwap, p.volume, 4.24304)),
              p.rank(p.correlation(p.rank(p.low), p.rank(p.adv(50)), 12.4413)))


def _a076(p: Panel) -> Any:
    a = p.rank(p.decay_linear(p.delta(p.vwap, 1.24383), 11.8259))
    b = p.ts_rank(p.decay_linear(p.ts_rank(p.correlation(p.indneutralize(p.low), p.adv(81),
                                                         8.14941), 19.569), 17.1543), 19.383)
    return -emax(a, b)


def _a077(p: Panel) -> Any:
    mid = (p.high + p.low) / 2.0
    a = p.rank(p.decay_linear((mid + p.high) - (p.vwap + p.high), 20.0451))
    b = p.rank(p.decay_linear(p.correlation(mid, p.adv(40), 3.1614), 5.64125))
    return emin(a, b)


def _a078(p: Panel) -> Any:
    a = p.rank(p.correlation(p.sum(_mix(p.low, p.vwap, 0.352233), 19.7428),
                             p.sum(p.adv(40), 19.7428), 6.83313))
    b = p.rank(p.correlation(p.rank(p.vwap), p.rank(p.volume), 5.77492))
    return np.power(a, b)


def _a079(p: Panel) -> Any:
    a = p.rank(p.delta(p.indneutralize(_mix(p.close, p.open, 0.60733)), 1.23438))
    b = p.rank(p.correlation(p.ts_rank(p.vwap, 3.60973), p.ts_rank(p.adv(150), 9.18637),
                             14.6644))
    return lt(a, b)


def _a080(p: Panel) -> Any:
    a = p.rank(np.sign(p.delta(p.indneutralize(_mix(p.open, p.high, 0.868128)), 4.04545)))
    b = p.ts_rank(p.correlation(p.high, p.adv(10), 5.11456), 5.53756)
    return -np.power(a, b)


def _a081(p: Panel) -> Any:
    inner = p.rank(p.rank(p.correlation(p.vwap, p.sum(p.adv(10), 49.6054), 8.47743)) ** 4)
    a = p.rank(np.log(p.product(inner, 14.9655)))
    b = p.rank(p.correlation(p.rank(p.vwap), p.rank(p.volume), 5.07914))
    return -lt(a, b)


def _a082(p: Panel) -> Any:
    a = p.rank(p.decay_linear(p.delta(p.open, 1.46063), 14.8717))
    b = p.ts_rank(p.decay_linear(p.correlation(p.indneutralize(p.volume), p.open, 17.4842),
                                 6.92131), 13.4283)
    return -emin(a, b)


def _a083(p: Panel) -> Any:
    rng = (p.high - p.low) / (p.sum(p.close, 5) / 5.0)
    return (p.rank(p.delay(rng, 2)) * p.rank(p.rank(p.volume))) / (rng / (p.vwap - p.close))


def _a084(p: Panel) -> Any:
    vw = p.vwap
    return signedpower(p.ts_rank(vw - p.ts_max(vw, 15.3217), 20.7127),
                       p.delta(p.close, 4.96796))


def _a085(p: Panel) -> Any:
    a = p.rank(p.correlation(_mix(p.high, p.close, 0.876703), p.adv(30), 9.61331))
    b = p.rank(p.correlation(p.ts_rank((p.high + p.low) / 2.0, 3.70596),
                             p.ts_rank(p.volume, 10.1595), 7.11408))
    return np.power(a, b)


def _a086(p: Panel) -> Any:
    a = p.ts_rank(p.correlation(p.close, p.sum(p.adv(20), 14.7444), 6.00049), 20.4195)
    b = p.rank((p.open + p.close) - (p.vwap + p.open))
    return -lt(a, b)


def _a087(p: Panel) -> Any:
    a = p.rank(p.decay_linear(p.delta(_mix(p.close, p.vwap, 0.369701), 1.91233), 2.65461))
    b = p.ts_rank(p.decay_linear(np.abs(p.correlation(p.indneutralize(p.adv(81)), p.close,
                                                      13.4132)), 4.89768), 14.4535)
    return -emax(a, b)


def _a088(p: Panel) -> Any:
    a = p.rank(p.decay_linear((p.rank(p.open) + p.rank(p.low))
                              - (p.rank(p.high) + p.rank(p.close)), 8.06882))
    b = p.ts_rank(p.decay_linear(p.correlation(p.ts_rank(p.close, 8.44728),
                                               p.ts_rank(p.adv(60), 20.6966), 8.01266),
                                 6.65053), 2.61957)
    return emin(a, b)


def _a089(p: Panel) -> Any:
    a = p.ts_rank(p.decay_linear(p.correlation(p.low, p.adv(10), 6.94279), 5.51607), 3.79744)
    b = p.ts_rank(p.decay_linear(p.delta(p.indneutralize(p.vwap), 3.48158), 10.1466), 15.3012)
    return a - b


def _a090(p: Panel) -> Any:
    a = p.rank(p.close - p.ts_max(p.close, 4.66719))
    b = p.ts_rank(p.correlation(p.indneutralize(p.adv(40)), p.low, 5.38375), 3.21856)
    return -np.power(a, b)


def _a091(p: Panel) -> Any:
    a = p.ts_rank(p.decay_linear(p.decay_linear(p.correlation(p.indneutralize(p.close),
                                                              p.volume, 9.74928), 16.398),
                                 3.83219), 4.8667)
    b = p.rank(p.decay_linear(p.correlation(p.vwap, p.adv(30), 4.01303), 2.6809))
    return -(a - b)


def _a092(p: Panel) -> Any:
    cond = lt((p.high + p.low) / 2.0 + p.close, p.low + p.open)
    a = p.ts_rank(p.decay_linear(cond, 14.7221), 18.8683)
    b = p.ts_rank(p.decay_linear(p.correlation(p.rank(p.low), p.rank(p.adv(30)), 7.58555),
                                 6.94024), 6.80584)
    return emin(a, b)


def _a093(p: Panel) -> Any:
    a = p.ts_rank(p.decay_linear(p.correlation(p.indneutralize(p.vwap), p.adv(81), 17.4193),
                                 19.848), 7.54455)
    b = p.rank(p.decay_linear(p.delta(_mix(p.close, p.vwap, 0.524434), 2.77377), 16.2664))
    return a / b


def _a094(p: Panel) -> Any:
    vw = p.vwap
    a = p.rank(vw - p.ts_min(vw, 11.5783))
    b = p.ts_rank(p.correlation(p.ts_rank(vw, 19.6462), p.ts_rank(p.adv(60), 4.02992),
                                18.0926), 2.70756)
    return -np.power(a, b)


def _a095(p: Panel) -> Any:
    a = p.rank(p.open - p.ts_min(p.open, 12.4105))
    inner = p.rank(p.correlation(p.sum((p.high + p.low) / 2.0, 19.1351),
                                 p.sum(p.adv(40), 19.1351), 12.8742))
    return lt(a, p.ts_rank(inner ** 5, 11.7584))


def _a096(p: Panel) -> Any:
    a = p.ts_rank(p.decay_linear(p.correlation(p.rank(p.vwap), p.rank(p.volume), 3.83878),
                                 4.16783), 8.38151)
    corr = p.correlation(p.ts_rank(p.close, 7.45404), p.ts_rank(p.adv(60), 4.13242), 3.65459)
    b = p.ts_rank(p.decay_linear(p.ts_argmax(corr, 12.6556), 14.0365), 13.4143)
    return -emax(a, b)


def _a097(p: Panel) -> Any:
    a = p.rank(p.decay_linear(p.delta(p.indneutralize(_mix(p.low, p.vwap, 0.721001)), 3.3705),
                              20.4523))
    corr = p.correlation(p.ts_rank(p.low, 7.87871), p.ts_rank(p.adv(60), 17.255), 4.97547)
    b = p.ts_rank(p.decay_linear(p.ts_rank(corr, 18.5925), 15.7152), 6.71659)
    return -(a - b)


def _a098(p: Panel) -> Any:
    a = p.rank(p.decay_linear(p.correlation(p.vwap, p.sum(p.adv(5), 26.4719), 4.58418),
                              7.18088))
    corr = p.correlation(p.rank(p.open), p.rank(p.adv(15)), 20.8187)
    b = p.rank(p.decay_linear(p.ts_rank(p.ts_argmin(corr, 8.62571), 6.95668), 8.07206))
    return a - b


def _a099(p: Panel) -> Any:
    a = p.rank(p.correlation(p.sum((p.high + p.low) / 2.0, 19.8975),
                             p.sum(p.adv(60), 19.8975), 8.8136))
    b = p.rank(p.correlation(p.low, p.volume, 6.28259))
    return -lt(a, b)


def _a100(p: Panel) -> Any:
    c, h, lo, v = p.close, p.high, p.low, p.volume
    clv = p.rank(((c - lo) - (h - c)) / (h - lo) * v)
    a = 1.5 * p.scale(p.indneutralize(p.indneutralize(clv)))
    b = p.scale(p.indneutralize(p.correlation(c, p.rank(p.adv(20)), 5)
                                - p.rank(p.ts_argmin(c, 30))))
    return -((a - b) * (v / p.adv(20)))


def _a101(p: Panel) -> Any:
    return (p.close - p.open) / ((p.high - p.low) + 0.001)


ALPHAS: dict[str, Callable[[Panel], Any]] = {
    f"alpha{int(name[2:]):03d}": fn for name, fn in sorted(globals().items())
    if name.startswith("_a") and name[2:].isdigit() and callable(fn)
}


# ============================================================================ evaluation
def evaluate(alpha_id: str, panel: Panel) -> tuple[np.ndarray | None, str]:
    """(T x N signal, "") or (None, why). Non-finite values become NaN; nothing is filled."""
    fn = ALPHAS[alpha_id]
    try:
        with np.errstate(all="ignore"):
            out = np.asarray(fn(panel), dtype=float)
    except Unmeasured as exc:
        return None, f"reads {exc.args[0]}: {NO_PROXY.get(str(exc.args[0]), 'no proxy')}"
    out = np.broadcast_to(out, panel.shape).copy()
    out[~np.isfinite(out) | ~panel.present] = np.nan
    return out, ""


def planted_panel(n: int = 80, n_sym: int = 4, seed: int = 0,
                  groups: Sequence[str] | None = None) -> Panel:
    """Planted random-walk bars -- for the census and the tests. Never market data."""
    rng = np.random.default_rng(seed)
    c = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.01, (n, n_sym)), axis=0))
    o = np.vstack([c[:1], c[:-1]]) * np.exp(rng.normal(0, 0.002, (n, n_sym)))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.003, (n, n_sym))))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.003, (n, n_sym))))
    v = rng.integers(50, 500, (n, n_sym)).astype(float)
    g = tuple(groups) if groups is not None else tuple("ab"[j % 2] for j in range(n_sym))
    return Panel(tuple(f"S{j}" for j in range(n_sym)), tuple(str(i) for i in range(n)),
                 o, h, lo, c, v, np.ones((n, n_sym), dtype=bool), g)


def census() -> dict[str, dict[str, Any]]:
    """Every alpha's MEASURED status: run it on an instrumented planted panel and record which
    fields it read. EXACT / PROXIED (with the proxies) / UNMEASURED (with the field), plus the
    windows it used -- whose median is the horizon a donated hypothesis is parameterised at."""
    out: dict[str, dict[str, Any]] = {}
    for aid in ALPHAS:
        p = planted_panel(n=60, n_sym=4, seed=1)
        _sig, why = evaluate(aid, p)
        touched = sorted(p.touched)
        if why:
            status = "UNMEASURED"
        elif touched:
            status = "PROXIED"
        else:
            status = "EXACT"
        wins = sorted(p.windows)
        out[aid] = {"status": status, "proxies": [t for t in touched if t in PROXIES],
                    "why": why, "windows": wins,
                    "horizon_bars": int(wins[len(wins) // 2]) if wins else 1}
    return out


def census_counts(rows: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, int]:
    rows = census() if rows is None else rows
    return {s: sum(1 for r in rows.values() if r["status"] == s) for s in STATUSES}


# ============================================================================ measurement
def forward_returns(panel: Panel, h: int) -> np.ndarray:
    """Each symbol's return from this bar's close to the close h of ITS OWN bars later. This is
    the LABEL, read only to measure a signal known at this bar -- never an input to one."""
    def fwd(s: np.ndarray) -> np.ndarray:
        out = np.full(s.shape[0], np.nan)
        if s.shape[0] > h:
            out[:-h] = s[h:] / s[:-h] - 1.0
        return out
    with np.errstate(all="ignore"):
        return panel.ts(panel.c, fwd)


def rank_ic(a: np.ndarray, b: np.ndarray, min_n: int = 30) -> float:
    """Spearman correlation of two aligned 1-D series (average ties), non-finite rows dropped.
    A MEASUREMENT of association, never a verdict."""
    m = np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < min_n:
        return float("nan")
    x, y = avg_rank(a[m]), avg_rank(b[m])
    sx, sy = float(np.std(x)), float(np.std(y))
    if sx <= 0.0 or sy <= 0.0:
        return float("nan")
    return float(np.mean((x - x.mean()) * (y - y.mean())) / (sx * sy))


def xs_ic(sig: np.ndarray, fwd: np.ndarray, min_members: int = 3) -> tuple[float, int]:
    """Mean over bars of the cross-sectional rank correlation between signal and forward return,
    on bars where at least `min_members` symbols carry both. (mean, bars used)."""
    ok = np.isfinite(sig) & np.isfinite(fwd)
    rows = ok.sum(axis=1) >= min_members
    if not rows.any():
        return float("nan"), 0
    rx, _ = row_ranks(np.where(ok, sig, np.nan)[rows])
    ry, _ = row_ranks(np.where(ok, fwd, np.nan)[rows])
    m = np.isfinite(rx)
    n = m.sum(axis=1)
    mx = np.where(m, rx, 0.0).sum(axis=1) / n
    my = np.where(m, ry, 0.0).sum(axis=1) / n
    dx = np.where(m, rx - mx[:, None], 0.0)
    dy = np.where(m, ry - my[:, None], 0.0)
    sxy, sxx, syy = (dx * dy).sum(axis=1), (dx * dx).sum(axis=1), (dy * dy).sum(axis=1)
    good = (sxx > 0) & (syy > 0)
    if not good.any():
        return float("nan"), 0
    vals = sxy[good] / np.sqrt(sxx[good] * syy[good])
    return float(vals.mean()), int(good.sum())


def panel_from_frames(frames: Sequence[Any], groups: Mapping[str, str]) -> Panel:
    """Union-of-times panel from BarFrame-shaped objects (symbol, time, open, high, low, close,
    volume). A symbol absent at a time is ABSENT (presence False), never zero-filled."""
    times = sorted({t for f in frames for t in f.time})
    pos = {t: i for i, t in enumerate(times)}
    n, k = len(times), len(frames)
    cols = {name: np.full((n, k), np.nan) for name in ("o", "h", "lo", "c", "v")}
    present = np.zeros((n, k), dtype=bool)
    for j, f in enumerate(frames):
        rows = np.fromiter((pos[t] for t in f.time), dtype=int, count=len(f.time))
        for name, src in (("o", f.open), ("h", f.high), ("lo", f.low), ("c", f.close),
                          ("v", f.volume)):
            cols[name][rows, j] = np.asarray(src, dtype=float)
        present[rows, j] = True
    return Panel(tuple(f.symbol for f in frames), tuple(times), cols["o"], cols["h"],
                 cols["lo"], cols["c"], cols["v"], present,
                 tuple(str(groups.get(f.symbol, "")) for f in frames))


# ============================================================================ the registry
def registry_classes(symbols: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Each symbol's lane and peer class from MetaTrader's registry, through
    `desks/mt5/research/universe_policy.py` -- the one place the two-lane order is enforced.

      hypothesis  may a STATISTICAL family mint a hypothesis on it (`may_hypothesise(sym)`)
      class_book  may a CROSS-SECTIONAL class-book family (`may_hypothesise(sym, <xs family>)`):
                  true for the hypothesis lane AND for share CFDs (principal, 2026-09-30)
      group       the indneutralize group: `peer_class`, else the registry's `asset_class`
      orientation +1 / -1: how a USD pair reads as the non-USD currency in dollars

    An unreachable registry admits NOTHING (absence is not a permission) and says why."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for p in (str(root / "desks" / "mt5"), str(root)):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from research import universe_policy as up  # type: ignore[import-not-found]
        xs_family = sorted(up.CROSS_SECTIONAL_FAMILIES)[0]
    except Exception as exc:
        why = f"universe_policy unreachable: {type(exc).__name__}: {exc}"[:200]
        return {s: {"hypothesis": False, "class_book": False, "group": "", "orientation": 1,
                    "why": why} for s in symbols}
    out: dict[str, dict[str, Any]] = {}
    for s in symbols:
        try:
            group = str(up.peer_class(s) or up.asset_class_of(s) or "")
            out[s] = {"hypothesis": bool(up.may_hypothesise(s)),
                      "class_book": bool(up.may_hypothesise(s, xs_family)),
                      "peer_class": up.peer_class(s), "group": group,
                      "orientation": int(up.usd_orientation(s)) if up.peer_class(s) == "fx_usd"
                      else 1, "why": ""}
        except Exception as exc:
            out[s] = {"hypothesis": False, "class_book": False, "group": "", "orientation": 1,
                      "why": f"{type(exc).__name__}: {exc}"[:160]}
    return out


def min_class_members() -> int:
    """`universe_policy.MIN_CLASS_MEMBERS` (the desk's floor for a class rank), or 5."""
    try:
        from research import universe_policy as up
        return int(up.MIN_CLASS_MEMBERS)
    except Exception:
        return 5
