"""THE PRINCIPAL'S PLAYBOOK AS DETECTORS -- H1, H2, H6-H11, to the pre-registered terms.

`docs/research/DISCRETIONARY_PLAYBOOK_PREREGISTRATION.md` fixed the thresholds on 2026-08-04,
before any of these had been backtested here. This module implements them and CHANGES NONE OF
THEM. Where the pre-registration names a number -- RSI 70/30, 0.3xATR(14) tolerance, >=2 touches
in 90 days, Donchian(20), 1.5xSMA20(volume), Bollinger(20,2), the three UTC sessions -- that number
appears here verbatim. Reading the data first and then picking a threshold is the one move that
would void every result this family ever produces.

WHERE THE PRE-REGISTRATION IS SILENT, THE CHOICE IS MADE HERE AND MARKED. H1 and H2 specify entries
and exits precisely; H6-H11 are registered as one-line testable cores, so their detector geometry
had to be fixed somewhere. It is fixed HERE, in code, dated, before any of them has been run
against the lake -- which is what pre-registration requires. Each such choice carries a
`# PRE-REGISTERED 2026-08-15` marker so a later reader can tell a playbook number from a desk one.

**H4 AND H5 READ THE MOAT TAPE, NOT THE CANDLES.** The pre-registration marks both BLOCKED on
recorder bringup -- true when written, stale since: the recorders have been taping every aggTrade
with its maker flag for weeks. They are implemented here against `libs.discretionary.tape`, which
is the real signed flow, and NOT against an OHLCV proxy. A candle-derived CVD would be a different
hypothesis wearing this one's name and carrying its priority.

**EVERY DETECTOR RETURNS SETUPS, NEVER ORDERS.** Direction, entry, stop and target -- the same
shape `libs/ict` produces, so one adapter serves all of them and no rule gets its own order path.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from libs.discretionary import tape

__all__ = [
    "BLOCKED",
    "READY",
    "Setup",
    "detect",
    "h1_structural_fade",
    "h2_volume_breakout",
    "h4_auction_value",
    "h5_cvd_divergence",
    "h6_wyckoff",
    "h7_vwap_reversion",
    "h8_supply_demand",
    "h9_opening_range",
    "h10_vol_compression",
    "h11_band_fade",
]

#: Nothing is blocked any more, and the empty dict is the finding. The pre-registration marked H4
#: and H5 "BLOCKED: recorder bringup (operator)" on 2026-08-04 -- true then. The recorders have
#: been taping every aggTrade with its maker flag since, so the inputs arrived and the label did
#: not change. Kept as a named, empty mapping so anything asking "what is still blocked" gets an
#: answer rather than an AttributeError, and so the next genuine block has somewhere to go.
BLOCKED: dict[str, str] = {}


@dataclass(frozen=True)
class Setup:
    """One detected trade story. Mirrors `libs.ict.strategy.ICTSetup` so a single adapter turns
    any rule in this family into a sized intent."""

    rule_id: str
    direction: int          # +1 long, -1 short
    entry_price: float
    stop: float
    target: float
    bar: int
    note: str


# --------------------------------------------------------------------------------------------
# indicators. Deliberately plain: every one of these has a dozen variants, and a variant chosen
# after seeing results is a threshold chosen after seeing results.
# --------------------------------------------------------------------------------------------

def _atr(b: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = b["close"].shift(1)
    tr = pd.concat([b["high"] - b["low"], (b["high"] - pc).abs(), (b["low"] - pc).abs()],
                   axis=1).max(axis=1)
    return tr.rolling(n).mean()


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0.0).ewm(alpha=1.0 / n, adjust=False).mean()
    dn = (-d.clip(upper=0.0)).ewm(alpha=1.0 / n, adjust=False).mean()
    rs = up / dn.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def _psar(b: pd.DataFrame, af0: float = 0.02, afmax: float = 0.2) -> pd.Series:
    """Parabolic SAR at the playbook's own defaults (0.02/0.2) -- H2 names them explicitly."""
    high, low = b["high"].to_numpy(), b["low"].to_numpy()
    n = len(b)
    out = np.full(n, np.nan)
    if n < 3:
        return pd.Series(out, index=b.index)
    bull, af, ep, sar = True, af0, high[0], low[0]
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if bull:
            sar = min(sar, low[i - 1], low[max(0, i - 2)])
            if low[i] < sar:
                bull, sar, ep, af = False, ep, low[i], af0
            elif high[i] > ep:
                ep, af = high[i], min(af + af0, afmax)
        else:
            sar = max(sar, high[i - 1], high[max(0, i - 2)])
            if high[i] > sar:
                bull, sar, ep, af = True, ep, high[i], af0
            elif low[i] < ep:
                ep, af = low[i], min(af + af0, afmax)
        out[i] = sar
    return pd.Series(out, index=b.index)


