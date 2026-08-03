"""ICT IN CRYPTO -- where the premise stops being an inference and becomes observable.

WHY THIS FILE EXISTS SEPARATELY FROM patterns.py. ICT was developed on FX and index futures, and
its core premise is that price seeks liquidity resting at obvious levels -- stops above equal
highs, below prior lows. On those markets the premise is an INFERENCE: nobody can see the stops.

Crypto perpetuals change that in one specific way that matters. A large share of the liquidity ICT
theorises about is FORCED, mechanical and partially observable: leveraged positions liquidate at
computable prices, open interest reports how much is out there, and funding settles on a fixed
8-hour clock that creates flow nobody chose to send. The desk's bybit recorder already captures
funding rate, open interest and mark price every ~10 seconds, and `M_FORCED_DELEVERAGE` is the
best-supported mechanism in the desk's own record.

So the crypto-specific claim is testable in a way the FX version is not: instead of assuming stops
rest above equal highs, the desk can watch open interest COLLAPSE while price runs, which is what a
cascade actually looks like in the data it owns.

WHAT IS DELIBERATELY NOT ASSERTED. Crypto trades 24/7 and has no exchange sessions, so there are no
"killzones" here in the FX sense. `session_partition` is a PARTITION -- a label for grouping, not a
claim that any bucket is special. Asserting a London killzone on a market with no London close
would be importing a conclusion from a different asset class, and the desk's own record (social
attention: a FAMILY KILL, 13 deaths) is what happens when borrowed folklore is not re-derived.

Every detector is causal and proven so by the same future-invariance test as patterns.py. Where a
crypto series is ABSENT -- no OI, no funding stamp -- the detector returns a neutral value AND the
absence is reportable, never silently filled with a plausible number.

Pure pandas/numpy. No I/O, no keys, no order paths.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from libs.features.definition import FeatureDefinition

import numpy as np
import pandas as pd

from libs.ict.patterns import ICT_FAMILY, liquidity_sweep

__all__ = [
    "FUNDING_HOURS_UTC",
    "equal_highs",
    "equal_lows",
    "funding_window",
    "oi_flush",
    "session_partition",
    "sweep_into_funding",
]

#: Perp funding settles on this clock at Binance and Bybit alike. A MECHANICAL FACT about the
#: venue, not a belief about behaviour -- which is exactly why it is worth testing: flow that
#: arrives because a contract says so is flow nobody chose to send.
FUNDING_HOURS_UTC = (0, 8, 16)

#: Fraction of price within which two extremes count as "equal". ICT's relative-equal-highs, made
#: numeric. Exposed as an argument everywhere rather than baked in: the right tolerance is an
#: empirical question per symbol and volatility regime, and picking one by eye here would smuggle
#: a fitted parameter into a detector.
DEFAULT_EQ_TOL = 0.0005


def _need(df: pd.DataFrame, *cols: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"crypto ICT patterns need {missing} -- got {list(df.columns)}")


def _hours(df: pd.DataFrame) -> pd.Series:
    _need(df, "timestamp")
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return ts.dt.hour + ts.dt.minute / 60.0


def funding_window(df: pd.DataFrame, minutes: int = 30) -> pd.Series:
    """1.0 inside the +/- window around a funding settlement, else 0.0.

    The only genuinely crypto-native "session" on this desk, and unlike a killzone it is not a
    behavioural guess: the contract settles at 00, 08 and 16 UTC whatever anybody believes. Traders
    who do not want to pay or receive move before it, which makes the window a place where flow is
    mechanically concentrated -- a testable claim rather than a borrowed one.
    """
    h = _hours(df)
    w = minutes / 60.0
    near = pd.Series(False, index=df.index)
    for f in FUNDING_HOURS_UTC:
        d = (h - f).abs()
        near |= (d <= w) | ((24.0 - d) <= w)     # wraps midnight
    return near.astype("float64").fillna(0.0)


def session_partition(df: pd.DataFrame) -> pd.Series:
    """0 Asia, 1 Europe, 2 US, by UTC hour. A PARTITION, not a claim.

    Crypto has no exchange sessions -- it never closes -- so there is no London open to trade
    around. What survives from the FX idea is only that participants are human and geographically
    clustered, which MAY produce a regime difference and may not. This function exists so the
    screen can ask; it asserts nothing about which bucket is special.

    Importing "killzones" as fact would be borrowing a conclusion across asset classes, and this
    desk already has the receipt for what that costs: M_ATTENTION_DELAY is a FAMILY KILL at 13
    deaths, from exactly that kind of unre-derived folklore.
    """
    h = _hours(df)
    return pd.Series(np.where(h < 7, 0.0, np.where(h < 13, 1.0, 2.0)),
                     index=df.index, dtype="float64").fillna(0.0)


def equal_highs(df: pd.DataFrame, lookback: int = 20,
                tol: float = DEFAULT_EQ_TOL) -> pd.Series:
    """Count of prior highs within `tol` of the current high -- resting liquidity, made numeric.

    ICT's "relative equal highs": a shelf of near-identical extremes is where stops accumulate,
    because that is where everyone's invalidation sits. Strictly prior bars only (`shift(1)` on the
    window), so the bar being scored is never part of its own shelf.
    """
    _need(df, "high")
    h = df["high"]
    out = pd.Series(0.0, index=df.index)
    for k in range(1, lookback + 1):
        out += ((h - h.shift(k)).abs() / h.replace(0.0, np.nan) <= tol).astype("float64")
    return out.fillna(0.0)


def equal_lows(df: pd.DataFrame, lookback: int = 20,
               tol: float = DEFAULT_EQ_TOL) -> pd.Series:
    _need(df, "low")
    lo = df["low"]
    out = pd.Series(0.0, index=df.index)
    for k in range(1, lookback + 1):
        out += ((lo - lo.shift(k)).abs() / lo.replace(0.0, np.nan) <= tol).astype("float64")
    return out.fillna(0.0)


def oi_flush(df: pd.DataFrame, window: int = 20, k: float = 2.0) -> pd.Series:
    """+1/-1 when OPEN INTEREST collapses while price runs -- an observed forced-deleveraging leg.

    THE CRYPTO-SPECIFIC PAYOFF, and the reason this module is worth more than the FX version. In
    FX, "price hunted stops" is an inference nobody can check. Here a liquidation cascade has a
    signature in data the desk already records: positions close involuntarily, so OI DROPS sharply
    at the same time price moves hard. Rising OI on a big move is the opposite event -- new
    positioning, not forced exit -- and conflating the two would merge a cascade with a breakout.

    Sign follows PRICE, so +1 is a squeeze up (shorts forced out) and -1 a flush down.

    Returns all-zero when `open_interest` is absent, and the caller can tell that apart from a
    genuine no-signal via `has_oi()` -- absence must never read as a measurement.
    """
    _need(df, "close")
    if "open_interest" not in df.columns:
        return pd.Series(0.0, index=df.index, dtype="float64")
    oi = pd.to_numeric(df["open_interest"], errors="coerce")
    d_oi = oi.diff()
    scale = d_oi.abs().rolling(window, min_periods=window).mean().shift(1)
    ret = df["close"].pct_change()
    ret_scale = ret.abs().rolling(window, min_periods=window).mean().shift(1)
    flushing = (d_oi < -(k * scale)) & (ret.abs() > (k * ret_scale))
    return pd.Series(np.where(flushing & (ret > 0), 1.0,
                              np.where(flushing & (ret < 0), -1.0, 0.0)),
                     index=df.index, dtype="float64").fillna(0.0)


def has_oi(df: pd.DataFrame) -> bool:
    """Is open interest actually present AND varying?

    A constant OI column is the same fact as a missing one for this purpose -- a venue that reports
    a frozen value tells you nothing about deleveraging -- and both must be distinguishable from
    'measured, no flush'. Same rule the moat miner applies to degenerate series.
    """
    if "open_interest" not in df.columns:
        return False
    oi = pd.to_numeric(df["open_interest"], errors="coerce").dropna()
    return len(oi) > 1 and float(oi.std()) > 0.0


def sweep_into_funding(df: pd.DataFrame, minutes: int = 30) -> pd.Series:
    """A liquidity sweep landing inside the funding window -- the crypto-only ICT hypothesis.

    Neither half is novel: sweeps are ICT's oldest idea and the funding clock is public. The
    CONJUNCTION is the crypto-specific, testable claim -- that mechanically-timed flow and
    liquidity-seeking price action coincide -- and it cannot be posed at all on a market without
    perpetuals. It is stated here as a hypothesis for the gauntlet, with no evidence attached.
    """
    return liquidity_sweep(df) * funding_window(df, minutes)


def _definitions() -> tuple[FeatureDefinition, ...]:
    from libs.features.definition import FeatureDefinition
    spec = (
        ("ict_funding_window", funding_window, ("timestamp",), 1,
         "within +/-30min of perp funding settlement (00/08/16 UTC) -- a venue fact, not a belief"),
        ("ict_session", session_partition, ("timestamp",), 1,
         "Asia/Europe/US bucket by UTC hour -- a PARTITION for the screen to test, not a killzone"),
        ("ict_equal_highs", equal_highs, ("high",), 21,
         "count of prior highs within tolerance -- resting stop liquidity, made numeric"),
        ("ict_equal_lows", equal_lows, ("low",), 21,
         "count of prior lows within tolerance"),
        ("ict_oi_flush", oi_flush, ("close", "open_interest"), 21,
         "OI collapsing while price runs -- forced deleveraging, OBSERVED not inferred"),
        ("ict_sweep_into_funding", sweep_into_funding, ("high", "low", "close", "timestamp"), 6,
         "sweep coinciding with the funding window -- the conjunction is the crypto-only claim"),
    )
    return tuple(
        FeatureDefinition(name=n, version=1, compute=f, inputs=i,
                          category=ICT_FAMILY, description=d, min_periods=m)
        for n, f, i, m, d in spec
    )


def register(registry: Any = None, *, bars: Any = None,
             overwrite: bool = False) -> list[str]:
    """Register the crypto-native ICT detectors under the same family and the same gate."""
    from libs.features.registry import register_feature
    out = []
    for d in _definitions():
        register_feature(d, registry=registry, bars=bars, overwrite=overwrite)
        out.append(getattr(d, "key", d.name))
    return out
