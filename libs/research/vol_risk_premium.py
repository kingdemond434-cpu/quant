"""VOLATILITY RISK PREMIUM -- the numeric primitives for the Stage-A screen of census gap #5.

WHY THIS MODULE EXISTS. `scripts/screen_vol_risk_premium.py` asks whether the premium of implied
over subsequently-realised volatility is a harvestable, CONDITIONAL edge rather than a constant that
the tail takes back. The desk has already asked a thinner version of that question once:
`scripts/run_options_vrp_backtest.py` measured a time-series IC of +0.06 on the Deribit DVOL index
-- the campaign's BEST measured IC anywhere -- and the census (`data/mechanism_census.json`, rank 5,
gap score 0.3264) records that it died on BREADTH and not on sign: TWO markets, BTC and ETH, because
DVOL exists for nothing else. A mechanism that dies for want of breadth needs more markets, not a
better estimator, and this module's entire reason to exist is to manufacture those markets out of
data that is free and keyless.

WHERE THE BREADTH COMES FROM -- AND WHY IT IS REAL BREADTH, NOT RESAMPLED BREADTH.
Deribit's DVOL index covers 2 currencies. Deribit's OPTION CHAIN covers 7 underlyings (BTC, ETH,
SOL, XRP, AVAX, TRX, HYPE at the time of writing) across 5-12 listed expiries each, and an implied
volatility can be inverted from any of them. A MARKET here is (underlying x tenor bucket): a
distinct underlying whose vol is quoted at a distinct point on the term structure. That is a real
widening on the underlying axis and a partly-real one on the tenor axis -- 30-day and 90-day BTC vol
are NOT independent observations, which is exactly why the screen measures the cross-market
correlation and reports the EFFECTIVE independent market count beside the raw one. Breadth that is
asserted rather than measured is how a 2-market result becomes a 20-market result on paper while
the standard error does not move at all.

WHY BLACK-76 AND NOT THE PUBLISHED `mark_iv`. `mark_iv` is a snapshot field with NO history: per
strike implied vol cannot be bought back, which is why `scripts/collect_deribit_surface.py` archives
it forward. But an option's MARK PRICE history is public (`get_tradingview_chart_data`) for every
instrument still listed, and inverting Black-76 on it reconstructs the implied vol the desk was
never recording. Verified against the live book before this module was written: the inversion below
reproduces Deribit's own `mark_iv` to within 0.01 vol points on both the inverse (BTC/ETH, price
quoted in coin) and the linear (USDC-settled) families. That is the difference between a screen that
can run today across 7 underlyings and one that must wait a year for a snapshot log to accrue.

WHAT THE RECONSTRUCTION CANNOT DO, STATED HERE SO THE SCREEN CAN DECLARE IT.
Only instruments that are STILL LISTED have retrievable history, so an expiry that has already
expired is gone. At a historical date t the retrievable chain therefore contains only contracts that
had a long time-to-expiry AT t. This is a TENOR-COMPOSITION bias -- short-tenor buckets simply begin
later -- and it is emphatically NOT a selection on outcome: an option does not stop being listed
because it performed badly, and for any non-expired expiry the strike ladder is complete. The screen
reports each market's own start date rather than pretending to a balanced panel.

NO NETWORK, NO FILE I/O, NO ARGV. Fetching lives in `scripts/collect_deribit_vol_markets.py`; this
module is pure numeric so its causality can be pinned by tests without a venue. Pure numpy + stdlib.
Zero promotion authority.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

__all__ = [
    "CONSTRUCTIONS",
    "MIN_MARKET_OBS",
    "TARGETS",
    "TENOR_BUCKETS",
    "TRADING_DAYS_PER_YEAR",
    "MarketSeries",
    "VrpAlignment",
    "align_markets",
    "atm_implied_vol",
    "black76_price",
    "bucket_of",
    "forward_from_parity",
    "implied_vol",
    "log_returns",
    "longest_contiguous_run",
    "market_key",
    "mean_pairwise_corr",
    "pooled_mean",
    "realised_vol",
    "short_vol_carry",
]

#: Calendar-day annualisation. Crypto trades continuously, so a year holds 365 daily returns and
#: NOT 252 -- using an equity convention here would inflate every realised vol by sqrt(365/252) =
#: 1.20 and manufacture a volatility risk premium out of the unit mismatch alone. That is not a
#: hypothetical: it is the single easiest way to "discover" this mechanism by accident.
TRADING_DAYS_PER_YEAR = 365.0

#: Paired (signal, target) observations below which a market is not screened at all. `axis_screen`
#: needs >30 rows after its own 20-period z-score warm-up; 60 is the floor `screen_orderbook_state`
#: uses and is kept identical so the two organs mean the same thing by "too short".
MIN_MARKET_OBS = 60

#: PRE-REGISTERED TENOR BUCKETS -- fixed before any result, in days to expiry.
#: Chosen to bracket the listed term structure (Deribit lists dailies, weeklies, monthlies and
#: quarterlies), NOT tuned to a result. A contract is assigned to the bucket its dte falls in ON
#: THE OBSERVATION DATE, so a single expiry migrates down the buckets as it ages and each bucket
#: always holds a roughly constant tenor -- which is the only way a "30-day vol" series means the
#: same thing in January as in June.
TENOR_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("t07", 3.0, 10.0),
    ("t30", 10.0, 45.0),
    ("t90", 45.0, 120.0),
    ("t180", 120.0, 400.0),
)

#: Realised-vol lookback in days for each bucket -- the RV window is MATCHED to the tenor whose
#: implied vol it is differenced against. A 7-day implied minus a 180-day realised is not a risk
#: premium, it is a term-structure spread wearing the premium's name.
_BUCKET_RV_WINDOW: dict[str, int] = {"t07": 7, "t30": 30, "t90": 90, "t180": 180}


@dataclass(frozen=True)
class VrpAlignment:
    """THE TIMESTAMP RULE, AS DATA -- echoed into every artifact rather than described in prose.

    THE CLOCK. Deribit stamps its daily bars, and settles its options, at 08:00 UTC. Every series
    in this screen -- option marks, the perpetual used for realised variance, the expiry instants
    -- is read on that ONE clock, from that ONE venue. This is not tidiness: the desk's kimchi /
    Turkey / Coinbase kills were all timezone artifacts, in which a candle labelled with one
    session's date was compared against a close from another and the ~1.6-day offset read as
    forecasting skill. Sourcing implied and realised from the same venue and the same stamp makes
    that class of error unavailable rather than merely unlikely.

    SIGNAL. `signal[t]` is computed from the option chain as marked at 08:00 UTC on day t, and from
    realised variance over a trailing window that ENDS at t. Every input is in the information set
    at 08:00 UTC on day t.

    TARGET. `target[t]` is the quantity realised OVER day t, i.e. across (t-1, t]. That is exactly
    `axis_screen`'s contract -- "target_ret[t] = return realised over period t" -- and the harness
    performs the forward shift ITSELF, pairing signal[t] with target[t+1]. Handing it an
    already-shifted target makes it shift twice, which is the misalignment signature its own
    lookahead rail fires on.

    SO THE PREDICTED WINDOW IS (t, t+1] AND THE DAY THE SIGNAL WAS OBSERVED IS NOT IN IT.

    THE DECLARED CONTAMINATION, and it is this mechanism's whole hazard. A trailing realised vol
    computed through t contains the squared return of day t, and `target[t]` is a function of that
    same squared return. Signal and same-period target are therefore mechanically linked, which is
    precisely what `axis_screen`'s angle-20 gate measures. The screen does not design that away --
    it pre-registers BOTH the through-t form and a form whose RV window ends at t-1, and reports
    the gate's reading on both. `rv_lag_days` records which one a row used.

    NO DISCOUNTING, DECLARED. Black-76 is applied undiscounted on the forward recovered from
    put-call parity, which is Deribit's own mark convention (verified to 0.01 vol points against
    the live book). No interest-rate series is assumed, and none is available keylessly; a rate
    guessed here would be a fabricated input wearing a model's name.
    """

    venue: str = "deribit"
    bar_seconds: int = 86_400
    stamp_utc: str = "08:00"
    rv_lag_days: int = 0

    def __post_init__(self) -> None:
        if self.bar_seconds <= 0:
            raise ValueError("bar_seconds must be positive")
        if self.rv_lag_days < 0:
            raise ValueError("rv_lag_days must not be negative")

    @property
    def horizon_days(self) -> float:
        """Target period in days -- what `axis_screen` needs to annualise and to deflate n_eff."""
        return float(self.bar_seconds) / 86_400.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "bar_seconds": int(self.bar_seconds),
            "stamp_utc": self.stamp_utc,
            "horizon_days": self.horizon_days,
            "rv_lag_days": int(self.rv_lag_days),
            "one_clock": (
                "implied vol, realised vol and the expiry instant are all read from Deribit at "
                "08:00 UTC -- one venue, one stamp, so a session-offset artifact is unavailable "
                "rather than merely unlikely"
            ),
            "signal_at": (
                "option chain as marked at 08:00 UTC on day t, plus realised variance over a "
                f"trailing window ending at day t-{int(self.rv_lag_days)}"
            ),
            "target_over": "day t, i.e. the half-open interval (t-1, t]",
            "forward_pairing": (
                "the harness shifts forward itself and pairs signal[t] with target[t+1]; the "
                "predicted window is (t, t+1] and the observation day is excluded from it"
            ),
            "excludes_current_period": True,
            "discounting": (
                "none -- undiscounted Black-76 on the parity-recovered forward, which is Deribit's "
                "own mark convention; no interest-rate series is assumed or fabricated"
            ),
            "declared_contamination": (
                "a trailing RV through t shares day t's squared return with the same-period "
                "target, so signal and target are mechanically linked; the angle-20 gate measures "
                "it and BOTH the through-t and the ending-at-t-1 forms are pre-registered"
            ),
        }


# --------------------------------------------------------------------------------------------
# Option maths. Undiscounted Black-76 on the forward -- Deribit's own mark convention.
# --------------------------------------------------------------------------------------------


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black76_price(forward: float, strike: float, t_years: float, sigma: float, *,
                  is_call: bool) -> float:
    """Undiscounted Black-76 price in the SAME currency as `forward` and `strike`.

    Degenerate inputs collapse to intrinsic rather than raising: a zero-vol or zero-time option is
    worth its intrinsic value, and a NaN here would silently poison a whole ladder.
    """
    f, k, t = float(forward), float(strike), float(t_years)
    if not (f > 0.0 and k > 0.0):
        return float("nan")
    intrinsic = max(0.0, (f - k) if is_call else (k - f))
    if t <= 0.0 or sigma <= 0.0:
        return intrinsic
    v = float(sigma) * math.sqrt(t)
    d1 = (math.log(f / k) + 0.5 * v * v) / v
    d2 = d1 - v
    if is_call:
        return f * _norm_cdf(d1) - k * _norm_cdf(d2)
    return k * _norm_cdf(-d2) - f * _norm_cdf(-d1)


def implied_vol(price: float, forward: float, strike: float, t_years: float, *,
                is_call: bool, lo: float = 1e-3, hi: float = 8.0,
                iterations: int = 80) -> float | None:
    """Invert Black-76 by bisection. None when the price is outside the no-arbitrage bracket.

    NONE, NOT A CLAMPED NUMBER. A mark below intrinsic or above the forward is not a very low or
    very high volatility -- it is a quote the model cannot represent (a stale mark, a crossed book,
    a chart bar from a moment with no two-sided market). Clamping such a row to the bracket edge
    would place a fabricated 800%-vol observation into a panel whose whole purpose is to measure
    the average level of implied vol. Bisection rather than Newton because the bracket is monotone
    and bounded, so it cannot diverge on a near-intrinsic deep-ITM quote where vega is ~0.
    """
    p, f, k, t = float(price), float(forward), float(strike), float(t_years)
    if not (math.isfinite(p) and f > 0.0 and k > 0.0 and t > 0.0):
        return None
    p_lo = black76_price(f, k, t, lo, is_call=is_call)
    p_hi = black76_price(f, k, t, hi, is_call=is_call)
    if not (p_lo <= p <= p_hi):
        return None
    a, b = lo, hi
    for _ in range(int(iterations)):
        m = 0.5 * (a + b)
        if black76_price(f, k, t, m, is_call=is_call) > p:
            b = m
        else:
            a = m
    return 0.5 * (a + b)


def forward_from_parity(strikes: Sequence[float], calls: Sequence[float], puts: Sequence[float],
                        *, inverse: bool) -> tuple[float, float] | None:
    """Recover (forward, atm_strike) from put-call parity. None when no strike carries both legs.

    WHY PARITY AND NOT A FUTURES FEED. The historical forward for a given expiry is not published
    per expiry, and substituting the perpetual or the index would import a basis error straight into
    every inverted vol -- largest exactly at the long tenors this screen widened onto. Parity
    recovers the forward the option market itself was using, from the same two quotes the vol is
    inverted from, so the implied vol and its forward can never disagree about the date.

    LINEAR (USDC-settled) legs are quoted in the quote currency: C - P = F - K, so F = K + C - P.
    INVERSE (BTC/ETH-settled) legs are quoted in COIN, i.e. as a fraction of the underlying, and
    the underlying used for that conversion is the forward itself. So (C - P) * F = F - K, which
    solves to F = K / (1 - (C - P)) with no external price at all.

    The strike used is the one with the smallest |C - P|, i.e. the nearest to at-the-money, where
    parity is least sensitive to a stale quote on either leg.
    """
    best: tuple[float, float, float] | None = None
    for k, c, p in zip(strikes, calls, puts, strict=True):
        kk, cc, pp = float(k), float(c), float(p)
        if not (kk > 0.0 and math.isfinite(cc) and math.isfinite(pp)):
            continue
        d = abs(cc - pp)
        if best is None or d < best[0]:
            best = (d, kk, cc - pp)
    if best is None:
        return None
    _, k_atm, diff = best
    if inverse:
        den = 1.0 - diff
        if den <= 0.0:
            return None
        fwd = k_atm / den
    else:
        fwd = k_atm + diff
    if not (math.isfinite(fwd) and fwd > 0.0):
        return None
    return fwd, k_atm


def atm_implied_vol(strikes: Sequence[float], calls: Sequence[float], puts: Sequence[float],
                    *, t_years: float, inverse: bool) -> tuple[float, float] | None:
    """(atm_implied_vol, forward) from one expiry's strike ladder on one date. None when unfittable.

    BOTH LEGS AT THE SAME STRIKE, AVERAGED. At the money the call and the put carry the same
    information and differ only by microstructure, so averaging their inverted vols is a free
    halving of quote noise; where only one leg inverts, that one is used. The strike is the one
    nearest the parity-recovered forward -- never a fixed moneyness, which would drift off the money
    as the underlying moves and turn a level series into a skew series without saying so.
    """
    par = forward_from_parity(strikes, calls, puts, inverse=inverse)
    if par is None:
        return None
    fwd, _ = par
    idx = -1
    best = math.inf
    for i, k in enumerate(strikes):
        kk = float(k)
        if kk <= 0.0:
            continue
        d = abs(kk - fwd)
        if d < best:
            best, idx = d, i
    if idx < 0:
        return None
    k_use = float(strikes[idx])
    scale = fwd if inverse else 1.0            # inverse marks are a fraction of the forward
    ivs: list[float] = []
    for px, is_call in ((float(calls[idx]), True), (float(puts[idx]), False)):
        if not math.isfinite(px):
            continue
        v = implied_vol(px * scale, fwd, k_use, t_years, is_call=is_call)
        if v is not None:
            ivs.append(v)
    if not ivs:
        return None
    return float(sum(ivs) / len(ivs)), fwd


def bucket_of(dte_days: float) -> str | None:
    """Tenor bucket for a days-to-expiry, or None when the contract falls outside every bucket."""
    d = float(dte_days)
    for name, lo, hi in TENOR_BUCKETS:
        if lo <= d < hi:
            return name
    return None


def market_key(underlying: str, bucket: str) -> str:
    """The MARKET identity for this screen: one underlying at one point on the term structure."""
    return f"{underlying.upper()}:{bucket}"


def longest_contiguous_run(dates_ms: np.ndarray, *, step_ms: int = 86_400_000) -> tuple[int, int]:
    """(start, stop) of the longest run of exactly-one-step-apart dates. Half-open, (0, 0) if empty.

    WHY A RUN AND NOT A MASK. `axis_screen` pairs signal[t] with target[t+1] by POSITION, so simply
    dropping a gap's rows re-labels the observation after it as "tomorrow" when it is a week later.
    Compaction is exactly the misalignment its own lookahead rail exists to catch, and it is
    invisible in the output. Taking the longest uninterrupted run instead shortens the sample --
    which can only ever ATTENUATE an IC toward zero, the safe direction -- and the screen reports
    how much it dropped rather than burying it.
    """
    d = np.asarray(dates_ms, dtype="int64")
    if d.size == 0:
        return 0, 0
    best_start = cur_start = 0
    best_len = cur_len = 1
    for i in range(1, d.size):
        if int(d[i] - d[i - 1]) == int(step_ms):
            cur_len += 1
        else:
            cur_start, cur_len = i, 1
        if cur_len > best_len:
            best_start, best_len = cur_start, cur_len
    return best_start, best_start + best_len


def rv_window_days(bucket: str) -> int:
    """Realised-vol lookback matched to the bucket's tenor. Falls back to 30 for an unknown name."""
    return _BUCKET_RV_WINDOW.get(bucket, 30)