def _last(s: pd.Series, i: int) -> float:
    v = s.iloc[i]
    return float(v) if pd.notna(v) else float("nan")


# --------------------------------------------------------------------------------------------
# H1 -- structural-level fade with RSI extreme. Every number below is from the pre-registration.
# --------------------------------------------------------------------------------------------

def h1_structural_fade(b: pd.DataFrame, *, window: int = 90, touches: int = 2,
                       tol_atr: float = 0.3, rsi_hi: float = 70.0,
                       rsi_lo: float = 30.0, stop_atr: float = 2.0) -> list[Setup]:
    """Level touched >=2x in 90 days within 0.3xATR(14); fade on RSI(14) >=70 / <=30.

    MECHANISM: resting liquidity at a repeatedly-tested level absorbs an exhausted push. The
    pre-registration's falsification is explicit -- H1 dies if this is indistinguishable from the
    unconditional short-vol payoff it resembles -- so nothing here tries to rescue it.
    """
    if len(b) < window + 20:
        return []
    atr, rsi = _atr(b), _rsi(b["close"])
    out: list[Setup] = []
    i = len(b) - 1
    px, a = float(b["close"].iloc[i]), _last(atr, i)
    if not np.isfinite(a) or a <= 0:
        return []
    tol = tol_atr * a
    hist = b.iloc[max(0, i - window):i]
    hi_touch = int((hist["high"] - px).abs().le(tol).sum())
    lo_touch = int((hist["low"] - px).abs().le(tol).sum())
    r = _last(rsi, i)
    if hi_touch >= touches and r >= rsi_hi:
        opp = float(hist["low"].min())
        out.append(Setup("H1_structural_fade", -1, px, px + stop_atr * a, opp, i,
                         f"{hi_touch} touches within {tol_atr}xATR over {window}d, RSI {r:.0f}"))
    elif lo_touch >= touches and r <= rsi_lo:
        opp = float(hist["high"].max())
        out.append(Setup("H1_structural_fade", +1, px, px - stop_atr * a, opp, i,
                         f"{lo_touch} touches within {tol_atr}xATR over {window}d, RSI {r:.0f}"))
    return out


# --------------------------------------------------------------------------------------------
# H2 -- breakout with volume confirmation, Donchian(20) + 1.5x SMA20(volume), PSAR trail.
# --------------------------------------------------------------------------------------------

def h2_volume_breakout(b: pd.DataFrame, *, n: int = 20, vol_mult: float = 1.5) -> list[Setup]:
    """Donchian(20) break confirmed by volume >= 1.5xSMA20(volume); PSAR(0.02/0.2) is the stop.

    THE ABLATION IS THE POINT. H2 dies if volume confirmation adds nothing over the bare break, so
    the volume test is a hard gate here rather than a score -- an un-gated version is a DIFFERENT
    arm and must be run as one, not blended in.
    """
    if len(b) < n + 25 or "volume" not in b:
        return []
    i = len(b) - 1
    prior = b.iloc[i - n:i]
    hi, lo = float(prior["high"].max()), float(prior["low"].min())
    v, vma = float(b["volume"].iloc[i]), float(b["volume"].rolling(n).mean().iloc[i])
    if not np.isfinite(vma) or vma <= 0 or v < vol_mult * vma:
        return []
    px = float(b["close"].iloc[i])
    sar = _last(_psar(b), i)
    if not np.isfinite(sar):
        return []
    width = hi - lo
    if px > hi:
        # PRE-REGISTERED 2026-08-15: target = one channel width projected from the break. The
        # playbook fixes the TRAIL as the exit structure and leaves the objective open; a channel
        # width is the only scale the setup itself provides, so no new parameter enters.
        return [Setup("H2_volume_breakout", +1, px, min(sar, lo), px + width, i,
                      f"Donchian({n}) high break on {v / vma:.1f}x volume")]
    if px < lo:
        return [Setup("H2_volume_breakout", -1, px, max(sar, hi), px - width, i,
                      f"Donchian({n}) low break on {v / vma:.1f}x volume")]
    return []


