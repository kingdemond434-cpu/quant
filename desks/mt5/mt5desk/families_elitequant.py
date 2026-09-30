"""FIVE MECHANISMS THE DESK COULD NOT EXPRESS, ABSORBED FROM THE ELITEQUANT MAP (2026-09-30).

The principal asked for github.com/EliteQuant/EliteQuant to be mined deep and wide. It is a
curated list (Apache-2.0) of ~200 platforms, libraries, models, data sources and blogs. Every
link was checked against this repository (the gap table is in
`/mnt/project-files/reports/elitequant_mining_2026-09-30.md`); most of what it points at the desk
already holds -- Carver's forecast scaling and FDM/IDM (`libs/portfolio/forecast.py`), triple
barrier labels, CPCV, deflated Sharpe, PSR, SPA, walk-forward, COT, LBMA, GARCH, Hurst, HMMs,
order-flow imbalance, TSMOM. These five were ABSENT: no family, no feature, no grep hit. Each is
reimplemented here from the published idea; no code from the linked repositories is copied
(several are GPL).

    ffd_reversion      de Prado, "Advances in Financial Machine Learning" ch.5 (the BlackArbs
                       Adv_Fin_ML_Exercises link): fractionally differentiated log price keeps
                       the memory an integer difference throws away and is still stationary, so
                       its extremes are a level-with-memory claim no return z-score can make.
    hl_spread_shock    Corwin & Schultz (2012) high-low spread estimator from OHLC alone (the
                       microstructure blogs on the list: tr8dr, Kinlay). A spike in the implied
                       spread marks a liquidity shock; returns printed while liquidity evaporated
                       reverse as it returns (Nagel 2012). Works on the whole bar history, where
                       the tick tape `spread_state` needs does not exist.
    sadf_explosive     Phillips, Shi & Yu (2015) backward sup-ADF (de Prado ch.17): an explosive
                       root is a bubble, not a trend. `ride` follows the explosive drift while
                       BSADF is above its critical value; `burst` fades it the bar the root
                       collapses back below -- the collapse a trend family is long into.
    carver_accel       Carver's pysystemtrade `accel` rule (Investment Idiocy): the CHANGE in a
                       vol-normalised EWMAC over its own fast span. It turns before the trend it
                       measures does, which is why it fails on different days from TSMOM.
    skew_premium       Carver's `skew` rule: realised negative skew is a risk premium (the payer
                       is whoever must buy crash insurance); long when an instrument's own recent
                       skew is abnormally negative against its history, short the mirror.

All five are PRICE ONLY and return the engine's `Signal`, so they reach the ten gates through
`families_orthogonal.ORTHOGONAL_FAMILIES` like every other family: the sweep enumerates them,
admission authorises them, the gauntlet judges them and the forward engine clocks them. Signals
use bars up to and including bar i; the engine enters at bar i+1's open.

PARAM_GRID is what `research/elitequant_breadth.py` seeds per hypothesis-lane symbol, and CULTURE
is each mechanism's provenance in the `libs/research/cell_culture.py` schema.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.families import Signal, _atr, _h1, bars_per_day


# --------------------------------------------------------------------------- shared helpers ---
def _signal(d: pd.DataFrame, i: int, side: int, atr: np.ndarray, *, stop_atr: float, rr: float,
            ttl_bars: int, tag: str) -> Signal | None:
    a = float(atr[i])
    px = float(d["close"].iloc[i])
    if not (np.isfinite(a) and a > 0 and np.isfinite(px) and px > 0):
        return None
    return Signal(time=d.index[i], side=int(side), stop=px - side * stop_atr * a,
                  target=px + side * stop_atr * a * rr, ttl_bars=int(ttl_bars), tag=tag)


def _crossings(z: np.ndarray, thresh: float) -> np.ndarray:
    """+1 where z crosses up through +thresh, -1 where it crosses down through -thresh."""
    prev = np.concatenate(([np.nan], z[:-1]))
    up = (z >= thresh) & (prev < thresh)
    dn = (z <= -thresh) & (prev > -thresh)
    return up.astype(int) - dn.astype(int)


def _daily(d: pd.DataFrame) -> tuple[pd.Series, list[int]]:
    """Daily closes derived from the bars, and for each day the bar index of its LAST bar.

    A daily decision is taken on the day's last bar, so the engine enters at the next day's first
    bar -- the same clock `multi_speed_trend` uses, without its per-signal reindexing."""
    close = d["close"].astype(float)
    dates = pd.Index(d.index.date)
    last = np.flatnonzero(np.r_[dates[1:] != dates[:-1], True])
    daily = pd.Series(close.to_numpy()[last], index=dates[last])
    return daily, [int(k) for k in last]


# ----------------------------------------------------------------------------- 1. FFD --------
def ffd_weights(d: float, *, thresh: float = 1e-4, max_len: int = 500) -> np.ndarray:
    """Fixed-width-window fractional-difference weights w_0..w_K, |w_K| >= thresh."""
    w = [1.0]
    k = 1
    while k < max_len:
        nxt = -w[-1] * (d - k + 1) / k
        if abs(nxt) < thresh:
            break
        w.append(nxt)
        k += 1
    return np.asarray(w, dtype=float)


def frac_diff(x: np.ndarray, d: float, *, thresh: float = 1e-4, max_len: int = 500) -> np.ndarray:
    """Causal FFD of `x`: out[t] = sum_k w_k x[t-k]; NaN until the window is full."""
    w = ffd_weights(d, thresh=thresh, max_len=max_len)
    out = np.full(x.size, np.nan)
    if x.size >= w.size:
        out[w.size - 1:] = np.convolve(x, w, mode="valid")
    return out


def family_ffd_reversion(df: pd.DataFrame, *, d: float = 0.4, z_window: int = 240,
                         entry_z: float = 2.0, mode: str = "fade", atr_n: int = 20,
                         stop_atr: float = 2.0, rr: float = 1.5, ttl_bars: int = 24) -> list[Signal]:
    """Trade the FFD log-price z-score as it crosses +-entry_z (fade, or follow the break)."""
    if not (0.0 < d < 1.0) or mode not in ("fade", "follow"):
        return []
    h = _h1(df)
    if len(h) < z_window + 600:
        return []
    x = frac_diff(np.log(h["close"].astype(float).to_numpy()), d)
    s = pd.Series(x)
    mu = s.rolling(z_window, min_periods=z_window).mean().to_numpy()
    sd = s.rolling(z_window, min_periods=z_window).std(ddof=1).to_numpy()
    z = (x - mu) / np.where(sd > 0, sd, np.nan)
    cross = _crossings(z, entry_z)
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    for i in np.flatnonzero(cross):
        if i >= len(h) - 1:
            continue
        side = -int(cross[i]) if mode == "fade" else int(cross[i])
        sig = _signal(h, int(i), side, atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                      tag=f"ffd_reversion:{mode}:d{d:g}")
        if sig:
            out.append(sig)
    return out


# ------------------------------------------------------------------ 2. Corwin-Schultz spread --
_CS_K = 3.0 - 2.0 * np.sqrt(2.0)


def corwin_schultz_spread(high: np.ndarray, low: np.ndarray) -> np.ndarray:
    """Two-bar Corwin-Schultz spread estimate (fraction of price), causal: bar t uses t-1 and t.

    Negative estimates (noise when the true spread is small) are set to 0, as the paper does."""
    hl = np.log(np.where(low > 0, high / low, np.nan)) ** 2
    beta = hl + np.concatenate(([np.nan], hl[:-1]))
    h2 = np.maximum(high, np.concatenate(([np.nan], high[:-1])))
    l2 = np.minimum(low, np.concatenate(([np.nan], low[:-1])))
    gamma = np.log(np.where(l2 > 0, h2 / l2, np.nan)) ** 2
    with np.errstate(invalid="ignore"):
        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _CS_K - np.sqrt(gamma / _CS_K)
        spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    return np.where(np.isfinite(spread), np.maximum(spread, 0.0), np.nan)


def family_hl_spread_shock(df: pd.DataFrame, *, base_window: int = 120, shock_k: float = 2.5,
                           move_bars: int = 3, move_atr: float = 1.0, mode: str = "fade",
                           atr_n: int = 20, stop_atr: float = 1.5, rr: float = 1.5,
                           ttl_bars: int = 12) -> list[Signal]:
    """Fade (or follow) the move printed while the implied spread spiked above its baseline."""
    if mode not in ("fade", "follow") or shock_k <= 1.0:
        return []
    h = _h1(df)
    if len(h) < base_window + 50:
        return []
    hi = h["high"].astype(float).to_numpy()
    lo = h["low"].astype(float).to_numpy()
    close = h["close"].astype(float).to_numpy()
    # Smooth over three bars: a single-pair estimate is too noisy to call a shock.
    spread = pd.Series(corwin_schultz_spread(hi, lo)).rolling(3, min_periods=2).mean()
    base = spread.rolling(base_window, min_periods=base_window // 2).median().shift(1)
    ratio = (spread / base.where(base > 0)).to_numpy()
    atr = _atr(h, atr_n).to_numpy()
    move = close - np.concatenate((np.full(move_bars, np.nan), close[:-move_bars]))
    fire = (ratio >= shock_k) & (np.abs(move) >= move_atr * atr)
    out: list[Signal] = []
    last = -10 ** 9
    for i in np.flatnonzero(fire):
        if i >= len(h) - 1 or i - last < move_bars:
            continue
        side = -int(np.sign(move[i])) if mode == "fade" else int(np.sign(move[i]))
        if side == 0:
            continue
        sig = _signal(h, int(i), side, atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                      tag=f"hl_spread_shock:{mode}")
        if sig:
            out.append(sig)
            last = int(i)
    return out


# ------------------------------------------------------------------------ 3. backward SADF ---
def bsadf(y: np.ndarray, *, window: int = 240, min_window: int = 40, starts: int = 8,
          step: int = 1) -> np.ndarray:
    """Backward sup-ADF: at t, the max ADF t-stat of dy = a + b*y_{-1} over windows ending at t
    whose start lies on a `starts`-point grid in [t-window, t-min_window]. No augmentation lags
    (speed; the statistic is used as a regime reading, not a p-value). O(starts) per bar through
    cumulative sums, so a 50k-bar series costs milliseconds."""
    n = y.size
    out = np.full(n, np.nan)
    if n < window + 2:
        return out
    x = y[:-1]
    dy = np.diff(y)
    c = [np.concatenate(([0.0], np.cumsum(v))) for v in (np.ones_like(x), x, dy, x * x, x * dy,
                                                          dy * dy)]
    ends = np.arange(window, n - 1 + 1, max(1, step))       # regression rows end at index e-1
    offsets = np.unique(np.linspace(min_window, window, starts).astype(int))
    best = np.full(ends.size, -np.inf)
    for off in offsets:
        s = ends - off
        cnt, sx, sy, sxx, sxy, syy = (cc[ends] - cc[s] for cc in c)
        with np.errstate(divide="ignore", invalid="ignore"):
            vx = sxx - sx * sx / cnt
            b = (sxy - sx * sy / cnt) / vx
            a = (sy - b * sx) / cnt
            rss = syy - 2 * a * sy - 2 * b * sxy + cnt * a * a + 2 * a * b * sx + b * b * sxx
            se = np.sqrt(np.maximum(rss, 0.0) / (cnt - 2) / vx)
            t = b / se
        best = np.where(np.isfinite(t) & (t > best), t, best)
    # regression rows 0..e-1 use y up to index e, i.e. bar e (the dy row e-1 is y[e]-y[e-1]).
    out[ends] = np.where(np.isfinite(best), best, np.nan)
    return out


def family_sadf_explosive(df: pd.DataFrame, *, window: int = 240, cv: float = 1.5,
                          mode: str = "burst", drift_bars: int = 24, atr_n: int = 20,
                          stop_atr: float = 2.0, rr: float = 2.0,
                          ttl_bars: int = 24) -> list[Signal]:
    """`ride`: follow the drift the bar BSADF crosses above cv. `burst`: fade the drift the bar
    it falls back below cv after having been above -- the explosive root collapsing."""
    if mode not in ("ride", "burst"):
        return []
    h = _h1(df)
    if len(h) < window + 100:
        return []
    close = h["close"].astype(float).to_numpy()
    stat = bsadf(np.log(close), window=window, min_window=max(20, window // 6))
    prev = np.concatenate(([np.nan], stat[:-1]))
    fire = (stat > cv) & (prev <= cv) if mode == "ride" else (stat <= cv) & (prev > cv)
    drift = close - np.concatenate((np.full(drift_bars, np.nan), close[:-drift_bars]))
    atr = _atr(h, atr_n).to_numpy()
    out: list[Signal] = []
    for i in np.flatnonzero(fire):
        if i >= len(h) - 1 or not np.isfinite(drift[i]) or drift[i] == 0:
            continue
        side = int(np.sign(drift[i])) * (1 if mode == "ride" else -1)
        sig = _signal(h, int(i), side, atr, stop_atr=stop_atr, rr=rr, ttl_bars=ttl_bars,
                      tag=f"sadf_explosive:{mode}")
        if sig:
            out.append(sig)
    return out


# ------------------------------------------------------------------------ 4. Carver accel ----
def _daily_entries(h: pd.DataFrame, forecast: np.ndarray, last_bar: list[int], thresh: float,
                   hold_days: int, atr: np.ndarray, *, stop_atr: float, rr: float,
                   tag: str) -> list[Signal]:
    """One entry per `hold_days` when |forecast| >= thresh, decided on the day's last bar."""
    out: list[Signal] = []
    last_i = -10 ** 9
    bpd = bars_per_day(h)
    for k, f in enumerate(forecast):
        if not np.isfinite(f) or abs(f) < thresh or k - last_i < hold_days:
            continue
        i = last_bar[k]
        if i >= len(h) - 1:
            continue
        sig = _signal(h, i, 1 if f > 0 else -1, atr, stop_atr=stop_atr, rr=rr,
                      ttl_bars=hold_days * bpd, tag=tag)
        if sig:
            out.append(sig)
            last_i = k
    return out


