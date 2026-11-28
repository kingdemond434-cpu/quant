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

  iv_level_state / iv_level_conditioned   (ported 2026-11-13 from the closed draft #234 onto
      this module's history and lag) The implied-vol LEVEL state: the close's percentile in its
      own trailing year (`iv_pct_1y`) or its 5-session change z-scored on its own year
      (`iv_chg_5d_z`). DIRECT: enter `direction` at the onset of the state, once per episode.
      INDIRECT: a base cell's signals kept only while the state holds. Payer: dealers short gamma
      hedging into a high-vol regime, or long gamma pinning a low-vol one.

`axis_feed` builds the options-implied axis file `world_model.load_inputs` reads (written by the
recorder to `data/lake/axes/options_implied.json`), in the same PIT envelope.

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
    (`searchsorted(..., side="right") - 1` on availability, not on value date), and a value whose
    AVAILABILITY is more than `max_stale_d` days before the decision is ABSENT, not carried
    forward -- with the D+1 lag that is `max_stale_d + 1` days past its VALUE date (default 4 ->
    5 days past the value date).
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


def load_reference(ticker: str, directory: Path | None = None
                   ) -> tuple[np.ndarray, np.ndarray] | None:
    """(value dates as UTC-midnight ns, closes) of `ticker`'s persisted daily history, sorted by
    date, positive finite closes only. None when the file is absent, unreadable or empty."""
    if not ticker:
        return None
    path = (directory or REFERENCE_DIR) / reference_filename(ticker)
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


# ------------------------------------------------------------------- (d) IV level state ---
#: Ported 2026-11-13 from the closed draft #234 (`family_implied_vol.py` /
#: `research/options_implied.py`), onto THIS module's reference history and lag: where implied
#: vol sits in its own trailing year, and how fast it has moved over five sessions. Both are
#: computed on the reference series' OWN date grid, each value from that date and earlier only,
#: and read through the same availability lookup (D+1 00:00 UTC, true-UTC bar instant, stale ->
#: absent) as every other family here.
YEAR = 252
MIN_YEAR = 126
LEVEL_FEATURES: tuple[str, ...] = ("iv_pct_1y", "iv_chg_5d_z")
_OPS: dict[str, Callable[[np.ndarray, float], np.ndarray]] = {
    "ge": lambda v, t: v >= t, "le": lambda v, t: v <= t}


def trailing_percentile(v: np.ndarray, window: int = YEAR, min_obs: int = MIN_YEAR
                        ) -> np.ndarray:
    """Share of the trailing `window` values (this one included) at or below this one; NaN until
    `min_obs` exist. Nothing after the value's own date enters."""
    out = np.full(v.size, np.nan)
    for i in range(v.size):
        if not math.isfinite(v[i]):
            continue
        w = v[max(0, i - window + 1):i + 1]
        w = w[np.isfinite(w)]
        if w.size >= min_obs:
            out[i] = float(np.mean(w <= v[i]))
    return out


def level_features(vals: np.ndarray) -> dict[str, np.ndarray]:
    """`iv_pct_1y`: the close's percentile in its trailing year. `iv_chg_5d_z`: the 5-observation
    change in vol points, z-scored on its own trailing year (this value included, as #234 did;
    still nothing later than the value's date)."""
    s = pd.Series(vals, dtype="float64")
    chg = s.diff(5)
    mu = chg.rolling(YEAR, min_periods=MIN_YEAR).mean()
    sd = chg.rolling(YEAR, min_periods=MIN_YEAR).std(ddof=0)
    z = ((chg - mu) / sd.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    return {"iv_pct_1y": trailing_percentile(np.asarray(vals, dtype="float64")),
            "iv_chg_5d_z": z.to_numpy()}


def level_state(iv_ticker: str, feature: str, op: str, threshold: float, at_ns: np.ndarray,
                *, max_stale_d: float = 4.0) -> np.ndarray | None:
    """Per instant: did `feature op threshold` hold on the newest value KNOWABLE then? False
    where nothing is knowable or it is stale; None when the state cannot be measured at all."""
    fn = _OPS.get(str(op))
    if fn is None or feature not in LEVEL_FEATURES:
        return None
    ref = load_reference(iv_ticker)
    if ref is None:
        return None
    dates, vals = ref
    feat = level_features(vals)[feature]
    j = asof_index(available_ns(dates), at_ns, max_stale_d=max_stale_d)
    v = np.where(j >= 0, feat[np.where(j >= 0, j, 0)], np.nan)
    with np.errstate(invalid="ignore"):
        return np.isfinite(v) & fn(v, float(threshold))


def family_iv_level_state(
    df: pd.DataFrame,
    *,
    iv_ticker: str,
    feature: str,
    op: str,
    threshold: float,
    direction: int = 1,
    ttl_bars: int = 24,
    max_stale_d: float = 4.0,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
) -> list[Signal]:
    """DIRECT: one `direction` entry per EPISODE, on the first bar at which the implied-vol state
    becomes true (the newest knowable value enters it after a bar at which it did not hold)."""
    if int(direction) not in (1, -1) or int(ttl_bars) < 1 or df is None or len(df) == 0:
        return []
    d = _h1(df)
    if len(d) <= int(atr_n) + 1:
        return []
    at = decision_utc_ns(d.index)
    if at is None:
        return []
    mask = level_state(iv_ticker, feature, op, threshold, at, max_stale_d=max_stale_d)
    if mask is None or not mask.any():
        return []
    from mt5desk.families_specialist import _signal
    onset = np.flatnonzero(mask & ~np.r_[False, mask[:-1]])
    atr = _atr(d, int(atr_n)).to_numpy()
    out: list[Signal] = []
    for i in onset:
        if i < int(atr_n) or i >= len(d) - 1:
            continue
        s = _signal(d, int(i), int(direction), atr, stop_atr=stop_atr, rr=rr,
                    ttl_bars=int(ttl_bars), tag=f"iv_level_state:{feature}:{op}:{iv_ticker}")
        if s is not None:
            out.append(s)
    return out


def family_iv_level_conditioned(
    df: pd.DataFrame,
    *,
    base_family: str,
    iv_ticker: str,
    feature: str,
    op: str,
    threshold: float,
    base_params: dict[str, Any] | None = None,
    symbol: str = "",
    max_stale_d: float = 4.0,
) -> list[Signal]:
    """INDIRECT: `base_family`'s own signals kept only while the implied-vol state holds at the
    signal bar. The un-conditioned base is the control arm."""
    got = _operator_base(df, base_family, base_params, symbol)
    if got is None:
        return []
    _d, sigs, at = got
    mask = level_state(iv_ticker, feature, op, threshold, at, max_stale_d=max_stale_d)
    if mask is None:
        return []
    return [s for s, k in zip(sigs, mask, strict=True) if k]


# ------------------------------------------------------------------ the world-model feed ---
#: Points per series handed to the representation factory (as #234: four years is enough for
#: the forge's 260-observation windows and keeps the file small), and the fewest worth a series.
FORGE_POINTS = 1040
FORGE_MIN_POINTS = 24
#: The VIX curve ratios fed beside the levels; the forge mints its own z / rank / diff, so the
#: derived percentile and change-z are NOT fed (they would be its own transforms twice).
FORGE_TERM: tuple[tuple[str, str, str], ...] = (("term_9d_30d", "^VIX9D", "^VIX"),
                                                ("term_30d_3m", "^VIX", "^VIX3M"))


def _iso_day(ns: int) -> str:
    return pd.Timestamp(int(ns), tz="UTC").date().isoformat()


def _points(dates: np.ndarray, vals: np.ndarray) -> list[dict[str, Any]]:
    """The lake's PIT envelope per point: `available_time` is the PUBLICATION bound (D+1 00:00
    UTC, `available_ns`); `world_model._points_from_rows` adds its own CLOCK_PAD_H on read, so
    the forge sees a value no earlier than the families do."""
    ok = np.isfinite(vals)
    dates, vals = dates[ok][-FORGE_POINTS:], vals[ok][-FORGE_POINTS:]
    avail = available_ns(dates)
    return [{"available_time": pd.Timestamp(int(a), tz="UTC").isoformat(), "d": _iso_day(int(t)),
             "v": round(float(v), 6), "vintage": "reference"}
            for t, a, v in zip(dates, avail, vals, strict=True)]


def axis_feed(mapped: dict[str, str], *, reference_dir: Path | None = None,
              universe_dir: Path | None = None) -> dict[str, Any]:
    """The options-implied axis document `world_model.load_inputs` reads (`series[name].points`).

    `mapped` is {MT5 symbol: IV ticker}. Per symbol: `iv_level`, and `vrp` (IV minus this
    broker's 21-day realised through the SAME broker date, which closes before D+1 00:00 UTC)
    when the symbol's H1 bars are on this host; for the VIX curve, the two contemporaneous term
    ratios. A series that cannot be built is named in `unmeasured`, never zero-filled."""
    series: dict[str, Any] = {}
    unmeasured: dict[str, str] = {}
    for sym, ticker in sorted(mapped.items()):
        ref = load_reference(ticker, reference_dir)
        if ref is None:
            unmeasured[f"{sym}.iv_level"] = f"no persisted reference history for {ticker}"
            continue
        dates, vals = ref
        series[f"{sym}.iv_level"] = {"what": f"{ticker} close (CBOE, public) for {sym}",
                                     "points": _points(dates, vals)}
        path = (universe_dir or BASE / "data" / "universe") / f"{sym}_H1.parquet"
        try:
            bars = _h1(pd.read_parquet(path)) if path.exists() else None
        except Exception:
            bars = None
        if bars is None or len(bars) == 0:
            unmeasured[f"{sym}.vrp"] = f"no {sym}_H1.parquet on this host"
            continue
        days, _last, rv = daily_realised_vol(bars)
        rv_on = pd.Series(rv, index=days).reindex(dates).to_numpy()
        series[f"{sym}.vrp"] = {"what": f"{ticker} minus this broker's 21d realised on {sym}",
                                "points": _points(dates, vals - rv_on)}
    for name, short, long_ in FORGE_TERM:
        a, b = load_reference(short, reference_dir), load_reference(long_, reference_dir)
        if a is None or b is None:
            unmeasured[f"VIX.{name}"] = f"{short} or {long_} has no persisted history"
            continue
        common, ia, ib = np.intersect1d(a[0], b[0], assume_unique=True, return_indices=True)
        series[f"VIX.{name}"] = {"what": f"{short}/{long_} on dates both are quoted",
                                 "points": _points(common, a[1][ia] / b[1][ib])}
    series = {k: v for k, v in series.items() if len(v["points"]) >= FORGE_MIN_POINTS}
    return {"id": "options_implied", "axis": "options_implied",
            "at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
            "source": "recorders/vol_archive.py reference history via "
                      "mt5desk/families_implied_vol.axis_feed",
            "shape": "series[name].points of available_time (publication bound), d, v",
            "clock": ("available_time = value date + 1 day 00:00 UTC; world_model adds "
                      "CLOCK_PAD_H on read"),
            "public_series": True,
            "caveat": "public CBOE history: a crowding-checked input, not a moat",
            "series": series, "unmeasured": unmeasured}


# ---------------------------------------------------------------------------- registration ---
#: Merged into `families_specialist`'s tables (and from there into ORTHOGONAL_FAMILIES,
#: FAMILY_INPUTS and FAMILY_TIMEFRAMES by `families_orthogonal`), so the sealed gauntlet resolves
#: them through its ordinary orthogonal lookup with no input branch.
IMPLIED_VOL_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "vrp_conditioned": family_vrp_conditioned,
    "iv_term_gated": family_iv_term_gated,
    "iv_shock": family_iv_shock,
    "iv_level_state": family_iv_level_state,
    "iv_level_conditioned": family_iv_level_conditioned,
}
#: The two operators: like `entry_conditioned`, never wrapped by another operator.
OPERATORS = frozenset({"vrp_conditioned", "iv_term_gated", "iv_level_conditioned"})

_REF = "data/vol_archive/reference/<{}>.json (CBOE daily close, usable from D+1 00:00 UTC)"
INFORMATION_CLASS: dict[str, str] = dict.fromkeys(IMPLIED_VOL_FAMILIES, "exogenous")
FOREIGN_SERIES: dict[str, tuple[tuple[str | None, str], ...]] = {
    "vrp_conditioned": (("iv_ticker", _REF.format("iv_ticker")),),
    "iv_term_gated": (("short_ticker", _REF.format("short_ticker")),
                      ("long_ticker", _REF.format("long_ticker"))),
    "iv_shock": (("iv_ticker", _REF.format("iv_ticker")),),
    "iv_level_state": (("iv_ticker", _REF.format("iv_ticker")),),
    "iv_level_conditioned": (("iv_ticker", _REF.format("iv_ticker")),),
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
    "iv_level_state": ("EXOGENOUS: the trailing-year percentile or 5-day change z of the CBOE "
                       "implied-vol index named by `iv_ticker`, read as of each bar with a D+1 "
                       "00:00 UTC lag; enters at the state's onset -- not price-only",
                       "data/vol_archive/reference/<iv_ticker>.json"),
    "iv_level_conditioned": ("EXOGENOUS: the same implied-vol level state as `iv_level_state`, "
                             "as a filter on the base cell's own signals; plus the base cell's "
                             "own inputs -- not price-only",
                             "data/vol_archive/reference/<iv_ticker>.json"),
}
#: Only the event family is held to H1: it decides once a day at a broker HOUR, which does not
#: exist on a four-hour or daily chart. The two OPERATORS run on whatever chart their base cell
#: carries -- the implied value is read at the signal's true UTC instant and the realised leg is
#: built from the chart's own last bar per broker date, which is the same daily close on every
#: rung of the ladder -- so restricting them would narrow the ladder for no reason.
TIMEFRAMES: dict[str, tuple[tuple[str, ...], str]] = {
    "iv_shock": (("H1",), "decides once a day at a broker decision HOUR against a DAILY "
                          "implied-vol close; on a four-hour or daily chart the decision hour "
                          "does not exist, and below the hour it would be one daily fact joined "
                          "to a finer clock than it carries"),
    "iv_level_state": (("H1",), "its hold `ttl_bars` is declared in H1 bars (a day at 24); on any "
                                "other chart the same number would be a different holding "
                                "period under the same identity"),
}
