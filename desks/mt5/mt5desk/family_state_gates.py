"""STATE-GATED FAMILIES -- a price-only base family's own signals, kept only in a market STATE.

The `family_alt_series.family_alt_conditioned` pattern, with the gate read off PRICES rather than
an alt series: run `base_family` at `base_params`, then keep only the signals whose state at
signal time passes the gate. The un-gated base cell is the control arm and already sits in the
docket; each cell here asks one question: does the base's entry pay in this state?

  sync_gated      (GAP_MAP row 87, the SYNCHRONISATION style). The Kuramoto order parameter of
      a fixed panel -- the 28 FX crosses of EUR GBP AUD NZD USD CAD CHF JPY present in the bar
      store, plus XAUUSD -- read at each base signal time t:

          phi_j = phase at the LAST sample of the analytic signal of symbol j's detrended log
                  closes over its last `window` H1 bars stamped <= t (FFT Hilbert, numpy only)
          R(t)  = | mean_j exp(i * phi_j) |

      R near 1 is a panel moving in lock-step (one common driver); R near 1/sqrt(N) is a panel
      whose members cycle independently. The phase at the window's END is the causal choice and
      carries the Hilbert transform's endpoint bias, which depends on each member's own spectrum,
      so R's level is not comparable across panels or eras -- which is why the gate reads R's
      RANK, never its level (below).

      THE GATE IS A TAIL OF R's OWN HISTORY (audit of #395). With ~22 members R's median sits near
      0.30, so a fixed 0.5 cut kept 88% of a reversion base's signals -- a near-copy of its
      ungated control, not an independent bet. Each signal's R is ranked against the R read at
      the base's EARLIER signals only (at least `min_history` of them; before that, no signal is
      kept), and the signal is kept in the `tail` of that distribution.

      THE GATE DIRECTION IS FIXED BY THE BASE'S MECHANISM (research/alpha_genome.MECHANISM_CLASS),
      so no regime trial is spent choosing it: a trend or breakout base needs a common driver to
      carry the move and is kept in the TOP tail of R; a reversion base needs idiosyncratic,
      self-correcting noise and is kept in the BOTTOM tail; any other class returns [].

  entropy_gated   (row 88). Bandt-Pompe permutation entropy of the symbol's own closes: ordinal
      patterns of order m (delay 1), normalised by log m!, over a trailing `window` of patterns,
      computed causally with rolling counts. A base signal is kept where that entropy's trailing
      z-score (`z_window` bars, data <= t only) is <= -threshold -- a low-entropy, PREDICTABLE
      window. The direction is fixed at "low", so the preprocessing choice is ONE trial per base,
      not a regime sweep.

  fisher_rao_gated (row 90, DISTRIBUTION VELOCITY). From the symbol's own H1 log returns, a
      fixed-nu (default 5) Student-t location-scale fit by EM to the trailing `window` (default
      120) returns ending at the signal bar, and to the `window` before it; the state is the
      Fisher-Rao distance between the two fits (closed form, derived in `fisher_rao_t`). A
      trend/breakout base is kept in the BOTTOM tail (slow drift, a stable regime); a reversion
      base in the TOP tail (fast drift). It reads only the symbol's own bars.

  absorption_gated (row 91, Kritzman, Li, Page & Rigobon 2011, "Principal components as a
      measure of systemic risk"). The panel is every hypothesis-lane symbol with an H1 file,
      loaded like sync_gated's with the same MAX_STALE_HOURS exclusion. AR at a stamp is the
      variance share of the top k = ceil(N/5) eigenvectors of the correlation of the last 360
      aligned H1 returns (15 trading days) of members with full windows (>= 20 of them, else the
      signal is dropped). The state is the standardised shift (AR_1d - AR_15d) / sd(AR over the
      15d window), computed only at signal times and memoised per bar. A trend/breakout base is
      kept in the TOP tail (a fragile, coupled market), a reversion base in the BOTTOM tail.
      IT GATES ENTRIES AND NOTHING ELSE: scaling heat or size by AR would be a capital modifier,
      which needs its own Rule-1 forward E[log W] proof and is out of scope here; no heat,
      sizing, allocator or money-path code reads it.

  Both new gates use the sync gate's rule (`keep_in_tail`): the state at a signal bar is ranked
  against the state at the base's STRICTLY EARLIER signal bars (tail 1/3, at least `min_history`
  30 of them, a bar's reading joining the history only once a later bar arrives), never against
  a fixed level, with the direction fixed by the base's MECHANISM_CLASS.

R and the entropy are computed only where a base signal exists for sync (one panel read per
signal time) and over the symbol's own closes for entropy. Every wrapper returns [] -- never an
ungated fallback -- when the base is unwrappable, the panel is short or the state unmeasurable.
"""
from __future__ import annotations

import bisect
import contextlib
import hashlib
import math
import sys
from collections.abc import Callable, Sequence
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk import families_cross_sectional as xs
from mt5desk.families import Signal, _h1, get_family_func

BASE = Path(__file__).resolve().parent.parent

#: The eight currencies whose 28 crosses form the synchronisation panel, plus gold.
SYNC_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY")
SYNC_EXTRA: tuple[str, ...] = ("XAUUSD",)

#: A panel member whose last bar at or before t is older than this is absent from R at t, not
#: stale inside it (covers a weekend plus a holiday on the H1 clock).
MAX_STALE_HOURS = 96

#: Mechanism classes each gate admits; anything else is refused (returns []).
SYNC_HIGH: frozenset[str] = frozenset({"trend", "breakout"})
SYNC_LOW: frozenset[str] = frozenset({"reversion"})

#: Orders the permutation entropy accepts: below 2 there is no pattern, above 6 the m! patterns
#: outrun any H1 window the desk has.
MIN_ORDER, MAX_ORDER = 2, 6


# ----------------------------------------------------------------------------- base family ---
def _unwrappable() -> frozenset[str]:
    from mt5desk.family_alt_series import _UNWRAPPABLE
    return _UNWRAPPABLE


def mechanism_class(name: str) -> str:
    """The base family's declared mechanism class, or "UNCLASSIFIED"."""
    try:
        from research import alpha_genome as ag
    except ImportError:                                            # pragma: no cover - path
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        try:
            from research import alpha_genome as ag
        except Exception:
            return "UNCLASSIFIED"
    except Exception:                                              # pragma: no cover - import
        return "UNCLASSIFIED"
    return str(ag.MECHANISM_CLASS.get(name, "UNCLASSIFIED"))


def base_signals(df: pd.DataFrame, base_family: str, base_params: dict[str, Any] | None
                 ) -> tuple[pd.DataFrame, list[Signal]]:
    """(the bar frame, `base_family`'s own signals on it), or an empty list when unwrappable."""
    d = _h1(df)
    if not base_family or base_family in _unwrappable():
        return d, []
    fn = get_family_func(base_family)
    if fn is None:
        return d, []
    params = dict(base_params or {})
    for k in ("timeframe", "session"):
        params.pop(k, None)
    try:
        raw = fn(d, **params)
    except Exception:
        return d, []
    return d, [s for s in (raw or []) if isinstance(s, Signal)]


def _ns(t: Any) -> int | None:
    try:
        ts = pd.Timestamp(t)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return int(ts.as_unit("ns").value)


