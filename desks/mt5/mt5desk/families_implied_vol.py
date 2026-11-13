"""OPTIONS-IMPLIED FAMILIES: the CBOE implied-vol indices `recorders/vol_archive.py` archives, read
point-in-time on the instruments they describe, through the sealed gauntlet unchanged.

THREE NON-EXOTIC MECHANISMS, each on the ground the recorder already maps (^VIX/^VXN/^VXD to the
US indices, ^GVZ to XAUUSD, ^EVZ to EURUSD):

  vrp_conditioned   A CONDITIONER (an operator over a base cell, like `entry_conditioned`). The
      variance risk premium -- implied vol minus THIS BROKER's realised vol on the cell's own
      bars -- is what option buyers pay sellers for insurance. When it is rich, dealers are long
      premium and calm, carry-like and trend books are paid; when it is thin or negative,
      realised has outrun implied and the hedgers are short gamma into the move. The base cell's
      signals are kept only on days whose premium is above (`high`) or at/below (`low`) its own
      trailing median. Payer: the option buyer / short-gamma hedger (Bollerslev, Tauchen & Zhou
      2009; Carr & Wu 2009).
  iv_term_gated     A REGIME GATE over a base cell. The VIX term structure is in contango in calm
      and inverts in stress (short-dated implied above longer-dated). The base cell's signals
      are kept only where the ratio short/long of a CONTEMPORANEOUS curve (both tenors quoted on
      the same date) is below (`contango`) or at/above (`backwardation`) `ratio_thr`. Payer: the
      stale-regime positioner whose risk model reads yesterday's regime.
  iv_shock          An EVENT family. A day-over-day log jump in the mapped implied-vol index of
      at least `k_sd` of its own trailing daily sd (strictly prior days) is a forced re-hedge;
      `fade` takes the side AGAINST the instrument's own trailing move into the decision bar,
      `follow` takes it WITH that move. One daily decision at `decision_hour` (broker), held
      `hold_d` days, entry at the next open.

HONEST CAVEAT, KEPT IN CODE BECAUSE IT GOVERNS HOW MUCH THESE MAY BE TRUSTED. The IV history is
PUBLIC -- any desk can download ten years of ^VIX this afternoon -- so these families are
CROWDING-CHECKED CONDITIONERS, NOT A MOAT. The only proprietary part is the join to this broker's
own realised vol in `vrp_conditioned`, and even that is a conditioner on a public series. Every
cell is charged to the trial census and judged by the sealed gauntlet like any other; nothing
here sizes, promotes or bypasses a gate.

WHERE THE HISTORY COMES FROM. `observations.jsonl` holds one forward-only value per cycle, which
cannot be backtested. The recorder also fetches each index's full daily history every cycle and
now PERSISTS it (`vol_archive.persist_reference`) to
`data/vol_archive/reference/<TICKER>.json` -- {date: close}, merged across cycles so a date the
source stops serving is kept and a restated value is logged under `restatements`. These families
read that file and nothing else; a missing, empty or unreadable file returns [] -- NEVER a
price-only fallback, which would judge a different hypothesis under this one's name.

POINT-IN-TIME, BY CONSTRUCTION, AND THE LAG IS A STATED CHOICE:
  * a CBOE daily close for date D is USABLE ONLY FROM D+1 00:00 UTC (`available_ns`). The index
    settles at 16:15 New York (20:15 / 21:15 UTC), so the next UTC midnight is after the close in
    both seasons; nothing finer is claimed.
  * the decision instant is the BAR'S OPEN converted from the broker clock to true UTC by the
    desk's one conversion (`libs.regime.session_clock.server_to_utc`, UTC+2 winter / UTC+3
    summer). The bar's own close -- when the signal is actually priced -- is an hour later still,
    so the comparison is conservative by one bar. A frame already stamped in UTC is read as
    broker time and so shifted 2-3 h EARLIER: stricter, never lenient.
  * a value is never read whose availability instant is after the decision instant
    (`searchsorted(..., side="right") - 1` on availability, not on value date), and a value older
    than `max_stale_d` days at the decision is ABSENT, not carried forward.
  * the realised leg of the premium for a signal on broker date T uses only broker dates
    strictly before T; the median it is compared with uses only days strictly before T.
  * THE RESTATEMENT CAVEAT: the backtest reads the LATEST value for each date (restated values
    are logged, not versioned per read). CBOE index restatements are rare and small, and the
    log makes any that occur visible; a strict as-first-seen read is possible from
    `first_seen` once the desk's own vintages are long enough.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, bars_per_day

BASE = Path(__file__).resolve().parent.parent
#: Written by `recorders/vol_archive.persist_reference` on the trading box (task MT5-VolArchive).
REFERENCE_DIR = BASE / "data" / "vol_archive" / "reference"
_NS_PER_D = 86_400_000_000_000
#: Hours after the value date's UTC midnight at which a daily close becomes usable: 24, i.e.
#: D+1 00:00 UTC (see the module docstring for why that is after the CBOE settle).
PUBLICATION_LAG_H = 24
#: Realised-vol window in trading days, matched to the recorder's own (`vol_archive.RV_WINDOW_D`)
#: so a cell and the archive mean the same premium.
RV_WINDOW_D = 21
ANNUALISE = math.sqrt(252.0)

_CACHE: dict[str, tuple[int, np.ndarray, np.ndarray]] = {}


# ----------------------------------------------------------------------- reference history ---
def reference_filename(ticker: str) -> str:
    """`^VIX9D` -> `VIX9D.json`. The recorder names its files by the same rule (a test pins it)."""
    safe = re.sub(r"[^A-Za-z0-9]+", "_", str(ticker or "").lstrip("^")).strip("_")
    return f"{safe or 'UNNAMED'}.json"


def load_reference(ticker: str) -> tuple[np.ndarray, np.ndarray] | None:
    """(value dates as UTC-midnight ns, closes) of `ticker`'s persisted daily history, sorted by
    date, positive finite closes only. None when the file is absent, unreadable or empty."""
    if not ticker:
        return None
    path = REFERENCE_DIR / reference_filename(ticker)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    key = str(path)
    hit = _CACHE.get(key)
    if hit is not None and hit[0] == mtime:
        return hit[1], hit[2]
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    closes = doc.get("closes") if isinstance(doc, dict) else None
    if not isinstance(closes, dict) or not closes:
        return None
    rows: list[tuple[int, float]] = []
    for k, v in closes.items():
        try:
            ns = int(pd.Timestamp(str(k)[:10], tz="UTC").value)
            val = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(val) and val > 0:
            rows.append((ns, val))
    if not rows:
        return None
    rows.sort()
    dates = np.array([r[0] for r in rows], dtype="int64")
    vals = np.array([r[1] for r in rows], dtype="float64")
    _CACHE[key] = (mtime, dates, vals)
    return dates, vals


def available_ns(value_dates_ns: np.ndarray) -> np.ndarray:
    """The first instant (UTC ns) each daily close may be read: D+1 00:00 UTC."""
    return value_dates_ns + int(PUBLICATION_LAG_H) * 3_600_000_000_000


def decision_utc_ns(stamps: pd.DatetimeIndex) -> np.ndarray | None:
    """True UTC instants (ns) of broker-stamped bars, by the desk's one conversion. None when the
    conversion is unavailable -- the families then return [], never read an unconverted clock."""
    if len(stamps) == 0:
        return np.zeros(0, dtype="int64")
    try:
        from libs.regime.session_clock import server_to_utc
        return np.asarray(server_to_utc(stamps).asi8, dtype="int64")
    except Exception:
        return None


def asof_index(avail: np.ndarray, at_ns: np.ndarray, *, max_stale_d: float) -> np.ndarray:
    """Row of the latest value AVAILABLE at each instant, -1 where none is or it is stale."""
    j = np.searchsorted(avail, at_ns, side="right") - 1
    jj = np.where(j >= 0, j, 0)
    ok = (j >= 0) & ((at_ns - avail[jj]) <= float(max_stale_d) * _NS_PER_D)
    return np.where(ok, j, -1)


def iv_asof(ticker: str, at_ns: np.ndarray, *, max_stale_d: float = 4.0) -> np.ndarray | None:
    """`ticker`'s close as known at each UTC instant; NaN where none is yet available or it is
    stale. None when the series itself is absent."""
    ref = load_reference(ticker)
    if ref is None:
        return None
    dates, vals = ref
    j = asof_index(available_ns(dates), at_ns, max_stale_d=max_stale_d)
    out = np.full(at_ns.size, np.nan)
    out[j >= 0] = vals[j[j >= 0]]
    return out


# ------------------------------------------------------------------------- shared plumbing ---
def _operator_base(df: pd.DataFrame, base_family: str, base_params: dict[str, Any] | None,
                   symbol: str) -> tuple[pd.DataFrame, list[Signal], np.ndarray] | None:
    """(bars, base signals, each signal's decision UTC ns), or None when there is nothing."""
    from mt5desk.families_specialist import base_signals, wrappable
    if not base_family or not wrappable(base_family) or df is None or len(df) == 0:
        return None
    d = _h1(df)
    sigs = base_signals(d, base_family, base_params, symbol)
    if not sigs:
        return None
    times = pd.DatetimeIndex([pd.Timestamp(s.time) for s in sigs])
    if times.tz is None:
        times = times.tz_localize("UTC")
    at = decision_utc_ns(times)
    if at is None:
        return None
    return d, sigs, at


def daily_realised_vol(d: pd.DataFrame, window_d: int = RV_WINDOW_D
                       ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(broker-date ns, last-bar stamp ns of that date, annualised close-to-close realised vol in
    PERCENT through that date) from the cell's OWN bars -- this broker's realised, the CBOE
    indices' units. NaN until a full window exists."""
    idx = d.index
    day = idx.normalize().asi8
    last = np.r_[day[1:] != day[:-1], True]
    pos = np.flatnonzero(last)
    close = d["close"].to_numpy(dtype="float64")[pos]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.r_[np.nan, np.diff(np.log(close))]
    rv = (pd.Series(r).rolling(int(window_d), min_periods=int(window_d)).std()
          .to_numpy() * ANNUALISE * 100.0)
    return day[pos], idx.asi8[pos], rv


# ------------------------------------------------------------------- (a) variance premium ---
def family_vrp_conditioned(
    df: pd.DataFrame,
    *,
    base_family: str,
    iv_ticker: str,
    base_params: dict[str, Any] | None = None,
    symbol: str = "",
    vrp_state: str = "high",
    rv_window_d: int = RV_WINDOW_D,
    median_window_d: int = 252,
    max_stale_d: float = 4.0,
) -> list[Signal]:
    """`base_family`'s signals kept only where the variance risk premium is in `vrp_state`.

    Premium at a signal = `iv_ticker` as known at the signal bar (D+1 00:00 UTC lag) minus this
    broker's realised vol through the LAST BROKER DATE BEFORE the signal's. `high`: above the
    median of the same premium over the previous `median_window_d` days (each day's premium taken
    at its own last bar with that day's realised vol, all strictly before the signal's date);
    `low`: at or below it. The base keeps its own sides; this only drops signals."""
    if vrp_state not in ("high", "low") or int(rv_window_d) < 5 or int(median_window_d) < 20:
        return []
    got = _operator_base(df, base_family, base_params, symbol)
    if got is None:
        return []
    d, sigs, at = got
    days, last_stamp, rv = daily_realised_vol(d, int(rv_window_d))
    last_utc = decision_utc_ns(pd.DatetimeIndex(pd.to_datetime(last_stamp, unit="ns", utc=True)))
    if last_utc is None or days.size == 0:
        return []
    iv_day = iv_asof(iv_ticker, last_utc, max_stale_d=max_stale_d)
    iv_sig = iv_asof(iv_ticker, at, max_stale_d=max_stale_d)
    if iv_day is None or iv_sig is None:
        return []
    vrp_day = iv_day - rv
    med = (pd.Series(vrp_day).rolling(int(median_window_d), min_periods=int(median_window_d) // 2)
           .median().to_numpy())
    sig_day = pd.DatetimeIndex([pd.Timestamp(s.time) for s in sigs])
    if sig_day.tz is None:
        sig_day = sig_day.tz_localize("UTC")
    # row of the last broker date STRICTLY before each signal's own date
    prev = np.searchsorted(days, sig_day.normalize().asi8, side="left") - 1
    ok = prev >= 0
    pp = np.where(ok, prev, 0)
    vrp_sig = np.where(ok, iv_sig - rv[pp], np.nan)
    thr = np.where(ok, med[pp], np.nan)
    good = ok & np.isfinite(vrp_sig) & np.isfinite(thr)
    keep = good & ((vrp_sig > thr) if vrp_state == "high" else (vrp_sig <= thr))
    return [s for s, k in zip(sigs, keep, strict=True) if k]


# --------------------------------------------------------------------- (b) term structure ---
def term_ratio(short_ticker: str, long_ticker: str
               ) -> tuple[np.ndarray, np.ndarray] | None:
    """(value dates ns, short/long) on the dates BOTH tenors are quoted -- a contemporaneous
    curve only, the recorder's own rule: a fresh short tenor beside a stale long one is a slope
    manufactured from a publication lag."""
    a, b = load_reference(short_ticker), load_reference(long_ticker)
    if a is None or b is None:
        return None
    common, ia, ib = np.intersect1d(a[0], b[0], assume_unique=True, return_indices=True)
    if common.size == 0:
        return None
    return common, a[1][ia] / b[1][ib]


def family_iv_term_gated(
    df: pd.DataFrame,
    *,
    base_family: str,
    short_ticker: str,
    long_ticker: str,
    base_params: dict[str, Any] | None = None,
    symbol: str = "",
    term_state: str = "contango",
    ratio_thr: float = 1.0,
    max_stale_d: float = 4.0,
) -> list[Signal]:
    """`base_family`'s signals kept only in the named implied-vol TERM REGIME: `contango` where
    short/long < `ratio_thr`, `backwardation` where it is >= `ratio_thr`, the ratio read from the
    latest contemporaneous curve available at the signal bar."""
    if term_state not in ("contango", "backwardation") or not float(ratio_thr) > 0:
        return []
    if not short_ticker or not long_ticker or short_ticker == long_ticker:
        return []
    got = _operator_base(df, base_family, base_params, symbol)
    if got is None:
        return []
    _d, sigs, at = got
    curve = term_ratio(short_ticker, long_ticker)
    if curve is None:
        return []
    dates, ratio = curve
    j = asof_index(available_ns(dates), at, max_stale_d=max_stale_d)
    r = np.where(j >= 0, ratio[np.where(j >= 0, j, 0)], np.nan)
    fin = np.isfinite(r)
    keep = fin & ((r < float(ratio_thr)) if term_state == "contango"
                  else (r >= float(ratio_thr)))
    return [s for s, k in zip(sigs, keep, strict=True) if k]


# ---------------------------------------------------------------------------- (c) IV shock ---
def shock_z(vals: np.ndarray, sd_window: int) -> np.ndarray:
    """Per value date: log(v_t / v_{t-1}) over the sd of the previous `sd_window` such changes
    (strictly prior, so a jump cannot inflate its own yardstick)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.r_[np.nan, np.diff(np.log(vals))]
    sd = (pd.Series(r).rolling(int(sd_window), min_periods=int(sd_window) // 2).std()
          .shift(1).to_numpy())
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(sd > 0, r / sd, np.nan)


def family_iv_shock(
    df: pd.DataFrame,
    *,
    iv_ticker: str,
    mode: str = "fade",
    k_sd: float = 2.0,
    sd_window: int = 60,
    return_lb_d: int = 1,
    decision_hour: int = 9,
    hold_d: int = 1,
    max_stale_d: float = 4.0,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    """On the first daily decision at which a NEW `iv_ticker` close is available and its jump is
    >= `k_sd` sd: `fade` trades against the instrument's own `return_lb_d`-day move into the
    decision bar, `follow` with it. A value date is acted on once (a holiday does not re-fire
    yesterday's shock)."""
    if mode not in ("fade", "follow") or not float(k_sd) > 0 or int(sd_window) < 20:
        return []
    if int(return_lb_d) < 1 or int(hold_d) < 1 or not iv_ticker or df is None or len(df) == 0:
        return []
    ref = load_reference(iv_ticker)
    if ref is None:
        return []
    from mt5desk.families_specialist import _daily_decisions, _signal
    d = _h1(df)
    pos = _daily_decisions(d, int(decision_hour))
    if pos.size <= int(return_lb_d):
        return []
    at = decision_utc_ns(d.index[pos])
    if at is None:
        return []
    dates, vals = ref
    z = shock_z(vals, int(sd_window))
    j = asof_index(available_ns(dates), at, max_stale_d=max_stale_d)
    close = d["close"].to_numpy(dtype="float64")[pos]
    atr = _atr(d, int(atr_n)).to_numpy()
    ttl = int(hold_d) * bars_per_day(d)
    out: list[Signal] = []
    acted = -1
    lb = int(return_lb_d)
    for k, p in enumerate(pos):
        jk = int(j[k])
        if jk < 0 or jk == acted or k < lb or p >= len(d) - 1:
            continue
        acted = jk                    # a value date is judged at its FIRST decision only
        zk = z[jk]
        if not (np.isfinite(zk) and zk >= float(k_sd)):
            continue
        a, b = close[k - lb], close[k]
        if not (a > 0 and b > 0) or a == b:
            continue
        move = 1 if b > a else -1
        side = -move if mode == "fade" else move
        s = _signal(d, int(p), side, atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl,
                    tag=f"iv_shock:{mode}:{iv_ticker}")
        if s is not None:
            out.append(s)
    return out


# ---------------------------------------------------------------------------- registration ---
#: Merged into `families_specialist`'s tables (and from there into ORTHOGONAL_FAMILIES,
#: FAMILY_INPUTS and FAMILY_TIMEFRAMES by `families_orthogonal`), so the sealed gauntlet resolves
#: them through its ordinary orthogonal lookup with no input branch.
IMPLIED_VOL_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "vrp_conditioned": family_vrp_conditioned,
    "iv_term_gated": family_iv_term_gated,
    "iv_shock": family_iv_shock,
}
#: The two operators: like `entry_conditioned`, never wrapped by another operator.
OPERATORS = frozenset({"vrp_conditioned", "iv_term_gated"})

_REF = "data/vol_archive/reference/<{}>.json (CBOE daily close, usable from D+1 00:00 UTC)"
INFORMATION_CLASS: dict[str, str] = dict.fromkeys(IMPLIED_VOL_FAMILIES, "exogenous")
FOREIGN_SERIES: dict[str, tuple[tuple[str | None, str], ...]] = {
    "vrp_conditioned": (("iv_ticker", _REF.format("iv_ticker")),),
    "iv_term_gated": (("short_ticker", _REF.format("short_ticker")),
                      ("long_ticker", _REF.format("long_ticker"))),
    "iv_shock": (("iv_ticker", _REF.format("iv_ticker")),),
}
INPUTS: dict[str, tuple[str, str]] = {
    "vrp_conditioned": ("EXOGENOUS: the CBOE implied-vol index named by `iv_ticker` (public, a "
                        "crowding-checked conditioner, not a moat) read as of each signal bar "
                        "with a D+1 00:00 UTC lag, minus this broker's realised vol from the "
                        "cell's own bars; plus the base cell's own inputs -- not price-only",
                        "data/vol_archive/reference/<iv_ticker>.json"),
    "iv_term_gated": ("EXOGENOUS: the implied-vol term ratio `short_ticker`/`long_ticker` on a "
                      "contemporaneous CBOE curve, read as of each signal bar with a D+1 00:00 "
                      "UTC lag; plus the base cell's own inputs -- not price-only",
                      "data/vol_archive/reference/<short_ticker|long_ticker>.json"),
    "iv_shock": ("EXOGENOUS: the day-over-day jump of the CBOE implied-vol index named by "
                 "`iv_ticker`, read as of each decision bar with a D+1 00:00 UTC lag -- not "
                 "price-only", "data/vol_archive/reference/<iv_ticker>.json"),
}
TIMEFRAMES: dict[str, tuple[tuple[str, ...], str]] = dict.fromkeys(
    IMPLIED_VOL_FAMILIES,
    (("H1",), "reads a DAILY implied-vol close against this broker's realised vol from the H1 "
              "store and decides at a broker hour; on a coarser chart the decision hour does "
              "not exist, and on a finer one the daily series would be joined to a clock it "
              "does not carry"))
