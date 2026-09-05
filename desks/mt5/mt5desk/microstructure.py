"""What a tick tape buys that bar data cannot. Pure arithmetic; no I/O, no broker, no decisions.

EVERY FUNCTION HERE IS UNCOMPUTABLE FROM BARS, and that is the entry criterion. The desk already
has open/high/low/close/tick_volume/spread per H1 bar for 251 symbols, and anything derivable from
those belongs in the bar features, not here. What is in this file needs the ORDER and the TIMING
of individual quote updates -- information that is destroyed the moment a bar is formed and cannot
be recovered from it at any price.

  EFFECTIVE SPREAD AT A LATENCY. What a market order actually costs when the decision is made at
  t and the fill lands at t+L. The bar's `spread` column is the broker's spread AT THE BAR STAMP;
  it says nothing about the spread at the instant this desk would have traded, and nothing at all
  about how far the quote moved while the order was in flight. `research/cost_surface.py` names
  this as its own open question in writing -- "whether it is EXECUTABLE at hour 01 needs
  symbol_info_tick from the trading box, which this box cannot reach ... a live-tick confirmation
  is owed and is recorded as such". This is that confirmation.

  REALISED SPREAD AND ADVERSE SELECTION. What the liquidity provider keeps after the mid has
  moved, and how far the mid moves at all in the seconds after a fill. Together they say whether
  a wide spread is a FEE the desk simply pays or a WARNING that the quote it crossed was about to
  move. A bar's spread column carries the first number's headline and none of the second.

  QUOTE-UPDATE INTENSITY AND BURSTINESS. `tick_volume` counts quote updates per bar and is the
  closest a bar gets. It cannot say whether 40,000 updates arrived evenly or in four bursts, and
  a breakout into a burst is a different trade from the same breakout into an even drip.

  MICROPRICE AND ORDER-FLOW IMBALANCE. Where the next mid is likelier to go, from the asymmetry
  of the quote revisions themselves (Cont-Kyle-Stoikov). Bars have no sides.

  THE TRUE INTRABAR PATH. Whether the high came before the low. Every backtest on this desk
  currently has to assume an order, and the assumption decides which of a stop and a target was
  hit on the bars where both were touched -- the bars that matter most.

HONESTY RULES, ENFORCED IN THE CODE RATHER THAN THE COMMENTS

  1. A RETAIL CFD TAPE HAS NO TRADE SIDE. There is no aggressor flag and no per-side size on this
     feed. So nothing here is called "order flow" without the word PROXY, and the imbalance
     functions return a `basis` field saying whether they used real quote sizes or only the sign
     of the revisions. `orthogonal_sweep._tape_series` already sets this precedent in its own
     comment and it is kept.
  2. MICROPRICE DEGRADES, IT DOES NOT FABRICATE. Where the broker supplies no per-side volume the
     microprice IS the mid, and `microprice_basis` says "mid_fallback". Inventing sizes to make a
     formula run produces a model of the invention.
  3. UNITS ARE POINTS, AND `point` IS ALWAYS PASSED IN. `mt5desk/universe.py` records what a units
     bug costs on a mixed universe: a JPY cross came out 150x more expensive than a dollar pair
     and would have been excluded as unaffordable. Nothing here guesses a unit.
  4. TOO FEW OBSERVATIONS IS UNMEASURED, NEVER A NUMBER. Every aggregate carries its `n`, and a
     cell below its minimum returns None rather than a value computed from three ticks (L1.28a).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

#: Below this many ticks a symbol-hour cell states no number. A percentile over 30 quotes is a
#: percentile wearing a costume.
MIN_TICKS_PER_CELL = 200

#: The latency grid the effective-spread surface is measured on, in milliseconds. It mirrors
#: `mt5desk/latency.py`'s GRID_MS so the two can be read together: that module asks what latency
#: is WORTH, this one measures what it COSTS, and a shared grid means the answer to one is
#: directly usable by the other. 0 is included as the reference point -- the cost of an
#: instantaneous fill, which is exactly half the quoted spread and nothing more.
LATENCY_GRID_MS: tuple[int, ...] = (0, 10, 50, 100, 250, 1_000, 5_000)

#: Horizons at which the realised spread (post-fill mid reversion) is measured, in milliseconds.
REALISED_HORIZONS_MS: tuple[int, ...] = (1_000, 5_000, 30_000, 300_000)


@dataclass
class QuoteStats:
    """One symbol-hour cell of microstructure, with the n behind every number."""

    symbol: str
    hour: int
    n_ticks: int
    status: str = "UNMEASURED"
    quoted_spread_pts_p50: float | None = None
    quoted_spread_pts_p75: float | None = None
    quoted_spread_pts_p90: float | None = None
    quoted_spread_pts_p99: float | None = None
    #: E[cost of crossing] in points, per latency in LATENCY_GRID_MS.
    effective_spread_pts: dict[str, float] = field(default_factory=dict)
    #: The slippage ON TOP of the half-spread, per latency -- the number a fill model needs.
    latency_slip_pts: dict[str, float] = field(default_factory=dict)
    #: Per horizon, ON THE BUY SIDE (see realised_spread_pts -- the two-sided average is
    #: algebraically the quoted spread and carries no information).
    realised_spread_pts: dict[str, float] = field(default_factory=dict)
    #: Per horizon: 2 * E|mid move|, the side-free adverse-selection magnitude.
    mid_move_pts: dict[str, float] = field(default_factory=dict)
    quote_intensity_per_min: float | None = None
    burstiness: float | None = None
    stale_frac: float | None = None
    microprice_tilt_pts: float | None = None
    microprice_basis: str = "mid_fallback"
    ofi_mean: float | None = None
    ofi_basis: str = "sign_only"
    zero_spread_frac: float | None = None
    crossed_frac: float | None = None


def quote_frame(ticks: pd.DataFrame, point: float) -> pd.DataFrame:
    """Add mid, spread, spread_pts and microprice to a decoded tick frame.

    Rows without a two-sided quote are DROPPED, not zero-filled: `bid == 0` on an MT5 tick means
    the field did not update on that tick, and treating it as a price of zero produces a spread
    of the entire quote. That is absence rendered as a value, which is the defect this desk keeps
    paying for (WS-005).
    """
    if point <= 0:
        raise ValueError("point must be positive: the unit is not optional and is never guessed")
    df = ticks.copy()
    for col in ("bid", "ask"):
        if col not in df.columns:
            raise KeyError(f"tick frame has no {col!r} column")
    df = df[(df["bid"] > 0) & (df["ask"] > 0)]
    if df.empty:
        return df
    df = df.sort_values("time_msc", kind="mergesort").reset_index(drop=True)
    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    df["spread"] = df["ask"] - df["bid"]
    df["spread_pts"] = df["spread"] / point
    # MICROPRICE NEEDS PER-SIDE SIZE, and this feed does not have it. MT5 gives one `volume`
    # field with no side attached, so the bid/ask weights the microprice is defined by do not
    # exist here. The microprice therefore IS the mid, and the frame SAYS SO in a column rather
    # than quietly returning a mid under a microprice name. If `tape.probe_depth` ever finds a
    # broker with real two-sided depth, the weighted form drops in and the basis column changes
    # with it -- which is how a consumer finds out, instead of by reading this comment.
    df["microprice"] = df["mid"]
    df["microprice_basis"] = "mid_fallback"
    return df


def quoted_spread_pts(df: pd.DataFrame) -> np.ndarray:
    """Quoted spread in points, zero-spread rows EXCLUDED.

    A zero spread is real on this account -- Fusion ZERO is commission-only and 24 of 251 symbols
    genuinely quote 0.0 (`mt5desk/universe.py`) -- but it is not a spread OBSERVATION, and mixing
    it into a percentile drags the median toward a cost the desk does not actually pay in points.
    Its SHARE is reported separately so a symbol that is mostly zero cannot report a confident
    cheap number.
    """
    s = np.asarray(df["spread_pts"], dtype=np.float64)
    return s[s > 0]


def effective_spread_pts(df: pd.DataFrame, latency_ms: int, point: float,
                         side: str = "both") -> np.ndarray:
    """What crossing ACTUALLY costs, per decision instant, at a given latency, in points.

    THE THING BAR DATA CANNOT SAY. A decision taken at tick i against mid_i is filled at the
    quote prevailing `latency_ms` later. For a buy that is `ask(t+L) - mid(t)`; for a sell,
    `mid(t) - bid(t+L)`. At L=0 this is exactly half the quoted spread. Above zero it also
    carries every basis point the market moved while the order was in flight, which is the term
    every cost model on this desk currently sets to zero by construction.

    Returned per observation rather than aggregated, so the caller can take a median, a p90 or a
    conditional mean without this function deciding which is the honest summary.
    """
    if df.empty:
        return np.empty(0, dtype=np.float64)
    t = np.asarray(df["time_msc"], dtype=np.int64)
    mid = np.asarray(df["mid"], dtype=np.float64)
    ask = np.asarray(df["ask"], dtype=np.float64)
    bid = np.asarray(df["bid"], dtype=np.float64)
    # The quote in force at t+L is the LAST tick at or before it -- searchsorted 'right' minus 1.
    j = np.searchsorted(t, t + int(latency_ms), side="right") - 1
    j = np.clip(j, 0, t.size - 1)
    buy = (ask[j] - mid) / point
    sell = (mid - bid[j]) / point
    if side == "buy":
        out = buy
    elif side == "sell":
        out = sell
    else:
        out = (buy + sell) / 2.0
    # A decision whose fill window runs past the end of the tape has no measured fill and is
    # dropped rather than filled with the last quote -- that would report the cost of a fill
    # that did not happen inside the data.
    valid = (t + int(latency_ms)) <= t[-1]
    return out[valid]


def realised_spread_pts(df: pd.DataFrame, horizon_ms: int, point: float,
                        side: str = "buy") -> np.ndarray:
    """The LP's revenue net of adverse selection on ONE side, in points.

        buy   2 * (ask(t) - mid(t+h))        the maker's revenue on a taker's buy
        sell  2 * (mid(t+h) - bid(t))        the mirror

    IT IS NOT AVERAGED OVER THE TWO SIDES, AND THE FIRST VERSION OF THIS FUNCTION WAS. Averaging
    looks like the neutral thing to do on a feed with no aggressor flag, and it is arithmetically
    catastrophic: the two expressions sum to `2*ask - 2*bid`, the mid(t+h) terms cancel exactly,
    and the "realised spread" comes out identically equal to the quoted spread on every tape.
    Price impact -- quoted minus realised -- was then identically zero BY CONSTRUCTION, on a
    trending market as much as on a flat one. The number was not noisy or biased; it carried no
    information at all, while looking like a measurement. Caught by
    test_price_impact_is_positive_when_the_mid_runs_away_from_fills.

    So the side is explicit, and the side-free adverse-selection term is `mid_move_pts` below.
    """
    if df.empty:
        return np.empty(0, dtype=np.float64)
    t = np.asarray(df["time_msc"], dtype=np.int64)
    mid = np.asarray(df["mid"], dtype=np.float64)
    ask = np.asarray(df["ask"], dtype=np.float64)
    bid = np.asarray(df["bid"], dtype=np.float64)
    j = np.searchsorted(t, t + int(horizon_ms), side="right") - 1
    j = np.clip(j, 0, t.size - 1)
    out = (2.0 * (ask - mid[j]) / point if side == "buy"
           else 2.0 * (mid[j] - bid) / point)
    valid = (t + int(horizon_ms)) <= t[-1]
    return out[valid]


def mid_move_pts(df: pd.DataFrame, horizon_ms: int, point: float) -> np.ndarray:
    """The side-free adverse-selection term: 2 * |mid(t+h) - mid(t)|, in points.

    WHAT IT IS FOR. The textbook decomposition is `effective = realised + 2 * price impact`, and
    price impact is signed by the trade's direction. This feed has no direction, so the signed
    quantity is unavailable -- but its MAGNITUDE is not, and the magnitude is the thing that
    distinguishes a wide spread that is a fee from a wide spread that is a warning. A symbol
    whose mid barely moves in the seconds after a quote is a symbol where the whole spread is
    revenue to the maker; one whose mid runs is one where a taker's fill is systematically stale
    the instant it lands.

    Reported as a magnitude and named one. Calling it "price impact" without the absolute value
    would be claiming a direction this feed cannot supply.
    """
    if df.empty:
        return np.empty(0, dtype=np.float64)
    t = np.asarray(df["time_msc"], dtype=np.int64)
    mid = np.asarray(df["mid"], dtype=np.float64)
    j = np.searchsorted(t, t + int(horizon_ms), side="right") - 1
    j = np.clip(j, 0, t.size - 1)
    valid = (t + int(horizon_ms)) <= t[-1]
    return (2.0 * np.abs(mid[j] - mid) / point)[valid]


def quote_intensity(df: pd.DataFrame, bucket: str = "1min") -> pd.Series:
    """Quote updates per bucket. `tick_volume` per bar is the coarse version of this."""
    if df.empty:
        return pd.Series(dtype=float)
    ts = pd.to_datetime(np.asarray(df["time_msc"], dtype=np.int64), unit="ms", utc=True)
    return pd.Series(1, index=ts).resample(bucket).sum().astype(float)


def burstiness(intensity: pd.Series) -> float | None:
    """Index of dispersion (Fano factor) of quote arrivals: variance / mean over the buckets.

    1.0 is a Poisson feed -- updates arriving independently. Above 1 the feed CLUSTERS, which is
    what a real quote stream does around news and session opens, and the degree of clustering is
    a liquidity-regime variable that a bar's tick count averages away entirely.
    """
    v = intensity.to_numpy(dtype=float)
    v = v[np.isfinite(v)]
    if v.size < 10 or v.mean() <= 0:
        return None
    return float(v.var(ddof=1) / v.mean())


def stale_fraction(df: pd.DataFrame) -> float | None:
    """Share of ticks that repeated the previous two-sided quote exactly.

    A high stale fraction with a high tick count is a feed republishing itself, which looks like
    a busy market to anything counting ticks.
    """
    if len(df) < 2:
        return None
    bid = np.asarray(df["bid"], dtype=np.float64)
    ask = np.asarray(df["ask"], dtype=np.float64)
    same = (bid[1:] == bid[:-1]) & (ask[1:] == ask[:-1])
    return float(np.count_nonzero(same) / same.size)


def order_flow_imbalance(df: pd.DataFrame) -> tuple[np.ndarray, str]:
    """A QUOTE-REVISION imbalance proxy, and the basis it was computed on.

    Cont-Kyle-Stoikov OFI in its size-weighted form needs the resting size at the best bid and
    ask. This feed does not carry it, so the SIGN-ONLY variant is used: +1 when the bid was
    revised up or the ask down (buy pressure), -1 for the mirror. It is returned with
    `basis="sign_only"` so no consumer can mistake it for the size-weighted quantity, and if a
    broker ever does supply per-side depth (`mt5desk/tape.probe_depth` answers that with
    evidence) the size-weighted form drops in behind the same signature.

    THIS IS A PROXY AND IS NAMED ONE. A CFD feed has no aggressor flag; anything calling itself
    order flow here would be a model of the naming, not of the flow.
    """
    if len(df) < 2:
        return np.empty(0, dtype=np.float64), "sign_only"
    bid = np.asarray(df["bid"], dtype=np.float64)
    ask = np.asarray(df["ask"], dtype=np.float64)
    # OFI_sign = sign(d bid) + sign(d ask), and the SIGN OF THE SECOND TERM IS THE WHOLE
    # SUBTLETY -- the first version of this function subtracted it, which makes a pure upward
    # drift (bid and ask both stepping up together) read as ZERO net pressure, the exact
    # opposite of what it is. In the Cont-Kyle-Stoikov construction an ask that RISES is
    # sellers retreating, which is buy pressure and adds; an ask that FALLS is sellers pressing,
    # which subtracts. Caught by test_the_flow_proxy_is_always_labelled_a_proxy.
    e = (np.sign(np.diff(bid)) + np.sign(np.diff(ask)))
    return e.astype(np.float64), "sign_only"


def intrabar_path(df: pd.DataFrame, freq: str = "1h") -> pd.DataFrame:
    """For every bar: did the high come before the low, and when did each happen?

    THE ASSUMPTION THIS RETIRES. A backtest fed only OHLC has to guess the order of the extremes,
    and the guess decides the outcome on exactly the bars that matter: the ones where a stop and
    a target were both inside the range. Assuming the favourable extreme came first flatters
    every strategy; assuming the adverse one did buries real ones. Neither is a measurement, and
    the tape settles it per bar.

    Columns:
      open/high/low/close   from the MID, so the path is comparable to a mid-quoted bar
      t_high / t_low        milliseconds from the bar's open to each extreme
      high_first            True when the high was printed before the low
      mae_pts / mfe_pts     worst adverse and best favourable excursion from the open, in points,
                            for a LONG taken at the bar's open -- the short case is the mirror
      path_ticks            how many quote updates the bar is built from (its own n)
    """
    if df.empty:
        return pd.DataFrame()
    ts = pd.to_datetime(np.asarray(df["time_msc"], dtype=np.int64), unit="ms", utc=True)
    mid = pd.Series(np.asarray(df["mid"], dtype=np.float64), index=ts)
    ms = pd.Series(np.asarray(df["time_msc"], dtype=np.int64), index=ts)
    g = mid.groupby(pd.Grouper(freq=freq))
    rows: list[dict[str, Any]] = []
    for stamp, chunk in g:
        if chunk.empty:
            continue
        t = ms.loc[chunk.index]
        i_hi = int(np.argmax(chunk.to_numpy()))
        i_lo = int(np.argmin(chunk.to_numpy()))
        t0 = int(t.iloc[0])
        rows.append({
            "bar": stamp, "open": float(chunk.iloc[0]), "high": float(chunk.max()),
            "low": float(chunk.min()), "close": float(chunk.iloc[-1]),
            "t_high_ms": int(t.iloc[i_hi]) - t0, "t_low_ms": int(t.iloc[i_lo]) - t0,
            "high_first": bool(i_hi < i_lo), "path_ticks": int(chunk.size),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.set_index("bar")


def path_excursions(path: pd.DataFrame, point: float) -> pd.DataFrame:
    """MAE and MFE in points for a long taken at each bar's open. The short case is the mirror."""
    if path.empty:
        return path
    out = path.copy()
    out["mfe_pts"] = (out["high"] - out["open"]) / point
    out["mae_pts"] = (out["open"] - out["low"]) / point
    return out