# --------------------------------------------------------------------------------------------
# Realised variance and the short-vol payoff.
# --------------------------------------------------------------------------------------------


def log_returns(closes: np.ndarray) -> np.ndarray:
    """r[t] = log(p[t]/p[t-1]), the return realised OVER period t. NaN at t=0 and on bad prices.

    CONTEMPORANEOUS BY CONSTRUCTION and it must stay that way: `axis_screen` does its own forward
    shift, so a target that is already forward gets shifted twice and the harness reads the result
    as misalignment rather than as edge.
    """
    p = np.asarray(closes, dtype="float64")
    out = np.full(p.size, np.nan)
    if p.size < 2:
        return out
    with np.errstate(invalid="ignore", divide="ignore"):
        prev = np.where(p[:-1] > 0.0, p[:-1], np.nan)
        cur = np.where(p[1:] > 0.0, p[1:], np.nan)
        out[1:] = np.log(cur / prev)
    return out


def realised_vol(rets: np.ndarray, window: int, *, lag: int = 0,
                 min_frac: float = 0.8) -> np.ndarray:
    """Annualised trailing realised vol. rv[t] uses r[t-lag-window+1 .. t-lag] and NOTHING LATER.

    STRICTLY CAUSAL, AND THE TEST SUITE PINS IT BY PERTURBING THE FUTURE. `lag=0` ends the window
    at t (what a trader observes at t); `lag=1` ends it at t-1 and is the pre-registered
    de-contaminated form -- day t's squared return is then absent from the signal while still being
    present in the same-period target, which is the only way the angle-20 gate can distinguish a
    forecast from a restatement.

    Zero-mean (not de-meaned) sum of squares: over a daily window the drift estimate is pure noise
    and subtracting it biases variance DOWN, which would manufacture premium.
    """
    r = np.asarray(rets, dtype="float64")
    w = max(int(window), 1)
    lg = max(int(lag), 0)
    out = np.full(r.size, np.nan)
    ok = np.isfinite(r)
    sq = np.where(ok, r * r, 0.0)
    csum = np.concatenate(([0.0], np.cumsum(sq)))
    ccnt = np.concatenate(([0.0], np.cumsum(ok.astype("float64"))))
    need = max(round(min_frac * w), 2)
    for t in range(r.size):
        end = t - lg + 1                       # exclusive right edge of the window
        start = end - w
        if start < 0 or end <= 0:
            continue
        n = ccnt[end] - ccnt[start]
        if n < need:
            continue
        var = (csum[end] - csum[start]) / n
        if var < 0.0:
            continue
        out[t] = math.sqrt(var * TRADING_DAYS_PER_YEAR)
    return out