def keep_in_tail(sigs: Sequence[Signal], state_at: Callable[[int, Signal], float | None], *,
                 keep_top: bool, tail: float = 1.0 / 3.0, min_history: int = 30
                 ) -> list[Signal]:
    """The base signals whose state ranks in the TOP (`keep_top`) or BOTTOM `tail` of the state
    read at the base's STRICTLY EARLIER signal bars -- the gate every wrapper here shares.

    `state_at(bar_ns, signal)` is read once per signal bar (memoised) and may return None (the
    signal is dropped and its bar adds nothing to the history). A bar's state joins the history
    only once a LATER bar arrives, so two signals on one bar never rank against each other, and
    nothing is kept until `min_history` earlier readings exist. The rank is the share of the
    history strictly below the reading: kept when >= 1 - tail (top) or <= tail (bottom).
    """
    q = float(tail)
    if not 0.0 < q < 1.0:
        return []
    need = max(1, int(min_history))
    keep: list[Signal] = []
    memo: dict[int, float | None] = {}
    timed = sorted(((k, s) for s in sigs if (k := _ns(s.time)) is not None),
                   key=lambda ks: ks[0])
    history: list[float] = []          # sorted readings at every STRICTLY EARLIER signal bar
    pending: tuple[int, float] | None = None
    for key, s in timed:
        if pending is not None and pending[0] != key:
            bisect.insort(history, pending[1])  # a bar's state joins once its bar has passed
            pending = None
        if key not in memo:
            memo[key] = state_at(key, s)
        v = memo[key]
        if v is None or not math.isfinite(v):
            continue
        pending = (key, v)
        if len(history) >= need:
            below = bisect.bisect_left(history, v) / len(history)
            if (below >= 1.0 - q) if keep_top else (below <= q):
                keep.append(s)
    return keep


# ------------------------------------------------------------------------- synchronisation ---
def panel_symbols(root: Path | None = None) -> list[str]:
    """The 28 crosses of SYNC_CURRENCIES present in the bar store (either quote order), + gold."""
    d = Path(root) if root is not None else xs.UNIVERSE_DIR
    out: list[str] = []
    for a, b in combinations(SYNC_CURRENCIES, 2):
        for sym in (f"{a}{b}", f"{b}{a}"):
            if (d / f"{sym}_H1.parquet").exists():
                out.append(sym)
                break
    out += [s for s in SYNC_EXTRA if (d / f"{s}_H1.parquet").exists()]
    return out


def load_panel() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """{symbol: (int64 ns stamps, closes)} for the panel, through the cross-sectional cache."""
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for sym in panel_symbols():
        series = xs._load_series(sym)
        if series is not None:
            out[sym] = series
    return out