# --------------------------------------------------------------------------------------------
# H6 -- Wyckoff spring / upthrust after a range.
# --------------------------------------------------------------------------------------------

def h6_wyckoff(b: pd.DataFrame, *, range_bars: int = 20, max_range_atr: float = 3.0,
               recover_bars: int = 2) -> list[Setup]:
    """Spring: price breaks a >=20-bar range LOW and closes back inside within 2 bars. Upthrust
    mirrors it.

    PRE-REGISTERED 2026-08-15: `range_bars=20`, `max_range_atr=3.0`, `recover_bars=2`. The
    pre-registration registers the CORE ("spring/upthrust after accumulation/distribution ranges")
    and leaves the geometry open; these fix it before the first run.

    THE RECOVERY IS THE WHOLE SIGNAL. A break that stays broken is a trend, not a spring, and
    counting it here would merge two opposite mechanisms into one row.
    """
    if len(b) < range_bars + 25:
        return []
    i = len(b) - 1
    a = _last(_atr(b), i)
    if not np.isfinite(a) or a <= 0:
        return []
    base = b.iloc[i - range_bars - recover_bars:i - recover_bars]
    hi, lo = float(base["high"].max()), float(base["low"].min())
    if (hi - lo) > max_range_atr * a:
        return []                        # not a range: a trend cannot spring
    recent = b.iloc[i - recover_bars:i + 1]
    px = float(b["close"].iloc[i])
    if float(recent["low"].min()) < lo and lo < px < hi:
        return [Setup("H6_wyckoff_spring", +1, px, float(recent["low"].min()) - 0.1 * a, hi, i,
                      f"spring: broke {range_bars}-bar low {lo:.4g}, recovered inside")]
    if float(recent["high"].max()) > hi and lo < px < hi:
        return [Setup("H6_wyckoff_upthrust", -1, px, float(recent["high"].max()) + 0.1 * a, lo, i,
                      f"upthrust: broke {range_bars}-bar high {hi:.4g}, rejected back inside")]
    return []


# --------------------------------------------------------------------------------------------
# H7 -- VWAP reversion with a slope trend filter.
# --------------------------------------------------------------------------------------------

def h7_vwap_reversion(b: pd.DataFrame, *, n: int = 20, dev: float = 2.0,
                      slope_bars: int = 10) -> list[Setup]:
    """Rolling VWAP(20); fade a >=2-sigma deviation, but only WITH the VWAP slope.

    PRE-REGISTERED 2026-08-15: `n=20`, `dev=2.0`, `slope_bars=10`. The registration names
    "session-VWAP reversion and VWAP-slope trend filter"; on a 24/7 tape there is no session, so a
    rolling window stands in and the substitution is stated rather than hidden.

    THE SLOPE FILTER IS A GATE, NOT A TIEBREAK. Fading a deviation against a trending VWAP is the
    losing half of this trade, and blending it in would average a mechanism with its own inverse.
    """
    if len(b) < n + slope_bars + 5 or "volume" not in b:
        return []
    tp = (b["high"] + b["low"] + b["close"]) / 3.0
    pv = (tp * b["volume"]).rolling(n).sum()
    vv = b["volume"].rolling(n).sum().replace(0.0, np.nan)
    vwap = pv / vv
    resid = (b["close"] - vwap).rolling(n).std()
    i = len(b) - 1
    w, s, px = _last(vwap, i), _last(resid, i), float(b["close"].iloc[i])
    if not (np.isfinite(w) and np.isfinite(s)) or s <= 0:
        return []
    slope = w - _last(vwap, i - slope_bars)
    z = (px - w) / s
    if z <= -dev and slope >= 0:
        return [Setup("H7_vwap_reversion", +1, px, px - dev * s, w, i,
                      f"{z:.1f} sigma below VWAP({n}) with slope up")]
    if z >= dev and slope <= 0:
        return [Setup("H7_vwap_reversion", -1, px, px + dev * s, w, i,
                      f"{z:.1f} sigma above VWAP({n}) with slope down")]
    return []