def short_vol_carry(iv: np.ndarray, rets: np.ndarray) -> np.ndarray:
    """THE MECHANISM'S OWN PAYOFF: the per-period P&L of a short variance position, normalised.

    carry[t] = 1 - r[t]^2 / (iv[t-1]^2 / 365)

    A desk that sells one day of variance at the implied level iv[t-1] receives iv[t-1]^2/365 and
    pays back r[t]^2. Dividing by the premium received makes the series dimensionless and therefore
    COMPARABLE ACROSS MARKETS, which is what pooling a 7-underlying panel requires; a raw variance
    difference would let BTC's variance scale dominate TRX's entirely.

    The shape is the honest one: bounded above by 1 (the most a vol seller can win is the whole
    premium) and unbounded below (the tail). Any Sharpe computed on it inherits that asymmetry
    rather than hiding it, which is the point -- the standing question about this mechanism is not
    whether the mean is positive but whether the tail takes it back.

    NaN at t=0, wherever iv[t-1] is not positive, and wherever r[t] is not finite.
    """
    v = np.asarray(iv, dtype="float64")
    r = np.asarray(rets, dtype="float64")
    if v.size != r.size:
        raise ValueError(f"iv/returns length mismatch: {v.size} vs {r.size}")
    out = np.full(v.size, np.nan)
    if v.size < 2:
        return out
    prev = v[:-1]
    with np.errstate(invalid="ignore", divide="ignore"):
        prem = np.where(prev > 0.0, prev * prev / TRADING_DAYS_PER_YEAR, np.nan)
        out[1:] = 1.0 - (r[1:] * r[1:]) / prem
    out[~np.isfinite(out)] = np.nan
    return out


