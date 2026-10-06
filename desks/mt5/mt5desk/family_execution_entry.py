"""EXECUTION-ENTRY FAMILIES -- the same directional thesis, entered at a better moment.

WHY THESE EXIST (2026-10-06). `execution_entry` is one of the fifteen declared alpha clusters
(`libs/research/alpha_clusters`: "money made or lost between the decision and the fill is a P&L
source with no market view at all") and no registered family classified into it, so
`empty_cluster_forcer` filed it UNREACHABLE and the breadth law could raise no debt against it.
`empty_cluster_forcer.MISSING_ARTIFACT` named this file as the remedy.

THE RAW MATERIAL IS ALREADY ON DISK. Every bar this desk holds carries Fusion's own `spread`
(`family_spread_state` reads the same column), and the session clock is `family_call.SESSIONS`,
the one window table the gauntlet, the forward clock and the executor share. Measured on the
committed H1 store: the server-hour-0 bar (the rollover and the Asia open) carries a spread well
above its session's norm -- EURUSD 16 against 12 points, GBPJPY 57 against 13 -- and the bar
after it is back at the norm. `overnight_gap_decay`, the desk's second certified mechanism,
decides on exactly that bar and fills on the next one.

TWO FAMILIES, both OPERATORS over a price-only base family's market entries. The base cell
entered at market is the control arm and already sits in the docket; each family asks whether
the ENTRY POLICY pays, holding the directional thesis fixed:

  entry_alpha_spread_session_median   Enter only when the last closed bar's spread is at or
      below its own session's trailing median (quantile `spread_q`). A base signal decided on a
      wide-spread bar is held until the spread normalises, at most `max_wait` bars, and is
      dropped when it never does. Payer: the venue's wide-spread hours, which a market entry
      pays to the liquidity provider.

  entry_alpha_post_open_normalised    Only the base signals whose fill would land in the first
      `open_minutes` of a session open (server hours `family_call.SESSIONS`), re-entered after
      the open window AND once the spread has normalised. Signals elsewhere are dropped: they are
      the base cell unchanged, and re-testing them would charge a second trial for no new
      question. Payer: the opening auction's liquidity vacuum.

CAUSALITY. A bar's `spread` is known when that bar CLOSES. A signal is stamped on the closed bar
whose spread admitted it and the engine fills at the next bar's open, so the spread that decided
an entry was printed before the entry. The session median is computed over STRICTLY EARLIER bars
of the same session (shifted one bar within the session), so the bar being judged never sets its
own threshold. `desks/mt5/tests/test_no_lookahead.py` corrupts the future and checks, because
both are registered "price only".

STOP AND TARGET MOVE WITH THE ENTRY. A delayed entry keeps the base signal's stop and target
DISTANCES from the new reference close, so the operator changes the entry and nothing else.

NOTHING HERE PROMOTES and nothing falls back: no spread column, an unwrappable base, a base that
rests stop orders (no market entry to move) or too little history each return [].
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.engine import Signal
from mt5desk.families import _h1, bar_minutes, get_family_func

#: The registry keys, and the cluster each is built to fill. `libs.research.alpha_clusters`
#: declares the same mapping exactly (a test pins them equal).
FAMILY_NAMES: tuple[str, ...] = ("entry_alpha_spread_session_median",
                                 "entry_alpha_post_open_normalised")
TARGET_CLUSTER = "execution_entry"

#: The default base: the desk's own certified overnight-gap mechanism, which decides on the
#: rollover bar where the spread is widest. A default the compiler can mint without a recipe.
DEFAULT_BASE = "overnight_gap_decay"

#: Bases whose signals need an injected runtime input (`family_alt_series._UNWRAPPABLE`) or are
#: themselves operators. Read from that module so the two lists cannot drift.
_SELF: frozenset[str] = frozenset(FAMILY_NAMES)

#: Bars of the SAME session a trailing median is taken over, and the minimum before it speaks.
MIN_WINDOW = 10


def wrappable_base(name: str) -> bool:
    """A price-only base this operator can rebuild from the bars alone."""
    if not name or name in _SELF:
        return False
    from mt5desk.family_alt_series import wrappable
    return bool(wrappable(name))


def session_opens() -> tuple[int, ...]:
    """Server-hour session opens, from the ONE session table the clock and gauntlet share."""
    from mt5desk.family_call import SESSIONS
    return tuple(sorted({int(w[0]) for w in SESSIONS.values() if w is not None}))


def session_labels(index: pd.DatetimeIndex) -> np.ndarray:
    """Per bar, the MOST RECENTLY OPENED session whose window holds the bar's server hour.

    The overlap (london and ny both open) belongs to ny, the session that just opened; hours no
    window holds are their own group `off`, so a quiet hour is never judged against a busy one.
    """
    from mt5desk.family_call import SESSIONS
    hours = np.asarray(pd.DatetimeIndex(index).hour)
    out = np.full(len(hours), "off", dtype=object)
    best = np.full(len(hours), -1)
    for name, win in SESSIONS.items():
        if win is None:
            continue
        lo, hi = int(win[0]), int(win[1])
        inside = (hours >= lo) & (hours < hi) & (lo > best)
        out[inside] = name
        best[inside] = lo
    return out


def bar_spread(df: pd.DataFrame, d: pd.DataFrame) -> pd.Series | None:
    """The broker's spread on `d`'s clock, from the ORIGINAL frame (`_h1` may drop columns)."""
    if "spread" not in df.columns:
        return None
    raw = pd.to_numeric(df["spread"], errors="coerce")
    raw.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    raw = raw[~raw.index.duplicated(keep="last")]
    sp = raw.reindex(d.index)
    if sp.notna().sum() == 0:
        return None
    return sp.astype(float)


def session_threshold(spread: pd.Series, labels: np.ndarray, *, window: int,
                      spread_q: float) -> pd.Series:
    """Per bar, the `spread_q` quantile of the previous `window` bars OF THE SAME SESSION.

    Shifted one bar within the session, so a bar never sets its own threshold; NaN until half
    the window is seen, and a NaN threshold admits nothing."""
    grp = pd.Series(labels, index=spread.index)
    return spread.groupby(grp, sort=False).transform(
        lambda s: s.rolling(int(window), min_periods=max(MIN_WINDOW // 2, int(window) // 2))
        .quantile(float(spread_q)).shift(1))


def spread_ok(df: pd.DataFrame, d: pd.DataFrame, *, window: int,
              spread_q: float) -> np.ndarray | None:
    """Boolean per bar of `d`: its spread is at or below its session's trailing quantile."""
    sp = bar_spread(df, d)
    if sp is None:
        return None
    thr = session_threshold(sp, session_labels(pd.DatetimeIndex(d.index)), window=window,
                            spread_q=spread_q)
    ok = (sp <= thr) & sp.notna() & thr.notna()
    return ok.to_numpy(dtype=bool)


