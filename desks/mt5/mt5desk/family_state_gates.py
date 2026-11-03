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

R and the entropy are computed only where a base signal exists for sync (one panel read per
signal time) and over the symbol's own closes for entropy. Both return [] -- never an ungated
fallback -- when the base is unwrappable, the panel is short or the state is unmeasurable.
"""
from __future__ import annotations

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
    q = float(tail)
    if not 0.0 < q < 1.0:
        return []
    need = max(1, int(min_history))
    keep: list[Signal] = []
    memo: dict[int, float | None] = {}
    timed = sorted(((k, s) for s in sigs if (k := _ns(s.time)) is not None),
                   key=lambda ks: ks[0])
    history: list[float] = []          # R at every STRICTLY EARLIER signal bar, in time order
    pending: tuple[int, float] | None = None
    for key, s in timed:
        if pending is not None and pending[0] != key:
            history.append(pending[1])  # a bar's R joins the history once its bar has passed
            pending = None
        if key not in memo:
            memo[key] = kuramoto_r(panel, s.time, window=window, min_symbols=min_symbols)
        r = memo[key]
        if r is None:
            continue
        pending = (key, r)
        if len(history) >= need:
            below = sum(1 for h in history if h < r) / len(history)
            if (below >= 1.0 - q) if mech in SYNC_HIGH else (below <= q):
                keep.append(s)
    return keep


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


STATE_GATE_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "sync_gated": family_sync_gated,
    "entropy_gated": family_entropy_gated,
}