@dataclass(frozen=True)
class MarketSeries:
    """One MARKET -- one underlying at one tenor bucket -- on a STRICTLY CONTIGUOUS daily grid.

    All arrays share one index. `atm_iv` is annualised implied vol in DECIMAL (0.55 = 55%), matching
    `realised_vol`'s units. The unit conversion happens exactly once, in the screen's panel reader,
    driven by the row's OWN `atm_iv_unit` declaration -- never inferred from magnitude. Deribit
    publishes `mark_iv` in PERCENT while the collector emits the Black-76 inversion in DECIMAL, and
    the two differ by 100x on a field that looks identical either way; a wrong guess leaves every
    IC intact (the harness z-scores, so a constant factor cancels) while destroying every Sharpe
    and every variance-swap payoff, which depend on the LEVEL.

    `rets` IS A FIELD, NOT A PROPERTY DERIVED FROM `close`, and the distinction is load-bearing.
    Realised variance and the daily return must be computed on the underlying's OWN uninterrupted
    bar series; deriving them from a `close` array that has already been subset to the dates where
    an implied vol exists would silently price a three-day move as a one-day return wherever the
    option book was thin. The caller computes both on the full bar series and indexes in.

    CONTIGUITY IS ENFORCED, NOT ASSUMED. `axis_screen` pairs signal[t] with target[t+1] by
    POSITION, so one missing day inside a market turns a one-day forward claim into a multi-day one
    at that seam, in whichever direction the gap happened to move. `__post_init__` rejects a
    non-contiguous grid outright rather than letting the screen average over the damage.
    """

    key: str
    underlying: str
    bucket: str
    dates_ms: np.ndarray
    atm_iv: np.ndarray
    close: np.ndarray
    rets: np.ndarray
    rv_now: np.ndarray
    rv_lag: np.ndarray

    def __post_init__(self) -> None:
        n = int(self.dates_ms.size)
        for nm in ("atm_iv", "close", "rets", "rv_now", "rv_lag"):
            arr = getattr(self, nm)
            if int(np.asarray(arr).size) != n:
                raise ValueError(f"{self.key}: {nm} length {np.asarray(arr).size} != {n}")
        d = np.asarray(self.dates_ms, dtype="int64")
        if n > 1 and not bool(np.all(np.diff(d) == 86_400_000)):
            raise ValueError(f"{self.key}: dates_ms is not a contiguous daily grid")