def family_carver_accel(df: pd.DataFrame, *, fast: int = 16, thresh: float = 0.5,
                        vol_window: int = 25, hold_days: int = 3, atr_n: int = 20,
                        stop_atr: float = 2.5, rr: float = 2.0) -> list[Signal]:
    """accel_t = ewmac_t - ewmac_{t-fast}, ewmac = (EMA_fast - EMA_4fast) / (price * daily vol),
    both on daily closes; the forecast is accel scaled by its own trailing abs-mean."""
    h = _h1(df)
    daily, last_bar = _daily(h)
    if daily.size < 4 * fast + vol_window + 120:
        return []
    p = daily.to_numpy(dtype=float)
    vol = pd.Series(np.diff(p, prepend=np.nan) / p).ewm(span=vol_window).std().to_numpy()
    s = pd.Series(p)
    ewmac = ((s.ewm(span=fast).mean() - s.ewm(span=4 * fast).mean()).to_numpy()
             / np.where(vol > 0, p * vol, np.nan))
    accel = ewmac - np.concatenate((np.full(fast, np.nan), ewmac[:-fast]))
    scale = pd.Series(np.abs(accel)).rolling(250, min_periods=60).mean().shift(1).to_numpy()
    forecast = accel / np.where(scale > 0, scale, np.nan)
    forecast[: 4 * fast] = np.nan
    return _daily_entries(h, forecast, last_bar, thresh, hold_days, _atr(h, atr_n).to_numpy(),
                          stop_atr=stop_atr, rr=rr, tag=f"carver_accel:{fast}")