def base_signals(d: pd.DataFrame, base_family: str,
                 base_params: dict[str, Any] | None) -> list[Signal]:
    """The base's MARKET-entry signals, built exactly as the gauntlet builds the base cell."""
    if not wrappable_base(base_family):
        return []
    fn = get_family_func(base_family)
    if fn is None:
        return []
    params = {k: v for k, v in dict(base_params or {}).items()
              if k not in ("timeframe", "session", "symbol")}
    try:
        raw = fn(d, side=1, **params)
    except TypeError:
        try:
            raw = fn(d, **params)
        except Exception:
            return []
    except Exception:
        return []
    # A stop-entry base already rests an order; there is no market entry to move.
    return [s for s in (raw or []) if isinstance(s, Signal) and s.trigger is None]


def _rebased(s: Signal, t: Any, ref_old: float, ref_new: float, tag: str) -> Signal | None:
    """`s` re-stamped at `t` with its stop and target kept at the same distance from the new
    reference close -- the entry moves, the trade's geometry does not."""
    if not (math.isfinite(ref_old) and math.isfinite(ref_new) and ref_new > 0):
        return None
    dist_stop = abs(ref_old - float(s.stop))
    dist_tgt = abs(float(s.target) - ref_old)
    if not (dist_stop > 0 and math.isfinite(dist_stop) and math.isfinite(dist_tgt)):
        return None
    side = int(s.side)
    return Signal(time=t, side=side, stop=ref_new - side * dist_stop,
                  target=ref_new + side * dist_tgt, ttl_bars=int(s.ttl_bars),
                  tag=f"{tag}<{s.tag}", trigger=None, wait_bars=1)