#: PRE-REGISTERED CONSTRUCTION SET -- four, fixed, named before any result was read. The family the
#: multiplicity charge is computed over. A fifth added after seeing the first four is the
#: garden-of-forking-paths the charter forbids, and it would silently deflate the correction every
#: other cell was judged against.
CONSTRUCTIONS: dict[str, Callable[[MarketSeries], np.ndarray]] = {
    # THE PREMIUM AS OBSERVED. Trailing RV runs through t -- what a trader actually sees at t, and
    # the form most exposed to the declared contamination.
    "vrp_level": lambda m: m.atm_iv - m.rv_now,
    # THE DE-CONTAMINATED PREMIUM. Trailing RV ends at t-1, so day t's squared return is not in the
    # signal while it is still in the same-period target. Pre-registered up front precisely so it
    # cannot be mistaken for a fix applied after seeing the gate fire.
    "vrp_level_lag": lambda m: m.atm_iv - m.rv_lag,
    # SCALE-FREE. log(IV/RV) is comparable across underlyings whose vol levels differ by 3x, which
    # is what makes a 7-underlying pool meaningful rather than a BTC series with noise stapled on.
    "vrp_log_ratio": lambda m: _safe_log_ratio(m.atm_iv, m.rv_lag),
    # THE CONTROL, and it is load-bearing. If the implied level ALONE scores as well as the premium,
    # then "premium" is a story told over a vol-level signal and the mechanism claim is unsupported.
    "iv_level": lambda m: m.atm_iv,
}