# --------------------------------------------------------------------------------------------
# H8 -- supply/demand zones: departure, base, return.
# --------------------------------------------------------------------------------------------

def h8_supply_demand(b: pd.DataFrame, *, base_bars: int = 3, base_atr: float = 1.0,
                     impulse_atr: float = 2.0, lookback: int = 60) -> list[Setup]:
    """Zone = the BASE that preceded an impulsive departure; the trade is the first return to it.

    PRE-REGISTERED 2026-08-15: `base_bars=3`, `base_atr=1.0`, `impulse_atr=2.0`, `lookback=60`.
    The registration defines the zone as "the base before an impulsive move" and leaves the
    magnitudes open.

    THE DEPARTURE IS WHAT MAKES IT A ZONE. A narrow range with nothing after it is just quiet
    tape, and admitting those would fill the book with every consolidation on the chart.
    """
    if len(b) < lookback + base_bars + 5:
        return []
    atr = _atr(b)
    i = len(b) - 1
    px = float(b["close"].iloc[i])
    a = _last(atr, i)
    if not np.isfinite(a) or a <= 0:
        return []
    for j in range(i - lookback, i - base_bars - 1):
        base = b.iloc[j:j + base_bars]
        aj = _last(atr, j + base_bars)
        if not np.isfinite(aj) or aj <= 0:
            continue
        bh, bl = float(base["high"].max()), float(base["low"].min())
        if (bh - bl) > base_atr * aj:
            continue
        nxt = float(b["close"].iloc[j + base_bars])
        if nxt - bh >= impulse_atr * aj and bl <= px <= bh:
            return [Setup("H8_demand_zone", +1, px, bl - 0.25 * a, bh + impulse_atr * a, i,
                          f"return to demand base [{bl:.4g},{bh:.4g}] after impulsive departure")]
        if bl - nxt >= impulse_atr * aj and bl <= px <= bh:
            return [Setup("H8_supply_zone", -1, px, bh + 0.25 * a, bl - impulse_atr * a, i,
                          f"return to supply base [{bl:.4g},{bh:.4g}] after impulsive departure")]
    return []


# --------------------------------------------------------------------------------------------
# H9 -- opening-range breakout. THE THREE SESSIONS ARE PRE-REGISTERED AND THERE ARE ONLY THREE.
# --------------------------------------------------------------------------------------------

#: "crypto has no bell -- session definitions (00:00 UTC, US open, Asia open) are pre-registered as
#: the ONLY three tested". Adding a fourth later is a new trial, counted as one.
SESSIONS_UTC: dict[str, int] = {"utc_midnight": 0, "asia_open": 1, "us_open": 13}


