"""Six idea families from the Tier-1 gap list (zuck, 2026-11-11), each the claim and nothing else.

    intraday_momentum       U1  the session's first window predicts its last window
    overnight_day_tug       U2  night leg and day leg disagree; trade one side of the tug
    implied_realised_gap    U3  CBOE GVZ / OVX (FRED) against the instrument's own realised vol
    weekend_crypto_gap      U4  Fusion crypto CFDs trade Sat-Sun; their weekend move vs Monday
    equity_gap_breadth      U5  share-CFD opening gaps across the US class, traded on the index
    holiday_drift           N1  the session before an exchange holiday, and the one after it

U6 (Kim-Wright term premium, FRED THREEFYTP10) needs no new family: it is a `world_macro_state`
cell on that series, minted by `research/tier1_idea_proposer.py` with the rest. N2 (degree-day
surprise) and N3 (Fed net liquidity) are World sensor's, in #903 and #904; they are not repeated.

WHAT EACH ONE READS, AND NOTHING ELSE. Desk bars, the instrument's own session clock
(`local_clock`, DST-exact), the free FRED series the world dataset hunter stores point-in-time,
the rule-generated holiday calendars under `data/calendars/holidays_<venue>.json`, and the
desk's own Fusion crypto and share-CFD bars. Crypto is read only as a sensor of an MT5
instrument; share CFDs only as a breadth input to an index (the class-book rule is kept: no
single name is a target here).

POINT IN TIME. A signal is stamped on a bar whose CLOSE is the latest information it used and is
filled at the next bar's open, as the engine fills every family. A FRED value is visible only
from the instant the hunter says it was knowable. A clock exit is a bar count fixed by the
session's declared hours, never read off where later bars happen to fall.

REFUSES (returns []) on a malformed window, missing input or too little history, never guesses.
`side` is accepted and unused, as in `family_world_macro`: the recipe's `direction` is the side,
so the sealed gauntlet (side=1) and the forward clock (side=-1 on a short) build the same trades.
"""
from __future__ import annotations

import json
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk import local_clock as LC
from mt5desk.engine import Signal

CALENDARS = Path(__file__).resolve().parents[1] / "data" / "calendars"
UNIVERSE = Path(__file__).resolve().parents[1] / "data" / "universe" / "universe.json"
DIRECTIONS = {"follow": 1, "fade": -1}
SIDES = {"long": 1, "short": -1}

#: The cash session each target is judged on, in the venue's own clock, and its holiday calendar.
#: Gold and silver use the COMEX pit hours, oil and gas the NYMEX pit hours; they have no
#: exchange-holiday calendar of their own here, so N1 does not target them.
SESSIONS: dict[str, tuple[str, str, str, str]] = {
    "US500": ("America/New_York", "09:30", "16:00", "nyse"),
    "US30": ("America/New_York", "09:30", "16:00", "nyse"),
    "NAS100": ("America/New_York", "09:30", "16:00", "nyse"),
    "US2000": ("America/New_York", "09:30", "16:00", "nyse"),
    "GER40": ("Europe/Berlin", "09:00", "17:30", "xetra"),
    "EUSTX50": ("Europe/Berlin", "09:00", "17:30", "xetra"),
    "FRA40": ("Europe/Paris", "09:00", "17:30", ""),
    "UK100": ("Europe/London", "08:00", "16:30", "lse"),
    "JPN225": ("Asia/Tokyo", "09:00", "15:00", "jpx"),
    "XAUUSD": ("America/New_York", "08:20", "13:30", ""),
    "XAGUSD": ("America/New_York", "08:25", "13:25", ""),
    "XTIUSD": ("America/New_York", "09:00", "14:30", ""),
    "XBRUSD": ("America/New_York", "09:00", "14:30", ""),
    "XNGUSD": ("America/New_York", "09:00", "14:30", ""),
}