#: PRE-REGISTERED TARGETS -- two, fixed.
TARGETS: dict[str, Callable[[MarketSeries], np.ndarray]] = {
    # The mechanism's own payoff: what a one-day short-variance position earned over period t.
    "short_vol_carry": lambda m: short_vol_carry(m.atm_iv, m.rets),
    # The PRIOR ATTEMPT'S target, kept unchanged so the widened screen is directly comparable with
    # the graveyard's `options_vrp` row (+0.06 IC on 2 markets). Without it, a different number on a
    # different target could be mistaken for having reproduced or refuted that result.
    "underlying_return": lambda m: m.rets,
}


def _safe_log_ratio(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    a = np.asarray(num, dtype="float64")
    b = np.asarray(den, dtype="float64")
    out = np.full(a.shape, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(a) & np.isfinite(b) & (a > 0.0) & (b > 0.0)
        out[ok] = np.log(a[ok] / b[ok])
    return out


# --------------------------------------------------------------------------------------------
# Breadth. The measurements that decide whether more markets bought anything.
# --------------------------------------------------------------------------------------------


def align_markets(series: Sequence[np.ndarray], dates: Sequence[np.ndarray]) -> \
        tuple[np.ndarray, np.ndarray]:
    """Align per-market series onto their COMMON date grid. Returns (dates, matrix[date, market]).

    INTERSECTION, NOT UNION, and not a forward fill. A market that was not listed on a date has no
    observation on it; carrying its last value forward would inject a flat stretch that reads as
    low volatility of the signal and inflates a z-score's tails. The intersection shortens the
    panel, which can only ever ATTENUATE an IC toward zero -- the safe direction.
    """
    if not series:
        return np.zeros(0, dtype="int64"), np.zeros((0, 0))
    common: np.ndarray | None = None
    for d in dates:
        dd = np.asarray(d, dtype="int64")
        common = dd if common is None else np.intersect1d(common, dd)
    if common is None or common.size == 0:
        return np.zeros(0, dtype="int64"), np.zeros((0, 0))
    cols = []
    for s, d in zip(series, dates, strict=True):
        dd = np.asarray(d, dtype="int64")
        ss = np.asarray(s, dtype="float64")
        idx = np.searchsorted(dd, common)
        cols.append(ss[idx])
    return common, np.column_stack(cols)


def mean_pairwise_corr(matrix: np.ndarray) -> float:
    """Mean off-diagonal Pearson correlation across markets. NaN when fewer than two are usable.

    THE NUMBER THAT DECIDES WHETHER BREADTH IS REAL. Twenty markets that move as one are one
    market with twenty names, and reporting the raw count beside a t-stat computed as if they were
    independent is how a 2-market result becomes a 20-market result on paper while the standard
    error does not move at all. This feeds `libs.validation.type2_cost.pooling_multiplier`, which
    turns (count, correlation) into the EFFECTIVE independent count the screen actually publishes.
    """
    m = np.asarray(matrix, dtype="float64")
    if m.ndim != 2 or m.shape[1] < 2:
        return float("nan")
    keep = [j for j in range(m.shape[1])
            if np.isfinite(m[:, j]).sum() >= 3 and np.nanstd(m[:, j]) > 0.0]
    if len(keep) < 2:
        return float("nan")
    vals: list[float] = []
    for a in range(len(keep)):
        for b in range(a + 1, len(keep)):
            x, y = m[:, keep[a]], m[:, keep[b]]
            ok = np.isfinite(x) & np.isfinite(y)
            if int(ok.sum()) < 3:
                continue
            xs, ys = x[ok], y[ok]
            if xs.std() <= 0.0 or ys.std() <= 0.0:
                continue
            vals.append(float(np.corrcoef(xs, ys)[0, 1]))
    return float(np.mean(vals)) if vals else float("nan")


def pooled_mean(matrix: np.ndarray, *, min_markets: int = 2) -> np.ndarray:
    """Equal-weight cross-market mean per date. NaN on dates with too few live markets.

    WHY A BOOK AND NOT A FLAT STACK. `axis_screen` z-scores over a trailing 20-period window and
    takes its own forward shift over the array it is handed. Concatenating M markets end to end
    puts a seam every T rows at which the z-window straddles two different markets and the forward
    shift pairs one market's signal with another's target -- 21 corrupted rows per seam, ~10% of a
    20-market panel, silently. Averaging cross-sectionally keeps ONE contiguous series with one
    clock, so every harness operation is exactly what it claims to be. Breadth then shows up where
    it honestly belongs: in the book's lower idiosyncratic noise, not in a manufactured n.

    Only scale-free constructions may be pooled this way; the caller enforces it.
    """
    m = np.asarray(matrix, dtype="float64")
    if m.ndim != 2 or m.size == 0:
        return np.zeros(0)
    ok = np.isfinite(m)
    cnt = ok.sum(axis=1)
    tot = np.where(ok, m, 0.0).sum(axis=1)
    out = np.full(m.shape[0], np.nan)
    live = cnt >= max(int(min_markets), 1)
    out[live] = tot[live] / cnt[live]
    return out