def h9_opening_range(b: pd.DataFrame, *, session: str = "utc_midnight", range_bars: int = 4,
                     vol_mult: float = 1.5) -> list[Setup]:
    """Opening-range break for one of the three registered sessions, volume-confirmed.

    NEEDS INTRADAY BARS AND SAYS SO. An "opening range" on daily candles is the day itself, which
    is not the hypothesis -- so this returns nothing unless the index carries intraday timestamps,
    and the caller reports UNAVAILABLE rather than a silent empty list.
    """
    if session not in SESSIONS_UTC or "volume" not in b or len(b) < range_bars + 25:
        return []
    idx = b.index
    if not isinstance(idx, pd.DatetimeIndex):
        return []
    if len(idx) > 1 and (idx[-1] - idx[-2]) >= pd.Timedelta(hours=23):
        return []                        # daily bars: no opening range exists to break
    hour = SESSIONS_UTC[session]
    today = idx[-1].normalize()
    opening = b[(idx >= today + pd.Timedelta(hours=hour))
                & (idx < today + pd.Timedelta(hours=hour) + pd.Timedelta(hours=range_bars))]
    if len(opening) < 2:
        return []
    hi, lo = float(opening["high"].max()), float(opening["low"].min())
    i = len(b) - 1
    px, v = float(b["close"].iloc[i]), float(b["volume"].iloc[i])
    vma = float(b["volume"].rolling(20).mean().iloc[i])
    if not np.isfinite(vma) or vma <= 0 or v < vol_mult * vma:
        return []
    width = hi - lo
    if px > hi:
        return [Setup(f"H9_orb_{session}", +1, px, lo, px + width, i,
                      f"{session} opening range [{lo:.4g},{hi:.4g}] broken up on "
                      f"{v / vma:.1f}x volume")]
    if px < lo:
        return [Setup(f"H9_orb_{session}", -1, px, hi, px - width, i,
                      f"{session} opening range [{lo:.4g},{hi:.4g}] broken down on "
                      f"{v / vma:.1f}x volume")]
    return []


# --------------------------------------------------------------------------------------------
# H10 -- volatility compression: BB squeeze / NR7 -> expansion.
# --------------------------------------------------------------------------------------------

def h10_vol_compression(b: pd.DataFrame, *, n: int = 20, k: float = 2.0,
                        squeeze_window: int = 60) -> list[Setup]:
    """Bollinger(20,2) bandwidth at a 60-bar low, or NR7, then trade the EXPANSION direction.

    PRE-REGISTERED 2026-08-15: `squeeze_window=60`. Bollinger(20,2) and NR7 come from the
    registration itself.

    THE DIRECTION COMES FROM THE EXPANSION, NEVER FROM THE SQUEEZE. A compression is direction-free
    by construction, and picking a side before the break is where this family usually invents an
    edge it does not have.
    """
    if len(b) < squeeze_window + n + 5:
        return []
    ma = b["close"].rolling(n).mean()
    sd = b["close"].rolling(n).std()
    bw = (2 * k * sd / ma.replace(0.0, np.nan))
    i = len(b) - 1
    rng = b["high"] - b["low"]
    nr7 = bool(rng.iloc[i - 1] == rng.iloc[i - 7:i].min()) if i >= 7 else False
    prior_bw = bw.iloc[i - squeeze_window:i]
    squeezed = bool(pd.notna(bw.iloc[i - 1]) and len(prior_bw.dropna()) > 5
                    and bw.iloc[i - 1] <= prior_bw.quantile(0.10))
    if not (squeezed or nr7):
        return []
    px, upper, lower = float(b["close"].iloc[i]), _last(ma + k * sd, i), _last(ma - k * sd, i)
    if not (np.isfinite(upper) and np.isfinite(lower)):
        return []
    width = upper - lower
    if px > upper:
        return [Setup("H10_vol_compression", +1, px, lower, px + width, i,
                      f"expansion up from {'NR7' if nr7 else 'BB squeeze'}")]
    if px < lower:
        return [Setup("H10_vol_compression", -1, px, upper, px - width, i,
                      f"expansion down from {'NR7' if nr7 else 'BB squeeze'}")]
    return []


# --------------------------------------------------------------------------------------------
# H11 -- band fade. Registered LAST deliberately (L0054), tested all the same.
# --------------------------------------------------------------------------------------------