def _atr(df: pd.DataFrame, n: int) -> np.ndarray:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(),
                    (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(int(n)).mean().to_numpy(dtype=float)


def _hhmm(minutes: int) -> str:
    m = int(minutes) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def _signal(idx: pd.DatetimeIndex, i: int, side: int, px: float, a: float, stop_atr: float,
            rr: float, ttl: int, tag: str) -> Signal:
    return Signal(time=idx[i], side=int(side), stop=px - side * stop_atr * a,
                  target=px + side * stop_atr * a * rr, ttl_bars=max(1, int(ttl)), tag=tag,
                  trigger=None, wait_bars=1)


def first_per_date(mask: np.ndarray | None, ymd: np.ndarray) -> dict[int, int]:
    """{local date: position of the first bar on that date where `mask` holds}."""
    out: dict[int, int] = {}
    if mask is None:
        return out
    for i in np.flatnonzero(mask):
        out.setdefault(int(ymd[i]), int(i))
    return out


def session_bars(index: Any, tz: str, open_at: str, close_at: str) -> dict[int, tuple[int, int]]:
    """{local date: (open bar, close bar)} -- the bar containing the open and the bar containing
    the minute before the close, on the same local date, open strictly before close."""
    o_min, c_min = LC.minutes_of(open_at), LC.minutes_of(close_at)
    if o_min is None or c_min is None or c_min <= o_min or not tz:
        return {}
    idx = pd.DatetimeIndex(index)
    try:
        _m, ymd = LC.local_frame(idx, tz)
    except Exception:
        return {}
    opens = first_per_date(LC.window_mask(idx, tz, open_at, "contains"), ymd)
    closes = first_per_date(LC.window_mask(idx, tz, _hhmm(c_min - 1), "contains"), ymd)
    return {d: (o, closes[d]) for d, o in opens.items() if d in closes and o < closes[d]}


# ------------------------------------------------------------------------------- U1 ----------
def family_intraday_momentum(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    tz: str = "America/New_York",
    open_at: str = "09:30",
    close_at: str = "16:00",
    first_min: int = 30,
    last_min: int = 30,
    min_move_atr: float = 0.0,
    direction: str = "follow",
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.0,
) -> list[Signal]:
    """U1: the return from yesterday's close to the end of today's first window predicts the
    session's last window (Gao, Han, Li and Zhou 2018, on the S&P 500 ETF).

    The payer is the late-day rebalancer: leveraged-ETF and short-gamma hedgers who must trade
    WITH the day's move into the close. On a bar coarser than the window, the window ends at the
    close of the bar containing its last minute (an H1 chart reads a 30-minute window to the hour
    boundary); the last window starts at the bar containing `close - last_min`, and the trade is
    held to the session's last bar. `direction="fade"` is the falsifier's mirror, charged as its
    own cell.
    """
    del side
    flip = DIRECTIONS.get(str(direction))
    o_min, c_min = LC.minutes_of(open_at), LC.minutes_of(close_at)
    if (flip is None or o_min is None or c_min is None or int(first_min) <= 0
            or int(last_min) <= 0 or o_min + int(first_min) >= c_min - int(last_min)):
        return []
    if df.empty or len(df) < int(atr_n) * 5:
        return []
    idx = pd.DatetimeIndex(df.index)
    sess = session_bars(idx, tz, open_at, close_at)
    if len(sess) < 2:
        return []
    _m, ymd = LC.local_frame(idx, tz)
    first_end = first_per_date(
        LC.window_mask(idx, tz, _hhmm(o_min + int(first_min) - 1), "contains"), ymd)
    last_start = first_per_date(
        LC.window_mask(idx, tz, _hhmm(c_min - int(last_min)), "contains"), ymd)
    close = df["close"].to_numpy(dtype=float)
    atr = _atr(df, atr_n)
    out: list[Signal] = []
    dates = sorted(sess)
    for prev, day in pairwise(dates):
        f, e = first_end.get(day), last_start.get(day)
        o, c = sess[day]
        if f is None or e is None or not (o <= f < e - 1 < e <= c):
            continue
        s = e - 1                                            # decide on the bar before the window
        base, a = close[sess[prev][1]], atr[s]
        if not (np.isfinite(a) and a > 0 and np.isfinite(base) and base > 0):
            continue
        move = close[f] - base
        if move == 0 or abs(move) < float(min_move_atr) * a:
            continue
        sd = int(np.sign(move)) * flip
        out.append(_signal(idx, s, sd, close[s], a, stop_atr, rr, c - e + 1,
                           f"intraday_momentum:{tz}:{direction}"))
    return out


# ------------------------------------------------------------------------------- U2 ----------
def family_overnight_day_tug(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    tz: str = "America/New_York",
    open_at: str = "09:30",
    close_at: str = "16:00",
    min_day_atr: float = 0.5,
    follow: str = "night",
    hold_bars: int = 0,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.0,
) -> list[Signal]:
    """U2: the night leg (yesterday's close to today's open) and the day leg (open to close) are
    priced by different clienteles -- overnight by retail and foreign flow, intraday by
    institutions (Lou, Polk and Skouras 2019, "A tug of war"). When they disagree in sign and the
    day leg is material, trade at the close in the direction of `follow` ("night" or "day") and
    hold to the next session's open (`hold_bars=0`: the bar count the declared hours fix).

    The open is read at the open of the bar containing the session open, so on an H1 chart a
    09:30 open is priced at 09:00 -- stated, not hidden.
    """
    del side
    if follow not in ("night", "day"):
        return []
    o_min, c_min = LC.minutes_of(open_at), LC.minutes_of(close_at)
    if o_min is None or c_min is None or c_min <= o_min or df.empty or len(df) < atr_n * 5:
        return []
    idx = pd.DatetimeIndex(df.index)
    sess = session_bars(idx, tz, open_at, close_at)
    if len(sess) < 2:
        return []
    span = LC.bar_minutes(idx)
    ttl = int(hold_bars) or max(1, round((1440 - (c_min - o_min)) / max(span, 1)))
    opn, close = df["open"].to_numpy(dtype=float), df["close"].to_numpy(dtype=float)
    atr = _atr(df, atr_n)
    out: list[Signal] = []
    dates = sorted(sess)
    for prev, day in pairwise(dates):
        o, c = sess[day]
        night, dayleg, a = opn[o] - close[sess[prev][1]], close[c] - opn[o], atr[c]
        if not (np.isfinite(a) and a > 0) or night * dayleg >= 0:
            continue
        if abs(dayleg) < float(min_day_atr) * a:
            continue
        sd = int(np.sign(night if follow == "night" else dayleg))
        out.append(_signal(idx, c, sd, close[c], a, stop_atr, rr, ttl,
                           f"overnight_day_tug:{tz}:{follow}"))
    return out


# ------------------------------------------------------------------------------- U3 ----------
#: The implied-vol series each target may be judged against. A pairing outside this table is
#: refused: GVZ against oil would be a different claim with no payer behind it.
IMPLIED_FOR = {"GVZCLS": ("XAUUSD", "XAGUSD", "XAUEUR", "XAUAUD"),
               "OVXCLS": ("XTIUSD", "XBRUSD")}


def fred_series(series_id: str) -> pd.Series | None:
    """A FRED series as the world dataset hunter stored it, on its knowable-at clock, or None."""
    try:
        from research.world_dataset_hunter import raw_world_series, series_key
    except ImportError:                                                    # desk-root callers
        from world_dataset_hunter import raw_world_series, series_key  # type: ignore[no-redef]
    s = raw_world_series(series_key("FRED", str(series_id), str(series_id)))
    return s if s is not None and len(s) else None


def _align(series: pd.Series, index: pd.DatetimeIndex) -> np.ndarray:
    s = series if series.index.tz is not None else series.tz_localize("UTC")
    want = index.tz
    s = s.tz_convert("UTC").tz_localize(None) if want is None else s.tz_convert(want)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.reindex(s.index.union(index)).ffill().reindex(index).to_numpy(dtype=float)


def day_ends(index: pd.DatetimeIndex) -> np.ndarray:
    """Positions of the last bar of each bar-clock date (UTC-stamped broker days)."""
    d = np.asarray(index.normalize().asi8)
    return np.flatnonzero(np.append(d[1:] != d[:-1], True))


def family_implied_realised_gap(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    implied_series: str = "GVZCLS",
    rv_days: int = 20,
    z_obs: int = 250,
    z_lo: float = 1.0,
    z_hi: float = 99.0,
    direction: str = "long",
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
    implied: pd.Series | None = None,
) -> list[Signal]:
    """U3: the CBOE gold (GVZ) or oil (OVX) implied volatility minus the instrument's own
    realised volatility, z-scored on its own daily history, as a state gate.

    The payer is the option buyer: a hedger who pays a premium over realised to insure a book.
    A premium unusually rich says hedgers are crowded into protection; the claim is that the
    underlying then drifts in `direction` while the premium is in [z_lo, z_hi). Realised vol is
    the annualised standard deviation of the last `rv_days` daily close-to-close log returns, in
    the same percentage points CBOE quotes. Decided at each day's last bar on values knowable by
    then; `implied` may be handed in (tests), otherwise the FRED series is read from the store.
    """
    del side
    flip = SIDES.get(str(direction))
    if flip is None or str(implied_series) not in IMPLIED_FOR or float(z_hi) <= float(z_lo):
        return []
    iv = implied if implied is not None else fred_series(str(implied_series))
    if iv is None or len(iv) < int(z_obs) // 2 or df.empty:
        return []
    idx = pd.DatetimeIndex(df.index)
    ends = day_ends(idx)
    if len(ends) < int(z_obs) + int(rv_days) + 2:
        return []
    close = df["close"].to_numpy(dtype=float)
    daily = pd.Series(close[ends], index=idx[ends])
    rv = np.log(daily).diff().rolling(int(rv_days)).std(ddof=1) * np.sqrt(252.0) * 100.0
    gap = pd.Series(_align(iv.astype(float), idx[ends]), index=idx[ends]) - rv
    r = gap.rolling(int(z_obs), min_periods=int(z_obs))
    z = ((gap - r.mean()) / r.std(ddof=1)).to_numpy(dtype=float)
    atr = _atr(df, atr_n)
    out: list[Signal] = []
    last = -10 ** 9
    for k, i in enumerate(ends):
        if i - last < int(hold_bars) or i >= len(idx) - 1:
            continue
        zi, a = z[k], atr[i]
        if not (np.isfinite(zi) and float(z_lo) <= zi < float(z_hi) and np.isfinite(a) and a > 0):
            continue
        out.append(_signal(idx, int(i), flip, close[i], a, stop_atr, rr, hold_bars,
                           f"implied_realised_gap:{implied_series}:{direction}"))
        last = int(i)
    return out


# ------------------------------------------------------------------------------- U4 ----------
#: The weekend-trading drivers this family may read. Fusion crypto CFDs, as MT5 instruments.
DRIVERS = ("BTCUSD", "ETHUSD")


def family_weekend_crypto_gap(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    driver_symbol: str = "BTCUSD",
    min_move_sd: float = 1.0,
    vol_weekends: int = 26,
    direction: str = "follow",
    require_gap_disagree: bool = False,
    hold_bars: int = 6,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.0,
    driver: pd.DataFrame | None = None,
) -> list[Signal]:
    """U4: the crypto CFD's weekend move, measured to the target's Monday reopen, as a signal for
    the target's first Monday session.

    Crypto CFDs keep pricing risk appetite while FX, gold and index CFDs are shut. The claim is
    that the target's reopen under-prices that weekend information and the gap continues
    (`follow`), or that it over-prices it and reverts (`fade`). The weekend move is the driver's
    log return from its last bar at or before the target's Friday close to its last bar that
    ENDS by the target's Monday open, in units of the standard deviation of the previous
    `vol_weekends` weekend moves (weekend crypto trades thinner than the week, so a weekday scale
    would read every weekend as quiet). Decided on the target's first Monday bar, filled at the
    next open, so the gap itself is never claimed. `require_gap_disagree` keeps only weekends
    where the target's reopen gap has the opposite sign to the driver's move (the part not yet
    priced).
    """
    del side
    flip = DIRECTIONS.get(str(direction))
    if flip is None or str(driver_symbol) not in DRIVERS or df.empty or len(df) < atr_n * 5:
        return []
    if driver is None:
        try:
            from mt5desk.family_inputs import bars_named
        except ImportError:                                                 # pragma: no cover
            return []
        driver = bars_named(str(driver_symbol), df)
    if driver is None or len(driver) < 200 or "close" not in driver.columns:
        return []
    # nanoseconds on both clocks: `asi8` is in the index's own unit, and a us-resolution frame
    # compared against ns Timedeltas finds no weekend at all
    idx = pd.DatetimeIndex(df.index).as_unit("ns")
    didx = pd.DatetimeIndex(driver.index).as_unit("ns")
    span = pd.Timedelta(minutes=LC.bar_minutes(idx))
    dclose = driver["close"].to_numpy(dtype=float)
    past: list[float] = []
    opn, close = df["open"].to_numpy(dtype=float), df["close"].to_numpy(dtype=float)
    atr = _atr(df, atr_n)
    gaps = np.flatnonzero(np.diff(idx.asi8) > pd.Timedelta(hours=36).value) + 1
    out: list[Signal] = []
    for i in gaps:
        if i + 1 >= len(idx) or idx[i].dayofweek != 0:
            continue
        fri, mon = idx[i - 1] + span, idx[i]
        p0 = int(np.searchsorted(didx.asi8, fri.value, side="right")) - 1
        p1 = int(np.searchsorted(didx.asi8, (mon - span).value, side="right")) - 1
        if p0 < 0 or p1 <= p0 or not (dclose[p0] > 0 and dclose[p1] > 0):
            continue
        move = float(np.log(dclose[p1] / dclose[p0]))
        hist = past[-int(vol_weekends):]
        past.append(move)
        v = float(np.std(hist, ddof=1)) if len(hist) >= int(vol_weekends) else 0.0
        if not v > 0:
            continue
        z = move / v
        if abs(z) < float(min_move_sd):
            continue
        gap = opn[i] - close[i - 1]
        if require_gap_disagree and gap * z >= 0:
            continue
        a = atr[i]
        if not (np.isfinite(a) and a > 0):
            continue
        out.append(_signal(idx, int(i), int(np.sign(z)) * flip, close[i], a, stop_atr, rr,
                           hold_bars, f"weekend_crypto_gap:{driver_symbol}:{direction}"))
    return out


# ------------------------------------------------------------------------------- U5 ----------
#: Cap on the share panel, so one call never loads the whole equity class on a small box.
MAX_NAMES = 400


def us_share_names(universe: Path = UNIVERSE) -> tuple[str, ...]:
    """US share CFDs in the registry: Equities, profit in USD, the cash-session line only."""
    try:
        doc = json.loads(universe.read_text("utf-8"))
    except (OSError, ValueError):
        return ()
    out = [k for k, v in doc.items()
           if isinstance(v, dict) and v.get("asset_class") == "Equities"
           and v.get("currency_profit") == "USD" and not str(k).upper().endswith(".24H")]
    return tuple(sorted(out)[:MAX_NAMES])


def gap_breadth(panel: dict[str, pd.DataFrame], tz: str, open_at: str, close_at: str, *,
                gap_sd: float, vol_days: int, min_names: int) -> pd.Series:
    """Per local date, (names gapping up beyond `gap_sd` - names gapping down) / names reporting,
    stamped at the open bar's time. A name's gap is its open over its previous session close,
    in units of its own trailing daily close-to-close volatility (prior days only)."""
    ups: dict[pd.Timestamp, int] = {}
    dns: dict[pd.Timestamp, int] = {}
    seen: dict[pd.Timestamp, int] = {}
    for d in panel.values():
        if d is None or len(d) < 50 or "open" not in d.columns:
            continue
        sess = session_bars(d.index, tz, open_at, close_at)
        if len(sess) < int(vol_days) + 2:
            continue
        dates = sorted(sess)
        idx = pd.DatetimeIndex(d.index)
        opn, close = d["open"].to_numpy(dtype=float), d["close"].to_numpy(dtype=float)
        cl = np.array([close[sess[x][1]] for x in dates])
        ret = np.diff(np.log(cl))
        for k in range(int(vol_days) + 1, len(dates)):
            sd = float(np.std(ret[k - 1 - int(vol_days):k - 1], ddof=1))
            o = sess[dates[k]][0]
            if not (sd > 0 and cl[k - 1] > 0 and opn[o] > 0):
                continue
            z = float(np.log(opn[o] / cl[k - 1])) / sd
            t = idx[o]
            seen[t] = seen.get(t, 0) + 1
            if z >= gap_sd:
                ups[t] = ups.get(t, 0) + 1
            elif z <= -gap_sd:
                dns[t] = dns.get(t, 0) + 1
    rows = {t: (ups.get(t, 0) - dns.get(t, 0)) / n for t, n in seen.items() if n >= min_names}
    return pd.Series(rows, dtype=float).sort_index()


@lru_cache(maxsize=4)
def _panel_breadth(timeframe: str, tz: str, open_at: str, close_at: str, gap_sd: float,
                   vol_days: int, min_names: int, stamp: int) -> pd.Series:
    del stamp                                                    # the cache key's file clock
    try:
        from research import orthogonal_sweep as inputs
    except ImportError:                                                     # pragma: no cover
        import orthogonal_sweep as inputs  # type: ignore[no-redef]
    panel = {s: inputs._bars(s, timeframe) for s in us_share_names()}
    return gap_breadth(panel, tz, open_at, close_at, gap_sd=gap_sd, vol_days=vol_days,
                       min_names=min_names)


def family_equity_gap_breadth(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    tz: str = "America/New_York",
    open_at: str = "09:30",
    close_at: str = "16:00",
    gap_sd: float = 2.0,
    vol_days: int = 20,
    min_names: int = 20,
    breadth_lo: float = 0.1,
    direction: str = "follow",
    hold_bars: int = 0,
    atr_n: int = 20,
    stop_atr: float = 1.5,
    rr: float = 1.0,
    breadth: pd.Series | None = None,
) -> list[Signal]:
    """U5: the share-CFD class's opening gaps, aggregated, as a signal for the index that day.

    In earnings season most outsized single-name gaps are earnings reactions; when far more names
    gap up than down (or the reverse), the information is about the whole tape, and the index
    under-reacts at the open (`follow`) or over-reacts (`fade`). Breadth is
    (big gaps up - big gaps down) / names reporting, computed at the open bar from opens and
    prior closes only; decided on the index's bar containing the open, held to the session's
    last bar (`hold_bars=0`). Trades the index, never a single name. `breadth` may be handed in
    (tests); otherwise the US share panel on this chart is read by the family itself.
    """
    del side
    flip = DIRECTIONS.get(str(direction))
    o_min, c_min = LC.minutes_of(open_at), LC.minutes_of(close_at)
    if flip is None or o_min is None or c_min is None or c_min <= o_min or df.empty:
        return []
    idx = pd.DatetimeIndex(df.index)
    if breadth is None:
        try:
            from mt5desk.families import bar_minutes
            from mt5desk.universe_registry import TIMEFRAME_MINUTES
            mins = bar_minutes(df)
            tf = next((k for k, v in TIMEFRAME_MINUTES.items() if v == mins), None)
            stamp = int(UNIVERSE.stat().st_mtime_ns) if UNIVERSE.exists() else 0
        except Exception:
            return []
        if tf is None:
            return []
        breadth = _panel_breadth(tf, tz, open_at, close_at, float(gap_sd), int(vol_days),
                                 int(min_names), stamp)
    if breadth is None or breadth.empty:
        return []
    sess = session_bars(idx, tz, open_at, close_at)
    span = LC.bar_minutes(idx)
    ttl = int(hold_bars) or max(1, round((c_min - o_min) / max(span, 1)))
    b = _align(breadth, idx)
    close = df["close"].to_numpy(dtype=float)
    atr = _atr(df, atr_n)
    out: list[Signal] = []
    for _day, (o, _c) in sorted(sess.items()):
        bi, a = b[o], atr[o]
        if not (np.isfinite(bi) and abs(bi) >= float(breadth_lo) and np.isfinite(a) and a > 0):
            continue
        # the breadth is stamped at the share bars' open time; a value dated later than this
        # index bar is not yet visible on it (`_align` carries only what is at or before it)
        out.append(_signal(idx, o, int(np.sign(bi)) * flip, close[o], a, stop_atr, rr, ttl,
                           f"equity_gap_breadth:{direction}"))
    return out


# ------------------------------------------------------------------------------- N1 ----------
@lru_cache(maxsize=16)
def _holidays(name: str, mtime_ns: int) -> frozenset[int]:
    del mtime_ns
    try:
        doc = json.loads((CALENDARS / f"holidays_{name}.json").read_text("utf-8"))
    except (OSError, ValueError):
        return frozenset()
    return frozenset(int(str(d).replace("-", "")) for d in doc.get("holidays") or [])


def holidays(name: str) -> frozenset[int]:
    """The closure dates (YYYYMMDD) of a rule-generated venue calendar; empty if unreadable."""
    if not name or not name.isalnum():
        return frozenset()
    path = CALENDARS / f"holidays_{name}.json"
    try:
        return _holidays(name, path.stat().st_mtime_ns)
    except OSError:
        return frozenset()


def _next_weekday(ymd: int) -> int:
    d = pd.Timestamp(str(ymd)) + pd.Timedelta(days=1)
    while d.dayofweek >= 5:
        d += pd.Timedelta(days=1)
    return int(d.strftime("%Y%m%d"))


def family_holiday_drift(
    df: pd.DataFrame,
    *,
    side: int | None = None,
    calendar: str = "nyse",
    tz: str = "America/New_York",
    open_at: str = "09:30",
    close_at: str = "16:00",
    leg: str = "pre",
    direction: str = "long",
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.0,
) -> list[Signal]:
    """N1: the index on the session before an exchange holiday (`leg="pre"`: from the close of
    the session before it to the pre-holiday close), or on the first session after it
    (`leg="post"`: from that session's open to its close).

    The pre-holiday effect (Ariel 1990; Kim and Park 1994) is paid by short sellers and
    market-makers who flatten before a long close and by the cash that sits idle over it. The
    holiday dates are the venue's own, generated by rule in `research/exchange_holidays.py`; a
    session whose next weekday is a closure date is a pre-holiday session. The CFD keeps
    printing through some closures, so the exit is a fixed number of bars set by the declared
    session length -- one trading day -- never by where later bars fall.
    """
    del side
    flip = SIDES.get(str(direction))
    hol = holidays(str(calendar))
    o_min, c_min = LC.minutes_of(open_at), LC.minutes_of(close_at)
    if flip is None or leg not in ("pre", "post") or not hol or o_min is None or c_min is None:
        return []
    if df.empty or len(df) < atr_n * 5:
        return []
    idx = pd.DatetimeIndex(df.index)
    sess = session_bars(idx, tz, open_at, close_at)
    dates = [d for d in sorted(sess) if d not in hol and pd.Timestamp(str(d)).dayofweek < 5]
    if len(dates) < 3:
        return []
    span = max(LC.bar_minutes(idx), 1)
    ttl = (max(1, round(1440 / span) - 1) if leg == "pre"
           else max(1, round((c_min - o_min) / span)))
    close = df["close"].to_numpy(dtype=float)
    atr = _atr(df, atr_n)
    out: list[Signal] = []
    for k in range(1, len(dates) - 1):
        day = dates[k]
        if _next_weekday(day) not in hol:
            continue
        # pre: decided at the close of the session before; post: on the bar before the first
        # post-holiday session's open bar, held through that session (the calendar is known in
        # advance, so naming that session is not reading a later bar)
        at = sess[dates[k - 1]][1] if leg == "pre" else sess[dates[k + 1]][0] - 1
        if at < 0:
            continue
        a = atr[at]
        if not (np.isfinite(a) and a > 0) or at >= len(idx) - 1:
            continue
        out.append(_signal(idx, at, flip, close[at], a, stop_atr, rr, ttl,
                           f"holiday_drift:{calendar}:{leg}:{direction}"))
    return out


TIER1_IDEA_FAMILIES = {
    "intraday_momentum": family_intraday_momentum,
    "overnight_day_tug": family_overnight_day_tug,
    "implied_realised_gap": family_implied_realised_gap,
    "weekend_crypto_gap": family_weekend_crypto_gap,
    "equity_gap_breadth": family_equity_gap_breadth,
    "holiday_drift": family_holiday_drift,
}