def hour_cell(df: pd.DataFrame, symbol: str, hour: int, point: float,
              min_ticks: int = MIN_TICKS_PER_CELL) -> QuoteStats:
    """Every microstructure statistic for one symbol-hour, or UNMEASURED with its n."""
    n = len(df)
    st = QuoteStats(symbol=symbol, hour=hour, n_ticks=n)
    if n < min_ticks:
        return st                                   # UNMEASURED, and the n says why
    st.status = "MEASURED"
    sp = quoted_spread_pts(df)
    all_sp = np.asarray(df["spread_pts"], dtype=np.float64)
    st.zero_spread_frac = round(float(np.count_nonzero(all_sp <= 0) / all_sp.size), 5)
    st.crossed_frac = round(float(np.count_nonzero(all_sp < 0) / all_sp.size), 6)
    if sp.size >= min_ticks:
        st.quoted_spread_pts_p50 = round(float(np.median(sp)), 3)
        st.quoted_spread_pts_p75 = round(float(np.quantile(sp, 0.75)), 3)
        st.quoted_spread_pts_p90 = round(float(np.quantile(sp, 0.90)), 3)
        st.quoted_spread_pts_p99 = round(float(np.quantile(sp, 0.99)), 3)
    half = (st.quoted_spread_pts_p50 or 0.0) / 2.0
    for lat in LATENCY_GRID_MS:
        eff = effective_spread_pts(df, lat, point)
        if eff.size >= min_ticks:
            v = round(float(np.median(eff)), 3)
            st.effective_spread_pts[str(lat)] = v
            # THE NUMBER A FILL MODEL ACTUALLY NEEDS: what latency costs ON TOP of the spread
            # every cost model already charges. Reporting only the total would let a consumer
            # double-charge the half-spread it is already paying.
            st.latency_slip_pts[str(lat)] = round(v - half, 3)
    for h in REALISED_HORIZONS_MS:
        rs = realised_spread_pts(df, h, point, side="buy")
        if rs.size >= min_ticks:
            st.realised_spread_pts[str(h)] = round(float(np.median(rs)), 3)
        mv = mid_move_pts(df, h, point)
        if mv.size >= min_ticks:
            st.mid_move_pts[str(h)] = round(float(np.mean(mv)), 3)
    inten = quote_intensity(df)
    if not inten.empty:
        st.quote_intensity_per_min = round(float(inten.mean()), 2)
        st.burstiness = (round(b, 3) if (b := burstiness(inten)) is not None else None)
    sf = stale_fraction(df)
    st.stale_frac = round(sf, 5) if sf is not None else None
    ofi, basis = order_flow_imbalance(df)
    st.ofi_basis = basis
    if ofi.size >= min_ticks:
        st.ofi_mean = round(float(ofi.mean()), 5)
    st.microprice_tilt_pts = 0.0
    st.microprice_basis = str(df["microprice_basis"].iloc[0]) if "microprice_basis" in df else \
        "mid_fallback"
    return st


def price_impact_pts(st: QuoteStats, horizon_ms: int = 30_000) -> float | None:
    """The adverse-selection magnitude in points: 2 * E|mid move| over the horizon.

    Near zero means the quoted spread is a FEE -- the mid does not run after a fill, so the
    maker keeps the spread and the taker's price is not stale. Large means it is a WARNING: the
    quote this desk crossed was systematically about to move, and the headline spread understates
    what trading there actually costs.

    Taken from `mid_move_pts` rather than from quoted-minus-realised, because the realised
    spread is only interpretable per side and this feed carries no aggressor flag. A signed
    price impact would be claiming a direction the data does not have.
    """
    v = st.mid_move_pts.get(str(horizon_ms))
    return round(v, 3) if v is not None else None