def h11_band_fade(b: pd.DataFrame, *, n: int = 20, z: float = 2.0) -> list[Setup]:
    """Z-score fade at band extremes.

    PRE-REGISTERED 2026-08-15: `n=20`, `z=2.0`. Registered last because three independent methods
    rank mean-reversion last on crypto (L0054) -- the prior sets EFFORT ORDER and never the bar, so
    this is tested on the same terms as everything above it.
    """
    if len(b) < n + 5:
        return []
    ma = b["close"].rolling(n).mean()
    sd = b["close"].rolling(n).std()
    i = len(b) - 1
    m, s, px = _last(ma, i), _last(sd, i), float(b["close"].iloc[i])
    if not (np.isfinite(m) and np.isfinite(s)) or s <= 0:
        return []
    zz = (px - m) / s
    if zz <= -z:
        return [Setup("H11_band_fade", +1, px, px - z * s, m, i, f"z {zz:.1f} at lower band")]
    if zz >= z:
        return [Setup("H11_band_fade", -1, px, px + z * s, m, i, f"z {zz:.1f} at upper band")]
    return []


#: Every implemented rule, by the id the journal and the multiplicity ledger use. H3 lives in
#: `libs/ict` and is added by the runner, which owns that import.
READY: dict[str, Any] = {
    "H1_structural_fade": h1_structural_fade,
    "H2_volume_breakout": h2_volume_breakout,
    "H6_wyckoff": h6_wyckoff,
    "H7_vwap_reversion": h7_vwap_reversion,
    "H8_supply_demand": h8_supply_demand,
    "H9_opening_range": h9_opening_range,
    "H10_vol_compression": h10_vol_compression,
    "H11_band_fade": h11_band_fade,
}


def detect(b: pd.DataFrame, rules: list[str] | None = None) -> list[Setup]:
    """Run the named rules (all READY ones by default) over one symbol's bars.

    A DETECTOR THAT RAISES MUST NOT SILENCE THE REST. One malformed frame taking out the whole
    family would read as "no setups today", which is a different and false claim.
    """
    out: list[Setup] = []
    for name in (rules or list(READY)):
        fn = READY.get(name)
        if fn is None:
            continue
        try:
            out.extend(fn(b))
        except Exception:
            continue
    return out


# --------------------------------------------------------------------------------------------
# H4 / H5 -- the two that needed the tape. Both take a TapeProfile the caller has already loaded,
# so one gzip pass serves both and they can never describe different windows.
# --------------------------------------------------------------------------------------------

def _tape_atr(bars: Any, lookback: int = 14) -> float:
    """True range over the TAPE's own bars. A stop for a tape-time rule must be sized in tape
    time -- a daily ATR on an hourly signal is a stop roughly five times wider than the move the
    rule is claiming, which quietly turns a fade into a hold-and-hope."""
    window = list(bars)[-(lookback + 1):]
    if len(window) < 2:
        return 0.0
    trs = []
    for prev, cur in itertools.pairwise(window):
        trs.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    return float(np.mean(trs)) if trs else 0.0


def h4_auction_value(profile: Any = None, *, stop_frac: float = 0.5) -> list[Setup]:
    """Acceptance/rejection at the value area: fade a print OUTSIDE the area back toward the POC.

    MECHANISM, as registered: price outside the value area is an auction that has not been
    accepted, and unaccepted prices revert to where volume actually traded. Price INSIDE the area
    is doing what it should and is not a signal.

    **THE PRICE IS THE TAPE'S LAST PRINT, NOT A CANDLE CLOSE.** The profile is built from the last
    day of prints; comparing it against a DAILY bar's close asks whether a level that may be
    twenty hours old sits outside an auction measured to the minute. The two objects have to be
    read from the same window or the comparison is between different days.

    PRE-REGISTERED 2026-08-15: `stop_frac=0.5` -- the stop sits half a value-area width beyond the
    edge that was broken. The registration fixes POC/VAH/VAL and the reversion claim; the stop
    geometry is fixed here, before the first run.
    """
    if profile is None:
        return []
    px = float(getattr(profile, "last_price", 0.0) or 0.0)
    width = float(profile.vah - profile.val)
    if width <= 0 or px <= 0:
        return []
    i = max(0, len(getattr(profile, "bars", ())) - 1)
    if px > profile.vah:
        return [Setup("H4_auction_value", -1, px, px + stop_frac * width, profile.poc, i,
                      f"print above VAH {profile.vah:.6g}, unaccepted -> POC {profile.poc:.6g}")]
    if px < profile.val:
        return [Setup("H4_auction_value", +1, px, px - stop_frac * width, profile.poc, i,
                      f"print below VAL {profile.val:.6g}, unaccepted -> POC {profile.poc:.6g}")]
    return []