def _positions(d: pd.DataFrame, sigs: list[Signal]) -> np.ndarray:
    st = pd.DatetimeIndex(d.index).as_unit("ns").asi8
    return np.searchsorted(st, np.array([pd.Timestamp(s.time).value for s in sigs],
                                        dtype="int64"), side="left")


def _valid(window: int, spread_q: float, max_wait: int) -> bool:
    return int(window) >= MIN_WINDOW and 0 < float(spread_q) < 1 and int(max_wait) >= 0


def family_entry_alpha_spread_session_median(
    df: pd.DataFrame,
    *,
    base_family: str = DEFAULT_BASE,
    base_params: dict[str, Any] | None = None,
    spread_q: float = 0.5,
    window: int = 120,
    max_wait: int = 3,
) -> list[Signal]:
    """The base's signals entered only off a bar whose spread is at or below its session's
    trailing median; a wide-spread decision waits up to `max_wait` bars, then is dropped."""
    if not _valid(window, spread_q, max_wait):
        return []
    d = _h1(df)
    if d.empty or len(d) < 2 * int(window):
        return []
    base = base_signals(d, base_family, base_params)
    if not base:
        return []
    ok = spread_ok(df, d, window=int(window), spread_q=float(spread_q))
    if ok is None:
        return []
    close = d["close"].to_numpy(dtype=float)
    n = len(d)
    out: list[Signal] = []
    for s, p in zip(base, _positions(d, base), strict=True):
        p = int(p)
        if p >= n or d.index[p] != pd.Timestamp(s.time):
            continue
        for j in range(p, min(p + int(max_wait) + 1, n - 1)):
            if ok[j]:
                g = (s if j == p else
                     _rebased(s, d.index[j], float(close[p]), float(close[j]),
                              "entry_alpha_spread_session_median"))
                if g is not None:
                    out.append(g)
                break
    return out


def family_entry_alpha_post_open_normalised(
    df: pd.DataFrame,
    *,
    base_family: str = DEFAULT_BASE,
    base_params: dict[str, Any] | None = None,
    open_minutes: int = 120,
    spread_q: float = 0.5,
    window: int = 120,
    max_wait: int = 6,
) -> list[Signal]:
    """The base's signals that would fill inside the first `open_minutes` of a session open,
    re-entered on the first closed bar past the open window whose spread has normalised."""
    if not _valid(window, spread_q, max_wait) or int(open_minutes) <= 0:
        return []
    d = _h1(df)
    if d.empty or len(d) < 2 * int(window):
        return []
    base = base_signals(d, base_family, base_params)
    if not base:
        return []
    ok = spread_ok(df, d, window=int(window), spread_q=float(spread_q))
    if ok is None:
        return []
    step = int(bar_minutes(d) or 60)
    idx = pd.DatetimeIndex(d.index)
    # Minutes from the most recent session open to each bar's CLOSE (= the next bar's fill time).
    close_min = (np.asarray(idx.hour) * 60 + np.asarray(idx.minute) + step) % 1440
    opens = [h * 60 for h in session_opens()]
    since = np.full(len(idx), 10 ** 6)
    for o in opens:
        since = np.minimum(since, (close_min - o) % 1440)
    in_window = since < int(open_minutes)
    close = d["close"].to_numpy(dtype=float)
    n = len(d)
    out: list[Signal] = []
    for s, p in zip(base, _positions(d, base), strict=True):
        p = int(p)
        if p >= n or d.index[p] != pd.Timestamp(s.time) or not in_window[p]:
            continue                       # not an open-window fill: the base cell unchanged
        for j in range(p + 1, min(p + int(max_wait) + 1, n - 1)):
            if not in_window[j] and ok[j]:
                g = _rebased(s, d.index[j], float(close[p]), float(close[j]),
                             "entry_alpha_post_open_normalised")
                if g is not None:
                    out.append(g)
                break
    return out


FAMILIES: dict[str, Any] = {
    "entry_alpha_spread_session_median": family_entry_alpha_spread_session_median,
    "entry_alpha_post_open_normalised": family_entry_alpha_post_open_normalised,
}