# ------------------------------------------------------------------------- 5. skew premium ---
def family_skew_premium(df: pd.DataFrame, *, lookback: int = 60, history: int = 250,
                        thresh: float = 1.0, hold_days: int = 5, atr_n: int = 20,
                        stop_atr: float = 2.5, rr: float = 2.0) -> list[Signal]:
    """Long when the trailing `lookback`-day skew is `thresh` sd BELOW its own `history` mean
    (the crash-insurance premium is richest), short when it is that far above."""
    h = _h1(df)
    daily, last_bar = _daily(h)
    if daily.size < lookback + history + 20:
        return []
    r = pd.Series(np.diff(np.log(daily.to_numpy(dtype=float)), prepend=np.nan))
    skew = r.rolling(lookback, min_periods=lookback).skew()
    mu = skew.rolling(history, min_periods=history // 2).mean().shift(1)
    sd = skew.rolling(history, min_periods=history // 2).std(ddof=1).shift(1)
    forecast = (-(skew - mu) / sd.where(sd > 0)).to_numpy()
    return _daily_entries(h, forecast, last_bar, thresh, hold_days, _atr(h, atr_n).to_numpy(),
                          stop_atr=stop_atr, rr=rr, tag=f"skew_premium:{lookback}")


ELITEQUANT_FAMILIES = {
    "ffd_reversion": family_ffd_reversion,
    "hl_spread_shock": family_hl_spread_shock,
    "sadf_explosive": family_sadf_explosive,
    "carver_accel": family_carver_accel,
    "skew_premium": family_skew_premium,
}

#: What `research/elitequant_breadth.py` seeds per symbol. Small on purpose: every cell is a
#: trial the deflated-Sharpe charge divides the error budget across.
PARAM_GRID: dict[str, dict[str, list]] = {
    "ffd_reversion": {"d": [0.3, 0.5], "entry_z": [2.0, 2.5], "mode": ["fade", "follow"]},
    "hl_spread_shock": {"shock_k": [2.0, 3.0], "move_atr": [1.0, 1.5], "mode": ["fade", "follow"]},
    "sadf_explosive": {"window": [120, 240], "cv": [1.0, 1.5], "mode": ["ride", "burst"]},
    "carver_accel": {"fast": [8, 16, 32], "thresh": [0.5, 1.0]},
    "skew_premium": {"lookback": [60, 120], "thresh": [0.75, 1.25]},
}

#: Provenance in the `libs/research/cell_culture.py` schema, declared per mechanism. These are
#: Western-canon mechanisms; the crowding prior says how much of the English literature trades
#: them on retail CFD venues, which is the orthogonality claim the Tier S test can falsify.
CULTURE: dict[str, dict[str, str]] = {
    "ffd_reversion": {
        "source_culture": "US/en", "participant_structure": "institutional",
        "crowding_prior": "medium",
        "failure_mode_hypothesis": ("fails when a level re-rates for good (a policy regime "
                                    "change), not when a trend reverses")},
    "hl_spread_shock": {
        "source_culture": "US/en", "participant_structure": "broker_specific",
        "crowding_prior": "low",
        "failure_mode_hypothesis": ("fails when the shock is informed flow (a news repricing), "
                                    "which a range or trend family does not distinguish")},
    "sadf_explosive": {
        "source_culture": "GLOBAL", "participant_structure": "retail_heavy",
        "crowding_prior": "low",
        "failure_mode_hypothesis": ("fails when an explosive run is fundamental (a squeeze that "
                                    "never collapses); earns on bubble collapses trend is long")},
    "carver_accel": {
        "source_culture": "GB/en", "participant_structure": "institutional",
        "crowding_prior": "medium",
        "failure_mode_hypothesis": ("turns before the trend it measures, so it loses in slow "
                                    "grinding trends where TSMOM earns, and vice versa")},
    "skew_premium": {
        "source_culture": "GB/en", "participant_structure": "institutional",
        "crowding_prior": "medium",
        "failure_mode_hypothesis": ("pays for bearing crash risk, so it loses in the crash "
                                    "itself -- the regime where trend and carry diverge")},
}