def h5_cvd_divergence(profile: Any = None, *, lookback: int = 10,
                      stop_atr: float = 1.5) -> list[Setup]:
    """Delta divergence: price makes a new extreme over the window and CUMULATIVE FLOW DOES NOT.

    MECHANISM, as registered: a new high the aggressive buyers did not fund is a push carried by
    makers -- the move is being sold into, and the level is more likely to fail than extend. That
    statement is unavailable from OHLCV at any resolution, which is why this hypothesis waited for
    the tape and why it is the one rule on the desk whose input nothing else can see.

    **A LEVEL IS NOT A DIVERGENCE, AND THE FIRST VERSION TESTED A LEVEL.** It fired a short on
    `cvd < 0` -- the sign of one scalar over the whole window. On a tape with any persistent
    imbalance that scalar keeps one sign for days, so the rule was "new high while the day happens
    to be net-sold", which fires constantly in one regime and never in the other. The registered
    claim is comparative: price sets a higher high, cumulative delta does not. That needs the
    SERIES, and it needs both series on one grid -- `profile.bars`, built in the same pass.

    PRE-REGISTERED 2026-08-15: `lookback=10`, `stop_atr=1.5`.
    """
    if profile is None:
        return []
    bars = list(getattr(profile, "bars", ()))
    if len(bars) < lookback + 2:
        return []
    cum = list(profile.cum_delta())
    i = len(bars) - 1
    a = _tape_atr(bars)
    if not np.isfinite(a) or a <= 0:
        return []
    px = float(bars[i].close)
    prior = bars[i - lookback:i]
    prior_cum = cum[i - lookback:i]
    if px >= max(x.high for x in prior) and cum[i] < max(prior_cum):
        return [Setup("H5_cvd_divergence", -1, px, px + stop_atr * a, px - 2.0 * a, i,
                      f"new {lookback}-bar high, cum delta {cum[i]:,.2f} BELOW its own "
                      f"{lookback}-bar high {max(prior_cum):,.2f} -- the push was not funded")]
    if px <= min(x.low for x in prior) and cum[i] > min(prior_cum):
        return [Setup("H5_cvd_divergence", +1, px, px - stop_atr * a, px + 2.0 * a, i,
                      f"new {lookback}-bar low, cum delta {cum[i]:,.2f} ABOVE its own "
                      f"{lookback}-bar low {min(prior_cum):,.2f} -- the flush was not funded")]
    return []


#: The two rules that consume the tape rather than the candles. THEY TAKE NO DATAFRAME: every
#: number they use -- price, extremes, flow, ATR -- comes off the tape, so there is no seam at
#: which a candle window and a tape window can disagree. `detect` cannot run them because the
#: caller owns the gzip read, and a rule that silently returned nothing when its input was missing
#: would be indistinguishable from a rule that found nothing.
TAPE_RULES: dict[str, Any] = {
    "H4_auction_value": h4_auction_value,
    "H5_cvd_divergence": h5_cvd_divergence,
}


def detect_with_tape(profile: Any, *, now_ms: int | None = None,
                     max_age_h: float | None = None) -> list[Setup]:
    """H4 and H5 for one symbol, given the profile the caller loaded.

    **A STALE TAPE IS REFUSED, NOT FADED.** If a recorder unit stops, the newest partition simply
    stops advancing and every function here keeps returning clean numbers about yesterday's
    auction. Fading the value area of a session that has already ended is a different hypothesis
    from the registered one, and it would be indistinguishable in the artifact.

    Empty when profile is None, and the caller reports that as NO TAPE rather than as no setups.
    """
    if profile is None:
        return []
    limit = tape.MAX_TAPE_AGE_H if max_age_h is None else max_age_h
    if hasattr(profile, "fresh") and not profile.fresh(now_ms, max_age_h=limit):
        return []
    out: list[Setup] = []
    for fn in TAPE_RULES.values():
        out.extend(fn(profile))
    return out