def end_phases(windows: np.ndarray) -> np.ndarray:
    """Phase at the LAST sample of each row's analytic signal (rows: log prices, one window each).

    Each row has its least-squares line removed, then the FFT Hilbert transform (zero the negative
    frequencies, double the positive ones) gives the analytic signal; its angle at the final index
    is the instantaneous phase at the window's end -- causal, endpoint bias accepted.
    """
    x = np.asarray(windows, dtype="float64")
    if x.ndim != 2 or x.shape[1] < 4:
        return np.full(x.shape[0] if x.ndim == 2 else 0, np.nan)
    n = x.shape[1]
    tt = np.arange(n, dtype="float64")
    tt -= tt.mean()
    mu = x.mean(axis=1, keepdims=True)
    slope = ((x - mu) @ tt / float(tt @ tt))[:, None]
    resid = x - mu - slope * tt[None, :]
    h = np.zeros(n)
    h[0] = 1.0
    if n % 2 == 0:
        h[n // 2] = 1.0
        h[1:n // 2] = 2.0
    else:
        h[1:(n + 1) // 2] = 2.0
    analytic = np.fft.ifft(np.fft.fft(resid, axis=1) * h[None, :], axis=1)
    return np.asarray(np.angle(analytic[:, -1]), dtype="float64")


def kuramoto_r(panel: dict[str, tuple[np.ndarray, np.ndarray]], t: Any, *, window: int = 128,
               min_symbols: int = 12) -> float | None:
    """R = |mean_j exp(i phi_j)| over panel members with a full `window` of closes <= t, or None
    when fewer than `min_symbols` qualify."""
    at = _ns(t)
    w = int(window)
    if at is None or w < 8:
        return None
    stale = int(MAX_STALE_HOURS * 3600 * 1e9)
    rows: list[np.ndarray] = []
    for stamps, closes in panel.values():
        j = int(np.searchsorted(stamps, at, side="right"))
        if j < w or at - int(stamps[j - 1]) > stale:
            continue
        seg = np.asarray(closes[j - w:j], dtype="float64")
        if not np.all(np.isfinite(seg)) or np.any(seg <= 0):
            continue
        rows.append(np.log(seg))
    if len(rows) < max(2, int(min_symbols)):
        return None
    phi = end_phases(np.vstack(rows))
    phi = phi[np.isfinite(phi)]
    if len(phi) < max(2, int(min_symbols)):
        return None
    return float(np.abs(np.exp(1j * phi).mean()))


def family_sync_gated(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    window: int = 128,
    tail: float = 1.0 / 3.0,
    min_history: int = 30,
    min_symbols: int = 12,
) -> list[Signal]:
    """`base_family`'s signals kept where the panel's Kuramoto R at signal time ranks in the tail
    its mechanism class needs, against R at the base's earlier signals only: trend/breakout the
    top `tail`, reversion the bottom `tail`."""
    mech = mechanism_class(base_family)
    if mech not in SYNC_HIGH and mech not in SYNC_LOW:
        return []
    _, sigs = base_signals(df, base_family, base_params)
    if not sigs:
        return []
    panel = load_panel()
    if len(panel) < max(2, int(min_symbols)):
        return []
    return keep_in_tail(
        sigs, lambda key, s: kuramoto_r(panel, s.time, window=window, min_symbols=min_symbols),
        keep_top=mech in SYNC_HIGH, tail=tail, min_history=min_history)


# ------------------------------------------------------------------- permutation entropy ---
def _pattern_codes(close: np.ndarray, order: int) -> np.ndarray:
    """One integer per bar i >= order-1: the ordinal pattern of close[i-order+1 .. i]."""
    c = np.asarray(close, dtype="float64")
    m = int(order)
    if len(c) < m:
        return np.empty(0, dtype="int64")
    win = np.lib.stride_tricks.sliding_window_view(c, m)
    ranks = np.argsort(np.argsort(win, axis=1, kind="stable"), axis=1, kind="stable")
    weights = m ** np.arange(m, dtype="int64")
    codes: np.ndarray = (ranks.astype("int64") * weights[None, :]).sum(axis=1)
    return codes


def permutation_entropy(close: Sequence[float] | np.ndarray, *, order: int = 4,
                        window: int = 168) -> np.ndarray:
    """Normalised Bandt-Pompe entropy per bar (NaN until `window` patterns exist).

    Value at bar i uses the `window` patterns ending at bars i-window+1 .. i, so only closes <= i.
    Rolling counts: S = sum_k c_k log c_k is updated by the one pattern entering and the one
    leaving, and H = (log W - S/W) / log m!.
    """
    c = np.asarray(close, dtype="float64")
    m = int(order)
    w = int(window)
    out = np.full(len(c), np.nan)
    if m < MIN_ORDER or m > MAX_ORDER or w < 2:
        return out
    codes = _pattern_codes(c, m)
    if len(codes) < w:
        return out
    _, idx = np.unique(codes, return_inverse=True)
    idx = idx.ravel()
    counts = np.zeros(int(idx.max()) + 1, dtype="int64")
    xlogx = np.zeros(w + 1)
    xlogx[1:] = np.arange(1, w + 1) * np.log(np.arange(1, w + 1))
    norm = math.log(math.factorial(m))
    logw = math.log(w)
    s = 0.0
    off = m - 1
    for i, k in enumerate(idx):
        if i >= w:                      # the pattern leaving first, so no count exceeds w
            o = idx[i - w]
            co = counts[o]
            s += xlogx[co - 1] - xlogx[co]
            counts[o] = co - 1
        ck = counts[k]
        s += xlogx[ck + 1] - xlogx[ck]
        counts[k] = ck + 1
        if i >= w - 1:
            out[i + off] = max(0.0, (logw - s / w) / norm)
    return out


def entropy_z(close: pd.Series, *, order: int = 4, window: int = 168,
              z_window: int = 24 * 60) -> pd.Series:
    """Trailing z-score of the permutation entropy on `close`'s own index (data <= t only)."""
    h = pd.Series(permutation_entropy(close.to_numpy(), order=order, window=window),
                  index=close.index)
    zw = max(10, int(z_window))
    minp = max(10, zw // 2)
    mu = h.rolling(zw, min_periods=minp).mean()
    sd = h.rolling(zw, min_periods=minp).std(ddof=0)
    return ((h - mu) / sd.where(sd > 1e-12)).replace([np.inf, -np.inf], np.nan)


def _value_at(series: pd.Series, t: Any) -> float | None:
    at = _ns(t)
    if at is None or series.empty:
        return None
    if not isinstance(series.index, pd.DatetimeIndex):
        return None
    ix = series.index
    ix = ix.tz_localize("UTC") if ix.tz is None else ix.tz_convert("UTC")
    stamps = ix.as_unit("ns").asi8      # pandas 3 defaults to microseconds; _ns() is nanoseconds
    j = int(np.searchsorted(stamps, at, side="right")) - 1
    if j < 0:
        return None
    v = float(series.iloc[j])
    return v if np.isfinite(v) else None


def family_entropy_gated(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    order: int = 4,
    window: int = 168,
    z_window: int = 24 * 60,
    threshold: float = 1.0,
) -> list[Signal]:
    """`base_family`'s signals kept where the symbol's permutation entropy z <= -threshold."""
    d, sigs = base_signals(df, base_family, base_params)
    if not sigs or d.empty or "close" not in d.columns:
        return []
    z = entropy_z(d["close"].astype("float64"), order=order, window=window, z_window=z_window)
    thr = abs(float(threshold))
    keep: list[Signal] = []
    for s in sigs:
        v = _value_at(z, s.time)
        if v is not None and v <= -thr:
            keep.append(s)
    return keep


# ------------------------------------------------------------- Fisher-Rao distribution drift ---
#: Degrees of freedom the Student-t fits hold fixed. Five is the usual H1-return tail weight and
#: keeps the metric's coefficients (a, b below) away from the Gaussian limit.
T_NU_DEFAULT = 5.0
#: EM iterations for the fixed-nu Student-t location-scale MLE (started at median / MAD).
T_EM_ITERS = 30
#: A window with more than this share of exactly-zero returns is a frozen feed: no fit.
T_FROZEN_ZERO_SHARE = 0.5
#: A fitted scale at or below this (log-return units) is a degenerate fit: no fit.
T_SIGMA_FLOOR = 1e-10


def t_fit(windows: np.ndarray, *, nu: float = T_NU_DEFAULT, iters: int = T_EM_ITERS
          ) -> tuple[np.ndarray, np.ndarray]:
    """(mu, sigma) per row: the Student-t location-scale MLE at fixed `nu`, by EM, numpy only.

    Started at the median and the MAD / 0.6745; each step weights x_i by
    w_i = (nu + 1) / (nu + ((x_i - mu) / sigma)^2), then mu = sum w x / sum w and
    sigma^2 = mean(w (x - mu)^2) -- the EM for the t as a scale mixture of normals (Lange,
    Little & Taylor 1989). A row whose spread is zero returns sigma NaN, and so does a FROZEN
    feed: more than half the returns exactly zero, or a fitted sigma at or below
    `T_SIGMA_FLOOR`. There the EM weights collapse onto the few moves and the distance is
    a property of the stale quote, not of the market (audit SF-1: 21.1 instead of NaN).
    """
    x = np.asarray(windows, dtype="float64")
    if x.ndim == 1:
        x = x[None, :]
    frozen = (x == 0.0).mean(axis=1) > T_FROZEN_ZERO_SHARE
    v = float(nu)
    mu = np.median(x, axis=1)
    sigma = np.median(np.abs(x - mu[:, None]), axis=1) / 0.6744897501960817
    sigma = np.where(sigma > 0, sigma, x.std(axis=1))
    bad = ~(sigma > 0)
    sigma = np.where(bad, 1.0, sigma)
    for _ in range(max(1, int(iters))):
        z2 = ((x - mu[:, None]) / sigma[:, None]) ** 2
        w = (v + 1.0) / (v + z2)
        mu = (w * x).sum(axis=1) / w.sum(axis=1)
        sigma = np.sqrt((w * (x - mu[:, None]) ** 2).mean(axis=1))
        bad |= ~(sigma > 0)
        sigma = np.where(sigma > 0, sigma, 1.0)
    bad |= frozen | ~(sigma > T_SIGMA_FLOOR)
    return mu, np.where(bad, np.nan, sigma)


def fisher_rao_t(mu1: Any, s1: Any, mu2: Any, s2: Any, *, nu: float = T_NU_DEFAULT
                 ) -> np.ndarray:
    """Fisher-Rao distance between two Student-t location-scale laws sharing a fixed `nu`.

    The Fisher information of t_nu(mu, sigma) is diagonal (Lange, Little & Taylor 1989):

        I_mu,mu = (nu + 1) / ((nu + 3) sigma^2) = a / sigma^2,   a = (nu + 1) / (nu + 3)
        I_si,si = 2 nu / ((nu + 3) sigma^2)     = b / sigma^2,   b = 2 nu / (nu + 3)

    so ds^2 = (a dmu^2 + b dsigma^2) / sigma^2. With x = mu sqrt(a / b) this is
    b (dx^2 + dsigma^2) / sigma^2: sqrt(b) times the Poincare half-plane metric, whose distance
    is arccosh(1 + |p - q|^2 / (2 sigma_p sigma_q)). Hence

        d = sqrt(b) * arccosh(1 + ((a / b) (mu1 - mu2)^2 + (sigma1 - sigma2)^2)
                                  / (2 sigma1 sigma2))

    -- the univariate elliptic case of Mitchell (1988, "Statistical manifolds of univariate
    elliptic distributions", Int. Stat. Review 56) and Calvo & Oller (2002). As nu -> inf,
    a -> 1 and b -> 2 and it is the familiar Gaussian Fisher-Rao distance. Pinned by
    tests/test_state_gates_geometry.py against the metric integrated numerically.
    """
    v = float(nu)
    a = (v + 1.0) / (v + 3.0)
    b = 2.0 * v / (v + 3.0)
    m1, m2 = np.asarray(mu1, dtype="float64"), np.asarray(mu2, dtype="float64")
    p, r = np.asarray(s1, dtype="float64"), np.asarray(s2, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        arg = 1.0 + ((a / b) * (m1 - m2) ** 2 + (p - r) ** 2) / (2.0 * p * r)
        out = np.sqrt(b) * np.arccosh(np.maximum(arg, 1.0))
    return np.asarray(np.where((p > 0) & (r > 0), out, np.nan), dtype="float64")


def fisher_rao_drift(close: Sequence[float] | np.ndarray, positions: Sequence[int] | np.ndarray,
                     *, window: int = 120, nu: float = T_NU_DEFAULT) -> np.ndarray:
    """The distribution velocity at each bar index in `positions` (NaN where unmeasurable).

    At bar j the log return is r_j = log c_j - log c_{j-1}. The trailing window is r over bars
    [j-w+1, j], the previous window r over [j-2w+1, j-w]; each gets a fixed-nu Student-t fit and
    the value is the Fisher-Rao distance between the two. Only closes at bars <= j are read, so
    truncating the series after j changes nothing.
    """
    c = np.asarray(close, dtype="float64")
    pos = np.asarray(positions, dtype="int64").ravel()
    out = np.full(len(pos), np.nan)
    w = int(window)
    if w < 8 or len(c) < 2 * w + 1 or len(pos) == 0:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.diff(np.log(c))           # r[i] is the return INTO bar i + 1
    ok = (pos >= 2 * w) & (pos < len(c))
    if not ok.any():
        return out
    win = np.lib.stride_tricks.sliding_window_view(r, w)  # win[k] = r[k : k + w]
    p = pos[ok]
    trail = win[p - w]                   # returns into bars p-w+1 .. p
    prev = win[p - 2 * w]                # returns into bars p-2w+1 .. p-w
    fine = np.isfinite(trail).all(axis=1) & np.isfinite(prev).all(axis=1)
    m1, s1 = t_fit(np.where(fine[:, None], trail, 0.0), nu=nu)
    m2, s2 = t_fit(np.where(fine[:, None], prev, 0.0), nu=nu)
    d = fisher_rao_t(m1, s1, m2, s2, nu=nu)
    out[np.flatnonzero(ok)] = np.where(fine, d, np.nan)
    return out


def _positions(index: pd.Index, keys: Sequence[int]) -> np.ndarray:
    """Index of the last bar stamped at or before each key (-1 when none)."""
    if not isinstance(index, pd.DatetimeIndex):
        return np.full(len(keys), -1, dtype="int64")
    ix = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    stamps = ix.as_unit("ns").asi8      # pandas 3 defaults to microseconds; _ns() is nanoseconds
    out: np.ndarray = np.searchsorted(stamps, np.asarray(keys, dtype="int64"), side="right") - 1
    return out


def family_fisher_rao_gated(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    window: int = 120,
    nu: float = T_NU_DEFAULT,
    tail: float = 1.0 / 3.0,
    min_history: int = 30,
) -> list[Signal]:
    """`base_family`'s signals kept where the symbol's Fisher-Rao distribution velocity ranks in
    the tail its class fixes, against the velocity at the base's earlier signals only: a
    trend/breakout base the BOTTOM tail (slow drift, a stable regime to ride), a reversion base
    the TOP tail (fast drift, a dislocation to fade)."""
    mech = mechanism_class(base_family)
    if mech not in SYNC_HIGH and mech not in SYNC_LOW:
        return []
    d, sigs = base_signals(df, base_family, base_params)
    if not sigs or d.empty or "close" not in d.columns:
        return []
    keys = sorted({k for s in sigs if (k := _ns(s.time)) is not None})
    if not keys:
        return []
    pos = _positions(d.index, keys)
    vals = fisher_rao_drift(d["close"].to_numpy(dtype="float64"), np.maximum(pos, 0),
                            window=window, nu=nu)
    state = {k: (float(v) if p >= 0 and np.isfinite(v) else None)
             for k, p, v in zip(keys, pos, vals, strict=True)}
    return keep_in_tail(sigs, lambda key, s: state.get(key), keep_top=mech in SYNC_LOW,
                        tail=tail, min_history=min_history)


# ---------------------------------------------------------------- absorption ratio (shift) ---
HOUR_NS = 3600 * 10**9
#: Members the absorption panel must keep at a read, below which the read is None (dropped).
ABSORPTION_MIN_MEMBERS = 20
#: AR memo, keyed (panel signature, bar ns, window, k divisor, min members). AR at a stamp is a
#: pure function of data at or before that stamp, so every cell in one process shares it.
_AR_MEMO: dict[tuple[Any, ...], float | None] = {}
_AR_MEMO_MAX = 400_000


def _research_module(name: str) -> Any:
    import importlib
    try:
        return importlib.import_module(f"research.{name}")
    except ImportError:                                            # pragma: no cover - path
        if str(BASE) not in sys.path:
            sys.path.insert(0, str(BASE))
        return importlib.import_module(f"research.{name}")


def absorption_panel_symbols(root: Path | None = None) -> list[str]:
    """Every hypothesis-lane symbol (research.universe_policy.lane) with an H1 file in the store."""
    d = Path(root) if root is not None else xs.UNIVERSE_DIR
    try:
        up = _research_module("universe_policy")
        syms = sorted(p.name[:-len("_H1.parquet")] for p in d.glob("*_H1.parquet"))
        return [s for s in syms if up.lane(s) == up.HYPOTHESIS]
    except Exception:
        return []


def load_absorption_panel() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """{symbol: (int64 ns stamps, closes)} for the absorption panel, through the same
    cross-sectional cache sync_gated's panel uses."""
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for sym in absorption_panel_symbols():
        series = xs._load_series(sym)
        if series is not None:
            out[sym] = series
    return out


def _panel_signature(panel: dict[str, tuple[np.ndarray, np.ndarray]]) -> tuple[Any, ...]:
    """What the AR memo is keyed on: each member's span AND a checksum of its closes, so a
    revised bar (same length, same last stamp) is never served a stale read."""
    return tuple(sorted(
        (sym, len(st), int(st[0]) if len(st) else 0, int(st[-1]) if len(st) else 0,
         float(np.asarray(cl, dtype="float64").sum()))
        for sym, (st, cl) in panel.items()))


def _candidates(panel: dict[str, tuple[np.ndarray, np.ndarray]], at: int, n_bars: int
                ) -> tuple[list[tuple[np.ndarray, np.ndarray]], np.ndarray]:
    """(the members fresh at `at` with >= n_bars bars, as recent slices) and the panel's MARKET
    CLOCK: the last `n_bars` stamps <= at on which at least half of those members print.

    A member whose last bar at or before `at` is older than MAX_STALE_HOURS is out. The majority
    clock keeps a weekend-trading member from defining hours on which the rest is closed.
    """
    stale = MAX_STALE_HOURS * HOUR_NS
    cands: list[tuple[np.ndarray, np.ndarray]] = []
    for stamps, closes in panel.values():
        j = int(np.searchsorted(stamps, at, side="right"))
        if j < n_bars or at - int(stamps[j - 1]) > stale:
            continue
        lo = max(0, j - 3 * n_bars)
        cands.append((stamps[lo:j], closes[lo:j]))
    if not cands:
        return cands, np.empty(0, dtype="int64")
    u, cnt = np.unique(np.concatenate([st for st, _ in cands]), return_counts=True)
    return cands, u[2 * cnt >= len(cands)][-n_bars:]


def aligned_returns(panel: dict[str, tuple[np.ndarray, np.ndarray]], t: Any, *,
                    window: int = 360, min_members: int = ABSORPTION_MIN_MEMBERS
                    ) -> np.ndarray | None:
    """(window x N) log returns on the panel's market clock ending at the last clock stamp <= t,
    one column per member that prints on EVERY one of the window + 1 clock stamps; None when
    fewer than `min_members` qualify."""
    at = _ns(t)
    w = int(window)
    if at is None or w < 8:
        return None
    cands, grid = _candidates(panel, at, w + 1)
    if len(cands) < int(min_members) or len(grid) < w + 1:
        return None
    cols: list[np.ndarray] = []
    for st, cl in cands:
        p = np.searchsorted(st, grid)
        if p[-1] >= len(st) or not np.array_equal(st[p], grid):
            continue
        c = np.asarray(cl[p], dtype="float64")
        if not np.all(np.isfinite(c)) or np.any(c <= 0):
            continue
        cols.append(np.diff(np.log(c)))
    if len(cols) < int(min_members):
        return None
    return np.column_stack(cols)


_BLAS: Any = None


def _one_blas_thread() -> Any:
    """Pin BLAS to one thread for the eigen-decomposition (audit SF-2: threaded BLAS inside a
    process pool oversubscribes the cores, 61 ms against 6.5 ms at N=140). Scoped to the call,
    so no other organ in the process is re-threaded; a box without threadpoolctl runs as before.
    """
    global _BLAS
    if _BLAS is None:
        try:
            from threadpoolctl import ThreadpoolController  # type: ignore[import-untyped]
            _BLAS = ThreadpoolController()
        except Exception:                          # optional on a stripped box
            _BLAS = False
    if _BLAS is False:
        return contextlib.nullcontext()
    return _BLAS.limit(limits=1, user_api="blas")


def absorption_ratio_of(returns: np.ndarray, *, k_divisor: int = 5) -> float | None:
    """AR = share of total variance on the top k = ceil(N / k_divisor) eigenvectors of the
    members' correlation matrix (Kritzman, Li, Page & Rigobon 2011). A flat member is dropped."""
    x = np.asarray(returns, dtype="float64")
    if x.ndim != 2 or x.shape[0] < 3:
        return None
    x = x[:, x.std(axis=0) > 1e-15]
    n = x.shape[1]
    if n < 2:
        return None
    with _one_blas_thread():
        eig = np.clip(np.linalg.eigvalsh(np.corrcoef(x, rowvar=False)), 0.0, None)[::-1]
    tot = float(eig.sum())
    if not tot > 0:
        return None
    k = -(-n // max(1, int(k_divisor)))
    return float(eig[:k].sum() / tot)


def absorption_ratio(panel: dict[str, tuple[np.ndarray, np.ndarray]], t: Any, *,
                     window: int = 360, k_divisor: int = 5,
                     min_members: int = ABSORPTION_MIN_MEMBERS,
                     _sig: tuple[Any, ...] | None = None) -> float | None:
    """AR over the `window` aligned H1 returns ending at the last clock stamp <= t (memoised)."""
    at = _ns(t)
    if at is None:
        return None
    key = (_sig if _sig is not None else _panel_signature(panel), at, int(window),
           int(k_divisor), int(min_members))
    if key in _AR_MEMO:
        return _AR_MEMO[key]
    rets = aligned_returns(panel, at, window=window, min_members=min_members)
    val = None if rets is None else absorption_ratio_of(rets, k_divisor=k_divisor)
    if len(_AR_MEMO) >= _AR_MEMO_MAX:
        _AR_MEMO.clear()
    _AR_MEMO[key] = val
    return val


def absorption_shift(panel: dict[str, tuple[np.ndarray, np.ndarray]], t: Any, *,
                     window: int = 360, short: int = 24, step: int = 6, k_divisor: int = 5,
                     min_members: int = ABSORPTION_MIN_MEMBERS,
                     _sig: tuple[Any, ...] | None = None) -> float | None:
    """The standardised AR shift at t: (AR_1d - AR_15d) / sd(AR over the 15d window).

    AR is read at the market-clock stamps among the last `window` (15 trading days of H1) at or
    before t whose UTC hour is a multiple of `step` -- an ABSOLUTE grid, so every signal and
    every cell in a process reuse the same memoised reads. AR_15d is their mean, AR_1d the mean
    of those inside the last `short` clock bars. Each read uses only data <= its own stamp,
    which is <= t. None when fewer than half the expected reads exist, the last day holds none,
    or AR does not move.
    """
    at = _ns(t)
    w, sh, st = int(window), int(short), max(1, int(step))
    if at is None or w < 8 or not 0 < sh <= w:
        return None
    sig = _sig if _sig is not None else _panel_signature(panel)
    cands, grid = _candidates(panel, at, w)
    if len(cands) < int(min_members) or len(grid) < w:
        return None
    cut = int(grid[-sh])
    longs: list[float] = []
    shorts: list[float] = []
    for s in grid:
        si = int(s)
        if (si // HOUR_NS) % st:
            continue
        v = absorption_ratio(panel, si, window=w, k_divisor=k_divisor,
                             min_members=min_members, _sig=sig)
        if v is None:
            continue
        longs.append(v)
        if si >= cut:
            shorts.append(v)
    if len(longs) < max(3, (w // st) // 2) or not shorts:
        return None
    arr = np.asarray(longs)
    sd = float(arr.std())
    if not sd > 1e-12:
        return None
    return float((np.mean(shorts) - arr.mean()) / sd)


def family_absorption_gated(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    window: int = 360,
    short: int = 24,
    step: int = 6,
    k_divisor: int = 5,
    min_members: int = ABSORPTION_MIN_MEMBERS,
    tail: float = 1.0 / 3.0,
    min_history: int = 30,
) -> list[Signal]:
    """`base_family`'s signals kept where the hypothesis-lane panel's standardised absorption
    shift ranks in the tail its class fixes, against the shift at the base's earlier signals
    only: trend/breakout the TOP tail (a fragile, coupled market), reversion the BOTTOM tail.
    A GATE ON ENTRIES ONLY: it scales no heat and sizes nothing (see the module docstring)."""
    mech = mechanism_class(base_family)
    if mech not in SYNC_HIGH and mech not in SYNC_LOW:
        return []
    _, sigs = base_signals(df, base_family, base_params)
    if not sigs:
        return []
    panel = load_absorption_panel()
    if len(panel) < int(min_members):
        return []
    sig = _panel_signature(panel)
    return keep_in_tail(
        sigs, lambda key, s: absorption_shift(panel, key, window=window, short=short, step=step,
                                              k_divisor=k_divisor, min_members=min_members,
                                              _sig=sig),
        keep_top=mech in SYNC_HIGH, tail=tail, min_history=min_history)


def is_h1(index: pd.Index) -> bool:
    """Whether a frame is an H1 chart: the median step between its stamps is one hour. The
    Markov refit grid is counted in hours and the rough-vol day closes on its 23:00 slot, so
    both read only H1; a frame on another chart is refused (audit SF-4), never re-read."""
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 3:
        return False
    step = np.diff(index.as_unit("ns").asi8)
    return bool(np.median(step) == HOUR_NS)


# ------------------------------------------------------------ Markov-switching variance (HMM) ---
#: Fit window (H1 returns), refit spacing (H1 bars) and the EM's stopping rule.
MS_FIT_WINDOW = 2000
MS_REFIT = 168
MS_MAX_ITER = 100
MS_TOL = 1e-8
#: A state's variance is floored at this share of its fit window's sample variance, and the
#: stay probabilities are clipped inside [MS_P_MIN, 1 - MS_P_MIN]: a state that collapses onto a
#: handful of identical returns, or a chain that never switches, is a degenerate fit.
MS_VAR_FLOOR = 1e-3
MS_P_MIN = 1e-6
#: The refit grid is anchored to TIME, not to the frame: grid instants are Saturday 00:00 UTC
#: plus whole multiples of `refit` hours since the epoch's first Saturday (1970-01-03), so a
#: frame cut at its start, a backfill, a subperiod removal and the live read all fit on the same
#: bars (audit M-1: a frame-counted grid re-phased on every leading cut). At the registered 168
#: the fit lands on the week's last bar, before the Sunday open.
MS_GRID_ANCHOR_NS = 2 * 24 * 3600 * 10**9
#: Fit memo, keyed on a digest of the fit window's own bytes and the EM settings, so every base
#: and cell on one symbol in a process shares a fit and a revised bar is never served a stale
#: one. A digest, not the 16 KB window: 50,000 raw keys held ~800 MB (audit SF-2).
_MS_MEMO: dict[tuple[Any, ...], tuple[float, ...] | None] = {}
_MS_MEMO_MAX = 50_000
_LOG_2PI = math.log(2.0 * math.pi)


def _gauss_logpdf(x: np.ndarray, mu: np.ndarray, var: np.ndarray) -> np.ndarray:
    """Row-wise Gaussian log density: x (F, T), mu and var (F,)."""
    out: np.ndarray = -0.5 * (_LOG_2PI + np.log(var)[:, None]
                              + (x - mu[:, None]) ** 2 / var[:, None])
    return out


def ms_fit(x: np.ndarray, *, max_iter: int = MS_MAX_ITER, tol: float = MS_TOL,
           var_floor: float = MS_VAR_FLOOR) -> np.ndarray:
    """Baum-Welch for a 2-state Gaussian HMM on each row of `x` (F windows x T returns).

    Returns (F, 6): mu_low, mu_high, var_low, var_high, p_stay_low, p_stay_high, with the states
    ORDERED BY VARIANCE (label switching resolved) and NaN rows for a degenerate window -- flat,
    unreadable, or a converged state whose variance sits on its floor. Each row
    stops on its own log-likelihood (|dLL| <= tol * (1 + |LL|)) and is frozen there, so a row's
    fit never depends on which other windows share its batch. The chain starts in its stationary
    distribution; forward/backward are scaled; the emission densities are shifted by their
    per-bar maximum so no extreme return underflows both states. The E-step uses the SMOOTHED
    probabilities, as Baum-Welch must; only the gate (`ms_filter_logodds`) is filtered.
    """
    x = np.atleast_2d(np.asarray(x, dtype="float64"))
    f_n, t_n = x.shape
    out = np.full((f_n, 6), np.nan)
    if t_n < 10 or f_n == 0:
        return out
    with np.errstate(invalid="ignore"):
        v_all = x.var(axis=1)
    good = np.isfinite(x).all(axis=1) & (v_all > 0)
    rows = np.flatnonzero(good)
    if not len(rows):
        return out
    xr = x[rows]
    floor = var_floor * v_all[rows]
    # Start: both means at the window mean, variances from the calm / wild split of the squared
    # deviations at their 70th percentile, stay probabilities 0.98.
    mean = xr.mean(axis=1)
    sq = (xr - mean[:, None]) ** 2
    calm = sq <= np.quantile(sq, 0.7, axis=1)[:, None]
    v0 = np.maximum((sq * calm).sum(1) / np.maximum(calm.sum(1), 1), floor)
    v1 = np.maximum((sq * ~calm).sum(1) / np.maximum((~calm).sum(1), 1), 2.0 * v0)
    stay = np.full(len(rows), 0.98)
    th = np.column_stack([mean, mean, v0, v1, stay, stay])
    ll_prev = np.full(len(rows), -np.inf)
    active = np.arange(len(rows))
    for _ in range(max(1, int(max_iter))):
        if not len(active):
            break
        new, ll = _ms_em_step(xr[active], th[active], floor[active])
        done = np.abs(ll - ll_prev[active]) <= tol * (1.0 + np.abs(ll))
        th[active] = new
        ll_prev[active] = ll
        active = active[~done]
    # A state sitting ON the variance floor collapsed onto a run of identical returns (a stalled
    # quote): its likelihood ratio is then astronomically large after any move and the gate
    # reads the feed, not the regime (audit M-2: log-odds 7e3..1e6). No fit.
    floored = np.minimum(th[:, 2], th[:, 3]) <= floor * (1.0 + 1e-6)
    th[floored] = np.nan
    swap = th[:, 2] > th[:, 3]                    # state 1 is ALWAYS the high-variance regime
    th[swap] = th[swap][:, [1, 0, 3, 2, 5, 4]]
    out[rows] = th
    return out


def _ms_em_step(x: np.ndarray, th: np.ndarray, floor: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray]:
    """One EM step on each row: (new parameters, the log-likelihood under the OLD ones)."""
    mu0, mu1, v0, v1, a00, a11 = (th[:, k] for k in range(6))
    f_n, t_n = x.shape
    ld0, ld1 = _gauss_logpdf(x, mu0, v0), _gauss_logpdf(x, mu1, v1)
    mx = np.maximum(ld0, ld1)
    e0, e1 = np.exp(ld0 - mx), np.exp(ld1 - mx)
    f0 = np.empty((f_n, t_n))
    f1 = np.empty((f_n, t_n))
    c = np.empty((f_n, t_n))
    q1 = (1.0 - a00) / (2.0 - a00 - a11)          # stationary P(high)
    q0 = 1.0 - q1
    for t in range(t_n):
        n0 = q0 * e0[:, t]
        n1 = q1 * e1[:, t]
        ct = n0 + n1
        c[:, t] = ct
        p0, p1 = n0 / ct, n1 / ct
        f0[:, t] = p0
        f1[:, t] = p1
        q0 = p0 * a00 + p1 * (1.0 - a11)
        q1 = p0 * (1.0 - a00) + p1 * a11
    ll = (np.log(c) + mx).sum(axis=1)
    b0 = np.empty((f_n, t_n))
    b1 = np.empty((f_n, t_n))
    b0[:, -1] = 1.0
    b1[:, -1] = 1.0
    for t in range(t_n - 2, -1, -1):
        g0 = e0[:, t + 1] * b0[:, t + 1] / c[:, t + 1]
        g1 = e1[:, t + 1] * b1[:, t + 1] / c[:, t + 1]
        b0[:, t] = a00 * g0 + (1.0 - a00) * g1
        b1[:, t] = (1.0 - a11) * g0 + a11 * g1
    gam0 = f0 * b0
    gam1 = f1 * b1
    s = gam0 + gam1
    gam0 /= s
    gam1 /= s
    w0 = e0[:, 1:] * b0[:, 1:] / c[:, 1:]
    w1 = e1[:, 1:] * b1[:, 1:] / c[:, 1:]
    xi00 = (f0[:, :-1] * a00[:, None] * w0).sum(1)  # expected low -> low transitions
    xi11 = (f1[:, :-1] * a11[:, None] * w1).sum(1)  # expected high -> high transitions
    n0, n1 = gam0.sum(1), gam1.sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        m0 = (gam0 * x).sum(1) / n0
        m1 = (gam1 * x).sum(1) / n1
        nv0 = np.maximum((gam0 * (x - m0[:, None]) ** 2).sum(1) / n0, floor)
        nv1 = np.maximum((gam1 * (x - m1[:, None]) ** 2).sum(1) / n1, floor)
        na00 = np.clip(xi00 / gam0[:, :-1].sum(1), MS_P_MIN, 1.0 - MS_P_MIN)
        na11 = np.clip(xi11 / gam1[:, :-1].sum(1), MS_P_MIN, 1.0 - MS_P_MIN)
    new = np.column_stack([m0, m1, nv0, nv1, na00, na11])
    bad = ~np.isfinite(new).all(axis=1)           # an emptied state keeps its last parameters
    new[bad] = th[bad]
    return new, ll


def ms_filter_logodds(x: np.ndarray, th: Sequence[float]) -> np.ndarray:
    """log P(high | x_0..x_t) - log P(low | x_0..x_t) for each t: the Hamilton filter of one
    return path under fit `th` (variance-ordered, as `ms_fit` returns it), started in the
    chain's stationary distribution. Causal by construction: entry t reads x_0..x_t only.

    The gate ranks the log-odds, not the probability: the two order the bars identically, and the
    probability rounds to exactly 0 or 1 in floating point after a large return, which would tie
    readings the log-odds keeps apart.
    """
    r = np.asarray(x, dtype="float64")
    mu0, mu1, v0, v1, a00, a11 = (float(v) for v in th)
    out = np.full(len(r), np.nan)
    if not (v0 > 0 and v1 > 0 and np.isfinite([mu0, mu1, a00, a11]).all()):
        return out
    lr = 0.5 * (math.log(v0) - math.log(v1)) + 0.5 * ((r - mu0) ** 2 / v0 - (r - mu1) ** 2 / v1)
    p1 = (1.0 - a00) / (2.0 - a00 - a11)        # predicted P(high) before the first return
    for t in range(len(r)):
        lo = math.log(p1) - math.log1p(-p1) + float(lr[t])
        if not math.isfinite(lo):
            continue                            # an unreadable return leaves the prediction
        out[t] = lo
        f1 = 1.0 / (1.0 + math.exp(-lo)) if lo > -700.0 else 0.0
        p1 = min(max((1.0 - f1) * (1.0 - a00) + f1 * a11, 1e-300), 1.0 - 1e-16)
    return out


def ms_grid_bars(stamps: Sequence[int] | np.ndarray, positions: Sequence[int] | np.ndarray,
                 *, refit: int = MS_REFIT) -> np.ndarray:
    """For each bar index p, the index g <= p of the last bar stamped at or before the last
    grid instant <= stamp(p) (see MS_GRID_ANCHOR_NS); -1 where no bar precedes it."""
    st = np.asarray(stamps, dtype="int64")
    pos = np.asarray(positions, dtype="int64").ravel()
    out = np.full(len(pos), -1, dtype="int64")
    inside = (pos >= 0) & (pos < len(st))
    if not inside.any():
        return out
    span = max(1, int(refit)) * HOUR_NS
    t = st[pos[inside]]
    inst = MS_GRID_ANCHOR_NS + ((t - MS_GRID_ANCHOR_NS) // span) * span
    out[inside] = np.searchsorted(st, inst, side="right") - 1
    return out


def markov_vol_state(index: pd.Index, close: Sequence[float] | np.ndarray,
                     positions: Sequence[int] | np.ndarray, *, fit_window: int = MS_FIT_WINDOW,
                     refit: int = MS_REFIT, max_iter: int = MS_MAX_ITER, tol: float = MS_TOL
                     ) -> np.ndarray:
    """The filtered log-odds of the high-variance regime at each bar index in `positions`.

    Bar j's return is R_j = log c_j - log c_{j-1}. The model is refitted on a grid fixed in TIME
    (`ms_grid_bars`): at bar p the fit is the one at g = the last bar stamped at or before the
    last grid instant <= stamp(p), on the `fit_window` returns over bars [g - fit_window + 1, g]
    (memoised on a digest of those returns), so its parameters read data at bars <= g <= p; the
    Hamilton filter then runs under that fit from the window's first bar THROUGH p. NaN before
    the first full fit window or where a window is degenerate. A frame cut at its start changes
    nothing at p while the window still fits inside it; one cut after p changes nothing at p.
    """
    c = np.asarray(close, dtype="float64")
    pos = np.asarray(positions, dtype="int64").ravel()
    out = np.full(len(pos), np.nan)
    w = int(fit_window)
    if (w < 10 or len(c) < w + 1 or not len(pos) or not isinstance(index, pd.DatetimeIndex)
            or len(index) != len(c)):
        return out
    ix = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.concatenate([[np.nan], np.diff(np.log(c))])   # r[j] = the return INTO bar j
    grid = ms_grid_bars(ix.as_unit("ns").asi8, pos, refit=refit)
    ok = (pos >= 0) & (pos < len(c)) & (grid >= w)
    fits: dict[int, tuple[float, ...] | None] = {}
    todo: list[tuple[int, tuple[Any, ...]]] = []
    for g in sorted({int(v) for v in grid[ok]}):
        key = (hashlib.blake2b(r[g - w + 1:g + 1].tobytes(), digest_size=16).digest(), w,
               int(max_iter), float(tol))
        if key in _MS_MEMO:
            fits[g] = _MS_MEMO[key]
        else:
            todo.append((g, key))
    if todo:
        th = ms_fit(np.vstack([r[g - w + 1:g + 1] for g, _ in todo]), max_iter=max_iter, tol=tol)
        if len(_MS_MEMO) + len(todo) > _MS_MEMO_MAX:
            _MS_MEMO.clear()
        for (g, key), row in zip(todo, th, strict=True):
            val = tuple(float(v) for v in row) if np.isfinite(row).all() else None
            _MS_MEMO[key] = fits[g] = val
    by_grid: dict[int, list[int]] = {}
    for i in np.flatnonzero(ok):
        by_grid.setdefault(int(grid[i]), []).append(int(i))
    for g, idx in by_grid.items():
        fit = fits.get(g)
        if fit is None:
            continue
        start = g - w + 1
        lo = ms_filter_logodds(r[start:max(int(pos[i]) for i in idx) + 1], fit)
        for i in idx:
            out[i] = lo[int(pos[i]) - start]
    return out


def family_markov_vol_gated(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    fit_window: int = MS_FIT_WINDOW,
    refit: int = MS_REFIT,
    max_iter: int = MS_MAX_ITER,
    tail: float = 1.0 / 3.0,
    min_history: int = 30,
) -> list[Signal]:
    """`base_family`'s signals kept where the filtered probability of the high-variance regime
    of a 2-state Markov-switching model of the symbol's own H1 returns ranks in the tail its
    class fixes, against that probability at the base's earlier signals only: a trend/breakout
    base the BOTTOM tail (the calm regime), a reversion base the TOP tail (the wild one)."""
    mech = mechanism_class(base_family)
    if mech not in SYNC_HIGH and mech not in SYNC_LOW:
        return []
    d, sigs = base_signals(df, base_family, base_params)
    if not sigs or d.empty or "close" not in d.columns:
        return []
    keys = sorted({k for s in sigs if (k := _ns(s.time)) is not None})
    if not keys:
        return []
    pos = _positions(d.index, keys)
    if not is_h1(d.index):
        return []
    vals = markov_vol_state(d.index, d["close"].to_numpy(dtype="float64"), pos,
                            fit_window=fit_window, refit=refit, max_iter=max_iter)
    state = {k: (float(v) if p >= 0 and np.isfinite(v) else None)
             for k, p, v in zip(keys, pos, vals, strict=True)}
    return keep_in_tail(sigs, lambda key, s: state.get(key), keep_top=mech in SYNC_LOW,
                        tail=tail, min_history=min_history)


# ------------------------------------------------------------- rough volatility (H of log RV) ---
DAY_NS = 24 * HOUR_NS
#: A UTC day is COMPLETE when it holds at least this share of the median bar count of the
#: trailing RV_COUNT_WINDOW days (itself included): a Sunday open stub or a half day at the
#: start of the file is not a day of variance. Read causally and per symbol, so a soft with a
#: nine-hour session is judged against its own sessions, never against a 24-hour FX clock.
RV_MIN_SHARE = 0.75
RV_COUNT_WINDOW = 20
#: ... and holds at most this share of exactly-zero H1 returns.
RV_MAX_FLAT_SHARE = 0.5


def daily_realised_variance(index: pd.Index, close: Sequence[float] | np.ndarray
                            ) -> tuple[np.ndarray, np.ndarray]:
    """(day start ns, RV) for every COMPLETE UTC day: RV = the sum of the squared H1 log returns
    of the bars stamped that day (the return INTO each bar, so the first carries the overnight).

    A day's value is knowable only once its last H1 slot (23:00 UTC) has printed, which is what
    `rough_vol_state` checks before it counts the day.
    """
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 2:
        return np.empty(0, dtype="int64"), np.empty(0)
    ix = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    st = ix.as_unit("ns").asi8
    c = np.asarray(close, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.concatenate([[np.nan], np.diff(np.log(c))])
    days, inv, counts = np.unique(st // DAY_NS, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    fine = np.isfinite(r)
    rv = np.bincount(inv, weights=np.where(fine, r * r, 0.0), minlength=len(days))
    # A day holding an unreadable return (the file's first bar has none) is incomplete.
    bad = np.bincount(inv, weights=(~fine).astype("float64"), minlength=len(days))
    # A day mostly of unchanged closes is a stalled feed, not a quiet day: a one-tick day's
    # log RV of -41 moved H by ~0.04 (audit SF-1).
    flat = np.bincount(inv, weights=(fine & (r == 0.0)).astype("float64"), minlength=len(days))
    med = (pd.Series(counts.astype("float64"))
           .rolling(RV_COUNT_WINDOW, min_periods=1).median().to_numpy())
    keep = ((counts >= RV_MIN_SHARE * med) & (bad == 0) & (rv > 0)
            & (flat <= RV_MAX_FLAT_SHARE * counts))
    return (days[keep] * DAY_NS).astype("int64"), rv[keep]


def hurst_of_log_rv(x: Sequence[float] | np.ndarray, *, window: int = 250, max_lag: int = 10
                    ) -> np.ndarray:
    """H at each day k: the least-squares slope of log m(q) on log q, q = 1..max_lag, where m(q)
    is the mean |x_{j+q} - x_j| over the pairs inside the trailing `window` days
    [k - window + 1, k] (Gatheral, Jaisson & Rosenbaum 2018, "Volatility is rough", the first
    absolute moment). NaN until `window` days exist. x is log RV = 2 log sigma + noise, and the
    factor 2 does not move the slope.
    """
    v = np.asarray(x, dtype="float64")
    n, w, lmax = len(v), int(window), int(max_lag)
    out = np.full(n, np.nan)
    if lmax < 2 or w <= lmax + 1 or n < w:
        return out
    lq = np.log(np.arange(1, lmax + 1, dtype="float64"))
    lq -= lq.mean()
    k = np.arange(w - 1, n)
    logm = np.empty((len(k), lmax))
    for q in range(1, lmax + 1):
        cs = np.concatenate([[0.0], np.cumsum(np.abs(v[q:] - v[:-q]))])  # pair j is (j, j + q)
        with np.errstate(divide="ignore"):
            logm[:, q - 1] = np.log((cs[k - q + 1] - cs[k - w + 1]) / (w - q))
    out[w - 1:] = ((logm - logm.mean(axis=1, keepdims=True)) @ lq) / float(lq @ lq)
    return np.where(np.isfinite(out), out, np.nan)


def rough_vol_state(index: pd.Index, close: Sequence[float] | np.ndarray, keys: Sequence[int],
                    *, window: int = 250, max_lag: int = 10) -> np.ndarray:
    """H at each ns stamp in `keys`, over the last `window` complete days whose final H1 slot
    (23:00 UTC) is at or before the stamp: a day still in progress at t never counts, and an
    incomplete day never counts at all. NaN until `window` such days exist."""
    k_arr = np.asarray(keys, dtype="int64")
    out = np.full(len(k_arr), np.nan)
    days, rv = daily_realised_variance(index, close)
    if len(days) < int(window):
        return out
    h = hurst_of_log_rv(np.log(rv), window=window, max_lag=max_lag)
    j = np.searchsorted(days + 23 * HOUR_NS, k_arr, side="right") - 1
    have = j >= 0
    out[have] = h[j[have]]
    return out


def family_rough_vol_gated(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    window: int = 250,
    max_lag: int = 10,
    tail: float = 1.0 / 3.0,
    min_history: int = 30,
) -> list[Signal]:
    """`base_family`'s signals kept where the roughness H of the symbol's own daily realised
    variance ranks in the tail its class fixes, against H at the base's earlier signals only: a
    trend/breakout base the TOP tail (persistent volatility), a reversion base the BOTTOM tail
    (rough, anti-persistent volatility)."""
    mech = mechanism_class(base_family)
    if mech not in SYNC_HIGH and mech not in SYNC_LOW:
        return []
    d, sigs = base_signals(df, base_family, base_params)
    if not sigs or d.empty or "close" not in d.columns:
        return []
    keys = sorted({k for s in sigs if (k := _ns(s.time)) is not None})
    if not keys or not is_h1(d.index):
        return []
    vals = rough_vol_state(d.index, d["close"].to_numpy(dtype="float64"), keys,
                           window=window, max_lag=max_lag)
    state = {k: (float(v) if np.isfinite(v) else None) for k, v in zip(keys, vals, strict=True)}
    return keep_in_tail(sigs, lambda key, s: state.get(key), keep_top=mech in SYNC_HIGH,
                        tail=tail, min_history=min_history)


#: WHY NO STATE GATE IS LIVE-EXECUTABLE YET (audit of #399, SF-3). Every wrapper ranks its state
#: against the state at ALL the base's earlier signals in the frame (`keep_in_tail`, at least
#: `min_history` of them), and the slow states need long windows besides (Markov 2,000 H1 returns,
#: rough-vol 250 complete days). The gateway's family read is 400 H1 bars, so a certificate
#: traded today would rank against a different, shorter history than it was certified on -- or
#: keep nothing -- with no refusal naming why. `executables.executor_gap` names this instead,
#: until the history is bounded in market time and the gateway reads that much.
LIVE_READ_GAP = ("state-gated wrapper: ranks against every earlier base signal in the frame "
                 "and needs up to 250 days of H1 history; the gateway's family read is 400 H1 "
                 "bars, so a live read would not reproduce the certified gate")

STATE_GATE_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "sync_gated": family_sync_gated,
    "entropy_gated": family_entropy_gated,
    "fisher_rao_gated": family_fisher_rao_gated,
    "absorption_gated": family_absorption_gated,
    "markov_vol_gated": family_markov_vol_gated,
    "rough_vol_gated": family_rough_vol_gated,
}
